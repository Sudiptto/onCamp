import json
import logging
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from openai import OpenAI

from jobs.ai.club_filter import REQUEST_TIMEOUT_SECONDS, get_model

PROMPT_PATH = Path(__file__).parent / "prompt.md"
DUPLICATE_PROMPT_PATH = Path(__file__).parent / "duplicate_prompt.md"
CAMPUS_TIMEZONE = "America/New_York"
logger = logging.getLogger(__name__)

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


def _complete(prompt_path: Path, payload: dict[str, Any]) -> tuple[Any, str]:
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
    try:
        response = client.chat.completions.create(
            model=model,
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": prompt_path.read_text(encoding="utf-8")},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
            **options,
        )
    except Exception as exc:
        raise ExtractionError(f"DeepSeek request failed: {exc}") from exc
    usage = _usage(response, model)
    logger.info(
        "DeepSeek usage model=%s prompt_tokens=%s completion_tokens=%s total_tokens=%s",
        model, usage["prompt_tokens"], usage["completion_tokens"], usage["total_tokens"],
    )
    return response, model


def _usage(response: Any, model: str) -> dict[str, Any]:
    usage = getattr(response, "usage", None)
    return {
        "model": model,
        "prompt_tokens": getattr(usage, "prompt_tokens", None),
        "completion_tokens": getattr(usage, "completion_tokens", None),
        "total_tokens": getattr(usage, "total_tokens", None),
    }


def _ask_deepseek(prompt_path: Path, payload: dict[str, Any]) -> str:
    response, _model = _complete(prompt_path, payload)
    return response.choices[0].message.content or ""


def _event_payload(caption: str, posted_at: datetime, club_name: str, college_name: str) -> dict[str, Any]:
    return {
        "club_name": club_name,
        "college_name": college_name,
        "posted_at": posted_at.isoformat(),
        "timezone": CAMPUS_TIMEZONE,
        "caption": caption,
    }


def extract_with_deepseek(
    caption: str, posted_at: datetime, club_name: str, college_name: str
) -> dict[str, Any]:
    return parse_extraction(_ask_deepseek(PROMPT_PATH, _event_payload(caption, posted_at, club_name, college_name)))


def extract_with_deepseek_metered(
    caption: str, posted_at: datetime, club_name: str, college_name: str
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Same extraction as extract_with_deepseek, plus token counts for the local credit ledger."""
    response, model = _complete(PROMPT_PATH, _event_payload(caption, posted_at, club_name, college_name))
    return parse_extraction(response.choices[0].message.content or ""), _usage(response, model)


def _describe(event: Any) -> dict[str, Any]:
    # works for a dict (new post) or an Event row (existing event)
    get = event.get if isinstance(event, dict) else lambda name: getattr(event, name, None)
    return {
        "title": get("title"),
        "start_time": get("start_time").isoformat() if get("start_time") else None,
        "end_time": get("end_time").isoformat() if get("end_time") else None,
        "location": get("location"),
        "description": get("description"),
    }


def judge_same_event_with_deepseek(new_post: dict[str, Any], candidates: list[Any]) -> int | None:
    # Returns the id of the existing event this post repeats, or None if it's a different one.
    payload = {
        "new_post": {**_describe(new_post), "caption": (new_post.get("caption") or "")[:1500]},
        "existing_events": [{"id": event.id, **_describe(event)} for event in candidates],
    }
    content = _ask_deepseek(DUPLICATE_PROMPT_PATH, payload)
    try:
        data = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ExtractionError(f"AI did not return valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ExtractionError("AI duplicate answer must be a JSON object")
    chosen = data.get("duplicate_of")
    valid_ids = {event.id for event in candidates}
    # True counts as 1 in Python, and an id we never sent is made up. Both mean no.
    if isinstance(chosen, bool) or chosen not in valid_ids:
        return None
    return chosen
