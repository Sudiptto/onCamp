from datetime import date, datetime, time, timedelta

from app.extensions import db


class Event(db.Model):
    """An upcoming event pulled from a club's Instagram post.

    Only upcoming events live here. Once an event has passed it is moved to
    archived_events (see app/services/event_archive.py).
    """

    __tablename__ = "events"

    id = db.Column(db.Integer, primary_key=True)
    club_id = db.Column(db.Integer, db.ForeignKey("clubs.id"), nullable=False)
    college_id = db.Column(db.Integer, db.ForeignKey("colleges.id"), nullable=False)
    # The Instagram post this event came from. Unique so one post can never create two events.
    post_id = db.Column(db.String(255), unique=True, nullable=True)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    # Campus local time (America/New_York), stored without a timezone.
    start_time = db.Column(db.DateTime, nullable=True)
    end_time = db.Column(db.DateTime, nullable=True)
    location = db.Column(db.String(255), nullable=True)
    is_free_food = db.Column(db.Boolean, default=False)
    google_form_url = db.Column(db.String(500), nullable=True)
    source_url = db.Column(db.String(500), nullable=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    __table_args__ = (
        # A reminder post ("Intro to Git is tomorrow!") is a new post_id, so post_id alone
        # can't catch it. Same club + same title (any capitalization) + same day = the same
        # event, so the database refuses a second copy. Built on expressions, so it needs no
        # extra column and works on both PostgreSQL and SQLite.
        db.Index(
            "uq_events_club_title_day",
            club_id,
            db.func.lower(title),
            db.func.date(start_time),
            unique=True,
        ),
        # The app's main question is "what's coming up at this college?", so it can jump
        # straight to one college's events in time order instead of scanning every row.
        db.Index("ix_events_college_start", college_id, start_time),
    )

    # The club's name and photo come from the club's own row, so they aren't copied here.
    club = db.relationship("Club", backref=db.backref("events", lazy="dynamic"))
    # Saves point at an event. When the event is archived (deleted from this table),
    # its saves go with it instead of pointing at a row that no longer exists.
    saves = db.relationship(
        "SavedEvent", back_populates="event", cascade="all, delete-orphan", passive_deletes=False
    )

    @classmethod
    def find_duplicate(cls, club_id: int, title: str, start_time: datetime):
        """The event this one would duplicate under uq_events_club_title_day, if any."""
        return cls.query.filter(
            cls.club_id == club_id,
            db.func.lower(cls.title) == db.func.lower(title),
            db.func.date(cls.start_time) == db.func.date(start_time),
        ).first()

    @classmethod
    def upcoming(cls, college_id: int, today: date, until: date | None = None):
        """One college's events from `today` (campus date) onward, soonest first.

        Starts at midnight so a date-only event (stored at 00:00) still shows on its own day.
        `until` is inclusive: events on that day are kept.
        """
        query = cls.query.filter(
            cls.college_id == college_id,
            cls.start_time >= datetime.combine(today, time.min),
        )
        if until is not None:
            query = query.filter(cls.start_time < datetime.combine(until + timedelta(days=1), time.min))
        return query.order_by(cls.start_time, cls.id)

    def to_dict(self):
        return {
            "id": self.id,
            "club_id": self.club_id,
            "title": self.title,
            "description": self.description,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "location": self.location,
            "is_free_food": self.is_free_food,
            "google_form_url": self.google_form_url,
            "source_url": self.source_url,
        }
