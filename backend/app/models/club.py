from app.extensions import db


class Club(db.Model):
    __tablename__ = "clubs"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    instagram_handle = db.Column(db.String(255), unique=True, nullable=False)
    seed_account = db.Column(db.String(255), nullable=False, default="hunterusg")
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "instagram_handle": self.instagram_handle,
            "seed_account": self.seed_account,
            "is_active": self.is_active,
        }
