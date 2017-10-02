#!/usr/bin/env python

from flask import Flask, request
from flask_restful import Resource, Api
import logging
import serial
import time
from pymongo import MongoClient

PORT = '/dev/ttyUSB0'
BAUDRATE = 115200
PIN = None

from gsmmodem.modem import GsmModem

print('Initializing modem...')

logging.basicConfig(format='%(levelname)s: %(message)s', level=logging.DEBUG)
modem = GsmModem(PORT, 115200)
modem.smsTextMode = False
modem.connect(PIN)

print('Connect to MongoDB')
# Define mongo 
client = MongoClient()
db = client.deepa

app = Flask(__name__)
api = Api(app)

def sendSms(msg):
    sms = modem.sendSms(msg['phone'], msg['body'])
    # Now check what SMS contains and define failed message!
    print(sms)
    return sms

class Send_SMS(Resource):
    def post(self):
        print('SendSMS: SMS Received')
        # Send SMS to Modem
        msg = request.get_json(silent=False, force=True)
        sms = sendSms(msg)
        msg['retries'] = 0
        if sms is True:
            print('Message sent!')
            db.sent.insert_one(msg)
        else:
            print('Errors sending message!')
            # if SMS Error sending
            db.queue.insert_one(msg)
        return msg['body']

class Process_Queue(Resource):
    def get(self):
        print('ProcessQueeu: Request initialized')
        messages = db.queue.find({"retries": {"$lt": 4}})
        if messages is None:
            return True
        for msg in messages:
            sms = sendSms(msg)
            msg['retries'] = msg['retries'] + 1
            if sms is True:
                print('Message sent!')
                db.queue.find_one_and_delete({'_id': msg['_id']})
                db.sent.insert_one(msg)
            else:
                print('Errors sending message!')
                db.sent.find_one_and_update({'_id': msg['_id']}, {"retries": msg['retries'] + 1})
        return True
 
api.add_resource(Send_SMS, '/sms')
api.add_resource(Process_Queue, '/queue')

if __name__ == '__main__':
    app.run('0.0.0.0')
