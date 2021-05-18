import os
import datetime

from tinydb import TinyDB, Query

dir_path = os.path.dirname(os.path.realpath(__file__))
DB_DIR = f"{dir_path}/db"
db = TinyDB(f'{DB_DIR}/db.json')
polls = db.table('polls')

all_polls = polls.all()

for poll in all_polls:
    poll_date = poll['date'].split('/')
    update_data = {
        'week_number': datetime.date(int(poll_date[2]), int(poll_date[1]), int(poll_date[0])).isocalendar()[1],
        'type': 'daily'
    }
    polls.update(update_data, doc_ids=[poll.doc_id])