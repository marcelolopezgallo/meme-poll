#!/usr/bin/env python

import logging
import os
import json
import time

from decouple import config
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, PollAnswerHandler, PollHandler
from tinydb import TinyDB, Query
from datetime import datetime

def start(update, context):
    context.bot.send_message(chat_id=update.effective_chat.id, text="Soy el bot de la meme poll. Para comenzar con la carga de memes inicia una poll con /new_poll. Luego, cada usuario puede cargar su meme con /new_meme. Finalmente, cuando todos los memes esten cargados, podes iniciar la poll con /start_poll")


def receive_image(update, context):
    enable_answer = True
    chat_id = update.effective_chat.id
    message_id = update.message.message_id
    from_user = update.message.from_user
    if from_user['username']:
        nickname = '@' + from_user['username']
    else:
        nickname = from_user['first_name']

    poll = polls.get((Query().current == True) & (Query().chat_id == chat_id))
    
    if poll:
        poll_doc_id = poll.doc_id
        if poll['status'] == 'loading':
            user = users.get((Query().user_id == from_user['id']) & (Query().chat_id == chat_id) & (Query().poll_id == poll_doc_id))
            if user:
                if user['status'] == "waiting for meme":
                    photo_id = update.message.photo[-1].file_id
                    new_image_data = {
                        'poll_doc_id': poll_doc_id,
                        'msg_id': message_id,
                        'user_id': from_user['id'],
                        'chat_id': chat_id,
                        'file_id': photo_id
                    }
                    images.insert(new_image_data)
                    if from_user['id'] not in UNLIMITED_IMAGES_WHITELIST:
                        users.update({'status': 'meme received'}, Query().user_id == from_user['id'])
                    output_message = f"Ok {nickname}, meme guardado!"
                    logging.info(f"New image: {new_image_data}")
                else:
                    enable_answer = False
            else:
                output_message = f"{nickname}, antes de enviar la imagen debes enviar /new_meme."
                logging.info(f"No user created")
        else:
            enable_answer = False
    else:
        enable_answer = False
        
    if enable_answer:
        context.bot.send_message(chat_id=chat_id, text=output_message)


def new_poll(update, context):
    chat_id = update.effective_chat.id
    from_user = update.message.from_user
    if from_user['username']:
        nickname = '@' + from_user['username']
    else:
        nickname = from_user['first_name']
    poll = polls.get((Query().current == True) & (Query().chat_id == chat_id))

    if poll:
        if poll['status'] == 'loading':
            output_message = f"Ya pueden cargar los memes con /new_meme. Una vez cargados, comenza la poll escribiendo /start_poll."
            logging.info("Poll en preparacion")
        elif poll['status'] == "started":
            output_message = f"Ya existe una poll en curso creada por {poll['started_by']}."
            logging.info(f"Poll already exists")
    else:
        today = datetime.now().strftime("%d/%m/%Y")
        previous_polls = polls.search((Query().date == today) & (Query().chat_id == chat_id))
        ignore_poll = True in (previous_poll['status'] == 'finished' and chat_id not in UNLIMITED_POLLS_WHITELIST for previous_poll in previous_polls)
        if ignore_poll:
            output_message = f"{nickname}, ya hubo una poll el dia de hoy. Podras crear una nueva mañana."
            logging.info(f"Poll already finished for today")
        else:
            new_poll_data = {
                "date": today,
                "chat_id": chat_id,
                "status": "loading",
                "created_by": from_user['id'],
                "started_by": "",
                "current": True,
                'poll_id': ''
                }
            polls.insert(new_poll_data)
            output_message = f"Ya pueden cargar los memes con /new_meme. Una vez cargados, comenza la poll escribiendo /start_poll."
            logging.info(f"Poll created")

    context.bot.send_message(chat_id=chat_id, text=output_message)


