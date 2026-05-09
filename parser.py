import os
import json
from google import genai
from dotenv import load_dotenv

load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

PARSE_PROMPT = """You are a life activity data extractor. Parse the user's natural language log entry and extract structured data.

Return ONLY a valid JSON object with this exact structure. Use null for any field not mentioned:

{
  "fitness": {
    "running_km": null,
    "cycling_km": null,
    "swim_hours": null,
    "gym_session": null
  },
  "mental": {
    "instagram_mins": null,
    "meditation": false,
    "mood": null
  },
  "finance": {
    "spent": null,
    "category": null
  },
  "engineering": {
    "learning_hours": null,
    "topics": []
  }
}

Extraction rules:
- Distances: always convert to km (e.g. "5 miles" = 8.05km)
- Time: always convert to hours as a decimal (30 min = 0.5, 90 min = 1.5)
- gym_session: must be exactly one of "push", "pull", "legs", "core" — or null if not a gym entry
- instagram_mins: extract minutes if user mentions instagram/reels/scrolling time
- mood: one of "great", "good", "neutral", "low" — only if explicitly stated or strongly implied
- meditation: true only if explicitly mentioned
- finance spent: INR number only, no symbols (interpret "1.5k" as 1500, "2K" as 2000)
- finance category: one of "food", "transport", "shopping", "entertainment", "health", "other"
- engineering topics: extract from ["OS", "GPU", "networking", "systems", "architecture", "databases", "compilers", "other"]
- If the user mentions multiple activities, extract all of them

Return ONLY the JSON object. No explanation, no markdown, no code fences."""


CLASSIFY_PROMPT = """You are a classifier for a personal life tracker bot.

Classify the user's message as either:
- "query" — the user is asking a question about their past data (e.g. "how much did I spend?", "how many km did I run?", "what's my instagram usage?")
- "log" — the user is logging an activity or event (e.g. "ran 8km", "spent ₹500 on food", "hit the gym")

Rules:
- Messages with question marks are almost always "query"
- Messages starting with "how", "what", "when", "did I", "show me", "tell me" are "query"
- Messages describing something the user just did are "log"
- When in doubt, return "log"

Return ONLY the single word: query OR log"""


def classify_message(text: str) -> str:
    """Returns 'query' or 'log'."""
    # Fast heuristics first (avoid an API call for obvious cases)
    lower = text.strip().lower()
    question_starters = ("how", "what", "when", "did i", "show me", "tell me", "am i", "have i", "is my", "was i")
    if text.strip().endswith("?") or any(lower.startswith(s) for s in question_starters):
        return "query"

    # Fall back to Gemini for ambiguous messages
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=f"{CLASSIFY_PROMPT}\n\nMessage: \"{text}\""
    )
    result = response.text.strip().lower()
    return "query" if "query" in result else "log"


def parse_activity(text: str) -> dict:
    """Parse a natural language activity log into structured data using Gemini 2.5 Flash."""
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=f"{PARSE_PROMPT}\n\nUser log entry: \"{text}\""
    )

    raw = response.text.strip()

    # Strip markdown code fences if model wraps output
    if raw.startswith("```"):
        lines = raw.split("\n")
        lines = [l for l in lines if not l.startswith("```")]
        raw = "\n".join(lines).strip()

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {
            "fitness": {"running_km": None, "cycling_km": None, "swim_hours": None, "gym_session": None},
            "mental": {"instagram_mins": None, "meditation": False, "mood": None},
            "finance": {"spent": None, "category": None},
            "engineering": {"learning_hours": None, "topics": []}
        }
