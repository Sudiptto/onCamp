from datetime import datetime, timedelta

ACTIVE_WINDOW_DAYS = 90
ACTIVE_CHECK_INTERVAL_DAYS = 1
INACTIVE_CHECK_INTERVAL_DAYS = 30


def classify_activity(last_post_at: datetime | None, now: datetime) -> dict:
    """Bucket a club by last post age; no post at all counts as inactive."""
    if last_post_at is None:
        days_since = None
        is_active = False
    else:
        days_since = (now - last_post_at).days
        is_active = days_since <= ACTIVE_WINDOW_DAYS

    interval = ACTIVE_CHECK_INTERVAL_DAYS if is_active else INACTIVE_CHECK_INTERVAL_DAYS
    return {
        "status": "active" if is_active else "inactive",
        "days_since_last_post": days_since,
        "check_interval_days": interval,
        "next_check_at": (now + timedelta(days=interval)).isoformat(),
    }
