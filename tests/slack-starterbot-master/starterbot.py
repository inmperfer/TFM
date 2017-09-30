import os
import time
import psycopg2
from slackclient import SlackClient


# smartfridge's ID as an environment variable
BOT_ID = os.environ.get("BOT_ID")


# constants
AT_BOT = "<@" + BOT_ID + ">"
EXAMPLE_COMMAND = "do"

# instantiate Slack & Twilio clients
slack_client = SlackClient(os.environ.get('SLACK_BOT_TOKEN'))



def handle_command(command, channel):
    """
        Receives commands directed at the bot and determines if they
        are valid commands. If so, then acts on the commands. If not,
        returns back what it needs for clarification.
    """
    print('handle_command')
    response = "Not sure what you mean. Use the *" + EXAMPLE_COMMAND + \
               "* command with numbers, delimited by spaces."
    if command.startswith(EXAMPLE_COMMAND):
        response = "Sure...write some more code then I can do that!"
    slack_client.api_call("chat.postMessage", channel=channel,
                          text=response, as_user=True)


def parse_slack_output(slack_rtm_output):
    """
        The Slack Real Time Messaging API is an events firehose.
        this parsing function returns None unless a message is
        directed at the Bot, based on its ID.
    """
    print('parse_slack_output')
    output_list = slack_rtm_output
    if output_list and len(output_list) > 0:
        for output in output_list:
            if output and 'text' in output and AT_BOT in output['text']:
                # return text after the @ mention, whitespace removed
                return output['text'].split(AT_BOT)[1].strip().lower(), \
                       output['channel']
    return None, None

def database_connection():
    # Define our connection string
    db_string_connection = "host='localhost' dbname='smartfridge' user='postgres' password='postgres'"

    # print the connection string we will use to connect
    print('Connecting to database ... {}'.format(db_string_connection))

    # get a connection, if a connect cannot be made an exception will be raised here
    db_conn = psycopg2.connect(db_string_connection)

    # conn.cursor will return a cursor object, you can use this cursor to perform queries
    database_cursor = db_conn.cursor()

    # execute our Query
    database_cursor.execute("SELECT name FROM products")

    # retrieve the records from the database
    records = database_cursor.fetchall()

    print(records)


if __name__ == "__main__":

    database_connection()

    READ_WEBSOCKET_DELAY = 1 # 1 second delay between reading from firehose
    if slack_client.rtm_connect():
        print("smartfridge connected and running!")
        while True:
            command, channel = parse_slack_output(slack_client.rtm_read())
            if command and channel:
                handle_command(command, channel)
            time.sleep(READ_WEBSOCKET_DELAY)
    else:
        print("Connection failed. Invalid Slack token or bot ID?")
