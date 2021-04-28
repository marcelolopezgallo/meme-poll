import telegram, logging, os, json, time, collections
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
dir_path = os.path.dirname(os.path.realpath(__file__))

from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, PollAnswerHandler
from tinydb import TinyDB, Query
from datetime import datetime

def start(update, context):
    context.bot.send_message(chat_id=update.effective_chat.id, text="Soy el bot de la meme poll. Para comenzar con la carga de memes iniciá una poll con /new_poll. Luego, cada usuario puede cargar su meme con /new_meme. Finalmente, cuando todos los memes esten cargados, podés iniciar la poll con /start_poll")

def receive_image(update, context):
    chat_id = update.effective_chat.id
    message_id = update.message.message_id
    from_user = update.message.from_user
    poll = polls.get((Query().current == True) & (Query().chat_id == chat_id))
    
    if poll:
        user = users.get(Query().user_id == from_user['id'])
        if user:
            poll_doc_id = poll.doc_id
            image = polls.get((Query().poll_doc_id == poll_doc_id) & (Query().chat_id == chat_id) & (Query().participants.any(Query().user_id == from_user['id'])))
            if not image:
                new_image_data = {
                    'poll_doc_id': poll_doc_id,
                    'msg_id': message_id,
                    'user_id': from_user['id'],
                    'chat_id': chat_id
                    }
                images.insert(new_image_data)
                users.update({'status': 'meme received'}, Query().user_id == from_user['id'])
                output_message = f"Ok @{from_user['username']}, meme guardado!"
                logging.info(f"New image: {new_image_data}")
            else:
                output_message = f"@{from_user['username']}, ya tenés un meme registrado para esta poll."
                logging.info(f"Already got meme")
        else:
            output_message = f"@{from_user['username']}, antes de enviar la imágen debés enviar /new_meme."
            logging.info(f"No user created")
        
        context.bot.send_message(chat_id=chat_id, text=output_message)
    else:
        pass
        #output_message = f"@{from_user['username']}, no hay ninguna poll creada. Podés crear una con /new_poll"

def new_poll(update, context):
    chat_id = update.effective_chat.id
    from_user = update.message.from_user
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
        new_poll_data = {
            "date": today,
            "chat_id": chat_id,
            "status": "loading",
            "created_by": from_user['id'],
            "started_by": "",
            "current": True,
            'poll_id': '',
            'winner': ''
            }
        polls.insert(new_poll_data)
        output_message = f"Ya pueden cargar los memes con /new_meme. Una vez cargados, comenzá la poll escribiendo /start_poll."
        logging.info(f"Poll created")

    context.bot.send_message(chat_id=chat_id, text=output_message)

def new_meme(update, context):
    chat_id = update.effective_chat.id
    from_user = update.message.from_user
    poll = polls.get((Query().current == True) & (Query().chat_id == chat_id))
    
    if poll:
        poll_doc_id = poll.doc_id
        user = users.get((Query().user_id == from_user['id']) & (Query().chat_id == chat_id) & (Query().poll_id == poll_doc_id))
        
        if user:
            if user['status'] == 'waiting for meme':
                output_message = f"@{from_user['username']}, aún estoy esperando que envíes tu meme."
                logging.info(f"Already waiting for meme: {user}")
            elif user['status'] == "meme received":
                output_message = f"@{from_user['username']}, ya tenés un meme registrado para esta poll"
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
            output_message = f"Ok @{from_user['username']}, enviame tu meme!"
            logging.info(f"New user created: {new_user_info}")
    else:
        output_message = f"@{from_user['username']}, no hay ninguna poll creada. Podés crear una con /new_poll"
    context.bot.send_message(chat_id=chat_id, text=output_message)

def start_poll(update, context):
    chat_id = update.effective_chat.id
    from_user = update.message.from_user
    poll = polls.get((Query().current == True) & (Query().chat_id == chat_id))
    
    if poll:
        poll_doc_id = poll.doc_id
        if poll['status'] == "loading":
            poll_images = images.search((Query().chat_id == chat_id) & (Query().poll_doc_id == poll_doc_id))
            options = []
            participants = []
            for image in poll_images:
                username = users.get(Query().user_id == image['user_id'])['username']
                options.append(username)
                participants.append(image['user_id'])
                context.bot.send_message(chat_id=chat_id, text=f"@{username}", reply_to_message_id=image['msg_id'])
            polls.update({'status': 'started', 'started_by': from_user['username']}, doc_ids=[poll_doc_id])
            today = datetime.now().strftime("%d/%m/%Y")
            message = context.bot.send_poll(chat_id=chat_id, question=f"Meme Poll {today}", is_anonymous=False, options=options, close_date=time.time() + POLL_TIMER)
            polls.update({'poll_id': message.poll.id}, doc_ids=[poll_doc_id])
            payload = {
                message.poll.id: {
                    "participants": [ {'user_id': participant, 'votes': 0} for participant in participants ],
                    "message_id": message.message_id,
                    "chat_id": chat_id,
                    "answers": 0,
                }
            }
            context.bot_data.update(payload)
            output_message = f"La poll ha sido iniciada por {from_user['username']}"
            logging.info("Poll started")
        elif poll['status'] == "started":
            output_message = f"La poll ya fue iniciada por {from_user['username']}"
            logging.info("Poll already started")
    else:
        output_message = f"@{from_user['username']}, no hay ninguna poll creada. Podés crear una con /new_poll"
    
    context.bot.send_message(chat_id=chat_id, text=output_message)

