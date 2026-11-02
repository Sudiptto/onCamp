from .college import College
from .club import Club
from .club_activity import ClubActivity
from .archived_club import ArchivedClub
from .event import Event
from .archived_event import ArchivedEvent
from .user import User
from .club_post import ClubPostCheckpoint

__all__ = [
    "College",
    "Club",
    "ClubActivity",
    "ArchivedClub",
    "Event",
    "ArchivedEvent",
    "User",
    "ClubPostCheckpoint",
]

# otherwise SQLAlchemy won't know these tables exist and they'll never get created in the database
