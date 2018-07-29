import json
import os
import urllib.parse
import sys
import urllib.request
import time
import psycopg2
import requests
from datetime import datetime
from slackclient import SlackClient
from psycopg2 import sql

from flask import Flask, request, jsonify, make_response

app = Flask(__name__)




@app.route('/', methods=['POST'])
def webhook():
    print("event received")
    GYM_POINTS = 1.0
    TRACK_POINTS = 1.0
    THROW_POINTS = 0.5
    SWIM_POINTS = 1.0
    PICKUP_POINTS = 0.5
    BIKING_POINTS = 1.0
    BOT_CHANNEL = "CBJAJPZ8B"
    data = request.get_json()
    if 'text' in list(data['event'].keys()):
        lower_text = data['event']['text'].lower()
    if data['type'] == "url_verification":
        return jsonify({'challenge': data['challenge']})

    count = 0
    print(request.__dict__)
    print(request.keys())
    print('HTTP_X_SLACK_RETRY_NUM' in list(request.keys()))
    if 'HTTP_X_SLACK_RETRY_NUM' in list(request.keys()):
        print("Retry Number" + request['HTTP_X_SLACK_RETRY_NUM'])
        send_debug_message(str(request['HTTP_X_SLACK_RETRY_NUM']))
    print(data)
    obj = SlackResponse(data)
    if not obj._bot:
        print("not a bot")
        if not obj.isRepeat():
            print("not a repeat")
            if obj._points_to_add > 0:
                print("points to add")
                obj.handle_db()
            else:
                print("executing commands")
                obj.execute_commands()
    print(obj)
    print("responding")
    return make_response("Ok", 200,)


def send_tribe_message(msg, channel="#random"):
    send_message(msg, channel)


def add_num_posts(mention_id, event_time, name):
    # "UPDATE tribe_data SET num_posts=num_posts+1, WHERE name = 'William Syre' AND last_time != "
    try:
        urllib.parse.uses_netloc.append("postgres")
        url = urllib.parse.urlparse(os.environ["HEROKU_POSTGRESQL_MAUVE_URL"])
        conn = psycopg2.connect(
            database=url.path[1:],
            user=url.username,
            password=url.password,
            host=url.hostname,
            port=url.port
        )
        cursor = conn.cursor()
        # get all of the people who's workout scores are greater than -1 (any non players have a workout score of -1)
        cursor.execute(sql.SQL(
            "UPDATE tribe_data SET num_posts=num_posts+1, "
            + "slack_id=%s, "
            + "last_time = %s "
            + "WHERE name = %s AND last_time != %s"), [mention_id[0], event_time, name, event_time])
        if cursor.rowcount == 0:
            #could also be a new person
            cursor.execute(sql.SQL(
                "UPDATE tribe_data SET num_posts=num_posts WHERE name = %s"), [name])
            if cursor.rowcount == 0:
                #new person
                cursor.execute(sql.SQL("INSERT INTO tribe_data VALUES (%s, 0, 0, 0, now(), -1, 1, %s, %s)"),
                               [name, mention_id[0], event_time])
                send_debug_message("%s is new to Tribe" % name)
            else:
                send_debug_message("Found a repeat slack post from ID: %s, TIME: %s, NAME: %s" % (mention_id[0], event_time, name), bot_name=name)
            conn.commit()
            cursor.close()
            conn.close()
            return True
        else:
            conn.commit()
            cursor.close()
            conn.close()
            return False
    except (Exception, psycopg2.DatabaseError) as error:
        send_debug_message(error)


def print_stats(datafield, rev, channel="#random"):
    try:
        urllib.parse.uses_netloc.append("postgres")
        url = urllib.parse.urlparse(os.environ["HEROKU_POSTGRESQL_MAUVE_URL"])
        conn = psycopg2.connect(
            database=url.path[1:],
            user=url.username,
            password=url.password,
            host=url.hostname,
            port=url.port
        )
        cursor = conn.cursor()
        # get all of the people who's workout scores are greater than -1 (any non players have a workout score of -1)
        cursor.execute(sql.SQL(
            "SELECT * FROM tribe_data WHERE workout_score > -1.0"), )
        leaderboard = cursor.fetchall()
        leaderboard.sort(key=lambda s: s[datafield], reverse=rev)  # sort the leaderboard by score descending
        string1 = "Leaderboard:\n"
        for x in range(0, len(leaderboard)):
            string1 += '%d) %s with %.1f points \n' % (x + 1, leaderboard[x][0], leaderboard[x][datafield])
        send_tribe_message(string1, channel)
        cursor.close()
        conn.close()
    except (Exception, psycopg2.DatabaseError) as error:
        send_debug_message(error)


