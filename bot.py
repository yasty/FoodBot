#-*- coding: utf-8 -*-
import time, json, copy, datetime, multiprocessing, requests, re, string, sys
from slackclient import SlackClient
from yelpapi import YelpAPI
from bs4 import BeautifulSoup

class Choice(object):
    def __init__(self, name=None, url=None, rating=None, img_url = None, categories=None,
                 address=None, phone=None, pricing=None):
        self.name = name
        self.votes = 0
        self.url = url
        self.rating = rating
        self.img_url = img_url
        self.categories = categories
        self.address = address
        self.phone = phone
        self.pricing = pricing

    def build_attachment(self):
        data = {}
        data["fallback"] = self.name
        data["title"] = self.name
        if self.url.startswith("http://www.yelp.com/") or self.url.startswith("https://www.yelp.com/") \
            or self.url.startswith("http://yelp.com/") or self.url.startswith("https://yelp.com/"):
            data["title_link"] = self.url
        data["text"] = "Located at *{0}*\n*Phone: * {1}\n*Pricing: * {2}".format(self.address, self.phone, self.pricing)
        data["fields"] = []
        if self.categories:
            categories = {}
            categories["title"] = "Categories"
            cats = "\n".join([c[0] for c in self.categories])
            categories["value"] = cats
            categories["short"] = True
            data["fields"].append(categories)
        if self.rating:
            rating = {}
            rating["title"] = "Rating"
            rating["value"] = str(self.rating)+"/5"
            rating["short"] = True
            data["fields"].append(rating)
        data["mrkdwn_in"] = ["text"]
        if self.img_url:
            data["thumb_url"] = self.img_url
        return data

def split_msg(msg):
    s = msg.partition(" ")
    return s[0].strip(), s[2].strip()

def process_text(text):
    text = text.strip()
    text = (c for c in text if 0 < ord(c) < 127)
    text = ''.join(text)
    text = re.sub(r'([^\s\w]|_)+', '', text)
    return text

def send_msg(txt, cnl):
    sc.api_call("chat.postMessage", channel=cnl, username=USERNAME, text=txt)

def get_key(item):
    return item.votes

def get_name(sc, user):
    global USERS
    if user not in USERS.keys():
        response = json.loads(sc.api_call("users.info", user=user))
        name = response["user"]["name"]
        USERS[user] = name
    return USERS[user]

def post_attachment(txt, cnl, att):
    params = {}
    params["token"] = token
    params["text"] = txt
    params["channel"] = cnl
    params["username"] = USERNAME
    params["attachments"] = json.dumps(att)
    response = requests.post("https://slack.com/api/chat.postMessage", params=params)
    print response.content

def post_snippet(cnl, content, fn, title):
    files = {"file": content}
    channel = []
    channel.append(cnl)
    params = {}
    params["token"] = token
    params["channels"] = channel
    params["username"] = USERNAME
    params["filename"] = fn
    params["title"] = title
    response = requests.post("https://slack.com/api/files.upload", params=params, files=files)
    return response.content

def get_yelp_results(term):
    global yelp
    response = yelp.search_query(term=term, location=LOCATION)
    return response

def build_choice(business_dict):
    name = None
    url = None
    rating = None
    img_url = None
    categories = None
    address = None
    phone = None
    if "name" in business_dict.keys():
        name = business_dict["name"]
    if "url" in business_dict.keys():
        url = business_dict["url"]
    if "rating" in business_dict.keys():
        rating = business_dict["rating"]
    if "image_url" in business_dict.keys():
        img_url = business_dict["image_url"]
    if "categories" in business_dict.keys():
        categories = business_dict["categories"]
    if "location" in business_dict.keys():
        if "address" in business_dict["location"].keys():
            if len(business_dict["location"]["address"])!=0:
                address = business_dict["location"]["address"][0]
    if "display_phone" in business_dict.keys():
        phone = business_dict["display_phone"]
    elif "phone" in business_dict.keys():
        phone = business_dict["phone"]
    print name
    print url
    print rating
    print img_url
    print categories
    print address
    print phone
    tmp = Choice(name, url, rating, img_url, categories, address, phone)
    return tmp

def get_pricing(term, indices=[0]):
    start_values = {}
    for i in indices:
        if (i/10) not in start_values.keys():
            start_values[i/10] = []
        start_values[i/10].append(i%10)
    url = "http://www.yelp.com/search?find_desc={0}&find_loc=6+Metrotech+Ctr,+Brooklyn,+NY&start={1}"
    pricing_values = []
    for i in sorted(start_values.keys()):
        response = requests.get(url.format(term, i))
        soup = BeautifulSoup(response.content)
        results = soup.find_all("li", {"class": "regular-search-result"})
        for num in start_values[i]:
            result = results[i].find("span", {"class": "business-attribute price-range"})
            if result:
                pricing_values.append(result.string)
            else:
                pricing_values.append(None)
    print pricing_values
    return pricing_values

