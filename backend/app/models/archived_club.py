from app.extensions import db


class ArchivedClub(db.Model):
    """Clubs with no post in over 2 years. Kept so discovery doesn't re-add them and they can be restored."""

    __tablename__ = "archived_clubs"

    id = db.Column(db.Integer, primary_key=True)
    college_id = db.Column(db.Integer, db.ForeignKey("colleges.id"), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    instagram_handle = db.Column(db.String(255), unique=True, nullable=False)
    instagram_user_id = db.Column(db.String(64), unique=True, nullable=True)
    profile_pic_url = db.Column(db.String(500), nullable=True)
    last_post_at = db.Column(db.DateTime, nullable=True)
    archived_at = db.Column(db.DateTime, nullable=False)
