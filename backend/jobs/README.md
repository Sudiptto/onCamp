# Scheduled Jobs

`jobs/` contains scheduler-facing entrypoints. Azure Functions, cron, or another managed scheduler should call a job entrypoint later; no trigger is defined here yet.

## Club discovery

`jobs/club_discovery.run()` performs one Hunter or college-USG refresh:

1. Resolve the configured USG seed account.
2. Walk the paginated following graph.
3. Keep public accounts and normalize the raw fields.
4. Classify likely club accounts using username/full-name signals.
5. Parse activity status when the payload contains an explicit activity signal.
6. Return a structured result and optionally write local outputs.

The current following payload does not contain post activity data, so club activity is `unknown` until a later ingestion stage supplies it. This avoids guessing that a club is inactive.

Example manual invocation:

```powershell
cd backend
.\venv\Scripts\python.exe discover_clubs.py --college hunter
```

The future scheduler should call `run()` and replace its file output with a database repository. The trigger itself is intentionally out of scope for this stage.
