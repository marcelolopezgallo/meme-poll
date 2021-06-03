import os
import datetime

from tinydb import TinyDB, Query
import Utils as Utils

dir_path = os.path.dirname(os.path.realpath(__file__))
DB_DIR = f"{dir_path}/../db"
db = TinyDB(f'{DB_DIR}/db.json')
polls = db.table('polls')

all_polls = polls.all()

for poll in all_polls:
    if poll['type'] == 'daily':
        poll_images = Utils.get_participants(poll['chat_id'], poll_doc_ids=[poll.doc_id], poll_type=poll['type'])
    elif poll['type'] == 'champions':
        poll_images = Utils.get_participants(poll['chat_id'], poll_type='champions', week_number=poll['week_number'])
    
    if 'participants' not in poll:
        update_data = {
            'participants': [{
                    'user_id': image['user_id'],
                    'msg_id': image['msg_id']
                } for image in poll_images]
        }

        polls.update(update_data, doc_ids=[poll.doc_id])
        print(f"updated poll: {poll.doc_id}")
    else:
        print(f"ignored poll: {poll.doc_id}")