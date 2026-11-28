# Scheduled Jobs

`jobs/` contains scheduler-facing entrypoints. Semester club discovery has an Azure Functions timer trigger; due activity checks and post extraction remain manual until their triggers are added.

## Semester club discovery (Azure Functions)

`function_app.py` defines an Azure Functions timer trigger for `jobs.club_discovery.semester_refresh.run_semester_discovery()`. It runs at **12:00 UTC on January 5 and August 5** (`0 0 12 5 1,8 *`). This is a semester-aligned twice-yearly schedule, not an exact 180-day interval. `run_on_startup` is disabled so deploying or restarting the Function App does not unexpectedly trigger a paid discovery run.

Each run queries every row in the `colleges` table, discovers and classifies that college's seed account following graph, then syncs approved clubs into the database. Newly added supported colleges are included once they have a `College` row with a seed account. The classification cache is stored in the `oncamp-discovery-cache` Blob container, so repeat semester runs don't reclassify unchanged accounts. `AzureWebJobsStorage` is used both by the timer host and this cache.

The first full discovery should be started manually after deploying and testing the Function App; the next scheduled run is the next January 5 or August 5. Configure `DATABASE_URL` to persistent Postgres, `APP_ENV=production`, `SECRET_KEY`, `HIKERAPI_ACCESS_KEY`, `LURK_API_KEY`, and `DEEPSEEK_API_KEY` in Function App settings. The Function App also needs `AzureWebJobsStorage` pointing to its Storage account. Do not rely on the local SQLite fallback or commit `local.settings.json`.

Existing PostgreSQL databases created with the earlier models must widen the profile-image URL columns; `create_all()` does not alter existing tables:

```sql
ALTER TABLE clubs ALTER COLUMN profile_pic_url TYPE text;
ALTER TABLE archived_clubs ALTER COLUMN profile_pic_url TYPE text;
```

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

`run_post_extraction.py` turns active clubs' Instagram posts into upcoming events. Posts are never stored; only events are. The fetch is LurkAPI user posts (1 credit per club, captions included). HikerAPI is still used for the following-graph discovery, not for this scan.

A no-database trial lives in `run_lurk_post_pilot.py`. It writes `backend/data/lurk/` (gitignored) and appends credit/token rows to [docs/lurkapi-post-migration.md](../../docs/lurkapi-post-migration.md). Re-running without `--refresh` uses the local cache and spends 0 Lurk credits. `--analyze` sends only the newest caption to DeepSeek.

```powershell
cd backend
.\venv\Scripts\python.exe run_lurk_post_pilot.py --username hunter_bsa --analyze
```

- Active clubs are scanned every 2 days (`--due`, picked by `club_post_checkpoints.checked_at`).
- Each club has a checkpoint (newest post id and date processed), so a post is sent to the AI at most once.
- Only events that have not happened yet (compared to the job's launch time, campus time) are saved to `events`. Past or undated events are skipped.
- At the start of every run, finished events move from `events` to `archived_events`.

```powershell
cd backend
python run_post_extraction.py --due --college hunter --limit 5
python run_post_extraction.py --username hunter_bsa --count 3
```

That command spends 1 Lurk credit per club. The local pilot above is the cheaper way to check one handle first.

## Manual end-to-end sequence

The semester discovery timer is separate from the manual activity and
post-extraction commands below. The intervals above only determine which clubs
are due **when those commands are run**. All active clubs use the same two-day
interval; there is no separate daily tier for the most active clubs. The
180-day activity-check interval is approximate, not tied to academic semester
dates. Archived clubs are not automatically rechecked or restored.

With the root `.env` configured and dependencies installed, run the following
from `backend/`. Discovery still calls HikerAPI. Post extraction calls LurkAPI (1 credit per club) and DeepSeek.

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
