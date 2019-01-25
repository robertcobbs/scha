import logging
import binascii
import re

import tornado.ioloop

import paho.mqtt.client as mqtt

from snap_profile.profile import Profile
from snap_profile.network import Network
from snapstraction.gus import Gus

import creds


BROKER_HOST = creds.HOST
BROKER_USERNAME = creds.USERNAME
BROKER_PASSWORD = creds.PASSWORD
BROKER_PORT = 8883


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
client.username_pw_set(BROKER_USERNAME, BROKER_PASSWORD)
client.connect(BROKER_HOST, BROKER_PORT, 60)
client.loop_start()


tornado.ioloop.IOLoop.current().start()
