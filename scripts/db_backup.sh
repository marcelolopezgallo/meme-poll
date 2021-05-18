#!/bin/bash

MY_PATH=$(dirname $0)
DB_PATH="$MY_PATH/../db/db.json"
DB_BACKUP_PATH="$MY_PATH/../db/db_backup.json"

cp $DB_PATH $DB_BACKUP_PATH