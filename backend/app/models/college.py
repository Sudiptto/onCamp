from app.extensions import db

# defines a new database table called colleges

class College(db.Model):
    __tablename__ = "colleges"

    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(50), unique=True, nullable=False)
    name = db.Column(db.String(255), nullable=False)
    seed_account = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    def to_dict(self):
        return {
            "id": self.id,
            "key": self.key,
            "name": self.name,
            "seed_account": self.seed_account,
        }