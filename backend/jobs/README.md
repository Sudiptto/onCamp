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