def send_message(msg, chan="#bot_testing", url='', bot_name='Workout Bot'):
    slack_token = os.getenv('BOT_OATH_ACCESS_TOKEN')
    sc = SlackClient(slack_token)
    if url == '':
        sc.api_call("chat.postMessage",channel=chan, text=msg, username=bot_name)
    else:
        sc.api_call("chat.postMessage",channel=chan, text=msg, username=bot_name, icon_url=url)

def send_debug_message(msg, bot_name='Workout Bot'):
    send_message(msg, chan="#bot_testing", bot_name=bot_name)

def get_group_info():
    url = "https://slack.com/api/users.list?token=" + os.getenv('BOT_OATH_ACCESS_TOKEN')
    json = requests.get(url).json()
    return json


def add_to_db(names, addition, ids):  # add "addition" to each of the "names" in the db
    cursor = None
    conn = None
    num_committed = 0
    try:
        urllib.parse.uses_netloc.append("postgres")
        url = urllib.parse.urlparse(os.environ["HEROKU_POSTGRESQL_MAUVE_URL"])
        conn = psycopg2.connect(
            database=url.path[1:],
            user=url.username,
            password=url.password,
            host=url.hostname,
            port=url.port
        )
        cursor = conn.cursor()
        for x in range(0, len(names)):
            print("starting", names[x])
            cursor.execute(sql.SQL(
                "SELECT workout_score FROM tribe_data WHERE name = %s"), (str(names[x]),))
            score = cursor.fetchall()[0][0]
            score = int(score)
            if score != -1:
                cursor.execute(sql.SQL(
                    "UPDATE tribe_data SET num_workouts = num_workouts+1, workout_score = workout_score+%s, last_post = "
                    "now(), slack_id=%s WHERE name = %s"),
                    (str(addition), ids[x], names[x],))
                conn.commit()
                send_debug_message("committed %s with %s points" % names[x], str(addition))
                print("committed %s" % names[x])
                num_committed += 1
            else:
                send_debug_message("invalid workout poster found " + names[x])
    except (Exception, psycopg2.DatabaseError) as error:
        send_debug_message(str(error))
    finally:
        if cursor is not None:
            cursor.close()
            conn.close()
        return num_committed


def add_hydration(data, addition):
    return None #does not work for slack
    cursor = None
    conn = None
    num_committed = 0
    names, ids = get_names_ids_from_message(data, True)
    try:
        urllib.parse.uses_netloc.append("postgres")
        url = urllib.parse.urlparse(os.environ["HEROKU_POSTGRESQL_MAUVE_URL"])
        conn = psycopg2.connect(
            database=url.path[1:],
            user=url.username,
            password=url.password,
            host=url.hostname,
            port=url.port
        )
        cursor = conn.cursor()
        for x in range(0, len(names)):
            cursor.execute(sql.SQL(
                "UPDATE tribe_water SET num_liters = num_liters+%s WHERE id = %s"),
                (str(addition), ids[x],))
            if cursor.rowcount == 0:  # If a user does not have an id yet
                cursor.execute(sql.SQL(
                    "UPDATE tribe_water SET num_liters = num_liters+%s, id = %s WHERE name = %s"),
                    (str(addition), ids[x], names[x],))
                send_debug_message("%s does not have an id yet" % names[x])
            if cursor.rowcount == 0:  # user is not in the db yet
                cursor.execute(sql.SQL("INSERT INTO tribe_water VALUES (%s, 1, %s)"), (names[x], ids[x],))
            conn.commit()
            send_debug_message("committed %s" % names[x])
            num_committed += 1
    except (Exception, psycopg2.DatabaseError) as error:
        send_debug_message(str(error))
    finally:
        if cursor is not None:
            cursor.close()
            conn.close()
        if len(names) == num_committed:
            like_message(data['group_id'], data['id'])
        return num_committed


