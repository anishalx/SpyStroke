# SpyStroke: Advanced Keylogger with Telegram Integration  
[![FOSSA Status](https://app.fossa.com/api/projects/git%2Bgithub.com%2Fanishalx%2FSpyStroke.svg?type=shield)](https://app.fossa.com/projects/git%2Bgithub.com%2Fanishalx%2FSpyStroke?ref=badge_shield)



**SpyStroke** is a sophisticated and stealthy keylogger that captures keystrokes seamlessly and delivers logs directly to your **Telegram bot**. Designed with precision and minimal footprint, SpyStroke ensures effective monitoring while maintaining operational invisibility. This tool is perfect for both **ethical research and cybersecurity enthusiasts**.

<p align="center"><img src="https://raw.githubusercontent.com/khoa083/khoa/main/Khoa_ne/img/Rainbow.gif" width="100%"></p>

<h2 align="center">METHODS FOR TELEGRAM</h2>

<p align="center"><img src="https://raw.githubusercontent.com/khoa083/khoa/main/Khoa_ne/img/Rainbow.gif" width="100%"></p>

## 🚀 Features
- **Real-time keystroke capture** with special key combinations like `Ctrl`, `Shift`, and more.
- **Telegram bot integration** for immediate delivery of keystroke logs.
- **Silent operation**: No terminal output, avoiding suspicion.
- **Cross-platform support**: Works on Windows, macOS, and Linux.
- **Asynchronous log delivery**: Customize time intervals for reports.
- **Clean and lightweight code** with Python.

---

## Installation

To set up and run SpyStroke on your machine, follow these steps:

### 1. Prerequisites

Ensure you have **Python 3.x** installed. You can download Python from the [official Python website](https://www.python.org/downloads/).

### 2. Install Dependencies

Use `pip` to install the required Python package

```bash
pip install pynput python-telegram-bot requests
```

### 3. Clone the Repository

Open your terminal or command prompt and run:

   ```bash
   git clone https://github.com/anishalx/SpyStroke.git
   cd SpyStroke/telegram
   ```




### 4. Set Up Your Telegram Bot

1. Go to [Telegram](https://telegram.org) and search for the **BotFather**.
2. Use the `/newbot` command to create a new bot.
3. You will receive a **bot token**. Keep this safe.
4. Start a chat with your bot by searching for its name in Telegram.
5. Use [this bot](https://t.me/getmyid_bot) to retrieve your **chat ID** (the ID where you want the logs sent).

### 5. Configure the Bot Token and Chat ID

Open the `main.py` file and replace the placeholders with your **bot token** and **chat ID**:

```python
bot_token = "YOUR_TELEGRAM_BOT_TOKEN"
chat_id = "YOUR_TELEGRAM_CHAT_ID"
```

### 6. Run the SpyStroke keylogger:
To start the keylogger, use:
```
python spystroke.py
```

---

##  Usage

1. **Start the Telegram bot**:
   - Send `/start` to your bot to receive the introductory message.
   - Use `/key_logger` to start capturing keystrokes.
   - Use `/exit` to stop the keylogger and shut down the bot.

2. **Configure reporting interval**:
   - Modify the `interval` value in the code to change the frequency of log delivery.

---

## 🖥️ Demo


   
<p align="center">
<a href="https://rumble.com/v6qm3q6-python-keylogger-capture-keystrokes-and-send-logs-to-telegram-full-setup-an.html">
<img src="https://github.com/user-attachments/assets/42098b22-a9e5-4680-8698-5ebf098dd099" alt="Watch the video" width="600">
</a>
</p>


<p align="center"><img src="https://raw.githubusercontent.com/khoa083/khoa/main/Khoa_ne/img/Rainbow.gif" width="70%"></p>

<h2 align="center">METHODS FOR EMAIL</h2>

<p align="center"><img src="https://raw.githubusercontent.com/khoa083/khoa/main/Khoa_ne/img/Rainbow.gif" width="70%"></p>

> [!WARNING]  
> This tool is intended for **educational and ethical use only**. The author is not responsible for any misuse or illegal activity involving this tool. Use responsibly and in compliance with all relevant laws and regulations.

##  Contributing
We welcome contributions to enhance SpyStroke!  
1. **Fork the repository**.
2. **Create a branch**:  
   ```bash
   git checkout -b feature-branch
   ```
3. **Make your changes** and submit a **pull request**.

---
# 📄 License
<details>
<summary>click here to see license</summary>
<br>
This project is licensed under the **MIT License**. See the [LICENSE](LICENSE) file for details.

---
<br>

[![FOSSA Status](https://app.fossa.com/api/projects/git%2Bgithub.com%2Fanishalx%2FSpyStroke.svg?type=large)](https://app.fossa.com/projects/git%2Bgithub.com%2Fanishalx%2FSpyStroke?ref=badge_large)
</details>

## 📢 Support and Feedback
For issues or suggestions, feel free to open a **GitHub issue** or contact me via [Email](mailto:s7vdi6a8l@mozmail.com).

---

[![Star History Chart](https://api.star-history.com/svg?repos=anishalx/spystroke&type=Timeline)](https://www.star-history.com/#anishalx/spystroke&Timeline)
