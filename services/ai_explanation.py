"""Optional OpenAI explanations for existing deterministic recommendations."""

import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


DEFAULT_MODEL = "gpt-4o-mini"
DEFAULT_ENDPOINT = "https://api.openai.com/v1/chat/completions"


class AIExplanationError(RuntimeError):
    """Raised when an optional AI explanation cannot be generated."""


def _recommendation_context(recommendation):
    """Keep the model grounded in the recommendation's existing evidence only."""
    return json.dumps({
        "resource_name": recommendation.get("resource_name"),
        "recommendation_type": recommendation.get("type"),
        "priority": recommendation.get("priority"),
        "title": recommendation.get("title"),
        "action": recommendation.get("action"),
        "reason": recommendation.get("reason"),
        "evidence": recommendation.get("evidence", []),
        "related_module": recommendation.get("related_module"),
    }, ensure_ascii=True)


def explain_recommendation(recommendation, timeout=12):
    """Return a concise explanation, or a safe unavailable result.

    The API key is read only on the server. The model is explicitly instructed
    to explain the supplied recommendation and never calculate or invent data.
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return {"available": False, "message": "AI explanation unavailable: the optional AI service is not configured."}

    endpoint = os.getenv("OPENAI_API_URL", DEFAULT_ENDPOINT)
    model = os.getenv("OPENAI_MODEL", DEFAULT_MODEL)
    payload = {
        "model": model,
        "temperature": 0.1,
        "max_tokens": 350,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You explain an existing CRFOS recommendation for an administrator. "
                    "Do not make a new recommendation, recalculate metrics, invent facts, "
                    "or change the suggested action. Use only the supplied evidence. "
                    "Return exactly three concise labeled sections: AI Explanation, "
                    "Key Evidence, Suggested Action."
                ),
            },
            {
                "role": "user",
                "content": "Explain this existing recommendation using only this JSON evidence:\n" + _recommendation_context(recommendation),
            },
        ],
    }
    request = Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            body = json.loads(response.read().decode("utf-8"))
        content = body["choices"][0]["message"]["content"].strip()
        if not content:
            raise AIExplanationError("The AI response was empty.")
        return {"available": True, "content": content}
    except (HTTPError, URLError, TimeoutError, KeyError, IndexError, ValueError, AIExplanationError) as error:
        return {"available": False, "message": "AI explanation unavailable right now."}
