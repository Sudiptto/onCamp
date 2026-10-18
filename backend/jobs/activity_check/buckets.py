from datetime import datetime, timedelta

ACTIVE_WINDOW_DAYS = 90
ARCHIVE_AFTER_DAYS = 730  # no post in 2 years: moves to archived_clubs
ACTIVE_CHECK_INTERVAL_DAYS = 2
INACTIVE_CHECK_INTERVAL_DAYS = 180  # roughly once a semester


def classify_activity(last_post_at: datetime | None, now: datetime) -> dict:
    """Bucket a club by last post age; no post at all counts as inactive (never archived on that alone)."""
    days_since = None if last_post_at is None else (now - last_post_at).days

    if days_since is not None and days_since > ARCHIVE_AFTER_DAYS:
        status = "archived"
    elif days_since is not None and days_since <= ACTIVE_WINDOW_DAYS:
        status = "active"
    else:
        status = "inactive"

    interval = ACTIVE_CHECK_INTERVAL_DAYS if status == "active" else INACTIVE_CHECK_INTERVAL_DAYS
    return {
        "status": status,
        "days_since_last_post": days_since,
        "check_interval_days": interval,
        "next_check_at": (now + timedelta(days=interval)).isoformat(),
    }
