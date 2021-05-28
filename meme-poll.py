#!/usr/bin/env python

import logging
import os
import json
import time
import datetime

from decouple import config
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, PollHandler, PollAnswerHandler
from telegram.error import TelegramError
from tinydb import TinyDB, Query
import scripts.Utils as Utils


def start(update, context):
    help_message = f"""<b>MEME POLL BOT</b>\n\nEl juego consiste en enviar memes y armar polls para votar al mejor. De Lunes a Sábados se podrán crear polls diarias con /new_poll. Una vez creada la poll, los miembros del grupo podrán subscribir sus memes a la poll con /new_meme. Finalizada la carga de memes, cualquier miembro podrá comenzar la poll con /start_poll y luego, a votar. Por último, los Domingos habrá una /champions_poll entre los ganadores de las polls de la semana.\n\n<u><i>Reglas durante las polls</i></u>\n
    - Habrá <u>{MAX_AUTOVOTES_PER_WEEK} autovoto permitido por cada tipo de poll</u>, es decir, 1 para las diarias y 1 para la champions de la semana. 
    - Aquel usuario que utilice el autovoto en alguna de las polls diarias, será bloqueado para enviar memes por el resto de la semana (incluso si se retracta de su autovoto).
    - Aquel usuario que utilice el autovoto en la champions poll, será bloqueado para enviar memes durante siguiente semana (incluso si se retracta de su autovoto).
    """
    
    context.bot.send_message(chat_id=update.effective_chat.id, text=help_message, parse_mode='HTML')


def receive_image(update, context):
    enable_answer = True
    chat_id = update.effective_chat.id
    nickname = Utils.get_nickname(update.message.from_user)
    poll = Utils.get_poll_data(chat_id)
    
    if poll:
        if poll['status'] == 'loading':
            user = Utils.get_user_data(chat_id, update.message.from_user.id, poll.doc_id)
            if user:
                if user['status'] == "waiting for meme":
                    photo_id = update.message.photo[-1].file_id
                    Utils.create_image({
                        'poll_doc_id': poll.doc_id,
                        'msg_id': update.message.message_id,
                        'user_id': update.message.from_user.id,
                        'chat_id': chat_id,
                        'file_id': photo_id
                    })

                    if update.message.from_user.id not in UNLIMITED_IMAGES_WHITELIST:
                        Utils.update_user(update.message.from_user.id, poll.doc_id, {'status': 'meme received'})

                    output_message = f"Ok {nickname}, meme guardado!"
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


def new_poll_v2(update, context):
    is_a_new_poll = False
    chat_id = update.effective_chat.id
    nickname = Utils.get_nickname(update.message.from_user)
    day = datetime.datetime.now().strftime("%A")

    if day != CHAMPIONS_POLL_DAY:
        poll = Utils.get_poll_data(chat_id)
        if poll:
            if poll['status'] == 'loading':
                output_message = f"Ya existe una Meme Poll abierta. Carga tu meme con /new_meme. Una vez cargados los memes, comenza la poll escribiendo /start_poll."
                logging.info("Poll en preparacion")
            elif poll['status'] == "started":
                output_message = f"Ya existe una poll en curso creada por {Utils.get_user_data(chat_id, poll['started_by'], poll.doc_id)['first_name']}."
                logging.info(f"Poll already exists")
        else:
            today = datetime.datetime.now().strftime("%d/%m/%Y")

            if Utils.enough_polls_for_today(chat_id, 'daily'):
                output_message = f"{nickname}, ya hubo una poll el dia de hoy. Podras crear una nueva mañana."
                logging.info(f"Enough polls for today")
            else:
                is_a_new_poll = True
                poll_doc_id = Utils.create_poll({
                    "date": datetime.datetime.now().strftime("%d/%m/%Y"),
                    "week_number": datetime.datetime.now().isocalendar()[1],
                    "type": "daily",
                    "chat_id": chat_id,
                    "status": "loading",
                    "created_by": update.message.from_user.id,
                    "started_by": "",
                    "current": True,
                    'poll_id': ''
                })
                output_message = f"Se abrio la Meme Poll {today}!. Carga tu meme con /new_meme. Una vez cargados los memes, comenza la poll escribiendo /start_poll."

    else:
        output_message = f"{nickname}, Hoy es domingo y los domingos es día de /champions_poll."

    message = context.bot.send_message(chat_id=chat_id, text=output_message)
    if PIN_ENABLED and is_a_new_poll:
        context.bot.pin_chat_message(chat_id=chat_id, message_id=message.message_id)
        Utils.update_poll(poll_doc_id, {
            'hint_msg_id': message.message_id
        })


