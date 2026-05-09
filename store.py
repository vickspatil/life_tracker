import json
import os
import uuid
from datetime import datetime, date, timedelta

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
GOALS_FILE = os.path.join(BASE_DIR, "goals.json")


def _data_file(user_id: str) -> str:
    return os.path.join(BASE_DIR, f"data_{user_id}.json")


def _load(user_id: str) -> dict:
    path = _data_file(user_id)
    if not os.path.exists(path):
        return {"logs": []}
    with open(path, "r") as f:
        return json.load(f)


def _save(data: dict, user_id: str):
    with open(_data_file(user_id), "w") as f:
        json.dump(data, f, indent=2, default=str)


def _load_goals() -> dict:
    with open(GOALS_FILE, "r") as f:
        return json.load(f)


# ──────────────────────────────────────────────
# Basic CRUD
# ──────────────────────────────────────────────

def delete_entry_by_id(entry_id: str, user_id: str) -> bool:
    """Delete a log entry by its UUID. Returns True if found and deleted."""
    data = _load(user_id)
    original_len = len(data["logs"])
    data["logs"] = [log for log in data["logs"] if log["id"] != entry_id]
    if len(data["logs"]) < original_len:
        _save(data, user_id)
        return True
    return False


def log_activity(raw_text: str, parsed: dict, user_id: str) -> dict:
    """Store a new activity log entry."""
    data = _load(user_id)
    entry = {
        "id": str(uuid.uuid4()),
        "timestamp": datetime.now().isoformat(),
        "date": date.today().isoformat(),
        "raw": raw_text,
        "parsed": parsed
    }
    data["logs"].append(entry)
    _save(data, user_id)
    return entry


def get_logs_for_period(start_date: date, end_date: date, user_id: str) -> list:
    data = _load(user_id)
    return [
        log for log in data["logs"]
        if start_date.isoformat() <= log["date"] <= end_date.isoformat()
    ]


def get_todays_logs(user_id: str) -> list:
    today = date.today()
    return get_logs_for_period(today, today, user_id)


def get_this_weeks_logs(user_id: str) -> list:
    today = date.today()
    start = today - timedelta(days=today.weekday())
    return get_logs_for_period(start, today, user_id)


def get_this_months_logs(user_id: str) -> list:
    today = date.today()
    return get_logs_for_period(today.replace(day=1), today, user_id)


def get_last_n_days_logs(n: int, user_id: str) -> list:
    today = date.today()
    return get_logs_for_period(today - timedelta(days=n - 1), today, user_id)


# ──────────────────────────────────────────────
# Aggregation
# ──────────────────────────────────────────────

def aggregate_stats(logs: list) -> dict:
    """Aggregate parsed log entries into summary stats."""
    stats = {
        "running_km": 0.0,
        "cycling_km": 0.0,
        "swim_hours": 0.0,
        "gym_sessions": [],
        "instagram_readings": [],
        "instagram_days_over_limit": 0,
        "total_spent_inr": 0.0,
        "spend_by_category": {},
        "learning_hours": 0.0,
        "learning_topics": [],
        "days_logged": set(),
        "days_with_gym": set(),
        "days_with_run": set(),
        "days_with_cycle": set(),
        "days_with_swim": set(),
        "days_with_learning": set(),
    }

    for log in logs:
        d = log["date"]
        stats["days_logged"].add(d)
        p = log.get("parsed", {})

        f = p.get("fitness", {}) or {}
        if f.get("running_km"):
            stats["running_km"] += f["running_km"]
            stats["days_with_run"].add(d)
        if f.get("cycling_km"):
            stats["cycling_km"] += f["cycling_km"]
            stats["days_with_cycle"].add(d)
        if f.get("swim_hours"):
            stats["swim_hours"] += f["swim_hours"]
            stats["days_with_swim"].add(d)
        if f.get("gym_session"):
            stats["gym_sessions"].append(f["gym_session"])
            stats["days_with_gym"].add(d)

        m = p.get("mental", {}) or {}
        if m.get("instagram_mins") is not None:
            stats["instagram_readings"].append({"date": d, "mins": m["instagram_mins"]})
            if m["instagram_mins"] > 30:
                stats["instagram_days_over_limit"] += 1

        fin = p.get("finance", {}) or {}
        if fin.get("spent"):
            stats["total_spent_inr"] += fin["spent"]
            cat = fin.get("category") or "other"
            stats["spend_by_category"][cat] = stats["spend_by_category"].get(cat, 0) + fin["spent"]

        eng = p.get("engineering", {}) or {}
        if eng.get("learning_hours"):
            stats["learning_hours"] += eng["learning_hours"]
            stats["days_with_learning"].add(d)
        if eng.get("topics"):
            stats["learning_topics"].extend(eng["topics"])

    stats["days_logged"] = len(stats["days_logged"])
    stats["days_with_gym"] = len(stats["days_with_gym"])
    stats["days_with_run"] = len(stats["days_with_run"])
    stats["days_with_cycle"] = len(stats["days_with_cycle"])
    stats["days_with_swim"] = len(stats["days_with_swim"])
    stats["days_with_learning"] = len(stats["days_with_learning"])
    stats["unique_gym_sessions"] = list(set(stats["gym_sessions"]))

    return stats


