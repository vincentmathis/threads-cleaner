# threads-cleaner

Bulk-delete your Threads posts and replies using browser automation. Clicks the web UI like a human — no API keys, no developer account, no rate limits.

## Requirements

- Python 3.11+
- [Playwright browsers](https://playwright.dev/python/docs/browsers): `uv run playwright install chromium`

## Usage

```bash
# Log in (opens a browser — navigate to threads.net, log in, go to your profile)
uv run threads-cleaner browser-login

# Delete all posts
uv run threads-cleaner browser-delete

# Delete posts + replies (max 10)
uv run threads-cleaner browser-delete --include-replies --max 10

# See what happens (opens browser but doesn't confirm)
uv run threads-cleaner browser-delete --dry-run --headed
```

## How it works

Playwright opens a real Chromium browser with your saved session cookies, navigates to your Threads profile, and clicks the UI:

1. Finds the first post's **More** (three dots) button
2. Clicks **Delete** in the popup menu
3. Clicks **Delete** in the confirmation dialog
4. Repeats for the next post
5. With `--include-replies`, also navigates to `/replies/` tab and repeats

Speed is limited by UI animation (~3-4s per item). Use `--max N` to delete in batches.

## License

MIT
