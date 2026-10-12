# AI Classification

This folder contains the DeepSeek adapter and review prompt for classifying the raw following dataset. It is intentionally a separate command from the discovery job.

The expected future flow is:

1. Run the raw following refresh; this preserves `following.json`.
2. Run `python backend/run_ai_club_filter.py`.
3. Build the `username`/`user_id`/`full_name` candidate list in memory (never written to disk) and send it to the configured cheap `deepseek-chat` model in batches (`--batch-size`, default 40).
4. If DeepSeek's content filter rejects a batch ("Content Exists Risk"), the batch is bisected automatically until the single offending account is isolated and skipped; every other account in that batch is still classified.
5. Validate the JSON response and match AI-selected `user_id` values against the original `following.json`, writing the original full records to `clubs.json`.

The prompt deliberately classifies from only `username`, `user_id`, and `full_name`. It must not invent bios, posts, activity, or facts that were not supplied. For 700-800 accounts, use the cheap model configured in `.env`; lower `--batch-size` if the provider rejects the context size.

The original `following.json` is never modified. The candidate list sent to DeepSeek is never written to disk.

## Retries, progress, and the cache

- Timeouts, rate limits, and server errors are retried twice with a short wait. The request timeout is 60 seconds (the openai library's own default is 10 minutes).
- If DeepSeek sends back malformed JSON, that batch is tried once more, then skipped and logged. The other batches keep going.
- If retries run out on a timeout or rate limit, the run stops instead of failing on every batch that is left.
- After every finished batch, the result for each account is saved to `club_classifications.json` (next to `clubs.json` by default). It holds only `user_id`, a yes/no result, the model name, and a short prompt fingerprint. No names or bios.
- If any account could not be classified, `clubs.json` is not touched and the command exits with an error. Run it again and only the missing accounts are sent to DeepSeek.
- Models other than `deepseek-chat` and `deepseek-reasoner` (for example `deepseek-flash`) are run in non-thinking mode. DeepSeek's newer models think before answering by default, which is slower and ignores `temperature`.
- Changing `DEEPSEEK_MODEL` or editing the prompt makes the old results outdated, so those accounts are classified again. Use `--no-cache` to redo everything.

### What happens when something goes wrong

| What goes wrong | What happens |
|---|---|
| A timeout, rate limit, or server error | Tried again twice with a short wait (Retry-After is respected). If it keeps failing, the run stops and keeps the batches that finished. |
| DeepSeek sends malformed JSON, or names an account that was not in the batch | That batch is tried once more, then skipped and logged. The other batches keep going. Nothing from it is saved. |
| Wrong API key (401), out of balance (402), or a model name that no longer exists (400, 404, 422) | Stops right away and prints the reason. No retries. |
| One account is rejected by DeepSeek's content filter | The batch is split until that account is found, then it is skipped. It is saved so it is not sent again. |
| Any account could not be classified | `clubs.json` is not touched. Run again and only the missing accounts are sent. |
| DeepSeek says nothing is a club | `clubs.json` is not touched. Run with `--no-cache` if that looks wrong. |
| Ctrl+C or a crash in the middle | Finished batches are saved. At most the batch in progress is redone. |
| The cache file is damaged | It is ignored and rebuilt. |
| `DEEPSEEK_MODEL` or the prompt changed | Old results are redone. |
| An account was unfollowed | It is left out of `clubs.json`. |
| An account has no `user_id` | It can't be saved, so it is sent every run and never selected. |

Not handled: two runs at the same time (the last one to save wins), and results never expire by age.