def print_water():
    try:
        urllib.parse.uses_netloc.append("postgres")
        url = urllib.parse.urlparse(os.environ["HEROKU_POSTGRESQL_MAUVE_URL"])
        conn = psycopg2.connect(
            database=url.path[1:],
            user=url.username,
            password=url.password,
            host=url.hostname,
            port=url.port
        )
        cursor = conn.cursor()
        # get all of the people who's workout scores are greater than -1 (any non players have a workout score of -1)
        cursor.execute(sql.SQL(
            "SELECT * FROM tribe_water WHERE num_liters > -1.0"), )
        leaderboard = cursor.fetchall()
        leaderboard.sort(key=lambda s: s[1], reverse=True)  # sort the leaderboard by score descending
        string1 = "Top 15:\n"
        string2 = "Everyone Else:\n"
        for x in range(0, 15):
            if x < len(leaderboard):
                string1 += '%d) %s with %d points \n' % (x + 1, leaderboard[x][0], leaderboard[x][1])
        if len(leaderboard) > 15:
            for x in range(15, len(leaderboard)):
                string2 += '%d) %s with %d points \n' % (x + 1, leaderboard[x][0], leaderboard[x][1])
        send_tribe_message(string1)  # need to split it up into 2 because groupme has a max message length for bots
        if len(leaderboard) > 15:
            send_tribe_message(string2)
        cursor.close()
        conn.close()
    except (Exception, psycopg2.DatabaseError) as error:
        send_debug_message(error)


def stringFromSeconds(seconds):
    if seconds < 0:
        return seconds, " seconds. You missed it, better luck next year."
    else:
        days = seconds / 60 / 60 / 24
        fracDays = days - int(days)
        hours = fracDays * 24
        fracHours = hours - int(hours)
        minutes = fracHours * 60
        fracMinutes = minutes - int(minutes)
        seconds = fracMinutes * 60
        return "%d days, %d hours, %d minutes, %d seconds" % (days, minutes, hours, seconds)

# def like_file(f, reaction='robot_face'):
#     print(f)
#     slack_token = os.getenv('BOT_OATH_ACCESS_TOKEN')
#     sc = SlackClient(slack_token)
#     res = sc.api_call("reactions.add", name=reaction, file=f)
#     print(res)


def subtract_from_db(names, subtraction, ids):  # subtract "subtraction" from each of the "names" in the db
    cursor = None
    conn = None
    num_committed = 0
    try:
        urllib.parse.uses_netloc.append("postgres")
        url = urllib.parse.urlparse(os.environ["HEROKU_POSTGRESQL_MAUVE_URL"])
        conn = psycopg2.connect(
            database=url.path[1:],
            user=url.username,
            password=url.password,
            host=url.hostname,
            port=url.port
        )
        cursor = conn.cursor()
        for x in range(0, len(names)):
            cursor.execute(sql.SQL(
                "UPDATE tribe_data SET workout_score = workout_score - %s WHERE name = %s"),
                [subtraction, names[x]])
            conn.commit()
            send_debug_message("subtracted %s" % names[x])
            num_committed += 1
    except (Exception, psycopg2.DatabaseError) as error:
        send_debug_message(str(error))
    finally:
        if cursor is not None:
            cursor.close()
            conn.close()
        return num_committed


def reset_scores():  # reset the scores of everyone
    cursor = None
    conn = None
    try:
        urllib.parse.uses_netloc.append("postgres")
        url = urllib.parse.urlparse(os.environ["HEROKU_POSTGRESQL_MAUVE_URL"])
        conn = psycopg2.connect(
            database=url.path[1:],
            user=url.username,
            password=url.password,
            host=url.hostname,
            port=url.port
        )
        cursor = conn.cursor()
        cursor.execute(sql.SQL(
            "UPDATE tribe_data SET num_workouts = 0, workout_score = 0, last_post = now()"))
        conn.commit()
    except (Exception, psycopg2.DatabaseError) as error:
        send_debug_message(str(error))
    finally:
        if cursor is not None:
            cursor.close()
            conn.close()


