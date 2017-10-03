#!/usr/bin/env python

from flask import Flask, request, Response
from flask_restful import Resource, Api
from pprint import pprint
from inspect import getmembers
import logging
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
db = client.watch

app = Flask(__name__)
api = Api(app)



def sendSms(msg):
    # status == 0: ENROUTE
    # status == 1: DELIVERED
    # status == 2: FAILED
    return modem.sendSms(msg["phone"], msg["body"])

class Send_SMS(Resource):
    def post(self):
        pprint('SendSMS: SMS Received')
        # Send SMS to Modem
        msg = request.get_json(silent=False, force=True)

        if "body" not in msg:
            return Response("{'error':'Missing\s body'}", status=400, mimetype='application/json')
        if "phone" not in msg:
            return Response("{'error':'Missing\s phone'}", status=400, mimetype='application/json')

        pprint('Json data in request OK!')
        sms = sendSms(msg)

        msg['retries'] = 0
        if sms.status == "2":
            pprint('Errors sending message!')
            db.queue.insert_one(msg)
            return Response("{'error':'Modem could not send message!'}", status=400, mimetype='application/json')
        elif sms.status == "0" or sms.status == "1":
            pprint('Message sent!')
            db.sent.insert_one(msg)
            return Response("{'body':'%s', 'phone':'%s'}" % (msg['body'], msg['phone']), status=200, mimetype='application/json')
        else:
            pprint('Message ERROR')
            return Response("{'error':'Could\s not\s parse\s data!'}", status=400, mimetype='application/json')

class Process_Queue(Resource):
    def get(self):
        pprint('ProcessQueeu: Request initialized')
        messages = db.queue.find({"retries": {"$lt": 4}})
        if messages is None:
            return True
        for msg in messages:
            sms = sendSms(msg)
            msg['retries'] = msg['retries'] + 1
            if sms.status == 2:
                pprint('Errors sending message!')
                db.sent.find_one_and_update({'_id': msg['_id']}, {"retries": msg['retries'] + 1})
            else:
                pprint('Message sent!')
                db.queue.find_one_and_delete({'_id': msg['_id']})
                db.sent.insert_one(msg)
        return True
 
api.add_resource(Send_SMS, '/sms')
api.add_resource(Process_Queue, '/queue')

if __name__ == '__main__':
    app.run('0.0.0.0')
