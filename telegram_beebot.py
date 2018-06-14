#!/usr/bin/python3 -u

# pip3 install -r requirements.txt
# to install requireed packages

import telegram
from telegram.ext import Updater
from telegram.ext import CommandHandler
from telegram.ext import MessageHandler, Filters
from ttn import MQTTClient as ttn_mqtt
import paho.mqtt.client as hiveeyes_mqtt
from configparser import RawConfigParser
import os
import logging
import time
import pytz
import datetime
import base64
from random import randint
import json
import collections
from dateutil import parser
from math import ceil
import math
from Sun import Sun

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

config = RawConfigParser()
config.read('config')

telegram_bot_token = config.get('Telegram', 'telegram_bot_token')

ttn_app_id = config.get('TTN', 'ttn_app_id')
ttn_key = config.get('TTN', 'ttn_key')
ttn_mqtt_address = config.get('TTN', 'ttn_mqtt_address')
ttn_device_base = config.get('TTN', 'ttn_device_base')
ttn_weight_var = config.get('TTN', 'ttn_weight_var')
ttn_battery_var = config.get('TTN', 'ttn_battery_var')

hiveeyes_mqtt_user = config.get('Hiveeyes', 'hiveeyes_mqtt_user')
hiveeyes_mqtt_pw = config.get('Hiveeyes', 'hiveeyes_mqtt_pw')
hiveeyes_address = config.get('Hiveeyes', 'hiveeyes_address')
hiveeyes_port = config.getint('Hiveeyes', 'hiveeyes_port')
hiveeyes_data_topic = config.get('Hiveeyes', 'hiveeyes_data_topic')
hiveeyes_data_topic_json_valid = config.get('Hiveeyes', 'hiveeyes_data_topic_json_valid')
hiveeyes_events_topic = config.get('Hiveeyes', 'hiveeyes_events_topic')
hiveeyes_weight_attr_valid = config.get('Hiveeyes', 'hiveeyes_weight_attr_valid')
hiveeyes_battery_attr_valid = config.get('Hiveeyes', 'hiveeyes_battery_attr_valid')

grafana_dashboard_base_url = config.get('Grafana', 'grafana_dashboard_base_url')
grafana_dashboard_today_url = config.get('Grafana', 'grafana_dashboard_today_url')
grafana_dashboard_totaytotal_url = config.get('Grafana', 'grafana_dashboard_todaytotal_url')
grafana_dashboard_yesterday_url = config.get('Grafana', 'grafana_dashboard_yesterday_url')
grafana_dashboard_7days_url = config.get('Grafana', 'grafana_dashboard_7days_url')

timezone = pytz.timezone(config.get('Other', 'timezone'))
coords = {'longitude' : config.getint('Other', 'longitude'), 'latitude' : config.getint('Other', 'latitude') }

# init some global variables
weight    = {}
battery   = {}
time_data = {}
sunset_today = {}

weight_1 = 0.0
time_data_1 = datetime.datetime.now().strftime('%d.%m. %H:%M')
battery_1 = 0.0

custom_schedule = False

print ('Starting Telegram BeeBot')

bot = telegram.Bot(token=telegram_bot_token)

updater = Updater(token=telegram_bot_token, request_kwargs={'read_timeout': 20, 'connect_timeout': 200})

dispatcher = updater.dispatcher

updater.start_polling()

def get_sunset_time():
    global sunset_today
    sun = Sun()
    sunset = sun.getSunsetTime( coords )
    sunset_time = str(sunset['hr']) + ':' + str(int(sunset['min'])) + ' UTC'
    sunset_time_local = parser.parse(sunset_time).astimezone(timezone)
    sunset_time_local_hr  = int(sunset_time_local.strftime('%H'))
    sunset_time_local_min = int(sunset_time_local.strftime('%M'))
    sunset_today = { 'hr' : sunset_time_local_hr , 'min' : sunset_time_local_min }
    return sunset_today

def print_daily(bot, job):
    global sunset_today
    global weight_1
    global custom_schedule

    get_sunset_time()
    time_update_daily = datetime.time(sunset_today['hr'],sunset_today['min'])

    filename = 'weight_1_yesterday.txt'
    if os.path.exists(filename) and os.path.getsize(filename) > 0:
        f = open(filename,'r+')
        weight_1_yesterday = float(f.read())
        if weight_1 == 0.0:
            weight_1 = weight_1_yesterday
    else:
        f = open(filename,'w')
        weight_1_yesterday = weight_1

    f.seek(0)
    f.truncate()
    f.write(str(weight_1))
    f.close()

    weight_1_dailydiff = weight_1 - weight_1_yesterday

    message = '*Daily summary*\nWeight Hive 1 : `' + str('{0:05.2f}'.format(weight_1)) + 'kg`  ( `' + \
              str('{0:+.0f}'.format(weight_1_dailydiff * 1000)) + 'g` )\n' + \
              'Sunset at ' + str(sunset_today['hr']) + ':' + str(sunset_today['min'])

    if not custom_schedule:
        for jobs in job.job_queue.get_jobs_by_name('daily_summary'):
            job.schedule_removal()

        print('update daily job to sunset time')
        job.job_queue.run_daily(print_daily, time_update_daily, context=job.context, name = 'daily_summary')
        message = message + ' (updated)'

    bot.send_message(chat_id=job.context, text=message, parse_mode='Markdown')

    image_url = grafana_dashboard_base_url + \
                grafana_dashboard_today_url + \
                '&dummy=' + str(randint(0, 10000000))

    bot.send_photo(chat_id=job.context, photo=image_url)

