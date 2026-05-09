import os
import logging
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
import random
from datetime import time, timezone, timedelta
from parser import parse_activity, classify_message
from query import answer_query
from store import log_activity, get_todays_logs, get_this_weeks_logs, aggregate_stats, delete_entry_by_id
from report import generate_weekly_report, generate_daily_nudge, generate_trend_summary
from prefs import get_prefs, add_topic, remove_topic, toggle_daily, get_all_subscribed
from content import generate_article

# 8:00 AM IST = UTC+5:30
IST = timezone(timedelta(hours=5, minutes=30))
DAILY_SEND_TIME = time(hour=8, minute=0, tzinfo=IST)

load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
_raw_ids = os.getenv("TELEGRAM_USER_IDS", os.getenv("TELEGRAM_USER_ID", ""))
ALLOWED_USER_IDS = {uid.strip() for uid in _raw_ids.split(",") if uid.strip()}

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

def is_authorised(update: Update) -> bool:
    if not ALLOWED_USER_IDS:
        return True  # No restriction set — open to anyone (not recommended)
    return str(update.effective_user.id) in ALLOWED_USER_IDS


def get_user_id(update: Update) -> str:
    return str(update.effective_user.id)


def build_ack(parsed: dict) -> str:
    """Build a quick acknowledgment message after logging an activity."""
    lines = ["✅ *Logged!*"]

    f = parsed.get("fitness") or {}
    if f.get("running_km"):
        lines.append(f"🏃 Run: *{f['running_km']}km*")
    if f.get("cycling_km"):
        lines.append(f"🚴 Cycle: *{f['cycling_km']}km*")
    if f.get("swim_hours"):
        lines.append(f"🏊 Swim: *{f['swim_hours']}h*")
    if f.get("gym_session"):
        lines.append(f"💪 Gym: *{f['gym_session'].capitalize()}* day")

    m = parsed.get("mental") or {}
    if m.get("instagram_mins") is not None:
        flag = " ⚠️ over limit!" if m["instagram_mins"] > 30 else ""
        lines.append(f"📱 Instagram: *{m['instagram_mins']} min*{flag}")
    if m.get("meditation"):
        lines.append("🧘 Meditation: done")
    if m.get("mood"):
        lines.append(f"😶 Mood: *{m['mood']}*")

    fin = parsed.get("finance") or {}
    if fin.get("spent"):
        lines.append(f"💸 Spent: *₹{fin['spent']}* ({fin.get('category', 'other')})")

    eng = parsed.get("engineering") or {}
    if eng.get("learning_hours"):
        topics = ", ".join(eng.get("topics") or []) or "general"
        lines.append(f"🧠 Learning: *{eng['learning_hours']}h* — {topics}")

    if len(lines) == 1:
        lines.append("_Hmm, I didn't catch any specific activity. Try being more specific — e.g. 'ran 5km' or 'spent ₹500 on food'._")

    return "\n".join(lines)


def build_weekly_summary_text(stats: dict) -> str:
    """Quick stats snapshot — not the full AI report."""
    return (
        f"📊 *This week so far:*\n"
        f"🏃 Run: {stats['running_km']:.1f}km\n"
        f"🚴 Cycle: {stats['cycling_km']:.1f}km\n"
        f"🏊 Swim: {stats['swim_hours']:.1f}h\n"
        f"💪 Gym: {stats['days_with_gym']} sessions ({', '.join(stats['unique_gym_sessions']) or 'none'})\n"
        f"📱 Instagram over-limit days: {stats['instagram_days_over_limit']}\n"
        f"💸 Spent this week: ₹{stats['total_spent_inr']:.0f}\n"
        f"🧠 Learning: {stats['learning_hours']:.1f}h over {stats['days_with_learning']} days\n"
        f"📅 Days logged: {stats['days_logged']}"
    )


