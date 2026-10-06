from app.extensions import db

class ClubActivity(db.Model):
    __tablename__ = "club_activity"

    id = db.Column(db.Integer, primary_key=True)
    club_id = db.Column(db.Integer, db.ForeignKey("clubs.id"), unique=True, nullable=False)
    college_id = db.Column(db.Integer, db.ForeignKey("colleges.id"), nullable=False)

    status = db.Column(db.String(20), nullable=False, default="inactive")  # "active" | "inactive"
    last_post_id = db.Column(db.String(255), nullable=True)
    last_post_at = db.Column(db.DateTime, nullable=True)

    next_check_at = db.Column(db.DateTime, nullable=True, index=True)
    checked_at = db.Column(db.DateTime, nullable=True)

    def to_dict(self):
        return {
            "club_id": self.club_id,
            "college_id": self.college_id,
            "status": self.status,
            "last_post_id": self.last_post_id,
            "last_post_at": self.last_post_at.isoformat() if self.last_post_at else None,
            "next_check_at": self.next_check_at.isoformat() if self.next_check_at else None,
            "checked_at": self.checked_at.isoformat() if self.checked_at else None,
        }
