from app.extensions import db


class User(db.Model):
    # No passwords here, Google handles the login.

    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    # Google's id for the person. Emails can change but this doesn't.
    google_sub = db.Column(db.String(255), unique=True, nullable=False)
    # Not unique on purpose. If someone leaves and their email gets reused, the new person
    # has a different google_sub and should get their own account, not the old one.
    email = db.Column(db.String(254), nullable=False, index=True)
    name = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now(), nullable=False)
    last_login_at = db.Column(db.DateTime(timezone=True), nullable=True)

    def to_dict(self):
        # leave google_sub out, nobody else needs it
        return {
            "id": self.id,
            "email": self.email,
            "name": self.name,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
