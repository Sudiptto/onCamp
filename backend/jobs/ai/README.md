# AI Classification

This folder contains the DeepSeek adapter and review prompt for classifying the raw following dataset. It is intentionally a separate command from the discovery job.

The expected future flow is:

1. Run the raw following refresh; this preserves `following.json`.
2. Run `python backend/run_ai_club_filter.py`.
3. Build the `username`/`user_id`/`full_name` candidate list in memory (never written to disk) and send it to the configured cheap `deepseek-chat` model in batches (`--batch-size`, default 40).
4. If DeepSeek's content filter rejects a batch ("Content Exists Risk"), the batch is bisected automatically until the single offending account is isolated and skipped; every other account in that batch is still classified.
5. Validate the JSON response and match AI-selected `user_id` values against the original `following.json`, writing the original full records to `clubs.json`.

The prompt deliberately classifies from only `username`, `user_id`, and `full_name`. It must not invent bios, posts, activity, or facts that were not supplied. For 700-800 accounts, use the cheap model configured in `.env`; lower `--batch-size` if the provider rejects the context size.

The original `following.json` is never modified, and no intermediate files are created — only `following.json` (input) and `clubs.json` (output) exist on disk.

