#!/usr/bin/python
# coding=utf-8

import pprint
import os
import time
import psycopg2
import requests
import urllib.request
import json
from slackclient import SlackClient
from watson_developer_cloud import VisualRecognitionV3 as VisualRecognition
from watson_developer_cloud import ConversationV1 as Conversation

######   CONSTANTS ########

# smartfridge's ID as an environment variable
BOT_ID = os.environ.get("BOT_ID")

SLACK_BOT_TOKEN=os.environ.get('SLACK_BOT_TOKEN')

AT_BOT = "<@" + BOT_ID + ">"

# 1 second delay between reading from firehose
READ_WEBSOCKET_DELAY = 1

# Get key to request Food2fork API
FOOD2FORK_KEY=os.environ.get('FOOD2FORK_KEY')

# Define our connection string
DB_STRING_CONNECTION = "host='localhost' dbname='smartfridge' user='postgres' password='postgres'"

VISUAL_RECOGNITION_VERSION = '2017-10-15'
VISUAL_RECOGNITION_URL = 'https://gateway-a.watsonplatform.net/visual-recognition/api'
VISUAL_RECOGNITION_KEY = os.environ.get('VISUAL_RECOGNITION_KEY')

CONVERSATION_VERSION = '2017-09-23',
CONVERSATION_USERNAME = os.environ.get('CONVERSATION_USERNAME')
CONVERSATION_PASSWORD = os.environ.get('CONVERSATION_PASSWORD')
CONVERSATION_URL = 'https://gateway.watsonplatform.net/conversation/api'
CONVERSATION_WORKSPACE = os.environ.get('CONVERSATION_WORKSPACE')