# ──────────────────────────────────────────────
# Trend Engine
# ──────────────────────────────────────────────

def get_week_summary(weeks_ago: int = 0, user_id: str = "") -> dict:
    """Aggregate stats for a past week. 0 = current week, 1 = last week, etc."""
    today = date.today()
    current_monday = today - timedelta(days=today.weekday())
    target_monday = current_monday - timedelta(weeks=weeks_ago)
    target_sunday = target_monday + timedelta(days=6)
    end = min(target_sunday, today)

    logs = get_logs_for_period(target_monday, end, user_id)
    stats = aggregate_stats(logs)

    # For past weeks, days_elapsed = 7. For current week, it's how many days in.
    if weeks_ago == 0:
        days_elapsed = today.weekday() + 1  # Mon=1 ... Sun=7
    else:
        days_elapsed = 7

    return {
        "week_start": target_monday.isoformat(),
        "weeks_ago": weeks_ago,
        "days_elapsed": days_elapsed,
        "stats": stats
    }


def get_n_week_trend(n: int = 4, user_id: str = "") -> list:
    """Return list of weekly summaries, oldest first."""
    return [get_week_summary(weeks_ago=i, user_id=user_id) for i in range(n - 1, -1, -1)]


def get_streak_data(user_id: str) -> dict:
    """
    For each key activity, count how many consecutive days (going back from today)
    it was done (or violated, in the case of instagram).
    Returns both current streak and a flag for whether it's a good or bad streak.
    """
    today = date.today()
    data = _load(user_id)

    # Index logs by date
    by_date: dict[str, list] = {}
    for log in data["logs"]:
        d = log["date"]
        if d not in by_date:
            by_date[d] = []
        by_date[d].append(log.get("parsed", {}))

    def day_has(d_str: str, check_fn) -> bool:
        if d_str not in by_date:
            return False
        return any(check_fn(p) for p in by_date[d_str])

    def count_streak(check_fn, start_offset=0) -> int:
        streak = 0
        for i in range(start_offset, 30):  # look back up to 30 days
            d_str = (today - timedelta(days=i)).isoformat()
            if day_has(d_str, check_fn):
                streak += 1
            else:
                break
        return streak

    def count_miss_streak(check_fn) -> int:
        """Count consecutive days WITHOUT this activity."""
        streak = 0
        for i in range(0, 30):
            d_str = (today - timedelta(days=i)).isoformat()
            if not day_has(d_str, check_fn):
                streak += 1
            else:
                break
        return streak

    checks = {
        "gym":      lambda p: bool((p.get("fitness") or {}).get("gym_session")),
        "running":  lambda p: bool((p.get("fitness") or {}).get("running_km")),
        "cycling":  lambda p: bool((p.get("fitness") or {}).get("cycling_km")),
        "swimming": lambda p: bool((p.get("fitness") or {}).get("swim_hours")),
        "learning": lambda p: bool((p.get("engineering") or {}).get("learning_hours")),
        "instagram_over": lambda p: (
            (p.get("mental") or {}).get("instagram_mins") is not None and
            (p.get("mental") or {}).get("instagram_mins", 0) > 30
        ),
    }

    streaks = {}
    for name, fn in checks.items():
        active_streak = count_streak(fn)
        miss_streak = count_miss_streak(fn)
        streaks[name] = {
            "active_streak": active_streak,   # consecutive days WITH activity
            "miss_streak": miss_streak,        # consecutive days WITHOUT activity
        }

    return streaks