def receive_poll_answer(update, context):
    """Summarize a users poll vote"""
    answer = update.poll_answer
    poll_id = answer.poll_id
    option_ids = answer.option_ids

    for option in option_ids:
        context.bot_data[poll_id]['participants'][option]['votes'] += 1
        context.bot_data[poll_id]['answers'] += 1
    
    logging.info(context.bot_data)
    logging.info(f"New vote: {context.bot_data[poll_id]}")
    

def poll_results(update, context):
    chat_id = update.effective_chat.id
    from_user = update.message.from_user
    poll = polls.get((Query().current == True) & (Query().chat_id == chat_id))
    
    if poll:
        poll_doc_id = poll.doc_id
        poll_id = poll['poll_id']
        max_votes = 0
        most_voted = []
        print(context.bot_data)
        for participant in context.bot_data[poll_id]['participants']:
            if participant['votes'] == max_votes:
                max_votes = participant['votes']
                most_voted.append(participant['user_id'])
            elif participant['votes'] > max_votes:
                max_votes = participant['votes']
                most_voted = [participant['user_id']]
        if max_votes == 0:
            output_message = "No hubo votos"
            logging.info("There were no votes")
        else:
            if len(most_voted) == 1:
                output_message = f"El ganador fue @{users.get(Query().user_id == most_voted[0])['username']}"
                polls.update({'status': 'finished', 'current': False, 'winner': most_voted[0]}, doc_ids=[poll_doc_id])
            else:
                output_message = "Empate entre {}. Iniciar desempate con /tiebreak".format(["@" + users.get(Query().user_id == participant)['username'] for participant in most_voted])
                polls.update({'status': 'tied', 'current': False, 'tied_users': most_voted}, doc_ids=[poll_doc_id])
                
    else:
        output_message = f"@{from_user['username']}, no hay ninguna poll creada. Podés crear una con /new_poll"
    
    context.bot.send_message(chat_id=chat_id, text=output_message)

def tiebreak(update, context):
    chat_id = update.effective_chat.id
    from_user = update.message.from_user
    poll = polls.get((Query().status == 'tied') & (Query().chat_id == chat_id))

    if poll:
        poll_doc_id = poll.doc_id
        tiebreak_images = images.search((Query().chat_id == chat_id) & (Query().poll_doc_id == poll_doc_id) & Query().user_id.one_of(poll['tied_users']))
        options = []
        participants = []
        for image in tiebreak_images:
            username = users.get(Query().user_id == image['user_id'])['username']
            options.append(username)
            participants.append(image['user_id'])
            context.bot.send_message(chat_id=chat_id, text=f"@{username}", reply_to_message_id=image['msg_id'])
        polls.update({'status': 'tied finished'}, doc_ids=[poll_doc_id])
        today = datetime.now().strftime("%d/%m/%Y")
        message = context.bot.send_poll(chat_id=chat_id, question=f"Desempate {today}", is_anonymous=False, options=options, close_date=time.time() + POLL_TIMER)
        new_poll_data = {
                "date": today,
                "chat_id": chat_id,
                "status": "tiebreak",
                "created_by": "",
                "started_by": "",
                "current": True,
                'poll_id': message.poll.id,
                'winner': ''
            }
        polls.insert(new_poll_data)
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
        output_message = f"@{from_user['username']}, no hay ninguna poll empatada."
    
    context.bot.send_message(chat_id=chat_id, text=output_message)


updater = Updater(token="1737215349:AAEbRrNJlCzBOAhPiDxjN_HfoVTXjBr06rU")
dispatcher = updater.dispatcher

db = TinyDB(f'{dir_path}/db/db.json')
users = db.table('users')
images = db.table('images')
polls = db.table('polls')

POLL_TIMER = 10800

dispatcher.add_handler(CommandHandler('start', start))
dispatcher.add_handler(CommandHandler('new_poll', new_poll))
dispatcher.add_handler(CommandHandler('new_meme', new_meme))
dispatcher.add_handler(CommandHandler('start_poll', start_poll))
dispatcher.add_handler(CommandHandler('poll_results', poll_results))
dispatcher.add_handler(CommandHandler('tiebreak', tiebreak))
dispatcher.add_handler(PollAnswerHandler(receive_poll_answer))
dispatcher.add_handler(MessageHandler(Filters.photo, receive_image))

updater.start_polling()