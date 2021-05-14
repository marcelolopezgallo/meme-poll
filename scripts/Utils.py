import os

from tinydb import TinyDB, Query

def get_nickname(from_user):
    if from_user['username']:
        nickname = '@' + from_user['username']
    else:
        nickname = from_user['first_name']
    
    return nickname

def get_winners(chat_id, filter=None, value=None):
    if filter == "week":
        poll_array = polls.search((Query().status == 'finished') & (Query().type == 'daily') & (Query().winner.exists()) & (Query().chat_id == chat_id) & (Query().week_number == value))
    else:
        poll_array = polls.search((Query().status == 'finished') & (Query().type == 'daily') & (Query().winner.exists()) & (Query().chat_id == chat_id))

    winners = []
    for poll in poll_array:
        data = {
            'user_id': poll['winner'],
            'msg_id': images.get((Query().poll_doc_id == poll.doc_id) & (Query().user_id == poll['winner']))['msg_id']
        }
        winners.append(data)
    
    return winners


def count_winners(chat_id, filter=None, value=None):
    if filter == "week":
        poll_array = polls.search((Query().status == 'finished') & (Query().type == 'daily') & (Query().winner.exists()) & (Query().chat_id == chat_id) & (Query().week_number == value))
    else:
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


dir_path = os.path.dirname(os.path.realpath(__file__))
DB_DIR = f"{dir_path}/../db"
db = TinyDB(f'{DB_DIR}/db.json')
users = db.table('users')
images = db.table('images')
polls = db.table('polls')
banned_users = db.table('banned_users')