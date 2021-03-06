#!/usr/bin/python
# coding=utf-8

######   LIBRARIES ########
import pprint
import os
import time
import datetime
import psycopg2
import requests
import urllib.request
import json
from slackclient import SlackClient
from watson_developer_cloud import VisualRecognitionV3 as VisualRecognition
from watson_developer_cloud import ConversationV1 as Conversation

######   CONSTANTS ########

# Slack bot id
BOT_ID = os.environ.get("BOT_ID")
# Slack token
SLACK_BOT_TOKEN=os.environ.get('SLACK_BOT_TOKEN')
# String to identify messages with bot as recipient
AT_BOT = "<@" + BOT_ID + ">"
# Delay between reading from firehose
READ_WEBSOCKET_DELAY = 1

# Food2fork API key
FOOD2FORK_KEY=os.environ.get('FOOD2FORK_KEY')

# Postgres database connection string
DB_STRING_CONNECTION = "host='localhost' dbname='smartfridge' user='postgres' password='postgres'"

# Watson Visual Recognition version (to ensure backward compatibility)
VISUAL_RECOGNITION_VERSION = '2017-10-15'
# Watson Visual Recognition base url
VISUAL_RECOGNITION_URL = 'https://gateway-a.watsonplatform.net/visual-recognition/api'
# Watson Visual Recognition API key
VISUAL_RECOGNITION_KEY = os.environ.get('VISUAL_RECOGNITION_KEY')

# Watson Conversation version (to ensure backward compatibility)
CONVERSATION_VERSION = '2017-09-23'
# Watson Conversation username
CONVERSATION_USERNAME = os.environ.get('CONVERSATION_USERNAME')
# Watson Conversation password
CONVERSATION_PASSWORD = os.environ.get('CONVERSATION_PASSWORD')
# Watson Conversation workspace identifier
CONVERSATION_WORKSPACE = os.environ.get('CONVERSATION_WORKSPACE')
# Watson Conversation base url
CONVERSATION_URL = 'https://gateway.watsonplatform.net/conversation/api'

# Number of remaining days to consider a product as next to expire
DAYS_TO_EXPIRE = 7
# Number of dish options provided to the user
TOTAL_NUMBER_OPTIONS = 6


