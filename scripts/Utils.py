import os
import datetime
import json

from tinydb import TinyDB, Query

def get_nickname(from_user):
    if from_user['username']:
        nickname = '@' + from_user['username']
    else:
        nickname = from_user['first_name']
    
    return nickname

def get_winners(chat_id, filter=None, value=None, user_ids=None):
    if filter == "week":
        poll_array = polls.search((Query().status == 'finished') & (Query().type == 'daily') & (Query().winner.exists()) & (Query().chat_id == chat_id) & (Query().week_number == value))
    else:
        poll_array = polls.search((Query().status == 'finished') & (Query().type == 'daily') & (Query().winner.exists()) & (Query().chat_id == chat_id))

    winners = []
    for poll in poll_array:
        data = {
            'user_id': poll['winner'],
            'msg_id': images.get((Query().poll_doc_id == poll.doc_id) & (Query().user_id == poll['winner']))['msg_id'],
            'date': poll['date']
        }
        winners.append(data)
    
    if user_ids:
        aux = [d for d in winners if d['user_id'] in user_ids]
        winners = aux

    return winners


def count_winners(chat_id, poll_type, value=None):
    if poll_type == "champions":
        poll_array = polls.search((Query().status == 'finished') & (Query().type == 'champions') & (Query().winner.exists()) & (Query().chat_id == chat_id))
    elif poll_type == "daily":
        poll_array = polls.search((Query().status == 'finished') & (Query().type == 'daily') & (Query().winner.exists()) & (Query().chat_id == chat_id))
    
    winners = []
    for poll in poll_array:
        winner_index = next((index for (index, winner) in enumerate(winners) if winner["user_id"] == poll['winner']), None)
        if isinstance(winner_index, int):
            winners[winner_index]['total_wins'] += 1
        else:
            data = {
                'user_id': poll['winner'],
                'total_wins': 1
            }
            winners.append(data)
    
    return winners

def poll_in_progress(chat_id, poll_type):
    poll = polls.get((Query().current == True) & (Query().chat_id == chat_id) & (Query().type == poll_type))
    if poll:
        poll_in_progress = True
    else:
        poll_in_progress = False
    
    return poll_in_progress


def get_poll_data(chat_id, poll_type):
    poll = polls.get((Query().current == True) & (Query().chat_id == chat_id) & (Query().type == poll_type))

    return poll

def ignore_poll(chat_id, poll_type):
    today = datetime.datetime.now().strftime("%d/%m/%Y")
    previous_polls = polls.search((Query().date == today) & (Query().chat_id == chat_id) & (Query().type == poll_type))
    
    return True in (previous_poll['status'] == 'finished' and chat_id not in UNLIMITED_POLLS_WHITELIST for previous_poll in previous_polls)

dir_path = os.path.dirname(os.path.realpath(__file__))
DB_DIR = f"{dir_path}/../db"
db = TinyDB(f'{DB_DIR}/db.json')
users = db.table('users')
images = db.table('images')
polls = db.table('polls')
banned_users = db.table('banned_users')

LOCAL_CONFIG_PATH = f"{dir_path}/../.local_config.json"

if os.path.exists(LOCAL_CONFIG_PATH):
    with open(LOCAL_CONFIG_PATH) as f:
        local_config = json.loads(f.read())
        UNLIMITED_POLLS_WHITELIST = local_config['UNLIMITED_POLLS_WHITELIST']
        UNLIMITED_IMAGES_WHITELIST = local_config['UNLIMITED_IMAGES_WHITELIST']
        PIN_ENABLED = local_config['PIN_ENABLED']
        ANONYMOUS_POLL = local_config['ANONYMOUS_POLL']
        POLLING_INTERVAL = local_config['POLLING_INTERVAL']
        ALLOW_MULTIPLE_ANSWERS = local_config['ALLOW_MULTIPLE_ANSWERS']
        POLL_TIMER = local_config['POLL_TIMER']
        FIRST_REMINDER = local_config['FIRST_REMINDER']
        READ_LATENCY = local_config['READ_LATENCY']
        CLEAN_HISTORY_ALLOWLIST = local_config['CLEAN_HISTORY_ALLOWLIST']
        MAX_AUTOVOTES_PER_WEEK = local_config['MAX_AUTOVOTES_PER_WEEK']
        CHAMPIONS_POLL_DAY = local_config['CHAMPIONS_POLL_DAY']