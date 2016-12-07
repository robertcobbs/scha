# Copyright (C) 2016 Synapse Wireless, Inc.
"""Reed Switch script SN171 protoboard - status to E20"""

from synapse.platforms import *
from synapse.pinWakeup import *

if platform[:3] == ('RF2' or 'SM2'):
    SLEEP_MODE = 2
else:
    SLEEP_MODE = 0

# I/O Pins
BUTTON = GPIO_5    # active low switch input
LED2_YLW = GPIO_2
LED1_GRN = GPIO_1
REED = GPIO_0

INITIAL_WAKE_COUNT = 5  # seconds to stay awake upon boot
wake_counter = INITIAL_WAKE_COUNT

second_count = 0
button_count = 0
sleep_allowed = True
last_buffer = -1

@setHook(HOOK_STARTUP)
def init():
    """Startup initialization."""
    # Init LEDs
    setPinDir(LED1_GRN, True)
    setPinDir(LED2_YLW, True)
    pulsePin(LED2_YLW, 500, True)
    writePin(LED1_GRN, True)

    # Init button
    setPinDir(BUTTON, False)
    setPinPullup(BUTTON, True)
    monitorPin(BUTTON, True)

    # Init reed switch
    setPinDir(REED, False)
    setPinPullup(REED, True)
    monitorPin(REED, True)
    wakeupOn(REED, True, False)

@setHook(HOOK_1S)
def tick1sec():
    """This exists so that the node can be told to stay awake at boot"""
    global wake_counter
    if wake_counter == 0:
        if sleep_allowed:
            writePin(LED1_GRN, False)
            sleep(SLEEP_MODE, 0)  # Untimed sleep
        wake_counter = -1
    if wake_counter > 0:
        wake_counter -= 1

@setHook(HOOK_GPIN)
def pin_event(pin, is_set):
    """Pin change event handler."""
    global wake_counter
    writePin(LED1_GRN, True)
    if pin == REED and is_set:
        reed_update('Closed')
    if pin == REED and not is_set:
        reed_update('Open')
    if pin == BUTTON and is_set:
        # If the button is pressed, toggle sleep state
        report_button_count()
        if sleep_allowed:
            sleep_prevent()
        else:
            sleep_allow()

@setHook(HOOK_RPC_SENT)
def _onSent(whichBuffer):
    global last_buffer, wake_counter
    if whichBuffer == last_buffer:
        # Done sending RPC. Yay! Go back to sleep.
        last_buffer = -1
        if sleep_allowed:
            wake_counter = 0

def reed_update(state):
    """Broadcast a RPC on reed switch state change."""
    global last_buffer
    pulsePin(LED2_YLW, 50, True)
    mcastRpc(1, 2, 'sensor_update', 'reed_switch', state, localAddr())
    last_buffer = getInfo(9)

def sleep_prevent():
    # Call this function to keep the node awake
    global sleep_allowed, wake_counter
    sleep_allowed = False

def sleep_allow():
    # Call this function to allow the node to sleep
    global  sleep_allowed, wake_counter
    sleep_allowed = True
    wake_counter = 0

def get_sleep_allowed():
    return sleep_allowed

def report_button_count():
    """Broadcast a status RPC."""
    global button_count
    button_count += 1
    mcastRpc(1, 2, 'set_button_count', button_count, localAddr())
