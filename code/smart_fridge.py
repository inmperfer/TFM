#!/usr/bin/python
# coding=utf-8

######   LIBRARIES ########
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

DAYS_TO_EXPIRE = 7

class SmartFridge():
    def __init__(self):
        self.context = {}
        self.intents = []
        self.entities = []

        # Enviroment variables
        self.context['search_recipe'] = False
        self.context['image_recipe'] = False
        self.context['suggest_dish'] = False
        self.context['yum_sugest'] = False
        self.context['cuisine_type'] = None
        self.context['ingredients'] = None
        self.context['intolerances'] = None
        self.context['dish'] = None
        self.context['counter'] = 0
        self.context['insult_counter'] = 0


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
        # Database cursor
        self.database_cursor = None



    ######   CONVERSATION MANAGEMENT ########

    def handle_command(self, command, channel):
        """
            Receives commands directed at the bot and determines if they
            are valid commands. If so, then acts on the commands. If not,
            returns back what it needs for clarification.
        """
        response = "Not sure what you mean. Please reword your request"

        print('\n\nINPUT = {}\n'.format(command))

        # Processing of the response
        if command == 'download_file_format_error':
            response = 'The file extension is not valid. Try with JPG or PNG.'
        # Visual recognition
        elif command.startswith('photo'):
            self.send_response('Please, give me a second... :hourglass_flowing_sand:')
            self.context['image_recipe'] = "true"
            response_text, intent, entity=self.update_conversation_context()

            with open('./download/food.jpg', 'rb') as image_file:
                vr_response = self.visual_recognition.classify(images_file=image_file, classifier_ids=['food'])
                if vr_response['images'] and len(vr_response['images'])>0:
                    image= vr_response['images'][0]
                    if image['classifiers'] and len(image['classifiers'])>0:
                        classifier=image['classifiers'][0]
                        if classifier['classes'] and len(classifier['classes'])>0:
                            food=classifier['classes'][0]['class']
                            score=classifier['classes'][0]['score']
                            if (food != 'non-food'):
                                response='Uhm... :yum: :yum: :yum: This looks really good. I think (score: {1}) it is... *{0}*'.format(food, score)
                                self.send_response(response)
                                response= '\n' + smartfridge.get_ingredients(self.get_recipe_id(food))
                            else:
                                response ='Are you sure it is edible? I do not recognize food in this image. \nPlease Try with a another one.'

        else:
            response_text, intent, entity = self.msg_to_conversation(command)
            print('intent = {} '.format(intent))
            print('entity = {} '.format(entity))

            # A suggestion is provide to the user because the required information
            # is not provided by the user after several attempts
            # YUM_SUGGEST
            if(self.context['yum_sugest'] == 'true'):
                self.send_response(response_text)
                response = self.yum_suggestion()

            elif(self.context['suggest_dish'] == 'true'):
                self.send_response(response_text)
                response = self.suggest_dish()


            # GET_RECIPE
            elif intent == 'get_recipe':
                if(self.context['search_recipe'] == 'true'):
                    response = self.get_recipe()
                elif(self.context['yum_sugest'] == 'true'):
                    response = self.yum_suggestion()
                else:
                    response= response_text

            # SUGGEST_DISH
            elif intent=='sugest_dish':
                if(self.context['suggest_dish'] == 'true'):
                    response = self.suggest_dish()
                elif(self.context['yum_sugest'] == 'true'):
                    response = self.yum_suggestion()
                else:
                    response = response_text

            # AVAILABLE_INGREDIENTS
            elif intent=='available_ingredients':
                self.send_response('I\'ll make a recap for you... \n\n')
                response = self.analize_content()

            # NEGATIVE_REACTION
            elif intent == 'negative_reaction':
                response = response_text

            # ANYTHING ELSE
            else:
                response = response_text

        # Send the corresponding response to the user interface (slack)
        self.send_response(response)


    # Prioritizes the use of ingredients that are about to expire
    # Excludes expired products
    def yum_suggestion(self):
        ingredients = []
        #response = 'yumyumBot suggestion with the available ingredients or the trending recipe of the day'

        # Obtain the 2 products with the closest expiration date and that are in more quantity
        db_query = 'SELECT name ' \
                    'FROM products ' \
                    'WHERE date(expiration_date) > current_date ' \
                    'ORDER by expiration_date ASC, quantity DESC ' \
                    'LIMIT 2'

        ingredients = self.fetch_content(db_query)

        if len(ingredients) > 0:
            query = ', '.join(map(str, ingredients))
            response = self.get_ingredients(self.get_recipe_id(query))
            # IMPROVEMENT: add to the query the register user intolerances
        else:
            response = self.get_top_rated_recipe()

        print('top rated = {}'.format(self.get_top_rated_recipe()))
        print('trending = {}'.format(self.get_trending_recipe()))

        return response



    def suggest_dish(self):
        print('ingredients={0}, cuisine type={1}, intolerances={2}'.format(self.context['ingredients'],
                                                                           self.context['cuisine_type'],
                                                                           self.context['intolerances']))

        query = ''
        response = ':disappointed: Sorry, no recipes found for your request. Please, try a new search'

        if (self.context['suggest_dish']):
            if self.context['ingredients'] != None:
                query = query + self.context['ingredients']
            if self.context['cuisine_type'] != None:
                query = query + ' ' + self.context['cuisine_type']
            if self.context['intolerances'] != None:
                query = query + ' ' + self.context['intolerances']

            if query != '':
                print('Buscando receta para: << {} >>'.format(query))
                response = self.get_ingredients(self.get_recipe_id(query))

        return response


    def analize_content(self):
        all_products = []
        expired_products = []
        products_to_expire = []
        header = ''
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

        # Products to expire in next DAYS_TO_EXPIRE days
        query_to_expire = "SELECT name " \
                          "FROM products " \
                          "WHERE date(expiration_date)>current_date " \
                          "AND date(expiration_date)<=current_date + interval '{} days' " \
                          "ORDER by name".format(DAYS_TO_EXPIRE)

        products_to_expire= self.fetch_content(query_to_expire)

        if len(all_products)>0:
            header = '\n\nThere are {0} products in total, {1} products are already expired and {2} products will expire soon. '.\
                            format(len(all_products), len(expired_products), len(products_to_expire))

            if(len(expired_products)>0):
                footer = '\n\nThrow out the expired foods. '
                recap = recap + '\n\n' + ':recycle: *Already expired*:  {0}.'.format(', '.join(map(str, expired_products)))
            else:
                recap = recap + '\n\n' + 'Great! :clap: There are no expired products.'
            if(len(products_to_expire)>0):
                footer = footer + 'Consider using the foods to expire as soon as possible.'
                recap = recap + '\n\n' + ':alarm_clock: *To expire*:  {0}.'.format(', '.join(map(str, products_to_expire)))
            else:
                recap = recap + '\n\n' + 'Congrats! :v: There are no products to expire in the next {0} days.'.format(DAYS_TO_EXPIRE)

        else:
            recap= ':-1: You have the fridge EMPTY! :disappointed_relieved:' \
                    'Make the purchase if you do not want to starve. ' \
                    'Today you will have to order food at home or go to your parents\' house :family:.'

        return(header + recap + footer)


    def get_recipe(self):
        recipe = ':disappointed: Sorry, no recipes found for your request. Please, try a new search'
        print('dish = {}'.format(self.context['dish']))
        print('search_recipe = {}'.format(self.context['search_recipe']))
        if (self.context['dish'] != None and self.context['search_recipe']):
            print('Buscando receta para: << {} >>'.format(self.context['dish']))
            recipe=self.get_ingredients(self.get_recipe_id(self.context['dish']))
        return recipe

    def update_conversation_context(self):
        print('update_conversation_context')
        return self.msg_to_conversation('')


    def msg_to_conversation(self, input_message):
        message = {}
        intent = ''
        entity = ''
        response_text = ''

        if (input_message != ''):
            message['text'] = input_message

        response = self.conversation.message(workspace_id=CONVERSATION_WORKSPACE,
                                             message_input=message,
                                             context=self.context,
                                             alternate_intents=False)

        self.update_local_context(response['context'])
        self.intents = response['intents']
        self.entities = response['entities']

        # Imprime la intencion y la entidad detectada
        if (len(self.intents) > 0 and len(self.entities) > 0):
            print('#{0}  (@{1}:{2})'.format(self.intents[0]['intent'], self.entities[0]['entity'],
                                            self.entities[0]['value']))
            intent = self.intents[0]['intent']
            entity = self.entities[0]['entity']
        elif (len(self.intents) > 0):
            print('#{0}'.format(self.intents[0]['intent']))
            intent = self.intents[0]['intent']
        elif (len(self.entities) > 0):
            print('@{0}:{1}'.format(self.entities[0]['entity'], self.entities[0]['value']))
            entity = self.entities[0]['entity']

        if (response["output"] and response["output"]["text"]):
            for r in response["output"]["text"]:
                response_text = response_text + '\n' + r

        return response_text, intent, entity

    def update_local_context(self, context):
        self.context = context
        for key, value in self.context.items():
            print('{0} = {1}'.format(key, value))
        print('\n')



    ######   SLACK ########
    def send_response(self, response):
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
                    extension = os.path.splitext(down_url)[1][1:].strip().lower()
                    if extension in ['jpg', 'png']:
                        self.download_file(down_url, 'download/food.jpg', 'download')
                        return 'photo', output['channel']
                    else:
                        return 'download_file_format_error', output['channel']

        return None, None


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

    def search_recipes(self, query, sortBy='r'):
        endpoint = 'http://food2fork.com/api/search'
        url = self._urlHelper(endpoint, q=query, sort=sortBy)
        print(url)
        return requests.get(url).json()

    def get_recipe_from_id(self, recipeId):
        endpoint = 'http://food2fork.com/api/get'
        try:
            url = self._urlHelper(endpoint, rId=recipeId)
            print(url)
            return requests.get(url).json()
        except Exception as inst:
            print(inst)
            return None

    def get_ingredients(self, recipeId):
        print('recipe id = {}'.format(recipeId))
        response = ':disappointed: Sorry, no recipes found for your request. Please, try a new search'
        if recipeId != None:
            recipe = self.get_recipe_from_id(recipeId)
            if recipe and 'recipe' in recipe:
                ingredients=[]
                source = '\nHere, you can find the *method of cooking*: {}'.format(recipe['recipe']['source_url'])
                for ingredient in (recipe['recipe']['ingredients']):
                    ingredients.append(ingredient)
                    str_ingredients= '\nTo cook this dish you need the following *ingredients*:' + '\n\n   - {}'.format('\n    - '.join(map(str, ingredients)))
                response = str_ingredients + '\n' + source

        return response


    def get_top_rated_recipe(self):
        return self.get_ingredients(self.get_recipe_id(''))

    def get_trending_recipe(self):
        return self.get_ingredients(self.get_recipe_id('', 't'))


    def get_recipe_id(self, query, sortBy='r'):
        recipes=self.search_recipes(query, sortBy)
        if recipes and 'recipes' in recipes and len(recipes['recipes'])>0:
            return(recipes['recipes'][0]['recipe_id'])
        else:
            return None


    ######   POSTGRES DATABASE ########

    def database_connection(self):
        print('Connecting to database ... ')

        # get a connection, if a connect cannot be made an exception will be raised here
        db_conn = psycopg2.connect(DB_STRING_CONNECTION)

        # conn.cursor will return a cursor object, you can use this cursor to perform queries
        self.database_cursor = db_conn.cursor()

    def fetch_content(self, query):
        # execute Query
        self.database_cursor.execute(query)

        # retrieve the records from the database
        records = self.database_cursor.fetchall()
        record_list=[]
        for r in records:
            record_list.append(r[0])
        return(record_list)




######   MAIN ########
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
