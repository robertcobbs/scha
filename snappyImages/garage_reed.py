from synapse.platforms import *
from synapse.pinWakeup import *

if platform[:3] == ('RF2' or 'SM2'):
    SLEEP_MODE = 2
else:
    SLEEP_MODE = 0

# I/O Pins
if platform[:3] == 'RF2':
    REED = GPIO_0
elif platform[:3] == 'SM2':
    REED = GPIO_F1

INITIAL_WAKE_COUNT = 5  # seconds to stay awake upon boot
wake_counter = INITIAL_WAKE_COUNT

sleep_allowed = True
last_buffer = -1


@setHook(HOOK_STARTUP)
def init():
    """Startup initialization."""
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
            sleep(SLEEP_MODE, 0)  # Untimed sleep
        wake_counter = -1
    if wake_counter > 0:
        wake_counter -= 1


@setHook(HOOK_GPIN)
def pin_event(pin, is_set):
    """Pin change event handler."""
    global wake_counter
    if pin == REED and is_set:
        reed_update('Closed')
    if pin == REED and not is_set:
        reed_update('Open')


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
