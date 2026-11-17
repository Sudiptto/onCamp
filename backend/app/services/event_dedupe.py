import re
import unicodedata
from difflib import SequenceMatcher

# Clubs post an event and then post a reminder, and the title comes back a little different.
SIMILARITY_CUTOFF = 0.9


def normalize_title(title):
    # lowercase, no accents or punctuation, single spaces
    text = unicodedata.normalize("NFKD", title or "")
    text = "".join(ch for ch in text if not unicodedata.combining(ch)).lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def titles_match(first, second):
    a, b = normalize_title(first), normalize_title(second)
    if not a or not b:
        return False
    if a == b:
        return True

    # "Part 1" and "Part 2" are close in spelling but they're different events
    if set(re.findall(r"\d+", a)) != set(re.findall(r"\d+", b)):
        return False

    # Only catches spelling and punctuation ("Mehndi" vs "Mehendi"). Titles that are really
    # worded differently ("Intro to Git" vs "Intro to Git Workshop") go to the AI check instead.
    return SequenceMatcher(None, a, b).ratio() >= SIMILARITY_CUTOFF


# Things a reminder might say that the first post left out (like the room).
_MERGEABLE = ("location", "end_time", "google_form_url", "description")


def fill_missing_fields(existing, **details):
    # Only fills blanks, never overwrites what we already have.
    changed = False
    for name in _MERGEABLE:
        value = details.get(name)
        if value and not getattr(existing, name):
            setattr(existing, name, value)
            changed = True
    if details.get("is_free_food") and not existing.is_free_food:
        existing.is_free_food = True
        changed = True
    return changed
