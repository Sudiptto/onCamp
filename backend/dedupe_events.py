"""Merges duplicate upcoming events that were saved before the reminder check existed.

Same club + same day + same or close title = duplicate. The oldest row stays, and saves
on the copies move over to it.

It also adds the uq_events_club_title_day index if your database file is missing it,
since create_all() won't add an index to a table that already exists.

Usage (from backend):
    python dedupe_events.py            # just shows what it would do
    python dedupe_events.py --apply
"""

import argparse
from collections import defaultdict

from sqlalchemy.exc import OperationalError, ProgrammingError

from app import create_app
from app.extensions import db
from app.models import Event, SavedEvent
from app.services.event_dedupe import fill_missing_fields, titles_match


def find_duplicate_groups(events):
    # Each group is oldest first and has at least 2 events.
    by_day = defaultdict(list)
    for event in events:
        if event.start_time is not None:
            by_day[(event.club_id, event.start_time.date())].append(event)

    groups = []
    for day_events in by_day.values():
        day_events.sort(key=lambda event: event.id)
        placed = []
        for event in day_events:
            for group in placed:
                if titles_match(group[0].title, event.title):
                    group.append(event)
                    break
            else:
                placed.append([event])
        groups.extend(group for group in placed if len(group) > 1)
    return sorted(groups, key=lambda group: (group[0].start_time, group[0].id))


def merge_group(group):
    # Everything goes into group[0]. Returns how many rows were removed.
    keeper, copies = group[0], group[1:]
    for copy in copies:
        fill_missing_fields(
            keeper,
            location=copy.location,
            end_time=copy.end_time,
            google_form_url=copy.google_form_url,
            description=copy.description,
            is_free_food=copy.is_free_food,
        )
        already_saved = {
            user_id for (user_id,) in db.session.query(SavedEvent.user_id).filter_by(event_id=keeper.id)
        }
        for saved in list(copy.saves):
            if saved.user_id in already_saved:
                db.session.delete(saved)  # saved both copies, one is enough
            else:
                saved.event_id = keeper.id
                already_saved.add(saved.user_id)
        db.session.flush()
        # reload so deleting the copy doesn't cascade onto the saves we just moved
        db.session.expire(copy, ["saves"])
        db.session.delete(copy)
    return len(copies)


def ensure_unique_index():
    # SQLAlchemy can't read back an index built on lower(title), so we can't ask if it
    # exists. Just try to create it and treat "already exists" as a no.
    index = next(i for i in Event.__table__.indexes if i.name == "uq_events_club_title_day")
    try:
        index.create(bind=db.engine)
    except (OperationalError, ProgrammingError) as exc:
        if "already exists" in str(exc):
            return False
        raise
    return True


def main(argv=None):
    parser = argparse.ArgumentParser(description="Merge duplicate upcoming events.")
    parser.add_argument("--apply", action="store_true", help="actually make the changes")
    args = parser.parse_args(argv)

    app = create_app()
    with app.app_context():
        groups = find_duplicate_groups(Event.query.all())
        if not groups:
            print("No duplicate events found.")
        for group in groups:
            keeper = group[0]
            print(f"{keeper.start_time:%Y-%m-%d %H:%M}  club {keeper.club_id}  keep #{keeper.id} {keeper.title!r}")
            for copy in group[1:]:
                print(f"    remove #{copy.id} {copy.title!r}")

        if not args.apply:
            if groups:
                print(f"\n{sum(len(g) - 1 for g in groups)} duplicate row(s). Run with --apply to merge them.")
            return 0

        removed = sum(merge_group(group) for group in groups)
        db.session.commit()
        print(f"\nRemoved {removed} duplicate row(s).")
        if ensure_unique_index():
            print("Created the uq_events_club_title_day index.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
