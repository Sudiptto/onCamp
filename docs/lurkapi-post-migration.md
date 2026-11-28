# LurkAPI post-scan migration

Local replacement for the HikerAPI call that loads a club's recent Instagram posts. Discovery (the following graph) still uses HikerAPI. This file is the research note and the credit/token ledger.

## What we replace

The costly repeating job is the club post scan: active clubs every 2 days, inactive clubs about once a semester. Each scan used one HikerAPI `/gql/user/medias` call, then DeepSeek read the caption.

LurkAPI replacement is one call:

`GET https://api.lurkapi.com/v2/instagram/user/posts?username=<handle>&first=12`

Auth is `x-api-key` (or `Authorization: Bearer`). The project key is `LURK_API_KEY` in `.env`. Docs also accept `LURKAPI_API_KEY`; the client checks both.

## What we do not replace

- Semester discovery / following graph. Lurk's similar-profiles endpoint is not the same as walking a seed account's following list.
- Comments, reel transcripts, and the single-post endpoint. User posts already include caption, shortcode, `taken_at`, media type, and like/comment counts. A second `/v1/instagram/post` call would spend another credit for fields we already have.
- DeepSeek event extraction. Only the fetch changes. `process_club_posts` still receives `{items: [...]}`.

## Cost rules (from Lurk docs, checked 2026-11-28)

- User posts: 1 credit per call. Instagram returns at most 12 posts per page, so `first=12` is the useful maximum and still 1 credit.
- Asking for `first=1` is not cheaper and can return a pinned old post. We always request a page and pick the newest `taken_at` locally.
- Cached Lurk responses cost the same as fresh ones (`cache_max_age` is ignored; user posts are cached up to 3 minutes). Our own file cache under `backend/data/lurk/` is what avoids a repeat charge.
- Charged: the call reached Instagram, including `404 not_found`. Do not guess handles.
- Free: invalid params, `401`, `402 insufficient_credits`, `429`, and `5xx`.
- Rate limit: 50 requests / 10 seconds per account (`retry-after` on 429). High-volume accounts can be raised to 100.
- Switching notes that matter here: Instagram profile/posts take `username` or `url`, not `handle`. Next page is `after` = previous `end_cursor`, not `max_id`. Only GET is allowed.

## Credit budget

Grant discussed: 50,000 credits. The first live call on 2026-11-28 returned `credits_remaining: 50099` after a 1-credit charge, so the account balance at the start of this pilot was 50,100.

One post scan = 1 credit per club. At ~200 Hunter clubs scanned every 2 days, that is about 100 credits/day, or ~3,000/month, before inactive rechecks. 50,000 credits is roughly 16 months of post scans at that rate, if we never paginate and never call post/comments/transcripts.

DeepSeek is separate from Lurk credits. The local pilot sends only the newest caption, not all 12, so a trial does not burn a full scan's tokens.

## How to run locally

From `backend/`, with `LURK_API_KEY` in the repo `.env`. This does not write events.

```powershell
.\venv\Scripts\python.exe run_lurk_post_pilot.py --username hunter_bsa --analyze
.\venv\Scripts\python.exe run_lurk_post_pilot.py --username hunter_bsa bcc.hunter thebaithakhunter --analyze
```

Omit `--refresh` to reuse `backend/data/lurk/<username>.json` and spend 0 Lurk credits. The scheduled extractor (`run_post_extraction.py`) now fetches through the same Lurk client instead of HikerAPI.

## Pilot results (local, no database writes)

Three known handles, one user-posts call each, DeepSeek on the newest caption only:

| club | posts on page | newest | analysis | DeepSeek tokens | Lurk credits |
| --- | --- | --- | --- | --- | --- |
| hunter_bsa | 12 | DgF9ff8NFdv | event, Pitha Utshob | 681 | 1 |
| bcc.hunter | 6 | Dflcb14xySV | event, virtual open house | 672 | 1 |
| thebaithakhunter | 12 | DgNsA0UB8UW | not an event | 613 | 1 |

Total this pilot: 3 Lurk credits, 1,966 DeepSeek tokens. Balance after the three calls: 50,097. A later cache re-read of `hunter_bsa` should add a 0-credit row.

## Local active-club event scan (2026-11-28 UTC)

- Target: existing `backend/instance/oncamp_dev.db`, not the placeholder
  `DATABASE_URL` in the root environment. The scan used the existing two-day
  due schedule and the default three newest posts per club.
- 149 active Hunter clubs were due. 148 completed; `huntercollegelmsa` returned
  `404 not_found` and remains due. No activity checks or discovery ran.
- 442 posts were considered; six were already checked, and 436 were processed.
  The scan added 29 upcoming events and archived three previously expired events.
  The database had 30 current events afterward.
- Lurk responses reported 148 credits charged for successful requests; the
  404 response omitted its charge. Lurk documents `not_found` as charged, so
  the expected total is 149 credits. The last reported balance was 49,948,
  down 149 from the pilot's 50,097; account balance may also reflect other use.
- DeepSeek reported 443 successful calls: 247,110 prompt tokens and 27,765
  completion tokens, for 274,875 total. Seven calls were duplicate checks in
  addition to 436 post extractions. Provider-reported usage excludes any
  failed or unreported requests.
- The first run stopped after one completed club due to Windows console
  encoding; it was resumed with `PYTHONUTF8=1`, and the checkpoint prevented
  that club from being scanned again.

## Post-extraction verification (2026-11-28 UTC)

The standalone post extractor and the database event scan both use LurkAPI;
HikerAPI remains in discovery and activity checks. A live read-only BSA check
fetched three recent posts, all already checkpointed: 1 reported Lurk credit,
0 DeepSeek calls or tokens, and a reported balance of 49,947. The local database
remained unchanged.

## Usage log

| fetched_at | username | lurk_credits | credits_remaining | local_cache | prompt_tokens | completion_tokens | total_tokens | newest_post | note |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
<!-- usage-log -->
| 2026-11-28T05:05:40.487089+00:00 | hunter_bsa | 0 | None | yes |  |  |  | DgF9ff8NFdv | fetch only |
| 2026-11-28T05:05:09.942206+00:00 | bcc.hunter | 1 | 50098 | no | 577 | 95 | 672 | Dflcb14xySV | event |
| 2026-11-28T05:05:11.877505+00:00 | thebaithakhunter | 1 | 50097 | no | 572 | 41 | 613 | DgNsA0UB8UW | not an event |
| 2026-11-28T05:04:44.887974+00:00 | hunter_bsa | 1 | 50099 | no | 577 | 104 | 681 | DgF9ff8NFdv | event |
