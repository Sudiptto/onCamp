# Events API

Base URL: `http://localhost:5000/api`. The React calendar requests these routes
through Vite's `/api` proxy. They read the configured database, not mock data.
Signed-out visitors receive events up to `ANON_EVENT_DAYS` days ahead (default 7);
`/events/archive` requires sign-in (see [AUTH.md](AUTH.md)).

| Route | Purpose |
|---|---|
| `GET /events` | All upcoming or ongoing dated events, ordered by start time. |
| `GET /events/filter` | Upcoming or ongoing events filtered by range and/or club. |
| `GET /events/archive` | Dated events from the past 120 days plus upcoming events, including the archive table. |

`/events/filter` accepts `range`: `1w`, `2w` (default), `1m`, `semester`
(120 days), or `all`. The endpoints `/events/filter` and `/events/archive` accept
an optional positive integer `club_id`. Invalid values return 400.
Ranges include the indicated number of calendar days after today. Dates and
times use the campus clock, `America/New_York`.

An event without an end time stays upcoming until the end of its start day.
Events without a start date are not displayed. Finished events are excluded
from upcoming results even if the archive job has not yet run.

## Response

```json
{
  "range": "2w",
  "count": 1,
  "events": [{
    "id": 12,
    "event_id": "post:123456",
    "club_id": "1",
    "club_name": "Hunter Coding Club",
    "club_link": "https://www.instagram.com/hunter_coding/",
    "club_pfp": null,
    "event_name": "Intro to Git Workshop",
    "event_link": null,
    "free_food": true,
    "date": "2026-10-07",
    "start_time": "17:00",
    "end_time": null,
    "start_datetime": "2026-10-07T17:00:00",
    "location": "Hunter North 1001",
    "post_link": "https://www.instagram.com/p/example/"
  }],
  "limited": false,
  "locked_count": 0
}
```

`id` is the integer primary key of an upcoming `events` row. Save and unsave
send that number to `/api/saved-events`. It is `null` once the event has moved
to the archive. `club_id` and `event_id` are strings for the frontend.
Instagram post IDs keep `event_id` stable when events move to the archive. For
a manually created event without a post ID, `event_id` is based on its table
and row ID and can change on archival. `club_pfp`, `event_link`, `end_time`, `location`,
and `post_link` can be `null`. `limited` and `locked_count` report events
hidden by the signed-out access rule.