def new_meme(update, context):
    chat_id = update.effective_chat.id
    from_user = update.message.from_user
    if from_user['username']:
        nickname = '@' + from_user['username']
    else:
        nickname = from_user['first_name']
    poll = polls.get((Query().current == True) & (Query().chat_id == chat_id))
    
    if poll:
        poll_doc_id = poll.doc_id
        if poll['status'] == 'started':
            output_message = f"{nickname}, la poll ya inicio, no se pueden subscribir mas memes."
        elif poll['status'] in ['tied', 'tiebreak']:
            output_message = f"{nickname}, no se pueden subscribir nuevos memes durante el tiebreak."
        elif poll['status'] == 'loading':
            user = users.get((Query().user_id == from_user['id']) & (Query().chat_id == chat_id) & (Query().poll_id == poll_doc_id))

            if user:
                if user['status'] == 'waiting for meme':
                    output_message = f"{nickname}, aun estoy esperando que envies tu meme."
                    logging.info(f"Already waiting for meme: {user}")
                elif user['status'] == "meme received":
                    output_message = f"{nickname}, ya tenes un meme registrado para esta poll."
                    logging.info(f"Already got meme")
            else:
                new_user_info = {
                    'chat_id': chat_id,
                    'user_id': from_user['id'],
                    'poll_id': poll_doc_id,
                    'username': from_user['username'],
                    'first_name': from_user['first_name'],
                    'status': 'waiting for meme'
                    }
                users.insert(new_user_info)
                output_message = f"Ok {nickname}, enviame tu meme!"
                logging.info(f"New user created: {new_user_info}")
    else:
        output_message = f"{nickname}, no hay ninguna poll creada. Podes crear una con /new_poll"
    context.bot.send_message(chat_id=chat_id, text=output_message)


def start_poll(update, context):
    enable_close = False
    chat_id = update.effective_chat.id
    from_user = update.message.from_user
    if from_user['username']:
        nickname = '@' + from_user['username']
    else:
        nickname = from_user['first_name']
    poll = polls.get((Query().current == True) & (Query().chat_id == chat_id))
    
    if poll:
        poll_doc_id = poll.doc_id
        if poll['status'] == "loading":
            poll_images = images.search((Query().chat_id == chat_id) & (Query().poll_doc_id == poll_doc_id))
            options = []
            for image in poll_images:
                first_name = users.get(Query().user_id == image['user_id'])['first_name']
                options.append(first_name)
                context.bot.send_message(chat_id=chat_id, text=f"{first_name}", reply_to_message_id=image['msg_id'])
            
            today = datetime.now().strftime("%d/%m/%Y")
            message = context.bot.send_poll(chat_id=chat_id, question=f"Meme Poll {today}", is_anonymous=ANONYMOUS_POLL, allows_multiple_answers=ALLOW_MULTIPLE_ANSWERS, options=options)
            if PIN_ENABLED:
                context.bot.pin_chat_message(chat_id=chat_id, message_id=message.message_id)
                logging.info(f"Poll pinned")
            
            polls.update({'status': 'started', 'started_by': from_user['id'], 'poll_id': message.poll.id, 'msg_id': message.message_id}, doc_ids=[poll_doc_id])
            output_message = f"La poll ha sido iniciada por {nickname}"
            logging.info("Poll started")
            enable_close = True
        elif poll['status'] == "started":
            output_message = f"La poll ya fue iniciada por {users.get((Query().user_id == poll['started_by']) & (Query().poll_id == poll_doc_id))['first_name']}"
            logging.info("Poll already started")
    else:
        output_message = f"{nickname}, no hay ninguna poll creada. Podes crear una con /new_poll"
    
    context.bot.send_message(chat_id=chat_id, text=output_message)
    if enable_close:
        close_poll(update, context, message.message_id, poll_doc_id)

