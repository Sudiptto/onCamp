from app.extensions import db


class Club(db.Model):
    __tablename__ = "clubs"

    id = db.Column(db.Integer, primary_key=True)
    college_id = db.Column(db.Integer, db.ForeignKey("colleges.id"), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    instagram_handle = db.Column(db.String(255), unique=True, nullable=False)
    profile_pic_url = db.Column(db.String(500), nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    def to_dict(self):
        return {
            "id": self.id,
            "college_id": self.college_id,
            "name": self.name,
            "instagram_handle": self.instagram_handle,
            "profile_pic_url": self.profile_pic_url,
            "is_active": self.is_active,
        }