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

The future scheduler should call `run()` and replace its file output with a database repository. The trigger itself is intentionally out of scope for this stage.

## Activity check

`jobs/activity_check.run()` splits `clubs.json` into active and inactive clubs. For each club it makes one `/gql/user/medias` call (`flat=true`), takes the newest post (by timestamp, since pinned posts can lead the grid), and buckets it:

- last post within 90 days: `active`, recheck daily
- older than 90 days or no posts: `inactive`, recheck monthly

Output is `club_activity.json` with `active` and `inactive` lists (post id, post code, last post date, days since, next check). Each record is shaped as one future DB row; the DB write would replace the file write in `pipeline.run()`. The full pipeline (discovery, AI filter, activity check) is meant to run once per semester.

```powershell
cd backend
.\venv\Scripts\python.exe run_activity_check.py --limit 5   # cheap sample (default 5)
.\venv\Scripts\python.exe run_activity_check.py --all       # every club, one API call each
```