def enable_daily(bot,update,job_queue,args):
    global sunset_today
    global custom_schedule

    get_sunset_time()

    if len(args) == 2:
        custom_schedule = True
        time_update_daily = datetime.time(int(args[0]),int(args[1]))
        message = 'Setting a daily timer for summary at ' + time_update_daily.strftime('%H:%M')
    else:
        custom_schedule = False
        time_update_daily = datetime.time(sunset_today['hr'],sunset_today['min'])
        message = 'Setting timer with todays sunset time for summary at '+ str(sunset_today['hr']) + ':' + str(sunset_today['min']) + \
                  '. Give hour and minute for another time, e.g. /enable_daily 20 15'

    for job in job_queue.get_jobs_by_name('daily_summary'):
        job.schedule_removal()

    print('add daily job')    
    job_queue.run_daily(print_daily, time_update_daily, context=update.message.chat_id, name = 'daily_summary')

    bot.send_message(chat_id=update.message.chat_id,text=message)

enable_daily_handler = CommandHandler('enable_daily', enable_daily, pass_job_queue=True, pass_args=True)
dispatcher.add_handler(enable_daily_handler)

def event(bot, update, args):
    if len(args) > 0:
        text=' '.join(args[1:])
        MQTT_MSG=json.dumps({'eventtitle': args[0], 'text': text})
        hiveeyes_client.publish(hiveeyes_events_topic, MQTT_MSG)

event_handler = CommandHandler('event', event, pass_args=True)
dispatcher.add_handler(event_handler)

# specific to thias' TTN device setup
def sleep(bot, update, args):
    if len(args) == 2:
        device = ttn_device_base + args[0]
        # convert to minutes as Adafruit Feather M0 LoRa watchdog sleep cycle lasts about 8s
        payload_int = int(args[1]) * 7 
        payload = base64.b64encode(payload_int.to_bytes(ceil(payload_int.bit_length()/8),'big')).decode()
        message = 'unit *' + device + '* should sleep for about ' + args[1] + ' minutes (after next uplink)'
        ttn_client.connect()
        ttn_client.send(device, payload, port=1, conf=True)
    else:
        message = 'wrong number of arguments. Use first number for device and second for sleep duration in minutes, eg. /sleep 2 10'

    bot.send_message(chat_id=update.message.chat_id, text=message, parse_mode='Markdown')

sleep_handler = CommandHandler('sleep', sleep, pass_args=True)
dispatcher.add_handler(sleep_handler)

def weights(bot, update):
    global weight_1

    filename = 'weight_1_old.txt'
    if os.path.exists(filename) and os.path.getsize(filename) > 0:
        f = open(filename,'r+')
        weight_1_old = float(f.read())
        if weight_1 == 0.0:
            weight_1 = weight_1_old
    else:
        f = open(filename,'w')
        weight_1_old = weight_1

    f.seek(0)
    f.truncate()
    f.write(str(weight_1))
    f.close()

    weight_1_diff = weight_1 - weight_1_old
    message = 'Hive 1 : `' + str('{0:05.2f}'.format(weight_1)) + 'kg`  ( `' + \
              str('{0:+.0f}'.format(weight_1_diff * 1000)) + 'g` ) \[ ' + \
              str(time_data_1) + ' ]\n' + \
              '/today1 /todaytotal1 /yesterday1 /sevendays1\n'
    bot.send_message(chat_id=update.message.chat_id, text=message, parse_mode='Markdown')

weights_handler = CommandHandler('weights', weights, pass_args=False)
dispatcher.add_handler(weights_handler)

def batteries(bot, update):
    message = 'Hive 1 : `' + str('{0:04.2f}'.format(battery_1)) + 'V`\n'
    bot.send_message(chat_id=update.message.chat_id, text=message, parse_mode='Markdown')

batteries_handler = CommandHandler('batteries', batteries, pass_args=False)
dispatcher.add_handler(batteries_handler)

# pull graphics from Grafana funtions
def today1(bot, update):
    image_url = grafana_dashboard_base_url + \
                grafana_dashboard_today_url + \
                '&dummy=' + str(randint(0, 10000000))
    bot.send_photo(chat_id=update.message.chat_id, photo=image_url)
    
today1_handler = CommandHandler('today1', today1, pass_args=False)
dispatcher.add_handler(today1_handler)

