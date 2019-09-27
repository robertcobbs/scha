from snappyatmega.sensors import *

LED_RED = 7
LED_GREEN = 6

LED_RED_STATUS = 'OFF'
LED_GREEN_STATUS = 'OFF'

count = 0

@setHook(HOOK_STARTUP)
def startup_event():
    setPinDir(LED_GREEN, True)
    writePin(LED_GREEN, True)
    setPinDir(LED_RED, True)
    writePin(LED_RED, True)

@setHook(HOOK_1S)
def five_second_event():
    global count
    count += 1
    if count > 4:
        count = 0
        get_temp()
        get_voltage()

def set_led(color, state):
    if color == 'green':
        LED = LED_GREEN
    elif color == 'red':
        LED = LED_RED

    if state == 'ON':
        writePin(LED, False)
        mcastRpc(1, 2, 'led_state', localAddr(), color, 'ON')
    else:
        writePin(LED, True)
        mcastRpc(1, 2, 'led_state', localAddr(), color, 'OFF')

def get_temp():
    raw_temp = atmega_temperature_read_raw()
    temp_dC = atmega_temperature_raw_to_dC(raw_temp)
    mcastRpc(1, 2, 'sensor_update', localAddr(), 'temp', temp_dC)

def get_voltage():
    ps_mV = atmega_ps_voltage()
    mcastRpc(1, 2, 'sensor_update', localAddr(), 'voltage', ps_mV
