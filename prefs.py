import json
import os

PREFS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "prefs.json")


def _load() -> dict:
    if not os.path.exists(PREFS_FILE):
        return {}
    with open(PREFS_FILE, "r") as f:
        return json.load(f)


def _save(data: dict):
    with open(PREFS_FILE, "w") as f:
        json.dump(data, f, indent=2)


def get_prefs(user_id: str) -> dict:
    data = _load()
    return data.get(str(user_id), {"topics": [], "daily_article": False})


def add_topic(user_id: str, topic: str) -> list:
    """Add a topic for a user. Returns updated topics list."""
    data = _load()
    uid = str(user_id)
    if uid not in data:
        data[uid] = {"topics": [], "daily_article": False}
    topic = topic.strip().lower()
    if topic and topic not in data[uid]["topics"]:
        data[uid]["topics"].append(topic)
    _save(data)
    return data[uid]["topics"]


def remove_topic(user_id: str, topic: str) -> list:
    """Remove a topic. Returns updated topics list."""
    data = _load()
    uid = str(user_id)
    if uid not in data:
        return []
    topic = topic.strip().lower()
    data[uid]["topics"] = [t for t in data[uid]["topics"] if t != topic]
    _save(data)
    return data[uid]["topics"]


def toggle_daily(user_id: str) -> bool:
    """Toggle daily article delivery. Returns new state."""
    data = _load()
    uid = str(user_id)
    if uid not in data:
        data[uid] = {"topics": [], "daily_article": False}
    data[uid]["daily_article"] = not data[uid].get("daily_article", False)
    _save(data)
    return data[uid]["daily_article"]


def get_all_subscribed() -> list:
    """Return list of {user_id, topics} for users opted into daily articles."""
    data = _load()
    result = []
    for uid, prefs in data.items():
        if prefs.get("daily_article") and prefs.get("topics"):
            result.append({"user_id": uid, "topics": prefs["topics"]})
    return result