# ──────────────────────────────────────────────
# Handlers
# ──────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorised(update):
        await update.message.reply_text("This bot is private.")
        return

    await update.message.reply_text(
        "Hey Vickey! 👋 I'm your personal life tracker.\n\n"
        "*Logging* — just tell me what you did:\n"
        "• _Ran 8km this morning_\n"
        "• _Hit the gym, push day_\n"
        "• _Spent ₹800 on groceries_\n"
        "• _Studied OS and memory management for 90 mins_\n"
        "• _Used Instagram for 45 mins today_\n\n"
        "*Questions* — ask anything about your data:\n"
        "• _How much have I spent in the last 10 days?_\n"
        "• _How many km did I run this week?_\n"
        "• _What's my Instagram usage this month?_\n"
        "• _How many gym sessions did I do last week?_\n\n"
        "*Commands:*\n"
        "/status — today's log\n"
        "/week — this week's raw stats\n"
        "/nudge — daily pace check-in\n"
        "/trend — 4-week trajectory per metric\n"
        "/report — full weekly report (path-centric, brutally honest)\n"
        "/delete — remove an entry from today's log\n\n"
        "*Knowledge:*\n"
        "/settopic <field> — add a topic (e.g. distributed systems)\n"
        "/mytopics — see your topics and daily delivery status\n"
        "/removetopic <topic> — remove a topic\n"
        "/toggledaily — turn daily 8 AM articles on/off\n"
        "/article — get an article now (or /article <topic> for a one-off)",
        parse_mode="Markdown"
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorised(update):
        return
    await update.message.reply_text(
        "*📋 Everything you can do:*\n"
        "\n"
        "*— Logging —*\n"
        "Just type naturally — no command needed:\n"
        "_Ran 8km · Hit the gym, push day · Spent ₹800 on food_\n"
        "_Cycled 35km · Studied OS for 90 mins · Used Instagram 45 mins_\n"
        "\n"
        "*— Tracking —*\n"
        "/status — today's entries\n"
        "/week — this week's raw stats\n"
        "/nudge — are you on pace today?\n"
        "/trend — 4-week trajectory per metric\n"
        "/report — full weekly report (brutally honest)\n"
        "/delete — remove an entry from today's log\n"
        "\n"
        "*— Knowledge Articles —*\n"
        "/settopic <field> — add a topic to your list\n"
        "    e.g. /settopic distributed systems\n"
        "/mytopics — see your topics + daily delivery status\n"
        "/removetopic <topic> — remove a topic\n"
        "/toggledaily — turn daily 8 AM articles on/off\n"
        "/article — get an article now (random from your topics)\n"
        "/article <topic> — one-off article on any topic\n"
        "\n"
        "*— Other —*\n"
        "/help — this message\n"
        "/cancel — cancel any pending action (e.g. a delete)",
        parse_mode="Markdown"
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorised(update):
        await update.message.reply_text("This bot is private.")
        return

    text = update.message.text.strip()
    if not text:
        return

    uid = get_user_id(update)

    # ── Delete flow: waiting for user to pick a number ──
    if context.user_data.get("awaiting_delete"):
        pending = context.user_data.get("delete_candidates", [])
        if text.isdigit():
            idx = int(text) - 1
            if 0 <= idx < len(pending):
                entry = pending[idx]
                success = delete_entry_by_id(entry["id"], uid)
                context.user_data.pop("awaiting_delete", None)
                context.user_data.pop("delete_candidates", None)
                if success:
                    await update.message.reply_text(
                        f"🗑️ Deleted: {entry['raw']}"
                    )
                else:
                    await update.message.reply_text("⚠️ Could not find that entry — it may have already been deleted.")
                return
            else:
                await update.message.reply_text(
                    f"⚠️ Please reply with a number between 1 and {len(pending)}, or /cancel."
                )
                return
        elif text.lower() in ("/cancel", "cancel"):
            context.user_data.pop("awaiting_delete", None)
            context.user_data.pop("delete_candidates", None)
            await update.message.reply_text("Cancelled.")
            return
        else:
            await update.message.reply_text(
                f"Reply with a number (1–{len(pending)}) to delete, or /cancel."
            )
            return

    # ── Classify: is this a question or a log entry? ──
    intent = classify_message(text)

    if intent == "query":
        processing_msg = await update.message.reply_text("_Looking up your data..._", parse_mode="Markdown")
        try:
            answer = answer_query(text, uid)
            await processing_msg.edit_text(answer, parse_mode="Markdown")
        except Exception as e:
            logger.error(f"Query error: {e}")
            await processing_msg.edit_text(f"⚠️ Couldn't answer that: {str(e)}")
        return

    processing_msg = await update.message.reply_text("_Logging..._", parse_mode="Markdown")

    try:
        parsed = parse_activity(text)
        log_activity(text, parsed, uid)
        ack = build_ack(parsed)
        await processing_msg.edit_text(ack, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error processing message: {e}")
        await processing_msg.edit_text(f"⚠️ Something went wrong: {str(e)}")


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorised(update):
        return

    uid = get_user_id(update)
    logs = get_todays_logs(uid)
    if not logs:
        await update.message.reply_text(
            "Nothing logged today yet. What are you waiting for?",
            parse_mode="Markdown"
        )
        return

    lines = ["*Today's entries:*"]
    for log in logs:
        lines.append(f"• {log['raw']}")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def week_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorised(update):
        return

    uid = get_user_id(update)
    msg = await update.message.reply_text("_Crunching your week..._", parse_mode="Markdown")
    try:
        logs = get_this_weeks_logs(uid)
        if not logs:
            await msg.edit_text("No data logged this week. That's the problem right there.")
            return
        stats = aggregate_stats(logs)
        await msg.edit_text(build_weekly_summary_text(stats), parse_mode="Markdown")
    except Exception as e:
        await msg.edit_text(f"⚠️ Error: {str(e)}")


async def report_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorised(update):
        return

    uid = get_user_id(update)
    msg = await update.message.reply_text("_Generating your weekly report... this might sting._", parse_mode="Markdown")
    try:
        report = generate_weekly_report(uid)
        await msg.edit_text(report, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Report error: {e}")
        await msg.edit_text(f"⚠️ Error generating report: {str(e)}")


async def nudge_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorised(update):
        return

    uid = get_user_id(update)
    msg = await update.message.reply_text("_Checking your day..._", parse_mode="Markdown")
    try:
        nudge = generate_daily_nudge(uid)
        await msg.edit_text(nudge, parse_mode="Markdown")
    except Exception as e:
        await msg.edit_text(f"⚠️ Error: {str(e)}")


async def delete_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorised(update):
        return

    uid = get_user_id(update)
    logs = get_todays_logs(uid)
    if not logs:
        await update.message.reply_text("Nothing logged today — nothing to delete.")
        return

    lines = ["Today's entries — reply with the number to delete:"]
    for i, log in enumerate(logs, 1):
        lines.append(f"{i}. {log['raw']}")
    lines.append("\nOr /cancel to abort.")

    context.user_data["awaiting_delete"] = True
    context.user_data["delete_candidates"] = logs

    await update.message.reply_text("\n".join(lines))


async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorised(update):
        return
    context.user_data.pop("awaiting_delete", None)
    context.user_data.pop("delete_candidates", None)
    await update.message.reply_text("Cancelled.")


async def trend_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorised(update):
        return

    uid = get_user_id(update)
    msg = await update.message.reply_text("_Analysing your 4-week trajectory..._", parse_mode="Markdown")
    try:
        trend = generate_trend_summary(uid)
        await msg.edit_text(trend, parse_mode="Markdown")
    except Exception as e:
        await msg.edit_text(f"⚠️ Error: {str(e)}")


# ──────────────────────────────────────────────
# Knowledge article handlers
# ──────────────────────────────────────────────

async def settopic_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorised(update):
        return
    uid = get_user_id(update)
    topic = " ".join(context.args).strip() if context.args else ""
    if not topic:
        await update.message.reply_text(
            "Usage: /settopic <field>\n\n"
            "Examples:\n"
            "  /settopic distributed systems\n"
            "  /settopic linux kernel internals\n"
            "  /settopic machine learning theory\n"
            "  /settopic computer networks\n\n"
            "You can add multiple topics — one per command. "
            "The daily article will pick one at random each day."
        )
        return
    topics = add_topic(uid, topic)
    prefs = get_prefs(uid)
    daily_status = "on" if prefs["daily_article"] else "off"
    await update.message.reply_text(
        f"Topic added: {topic}\n\n"
        f"Your topics: {', '.join(topics)}\n"
        f"Daily delivery: {daily_status} — use /toggledaily to change."
    )


async def mytopics_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorised(update):
        return
    uid = get_user_id(update)
    prefs = get_prefs(uid)
    topics = prefs.get("topics", [])
    daily = prefs.get("daily_article", False)
    if not topics:
        await update.message.reply_text(
            "No topics set yet. Use /settopic <field> to add one."
        )
        return
    daily_label = "on — article sent every day at 8 AM" if daily else "off — use /toggledaily to enable"
    lines = ["Your topics:"]
    for i, t in enumerate(topics, 1):
        lines.append(f"  {i}. {t}")
    lines.append(f"\nDaily delivery: {daily_label}")
    lines.append("\nUse /removetopic <topic> to remove one, or /article to get one now.")
    await update.message.reply_text("\n".join(lines))


async def removetopic_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorised(update):
        return
    uid = get_user_id(update)
    topic = " ".join(context.args).strip() if context.args else ""
    if not topic:
        await update.message.reply_text("Usage: /removetopic <topic>")
        return
    topics = remove_topic(uid, topic)
    if topics:
        await update.message.reply_text(f"Removed. Remaining topics: {', '.join(topics)}")
    else:
        await update.message.reply_text("Removed. No topics left — use /settopic to add one.")


async def toggledaily_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorised(update):
        return
    uid = get_user_id(update)
    prefs = get_prefs(uid)
    if not prefs.get("topics"):
        await update.message.reply_text(
            "You need at least one topic first. Use /settopic <field>."
        )
        return
    is_on = toggle_daily(uid)
    if is_on:
        await update.message.reply_text(
            "Daily articles: ON\n"
            "You'll get a knowledge article every morning at 8 AM.\n"
            "Use /article anytime to get one on demand."
        )
    else:
        await update.message.reply_text("Daily articles: OFF")


async def article_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorised(update):
        return
    uid = get_user_id(update)

    # Allow one-off topic: /article quantum computing
    one_off = " ".join(context.args).strip() if context.args else ""
    if one_off:
        topic = one_off
    else:
        prefs = get_prefs(uid)
        topics = prefs.get("topics", [])
        if not topics:
            await update.message.reply_text(
                "No topics set. Use /settopic <field> first, "
                "or do /article <topic> for a one-off."
            )
            return
        topic = random.choice(topics)

    msg = await update.message.reply_text(f"Generating article on: {topic}...")
    try:
        article = generate_article(topic)
        await msg.edit_text(article, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Article generation error: {e}")
        await msg.edit_text(f"Could not generate article: {str(e)}")


async def send_daily_articles(context: ContextTypes.DEFAULT_TYPE):
    """Job: runs every day at 8 AM IST, sends articles to all opted-in users."""
    subscribers = get_all_subscribed()
    logger.info(f"Daily article job: {len(subscribers)} subscriber(s)")
    for sub in subscribers:
        uid = sub["user_id"]
        topic = random.choice(sub["topics"])
        try:
            article = generate_article(topic)
            await context.bot.send_message(
                chat_id=uid,
                text=article,
                parse_mode="Markdown"
            )
            logger.info(f"Sent daily article to {uid} on topic: {topic}")
        except Exception as e:
            logger.error(f"Failed to send daily article to {uid}: {e}")


# ──────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────

def main():
    if not TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN is not set in .env")

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("week", week_command))
    app.add_handler(CommandHandler("report", report_command))
    app.add_handler(CommandHandler("nudge", nudge_command))
    app.add_handler(CommandHandler("trend", trend_command))
    app.add_handler(CommandHandler("delete", delete_command))
    app.add_handler(CommandHandler("cancel", cancel_command))
    app.add_handler(CommandHandler("settopic", settopic_command))
    app.add_handler(CommandHandler("mytopics", mytopics_command))
    app.add_handler(CommandHandler("removetopic", removetopic_command))
    app.add_handler(CommandHandler("toggledaily", toggledaily_command))
    app.add_handler(CommandHandler("article", article_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Daily article job — 8:00 AM IST
    app.job_queue.run_daily(send_daily_articles, time=DAILY_SEND_TIME)

    logger.info("Bot is running. Press Ctrl+C to stop.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
