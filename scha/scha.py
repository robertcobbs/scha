import logging
import binascii
import re

import tornado.ioloop

import paho.mqtt.client as mqtt

from snap_profile.profile import Profile
from snap_profile.network import Network
from snapstraction.gus import Gus


PI_IP = '10.10.10.10'
PI_USERNAME = 'your_username'
PI_PASSWORD = 'your_password'


logging.basicConfig(level=logging.INFO)


p = Profile.load('default')
n = Network.load(p.network)
gus = Gus(p, n, None)
gus.start()


def led_state(source, color, state, addr):
    topic = 'scha/' + binascii.hexlify(addr) + '/led/' + color + '/state'
    client.publish(topic, payload=str(state), retain=True)

gus.on_rpc('led_state', led_state)


def sensor_update(source, sensor_type, state, addr):
    topic = 'scha/' + binascii.hexlify(addr) + '/' + sensor_type + '/state'
    client.publish(topic, payload=str(state), retain=True)

gus.on_rpc('sensor_update', sensor_update)


def on_connect(client, userdata, flags, rc):
    print('MQTT client connect with result code ' + str(rc))
    client.subscribe('scha/#')

def on_message(client, userdata, msg):
    print(msg.topic + ' ' + str(msg.payload))
    if bool(re.search('led/.*/state/set', msg.topic)):
        node_addr = msg.topic.split('/')[1]
        color = msg.topic.split('/')[3]
        set_led(node_addr, color, msg.payload)


def set_led(node_addr, color, state):
    response = gus.callback_ucast_rpc(node_addr, 'set_led', color, state)
    print response


client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message
client.username_pw_set(PI_USERNAME, PI_PASSWORD)
client.connect(PI_IP, 1883, 60)
client.loop_start()


tornado.ioloop.IOLoop.current().start()
