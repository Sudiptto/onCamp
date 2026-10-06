# Events API (mock data)

Base URL: `http://localhost:5000/api`. All routes are `GET` and currently return mock data from `app/api/mock_events.py`.

| Route | Purpose |
|---|---|
| `/events` | All upcoming events (today onward), sorted by start. |
| `/events/filter` | Upcoming events narrowed by `range` and/or `club_id`. |
| `/events/archive` | Legacy: past and upcoming events from the last semester. |

## Query params

- `/events/filter`
  - `range`: `1w`, `2w` (default), `1m`, `semester`, `all`. Invalid values return 400.
  - `club_id`: optional, e.g. `club_001`.
- `/events/archive`
  - `club_id`: optional.

## Response

```json
{
  "range": "2w",
  "count": 1,
  "events": [{
    "event_id": "evt_001",
    "club_id": "club_001",
    "club_name": "Hunter Coding Club",
    "club_link": "https://instagram.com/hunter_coding",
    "club_pfp": "https://placehold.co/128x128?text=HU",
    "event_name": "Intro to Git Workshop",
    "event_link": null,
    "free_food": true,
    "date": "2026-10-07",
    "start_time": "17:00",
    "end_time": "18:30",
    "start_datetime": "2026-10-07T17:00:00",
    "location": "Hunter North 1001",
    "post_link": "https://instagram.com/p/Cabc001/"
  }]
}
```

- `date` is `YYYY-MM-DD`; times are 24-hour `HH:MM`.
- `event_link` is `null` when there is no form or RSVP link.
- `free_food` is a JSON boolean (`true` or `false`).
- `range` is `"archive"` for the archive route.

## Notes

- Mock dates are offsets from today, so they never go stale.
- Each route has a `# FILTER VIA DATABASE` comment marking where the DB query replaces the mock filter.
- Finished events drop off `/events` automatically (`start >= now`) and remain available via `/events/archive`.
