from app.extensions import db


class ArchivedEvent(db.Model):
    """Events that have already happened, moved out of `events` so that table stays small."""

    __tablename__ = "archived_events"

    id = db.Column(db.Integer, primary_key=True)
    club_id = db.Column(db.Integer, db.ForeignKey("clubs.id"), nullable=False, index=True)
    college_id = db.Column(db.Integer, db.ForeignKey("colleges.id"), nullable=False)
    post_id = db.Column(db.String(255), unique=True, nullable=True)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    start_time = db.Column(db.DateTime, nullable=True)
    end_time = db.Column(db.DateTime, nullable=True)
    location = db.Column(db.String(255), nullable=True)
    is_free_food = db.Column(db.Boolean, default=False)
    google_form_url = db.Column(db.String(500), nullable=True)
    source_url = db.Column(db.String(500), nullable=True)
    created_at = db.Column(db.DateTime, nullable=True)  # when it was first added to events
    archived_at = db.Column(db.DateTime, nullable=False)  # naive UTC
