from app.extensions import db


class ClubPostCheckpoint(db.Model):
    """Where the post scan left off for a club, so the next run skips everything up to it.

    Posts themselves are never stored. Only the events found in them are (see Event), so this
    row is what stops the same post from being sent to the AI twice.
    """

    __tablename__ = "club_post_checkpoints"

    id = db.Column(db.Integer, primary_key=True)
    club_id = db.Column(db.Integer, db.ForeignKey("clubs.id"), unique=True, nullable=False)
    # Newest post already processed. Empty until a club has had at least one post processed.
    last_post_id = db.Column(db.String(255), nullable=True)
    last_post_at = db.Column(db.DateTime, nullable=True)  # naive UTC
    # When the last scan of this club finished; drives the "scan active clubs every 2 days" schedule.
    checked_at = db.Column(db.DateTime, nullable=False)  # naive UTC
