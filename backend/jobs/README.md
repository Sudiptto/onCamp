# Scheduled Jobs

`jobs/` contains scheduler-facing entrypoints. Azure Functions, cron, or another managed scheduler should call a job entrypoint later; no trigger is defined here yet.

## Club discovery

`jobs/club_discovery.run()` performs one Hunter or college-USG refresh:

1. Resolve the configured USG seed account.
2. Walk the paginated following graph.
3. Keep public accounts and normalize the raw fields.
4. Return the raw public following result and refresh metadata.

AI classification runs separately under `jobs/ai/` after discovery. The current discovery job does not classify clubs or determine activity.

Example manual invocation:

```powershell
cd backend
.\venv\Scripts\python.exe discover_clubs.py --college hunter
```

Run the discovery and AI-filter stages together for a college:

```powershell
cd backend
.\venv\Scripts\python.exe run_full_pipeline.py --college hunter
```

The future scheduler should call `run()` and replace its file output with a database repository. The trigger itself is intentionally out of scope for this stage.

## Activity check

`jobs/activity_check.run()` splits `clubs.json` into active and inactive clubs. For each club it makes one `/gql/user/medias` call (`flat=true`), takes the newest post (by timestamp, since pinned posts can lead the grid), and buckets it:

- last post within 90 days: `active`, recheck every 2 days
- 91 days to 2 years old, or no posts: `inactive`, recheck every 180 days (about once a semester)
- over 2 years old: `archived`; the club moves to the `archived_clubs` table (its events are deleted) and `sync_clubs.py` will not re-add it

The activity pipeline writes a JSON result. `run_due_activity_checks.py` selects
due database clubs and persists their results in `club_activity`. Clubs without
an Instagram user ID cannot be checked and are counted separately.
Discovery and AI classification are intended to run about once per semester.

```powershell
cd backend
.\venv\Scripts\python.exe run_activity_check.py --limit 5   # cheap sample (default 5)
.\venv\Scripts\python.exe run_activity_check.py --all       # every club, one API call each
```

## Post extraction (events)

`run_post_extraction.py` turns active clubs' Instagram posts into upcoming events. Posts are never stored; only events are.

- Active clubs are scanned every 2 days (`--due`, picked by `club_post_checkpoints.checked_at`).
- Each club has a checkpoint (newest post id and date processed), so a post is sent to the AI at most once.
- Only events that have not happened yet (compared to the job's launch time, campus time) are saved to `events`. Past or undated events are skipped.
- At the start of every run, finished events move from `events` to `archived_events`.

```powershell
cd backend
python run_post_extraction.py --due --college hunter --limit 5
python run_post_extraction.py --username hunter_bsa --count 3
```

## Manual end-to-end sequence

No Azure Function, timer, cron expression, run time, or timezone for a scheduled
trigger is configured yet. The intervals above only determine which clubs are
due **when the commands are run**. All active clubs use the same two-day
interval; there is no separate daily tier for the most active clubs. The
180-day interval is approximate, not tied to academic semester dates. Archived
clubs are not automatically rechecked or restored.

With the root `.env` configured and dependencies installed, run the following
from `backend/`. API calls to Hiker and DeepSeek can incur costs:

```powershell
# Once per database, or when college configuration changes.
python seed_colleges.py

# Discovery and AI classification; explicitly select the output used by sync_clubs.
python run_full_pipeline.py --college hunter --output-dir data
python sync_clubs.py --college hunter --input data/clubs.json

# Check every due database club and update activity status and next-check times.
python run_due_activity_checks.py --college hunter --all

# Fetch posts from due active clubs, extract events, and archive finished events.
python run_post_extraction.py --due --college hunter
```

Run the last two commands in that order on each manual refresh. Without `--all`,
the activity check only processes five clubs by default. Post extraction reads
the newest three posts per club by default; `--count` can increase this up to
12, so a busy club may have older posts missed between scans. Failed scans need
attention and a retry. The event API and calendar show only events successfully
stored in the same configured database; an empty database gives an empty
calendar. See [Events API](../docs/EVENTS_API.md).
