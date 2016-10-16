import json
import os
import traceback

import Algorithmia
import requests
import yaml
from playsound import playsound

###
# Credit:
# http://blog.algorithmia.com/sentiment-analysis-slack-chatbot-python/
# https://github.com/slackhq/python-rtmbot
###

# Current working directory
CWD = os.path.dirname(__file__)

CONFIG = yaml.load(file(os.path.join(CWD, "resources", "rtmbot.conf"), "r"))

ALGORITHMIA_CLIENT = Algorithmia.client(CONFIG["ALGORITHMIA_KEY"])
ALGORITHM = ALGORITHMIA_CLIENT.algo("nlp/SocialSentimentAnalysis/0.1.3")

outputs = []


def resolve_mood(text):
    try:
        sentence = {
            "sentence": text
        }

        result = ALGORITHM.pipe(sentence)
        if not result or not result.result:
            return

        sentiment = result.result[0]

        compound = sentiment.get("compound", 0)
        print compound
        compound = (int((1-((compound + 1)/2))*20000))+45000

        # print to the console what just happened
        print 'Comment "{}", compound result {}'.format(text, compound)

        return compound
    except Exception as exception:
        # a few things can go wrong but the important thing is keep going
        # print the error and then move on
        print "Something went wrong processing the text: {}".format(text)
        print traceback.format_exc(exception)


def get_bulb(bulb=None):
    if bulb == 'first':
        return "/lights/1"
    elif bulb == 'second':
        return "/lights/2"
    elif bulb == 'third':
        return "/lights/3"
    else:
        return "/groups/0"


def send_to_api(compound):
    endpoint = CONFIG["HUE_API_URL"]
    action = "/action"
    bulb = get_bulb()
    url = endpoint + bulb + action
    data = json.dumps(body(compound))
    r = requests.put(url, data)

    # let's celebrate
    jingle = None
    if compound > 63000:
        jingle = 'sad.mp3'
    elif compound < 47000:
        jingle = 'happy.mp3'

    if jingle:
        playsound(os.path.join(CWD, "resources", "audio", jingle))
    return r


def body(compound):
    return {"on": True, "hue": compound, "sat": 254, "bri": 254}


# A callback listening to a Slack channel
def process_message(data):
    text = data.get("text", None)

    if not text or data.get("subtype", "") == "channel_join":
        return

    # remove any odd encoding
    text = text.encode('utf-8')

    channel = data.get("channel", None)
    if not channel:
        return

    # don't log the current mood reply!
    if text.startswith('Positive:'):
        return

    # update overall sentiment
    compound = resolve_mood(text)

    # publish results
    send_to_api(compound)
