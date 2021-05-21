import os
import datetime

from tinydb import TinyDB, Query

dir_path = os.path.dirname(os.path.realpath(__file__))
DB_DIR = f"{dir_path}/../db"
db = TinyDB(f'{DB_DIR}/db.json')
users = db.table('users')

all_users = users.all()

for user in all_users:
    if user['autovote'] is None:
        update_data = {
            'autovote': False,
        }
        users.update(update_data, doc_ids=[user.doc_id])