def new_meme_v2(update, context):
    chat_id = update.effective_chat.id
    nickname = Utils.get_nickname(update.message.from_user)
    poll = Utils.get_poll_data(chat_id)
    
    if poll:
        if poll['status'] == 'started':
            output_message = f"{nickname}, la poll ya inicio, no se pueden subscribir mas memes."
        elif poll['status'] in ['tied', 'tiebreak']:
            output_message = f"{nickname}, no se pueden subscribir nuevos memes durante el tiebreak."
        elif poll['status'] == 'loading':
            user = Utils.get_user_data(chat_id, update.message.from_user.id, poll.doc_id)
            if user:
                if user['status'] == 'waiting for meme':
                    output_message = f"{nickname}, aun estoy esperando que envies tu meme."
                    logging.info(f"Already waiting for meme: {user}")
                elif user['status'] == "meme received":
                    output_message = f"{nickname}, ya tenes un meme registrado para esta poll."
                    logging.info(f"Already got meme")
            else:
                week_number = datetime.datetime.now().isocalendar()[1]
                
                if Utils.user_is_banned(update.message.from_user.id, week_number):
                    output_message = f"{nickname}, tu usuario fue blockeado por esta semana por {Utils.get_banned_user_data(update.message.from_user.id, week_number)['reason']}."
                else:
                    Utils.create_user({
                        'chat_id': chat_id,
                        'user_id': update.message.from_user.id,
                        'poll_id': poll.doc_id,
                        'username': update.message.from_user.username,
                        'first_name': update.message.from_user.first_name,
                        'status': 'waiting for meme',
                        'autovote': False,
                        'voted_option': None
                    })
                    output_message = f"Ok {nickname}, enviame tu meme!"
    else:
        output_message = f"{nickname}, no hay ninguna poll creada. Podes crear una con /new_poll"
    
    context.bot.send_message(chat_id=chat_id, text=output_message)


def delete_meme(update, context):
    chat_id = update.effective_chat.id
    poll_in_progress, poll_type = Utils.poll_in_progress_v2(chat_id)

    if poll_in_progress:
        poll = Utils.get_poll_data(chat_id, poll_type=poll_type)
        user_image = Utils.get_user_image(update.message.from_user.id, poll.doc_id)
        if user_image:
            try:
                Utils.delete_user_image(user_image.doc_id)
                Utils.update_user(update.message.from_user.id, poll.doc_id, {'status': 'waiting for meme'})
                output_message = f"Ok {Utils.get_nickname(update.message.from_user)}, tu meme fue borrado correctamente."
            except Exception as e:
                logging.error(f"image {user_image.doc_id} delete failed. {e}")
        else:
            output_message = f"{Utils.get_nickname(update.message.from_user)}, no tenes un meme registrado en esta poll."
    else:
        output_message = "No hay ninguna poll en curso."
    
    context.bot.send_message(chat_id=chat_id, text=output_message)


