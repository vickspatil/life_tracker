# Life Tracker — Setup Guide

A Telegram bot that logs your daily activities in plain English and gives you weekly brutally honest reports on how you're tracking against your goals.

---

## Step 1 — Get your API keys

### Telegram Bot Token
1. Open Telegram and message **@BotFather**
2. Send `/newbot`
3. Give it a name (e.g. `VickedLifeBot`) and a username (e.g. `vicked_life_bot`)
4. BotFather will give you a token — copy it

### Your Telegram User ID
1. Message **@userinfobot** on Telegram
2. It will reply with your user ID number — copy it

### Anthropic API Key
1. Go to [console.anthropic.com](https://console.anthropic.com)
2. Sign in → **API Keys** → **Create Key**
3. Copy the key (starts with `sk-ant-...`)

---

## Step 2 — Configure your environment

```bash
cd life_tracker
cp .env.example .env
```

Open `.env` and fill in your three values:
```
TELEGRAM_BOT_TOKEN=7123456789:AAF...
TELEGRAM_USER_ID=123456789
ANTHROPIC_API_KEY=sk-ant-...
```

---

## Step 3 — Install dependencies

Make sure you have Python 3.10+ installed.

```bash
cd life_tracker
pip install -r requirements.txt
```

---

## Step 4 — Run the bot

```bash
python bot.py
```

You should see: `Bot is running. Press Ctrl+C to stop.`

Open Telegram, find your bot, and send `/start`.

---

## How to use it

Just message the bot naturally:

| What you say | What gets logged |
|---|---|
| `Ran 12km this morning` | 🏃 running_km: 12 |
| `Hit the gym, push day` | 💪 gym: push |
| `Cycled 35km on the highway` | 🚴 cycling_km: 35 |
| `Swam for 1.5 hours` | 🏊 swim_hours: 1.5 |
| `Spent ₹1200 on groceries` | 💸 finance: 1200, food |
| `Studied OS scheduling for 2 hours` | 🧠 learning: 2h, OS |
| `Used Instagram for 20 mins today` | 📱 instagram: 20 min |

### Commands

| Command | What it does |
|---|---|
| `/start` | Introduction |
| `/status` | See today's logged entries |
| `/week` | Raw stats for this week |
| `/report` | Full AI weekly performance report |
| `/nudge` | Quick daily check-in |

---

## Running it persistently (optional)

To keep the bot running 24/7 even when your terminal is closed, run it with `nohup`:

```bash
nohup python bot.py > bot.log 2>&1 &
```

Or use `screen`:

```bash
screen -S lifebot
python bot.py
# Ctrl+A then D to detach
```

---

## Updating your goals

Edit `goals.json` directly — it's plain JSON. Changes take effect immediately on the next `/report`.

---

## Data

All your logs are stored in `data.json` in this folder. It's plain JSON — you can read, back up, or export it anytime.
