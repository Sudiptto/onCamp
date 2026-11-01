from datetime import datetime, timezone
from typing import Any

from app.extensions import db
from app.models import Club, ClubPost, ClubPostCheckpoint, College
from jobs.post_extraction.ai import ExtractionError, extract_with_deepseek, find_google_form_url
from jobs.post_extraction.posts import extract_recent_posts


def _naive_utc(value: datetime | str) -> datetime:
    if isinstance(value, str):
        value = datetime.fromisoformat(value)
    if value.tzinfo is not None:
        value = value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


def select_new_posts(
    posts: list[dict[str, Any]],
    checkpoint_at: datetime | None,
    seen_ids: set[str],
) -> list[dict[str, Any]]:
    """Return only posts we have not processed yet, oldest first.

    A post is skipped if its id was already stored, or if it is not newer than the
    checkpoint (the newest post processed on a previous run).
    """
    new_posts = []
    for post in posts:
        if post["post_id"] in seen_ids:
            continue
        if checkpoint_at is not None and _naive_utc(post["taken_at"]) <= checkpoint_at:
            continue
        new_posts.append(post)
    return sorted(new_posts, key=lambda post: post["taken_at"])


def process_club_posts(
    club: Club,
    raw_medias: Any,
    count: int,
    extractor: Any = extract_with_deepseek,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Run AI extraction on a club's newest `count` posts that have not been checked yet.

    Posts are handled oldest first and the checkpoint moves forward after each success,
    so if the AI fails mid-run the failed post (and anything newer) is retried next time.
    """
    now = _naive_utc(now or datetime.now(timezone.utc))
    college = db.session.get(College, club.college_id)
    recent = extract_recent_posts(raw_medias, count)

    checkpoint = ClubPostCheckpoint.query.filter_by(club_id=club.id).first()
    seen_ids = {
        post_id
        for (post_id,) in db.session.query(ClubPost.post_id).filter(
            ClubPost.post_id.in_([post["post_id"] for post in recent])
        )
    }
    new_posts = select_new_posts(recent, checkpoint.last_post_at if checkpoint else None, seen_ids)

    saved: list[ClubPost] = []
    error = None
    for post in new_posts:
        posted_at = _naive_utc(post["taken_at"])
        try:
            details = extractor(post["caption"], posted_at, club.name, college.name)
        except ExtractionError as exc:
            error = f"{post['post_id']}: {exc}"
            break

        row = ClubPost(
            post_id=post["post_id"],
            club_id=club.id,
            college_id=club.college_id,
            post_code=post["post_code"],
            post_url=post["post_url"],
            posted_at=posted_at,
            caption=post["caption"],
            google_form_url=find_google_form_url(post["caption"]),
            extracted_at=now,
            **details,
        )
        db.session.add(row)
        if checkpoint is None:
            checkpoint = ClubPostCheckpoint(club_id=club.id)
            db.session.add(checkpoint)
        checkpoint.last_post_id = post["post_id"]
        checkpoint.last_post_at = posted_at
        checkpoint.checked_at = now
        db.session.commit()
        saved.append(row)

    return {
        "fetched": len(recent),
        "already_checked": len(recent) - len(new_posts),
        "processed": len(saved),
        "posts": saved,
        "error": error,
    }