class SlackResponse:
    # event
    # event_type
    # files = []
    # ts
    # text
    # channel
    # user_id
    # bot
    # mentions = []
    # points_to_add
    # all_ids
    # all_names
    def __init__(self, json_data):
        self._event = json_data['event']
        self._event_time = json_data['event_time']
        self._bot = 'bot_id' in list(self._event.keys()) and self._event['bot_id'] != None
        self._event_type = self._event['type']
        if 'files' in list(self._event.keys()):
            self._files = self._event['files']
        else:
            self._files = []
        self._ts = self._event['ts']
        if 'text' in list(self._event.keys()):
            self._text = self._event['text']
        else:
            self._text = ''
        self._channel = self._event['channel']
        if not self._bot:
            self._user_id = self._event['user']
        else:
            self.user_id = self._event['bot_id']
        self.parse_text_for_mentions()
        if not self._bot:
            self._all_ids = self._mentions + [self._user_id]
        else:
            self._all_ids = self._mentions
        self.match_names_to_ids()
        self._lower_text = self._text.lower()
        self.parse_for_additions()
        

    def parse_text_for_mentions(self):
        text = self._text
        indicies = []
        mention_ids = []
        i = 0
        while(i < len(text)):
            temp = text.find('@', i)
            if temp == -1:
                i = len(text)
            else:
                indicies.append(temp)
                i = temp + 1
        for index in indicies:
            mention_ids.append(text[index + 1:text.find('>', index)])
        self._mentions = mention_ids

    def match_names_to_ids(self):
        mention_ids = self._all_ids
        mention_names = []
        info = get_group_info()
        for id in mention_ids:
            for member in info['members']:
                if member['id'] == id:
                    mention_names.append(member['real_name'])
        self._all_names = mention_names
        if len(self._all_names) > 0:
            self._name = self._all_names[-1]
        else:
            self._name = ""
    
    def parse_for_additions(self):
        GYM_POINTS = 1.0
        TRACK_POINTS = 1.0
        THROW_POINTS = 0.5
        SWIM_POINTS = 1.0
        PICKUP_POINTS = 0.5
        BIKING_POINTS = 1.0
        self._points_to_add = 0
        if '!gym' in self._lower_text:
            self._points_to_add += GYM_POINTS
        if '!track' in self._lower_text:
            self._points_to_add += TRACK_POINTS
        if '!throw' in self._lower_text:
            self._points_to_add += THROW_POINTS
        if '!swim' in self._lower_text:
            self._points_to_add += SWIM_POINTS
        if '!pickup' in self._lower_text:
            self._points_to_add += PICKUP_POINTS
        if '!bike' in self._lower_text:
            self._points_to_add += BIKING_POINTS


    def handle_db(self):
        if not self._repeat:
            num = add_to_db(self._all_names, self._points_to_add, self._all_ids)
            if num == len(self._all_names):
                self.like_message() 
            else:
                self.like_message(reaction='skull_and_crossbones')


    def isRepeat(self):
        self._repeat = add_num_posts([self._user_id], self._event_time, self._name)
        if self._repeat:
            send_debug_message("Found a repeat slack post from ID: %s, TIME: %s, NAME: %s" % (self._user_id, self._ts, str(self._all_names)))


    def execute_commands(self):
        count = 0
        if not self._repeat:
            if "!leaderboard" in self._lower_text:
                count += 1
                print_stats(3, True, channel=self._channel)
            if '!workouts' in self._lower_text:  # display the leaderboard for who works out the most
                count +=1 
                print_stats(2, True, channel=self._channel)
            if '!talkative' in self._lower_text:  # displays the leaderboard for who posts the most
                count +=1
                print_stats(1, True, channel=self._channel)
            if '!handsome' in self._lower_text:  # displays the leaderboard for who posts the most
                count +=1
                print_stats(1, True, channel=self._channel)
            if '!heatcheck' in self._lower_text:
                count +=1
                send_tribe_message("Kenta wins", channel=self._channel)
            if '!regionals' in self._lower_text:
                count +=1
                now = datetime.now()
                regionals = datetime(2019, 4, 28, 8, 0, 0)
                until = regionals - now
                send_tribe_message("regionals is in " + stringFromSeconds(until.total_seconds()), channel=self._channel)
            if '!subtract' in self._lower_text and self._user_id == 'UAPHZ3SJZ':
                send_debug_message("SUBTRACTING: " + self._lower_text[-3:] + " FROM: " + str(self._all_names))
                num = subtract_from_db(self._all_names[:-1], float(self._lower_text[-3:]), self._all_ids[:-1])
                count +=1
            if '!reset' in self._lower_text and self._user_id == 'UAPHZ3SJZ':
                print_stats(3, True, channel=self._channel)
                reset_scores()
                send_debug_message("Reseting leaderboard")
                count +=1
            if '!add' in self._lower_text and self._user_id == 'UAPHZ3SJZ':
                send_debug_message("ADDING: " + self._lower_text[-3:] + " TO: " + str(self._all_names))
                num = add_to_db(self._all_names[:-1], self._lower_text[-3:], self._all_ids[:-1])
                count +=1
            if self._points_to_add > 0:
                self.like_message(reaction='angry')
            if 'groupme' in self._lower_text:
                self.like_message(reaction='thumbsdown')
            if count >= 1:
                self.like_message()


    def like_message(self, reaction='robot_face'):
        slack_token = os.getenv('BOT_OATH_ACCESS_TOKEN')
        sc = SlackClient(slack_token)
        res = sc.api_call("reactions.add", name=reaction, channel=self._channel, timestamp=self._ts)
            

    def __repr__(self):
        return str(self.__dict__)