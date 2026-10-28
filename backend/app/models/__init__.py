from .college import College
from .club import Club
from .club_activity import ClubActivity
from .event import Event
from .user import User

__all__ = ["College", "Club", "ClubActivity", "Event", "User"]

# Updated models/__init__.py
# otherwise SQLAlchemy won't know these tables exist and they'll never get created in the database