def tiebreak(update, context):
    time.sleep(2)
    enable_close = False
    enable_answer = False
    poll = polls.get((Query().current == True) & (Query().status == 'tied') & (Query().poll_id == update.poll.id))

    if poll:
        poll_doc_id = poll.doc_id
        poll_id = poll['poll_id']
        chat_id = poll['chat_id']
        tiebreak_images = images.search((Query().chat_id == chat_id) & (Query().poll_doc_id == poll_doc_id) & Query().user_id.one_of(poll['tied_users']))
        options = []
        for image in tiebreak_images:
            first_name = users.get(Query().user_id == image['user_id'])['first_name']
            options.append(first_name)
            context.bot.send_message(chat_id=chat_id, text=f"{first_name}", reply_to_message_id=image['msg_id'])

        today = datetime.now().strftime("%d/%m/%Y")
        message = context.bot.send_poll(chat_id=chat_id, question=f"Desempate {today}", is_anonymous=ANONYMOUS_POLL, allows_multiple_answers=ALLOW_MULTIPLE_ANSWERS, options=options)
        if PIN_ENABLED:
            context.bot.pin_chat_message(chat_id=chat_id, message_id=message.message_id)
            logging.info(f"Poll pinned")

        polls.update({'status': 'tiebreak', 'poll_id': message.poll.id, 'msg_id': message.message_id}, doc_ids=[poll_doc_id])
        output_message = f"Empieza el desempate!"
        enable_close = True
        enable_answer = True
    
    if enable_answer:
        context.bot.send_message(chat_id=chat_id, text=output_message)
    if enable_close:
        close_poll(update, context, message.message_id, poll_doc_id)


def cancel_poll(update, context):
    chat_id = update.effective_chat.id
    from_user = update.message.from_user
    if from_user['username']:
        nickname = '@' + from_user['username']
    else:
        nickname = from_user['first_name']
    poll = polls.get((Query().current == True) & (Query().chat_id == chat_id))

    if poll:
        poll_doc_id = poll.doc_id
        
        if poll['created_by'] == from_user['id']:
            if poll['status'] == 'started':
                context.bot.stop_poll(chat_id=chat_id, message_id=poll['msg_id'])
                if PIN_ENABLED:
                    context.bot.unpin_chat_message(chat_id=chat_id, message_id=poll['msg_id'])
                    logging.info(f"Poll unpinned")
            
            polls.update({ 'status': 'cancelled', 'cancelled_by': from_user['id'], 'current': False}, doc_ids=[poll_doc_id])
            output_message = f"{nickname}, la poll fue cancelada con exito."
        else:
            output_message = f"{nickname}, la poll solo puede ser cancelada por el usuario que la haya iniciado."
    else:
        output_message = f"{nickname}, no hay ninguna poll activa para cancelar."
    
    context.bot.send_message(chat_id=chat_id, text=output_message)


def hall_of_fame(update, context):
    chat_id = update.effective_chat.id
    from_user = update.message.from_user
    if from_user['username']:
        nickname = '@' + from_user['username']
    else:
        nickname = from_user['first_name']
    finished_polls = polls.search((Query().status == 'finished') & (Query().winner.exists()) & (Query().chat_id == chat_id))

    winners = []
    for poll in finished_polls:
        winner_index = next((index for (index, winner) in enumerate(winners) if winner["user_id"] == poll['winner']), None)
        if isinstance(winner_index, int):
            winners[winner_index]['total_wins'] += 1
        else:
            winners.append({ 'user_id': poll['winner'], 'total_wins': 1})
    
    output_message = "Hall of Fame\n\n"
    for winner in winners:
        output_message += f"{users.get((Query().user_id == winner['user_id']) & (Query().chat_id == chat_id))['first_name']}:\t{winner['total_wins']}\n"
    
    context.bot.send_message(chat_id=chat_id, text=output_message)

def close_poll(update, context, poll_message_id, poll_doc_id):
    time.sleep(POLL_TIMER)
    poll = polls.get(doc_id=poll_doc_id)
    
    if poll['status'] in ['started', 'tiebreak']:
        chat_id = poll['chat_id']
        today = datetime.now().strftime("%d/%m/%Y")
        output_message = f"Fin de la Meme Poll {today}"
        context.bot.send_message(chat_id=chat_id, text=output_message)
        polls.update({ 'status': 'closed'}, doc_ids=[poll_doc_id])
        
        if PIN_ENABLED:
            context.bot.unpin_chat_message(chat_id=chat_id, message_id=poll_message_id)
            logging.info(f"Poll unpinned")
        context.bot.stop_poll(chat_id=chat_id, message_id=poll_message_id)
        logging.info(f"Poll Stopped")


