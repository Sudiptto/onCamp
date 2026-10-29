from .college import College
from .club import Club
from .club_activity import ClubActivity
from .archived_club import ArchivedClub
from .event import Event
from .user import User

__all__ = ["College", "Club", "ClubActivity", "ArchivedClub", "Event", "User"]

# otherwise SQLAlchemy won't know these tables exist and they'll never get created in the database
