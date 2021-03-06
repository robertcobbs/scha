"""Low-power motion monitoring script for the Synapse Wireless LightSense."""
DS_PACKET_SERIAL = 6
DS_NULL = 0

LS_VERSION = "v2.0.0"

# If the LSP module is installed, set this to true to get more sensor data:
IS_LSPLUS = False

# I/O
LED_PIN = 4       # Active low LED
BUTTON_PIN = 5    # Active low button
MOTION_PIN = 6

# Active-high enable pins
MOTION_EN = 7
TEMPERATURE_EN = 9
VREF_EN = 10
LIGHT_EN = 12

# Sensor ADC channels
VREF_CH = 3
TEMPERATURE_CH = 0
LIGHT_CH = 5

# LSP (LightSensePlus module) parameters
LSP_I2C_ADDRESS = 0x27 << 1  # I2C address of the Honeywell HumidIcon
STALE_MASK = 0x40  # Bitmask for the "stale" data bit status flag
HI_HUMID_MASK = 0x3f  # Bitmask for the 'hi' humidity data byte
I2C_RETRIES = 3

STARTUP_DELAY = 10  # Seconds to wait after powered on before starting
seconds_since_startup = 0

# Device states
ST_WAIT_NEW_MOTION = 0  # Asleep, waiting for new motion or report period
ST_WAIT_DEADBAND = 1    # Asleep, waiting on post-motion deadband expiry
ST_WAIT_STILL = 2       # Asleep, waiting on motion or stillness expiry
ST_INIT = 3             # Awake, initial boot delay

# Report types
RT_MOTION = "motion"
RT_STILL = "still"

# FSM driver Events
EV_MOTION = 0
EV_EXPIRY = 1
EV_RPTSENT = 2

mcast_group = 1
mcast_ttl = 5

# Configurable Motion timers
MOTION_DEADBAND = 1        # Seconds after motion event before re-arming
MOTION_STILLNESS = 60      # Seconds armed before declaring "stillness"
STILL_REPORT_PERIOD = 120  # Seconds to wait before re-sending "still" message
PIR_SETTLE_TIME = 5        # Seconds to wait for the PIR to settle after enabling

device_state = ST_INIT
current_rpc_buffer = None

# Raw sensor values
batt = 0
photo = 0
temperature = 0
humidity = 0

initialized = False


def _read_battery():
    """Returns the current battery voltage in mV."""
    writePin(VREF_EN, True)
    batt_val = readAdc(VREF_CH)
    writePin(VREF_EN, False)
    return ((30690/batt_val)*100)/3  # Convert to mV


def _read_photocell():
    """Returns the current average photocell value."""
    writePin(LIGHT_EN, True)
    i = 0
    total_sum = 0
    while i < 32:  # Average reading
        if i > 1:  # Throw away first couple
            total_sum += readAdc(LIGHT_CH)
        i += 1
    photo_val = total_sum/(i-2)
    writePin(LIGHT_EN, False)
    return photo_val


def _read_temperature():
    """Returns the current average temperature value."""
    writePin(TEMPERATURE_EN, True)
    i = 0
    total_sum = 0
    while i < 32:  # Average reading
        if i > 1:  # Throw away first couple
            total_sum += readAdc(TEMPERATURE_CH)
        i += 1
    temperature_val = total_sum/(i-2)
    writePin(TEMPERATURE_EN, False)
    return temperature_val


def _read_lsp():
    i2cWrite(chr(LSP_I2C_ADDRESS), I2C_RETRIES, False)
    sleep(1,1)
    read_address = chr(LSP_I2C_ADDRESS | 1)
    lsp_data = i2cRead(read_address, 4, I2C_RETRIES, False)
    return lsp_data


def _update_sensors():
    """Reads all three sensors and stores their values."""
    global batt, photo, temperature, humidity

    batt = _read_battery()
    photo = _read_photocell()
    if IS_LSPLUS:
        lsp_data = _read_lsp()
        if lsp_data is None or len(lsp_data) != 4:
            humidity = "BROKEN"
            temperature = "None"
        else:
            humidity = ((ord(lsp_data[0]) & HI_HUMID_MASK) << 8) + ord(lsp_data[1])
            temperature = ((ord(lsp_data[2]) << 8) + ord(lsp_data[1]) >> 2)
    else:
        temperature = _read_temperature()


def _send_report(report_type):
    """Sends and ls_report message containing motion and sensor values."""
    global current_rpc_buffer

    _update_sensors()
    writePin(LED_PIN, False)
    if IS_LSPLUS:
        mcastRpc(mcast_group, mcast_ttl, "lsp_report", localAddr(), LS_VERSION, batt, photo, temperature, humidity, report_type)
    else:
        mcastRpc(mcast_group, mcast_ttl, "ls_report", localAddr(), LS_VERSION, batt, photo, temperature, report_type)
    current_rpc_buffer = getInfo(9)