def build_fr_term(term, result_numbers=[0]):
    response = get_yelp_results(term)
    if "businesses" in response.keys():
        businesses = response["businesses"]
        result = []
        if businesses:
            indices = []
            for num in result_numbers:
                if num<len(businesses):
                        tmp = build_choice(businesses[num])
                        result.append(tmp)
                        indices.append(num)
            pricing_values = get_pricing(term, indices)
            if len(pricing_values)==len(result):
                for i in range(len(result)):
                    result[i].pricing = pricing_values[i]
        else:
            tmp = Choice(name=term, url=term)
            result.append(tmp)
        if len(result)==1:
            return result[0]
        return result

def rsvp(sc, data):
    """indicate that you will be attending the event."""
    global ATTENDEES, USERS
    if type(data)==type({}):
        if ("user" in data.keys()) and ("channel" in data.keys()):
            if (data["user"]) and (type(data["user"]) in string_types) \
                and (data["channel"]) and (type(data["channel"]) in string_types):
                user = data["user"]
                channel = data["channel"]
                name = get_name(sc, user)
                msg = u""
                if user not in ATTENDEES:
                    ATTENDEES.append(user)
                    msg = u"{0} has RSVP'ed".format(name)
                else:
                    msg = u"{0} is already RSVP'ed".format(name)
                print msg
                send_msg(msg, channel)

def dersvp(sc, data):
    """remove name from list of attendees."""
    global ATTENDEES, USERS
    if type(data)==type({}):
        if ("user" in data.keys()) and ("channel" in data.keys()):
            if (data["user"]) and (type(data["user"]) in string_types) \
                and (data["channel"]) and (type(data["channel"]) in string_types):
                user = data["user"]
                channel = data["channel"]
                name = get_name(sc, user)
                msg = u""
                if user not in ATTENDEES:
                    msg = u"{0} is not RSVP'ed yet".format(name)
                else:
                    ATTENDEES.remove(user)
                    msg = u"{0} is no longer RSVP'ed".format(name)
                print msg
                send_msg(msg, channel)

def vote(sc, data):
    """[choice] cast your vote for choice. Choice can be an existing option's number as shown in !choices, choice name, or a new option."""
    global CHOICES, VOTES, USERS
    if type(data)==type({}):
        if ("user" in data.keys()) and ("data" in data.keys()) and ("channel" in data.keys()):
            if (data["data"]) and (type(data["data"]) in string_types) \
                and (data["user"]) and (type(data["user"]) in string_types) \
                and (data["channel"]) and (type(data["channel"]) in string_types):
                vote_for = process_text(data["data"])
                channel = data["channel"]
                if len(vote_for)>50:
                    msg = u"Restaurant name too long"
                    print msg
                    send_msg(msg, channel)
                    return
                user = data["user"]
                index = -1
                try:
                    index = int(vote_for) - 1
                    if (index<len(CHOICES) and index>=0 and len(CHOICES)>0):
                        vote_for = CHOICES[index].name
                    else:
                        msg = "Not a valid choice."
                        send_msg(msg, channel)
                        return
                except:
                    tmp = build_fr_term(vote_for)
                    for ind, item in enumerate(CHOICES):
                        if tmp.url.lower()==item.url.lower():
                            index = ind
                            break
                    if index == -1:
                        CHOICES.append(tmp)
                        index = len(CHOICES)-1
                prev = -1
                if user in VOTES.keys():
                    prev = VOTES[user]
                name = get_name(sc, user)
                msg = u""
                if prev>-1:
                    if (CHOICES[prev]==CHOICES[index]):
                        msg = u"You're already voting for that option"
                    else:
                        CHOICES[prev].votes -= 1
                        CHOICES[index].votes += 1
                        msg = u"{0} changed vote from {1} to {2}".format(name, CHOICES[prev].name, CHOICES[index].name)
                        if CHOICES[prev].votes<1:
                            index-=1
                            for user in VOTES:
                                if VOTES[user]>prev:
                                    VOTES[user] -= 1
                            CHOICES.pop(prev)
                else:
                    CHOICES[index].votes += 1
                    msg = u"Vote recorded: {0} wants {1}".format(USERS[user], CHOICES[index].name)
                VOTES[user] = index
                print msg
                send_msg(msg, channel)

def choices(sc, data):
    """show current choices people are voting on."""
    if type(data)==type({}):
        if "channel" in data.keys():
            if data["channel"] and (type(data["channel"]) in string_types):
                channel = data["channel"]
                msg = u""
                attachments = []
                if not len(CHOICES):
                    msg = u"No choices currently added"
                else:
                    for index, choice in enumerate(CHOICES):
                        msg += u"{0}. {1}\n".format(index+1, choice.name)
                        response = choice.build_attachment()
                        if type(response) == type({}):
                            attachments.append(response)
                        '''if choice.url:
                            msg += choice.url + "\n"'''
                print msg
                print attachments
                post_attachment(msg, channel, attachments)
    
