from app.extensions import db


class SavedEvent(db.Model):
    """One user bookmarking one upcoming event, so their saves follow them across devices."""

    __tablename__ = "saved_events"
    __table_args__ = (
        # A user can save an event only once, even if they double-click or two tabs race.
        # This also serves "list my saved events", since user_id is its first column.
        db.UniqueConstraint("user_id", "event_id", name="uq_saved_events_user_event"),
    )

    id = db.Column(db.Integer, primary_key=True)
    # ON DELETE CASCADE: when an account or an event row goes away, its saves go too.
    # Events are deleted from `events` when they are archived, so saves only ever point
    # at upcoming events.
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    event_id = db.Column(
        db.Integer, db.ForeignKey("events.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_at = db.Column(db.DateTime, server_default=db.func.now(), nullable=False)

    event = db.relationship("Event", back_populates="saves")

    def to_dict(self):
        event = self.event
        calendar = None
        if event is not None and event.club is not None and event.start_time is not None:
            # Imported here so loading models does not pull the calendar service in first.
            from app.services.calendar_events import _format_event
            calendar = _format_event(event, event.club)
        return {
            "event_id": self.event_id,
            "saved_at": self.created_at.isoformat() if self.created_at else None,
            "event": event.to_dict() if event else None,
            "calendar": calendar,
        }