# ──────────────────────────────────────────────
# Pace Projection
# ──────────────────────────────────────────────

def get_pace_projection(user_id: str) -> dict:
    """
    Given current week's progress and what day it is,
    project whether each metric is on track and what's needed.
    """
    today = date.today()
    days_elapsed = today.weekday() + 1   # Mon=1 ... Sun=7
    days_remaining = 7 - days_elapsed

    weekly_logs = get_this_weeks_logs(user_id)
    monthly_logs = get_this_months_logs(user_id)
    stats = aggregate_stats(weekly_logs)
    monthly_stats = aggregate_stats(monthly_logs)

    goals = _load_goals()
    f_goals = goals["fitness"]
    e_goals = goals["engineering"]
    m_goals = goals["mental"]
    fin_goals = goals["finance"]

    def projection(done: float, target: float) -> dict:
        needed = max(0.0, target - done)
        expected_by_now = target * (days_elapsed / 7)
        deficit = expected_by_now - done
        on_path = done >= expected_by_now
        # If days_remaining > 0, daily_needed tells you the pace required
        daily_needed = round(needed / days_remaining, 1) if days_remaining > 0 else needed
        return {
            "done": round(done, 1),
            "target": target,
            "needed_to_finish_week": round(needed, 1),
            "expected_by_today": round(expected_by_now, 1),
            "deficit_vs_expected": round(deficit, 1),
            "on_path": on_path,
            "daily_needed_to_recover": daily_needed,
        }

    # Gym: target is N sessions by end of week
    gym_done = stats["days_with_gym"]
    gym_target = f_goals["gym_days_per_week"]
    gym_sessions_hit = stats["unique_gym_sessions"]
    gym_sessions_missing = [s for s in f_goals["gym_sessions_required"] if s not in gym_sessions_hit]

    # Learning: daily target, so weekly = target * 7
    learning_weekly_target = e_goals["learning_hours_per_day"] * 7
    learning_done = stats["learning_hours"]

    # Instagram: count days over limit
    instagram_days_over = stats["instagram_days_over_limit"]

    # Finance: monthly
    monthly_spent = monthly_stats["total_spent_inr"]
    monthly_target = fin_goals["monthly_budget_inr"]
    today_obj = date.today()
    days_in_month = (today_obj.replace(month=today_obj.month % 12 + 1, day=1) - timedelta(days=1)).day
    daily_budget = monthly_target / days_in_month
    expected_spend_by_now = daily_budget * today_obj.day
    spend_deficit = monthly_spent - expected_spend_by_now  # positive = over budget

    return {
        "day_of_week": today.strftime("%A"),
        "days_elapsed": days_elapsed,
        "days_remaining": days_remaining,
        "running":  projection(stats["running_km"],  f_goals["running_km_per_week"]),
        "cycling":  projection(stats["cycling_km"],  f_goals["cycling_km_per_week"]),
        "swimming": projection(stats["swim_hours"],  f_goals["swim_hours_per_week"]),
        "gym": {
            "sessions_done": gym_done,
            "target": gym_target,
            "sessions_hit": gym_sessions_hit,
            "sessions_missing": gym_sessions_missing,
            "on_path": gym_done >= round(gym_target * days_elapsed / 7),
        },
        "learning": projection(learning_done, learning_weekly_target),
        "instagram": {
            "days_over_limit_this_week": instagram_days_over,
            "limit_per_day_mins": m_goals["instagram_max_mins_per_day"],
        },
        "finance": {
            "monthly_spent": round(monthly_spent, 0),
            "monthly_budget": monthly_target,
            "expected_spend_by_today": round(expected_spend_by_now, 0),
            "over_budget_by": round(spend_deficit, 0),
            "on_path": monthly_spent <= expected_spend_by_now,
            "remaining_budget": round(monthly_target - monthly_spent, 0),
        }
    }
