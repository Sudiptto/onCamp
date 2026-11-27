"""Tests for the database migrations in backend/migrations.

They run on a temporary SQLite file by default. To also run them on Postgres (what Supabase
runs), point MIGRATION_TEST_DATABASE_URL at an EMPTY, throwaway Postgres database:

    MIGRATION_TEST_DATABASE_URL=postgresql://user:pass@localhost/oncamp_test pytest tests/test_migrations.py

Every test wipes that database's public schema, so never use the shared database for it.
"""

import os
import warnings
from datetime import datetime
from pathlib import Path

import pytest
import sqlalchemy as sa
from flask import current_app
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy.exc import IntegrityError

from app import create_app
from app.extensions import db
from app.models import Club, College, Event, SavedEvent

MIGRATIONS_DIR = str(Path(__file__).resolve().parents[1] / "migrations")
BASELINE = "0001_baseline"
DUPLICATE_INDEX = "uq_events_club_title_day"
NEW_INDEXES = {DUPLICATE_INDEX, "ix_events_college_start", "ix_saved_events_event_id"}

DATABASES = ["sqlite"]
if os.getenv("MIGRATION_TEST_DATABASE_URL"):
    DATABASES.append("postgresql")


@pytest.fixture(params=DATABASES)
def migration_app(request, tmp_path):
    if request.param == "sqlite":
        url = f"sqlite:///{tmp_path / 'migrations.db'}"
    else:
        url = os.environ["MIGRATION_TEST_DATABASE_URL"]

    app = create_app({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": url,
        "RATELIMIT_ENABLED": False,
        "AUTO_CREATE_TABLES": False,
    })
    with app.app_context():
        reset_database()
        yield app
        db.session.remove()
        reset_database()
        db.engine.dispose()


def reset_database():
    db.session.remove()
    if db.engine.dialect.name == "postgresql":
        with db.engine.begin() as conn:
            conn.execute(sa.text("DROP SCHEMA public CASCADE"))
            conn.execute(sa.text("CREATE SCHEMA public"))
    else:
        db.drop_all()
        with db.engine.begin() as conn:
            conn.execute(sa.text("DROP TABLE IF EXISTS alembic_version"))


def alembic_config():
    return current_app.extensions["migrate"].migrate.get_config(MIGRATIONS_DIR)


def upgrade(revision="head"):
    db.session.remove()
    command.upgrade(alembic_config(), revision)


def index_names():
    if db.engine.dialect.name == "postgresql":
        query = "SELECT indexname FROM pg_indexes WHERE schemaname = current_schema()"
    else:
        query = "SELECT name FROM sqlite_master WHERE type = 'index'"
    with db.engine.connect() as conn:
        return {row[0] for row in conn.execute(sa.text(query))}


def table_names():
    return set(sa.inspect(db.engine).get_table_names())


def add_club():
    college = College(key="hunter", name="Hunter College", seed_account="hunterusg")
    db.session.add(college)
    db.session.flush()
    club = Club(college_id=college.id, name="Coding Club", instagram_handle="hunter.coding")
    db.session.add(club)
    db.session.flush()
    return club


def add_event(club, title, start_time, post_id):
    db.session.add(Event(
        club_id=club.id, college_id=club.college_id, title=title,
        start_time=start_time, post_id=post_id,
    ))


# fresh database

def test_migrations_build_exactly_what_the_models_describe(migration_app):
    """Fails if someone changes a model and forgets to write a migration for it."""
    upgrade()
    with db.engine.connect() as conn, warnings.catch_warnings():
        # Alembic can't compare expression indexes (uq_events_club_title_day) and warns
        # about it. The tests below check that index directly.
        warnings.simplefilter("ignore")
        differences = compare_metadata(MigrationContext.configure(conn), db.metadata)

    assert differences == [], (
        "The models and the migrations don't match. Run "
        "`flask --app run db migrate -m \"...\"` and commit the new file.\n"
        f"Differences: {differences}"
    )


def test_migrations_create_every_model_table_and_the_new_indexes(migration_app):
    upgrade()

    assert set(db.metadata.tables) <= table_names()
    assert NEW_INDEXES <= index_names()


def test_migrated_index_blocks_a_duplicate_event(migration_app):
    upgrade()
    club = add_club()
    add_event(club, "Intro to Git", datetime(2026, 12, 1, 18, 0), "post-1")
    db.session.commit()

    # A reminder post: new post_id, different capitalization, same day, different time.
    add_event(club, "INTRO TO GIT", datetime(2026, 12, 1, 9, 30), "post-2")
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()

    # Same title on another day is a different event.
    add_event(club, "Intro to Git", datetime(2026, 12, 8, 18, 0), "post-3")
    db.session.commit()
    assert Event.query.count() == 2


def test_downgrade_removes_the_second_migration_only(migration_app):
    upgrade()
    command.downgrade(alembic_config(), BASELINE)

    assert "saved_events" not in table_names()
    assert not NEW_INDEXES & index_names()
    assert "events" in table_names()


# a database built by create_all(), like the shared one

def test_upgrade_skips_saved_events_that_create_all_already_made(migration_app):
    # Original tables, then create_all() adding saved_events later. It never adds the
    # new indexes to events, because that table already existed.
    upgrade(BASELINE)
    SavedEvent.__table__.create(db.engine)
    assert DUPLICATE_INDEX not in index_names()

    upgrade()

    assert NEW_INDEXES <= index_names()


def test_upgrade_is_a_no_op_when_everything_already_exists(migration_app):
    # Everything made by create_all() (and the index added by dedupe_events.py).
    db.create_all()
    command.stamp(alembic_config(), BASELINE)

    upgrade()

    assert NEW_INDEXES <= index_names()


def test_upgrade_stops_on_duplicates_lists_them_and_deletes_nothing(migration_app):
    upgrade(BASELINE)
    club = add_club()
    add_event(club, "Intro to Git", datetime(2026, 12, 1, 18, 0), "post-1")
    add_event(club, "intro to git", datetime(2026, 12, 1, 9, 30), "post-2")  # planted copy
    add_event(club, "Resume Workshop", datetime(2026, 12, 2, 17, 0), "post-3")
    db.session.commit()

    with pytest.raises(RuntimeError) as error:
        upgrade()

    message = str(error.value)
    assert "1 group(s) of duplicate events" in message
    assert "'intro to git'" in message
    assert "2026-12-01" in message
    assert "Resume Workshop".lower() not in message
    assert Event.query.count() == 3
    assert "saved_events" not in table_names()
    assert DUPLICATE_INDEX not in index_names()

    # Once the extra copy is gone, the upgrade goes through.
    Event.query.filter_by(post_id="post-2").delete()
    db.session.commit()
    upgrade()

    assert NEW_INDEXES <= index_names()
