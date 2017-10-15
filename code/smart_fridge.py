#!/usr/bin/python
# coding=utf-8

import os
import time
import psycopg2
from slackclient import SlackClient
import requests
import urllib.request
import json

from watson_developer_cloud import VisualRecognitionV3

# smartfridge's ID as an environment variable
BOT_ID = os.environ.get("BOT_ID")

# Get key to request Food2fork API
FOOD2FORK_KEY=os.environ.get('FOOD2FORK_KEY')

SLACK_BOT_TOKEN=os.environ.get('SLACK_BOT_TOKEN')

# constants
AT_BOT = "<@" + BOT_ID + ">"
EXAMPLE_COMMAND = "do"

# Define our connection string
db_string_connection = "host='localhost' dbname='smartfridge' user='postgres' password='postgres'"


VISUAL_RECOGNITION_VERSION = '2017-10-15'
VISUAL_RECOGNITION_URL = 'https://gateway-a.watsonplatform.net/visual-recognition/api'
VISUAL_RECOGNITION_KEY = os.environ.get('VISUAL_RECOGNITION_KEY')

class SmartFridge():
    def __init__(self):
        #  instantiate Slack
        self.slack_client = SlackClient(SLACK_BOT_TOKEN)
        self.food2fork_key = FOOD2FORK_KEY
        self.database_cursor = None
        self.visual_recognition = VisualRecognitionV3(version=VISUAL_RECOGNITION_VERSION,
                                                      url=VISUAL_RECOGNITION_URL,
                                                      api_key=VISUAL_RECOGNITION_KEY)


    def getdbinformation(self):
        # execute our Query
        self.database_cursor.execute("SELECT name FROM products")

        # retrieve the records from the database
        records = self.database_cursor.fetchall()
        ingredients_fridge=[]
        for r in records:
            ingredients_fridge.append(r[0])
        return(','.join(map(str, ingredients_fridge)))


    def handle_command(self, command, channel):
        """
            Receives commands directed at the bot and determines if they
            are valid commands. If so, then acts on the commands. If not,
            returns back what it needs for clarification.
        """
        response = "Not sure what you mean. Use the *" + EXAMPLE_COMMAND + \
               "* command with numbers, delimited by spaces."

        # Get the command to the user (Ojo! sustituir por llamada a Watson conversation)
        if command.startswith('do'):
            response = "Sure...write some more code then I can do that!"
        elif command.startswith('db'):
            response=self.getdbinformation()
        elif command.startswith('photo'):
            with open('./download/food.jpg', 'rb') as image_file:
                vr_response = smartfridge.visual_recognition.classify(images_file=image_file,
                                                                      classifier_ids=['food'])

                if vr_response['images'] and len(vr_response['images'])>0:
                    image= vr_response['images'][0]
                    if image['classifiers'] and len(image['classifiers'])>0:
                        classifier=image['classifiers'][0]
                        if classifier['classes'] and len(classifier['classes'])>0:
                            food=classifier['classes'][0]['class']
                            score=classifier['classes'][0]['score']
                            response='This is... {0} (score: {1})'.format(food, score)

        # Provide response
        self.slack_client.api_call("chat.postMessage",
                                   channel=channel,
                                   text=response,
                                   as_user=True)


    def parse_slack_output(self, slack_rtm_output):
        """
            The Slack Real Time Messaging API is an events firehose.
            this parsing function returns None unless a message is
            directed at the Bot, based on its ID.
        """

        output_list = slack_rtm_output
        if output_list and len(output_list) > 0:
            for output in output_list:
                if output and 'text' in output and AT_BOT in output['text']:
                    # return text after the @ mention, whitespace removed
                    return output['text'].split(AT_BOT)[1].strip().lower(), output['channel']

                elif output and 'file' in output and 'url_private_download' in output['file']:
                    down_url = output['file']['url_private_download']
                    self.download_file(down_url, 'download/food.jpg', 'download')
                    return 'photo', output['channel']

        return None, None



    def database_connection(self):
        # print the connection string we will use to connect
        print('Connecting to database ... {}'.format(db_string_connection))

        # get a connection, if a connect cannot be made an exception will be raised here
        db_conn = psycopg2.connect(db_string_connection)

        # conn.cursor will return a cursor object, you can use this cursor to perform queries
        self.database_cursor = db_conn.cursor()

    def _urlHelper(self, endpoint, **kwargs):
        data = {'key': self.food2fork_key}

        for key, value in kwargs.items():
            data[key] = value

        return endpoint + '?' + urllib.parse.urlencode(data)


    def recipes_by_ingredients(self, query):
        endpoint = 'http://food2fork.com/api/search'
        url = self._urlHelper(endpoint, q=query)
        print(url)
        return requests.get(url).json()


    def download_file(self, url, local_filename, basedir):
        try:
            os.stat(basedir)
        except:
            os.mkdir(basedir)
        try:
            print('Savigng to {}'.format(local_filename))
            headers = {'Authorization': 'Bearer '+ os.environ.get('SLACK_BOT_TOKEN')}
            r = requests.get(url, headers=headers)
            with open(local_filename, 'wb') as f:
                for chunk in r.iter_content(chunk_size=1024):
                    if chunk:
                        f.write(chunk)
        except:
            return False

        return True

if __name__ == "__main__":
    smartfridge=SmartFridge()
    smartfridge.database_connection()

    ingredients='chicken, tomatoes, cheese, onion, egg'
    recipes=smartfridge.recipes_by_ingredients(ingredients)['recipes']

    for i, recipe in enumerate(recipes):
        print('[{0}] : {1}'.format(i+1, recipe['title']))


    READ_WEBSOCKET_DELAY = 1 # 1 second delay between reading from firehose
    if smartfridge.slack_client.rtm_connect():
        print("smartfridge connected and running!")
        while True:
            command, channel = smartfridge.parse_slack_output(smartfridge.slack_client.rtm_read())
            if command and channel:
                smartfridge.handle_command(command, channel)
            time.sleep(READ_WEBSOCKET_DELAY)
    else:
        print("Connection failed. Invalid Slack token or bot ID?")
