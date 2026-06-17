# threads-cleaner

Bulk-delete your Threads posts and replies via browser automation.  
No API keys, no developer account, no rate limits.

> **Desktop web status:** Meta broke the `threads.com` desktop web UI — the More (⋮) menu doesn't open.  
> This tool works around it by using a **mobile viewport**. The browser opens phone-sized, which serves the working mobile web version.

## Installation

```bash
pipx install threads-cleaner
# or
uv tool install threads-cleaner
```

You can also download a packaged .exe directly from [here](https://github.com/vincentmathis/threads-cleaner/releases/download/v1.0.0/threads-cleaner.exe)

Then install the Chromium browser:

```bash
threads-cleaner install-browser
```

## Quick start

```bash
# 1. Log in (opens a phone-sized browser — go to threads.com, sign in, go to your profile)
threads-cleaner login

# 2. Delete all posts (default action — no subcommand needed)
threads-cleaner

# 3. Watch what happens
threads-cleaner --headed --max 5
```

## Usage

| Command / Option | Description |
|------------------|-------------|
| *(default)* | Deletes posts/replies — no subcommand needed |
| `login` | Opens a headed browser — log into Threads, session saved automatically |
| `install-browser` | Download the Chromium browser required by Playwright |
| `--target`, `-t` | What to delete: `posts` (default), `replies`, or `both` |
| `--max N`, `-m N` | Stop after N deletions (0 = unlimited) |
| `--dry-run` | Open browser, navigate to profile, no destructive clicks |
| `--headed` | Show the browser window (for debugging) |
| `--yes`, `-y` | Skip the confirmation prompt (for scripting) |

### Examples

```bash
# Delete up to 10 posts, show browser
threads-cleaner --headed --max 10

# Delete everything including replies, no prompts
threads-cleaner --target both --yes

# Preview what the tool would do
threads-cleaner --dry-run --headed

# Delete 50 replies only
threads-cleaner --target replies --max 50
```

## How it works

1. **`login`** opens a Chromium window in mobile mode (390×844).  
   You sign into `threads.com` — session cookies are saved to `~/.config/threads-cleaner/session.json`.

2. **`threads-cleaner`** (default action) loads those cookies, navigates to your profile, and for each post:
   - Clicks the **More** (⋮) button via Playwright's native mouse click
   - Clicks **Delete** in the mobile bottom-sheet menu
   - Clicks **Delete** in the confirmation dialog (or detects auto-deletion if no dialog appears)
   - Marks each item as "tried" immediately to prevent loops

3. With `--target replies` or `--target both`, it also navigates to `@{username}/replies/` and repeats.

Each UI interaction takes ~4-5 seconds. The tool scrolls automatically and can delete hundreds of items per session.

### Safety

- **`--dry-run`** opens the browser but never clicks anything destructive.
- **`--max N`** stops after N successful deletes.
- "Something went wrong" toasts are detected and counted as failures (never falsely reported as deleted).
- Session cookies expire — re-run `browser-login` if you see a login error.
- Every "More" button is tried at most once — no infinite retry loops.

## Requirements

- Python 3.11+
- Chromium (installed via `threads-cleaner install-browser`)

## Why not use an API?

| Approach | Result |
|----------|--------|
| Meta Threads Graph API | Requires approved FB Developer account (author's was suspended) |
| Instagram REST API (`text_feed`, `media/delete`) | Returns 404 or kills the session server-side |
| Threads GraphQL endpoint (`threads.com/api/graphql`) | Same-origin fetch fails from extension context |
| **Browser UI automation ← you are here** | Works. Clicks the real UI like a human. |

## License

MIT