class SmartFridge():
    def __init__(self):
        self.context = {}
        self.intents = []
        self.entities = []

        # Enviroment variables
        self.context['search_recipe'] = False
        self.context['image_recipe'] = False
        self.context['dish'] = None
        self.context['counter'] = 0
        self.context['yum_sugest'] = False
        self.context['cuisine_type'] = None
        self.context['ingredients'] = None
        self.context['intolerances'] = None

        #  Slack client instance
        self.slack_client = SlackClient(SLACK_BOT_TOKEN)

        # Watson Conversation sevice instance
        self.conversation = Conversation(version = CONVERSATION_VERSION,
                                         username = CONVERSATION_USERNAME,
                                         password = CONVERSATION_PASSWORD,
                                         url = CONVERSATION_URL)

        #  Watson Visual Recognition service instance
        self.visual_recognition = VisualRecognition(version=VISUAL_RECOGNITION_VERSION,
                                                    url=VISUAL_RECOGNITION_URL,
                                                    api_key=VISUAL_RECOGNITION_KEY)
        self.database_cursor = None


    def fetch_content(self, query):
        # execute Query
        self.database_cursor.execute(query)

        # retrieve the records from the database
        records = self.database_cursor.fetchall()
        record_list=[]
        for r in records:
            record_list.append(r[0])
        return(record_list)


    def handle_command(self, command, channel):
        """
            Receives commands directed at the bot and determines if they
            are valid commands. If so, then acts on the commands. If not,
            returns back what it needs for clarification.
        """
        response = "Not sure what you mean. Please reword your request"

        print('\n\nINPUT = {}\n'.format(command))

        if command.startswith('photo'):
            self.context['image_recipe']="true"
            response_text, intent, entity=self.update_conversation_context()
            # print('Respuesta tras actualizar contexto')
            # print(response_text)
            # print(intent)
            # print(entity)

            with open('./download/food.jpg', 'rb') as image_file:
                vr_response = self.visual_recognition.classify(images_file=image_file, classifier_ids=['food'])
                if vr_response['images'] and len(vr_response['images'])>0:
                    image= vr_response['images'][0]
                    if image['classifiers'] and len(image['classifiers'])>0:
                        classifier=image['classifiers'][0]
                        if classifier['classes'] and len(classifier['classes'])>0:
                            food=classifier['classes'][0]['class']
                            score=classifier['classes'][0]['score']
                            response='Uhm... :yum: :yum: :yum: This looks really good. I think (score: {1}) it is... *{0}*'.format(food, score)
                            response=response + '\n' + smartfridge.get_ingredients(self.get_recipe_id(food))

        else:
            response_text, intent, entity = self.msg_to_conversation(command)
            print('intent = {} '.format(intent))
            print('entity = {} '.format(entity))

            if intent=='get_recipe':
                response='No recipe found'
                self.send_response(response_text)
                recipe = self.get_recipe()
                if recipe!='':
                    response=recipe
            elif intent=='sugest_dish':
                self.sugest_dish()
                response = response_text
            elif intent=='available_ingredients':
                self.send_response('Ok, let me take a look, and I\'ll make a recap for you\n\n')
                response = self.analize_content()
            else:
                response = response_text

            self.send_response(response)


    def analize_content(self):
        all_products = []
        expired_products = []
        products_to_expire = []
        recap = ''

        # All products
        query_all = "SELECT name " \
                    "FROM products " \
                    "ORDER by name"
        all_products = self.fetch_content(query_all)

        # Expired products
        query_expired = "SELECT name " \
                        "FROM products " \
                        "WHERE date(expiration_date)<=current_date " \
                        "ORDER by name"
        expired_products = self.fetch_content(query_expired)

        # Products to expire in next 7 days
        query_to_expire = "SELECT name " \
                          "FROM products " \
                          "WHERE date(expiration_date)>current_date " \
                          "AND date(expiration_date)<=current_date + interval '7 days' " \
                          "ORDER by name"

        products_to_expire= self.fetch_content(query_to_expire)

        if len(all_products)>0:
            recap= 'There are currently a total of {} *available* products: '.format(len(all_products)) + (', '.join(map(str, all_products)))
            if(len(expired_products)>0):
                recap = recap + '\n\n' + ':recycle: There are {} *expired* products: '.format(len(expired_products)) + (', '.join(map(str, all_products)))
            else:
                recap = recap + '\n\n' + 'Great! :clap: There are no expired products'
            if(len(products_to_expire)>0):
                recap = recap + '\n\n' + 'There are {} products *to expire*: '.format(len(products_to_expire)) + (', '.join(map(str, products_to_expire)))
            else:
                recap = recap + '\n\n' + 'Congrats! :v: There are no products to expire in the next 7 days'

        else:
            recap= ':-1: You have the fridge EMPTY! :disappointed_relieved:' \
                    'Make the purchase if you do not want to starve. ' \
                    'Today you will have to order food at home or go to your parents\' house :family:'

        return(recap)




    def send_response(self, response):
        # Provide response
        self.slack_client.api_call("chat.postMessage",
                                   channel=channel,
                                   text=response,
                                   as_user=True)


    def update_conversation_context(self):
        print('update_conversation_context')
        return self.msg_to_conversation('')


    def get_recipe(self):
        recipe=''
        print('dish = {}'.format(self.context['dish']))
        print('search_recipe = {}'.format(self.context['search_recipe']))
        if (self.context['dish']!=None and self.context['search_recipe']):
            print('Buscando receta para: << {} >>'.format(self.context['dish']))
            recipe=self.get_ingredients(self.get_recipe_id(self.context['dish']))
        return recipe



    def sugest_dish(self):
        print('La intencion detectada es sugest_dish')


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




    def msg_to_conversation(self, input_message):
        message = {}
        intent = ''
        entity = ''
        response_text= ''

        if(input_message != ''):
            message['text'] = input_message

        response = self.conversation.message(workspace_id = CONVERSATION_WORKSPACE,
                                             message_input = message,
                                             context = self.context,
                                             alternate_intents = False)

        self.update_local_context(response['context'])
        self.intents = response['intents']
        self.entities = response['entities']

        # Imprime la intencion y la entidad detectada
        if(len(self.intents) > 0 and len(self.entities)>0 ):
            print('#{0}  (@{1}:{2})'.format(self.intents[0]['intent'], self.entities[0]['entity'], self.entities[0]['value']))
            intent = self.intents[0]['intent']
            entity = self.entities[0]['entity']
        elif(len(self.intents) > 0):
            print('#{0}'.format(self.intents[0]['intent']))
            intent = self.intents[0]['intent']
        elif(len(self.entities)>0 ):
            print('@{0}:{1}'.format(self.entities[0]['entity'], self.entities[0]['value']))
            entity = self.entities[0]['entity']

        if(response["output"] and response["output"]["text"]):
            response_text = response["output"]["text"][0]

        return response_text, intent, entity


    def update_local_context(self, context):
        self.context = context
        for key, value in self.context.items():
            print('{0} = {1}'.format(key, value))
        print('\n')


    def database_connection(self):
        # print the connection string we will use to connect
        print('Connecting to database ... {}'.format(DB_STRING_CONNECTION))

        # get a connection, if a connect cannot be made an exception will be raised here
        db_conn = psycopg2.connect(DB_STRING_CONNECTION)

        # conn.cursor will return a cursor object, you can use this cursor to perform queries
        self.database_cursor = db_conn.cursor()

    def _urlHelper(self, endpoint, **kwargs):
        data = {'key': FOOD2FORK_KEY}

        for key, value in kwargs.items():
            data[key] = value

        return endpoint + '?' + urllib.parse.urlencode(data)


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

