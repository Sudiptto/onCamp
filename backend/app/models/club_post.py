from app.extensions import db


class ClubPostCheckpoint(db.Model):
    """The newest post we have already processed for a club, so the next run skips everything up to it."""

    __tablename__ = "club_post_checkpoints"

    id = db.Column(db.Integer, primary_key=True)
    club_id = db.Column(db.Integer, db.ForeignKey("clubs.id"), unique=True, nullable=False)
    last_post_id = db.Column(db.String(255), nullable=False)
    last_post_at = db.Column(db.DateTime, nullable=False)  # naive UTC
    checked_at = db.Column(db.DateTime, nullable=False)  # naive UTC


class ClubPost(db.Model):
    """One processed Instagram post and what the AI pulled out of its caption."""

    __tablename__ = "club_posts"

    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.String(255), unique=True, nullable=False)
    club_id = db.Column(db.Integer, db.ForeignKey("clubs.id"), nullable=False, index=True)
    college_id = db.Column(db.Integer, db.ForeignKey("colleges.id"), nullable=False)

    post_code = db.Column(db.String(64), nullable=True)
    post_url = db.Column(db.String(500), nullable=False)
    posted_at = db.Column(db.DateTime, nullable=False)  # naive UTC
    caption = db.Column(db.Text, nullable=True)

    is_event = db.Column(db.Boolean, nullable=False, default=False)
    title = db.Column(db.String(255), nullable=True)
    description = db.Column(db.Text, nullable=True)
    # Event times are campus local time (America/New_York), stored without a timezone.
    start_time = db.Column(db.DateTime, nullable=True)
    end_time = db.Column(db.DateTime, nullable=True)
    location = db.Column(db.String(255), nullable=True)
    has_free_food = db.Column(db.Boolean, nullable=False, default=False)
    google_form_url = db.Column(db.String(500), nullable=True)

    ai_model = db.Column(db.String(100), nullable=True)
    extracted_at = db.Column(db.DateTime, nullable=False)  # naive UTC