class SmartFridge():
    def __init__(self):
        self.context = {}
        self.option_dict = {}
        self.intents = []
        self.entities = []
        self.recipe_options = []
        self.database_cursor = None


        # Reset enviroment variables

        self.context['search_recipe'] = False
        self.context['image_recipe'] = False
        self.context['suggest_dish'] = False
        self.context['yum_sugest'] = False
        self.context['summary'] = False
        self.context['option'] = None
        self.context['cuisine_type'] = None
        self.context['ingredients'] = None
        self.context['intolerances'] = None
        self.context['dish'] = None
        self.context['counter'] = 0
        self.context['insult_counter'] = 0


        # Services initialization

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
        # Database connection
        self.database_connection(DB_STRING_CONNECTION)



    ######   CONVERSATION MANAGEMENT ########

    # Receives commands directed at the bot and determines if they
    # are valid commands. If so, then acts on the commands. If not,
    # returns back what it needs for clarification.
    def handle_command(self, command):

        response = "Not sure what you mean. Please reword your request"

        print('\n\nINPUT = {}\n'.format(command))

        # Processing of the response
        if command == 'download_file_format_error':
            response = 'The file extension is not valid. Try with JPG or PNG.'
        # Food image recognition
        elif command.startswith('photo'):
            self.send_response('Please, give me a second... :hourglass_flowing_sand:')
            self.context['image_recipe'] = "true"
            response_text, intent, entity=self.update_conversation_context()
            response = self.image_food_recognition()
        else:
            response_text, intent, entity = self.msg_to_conversation(command)
            print('intent = {} '.format(intent))
            print('entity = {} '.format(entity))

            # A suggestion is provide to the user because the required information
            # is not provided by the user after several attempts
            # $yum_sugest
            if(self.context['yum_sugest'] == 'true'):
                self.send_response(response_text)
                response = self.yum_suggestion()

            # $suggest_dish
            elif(self.context['suggest_dish'] == 'true'):
                self.send_response(response_text)
                response = self.suggest_dish()

            # $summary
            elif(self.context['summary'] == 'true'):
                self.send_response(response_text)
                response = self.get_db_summary()

            # $search_recipe
            elif(self.context['search_recipe'] == 'true'):
                self.send_response(response_text)
                response = self.get_recipe()

            # #get_recipe
            elif intent == 'get_recipe':
                if(self.context['search_recipe'] == 'true'):
                    response = self.get_recipe()
                elif(self.context['yum_sugest'] == 'true'):
                    response = self.yum_suggestion()
                else:
                    response= response_text

            # #suggest_dish
            elif intent=='sugest_dish':
                if(self.context['suggest_dish'] == 'true'):
                    response = self.suggest_dish()
                elif(self.context['yum_sugest'] == 'true'):
                    response = self.yum_suggestion()
                else:
                    response = response_text

            # #available_ingredients
            elif intent=='available_ingredients':
                ingredients = self.context['ingredients']
                if ingredients != None:
                    self.send_response(response_text)
                    response = self.get_ingredients_information(ingredients)
                else:
                    self.send_response(response_text)
                    response = self.get_db_summary()

            # #needed_ingredients
            elif intent == 'needed_ingredients':
                response = response_text

            # #select_option
            elif intent == 'select_option':
                option_response = self.select_option()
                if option_response != '':
                    response = option_response
                else:
                    response = response_text

            # #negative_reaction
            elif intent == 'negative_reaction':
                response = response_text

            # #anaything_else
            else:
                response = response_text

        # Send the corresponding response to the user interface (slack)
        self.send_response(response)


    def select_option(self):
        response = ''
        if (self.context['option']!= None) and (len(self.recipe_options) > 0):
            index = self.parse_to_valid_index(self.context['option'])
            if index != None:
                selection = self.recipe_options[index]
                response = 'Ok, good choice! The {} recipe below: '.format(selection)
                response = response + '\n' + self.get_ingredients(self.option_dict[selection])
                self.recipe_options = []

        return response


    def parse_to_valid_index(self, opt):
        value = None

        if opt in range(1, TOTAL_NUMBER_OPTIONS+1):
            value = opt - 1
        else:
            value = None

        return value



    # Prioritizes the use of ingredients that are about to expire
    # Excludes expired products
    def yum_suggestion(self, n_options=6):
        header = 'I have found the following recipes for you:'
        response = ''
        footer = 'Please, provide a valid option from 1 to 6'

        self.recipe_options= []
        self.context['yum_sugest'] = False

        if n_options > 0:

            available_ingredients_options = []
            top_rated_options = []
            trending_options = []

            # n_recipes recipe suggestion by using the n_ingredients with closest expiration date and biggest quantity
            available_ingredients_options = self.get_recipe_options_from_available_ingredients(n_options=2,
                                                                                               n_ingredients=2)

            top_rated_options = self.get_top_rated_recipe_options\
                (n_options=((TOTAL_NUMBER_OPTIONS - len(available_ingredients_options)) // 2)
                           + ((TOTAL_NUMBER_OPTIONS - len(available_ingredients_options)) % 2))

            trending_options = self.get_trending_recipe_options(
                n_options=((TOTAL_NUMBER_OPTIONS - len(available_ingredients_options)) // 2))

            self.recipe_options = available_ingredients_options + top_rated_options + trending_options
            print(self.recipe_options)
            for i, recipe in enumerate(self.recipe_options[:n_options]):
                response = response + '\n' + '[{0}] :  {1}'.format(i+1, recipe)

        if response == '':
            response = ':disappointed: Sorry, no recipes found for your request. Please, try a new search'
        else:
            response = header + '\n' + response + '\n' + footer
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


    def get_db_summary(self):
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
            header = '\n\nThere are {0} products in total, ' \
                     '{1} products are already expired and {2} products will expire soon. '.\
                            format(len(all_products), len(expired_products), len(products_to_expire))

            if(len(expired_products)>0):
                footer = '\n\nThrow the expired foods out. '
                recap = recap + '\n\n' + ':recycle: *Already expired*:  {0}.'\
                    .format(', '.join(map(str, expired_products)))
            else:
                recap = recap + '\n\n' + 'Great! :clap: There are no expired products.'
            if(len(products_to_expire)>0):
                footer = footer + 'Consider using the foods to expire as soon as possible.'
                recap = recap + '\n\n' + ':alarm_clock: *To expire*:  {0}.'\
                    .format(', '.join(map(str, products_to_expire)))
            else:
                recap = recap + '\n\n' + 'Congrats! :v: There are no products to expire in the next {0} days.'\
                    .format(DAYS_TO_EXPIRE)

        else:
            recap= ':-1: You have the fridge EMPTY! :disappointed_relieved:' \
                    'Make the purchase if you do not want to starve. ' \
                    'Today you will have to order food at home.'

        return(header + recap + footer)


    def image_food_recognition(self):
        food, score = self.get_food_from_image('./download/food.jpg')
        if (food != 'non-food'):
            response = 'Uhm... :yum: :yum: :yum: This looks really good. I think (score: {1}) it is... *{0}*'\
                .format(food, score)
            self.send_response(response)
            response = '\n' + smartfridge.get_ingredients(self.get_recipe_id(food))
        else:
            response = 'Are you sure it is edible? I do not recognize food in this image. \nPlease, try with another one.'

        return response


    def get_recipe(self):
        recipe = ':disappointed: Sorry, no recipes found for your request. Please, try a new search'
        print('dish = {}'.format(self.context['dish']))
        print('search_recipe = {}'.format(self.context['search_recipe']))
        if (self.context['dish'] != None and self.context['search_recipe']):
            print('Buscando receta para: << {} >>'.format(self.context['dish']))
            recipe=self.get_ingredients(self.get_recipe_id(self.context['dish']))
        return recipe

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
                    str_ingredients= '\nI found *{}*. To cook this you need the following *ingredients*:'\
                                         .format(recipe['recipe']['title']) + \
                                     '\n\n   - {}'.format('\n    - '.join(map(str, ingredients)))
                response = str_ingredients + '\n' + source

        return response



    def get_ingredients_information(self, ingredients):
        info = ""
        try:
            records = self.get_db_information_about_ingredients(ingredients)
            if len(records)>0:
                for r in records:
                    # Not expired product
                    if r[1].date() >= datetime.datetime.now().date():
                        info = info + '\n' + 'There are {0} grams of {1}, the expiration date is {2}'.\
                            format(round(r[2], 0), r[0], r[1].strftime("%d/%m/%Y"))
                    # Expired product
                    else:
                        info = info + '\n' + 'The {0} expired the day {1}. Throw it out!'\
                            .format(r[0], r[1].strftime("%d/%m/%Y"))
            else:
                info = 'There are no  {} left at home, write it down on the shopping list.'.format(ingredients)
        except:
            info = 'Sorry, we are having technical problems, please try again.'

        return info



    def get_top_rated_recipe(self):
        return self.get_ingredients(self.get_recipe_id(''))

    def get_trending_recipe(self):
        return self.get_ingredients(self.get_recipe_id('', 't'))

    def get_recipe_options_from_available_ingredients(self, n_options=2, n_ingredients=2):
        ingredients = []
        options = []

        # IMPROVEMENT: add to the query the register user intolerances
        ingredients = self.get_top_expired_ingredients_from_db(n_ingredients)

        if len(ingredients) > 0:
            query = ', '.join(map(str, ingredients))
            recipes = self.search_recipes(query)

        if recipes and 'recipes' in recipes:
            for recipe in recipes['recipes'][:n_options]:
                options.append(recipe['title'])
                self.option_dict[recipe['title']]=recipe['recipe_id']
        return options

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

        # Print intent and entity
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



    ######   VISUAL RECOGNITION ########
    def get_food_from_image(self, image_path):
        with open(image_path, 'rb') as image_file:
            vr_response = self.visual_recognition.classify(images_file=image_file, classifier_ids=['food'])
            if vr_response['images'] and len(vr_response['images']) > 0:
                image = vr_response['images'][0]
                if image['classifiers'] and len(image['classifiers']) > 0:
                    classifier = image['classifiers'][0]
                    if classifier['classes'] and len(classifier['classes']) > 0:
                        food = classifier['classes'][0]['class']
                        score = classifier['classes'][0]['score']
                        return food, score
        return None, None



    ######   SLACK ########
    """
        The Slack Real Time Messaging API is an events firehose.
        this parsing function returns None unless a message is
        directed at the Bot, based on its ID.
    """
    def parse_slack_output(self, slack_rtm_output, download_path='download/food.jpg'):
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
                        self.download_file(down_url, download_path, 'download')
                        return 'photo', output['channel']
                    else:
                        return 'download_file_format_error', output['channel']
        return None, None

    # Provide response
    def send_response(self, response):
        result = self.slack_client.api_call("chat.postMessage",
                                            channel=channel,
                                            text=response,
                                            as_user=True)
        return result


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
    def food2fork_request(self, endpoint, **kwargs):
        data = {'key': FOOD2FORK_KEY}
        for key, value in kwargs.items():
            data[key] = value
        return endpoint + '?' + urllib.parse.urlencode(data)


    def search_recipes(self, query, sortBy='r'):
        endpoint = 'http://food2fork.com/api/search'
        url = self.food2fork_request(endpoint, q=query, sort=sortBy)
        print(url)
        return requests.get(url).json()


    def get_recipe_from_id(self, recipeId):
        endpoint = 'http://food2fork.com/api/get'
        try:
            url = self.food2fork_request(endpoint, rId=recipeId)
            print(url)
            return requests.get(url).json()
        except Exception as inst:
            print(inst)
            return None


    def get_recipe_id(self, query, sortBy='r'):
        recipes=self.search_recipes(query, sortBy)
        if recipes and 'recipes' in recipes and len(recipes['recipes'])>0:
            return(recipes['recipes'][0]['recipe_id'])
        else:
            return None



    def get_top_rated_recipe_options(self, n_options=1):
        options = []
        recipes = self.search_recipes('')
        if recipes and 'recipes' in recipes:
            for recipe in recipes['recipes'][:n_options]:
                options.append(recipe['title'])
                self.option_dict[recipe['title']] = recipe['recipe_id']
        return options



    def get_trending_recipe_options(self, n_options=1):
        options = []
        recipes = self.search_recipes('', sortBy='t')

        if recipes and 'recipes' in recipes:
            for recipe in recipes['recipes'][:n_options]:
                options.append(recipe['title'])
                self.option_dict[recipe['title']] = recipe['recipe_id']

        return options





    ######   POSTGRES DATABASE ########

    def database_connection(self, str_db_connection):
        print('Connecting to database ... ')
        # get a connection, if a connect cannot be made an exception will be raised here
        db_conn = psycopg2.connect(str_db_connection)
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


    # Obtain the n_ingredients products with the closest expiration date and that are in more quantity
    def get_top_expired_ingredients_from_db(self, n_ingredients=2):
        ingredients = []
        db_query = 'SELECT name ' \
                    'FROM products ' \
                    'WHERE date(expiration_date) > current_date ' \
                    'ORDER by expiration_date ASC, quantity DESC ' \
                    'LIMIT {}'.format(n_ingredients)

        ingredients = self.fetch_content(db_query)

        return ingredients

    def get_db_information_about_ingredients(self, ingredients):
        query = "SELECT name, expiration_date, quantity " \
                "FROM products " \
                "WHERE name like '%{}%'".format(ingredients)

        self.database_cursor.execute(query)
        records = self.database_cursor.fetchall()

        return records





if __name__ == "__main__":

    smartfridge=SmartFridge()

    if smartfridge.slack_client.rtm_connect():
        print("smartfridge connected and running!")
        while True:
            command, channel = smartfridge.parse_slack_output(smartfridge.slack_client.rtm_read())
            if command and channel:
                smartfridge.handle_command(command)
            time.sleep(READ_WEBSOCKET_DELAY)
    else:
        print("Connection failed. Invalid Slack token or bot ID?")




