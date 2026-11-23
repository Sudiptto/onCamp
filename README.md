# onCamp

College students miss events constantly — not because they don't care, but because club announcements are buried in Instagram posts nobody sees in time. onCamp fixes that.

It automatically discovers student clubs at Hunter College by traversing public Instagram following graphs, scans their recent posts for upcoming events and free food, and surfaces everything into a single clean calendar. No manual curation, no sign-ups required from clubs — it just works in the background.

## Key goals

- Build a fully automated discovery pipeline that finds active Hunter clubs from a single seed Instagram account
- Scan club posts daily, detect events and free food mentions using AI, and extract structured info (date, time, location)
- Present everything in a simple UI students can actually use — upcoming events, what has food, what's happening this week
- Keep infrastructure costs under $5/month and design it to scale to other colleges with minimal changes

## Where it's headed

Start with Hunter, prove the pipeline works, then expand to other CUNY schools and eventually any college. The long-term vision is a lightweight campus activity layer that lives on top of Instagram without requiring clubs to change how they post.

## Repo structure

```text
onCamp/
├── backend/        # Flask + SQLAlchemy API
├── frontend/       # React (Vite) UI
├── .env.example    # copy this to .env and fill in values
├── .gitignore
├── README.md
└── .env            # local secrets (never committed)
```

## Setup

### Prerequisites

- Python 3.11+
- Node 18+
- Git

### 1. Clone and create your environment file

```bash
git clone https://github.com/your-org/onCamp.git
cd onCamp
cp .env.example .env
```

Fill in `.env` with the values shared by the team. Never commit `.env`.

### 2. Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
flask --app run db upgrade      # create or update the database tables
python run.py
```

Flask runs at `http://localhost:5000`.

Database tables are managed with Flask-Migrate (files in `backend/migrations/versions`).
After changing a model, run `flask --app run db migrate -m "what changed"`, check the new
file, and commit it. Alembic can't see expression indexes (like `uq_events_club_title_day`),
so write those by hand. `pytest` fails if the models and the migrations don't match.

### 3. Frontend

```bash
cd frontend
npm install
npm run dev
```

Vite runs at `http://localhost:5173`.

The calendar reads events from the backend database through the `/api` proxy.
To populate that database, see the manual discovery, activity-check, and post
extraction sequence in [Scheduled Jobs](backend/jobs/README.md). Until a
scheduler is deployed, activity checks and post extraction do not run automatically.
Semester club discovery has an Azure Functions timer entrypoint; it runs only
after that Function App is deployed and configured.

## Environment variables

All secrets live in `.env` at the project root. Never hardcode keys in source files.

| Variable | Description |
|---|---|
| `DATABASE_URL` | Supabase Postgres connection string (shared, ask team) |
| `HIKERAPI_ACCESS_KEY` | HikerAPI key for Instagram data |
| `HIKER_BASE_URL` | `https://api.instagrapi.com` |
| `HIKER_FOLLOWING_ENDPOINT` | Current cursor-based following route: `/gql/user/following/chunk` |
| `HIKER_FOLLOWING_FORCE` | `true` skips Hiker's extra privacy check because the page already includes `is_private` |
| `HIKER_PAGE_SIZE` | Requested accounts per following page on the g2 fallback; defaults to `50` |
| `HIKER_MAX_PAGES` | Safety limit for one refresh; defaults to `25` |
| `DEEPSEEK_API_KEY` | DeepSeek API key for club validation |
| `DEEPSEEK_BASE_URL` | DeepSeek OpenAI-compatible API base URL |
| `DEEPSEEK_MODEL` | Cheap model used by the separate AI filter, defaults to `deepseek-chat` |
| `SEED_ACCOUNT` | Instagram handle to start discovery from (`hunterusg`) |
| `APP_ENV` | Runtime environment (`development`, `production`) |

The backend loads the root `.env` before reading its database and other
configuration. If `DATABASE_URL` is unset, it uses the local SQLite database.

## Branch convention

```text
main          # stable
dev           # active development, PRs merge here first
feat/<name>   # feature branches off dev
```

## Architecture notes

This repo intentionally starts with a Hunter-first pipeline while keeping the application model flexible enough to expand beyond Hunter.

- Discovery logic is isolated under the scheduler-ready `backend/jobs/club_discovery/` package.
- Scheduler-ready discovery jobs live under `backend/jobs/`; the semester discovery timer is defined in `backend/function_app.py`.
- API routes are registered through a Flask app factory.
- UI components are separated by concern and can be expanded without modifying the data layer.
- The seed account is configurable and can be replaced as the platform expands to other colleges.
- Discovery is a scheduled refresh job, not a user-facing request. `backend/jobs/club_discovery.run()` resolves the seed once, walks the paginated following graph, removes private accounts, and returns a raw refresh summary. AI filtering runs separately through `backend/run_ai_club_filter.py`.
- The semester discovery timer reads supported colleges and seed accounts from the `colleges` table, runs discovery and AI classification, and syncs approved clubs to the database. Activity checks and post extraction remain manual until their own timers are added.
- The current live route returned 25 accounts per page, so Hunter's 284-account graph took 12 cursor pages in the verified refresh. The result was 259 raw accounts, 25 private accounts skipped, and 234 public accounts written to the clean export.
- Following pages are `UserShort` records. The raw discovery export intentionally stores only `username`, `user_id`, `full_name`, `profile_pic_url`, and `is_private`.
- The AI filter preserves `following.json`, sends only `username`, `user_id`, and `full_name` to DeepSeek, then matches approved IDs back to the original records to produce `clubs.json`.

## Future roadmap

1. Build the discovery pipeline around a configurable seed account.
2. Add post ingestion and AI extraction for event metadata.
3. Persist normalized club and event records.
4. Expose a calendar-oriented frontend for students.
5. Extend the system to new campuses with configurable college settings.