def start_poll_v2(update, context):
    chat_id = update.effective_chat.id
    nickname = Utils.get_nickname(update.message.from_user)
    poll_in_progress, poll_type = Utils.poll_in_progress_v2(chat_id)

    if poll_in_progress:
        now = datetime.datetime.now()
        if now >= now.replace(hour=START_POLL_HOUR):
            if poll_type == 'daily':
                poll = Utils.get_poll_data(chat_id, poll_type)

            if poll['status'] == "loading":
                if PIN_ENABLED:
                    context.bot.unpin_chat_message(chat_id=chat_id, message_id=poll['hint_msg_id'])
                
                poll_images = Utils.get_participants(chat_id, poll_doc_ids=[poll.doc_id], poll_type=poll_type)
                options = []
                for image in poll_images:
                    first_name = Utils.get_user_data(chat_id, image['user_id'])['first_name']
                    options.append(first_name)
                    context.bot.send_message(chat_id=chat_id, text=f"{first_name}", reply_to_message_id=image['msg_id'], allow_sending_without_reply=True)
                
                try:
                    today = datetime.datetime.now().strftime("%d/%m/%Y")
                    message = context.bot.send_poll(chat_id=chat_id, question=f"Meme Poll {today}", is_anonymous=ANONYMOUS_POLL, allows_multiple_answers=ALLOW_MULTIPLE_ANSWERS, options=options)
                    logging.info("Poll started")

                    if PIN_ENABLED:
                        context.bot.pin_chat_message(chat_id=chat_id, message_id=message.message_id)
                        logging.info(f"Poll pinned")
                    
                    Utils.update_poll(poll.doc_id, {
                        'status': 'started',
                        'started_by': update.message.from_user['id'],
                        'started_at': time.time(),
                        'poll_id': message.poll.id,
                        'msg_id': message.message_id,
                        'participants': [{
                            'user_id': image['user_id'],
                            'msg_id': image['msg_id']
                        } for image in poll_images]
                    })
                    output_message = f"La poll fue iniciada por {nickname} y cerrara automaticamente en {int(POLL_TIMER / 60)} min."
                    
                    context.job_queue.run_once(first_reminder, FIRST_REMINDER, context=poll.doc_id)
                    context.job_queue.run_once(schedule_close, POLL_TIMER, context=poll.doc_id)

                except TelegramError as e:
                    if e.message == 'Poll must have at least 2 option':
                        output_message = "No pude iniciar la poll ya que debe haber al menos 2 participantes."
                    logging.error(e.message)

            elif poll['status'] == "started":
                output_message = f"La poll ya fue iniciada por {Utils.get_user_data(chat_id, poll['started_by'], poll.doc_id)['first_name']}"
                logging.info("Poll already started")
        else:
            output_message = f"La poll podrá iniciarese a partir de las {START_POLL_HOUR}"
            logging.info("Poll already started")
    else:
        output_message = f"{nickname}, no hay ninguna poll creada. Podes crear una con /new_poll"
    
    context.bot.send_message(chat_id=chat_id, text=output_message)


def tiebreak_v2(update, context):
    chat_id = update.effective_chat.id
    poll_in_progress, poll_type = Utils.poll_in_progress_v2(chat_id)
    
    if poll_in_progress:
        poll = Utils.get_poll_data(chat_id, poll_type)

        if poll['status'] == 'tied':
            tiebreak_images = [image for image in poll['participants'] if image['msg_id'] in poll['tied_msg_ids']]
            
            options = []
            for image in tiebreak_images:
                first_name = Utils.get_user_data(chat_id, image['user_id'])['first_name']
                options.append(first_name)
                context.bot.send_message(chat_id=chat_id, text=f"{first_name}", reply_to_message_id=image['msg_id'])

            try:
                today = datetime.datetime.now().strftime("%d/%m/%Y")
                message = context.bot.send_poll(chat_id=chat_id, question=f"Desempate {today}", is_anonymous=ANONYMOUS_POLL, allows_multiple_answers=ALLOW_MULTIPLE_ANSWERS, options=options)
                if PIN_ENABLED:
                    context.bot.pin_chat_message(chat_id=chat_id, message_id=message.message_id)
                    logging.info(f"Poll pinned")

                polls.update({'status': 'tiebreak', 'poll_id': message.poll.id, 'msg_id': message.message_id, 'started_at': time.time()}, doc_ids=[poll.doc_id])
                output_message = f"Desempate iniciado por {int(POLL_TIMER / 60)} min!"
                
                context.job_queue.run_once(first_reminder, FIRST_REMINDER, context=poll.doc_id)
                context.job_queue.run_once(schedule_close, POLL_TIMER, context=poll.doc_id)
            
            except Exception as e:
                output_message = f"Error al iniciar el tiebreak: {e}"
                logging.error(e)
        else:
            output_message = f"No hay ninguna Poll empatada."
    
    context.bot.send_message(chat_id=chat_id, text=output_message)


