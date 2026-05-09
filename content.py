import os
from google import genai
from dotenv import load_dotenv

load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

ARTICLE_PROMPT = """You are a brilliant teacher writing a short daily knowledge article for an engineer who wants to grow.

Topic: {topic}

Write a focused, insightful article of exactly 250-350 words. Structure it as:

*[Punchy title — make it specific, not generic]*

[2-3 sentences of context: why this matters, what problem it solves, or a surprising angle that hooks the reader immediately]

*The core idea*
[Explain the concept clearly. Use a concrete analogy or real-world example. Assume the reader is smart but hasn't studied this specific thing deeply.]

*How it actually works*
[One level deeper — the mechanism, the tradeoff, or the "aha" detail that most introductions skip. Keep it grounded: numbers, names, or a specific case if relevant.]

*Why you should care*
[One practical takeaway: how this shows up in real systems, interviews, or daily engineering work. Make it actionable.]

Rules:
- Telegram-safe: use only *bold* and _italic_ for formatting, no headers with #, no bullet points with -
- No fluff, no "In conclusion", no encouragement
- End with one sharp sentence the reader will remember
- Each article should feel like a different slice of the topic — not always the 101 explanation"""


def generate_article(topic: str) -> str:
    """Generate a knowledge article on the given topic using Gemini."""
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=ARTICLE_PROMPT.format(topic=topic)
    )
    return response.text.strip()
