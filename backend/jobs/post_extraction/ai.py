import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from openai import OpenAI

from jobs.ai.club_filter import REQUEST_TIMEOUT_SECONDS, get_model

PROMPT_PATH = Path(__file__).parent / "prompt.md"
CAMPUS_TIMEZONE = "America/New_York"

# Google Forms live on either of these hosts; the AI is not asked to find links.
_FORM_URL = re.compile(
    r"https?://(?:docs\.google\.com/forms/[^\s)\]>\"']+|forms\.gle/[^\s)\]>\"']+|forms\.google\.com/[^\s)\]>\"']+)",
    re.IGNORECASE,
)


class ExtractionError(RuntimeError):
    """The AI call failed or returned something unusable."""


def find_google_form_url(caption: str) -> str | None:
    match = _FORM_URL.search(caption or "")
    return match.group(0).rstrip(".,!?;:") if match else None


def _parse_time(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return datetime.fromisoformat(value.strip()).replace(tzinfo=None)
    except ValueError:
        return None


def _clean_text(value: Any, limit: int) -> str | None:
    return value.strip()[:limit] if isinstance(value, str) and value.strip() else None


def parse_extraction(content: str) -> dict[str, Any]:
    """Validate the AI's JSON and turn it into the fields we store."""
    try:
        data = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ExtractionError(f"AI did not return valid JSON: {exc}") from exc
    if not isinstance(data, dict) or not isinstance(data.get("is_event"), bool):
        raise ExtractionError("AI response must be an object with a boolean is_event")

    start_time = _parse_time(data.get("start_time"))
    end_time = _parse_time(data.get("end_time"))
    if start_time and end_time and end_time < start_time:
        end_time = None
    return {
        "is_event": data["is_event"],
        "title": _clean_text(data.get("title"), 255),
        "description": _clean_text(data.get("description"), 2000),
        "start_time": start_time,
        "end_time": end_time,
        "location": _clean_text(data.get("location"), 255),
        "has_free_food": data.get("has_free_food") is True,
    }


def extract_with_deepseek(
    caption: str, posted_at: datetime, club_name: str, college_name: str
) -> dict[str, Any]:
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        raise ExtractionError("Missing DEEPSEEK_API_KEY in the local .env file")

    client = OpenAI(
        api_key=api_key,
        base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
        timeout=REQUEST_TIMEOUT_SECONDS,
        max_retries=2,
    )
    model = get_model()
    options = {}
    if model not in {"deepseek-chat", "deepseek-reasoner"}:
        options["extra_body"] = {"thinking": {"type": "disabled"}}
    payload = {
        "club_name": club_name,
        "college_name": college_name,
        "posted_at": posted_at.isoformat(),
        "timezone": CAMPUS_TIMEZONE,
        "caption": caption,
    }
    try:
        response = client.chat.completions.create(
            model=model,
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": PROMPT_PATH.read_text(encoding="utf-8")},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
            **options,
        )
    except Exception as exc:
        raise ExtractionError(f"DeepSeek request failed: {exc}") from exc
    return parse_extraction(response.choices[0].message.content or "")