def cancel_poll(update, context):
    chat_id = update.effective_chat.id
    nickname = Utils.get_nickname(update.message.from_user)
    poll = Utils.get_poll_data(chat_id)

    if poll:        
        if poll['created_by'] == update.message.from_user.id:
            if poll['status'] == 'loading':
                if PIN_ENABLED:
                    context.bot.unpin_chat_message(chat_id=chat_id, message_id=poll['hint_msg_id'])
            if poll['status'] in ['started', 'tiebreak']:
                context.bot.stop_poll(chat_id=chat_id, message_id=poll['msg_id'])
                if PIN_ENABLED:
                    context.bot.unpin_chat_message(chat_id=chat_id, message_id=poll['msg_id'])
                    logging.info(f"Poll unpinned")
            
            polls.update({ 'status': 'cancelled', 'cancelled_by': update.message.from_user.id, 'current': False}, doc_ids=[poll.doc_id])
            output_message = f"{nickname}, la poll fue cancelada con exito."
        else:
            output_message = f"{nickname}, la poll solo puede ser cancelada por el usuario que la haya iniciado."
    else:
        output_message = f"{nickname}, no hay ninguna poll activa para cancelar."
    
    context.bot.send_message(chat_id=chat_id, text=output_message)


def hall_of_fame(update, context):
    chat_id = update.effective_chat.id
    daily_winners = Utils.count_winners(chat_id, poll_type='daily')
    weekly_winners = Utils.count_winners(chat_id, poll_type='champions')
    
    daily_message = ""
    if daily_winners:
        for winner in sorted(daily_winners, key = lambda i: i['total_wins'], reverse=True):
            daily_message += "{0:<10} {1}".format(Utils.get_user_data(chat_id, winner['user_id'])['first_name'], winner['total_wins']) + "\n"
    
    weekly_message = ""
    if weekly_winners:
        for winner in sorted(weekly_winners, key = lambda i: i['total_wins'], reverse=True):
            weekly_message += "{0:<10} {1}".format(Utils.get_user_data(chat_id, winner['user_id'])['first_name'], winner['total_wins']) + "\n"
    
    output_message = "<b>Hall of Fame</b>\n\n" + "<b>Diarias</b>\n" + "<pre>" + daily_message + "</pre>" + "\n<b>Semanales</b>\n" + "<pre>" + weekly_message + "</pre>"
    context.bot.send_message(chat_id=chat_id, text=output_message, parse_mode='HTML')


def schedule_close(context):    
    poll_doc_id = context.job.context
    poll = polls.get(doc_id=poll_doc_id)
    chat_id = poll['chat_id']
    poll_message_id = poll['msg_id']
    
    if poll['status'] in ['started', 'tiebreak']:
        today = datetime.datetime.now().strftime("%d/%m/%Y")
        output_message = f"Fin de la Meme Poll {today}"
        context.bot.send_message(chat_id=chat_id, text=output_message)
        polls.update({ 'status': 'closed'}, doc_ids=[poll_doc_id])
        
        if PIN_ENABLED:
            context.bot.unpin_chat_message(chat_id=chat_id, message_id=poll_message_id)
            logging.info(f"Poll unpinned")
        context.bot.stop_poll(chat_id=chat_id, message_id=poll_message_id)
        logging.info(f"Poll Stopped")
    else:
        logging.info("Scheduled close ignored")


def close_poll_v2(update, context):
    chat_id = update.effective_chat.id
    poll = Utils.get_poll_data(chat_id)
    
    if poll:
        
        if poll['status'] in ['started', 'tiebreak']:
            poll_message_id = poll['msg_id']
            
            if poll['type'] == 'daily':
                today = datetime.datetime.now().strftime("%d/%m/%Y")
                output_message = f"Fin de la Meme Poll {today}"
            elif poll['type'] == 'champions':
                week_number = datetime.datetime.now().isocalendar()[1]
                output_message = f"Fin de la Champions Poll - Semana {week_number}"
            
            Utils.update_poll(poll.doc_id, {
                'status': 'closed'
            })
            
            if PIN_ENABLED:
                context.bot.unpin_chat_message(chat_id=chat_id, message_id=poll_message_id)
                logging.info(f"Poll unpinned")

            context.bot.stop_poll(chat_id=chat_id, message_id=poll_message_id)
            logging.info(f"Poll Stopped")
    else:
        output_message = f"No hay ninguna poll iniciada."
    
    context.bot.send_message(chat_id=chat_id, text=output_message)


