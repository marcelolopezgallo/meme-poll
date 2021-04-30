import logging
import os

from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, PollAnswerHandler
from tinydb import TinyDB, Query
from datetime import datetime

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
dir_path = os.path.dirname(os.path.realpath(__file__))


def start(update, context):
    context.bot.send_message(chat_id=update.effective_chat.id, text="Soy el bot de la meme poll. Para comenzar con la carga de memes iniciá una poll con /new_poll. Luego, cada usuario puede cargar su meme con /new_meme. Finalmente, cuando todos los memes esten cargados, podés iniciar la poll con /start_poll")


def receive_image(update, context):
    answer = True
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
                    new_image_data = {
                        'poll_doc_id': poll_doc_id,
                        'msg_id': message_id,
                        'user_id': from_user['id'],
                        'chat_id': chat_id
                    }
                    images.insert(new_image_data)
                    if from_user['id'] not in UNLIMITED_IMAGES_WHITELIST:
                        users.update({'status': 'meme received'}, Query().user_id == from_user['id'])
                    output_message = f"Ok {nickname}, meme guardado!"
                    logging.info(f"New image: {new_image_data}")
                else:
                    answer = False
            else:
                output_message = f"{nickname}, antes de enviar la imágen debés enviar /new_meme."
                logging.info(f"No user created")
        else:
            answer = False
    else:
        answer = False
        
    if answer:
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
            output_message = f"Ya pueden cargar los memes con /new_meme. Una vez cargados, comenzá la poll escribiendo /start_poll."
            logging.info("Poll en preparacion")
        elif poll['status'] == "started":
            output_message = f"Ya existe una poll en curso creada por {poll['started_by']}."
            logging.info(f"Poll already exists")
    else:
        today = datetime.now().strftime("%d/%m/%Y")
        previous_polls = polls.search((Query().date == today) & (Query().chat_id == chat_id))
        ignore_poll = True in (previous_poll['status'] == 'finished' and chat_id not in UNLIMITED_POLLS_WHITELIST for previous_poll in previous_polls)
        if ignore_poll:
            output_message = f"{nickname}, ya hubo una poll el día de hoy. Podrás crear una nueva mañana."
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
            output_message = f"Ya pueden cargar los memes con /new_meme. Una vez cargados, comenzá la poll escribiendo /start_poll."
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
            output_message = f"{nickname}, la poll ya inicio, no se pueden subscribir más memes."
        elif poll['status'] in ['tied', 'tiebreak']:
            output_message = f"{nickname}, no se pueden subscribir nuevos memes durante el tiebreak."
        elif poll['status'] == 'loading':
            user = users.get((Query().user_id == from_user['id']) & (Query().chat_id == chat_id) & (Query().poll_id == poll_doc_id))

            if user:
                if user['status'] == 'waiting for meme':
                    output_message = f"{nickname}, aún estoy esperando que envíes tu meme."
                    logging.info(f"Already waiting for meme: {user}")
                elif user['status'] == "meme received":
                    output_message = f"{nickname}, ya tenés un meme registrado para esta poll."
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
        output_message = f"{nickname}, no hay ninguna poll creada. Podés crear una con /new_poll"
    context.bot.send_message(chat_id=chat_id, text=output_message)


def start_poll(update, context):
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
            participants = []
            for image in poll_images:
                username = users.get(Query().user_id == image['user_id'])['username'] or users.get(Query().user_id == image['user_id'])['first_name']
                options.append(username)
                participants.append(image['user_id'])
                context.bot.send_message(chat_id=chat_id, text=f"{users.get(Query().user_id == image['user_id'])['first_name']}", reply_to_message_id=image['msg_id'])
            polls.update({'status': 'started', 'started_by': from_user['id']}, doc_ids=[poll_doc_id])
            today = datetime.now().strftime("%d/%m/%Y")
            message = context.bot.send_poll(chat_id=chat_id, question=f"Meme Poll {today}", is_anonymous=ANONYMOUS_POLL, options=options)
            if PIN_ENABLED:
                context.bot.pin_chat_message(chat_id=chat_id, message_id=message.message_id)
            polls.update({'poll_id': message.poll.id, 'msg_id': message.message_id}, doc_ids=[poll_doc_id])
            payload = {
                message.poll.id: {
                    "participants": [ {'user_id': participant, 'votes': 0} for participant in participants ],
                    "message_id": message.message_id,
                    "chat_id": chat_id,
                    "answers": 0,
                }
            }
            context.bot_data.update(payload)
            output_message = f"La poll ha sido iniciada por {nickname}"
            logging.info("Poll started")
        elif poll['status'] == "started":
            output_message = f"La poll ya fue iniciada por {nickname}"
            logging.info("Poll already started")
    else:
        output_message = f"{nickname}, no hay ninguna poll creada. Podés crear una con /new_poll"
    
    context.bot.send_message(chat_id=chat_id, text=output_message)


def receive_poll_answer(update, context):
    """Summarize a users poll vote"""
    answer = update.poll_answer
    poll_id = answer.poll_id
    option_ids = answer.option_ids

    for option in option_ids:
        context.bot_data[poll_id]['participants'][option]['votes'] += 1
        context.bot_data[poll_id]['answers'] += 1
    
    logging.info(f"New vote: {context.bot_data[poll_id]}")


