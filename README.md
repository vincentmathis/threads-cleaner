# threads-cleaner

Bulk-delete your Threads posts and replies. Free, open-source, runs 100% locally.

## Quick start

```bash
# Install & run with uv (no permanent install needed)
uv run --with threads-cleaner threads-cleaner login

# Or clone and run from source
git clone https://github.com/YOUR_USERNAME/threads-cleaner
cd threads-cleaner
uv run threads-cleaner login
```

## Usage

```bash
# See which account is logged in
threads-cleaner whoami

# Preview what would be deleted (no changes made)
threads-cleaner delete --older-than 30 --dry-run

# Delete posts older than 30 days
threads-cleaner delete --older-than 30

# Delete posts before a specific date
threads-cleaner delete --before 2024-01-01

# Delete everything
threads-cleaner delete --yes
```

## Login

The tool uses your browser's session cookie — no developer account needed.

1. Log in to threads.net in Chrome/Firefox/Edge/Brave
2. Run `threads-cleaner login` (reads cookies automatically via browser-cookie3)
3. If auto-detection fails, paste your `sessionid` cookie from DevTools

## Install permanently

```bash
uv tool install .
# Then use as: threads-cleaner delete --dry-run
```

Or from PyPI (once published):

```bash
uv tool install threads-cleaner
```

## How it works

- Fetches posts via `i.instagram.com/api/v1/text_feed/` (Threads backend API)
- Sorts oldest → newest for safe deletion
- Deletes via `i.instagram.com/api/v1/media/{id}/delete/`
- Rate-limited: 1s between deletes, 60s backoff on 429

## License

MIT
