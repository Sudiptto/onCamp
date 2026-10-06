"""Mock calendar data for frontend development. Replace with DB queries later."""

from datetime import date, datetime, timedelta

_CLUBS = {
    "club_001": ("Hunter Coding Club", "hunter_coding", "https://instagram.com/hunter_coding"),
    "club_002": ("Hunter Dance Society", "hunter_dance", "https://instagram.com/hunter_dance"),
    "club_003": ("Hunter Pre-Med Association", "hunter_premed", "https://instagram.com/hunter_premed"),
    "club_004": ("Hunter Film Collective", "hunter_film", "https://instagram.com/hunter_film"),
}

# (id, club_id, name, form link, days from today, start, end, location, post shortcode, free food)
_EVENTS = [
    ("evt_001", "club_001", "Intro to Git Workshop", None, 1, "17:00", "18:30", "Hunter North 1001", "Cabc001", True),
    ("evt_002", "club_002", "Open Dance Practice", None, 2, "18:00", "20:00", "Thomas Hunter Hall, Room 305", "Cabc002", False),
    ("evt_003", "club_003", "MCAT Study Session", "https://forms.gle/mock-mcat", 4, "16:00", "18:00", "Hunter West 420", "Cabc003", True),
    ("evt_004", "club_004", "Movie Night: Short Films", None, 6, "19:00", "21:30", "Hunter East 214", "Cabc004", False),
    ("evt_005", "club_001", "Hackathon Kickoff", "https://forms.gle/mock-hack", 10, "10:00", "17:00", "Hunter North 1001", "Cabc005", True),
    ("evt_006", "club_002", "Spring Showcase Auditions", "https://forms.gle/mock-audition", 13, "17:30", "20:00", "Assembly Hall", "Cabc006", False),
    ("evt_007", "club_003", "Med School Panel", None, 24, "18:00", "19:30", "Hunter West 1214", "Cabc007", False),
    ("evt_008", "club_004", "Student Film Festival", "https://forms.gle/mock-fest", 45, "18:00", "22:00", "Kaye Playhouse", "Cabc008", True),
    ("evt_009", "club_001", "Demo Day", None, 80, "15:00", "18:00", "Hunter North 1001", "Cabc009", False),
    # Past events (archive only)
    ("evt_010", "club_002", "Fall Welcome Mixer", None, -3, "17:00", "19:00", "Hunter West Lobby", "Cabc010", True),
    ("evt_011", "club_001", "Python Basics Night", None, -20, "17:00", "18:30", "Hunter North 1001", "Cabc011", False),
    ("evt_012", "club_003", "Clinical Volunteering Info Session", "https://forms.gle/mock-clinical", -45, "18:00", "19:30", "Hunter West 420", "Cabc012", True),
    ("evt_013", "club_004", "Screenwriting Meetup", None, -90, "16:00", "18:00", "Hunter East 214", "Cabc013", False),
]

# FILTER VIA DATABASE
RANGES = {
    "1w": 7,
    "2w": 14,
    "1m": 30,
    "semester": 120,
    "all": None,
}


ARCHIVE_DAYS = 120  # last semester


def get_mock_events(
    range_key: str = "all",
    club_id: str | None = None,
    include_past: bool = False,
) -> list[dict]:
    """Return events sorted by start; upcoming only unless include_past (archive window)."""
    today = date.today()
    days = RANGES[range_key]
    end = today + timedelta(days=days) if days is not None else None
    earliest = today - timedelta(days=ARCHIVE_DAYS) if include_past else today

    events = []
    for eid, cid, name, link, offset, start, end_t, location, shortcode, free_food in _EVENTS:
        day = today + timedelta(days=offset)
        if day < earliest or (end and day > end):
            continue
        if club_id and cid != club_id:
            continue
        club_name, handle, club_link = _CLUBS[cid]
        events.append({
            "event_id": eid,
            "club_id": cid,
            "club_name": club_name,
            "club_link": club_link,
            "club_pfp": f"https://placehold.co/128x128?text={handle[:2].upper()}",
            "event_name": name,
            "event_link": link,
            "free_food": free_food,
            "date": day.isoformat(),
            "start_time": start,
            "end_time": end_t,
            "start_datetime": datetime.fromisoformat(f"{day.isoformat()}T{start}").isoformat(),
            "location": location,
            "post_link": f"https://instagram.com/p/{shortcode}/",
        })
    return sorted(events, key=lambda e: e["start_datetime"])
