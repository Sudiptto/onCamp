"""Saved events table, the duplicate-event rule and the college/start index on events

Revision ID: 0002_saved_events_dup_rule
Revises: 0001_baseline
Create Date: 2026-11-22

The shared database was built by db.create_all(), so it may already have some of this:
create_all() adds a new table like saved_events, but never adds an index to a table that
already exists (events). Each step below checks first and skips what is already there.

Before adding the unique index, this looks for events that would break it. If it finds
any, it stops and lists them. It never deletes anything; merge them with
`python dedupe_events.py --apply` (or by hand) and run the upgrade again.
"""
from alembic import op
import sqlalchemy as sa


revision = "0002_saved_events_dup_rule"
down_revision = "0001_baseline"
branch_labels = None
depends_on = None

DUPLICATE_INDEX = "uq_events_club_title_day"
COLLEGE_START_INDEX = "ix_events_college_start"
SAVED_EVENT_INDEX = "ix_saved_events_event_id"

# Shown in the error so it stays readable if there are many.
MAX_LISTED_DUPLICATES = 20


def index_exists(bind, name):
    # Looked up by name in the catalog, because SQLAlchemy can't reflect expression
    # indexes on SQLite, so inspect().get_indexes() would miss uq_events_club_title_day.
    if bind.dialect.name == "postgresql":
        query = sa.text(
            "SELECT 1 FROM pg_indexes WHERE schemaname = current_schema() AND indexname = :name"
        )
    elif bind.dialect.name == "sqlite":
        query = sa.text("SELECT 1 FROM sqlite_master WHERE type = 'index' AND name = :name")
    else:
        return any(
            index["name"] == name
            for table in sa.inspect(bind).get_table_names()
            for index in sa.inspect(bind).get_indexes(table)
        )
    return bind.execute(query, {"name": name}).first() is not None


def find_duplicate_events(bind):
    # The same groups uq_events_club_title_day would refuse. Rows without a start_time are
    # left out, since NULL dates never clash in a unique index.
    rows = bind.execute(
        sa.text(
            """
            SELECT club_id, lower(title) AS title, date(start_time) AS day,
                   COUNT(*) AS copies, MIN(id) AS first_id, MAX(id) AS last_id
            FROM events
            WHERE start_time IS NOT NULL
            GROUP BY club_id, lower(title), date(start_time)
            HAVING COUNT(*) > 1
            ORDER BY club_id, day, title
            """
        )
    ).fetchall()
    return rows


def duplicate_error(rows):
    lines = [
        f"  club_id={row.club_id}  day={row.day}  title={row.title!r}  "
        f"copies={row.copies}  ids {row.first_id}..{row.last_id}"
        for row in rows[:MAX_LISTED_DUPLICATES]
    ]
    if len(rows) > MAX_LISTED_DUPLICATES:
        lines.append(f"  ...and {len(rows) - MAX_LISTED_DUPLICATES} more")
    return RuntimeError(
        f"Can't add {DUPLICATE_INDEX}: {len(rows)} group(s) of duplicate events already exist.\n"
        + "\n".join(lines)
        + "\nNothing was deleted. Merge them with `python dedupe_events.py --apply` "
        "(or remove the extra copies by hand), then run `flask --app run db upgrade` again."
    )


def upgrade():
    bind = op.get_bind()

    # Check first, so a failed upgrade leaves the database exactly as it was
    # (SQLite doesn't roll back table creation the way Postgres does).
    duplicates = find_duplicate_events(bind)
    if duplicates and not index_exists(bind, DUPLICATE_INDEX):
        raise duplicate_error(duplicates)

    if not sa.inspect(bind).has_table("saved_events"):
        op.create_table(
            "saved_events",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "user_id",
                sa.Integer(),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "event_id",
                sa.Integer(),
                sa.ForeignKey("events.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.UniqueConstraint("user_id", "event_id", name="uq_saved_events_user_event"),
        )
    if not index_exists(bind, SAVED_EVENT_INDEX):
        op.create_index(SAVED_EVENT_INDEX, "saved_events", ["event_id"])

    # Same club + same title (any capitalization) + same day = one event.
    # Alembic's autogenerate can't see expression indexes, so this one is written by hand.
    if not index_exists(bind, DUPLICATE_INDEX):
        op.create_index(
            DUPLICATE_INDEX,
            "events",
            ["club_id", sa.text("lower(title)"), sa.text("date(start_time)")],
            unique=True,
        )
    if not index_exists(bind, COLLEGE_START_INDEX):
        op.create_index(COLLEGE_START_INDEX, "events", ["college_id", "start_time"])


def downgrade():
    op.drop_index(COLLEGE_START_INDEX, table_name="events")
    op.drop_index(DUPLICATE_INDEX, table_name="events")
    op.drop_index(SAVED_EVENT_INDEX, table_name="saved_events")
    op.drop_table("saved_events")