def receive_poll_update(update, context):
    if update.poll.is_closed:
        poll_results(update, context)

def poll_results(update, context):
    poll_result = 'no votes'
    enable_answer = False
    poll = polls.get((Query().current == True) & (Query().poll_id == update.poll.id))

    if poll:
        chat_id = poll['chat_id']
        poll_doc_id = poll.doc_id
        poll_id = poll['poll_id']
        if poll['status'] == 'closed':
            enable_answer = True
            max_votes = 0
            most_voted = []

            for participant in update.poll.options:
                if participant['voter_count'] == max_votes:
                    max_votes = participant['voter_count']
                    most_voted.append(participant['text'])
                elif participant['voter_count'] > max_votes:
                    max_votes = participant['voter_count']
                    most_voted = [participant['text']]

            if max_votes == 0:
                output_message = "No hubo votos"
                polls.update({'status': 'finished', 'current': False}, doc_ids=[poll_doc_id])
                logging.info("There were no votes")
            else:
                if len(most_voted) == 1:
                    poll_result = 'winner'
                    output_message = f"Ganador: {most_voted[0]}"
                    polls.update({'status': 'finished', 'current': False, 'winner': users.get((Query().poll_id == poll_doc_id) & (Query().first_name == most_voted[0]))['user_id']}, doc_ids=[poll_doc_id])
                else:
                    poll_result = 'tied'
                    output_message = f"Empate entre {most_voted}. Comenzando desempate..."
                    polls.update({'status': 'tied', 'tied_users': [users.get((Query().poll_id == poll_doc_id) & (Query().first_name == u))['user_id'] for u in most_voted]}, doc_ids=[poll_doc_id])

    if enable_answer:
        if poll_result == 'winner':
            context.bot.send_message(chat_id=chat_id, text=output_message)
            user_id = users.get((Query().first_name == most_voted[0]) & (Query().poll_id == poll_doc_id))['user_id']
            photo_id = images.get((Query().user_id == user_id) & (Query().poll_doc_id == poll_doc_id))['file_id']
            photo = context.bot.get_file(photo_id).download_as_bytearray()
            context.bot.set_chat_photo(chat_id=chat_id, photo=bytes(photo))
            logging.info("Setting chat photo")
        elif poll_result == 'tied':
            context.bot.send_message(chat_id=chat_id, text=output_message)
            tiebreak(update, context)
        else:
            context.bot.send_message(chat_id=chat_id, text=output_message)


dir_path = os.path.dirname(os.path.realpath(__file__))

LOG_DIR = f"{dir_path}/log"
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO, filename=f"{LOG_DIR}/meme-poll.log")

LOCAL_CONFIG_PATH = f"{dir_path}/.local_config.json"
BOT_TOKEN = config('BOT_TOKEN')
updater = Updater(token=BOT_TOKEN, use_context=True)
dispatcher = updater.dispatcher

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


DB_DIR = f"{dir_path}/db"
if not os.path.exists(DB_DIR):
    os.makedirs(DB_DIR)

db = TinyDB(f'{DB_DIR}/db.json')
users = db.table('users')
images = db.table('images')
polls = db.table('polls')

dispatcher.add_handler(CommandHandler('start', start))
dispatcher.add_handler(CommandHandler('new_poll', new_poll))
dispatcher.add_handler(CommandHandler('new_meme', new_meme))
dispatcher.add_handler(CommandHandler('start_poll', start_poll, run_async=True))
#dispatcher.add_handler(CommandHandler('tiebreak', tiebreak, run_async=True))
dispatcher.add_handler(CommandHandler('cancel_poll', cancel_poll))
dispatcher.add_handler(CommandHandler('hall_of_fame', hall_of_fame))
dispatcher.add_handler(PollHandler(receive_poll_update, run_async=True))
dispatcher.add_handler(MessageHandler(Filters.photo, receive_image))

updater.start_polling(poll_interval=POLLING_INTERVAL)
