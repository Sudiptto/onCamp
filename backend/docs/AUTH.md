# Accounts: Google sign-in

There are no passwords. Students sign in with Google, the backend checks the token Google gives back,
and then sets its own session cookie. Logged out visitors can see the next `ANON_EVENT_DAYS` days (default 7).

## Google Cloud setup (one time)

1. Google Cloud Console -> APIs & Services -> OAuth consent screen. User type: External. Scopes: openid, email, profile.
   While the app is in "Testing", only listed test users can sign in. Publish it ("In production") before launch.
2. Credentials -> Create credentials -> OAuth client ID -> **Web application**.
3. Authorized JavaScript origins: `http://localhost:5173` and your production URL. No redirect URI is needed.
4. Put the client ID in the root `.env` as `GOOGLE_CLIENT_ID` and in `frontend/.env` as `VITE_GOOGLE_CLIENT_ID`.

## Routes

| Route | Purpose |
|---|---|
| `GET /api/auth/csrf` | Returns the CSRF token for this session. |
| `POST /api/auth/google` | Body `{"credential": "<Google ID token>"}`. Needs `X-CSRF-Token`. Verifies the token, creates or updates the user, starts a session. |
| `GET /api/auth/me` | Current user or `null`. |
| `POST /api/auth/logout` | Needs `X-CSRF-Token`. Clears the session. |

## Access rules (enforced on the server)

- `/api/events` and `/api/events/filter`: signed-out visitors only receive events up to `ANON_EVENT_DAYS` ahead.
  Responses include `limited` and `locked_count`.
- `/api/events/archive`: requires sign-in (401 with `"code": "login_required"`).
- Protect any new user-only route with `@login_required` from `app/api/auth_helpers.py`.

## Notes

- Users are matched on Google's `sub`, not email. The email is refreshed on each login.
- Reminders must only be sent to the signed-in user's own Google email (already verified by Google).
- The `users` table changed shape (no `password_hash`). In dev, delete `oncamp_dev.db` or run `DROP TABLE users;`
  before starting, because `create_all()` does not alter existing tables.