def poll_results(update, context):
    we_have_a_winner = False
    chat_id = update.effective_chat.id
    from_user = update.message.from_user
    if from_user['username']:
        nickname = '@' + from_user['username']
    else:
        nickname = from_user['first_name']

    poll = polls.get((Query().current == True) & (Query().chat_id == chat_id))
    
    if poll:
        poll_doc_id = poll.doc_id
        poll_id = poll['poll_id']
        if poll['status'] == 'loading':
            output_message = f"{nickname}, la poll no se ha iniciado. Por lo tanto, no tengo resultados."
        else:
            max_votes = 0
            most_voted = []
            if poll['status'] == 'started':
                context.bot.stop_poll(chat_id=chat_id, message_id=poll['msg_id'])

            for participant in context.bot_data[poll_id]['participants']:
                if participant['votes'] == max_votes:
                    max_votes = participant['votes']
                    most_voted.append(participant['user_id'])
                elif participant['votes'] > max_votes:
                    max_votes = participant['votes']
                    most_voted = [participant['user_id']]

            if max_votes == 0:
                output_message = "No hubo votos"
                polls.update({'status': 'finished', 'current': False}, doc_ids=[poll_doc_id])
                logging.info("There were no votes")
            else:
                if len(most_voted) == 1:
                    we_have_a_winner = True
                    output_message = f"Ganador: {users.get(Query().user_id == most_voted[0])['first_name']}"
                    polls.update({'status': 'finished', 'current': False, 'winner': most_voted[0]}, doc_ids=[poll_doc_id])
                else:
                    output_message = "Empate entre {}. Iniciar desempate con /tiebreak".format([users.get(Query().user_id == participant)['first_name'] for participant in most_voted])
                    polls.update({'status': 'tied', 'tied_users': most_voted}, doc_ids=[poll_doc_id])

            if PIN_ENABLED:
                context.bot.unpin_chat_message(chat_id=chat_id, message_id=poll['msg_id'])
    else:
        output_message = f"{nickname}, no hay ninguna poll creada. Podés crear una con /new_poll"
    
    if we_have_a_winner:
        context.bot.send_message(chat_id=chat_id, text=output_message, reply_to_message_id=images.get((Query().chat_id == chat_id) & (Query().poll_doc_id == poll_doc_id) & (Query().user_id == most_voted[0]))['msg_id'])
    else:
        context.bot.send_message(chat_id=chat_id, text=output_message)


def tiebreak(update, context):
    chat_id = update.effective_chat.id
    from_user = update.message.from_user
    if from_user['username']:
        nickname = '@' + from_user['username']
    else:
        nickname = from_user['first_name']
    poll = polls.get((Query().current == True) & (Query().status == 'tied') & (Query().chat_id == chat_id))

    if poll:
        poll_doc_id = poll.doc_id
        poll_id = poll['poll_id']
        tiebreak_images = images.search((Query().chat_id == chat_id) & (Query().poll_doc_id == poll_doc_id) & Query().user_id.one_of(poll['tied_users']))
        options = []
        participants = []
        for image in tiebreak_images:
            username = users.get(Query().user_id == image['user_id'])['username'] or users.get(Query().user_id == image['user_id'])['first_name']
            options.append(username)
            participants.append(image['user_id'])
            context.bot.send_message(chat_id=chat_id, text=f"{users.get(Query().user_id == image['user_id'])['first_name']}", reply_to_message_id=image['msg_id'])
        today = datetime.now().strftime("%d/%m/%Y")
        message = context.bot.send_poll(chat_id=chat_id, question=f"Desempate {today}", is_anonymous=ANONYMOUS_POLL, options=options)
        polls.update({'status': 'tiebreak', 'poll_id': message.poll.id, 'msg_id': message.message_id}, doc_ids=[poll_doc_id])
        if PIN_ENABLED:
            context.bot.pin_chat_message(chat_id=chat_id, message_id=message.message_id)
        payload = {
            message.poll.id: {
                "participants": [ {'user_id': participant, 'votes': 0} for participant in participants ],
                "message_id": message.message_id,
                "chat_id": chat_id,
                "answers": 0,
            }
        }
        context.bot_data.update(payload)
        output_message = f"Empieza el desempate!"
    else:
        output_message = f"{nickname}, no hay ninguna poll empatada."
    
    context.bot.send_message(chat_id=chat_id, text=output_message)


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
            
            polls.update({ 'status': 'cancelled', 'cancelled_by': from_user['id'], 'current': False}, doc_ids=[poll_doc_id])
            output_message = f"{nickname}, la poll fue cancelada con éxito."
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


updater = Updater(token="1737215349:AAEbRrNJlCzBOAhPiDxjN_HfoVTXjBr06rU")
dispatcher = updater.dispatcher

db_dir = f"{dir_path}/db"
if not os.path.exists(db_dir):
    os.makedirs(db_dir)

db = TinyDB(f'{db_dir}/db.json')
users = db.table('users')
images = db.table('images')
polls = db.table('polls')

UNLIMITED_POLLS_WHITELIST = [-590852642, 18969128]
UNLIMITED_IMAGES_WHITELIST = [18969128]
PIN_ENABLED = False
ANONYMOUS_POLL = False

dispatcher.add_handler(CommandHandler('start', start))
dispatcher.add_handler(CommandHandler('new_poll', new_poll))
dispatcher.add_handler(CommandHandler('new_meme', new_meme))
dispatcher.add_handler(CommandHandler('start_poll', start_poll))
dispatcher.add_handler(CommandHandler('poll_results', poll_results))
dispatcher.add_handler(CommandHandler('tiebreak', tiebreak))
dispatcher.add_handler(CommandHandler('cancel_poll', cancel_poll))
dispatcher.add_handler(CommandHandler('hall_of_fame', hall_of_fame))
dispatcher.add_handler(PollAnswerHandler(receive_poll_answer))
dispatcher.add_handler(MessageHandler(Filters.photo, receive_image))

updater.start_polling()
