# Accounts: Google sign-in

There are no passwords. Students sign in with Google, the backend checks the token Google gives back,
and then sets its own session cookie. Logged out visitors can see the next `ANON_EVENT_DAYS` days (default 7).

## Google Cloud setup (one time)

Use the new Google account to sign in to [Google Cloud Console](https://console.cloud.google.com/),
then create or select the project that will own onCamp's OAuth client.

1. Configure the app in [Google Auth Platform](https://console.cloud.google.com/auth/overview):
   - [Branding](https://console.cloud.google.com/auth/branding): set the app name and support email.
   - [Audience](https://console.cloud.google.com/auth/audience): choose **External**. While the app is in
     **Testing**, add the Google accounts that should be able to sign in as test users. The new account
     that owns the project is not automatically the only account allowed to sign in.
   - [Data Access](https://console.cloud.google.com/auth/data-access): request `openid`, `email`, and `profile`.
     Publish the app (move it to **In production**) before launch.
2. Open [Clients](https://console.cloud.google.com/auth/clients), choose **Create client**, and select
   **Web application**. You can also find OAuth credentials from
   [APIs & Services → Credentials](https://console.cloud.google.com/apis/credentials).
3. Add `http://localhost:5173` under **Authorized JavaScript origins**, plus the production frontend
   origin when available. This app uses Google Identity Services; no authorized redirect URI is needed.
4. Copy the new Web client ID (it ends in `.apps.googleusercontent.com`) into both files, replacing the
   old value:
   - Root `.env`: `GOOGLE_CLIENT_ID=<new-client-id>`
   - `frontend/.env`: `VITE_GOOGLE_CLIENT_ID=<same-new-client-id>`

   The backend verifies tokens against `GOOGLE_CLIENT_ID`, so both variables must contain the same new
   client ID. Keep the client ID out of source code; it is configuration, not a client secret.

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
