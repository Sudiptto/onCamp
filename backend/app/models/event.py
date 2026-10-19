from datetime import date as date_type

from app.extensions import db


class Event(db.Model):
    """One event found in a club's Instagram post.

    One club can have many events, and one post can announce several events,
    so each event gets its own row that points back to its club and its post.
    """

    __tablename__ = "events"
    __table_args__ = (
        # Same club + same day + same title = the same event (e.g. a reminder post),
        # so the database refuses to store it twice.
        db.UniqueConstraint("club_id", "date", "title", name="uq_events_club_date_title"),
        # Lets the app jump straight to one college's upcoming events instead of
        # scanning every event.
        db.Index("ix_events_college_date", "college_id", "date"),
    )

    # Already existing fields
    id = db.Column(db.Integer, primary_key=True)
    club_id = db.Column(db.Integer, db.ForeignKey("clubs.id"), nullable=False)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    start_time = db.Column(db.DateTime, nullable=True)
    end_time = db.Column(db.DateTime, nullable=True)
    location = db.Column(db.String(255), nullable=True)
    is_free_food = db.Column(db.Boolean, default=False)
    source_url = db.Column(db.String(500), nullable=True)  # the Instagram post link
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    # --- New fields for Schema 2 (all optional, so nothing existing breaks) ---
    # Which college the event belongs to, for fast "upcoming at Hunter" lookups.
    college_id = db.Column(db.Integer, db.ForeignKey("colleges.id"), nullable=True)
    # The day of the event on its own, so the date is kept even when a post gives no time.
    date = db.Column(db.Date, nullable=True)
    # The Instagram post this event came from (one post can announce several events).
    instagram_post_id = db.Column(db.String(64), nullable=True, index=True)
    event_link = db.Column(db.String(500), nullable=True)    # sign-up / RSVP form
    meeting_link = db.Column(db.String(500), nullable=True)  # Zoom, Teams, etc.
    # When the event may be deleted from the database. Left empty until the
    # team agrees on the rule.
    delete_after = db.Column(db.Date, nullable=True, index=True)

    # The club's name, link and photo come from the club's own record,
    # so they are not copied onto every event.
    club = db.relationship("Club", backref=db.backref("events", lazy="dynamic"))

    @classmethod
    def upcoming(cls, college_id, today=None, until=None):
        """Events for one college from today onward, soonest first."""
        today = today or date_type.today()
        query = cls.query.filter(cls.college_id == college_id, cls.date >= today)
        if until is not None:
            query = query.filter(cls.date <= until)
        return query.order_by(cls.date, cls.start_time)

    def to_dict(self):
        return {
            # Existing keys (unchanged)
            "id": self.id,
            "club_id": self.club_id,
            "title": self.title,
            "description": self.description,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "location": self.location,
            "is_free_food": self.is_free_food,
            "source_url": self.source_url,
            # New keys
            "college_id": self.college_id,
            "date": self.date.isoformat() if self.date else None,
            "instagram_post_id": self.instagram_post_id,
            "event_link": self.event_link,
            "meeting_link": self.meeting_link,
            "delete_after": self.delete_after.isoformat() if self.delete_after else None,
        }