#######   FOOD2FORK    #######
    def search_recipes(self, query):
        endpoint = 'http://food2fork.com/api/search'
        url = self._urlHelper(endpoint, q=query)
        return requests.get(url).json()

    def get_recipe_from_id(self, recipeId):
        endpoint = 'http://food2fork.com/api/get'
        try:
            url = self._urlHelper(endpoint, rId=recipeId)
            return requests.get(url).json()
        except Exception as inst:
            print(inst)
            return None

    def get_ingredients(self, recipeId):
        recipe=self.get_recipe_from_id(recipeId)
        if recipe and 'recipe' in recipe:
            ingredients=[]
            source = '\nHere, you can find the *method of cooking*: {}'.format(recipe['recipe']['source_url'])
            for ingredient in (recipe['recipe']['ingredients']):
                ingredients.append(ingredient)
                str_ingredients= '\nTo cook this dish you need the following *ingredients*:' + '\n\n   - {}'.format('\n    - '.join(map(str, ingredients)))
            return (str_ingredients + '\n' + source)


    def get_recipes_from_ingredients(self, ingredients):
        recipes=self.search_recipes(ingredients)
        if recipes and 'recipes' in recipes:
            for i, recipe in enumerate(recipes['recipes'][:5]):
                print('[{0}] : {1}'.format(i+1, recipe['title']))

    def get_recipe_id(self, query):
        print('query = {}'.format(query))
        recipes=self.search_recipes(query)
        if recipes and 'recipes' in recipes and len(recipes['recipes'])>0:
            return(recipes['recipes'][0]['recipe_id'])
        else:
            return None

    def get_recipes_from_database(self):
        recipe_ids=[]
        query="SELECT name FROM products"
        db_products=self.fetch_content(query)
        for product in db_products:
            id=self.get_recipe_id(product)
            if id not in recipe_ids:
                recipe_ids.append(id)


####   MAIN  ####
if __name__ == "__main__":
    smartfridge=SmartFridge()
    smartfridge.database_connection()

    #ingredients = 'chicken, tomatoes, cheese, onion, egg'
    #smartfridge.get_recipes_from_ingredients(ingredients)

    if smartfridge.slack_client.rtm_connect():
        print("smartfridge connected and running!")
        while True:
            command, channel = smartfridge.parse_slack_output(smartfridge.slack_client.rtm_read())
            if command and channel:
                smartfridge.handle_command(command, channel)
            time.sleep(READ_WEBSOCKET_DELAY)
    else:
        print("Connection failed. Invalid Slack token or bot ID?")
