import os
import json
from google import genai
from dotenv import load_dotenv
from store import (
    get_this_weeks_logs, get_this_months_logs, get_todays_logs,
    aggregate_stats, get_n_week_trend, get_streak_data, get_pace_projection
)

load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

GOALS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "goals.json")


def load_goals() -> dict:
    with open(GOALS_FILE, "r") as f:
        return json.load(f)


# ──────────────────────────────────────────────
# Weekly Report — path-centric, trend-first
# ──────────────────────────────────────────────

REPORT_PROMPT = """You are Vicked's personal performance coach. Brutally honest. You care about his long-term trajectory more than any single week's numbers.

His philosophy: "Where I am doesn't matter. Which path I'm on matters."
Your job: tell him whether he's on the right path or the wrong one — and be specific about why.

━━━ GOALS ━━━
🏃 Run: {running_target}km/week
🚴 Cycle: {cycling_target}km/week
🏊 Swim: {swim_target}h/week
💪 Gym: {gym_target} sessions/week (push + pull + legs + core — all 4 matter)
📱 Instagram: max {instagram_target} min/day
💸 Spending: max ₹{monthly_budget}/month
🧠 CS Learning: {learning_target}h/day

━━━ MULTI-WEEK TREND (oldest → newest) ━━━
{trend_data}

━━━ THIS WEEK'S PACE PROJECTION ━━━
{pace_data}

━━━ STREAKS ━━━
{streak_data}

━━━ THIS MONTH'S FINANCES ━━━
{monthly_finance}

Write the report in exactly these 4 sections. Use this format:

**🔴 Off-path**
[What's trending wrong — use the multi-week data to call out direction, not just current numbers. "You cycled 80km → 60km → 40km. That's a declining trend, not a bad week." Be specific.]

**🟢 On-path**
[What's trending right or holding steady. Brief. Numbers only.]

**⚡ Hard truth**
[One uncomfortable insight about his trajectory. Not what he did wrong this week — what pattern is emerging that he needs to face. Make it sting a little.]

**🎯 This week's single focus**
[One thing. The most important lever to pull. Be concrete — not "do more cycling" but "you need 15km/day for the next 4 days to hit 100km. Start tomorrow."]

Rules:
- Always reference the trend (multiple weeks), not just this week in isolation
- Use pace projections to show what's mathematically needed
- Call out miss streaks — "4 days without studying is a habit forming, not a gap"
- Under 300 words
- No filler. Every sentence must contain a number or a specific observation."""


def generate_weekly_report(user_id: str) -> str:
    goals = load_goals()

    # Trend: last 4 weeks
    trend = get_n_week_trend(4, user_id=user_id)
    trend_summary = []
    for w in trend:
        label = "This week" if w["weeks_ago"] == 0 else f"{w['weeks_ago']}w ago"
        s = w["stats"]
        trend_summary.append(
            f"{label} (day {w['days_elapsed']}/7): "
            f"Run {s['running_km']:.0f}km | "
            f"Cycle {s['cycling_km']:.0f}km | "
            f"Swim {s['swim_hours']:.1f}h | "
            f"Gym {s['days_with_gym']}x ({','.join(s['unique_gym_sessions']) or 'none'}) | "
            f"Learn {s['learning_hours']:.1f}h | "
            f"Insta over-limit {s['instagram_days_over_limit']}d | "
            f"Spent ₹{s['total_spent_inr']:.0f}"
        )

    # Pace projection
    pace = get_pace_projection(user_id)

    # Streaks
    streaks = get_streak_data(user_id)
    streak_lines = []
    for activity, data in streaks.items():
        active = data["active_streak"]
        miss = data["miss_streak"]
        if active > 1:
            streak_lines.append(f"  {activity}: ✅ {active} days in a row")
        elif miss > 1:
            streak_lines.append(f"  {activity}: ❌ {miss} days without it")

    # Monthly finance
    monthly_logs = get_this_months_logs(user_id)
    monthly_stats = aggregate_stats(monthly_logs)
    fin = goals["finance"]
    monthly_finance = {
        "spent_so_far": monthly_stats["total_spent_inr"],
        "monthly_budget": fin["monthly_budget_inr"],
        "remaining": fin["monthly_budget_inr"] - monthly_stats["total_spent_inr"],
        "by_category": monthly_stats["spend_by_category"]
    }

    prompt = REPORT_PROMPT.format(
        running_target=goals["fitness"]["running_km_per_week"],
        cycling_target=goals["fitness"]["cycling_km_per_week"],
        swim_target=goals["fitness"]["swim_hours_per_week"],
        gym_target=goals["fitness"]["gym_days_per_week"],
        instagram_target=goals["mental"]["instagram_max_mins_per_day"],
        monthly_budget=goals["finance"]["monthly_budget_inr"],
        learning_target=goals["engineering"]["learning_hours_per_day"],
        trend_data="\n".join(trend_summary),
        pace_data=json.dumps(pace, indent=2),
        streak_data="\n".join(streak_lines) if streak_lines else "  No streaks yet.",
        monthly_finance=json.dumps(monthly_finance, indent=2)
    )

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt
    )
    return response.text.strip()


