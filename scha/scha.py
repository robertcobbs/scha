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


node_report_intervals = {}
seconds_since_last_message = {}


def led_state(source, addr, color, state):
    topic = 'scha/' + binascii.hexlify(addr) + '/led/' + color + '/state'
    client.publish(topic, payload=str(state), retain=True)

gus.on_rpc('led_state', led_state)


def sensor_update(source, addr, sensor_type, state):
    topic = 'scha/' + binascii.hexlify(addr) + '/' + sensor_type + '/state'
    client.publish(topic, payload=str(state), retain=True)

gus.on_rpc('sensor_update', sensor_update)


def rm150_rpt(source, addr, report_interval, last_amb_temp, last_amb_humid, last_ext1, last_ext2):
    node_report_intervals[addr] = report_interval
    seconds_since_last_message[addr] = 0

    topic = 'scha/' + binascii.hexlify(addr) + '/status'
    client.publish(topic, payload='online', retain=True)

    # Publish updates
    topic = 'scha/' + binascii.hexlify(addr) + '/report_interval'
    client.publish(topic, payload=str(report_interval), retain=False)

    topic = 'scha/' + binascii.hexlify(addr) + '/ambient_temp'
    client.publish(topic, payload=str(last_amb_temp), retain=False)

    topic = 'scha/' + binascii.hexlify(addr) + '/ambient_humidity'
    client.publish(topic, payload=str(last_amb_humid), retain=False)

    topic = 'scha/' + binascii.hexlify(addr) + '/probe1'
    client.publish(topic, payload=str(last_ext1), retain=False)

    topic = 'scha/' + binascii.hexlify(addr) + '/probe2'
    client.publish(topic, payload=str(last_ext2), retain=False)

gus.on_rpc('rm150_rpt', rm150_rpt)


def ls_report(source, addr, ls_version, batt, photo, temperature, report_type)
    topic = 'scha/' + binascii.hexlify(addr) + '/' + 'motion/state'
    client.publish(topic, payload=str(report_type), retain=True)

gus.on_rpc('ls_report', ls_report)


def last_message_timeout():
    for addr in seconds_since_last_message:
        seconds_since_last_message[addr] += 1
        if seconds_since_last_message[addr] > (node_report_intervals[addr] * 3):
            topic = 'scha/' + binascii.hexlify(addr) + '/status'
            client.publish(topic, payload='offline', retain=False)


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
client.tls_set_context()
client.connect(BROKER_HOST, BROKER_PORT, 60)
client.loop_start()

task = tornado.ioloop.PeriodicCallback(last_message_timeout, 1000)
task.start()

tornado.ioloop.IOLoop.current().start()