def receive_poll_update(update, context):
    if update.poll.is_closed:
        poll_results(update, context)


def receive_poll_answer_v2(update, context):
    poll = Utils.get_poll_data(poll_id=update.poll_answer.poll_id)
    voter_id = update.poll_answer.user.id
    voted_option = update.poll_answer.option_ids
    
    if poll:
        if voted_option:
            voted_option = voted_option[0]
            is_autovote = Utils.check_autovote(voter_id, voted_option, poll)

            if is_autovote:
                voter_name = Utils.get_user_data(poll['chat_id'], voter_id, poll.doc_id)['first_name']
                if Utils.previous_autovote(voter_id, poll):
                    output_message = f"{voter_name}, podrías votar a otros alguna vez..."
                else:
                    Utils.add_vote(voter_id, voted_option, poll, is_autovote)
                    autovote_count = Utils.autovote_count(voter_id, poll['chat_id'])

                    
                    if autovote_count < MAX_AUTOVOTES_PER_WEEK:
                        output_message = f"{voter_name}, consumiste {autovote_count} de los {MAX_AUTOVOTES_PER_WEEK} autovotos permitidos por semana."
                    else:
                        output_message = f"{voter_name}, consumiste todos los autovotos permitidos por semana. No podras subscribir mas memes por esta semana."
                        Utils.ban_user(voter_id, poll)

            else:
                Utils.add_vote(voter_id, voted_option, poll, is_autovote)
        else:
            was_autovoter = Utils.retract_vote(voter_id, poll)
            if was_autovoter:
                week_number = datetime.datetime.now().isocalendar()[1]
                voter_name = Utils.get_user_data(poll['chat_id'], voter_id, poll.doc_id)['first_name']
                if Utils.user_is_banned(voter_id, week_number):
                    Utils.unban_user(voter_id, week_number)
                    output_message = f"{voter_name}, recuperaste 1 autovoto y fuiste desbloqueado por esta semana."
                else:
                    output_message = f"{voter_name}, recuperaste 1 autovoto."
    
    context.bot.send_message(chat_id=poll['chat_id'], text=output_message)


def receive_poll_answer_v3(update, context):
    poll = Utils.get_poll_data(poll_id=update.poll_answer.poll_id)
    voter_id = update.poll_answer.user.id
    voted_option = update.poll_answer.option_ids
    
    if poll:
        if voted_option:
            voted_option = voted_option[0]
            is_autovote = Utils.check_autovote(voter_id, voted_option, poll)

            if is_autovote:
                voter_name = Utils.get_user_data(poll['chat_id'], voter_id, poll.doc_id)['first_name']
                if Utils.previous_autovote(voter_id, poll):
                    output_message = f"{voter_name}, podrías votar a otros alguna vez..."
                else:
                    Utils.add_vote(voter_id, voted_option, poll, is_autovote)
                    autovote_count = Utils.autovote_count(voter_id, poll['chat_id'], poll_type=poll['type'])

                    if autovote_count < MAX_AUTOVOTES_PER_WEEK:
                        output_message = f"{voter_name}, consumiste {autovote_count} de los {MAX_AUTOVOTES_PER_WEEK} autovotos permitidos por semana."
                    else:
                        if poll['type'] == 'daily':
                            output_message = f"{voter_name}, consumiste todos los autovotos permitidos para las diarias. No podrás subscribir mas memes por esta semana."
                            Utils.ban_user(voter_id, poll['chat_id'], poll['week_number'])
                        elif poll['type'] == 'champions':
                            output_message = f"{voter_name}, utilizaste todos los autovotos permitidos para las champions. No podrás subscribir memes la próxima semana."
                            Utils.ban_user(voter_id, poll['chat_id'], poll['week_number'] + 1)

            else:
                Utils.add_vote(voter_id, voted_option, poll, is_autovote)
    
    context.bot.send_message(chat_id=poll['chat_id'], text=output_message)


