#!/usr/bin/env python

from flask import Flask, request
from flask_restful import Resource, Api
from pprint import pprint
import logging
import serial
import time
from pymongo import MongoClient

PORT = '/dev/ttyUSB0'
BAUDRATE = 115200
PIN = None

from gsmmodem.modem import GsmModem

pprint('Initializing modem...')

logging.basicConfig(format='%(levelname)s: %(message)s', level=logging.DEBUG)
modem = GsmModem(PORT, 115200)
modem.smsTextMode = False
modem.connect(PIN)

pprint('Connect to MongoDB')
# Define mongo 
client = MongoClient()
db = client.deepa

app = Flask(__name__)
api = Api(app)



def sendSms(msg):
    sms = modem.sendSms(msg['phone'], msg['body'])
    # Now check what SMS contains and define failed message!
    # sms.status == 0: ENROUTE
    # sms.status == 1: DELIVERED
    # sms.status == 2: FAILED
    pprint(sms)
    return sms

class Send_SMS(Resource):
    def post(self):
        pprint('SendSMS: SMS Received')
        # Send SMS to Modem
        msg = request.get_json(silent=False, force=True)
        sms = sendSms(msg)
        msg['retries'] = 0  
        if sms.status == "1":
            pprint('Message sent!')
            db.sent.insert_one(msg)
        if sms.status == "2":
            pprint('Errors sending message!')
            # if SMS Error sending
            db.queue.insert_one(msg)
        else:
            pprint('SMS ENROUTE! Not sent nor failed, yet finished? WTF?')
        return msg['body']

class Process_Queue(Resource):
    def get(self):
        pprint('ProcessQueeu: Request initialized')
        messages = db.queue.find({"retries": {"$lt": 4}})
        if messages is None:
            return True
        for msg in messages:
            sms = sendSms(msg)
            msg['retries'] = msg['retries'] + 1
            if sms.status == 1:
                pprint('Message sent!')
                db.queue.find_one_and_delete({'_id': msg['_id']})
                db.sent.insert_one(msg)
            else:
                pprint('Errors sending message!')
                db.sent.find_one_and_update({'_id': msg['_id']}, {"retries": msg['retries'] + 1})
        return True
 
api.add_resource(Send_SMS, '/sms')
api.add_resource(Process_Queue, '/queue')

if __name__ == '__main__':
    app.run('0.0.0.0')
