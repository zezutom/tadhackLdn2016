import Algorithmia
import yaml
import traceback
import colorsys
import requests

###
# Credit:
# http://blog.algorithmia.com/sentiment-analysis-slack-chatbot-python/
# https://github.com/slackhq/python-rtmbot
###

CONFIG = yaml.load(file("rtmbot.conf", "r"))

ALGORITHMIA_CLIENT = Algorithmia.client(CONFIG["ALGORITHMIA_KEY"])
ALGORITHM = ALGORITHMIA_CLIENT.algo('nlp/SocialSentimentAnalysis/0.1.3')

outputs = []

sentiment_results = {
    "negative": 0,
    "neutral": 0,
    "positive": 0
}

sentiment_averages = {
    "negative": 0,
    "neutral": 0,
    "positive": 0,
    "total": 0
}


def display_current_mood(channel):
    reply = ""

    # something has gone wrong if we don't have a channel do nothing
    if not channel:
        return

    # loop over our stats and send them in the
    # best layout we can.
    for k, v in sentiment_averages.iteritems():
        if k == "total":
            continue
        reply += "{}: {}%\n ".format(k.capitalize(), v)

    # todo - remove, this is meant to be sent out
    color = get_current_mood_color()
    reply += "Color | HLS: {}, {}, {} | RGB: {}, {}, {}, | Compound: {}\n"\
        .format(
            color["hls"][0], color["hls"][1], color["hls"][2],
            color["rgb"][0], color["rgb"][1], color["rgb"][2],
            color["compound"])

    outputs.append([channel, str(reply)])
    return


def get_current_mood_color():

    # utility
    def round_up(x):
        return round(x, 2)

    # translate sentiment into RGB
    r = sentiment_averages["negative"]
    g = sentiment_averages["neutral"]
    b = sentiment_averages["positive"]

    # calculate HLS out of RGB
    hls = colorsys.rgb_to_hls(r, g, b)

    # calculate a single point on a scale 0 - 4
    #
    # scale definition:
    # 0 -> stressed, upset
    # 1 -> calm, peaceful
    # 2 -> happy, deeply relaxed
    # 3 -> love, sensual
    # 4 -> warm, curious, loving
    def get_mood(hapiness):
        print "Happiness level: {}".format(str(hapiness))
        mood = 2 # happy and relaxed by default
        if hapiness > 80:
            mood = 4
        elif hapiness > 60:
            mood = 3
        elif hapiness > 40:
            mood = 2
        elif hapiness > 20:
            mood = 1
        else:
            mood = 0
        return mood

    return {
        "rgb": [round_up(r), round_up(g), round_up(b)],
        "hls": [round_up(hls[0]), round_up(hls[1]), round_up(hls[2])],
        "compound": get_mood(b)
    }


def publish_current_mood():
    # get mood color
    color = get_current_mood_color()

    # todo talk directly to the Philips Hue api?

    ## update status file on dropbox
    token = CONFIG["DROPBOX_TOKEN"]

    # delete an existing file in the current folder
    req = requests.post("https://api.dropboxapi.com/2/files/delete",
                        headers={"Content-Type": "application/json",
                                   "Authorization": "Bearer {}".format(token)},
                        json={"path": "/current/mood"})
    print "Delete the existing status: HTTP {}, text: {}".format(req.status_code, req.text)

    # resolve compound color to a folder name
    folder = color["compound"]

    # copy the corresponding file to the current folder
    req = requests.post("https://api.dropboxapi.com/2/files/copy",
                        headers={"Content-Type": "application/json",
                                 "Authorization": "Bearer {}".format(token)},
                        json={
                            "from_path": "/{}/mood".format(folder),
                            "to_path": "/current/mood"
                        })
    print "Publish new status: HTTP {}, text: {}".format(req.status_code, req.text)

    return


def resolve_mood(text):
    try:
        sentence = {
            "sentence": text
        }

        result = ALGORITHM.pipe(sentence)
        if not result or not result.result:
            return

        sentiment = result.result[0]

        verdict = "neutral"
        overall_sentiment = sentiment.get('compound', 0)

        if overall_sentiment > 0:
            sentiment_results["positive"] += 1
            verdict = "positive"
        elif overall_sentiment < 0:
            sentiment_results["negative"] += 1
            verdict = "negative"
        else:
            sentiment_results["neutral"] += 1

        # increment counter so we can work out averages
        sentiment_averages["total"] += 1

        for k, v in sentiment_results.iteritems():
            if k == "total" or v == 0:
                continue
            sentiment_averages[k] = round(
                float(v) / float(sentiment_averages["total"]) * 100, 2)

        # print to the console what just happened
        print 'Comment "{}" was {}, compound result {}'.format(text, verdict, overall_sentiment)

    except Exception as exception:
        # a few things can go wrong but the important thing is keep going
        # print the error and then move on
        print "Something went wrong processing the text: {}".format(text)
        print traceback.format_exc(exception)


def process_message(data):

    text = data.get("text", None)

    if not text or data.get("subtype", "") == "channel_join":
        return

    # remove any odd encoding
    text = text.encode('utf-8')

    channel = data.get("channel", None)
    if not channel:
        return

    if "current mood?" in text:
        return display_current_mood(channel)

    # don't log the current mood reply!
    if text.startswith('Positive:'):
        return

    # update overall sentiment
    resolve_mood(text)

    # publish results
    publish_current_mood()