def poll_results(update, context):
    poll_result = 'no votes'
    enable_answer = False
    poll = polls.get((Query().current == True) & (Query().poll_id == update.poll.id))

    if poll:
        chat_id = poll['chat_id']
        poll_doc_id = poll.doc_id

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
                    if poll['type'] == 'daily':
                        winner_id = users.get((Query().poll_id == poll_doc_id) & (Query().first_name == most_voted[0]))['user_id']
                        polls.update({'status': 'finished', 'current': False, 'winner': winner_id}, doc_ids=[poll_doc_id])
                        output_message = f"Ganador: {most_voted[0]}"
                    elif poll['type'] == 'champions':
                        winner_poll = polls.get((Query().chat_id == chat_id) & (Query().date == most_voted[0].split(" ")[1]))
                        winner_id = users.get((Query().poll_id == winner_poll.doc_id) & (Query().first_name == most_voted[0].split(" ")[0]))['user_id']
                        polls.update({'status': 'finished', 'current': False, 'winner': winner_id}, doc_ids=[poll_doc_id])
                        output_message = f"Ganador: {most_voted[0].split(' ')[0]}"
                else:
                    poll_result = 'tied'
                    if poll['type'] == 'daily':
                        output_message = f"Empate entre {most_voted}. Comenzar el desempate con /tiebreak"
                        polls.update({
                            'status': 'tied',
                            'tied_users': [users.get((Query().poll_id == poll_doc_id) & (Query().first_name == u))['user_id'] for u in most_voted],
                            'tied_msg_ids': [images.get((Query().user_id == users.get((Query().poll_id == poll_doc_id) & (Query().first_name == u))['user_id']) & (Query().poll_doc_id == poll.doc_id))['msg_id'] for u in most_voted]
                        }, doc_ids=[poll_doc_id])
                    elif poll['type'] == 'champions':
                        output_message = f"Empate entre {[u.split(' ')[0] for u in most_voted]}. Comenzar el desempate con /champions_tiebreak"
                        polls.update({'status': 'tied', 'tied_msg_ids': [images.get((Query().user_id == users.get((Query().poll_id == polls.get((Query().chat_id == chat_id) & (Query().date == u.split(' ')[1])).doc_id) & (Query().first_name == u.split(' ')[0]))['user_id']) & (Query().poll_doc_id == polls.get((Query().chat_id == chat_id) & (Query().date == u.split(" ")[1])).doc_id))['msg_id'] for u in most_voted]}, doc_ids=[poll_doc_id])

    if enable_answer:
        if poll_result == 'winner':
            context.bot.send_message(chat_id=chat_id, text=output_message, reply_to_message_id=poll['msg_id'])
            if poll['type'] == 'daily':
                photo_id = images.get((Query().user_id == winner_id) & (Query().poll_doc_id == poll_doc_id))['file_id']
                photo = context.bot.get_file(photo_id).download_as_bytearray()
                context.bot.set_chat_photo(chat_id=chat_id, photo=bytes(photo))
                logging.info("Setting chat photo")
        
        elif poll_result == 'tied':
            context.bot.send_message(chat_id=chat_id, text=output_message)
        
        else:
            context.bot.send_message(chat_id=chat_id, text=output_message)


