# threads-cleaner

Bulk-delete your Threads posts and replies via browser automation.  
Clicks the web UI like a human — no API keys, no developer account, no rate limits.

## Installation

```bash
pip install threads-cleaner
# or
uv add threads-cleaner
```

Then install the Playwright browser:

```bash
playwright install chromium
# or
uv run playwright install chromium
```

## Quick start

```bash
# 1. Log in (opens a browser — go to threads.net, sign in, navigate to your profile)
threads-cleaner browser-login

# 2. Delete all posts
threads-cleaner browser-delete

# 3. Show the browser window to watch what happens
threads-cleaner browser-delete --headed --max 5
```

## Usage

| Command | Description |
|---------|-------------|
| `browser-login` | Opens a headed browser — log into Threads and session is saved automatically |
| `browser-delete` | Deletes posts by clicking the Threads UI |
| `browser-delete --include-replies` | Also delete your replies |
| `browser-delete --max N` | Stop after N deletions (0 = unlimited) |
| `browser-delete --dry-run` | Open browser, navigate to profile, but don't confirm any deletes |
| `browser-delete --headed` | Show the browser (useful for debugging) |
| `browser-delete --yes` | Skip the confirmation prompt (for scripting) |

### Examples

```bash
# Delete up to 10 posts, show the browser
threads-cleaner browser-delete --headed --max 10

# Delete everything including replies, no prompts
threads-cleaner browser-delete --include-replies --yes

# Preview what the tool would do
threads-cleaner browser-delete --dry-run --headed

# Delete 50 replies only
threads-cleaner browser-delete --include-replies --max 50
```

## How it works

1. **`browser-login`** opens a Chromium window — you sign into threads.net and the session cookies are saved locally.
2. **`browser-delete`** loads those cookies into a fresh browser, navigates to your profile, and for each post:
   - Clicks the **More** (⋮) button
   - Clicks **Delete** in the popup menu
   - Clicks **Delete** in the confirmation dialog
3. With `--include-replies`, it also navigates to `/replies/` and repeats the same loop.

Each delete takes ~3-4 seconds (limited by UI animations).  
The tool scrolls down automatically as it runs, so it can delete hundreds of items in one session.

### Safety

- **`--dry-run`** opens the browser and navigates to your profile but never clicks anything destructive.
- **`--max N`** stops after N successful deletes.
- If a "Something went wrong" toast appears, the tool counts it as a failure (not a success) and continues.
- Session cookies expire — re-run `browser-login` if you get a login error.

## Requirements

- Python 3.11+
- Chromium (installed via `playwright install chromium`)

## Why no API?

Meta's Threads Graph API requires an approved Facebook Developer account (the author's was suspended).  
The Instagram REST API endpoints that Threads used internally are now returning 404 or killing sessions.  
The only reliable approach is real browser automation that clicks the UI like a human.

## License

MIT