# ──────────────────────────────────────────────
# Daily Nudge — pace-aware, streak-aware
# ──────────────────────────────────────────────

NUDGE_PROMPT = """You are Vicked's no-nonsense daily coach. Today is {day_of_week}.

━━━ TODAY'S LOG ━━━
{today_stats}

━━━ THIS WEEK'S PACE ━━━
{pace_data}

━━━ STREAKS ━━━
{streak_lines}

Write a sharp 3-4 sentence check-in:
- Tell him if he's on pace for each major metric this week (use the numbers)
- Call out any growing miss streaks — these are dangerous
- End with one concrete action he should do TODAY to stay on path

Be direct. No encouragement unless genuinely earned. Use numbers."""


def generate_daily_nudge(user_id: str) -> str:
    goals = load_goals()
    today_logs = get_todays_logs(user_id)
    today_stats = aggregate_stats(today_logs)
    pace = get_pace_projection(user_id)
    streaks = get_streak_data(user_id)

    streak_lines = []
    for activity, data in streaks.items():
        miss = data["miss_streak"]
        active = data["active_streak"]
        if miss > 1:
            streak_lines.append(f"  ❌ {activity}: {miss} days without it")
        elif active > 1:
            streak_lines.append(f"  ✅ {activity}: {active} days in a row")

    prompt = NUDGE_PROMPT.format(
        day_of_week=pace["day_of_week"],
        today_stats=json.dumps(today_stats, indent=2),
        pace_data=json.dumps(pace, indent=2),
        streak_lines="\n".join(streak_lines) if streak_lines else "  No patterns yet.",
    )

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt
    )
    return response.text.strip()


# ──────────────────────────────────────────────
# Trend Summary — for /trend command
# ──────────────────────────────────────────────

TREND_PROMPT = """You are Vicked's performance analyst. Give him a clean multi-week trend breakdown.

━━━ 4-WEEK DATA ━━━
{trend_data}

━━━ GOALS ━━━
Run: {running_target}km/week | Cycle: {cycling_target}km/week | Swim: {swim_target}h/week
Gym: {gym_target}x/week | Learn: {learning_target}h/day | Instagram: <{instagram_target}min/day

For each metric, write one line with:
- The trend direction (↑ improving / ↓ declining / → flat)
- The last 4 week numbers
- One sharp sentence on what the trend means

Format:
🏃 Running: [numbers] [↑/↓/→] — [one sentence verdict]
🚴 Cycling: ...
🏊 Swimming: ...
💪 Gym: ...
🧠 Learning: ...
📱 Instagram: ...

End with 2 sentences: overall trajectory verdict — is Vicked building momentum or losing it?"""


def generate_trend_summary(user_id: str) -> str:
    goals = load_goals()
    trend = get_n_week_trend(4, user_id=user_id)

    trend_lines = []
    for w in trend:
        label = "This week" if w["weeks_ago"] == 0 else f"{w['weeks_ago']}w ago"
        s = w["stats"]
        trend_lines.append(
            f"{label} ({w['days_elapsed']}/7 days): "
            f"Run={s['running_km']:.0f}km, Cycle={s['cycling_km']:.0f}km, "
            f"Swim={s['swim_hours']:.1f}h, Gym={s['days_with_gym']}x, "
            f"Learn={s['learning_hours']:.1f}h, InstaOver={s['instagram_days_over_limit']}d"
        )

    prompt = TREND_PROMPT.format(
        trend_data="\n".join(trend_lines),
        running_target=goals["fitness"]["running_km_per_week"],
        cycling_target=goals["fitness"]["cycling_km_per_week"],
        swim_target=goals["fitness"]["swim_hours_per_week"],
        gym_target=goals["fitness"]["gym_days_per_week"],
        learning_target=goals["engineering"]["learning_hours_per_day"],
        instagram_target=goals["mental"]["instagram_max_mins_per_day"],
    )

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt
    )
    return response.text.strip()
