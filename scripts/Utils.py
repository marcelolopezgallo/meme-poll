import os
import datetime
import json
import logging

from decouple import Undefined

from tinydb import TinyDB, Query

def get_nickname(from_user):
    if from_user['username']:
        nickname = '@' + from_user['username']
    else:
        nickname = from_user['first_name']
    
    return nickname

def get_participants(chat_id, poll_doc_ids=[], poll_type=None, is_tied=False, tied_users=None, week_number=None, tied_msg_ids=None):
    if poll_type == 'daily':
        if is_tied:
            participants = images.search((Query().chat_id == chat_id) & (Query().poll_doc_id.one_of(poll_doc_ids)) & Query().user_id.one_of(tied_users))
        else:
            participants = images.search((Query().chat_id == chat_id) & (Query().poll_doc_id.one_of(poll_doc_ids)))
    
    elif poll_type == 'champions':
        if is_tied:
            participants = images.search((Query().chat_id == chat_id) & (Query().msg_id.one_of(tied_msg_ids)))
        else:
            poll_array = polls.search((Query().status == 'finished') & (Query().type == 'daily') & (Query().winner.exists()) & (Query().chat_id == chat_id) & (Query().week_number == week_number))

            participants = []
            for poll in poll_array:
                data = {
                    'user_id': poll['winner'],
                    'msg_id': images.get((Query().poll_doc_id == poll.doc_id) & (Query().user_id == poll['winner']))['msg_id'],
                    'date': poll['date']
                }
                participants.append(data)

    return participants


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


def poll_in_progress_v2(chat_id):
    poll = polls.get((Query().current == True) & (Query().chat_id == chat_id))
    if poll:
        poll_in_progress = True
        poll_type = poll['type']
    else:
        poll_in_progress = False
        poll_type = Undefined

    return poll_in_progress, poll_type


def get_poll_data(chat_id=None, poll_type=None, poll_id=None):
    if poll_type:
        poll = polls.get((Query().current == True) & (Query().chat_id == chat_id) & (Query().type == poll_type))
    elif poll_id:
        poll = polls.get(Query().poll_id == poll_id)

    return poll

def get_user_data(chat_id, user_id, poll_doc_id=None):
    user_data = users.get((Query().chat_id == chat_id) & (Query().user_id == user_id))

    return user_data


def ignore_poll(chat_id, poll_type):
    today = datetime.datetime.now().strftime("%d/%m/%Y")
    previous_polls = polls.search((Query().date == today) & (Query().chat_id == chat_id) & (Query().type == poll_type))
    
    return True in (previous_poll['status'] == 'finished' and chat_id not in UNLIMITED_POLLS_WHITELIST for previous_poll in previous_polls)


def check_autovote(voter_id, voted_option, poll):
    if poll['type'] == 'daily':
        if poll['status'] == 'started':
            poll_images = poll['participants']
        elif poll['status'] == 'tiebreak':
            poll_images = [image for image in poll['participants'] if image['msg_id'] in poll['tied_msg_ids']]

    return True if poll_images[voted_option]['user_id'] == voter_id else False

def autovote_count(voter_id, week_number=None):
    polls_this_week = polls.search((Query().week_number.exists()) & (Query().week_number == week_number or datetime.datetime.now().isocalendar()[1]))
    
    autovote_count = 0
    for p in polls_this_week:
        u = users.get((Query().user_id == voter_id) & (Query().poll_id == p.doc_id))
        if u and 'autovote' in u:
            autovote_count += 1
    
    return autovote_count

def add_vote(voter_id, voted_option, poll, is_autovote):
    users.update({
        'voted_option': voted_option,
        'autovote': is_autovote
    }, (Query().user_id == voter_id) & (Query().poll_id == poll.doc_id))
    
    logging.info(f"Adding vote from {voter_id} in poll {poll['poll_id']}")

def retract_vote(voter_id, poll):
    was_autovoter = users.get((Query().user_id == voter_id) & (Query().poll_id == poll.doc_id))['autovote']
    
    users.update({
        'voted_option': None,
        'autovote': None
    }, (Query().user_id == voter_id) & (Query().poll_id == poll.doc_id))

    logging.info(f"Retracting vote from {voter_id} in poll {poll['poll_id']}")

    return was_autovoter


def ban_user(voter_id, poll):
    blocked_user_data = {
        'user_id': voter_id,
        'chat_id': poll['chat_id'],
        'week_number': poll['week_number'],
        'reason': 'superar limite de autovotos'
    }
    banned_users.insert(blocked_user_data)

    logging.info(f"Banned user {voter_id} for week {poll['week_number']}")


def user_is_banned(voter_id, week_number):
    is_banned = banned_users.get((Query().user_id == voter_id) & (Query().week_number == week_number))

    return True if is_banned else False


def unban_user(voter_id, week_number):
    banned_users.remove((Query().user_id == voter_id) & (Query().week_number == week_number))

    logging.info(f"Unbanned user {voter_id} for week {poll['week_number']}")


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