def todaytotal1(bot, update):
    image_url = grafana_dashboard_base_url + \
                grafana_dashboard_totaytotal_url + \
                '&dummy=' + str(randint(0, 10000000))
    bot.send_photo(chat_id=update.message.chat_id, photo=image_url)

todaytotal1_handler = CommandHandler('todaytotal1', todaytotal1, pass_args=False)
dispatcher.add_handler(todaytotal1_handler)

def yesterday1(bot, update):
    image_url = grafana_dashboard_base_url + \
                grafana_dashboard_yesterday_url + \
                '&dummy=' + str(randint(0, 10000000))
    bot.send_photo(chat_id=update.message.chat_id, photo=image_url)

yesterday1_handler = CommandHandler('yesterday1', yesterday1, pass_args=False)
dispatcher.add_handler(yesterday1_handler)

def sevendays1(bot, update):
    image_url = grafana_dashboard_base_url + \
                grafana_dashboard_7days_url + \
                '&dummy=' + str(randint(0, 10000000))
    bot.send_photo(chat_id=update.message.chat_id, photo=image_url)

sevendays1_handler = CommandHandler('sevendays1', sevendays1, pass_args=False)
dispatcher.add_handler(sevendays1_handler)

# TTN MQTT callbacks
def connect_callback(res, client):
    print('Connected to ' + ttn_mqtt_address + ' with result code:', res)

def uplink_callback(msg, client):
    global ttn_device_base
    device_num = msg.dev_id.split(ttn_device_base)[1]
    print('Received TTN uplink from', ttn_device_base + device_num)

def downlink_callback(mid, client):
    print('Sending downlink #', mid)

# Hiveeyes MQTT callbacks
def on_connect(hiveeyes_client, userdata, flags, rc):
    print('Connected to ' + hiveeyes_address + ':' + str(hiveeyes_port) + ' with result code ' + str(rc))

def on_message(hiveeyes_client, userdata, msg):
    global weight_1
    global battery_1
    global time_data_1
    time_data_1 = datetime.datetime.now().strftime('%d.%m. %H:%M')
    topic_last  = msg.topic.rsplit('/', 1)[-1]
    if 'analog_in' in topic_last:
        # here, expect CayenneLPP encoded MQTT data from TTN where weight and battery data is sent with data type analog_in_[port] 
        port  = topic_last.split('_')[-1]
        sensor_value = float(msg.payload)
        if port == '1':
            weight_1 = sensor_value
        if port == '3':
            battery_1 = sensor_value
        print(msg.topic + ' : ' + str(sensor_value))
    elif topic_last in hiveeyes_data_topic_json_valid:
        # here, expect JSON object
        payload = json.loads(msg.payload.decode('utf-8'))
        for attr, value in payload.items():
            if attr in hiveeyes_weight_attr_valid:
                # convert [g] to [kg]
                if value >= 1000:
                    weight_1 = value / 1000
                else:
                    weight_1 = value
                print(msg.topic + ' ' + attr + ': ' + str(weight_1))
            elif attr in hiveeyes_battery_attr_valid:
                # convert [mV] to [V]
                if value >= 1000:
                    battery_1 = value / 1000
                else:
                    battery_1 = value
                print(msg.topic + ' ' + attr + ': ' + str(battery_1))

    # ToDo: Handle multiple devices per MQTT Topic -> replace weight_1 with weight[device]
    #    weight[device]    = weight_1
    #    battery[device]   = battery_1
    #    time_data[device] = time_data_1

def on_log(client, userdata, level, buf):
    print('log: ',buf)

def on_subscribe(client, userdata, mid, granted_qos):
    print('Subscribed to the topic ' + hiveeyes_data_topic + ' from broker ' + hiveeyes_address + ' '+str(granted_qos))

def on_publish(client,userdata,result):
    print('event data published')

# TTN MQTT init
if ttn_app_id and ttn_key and ttn_mqtt_address:
    ttn_client = ttn_mqtt(ttn_app_id, ttn_key, mqtt_address=ttn_mqtt_address)
    ttn_client.set_connect_callback(connect_callback)
    ttn_client.set_uplink_callback(uplink_callback)
    ttn_client.set_downlink_callback(downlink_callback)
    ttn_client.connect()
else:
    print('TTN MQTT not configured.')

# Hiveeyes MQTT init
if hiveeyes_address:
    hiveeyes_client = hiveeyes_mqtt.Client('Telegram Bot')
    if hiveeyes_mqtt_user and hiveeyes_mqtt_pw:
        hiveeyes_client.username_pw_set(hiveeyes_mqtt_user, hiveeyes_mqtt_pw)
    hiveeyes_client.on_connect    = on_connect
    hiveeyes_client.on_message    = on_message
    hiveeyes_client.on_subscribe  = on_subscribe
    hiveeyes_client.on_publish    = on_publish
    #hiveeyes_client.on_log        =  on_log
    hiveeyes_client.connect(hiveeyes_address, hiveeyes_port)
    hiveeyes_client.subscribe(hiveeyes_data_topic)
    hiveeyes_client.loop_start()

else:
    print('Hiveeyes MQTT not configured.')
