# Fixture Data

Small samples pulled from the real Hunter following/AI-classification run (`backend/data/`), trimmed for readability. Kept intentionally small so tests stay fast and reviewable.

- `raw_following_sample.json` — raw HikerAPI `UserShort`-shaped records (before normalization). Includes real accounts (`bcc.hunter`, `hunterknittedknockers`, `mysocialdesigner`, `thebaithakhunter`, `hunter.hsa`, `prelawsocietyhc`) plus two synthetic records: one private account and one using alternate field names (`id`/`name`/`profile_picture`, no `is_private` key) to exercise the fallback branches in `normalize_account`.
- `following_sample.json` — the expected normalized, public-only output of `extract_public_accounts` for the raw sample above.
- `ai_clubs_response_sample.json` — a simulated DeepSeek `{"clubs": [...]}` response for the following sample. `mysocialdesigner` (a private individual, "Roger Coles") is intentionally excluded to prove non-club filtering; `hunterknittedknockers` is intentionally included to prove the no-keyword-required club case.
- `ai_clubs_response_invalid_sample.json` — same shape but references a `user_id` absent from `following_sample.json`, used to test the unknown-ID error path.