def _fsm(event):
    """Kicks off the finite state machine logic loop."""
    global device_state

    while event is not None:

        # State Machine
        if device_state == ST_INIT:
            writePin(LED_PIN, True)
            device_state = ST_WAIT_NEW_MOTION
            _monitor_motion(True)
            event = _sleep(STILL_REPORT_PERIOD)
        elif device_state == ST_WAIT_NEW_MOTION:
            # Waiting for motion to occur
            if event == EV_EXPIRY:
                _send_report(RT_STILL)   # Gratuitous periodic report
                event = None
            elif event == EV_MOTION:
                device_state = ST_WAIT_DEADBAND
                _monitor_motion(False)
                _send_report(RT_MOTION)   # Report new motion immediately
                event = None
            elif event == EV_RPTSENT:
                event = _sleep(STILL_REPORT_PERIOD)
        elif device_state == ST_WAIT_DEADBAND:
            # Motion detector disabled, waiting for deadband timer
            if event == EV_EXPIRY:
                # Deadband has expired; reenable motion detect and wait for stillness
                _monitor_motion(True)
                device_state = ST_WAIT_STILL
                event = _sleep(MOTION_STILLNESS)
            elif event == EV_MOTION:
                reboot()   # Should never happen!
            elif event == EV_RPTSENT:
                event = _sleep(MOTION_DEADBAND)
        elif device_state == ST_WAIT_STILL:
            if event == EV_EXPIRY:
                device_state = ST_WAIT_NEW_MOTION
                _send_report(RT_STILL)   # Report stillness
                event = None
            elif event == EV_MOTION:
                device_state = ST_WAIT_DEADBAND
                _monitor_motion(False)
                _send_report(RT_MOTION)   # Report new motion
                event = None
            elif event == EV_RPTSENT:
                reboot()   # Should never happen!


def _sleep(time):
    """Sleep for an amount of time, and report event based on early wake."""
    rx(False)  # Radio remains off until next tx

    ticks_remain = sleep(0, time)
    return EV_EXPIRY if ticks_remain == 0 else EV_MOTION


@setHook(HOOK_RPC_SENT)
def _report_sent(buf_ref):
    """Kick off the FSM after an RPC has been sent."""
    global current_rpc_buffer

    # Don't run through the state machine until after startup period
    if initialized:
        writePin(LED_PIN, True)
        if buf_ref == current_rpc_buffer:
            current_rpc_buffer = None
            _fsm(EV_RPTSENT)


@setHook(HOOK_100MS)
def _tick100ms(ticks):
    """Blinks LED during awake-init time."""
    if not initialized:
        pulsePin(LED_PIN, 50, False)


@setHook(HOOK_1S)
def _tick1s():
    """Counts down the awake-init time."""
    global initialized, seconds_since_startup

    if not initialized and seconds_since_startup > STARTUP_DELAY:
        initialized = True
        _init()
    else:
        seconds_since_startup += 1


@setHook(HOOK_STARTUP)
def _startup():
    """Makes sure LED is off on boot."""
    # Turn LED off
    writePin(LED_PIN, True)


def _init():
    """Initializes the device for low power consumption."""
    # No PacketSerial connection
    crossConnect(DS_PACKET_SERIAL, DS_NULL)

    # Default all pins to output/low for minimum power consumption
    _set_pins_low_power()

    if IS_LSPLUS:
        i2cInit(True)

    # Precharge ADC
    _update_sensors()

    # Enable inputs
    setPinDir(BUTTON_PIN, False)
    setPinDir(MOTION_PIN, False)

    _monitor_motion(True)

    writePin(LED_PIN, True)

    # Kickoff FSM
    _fsm(EV_EXPIRY)


def _set_pins_low_power():
    """Sets all pins to low outputs for power savings."""
    pin = 0
    while pin <= 32:
        setPinDir(pin, True)
        writePin(pin, False)
        pin += 1


def _monitor_motion(do_monitor):
    """Sets or unsets the motion sensor's pin monitoring."""
    writePin(MOTION_EN, do_monitor)

    if do_monitor:
        # When enabling motion detector, must allow settling time
        sleep(0, PIR_SETTLE_TIME)  # Simple sleep, don't call _sleep()!
        poke(0x16, peek(0x16) | 0x40)  # Wake on rising edge
        poke(0x17, peek(0x17) | 0x40)
    else:
        poke(0x16, peek(0x16) & ~0x40)
        poke(0x17, peek(0x17) & ~0x40)
