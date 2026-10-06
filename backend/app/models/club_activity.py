from app.extensions import db


class ClubActivity(db.Model):

    __tablename__ = "club_activity"

    id = db.Column(db.Integer, primary_key=True)
    club_id = db.Column(db.Integer, db.ForeignKey("clubs.id"), unique=True, nullable=False)

    status = db.Column(db.String(20), nullable=False, default="inactive")  # "active" | "inactive"
    last_post_id = db.Column(db.String(255), nullable=True)
    last_post_at = db.Column(db.DateTime, nullable=True)
    days_since_last_post = db.Column(db.Integer, nullable=True)

    check_interval_days = db.Column(db.Integer, nullable=False, default=30)
    next_check_at = db.Column(db.DateTime, nullable=True)
    checked_at = db.Column(db.DateTime, nullable=True)

    def to_dict(self):
        return {
            "club_id": self.club_id,
            "status": self.status,
            "last_post_id": self.last_post_id,
            "last_post_at": self.last_post_at.isoformat() if self.last_post_at else None,
            "days_since_last_post": self.days_since_last_post,
            "check_interval_days": self.check_interval_days,
            "next_check_at": self.next_check_at.isoformat() if self.next_check_at else None,
            "checked_at": self.checked_at.isoformat() if self.checked_at else None,
        }