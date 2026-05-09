"""
query.py — Natural language query answering over the user's logged data.

Handles questions like:
  "How much have I spent in the last 10 days?"
  "How many km did I run this month?"
  "What's my average Instagram usage this week?"
  "How many gym sessions did I do last week?"
"""

import os
import json
from datetime import date, timedelta
from google import genai
from dotenv import load_dotenv
from store import get_last_n_days_logs, get_this_weeks_logs, get_this_months_logs, aggregate_stats, get_logs_for_period, _load

load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))


QUERY_SYSTEM_PROMPT = """You are Vicked's personal life analytics assistant. You have access to his structured activity logs and must answer his question accurately.

The user logs data across these categories:
- fitness: running_km, cycling_km, swim_hours, gym_session (push/pull/legs/core)
- mental: instagram_mins (limit is 30 min/day), meditation, mood
- finance: spent (INR), category (food/transport/shopping/entertainment/health/other)
- engineering: learning_hours, topics (OS/GPU/networking/systems/architecture/databases/compilers/other)

You will be given:
1. The user's question
2. A JSON dump of their raw log entries for the relevant period

Your job:
- Answer the question directly and specifically using the data provided
- Show exact numbers (totals, averages, breakdowns) where relevant
- If the question is about spending, show category breakdown if insightful
- If the question is about fitness, show per-day or total as appropriate
- Be concise but complete. Use bullet points only when listing multiple items
- Format numbers cleanly (e.g., ₹1,500, 8.5km, 2.5h)
- If data is sparse or missing for the period, say so clearly
- Do NOT lecture or moralize unless the user asks for a review
- Use Markdown formatting for Telegram (bold with *text*, not **text**)

Respond only with the answer — no preamble like "Based on your logs..."."""


def _fetch_logs_for_question(text: str, user_id: str) -> tuple[list, str]:
    """
    Heuristically determine the right time window for the question,
    fetch the logs, and return (logs, period_label).
    """
    lower = text.lower()
    today = date.today()

    # Explicit day counts: "last 10 days", "past 7 days", etc.
    import re
    day_match = re.search(r'(?:last|past)\s+(\d+)\s+days?', lower)
    week_match = re.search(r'(?:last|past)\s+(\d+)\s+weeks?', lower)
    month_match = re.search(r'(?:last|past)\s+(\d+)\s+months?', lower)

    if day_match:
        n = int(day_match.group(1))
        logs = get_last_n_days_logs(n, user_id)
        return logs, f"last {n} days"

    if week_match:
        n = int(week_match.group(1))
        start = today - timedelta(weeks=n)
        logs = get_logs_for_period(start, today, user_id)
        return logs, f"last {n} weeks"

    if month_match:
        n = int(month_match.group(1))
        start = today - timedelta(days=n * 30)
        logs = get_logs_for_period(start, today, user_id)
        return logs, f"last {n} months"

    # Keywords
    if any(w in lower for w in ["this week", "week so far"]):
        logs = get_this_weeks_logs(user_id)
        return logs, "this week"

    if any(w in lower for w in ["this month", "month so far"]):
        logs = get_this_months_logs(user_id)
        return logs, "this month"

    if "yesterday" in lower:
        yesterday = today - timedelta(days=1)
        logs = get_logs_for_period(yesterday, yesterday, user_id)
        return logs, "yesterday"

    if "today" in lower:
        logs = get_logs_for_period(today, today, user_id)
        return logs, "today"

    if any(w in lower for w in ["last week", "previous week"]):
        # Last Mon–Sun
        current_monday = today - timedelta(days=today.weekday())
        last_monday = current_monday - timedelta(weeks=1)
        last_sunday = current_monday - timedelta(days=1)
        logs = get_logs_for_period(last_monday, last_sunday, user_id)
        return logs, "last week"

    # Default: last 30 days (broad enough to answer most questions)
    logs = get_last_n_days_logs(30, user_id)
    return logs, "last 30 days"


def answer_query(question: str, user_id: str) -> str:
    """Answer a natural language question about the user's logged data."""
    logs, period_label = _fetch_logs_for_question(question, user_id)

    if not logs:
        return f"No data found for {period_label}. Start logging and I'll be able to answer this!"

    # Build a compact JSON summary for the AI
    # Include raw entries + basic aggregates
    stats = aggregate_stats(logs)

    # Make stats serializable
    serializable_stats = {k: v for k, v in stats.items()}

    context = {
        "period": period_label,
        "total_entries": len(logs),
        "aggregated_stats": serializable_stats,
        "daily_entries": _build_daily_summary(logs),
    }

    context_str = json.dumps(context, indent=2, default=str)

    prompt = f"""User question: "{question}"

Data ({period_label}):
{context_str}"""

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=f"{QUERY_SYSTEM_PROMPT}\n\n{prompt}"
    )

    return response.text.strip()


def _build_daily_summary(logs: list) -> dict:
    """Group logs by date for a clean daily view."""
    by_date = {}
    for log in logs:
        d = log["date"]
        if d not in by_date:
            by_date[d] = []
        p = log.get("parsed", {})
        entry = {}

        f = p.get("fitness") or {}
        if f.get("running_km"):
            entry["run_km"] = f["running_km"]
        if f.get("cycling_km"):
            entry["cycle_km"] = f["cycling_km"]
        if f.get("swim_hours"):
            entry["swim_h"] = f["swim_hours"]
        if f.get("gym_session"):
            entry["gym"] = f["gym_session"]

        m = p.get("mental") or {}
        if m.get("instagram_mins") is not None:
            entry["ig_mins"] = m["instagram_mins"]
        if m.get("mood"):
            entry["mood"] = m["mood"]

        fin = p.get("finance") or {}
        if fin.get("spent"):
            entry["spent"] = fin["spent"]
            entry["category"] = fin.get("category", "other")

        eng = p.get("engineering") or {}
        if eng.get("learning_hours"):
            entry["learning_h"] = eng["learning_hours"]
        if eng.get("topics"):
            entry["topics"] = eng["topics"]

        if entry:
            by_date[d].append(entry)

    return by_date