def clean_history(update, context):
    chat_id = update.effective_chat.id

    if update.message.from_user.id in CLEAN_HISTORY_ALLOWLIST:    
        user_docs = users.search(Query().chat_id == chat_id)
        image_docs = images.search(Query().chat_id == chat_id)
        poll_docs = polls.search(Query().chat_id == chat_id)
        banned_users_docs = banned_users.search(Query().chat_id == chat_id)

        logging.info(f"Removing all users in chat {chat_id} from db.")
        for doc in user_docs:
            users.remove(doc_ids=[doc.doc_id])
        
        logging.info(f"Removing all images in chat {chat_id} from db.")
        for doc in image_docs:
            images.remove(doc_ids=[doc.doc_id])
        
        logging.info(f"Removing all polls in chat {chat_id} from db.")
        for doc in poll_docs:
            polls.remove(doc_ids=[doc.doc_id])
        
        logging.info(f"Removing all banned users in chat {chat_id} from db.")
        for doc in banned_users_docs:
            banned_users.remove(doc_ids=[doc.doc_id])
        
        output_message = "Se borro el historico con exito."
    else:
        output_message = "Esta funcionalidad no está permitida para tu usuario."

    context.bot.send_message(chat_id=chat_id, text=output_message)


def first_reminder(context):
    poll_doc_id = context.job.context
    poll = polls.get(doc_id=poll_doc_id)
    chat_id = poll['chat_id']
    today = datetime.datetime.now().strftime("%d/%m/%Y")

    if poll['status'] == 'started':
        output_message = f"La Meme Poll {today} finaliza en {int((POLL_TIMER - FIRST_REMINDER) / 60)} min."
    elif poll['status'] == 'tiebreak':
        output_message = f"El desempate finaliza en {int((POLL_TIMER - FIRST_REMINDER) / 60)} min."

    context.bot.send_message(chat_id=chat_id, text=output_message)


def champions_poll(update, context):
    chat_id = update.effective_chat.id
    day = datetime.datetime.now().strftime("%A")
    
    if day == CHAMPIONS_POLL_DAY:
        if Utils.enough_polls_for_today(chat_id, poll_type='champions'):
            output_message = f"Ya hubo una Champions Poll el día de hoy."
        else:
            poll_in_progress, poll_type = Utils.poll_in_progress_v2(chat_id)
            if poll_in_progress:
                output_message = f"Ya hay una Champions Poll en curso."
            else:
                week_number = datetime.datetime.now().isocalendar()[1]
                week_winners = Utils.get_participants(chat_id, poll_type='champions', week_number=week_number)
                options = []
                for item in week_winners:
                    first_name = Utils.get_user_data(chat_id, item['user_id'])['first_name']
                    options.append(first_name + " " + item['date'])
                    context.bot.send_message(chat_id=chat_id, text=f"{first_name}", reply_to_message_id=item['msg_id'])
                
                try:
                    message = context.bot.send_poll(chat_id=chat_id, question=f"Champions Poll - Semana {week_number}", is_anonymous=ANONYMOUS_POLL, allows_multiple_answers=ALLOW_MULTIPLE_ANSWERS, options=options)
                    if PIN_ENABLED:
                        context.bot.pin_chat_message(chat_id=chat_id, message_id=message.message_id)
                        logging.info(f"Poll pinned")

                    poll_doc_id = Utils.create_poll({
                        "date": datetime.datetime.now().strftime("%d/%m/%Y"),
                        "week_number": datetime.datetime.now().isocalendar()[1],
                        "month_number": datetime.datetime.now().strftime("%d/%m/%Y").split("/")[1],
                        "type": "champions",
                        "chat_id": chat_id,
                        "status": "started",
                        "created_by": update.message.from_user.id,
                        "started_by": update.message.from_user.id,
                        "started_at": time.time(),
                        "poll_id": message.poll.id,
                        "msg_id": message.message_id,
                        "current": True,
                        "participants": [{
                            'user_id': image['user_id'],
                            'date': image['date'],
                            'msg_id': image['msg_id']
                        } for image in week_winners]
                    })

                    for winner in week_winners:
                        if not Utils.get_user_data(chat_id, winner['user_id'], poll_doc_id):
                            new_user_info = {
                                'chat_id': chat_id,
                                'user_id': winner['user_id'],
                                'poll_id': poll_doc_id,
                                'first_name': Utils.get_user_data(chat_id, winner['user_id'])['first_name'],
                                'status': 'in champions',
                                'autovote': False,
                                'voted_option': None
                            }
                            users.insert(new_user_info)

                    output_message = f"Se inicio la Champions Poll - Semana {week_number}!"
                    logging.info("Weekly poll started")

                except TelegramError as e:
                    if e.message == 'Poll must have at least 2 option':
                        output_message = "No pude iniciar la poll ya que debe haber al menos 2 participantes."
                    logging.error(e.message)

    else:
        output_message = f"Las Champion Polls son solo los Domingos."
    
    context.bot.send_message(chat_id=chat_id, text=output_message)


