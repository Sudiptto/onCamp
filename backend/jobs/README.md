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

Output is `club_activity.json` with `active` and `inactive` lists (post id, post code, last post date, days since, next check). Each record is shaped as one future DB row; the DB write would replace the file write in `pipeline.run()`. The full pipeline (discovery, AI filter, activity check) is meant to run once per semester.

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