def show_poll(sc, data):
    """show current rankings."""
    if type(data)==type({}):
        if "channel" in data.keys():
            if data["channel"] and (type(data["channel"]) in string_types):
                msg = u""
                if not len(CHOICES):
                    msg = u"No poll to show"
                else:
                    tmp = copy.deepcopy(CHOICES)
                    tmp = sorted(tmp, key=get_key, reverse=True)
                    for index, item in enumerate(tmp):
                        msg += u"{0}. {1} with {2} votes\n".format(index+1, item.name, item.votes)
                print msg
                send_msg(msg, data["channel"])
    
def attendees(sc, data):
    """shows a list of people currently RSVP'ed."""
    if type(data)==type({}):
        if "channel" in data.keys():
            channel = data["channel"]
            if len(ATTENDEES):
                msg = u"Attending: "
                if data["channel"] and (type(data["channel"]) in string_types):
                    msg += ", ".join([get_name(sc, user) for user in ATTENDEES])
            else:
                msg = u"No one currently attending"
            print msg
            send_msg(msg, channel)

def help(sc, data):
    """displays this message."""
    if type(data)==type({}):
        if "channel" in data.keys():
            channel = data["channel"]
            msg = "{0:15}{1}\n".format("!help", help.__doc__)
            for cmd in COMMANDS:
                if cmd!="!help":
                    msg += "{0:15}{1}\n".format(cmd, COMMANDS[cmd].__doc__)
            msg.expandtabs
            print msg
            send_msg(msg, channel)

def when(sc, data):
    """displays when the next food day is"""
    if type(data)==type({}):
        if "channel" in data.keys():
            channel = data["channel"]
            d = datetime.date.today()
            days_ahead = 4 - d.weekday()
            if days_ahead <0:
                days_ahead +=7
            d = d + datetime.timedelta(days_ahead)
            if (d == datetime.date.today()):
                msg = "Today is food day!!1one!"
            else:
                msg = d.strftime("Next food day is on %A, %B %d, %Y.")
            print msg
            send_msg(msg, channel)

def recommend(sc, data):
    """[term] get top yelp recommendations for the given term"""
    if type(data)==type({}):
        if "channel" in data.keys() and "data" in data.keys():
            if data["data"].strip() and data["channel"].strip():
                channel = data["channel"]
                term = data["data"]
                if len(term)<40:
                    attachments = []
                    recommendations = build_fr_term(term, range(3))
                    if type(recommendations)==type([]):
                        for recommendation in recommendations:
                            try:
                                attachments.append(recommendation.build_attachment())
                            except:
                                pass
                        msg = u"Top {0} recommendations for {1} near Poly.".format(len(attachments), term)
                        print attachments
                        post_attachment(msg, channel, attachments)
                    else:
                        msg = u"No recommendations available."
                        print msg
                        send_msg(msg, channel)
                else:
                    msg = u"Recommendation query too long"
                    send_msg(msg, channel)

def source(sc, data):
    """uploads a snippet with the bot's source code"""
    if type(data)==type({}):
        if "channel" in data.keys():
            channel = data["channel"]
            filename = sys.argv[0]
            with open(filename, "rb") as r:
                response = post_snippet(channel, r, filename, filename)
                print response

config = {}
with open("config.json", "r") as r:
    config = json.load(r)

token = config["token"]
yck = config["yck"]
ycs = config["ycs"]
ytok = config["ytok"]
yts = config["yts"]

cnl = ""
ATTENDEES = []
VOTES = {}
CHOICES = []
USERS = {}
USERNAME = "SouperBot"
LOCATION = "6 Metrotech Ctr, Brooklyn, NY"
COMMANDS = {"!vote": globals()["vote"], "!rsvp": globals()["rsvp"], "!attendees": globals()["attendees"], "!dersvp": globals()["dersvp"],
        "!choices": globals()["choices"], "!help": globals()["help"], "!show_poll": globals()["show_poll"], "!when": globals()["when"],
        "!recommend": globals()["recommend"], "!source": globals()["source"]}
string_types = [type(u""), type("")]
sc = SlackClient(token)
yelp = YelpAPI(yck, ycs, ytok, yts)

if sc.rtm_connect():
    cnl = sc.server.channels.find("food-day")
    while True:
        read = {}
        try:
            read = sc.rtm_read()
        except:
            if sc.rtm_connect():
                read = sc.rtm_read()
        for d in read:
            if ("type" in d.keys()):
                if d["type"]=="message" and d['channel']==cnl.id and ("subtype" not in d.keys()):
                    msg = d["text"]
                    cmd, options = split_msg(msg)
                    user = d["user"]
                    args = {"data": options, "user": user, "channel": cnl.id}
                    if cmd in COMMANDS.keys():
                        print args
                        print "Calling {0}".format(cmd)
                        COMMANDS[cmd](sc, args)
        time.sleep(0.5)