def champions_tiebreak(update, context):
    chat_id = update.effective_chat.id
    poll_in_progress, poll_type = Utils.poll_in_progress_v2(chat_id)

    if poll_in_progress and poll_type == 'champions':
        poll = Utils.get_poll_data(chat_id, poll_type='champions')
        week_number = datetime.datetime.now().isocalendar()[1]
        tiebreak_images = [image for image in poll['participants'] if image['msg_id'] in poll['tied_msg_ids']]

        options = []
        for image in tiebreak_images:
            first_name = Utils.get_user_data(chat_id, image['user_id'])['first_name']
            options.append(first_name + " " + image['date'])
            context.bot.send_message(chat_id=chat_id, text=f"{first_name}", reply_to_message_id=image['msg_id'])
        
        message = context.bot.send_poll(chat_id=chat_id, question=f"Champions Poll Tiebreak - Semana {week_number}", is_anonymous=ANONYMOUS_POLL, allows_multiple_answers=ALLOW_MULTIPLE_ANSWERS, options=options)
        
        polls.update({
            'status': 'tiebreak',
            'poll_id': message.poll.id,
            'msg_id': message.message_id,
            'started_at': time.time()
        }, doc_ids=[poll.doc_id])

        if PIN_ENABLED:
            context.bot.pin_chat_message(chat_id=chat_id, message_id=message.message_id)
            logging.info(f"Poll pinned")

        output_message = f"Se inicio el tiebreak Champions Poll - Semana {week_number}!"
        logging.info("Weekly poll started")
    else:
        output_message = f"No hay ninguna Champions Poll empatada."
    
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
        FIRST_REMINDER = local_config['FIRST_REMINDER']
        READ_LATENCY = local_config['READ_LATENCY']
        CLEAN_HISTORY_ALLOWLIST = local_config['CLEAN_HISTORY_ALLOWLIST']
        MAX_AUTOVOTES_PER_WEEK = local_config['MAX_AUTOVOTES_PER_WEEK']
        CHAMPIONS_POLL_DAY = local_config['CHAMPIONS_POLL_DAY']
        START_POLL_HOUR = local_config['START_POLL_HOUR']

DB_DIR = f"{dir_path}/db"
if not os.path.exists(DB_DIR):
    os.makedirs(DB_DIR)

db = TinyDB(f'{DB_DIR}/db.json')
users = db.table('users')
images = db.table('images')
polls = db.table('polls')
banned_users = db.table('banned_users')

dispatcher.add_handler(CommandHandler('start', start))
dispatcher.add_handler(CommandHandler('new_poll', new_poll_v2))
dispatcher.add_handler(CommandHandler('new_meme', new_meme_v2))
dispatcher.add_handler(CommandHandler('delete_meme', delete_meme))
dispatcher.add_handler(CommandHandler('start_poll', start_poll_v2))
dispatcher.add_handler(CommandHandler('close_poll', close_poll_v2))
dispatcher.add_handler(CommandHandler('tiebreak', tiebreak_v2))
dispatcher.add_handler(CommandHandler('cancel_poll', cancel_poll))
dispatcher.add_handler(CommandHandler('hall_of_fame', hall_of_fame))
dispatcher.add_handler(CommandHandler('clean_history', clean_history))
dispatcher.add_handler(CommandHandler('champions_poll', champions_poll))
dispatcher.add_handler(CommandHandler('champions_tiebreak', champions_tiebreak))
dispatcher.add_handler(PollHandler(receive_poll_update))
dispatcher.add_handler(PollAnswerHandler(receive_poll_answer_v3))
dispatcher.add_handler(MessageHandler(Filters.photo, receive_image))

updater.start_polling(poll_interval=POLLING_INTERVAL, read_latency=READ_LATENCY)
