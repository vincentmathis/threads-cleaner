from __future__ import annotations

import re
import time
from datetime import datetime, timedelta, timezone

from rich.console import Console

from threads_cleaner import config

console = Console()


class BrowserDeleter:
    def __init__(self, session: dict, *, headed: bool = False, older_than: str | None = None):
        self.session = session
        self._headed = headed
        self._browser = None
        self._context = None
        self._page = None
        self._pw = None
        self._older_than = self._parse_older_than(older_than) if older_than else None

    @staticmethod
    def _parse_older_than(value: str) -> str:
        match = re.match(r'^(\d+)([hdwmy])$', value.lower().strip())
        if not match:
            raise ValueError(f"Invalid --older-than format: '{value}'. Use e.g. 30d, 7d, 24h, 2w, 1m")
        num = int(match.group(1))
        unit = match.group(2)
        now = datetime.now(timezone.utc)
        if unit == 'h':
            threshold = now - timedelta(hours=num)
        elif unit == 'd':
            threshold = now - timedelta(days=num)
        elif unit == 'w':
            threshold = now - timedelta(weeks=num)
        elif unit == 'm':
            threshold = now - timedelta(days=num * 30)
        elif unit == 'y':
            threshold = now - timedelta(days=num * 365)
        return threshold.isoformat()

    def _cookies_for_playwright(self) -> list[dict]:
        cookies = []
        now_ts = int(time.time()) + 86400 * 30
        for name in ("sessionid", "csrftoken", "ds_user_id", "rur"):
            val = self.session.get(name, "")
            if val:
                for domain in (".threads.net", ".threads.com"):
                    cookies.append({
                        "name": name, "value": val,
                        "domain": domain, "path": "/",
                        "secure": True, "sameSite": "Lax",
                        "expires": now_ts,
                        **({"httpOnly": True} if name == "sessionid" else {}),
                    })
        return cookies

    def start(self):
        import os
        # PyInstaller bundles Playwright's driver into a temp dir, which makes
        # the driver look for browsers there instead of the user profile.
        # Tell it to use the standard install location.
        pw_browsers = os.environ.get("PLAYWRIGHT_BROWSERS_PATH") or os.path.join(
            os.environ.get("USERPROFILE", ""), "AppData", "Local", "ms-playwright"
        )
        if os.path.isdir(pw_browsers):
            os.environ["PLAYWRIGHT_BROWSERS_PATH"] = pw_browsers
        from playwright.sync_api import sync_playwright
        self._pw = sync_playwright().start()
        try:
            self._browser = self._pw.chromium.launch(
                headless=not self._headed,
                args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
            )
        except Exception as e:
            msg = str(e)
            console.print(f"[red]{msg}[/]")
            if "executable" in msg.lower():
                console.print("Run: [bold]threads-cleaner install-browser[/]")
                raise RuntimeError("Playwright browser not installed") from e
            raise
        self._context = self._browser.new_context(
            viewport={"width": 390, "height": 844},
            user_agent="Mozilla/5.0 (Linux; Android 14; Pixel 8 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.6367.83 Mobile Safari/537.36",
        )
        self._page = self._context.new_page()
        console.print("[dim]  setting session cookies...[/]")
        self._context.add_cookies(self._cookies_for_playwright())
        self._page.goto("about:blank")

    def stop(self):
        if self._browser:
            self._browser.close()
        if self._pw:
            self._pw.stop()

    def _dismiss_popups(self):
        try:
            self._page.keyboard.press("Escape")
            time.sleep(0.3)
        except: pass
        for text in ["Allow", "Accept", "Accept all", "Allow all", "Reject", "Close", "Got it"]:
            try:
                btn = self._page.locator(f'button:has-text("{text}")').first
                if btn.is_visible(timeout=500):
                    btn.click(timeout=1000)
                    time.sleep(0.3)
            except: pass
        try:
            self._page.keyboard.press("Escape")
            time.sleep(0.3)
            self._page.keyboard.press("Escape")
            time.sleep(0.3)
        except: pass

    def _click_menu_delete(self) -> bool:
        try:
            item = self._page.locator('[role="menuitem"]').filter(
                has_text=re.compile(r"Delete", re.IGNORECASE)
            ).first
            item.wait_for(state="attached", timeout=6000)
            item.click(timeout=5000, force=True)
            return True
        except Exception:
            return False

    def _click_confirm_delete(self) -> bool:
        try:
            time.sleep(0.5)
            dialog = self._page.locator('[role="dialog"]').first
            dialog.wait_for(state="visible", timeout=10000)
            item = dialog.locator('[role="button"]').filter(
                has_text=re.compile(r"Delete", re.IGNORECASE)
            ).first
            item.wait_for(state="attached", timeout=3000)
            item.click(timeout=5000, force=True)
            return True
        except Exception:
            return False

    def _dismiss_toasts(self):
        try:
            self._page.keyboard.press("Escape")
            time.sleep(0.4)
            self._page.keyboard.press("Escape")
            time.sleep(0.3)
        except:
            pass

    def _has_error_toast(self) -> bool:
        return self._page.evaluate("""
            (() => {
                const all = document.querySelectorAll('span, div, [role="alert"]');
                for (const el of all) {
                    const txt = (el.innerText || el.textContent || '').toLowerCase();
                    if (txt.includes('something went wrong') || txt.includes('try again')) {
                        return true;
                    }
                }
                return false;
            })()
        """)

    def _delete_item_on_thread(self, username: str) -> bool:
        """Find and delete the current user's More-button item on the current thread page.
        Finds a container that has BOTH a user link AND a timestamp AND a
        svg[aria-label="More"] — that container is the post wrapper, and the More
        button inside it is the correct three-dot menu."""
        candidate = self._page.evaluate(r"""
            ({username, olderThan}) => {
                const escaped = username.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
                const userPattern = new RegExp('/@' + escaped + '(/|$|\\?|#)');

                // 1. Collect all svg[aria-label="More"] with positions
                const moreSvgs = [];
                for (const svg of document.querySelectorAll('svg[aria-label="More"]')) {
                    if (svg.hasAttribute('data-oc-processed')) continue;
                    const r = svg.getBoundingClientRect();
                    if (r.width < 5 || r.height < 5) continue;
                    // Walk up to clickable parent
                    let target = svg.parentElement;
                    for (let up = 0; up < 5; up++) {
                        if (!target) break;
                        if (target.tagName === 'BUTTON' || target.getAttribute('role') === 'button') break;
                        target = target.parentElement;
                    }
                    if (!target) continue;
                    moreSvgs.push({svg, target, y: r.y});
                }
                if (!moreSvgs.length) return false;

                // 2. For each More SVG, find the closest parent container that has BOTH
                //    a user link AND a timestamp (post container). Pick the SVG with
                //    the smallest depth (tightest container) — avoids nav/sidebar SVGs
                //    that match at a higher page level.
                let bestTarget = null;
                let bestSvg = null;
                let bestDepth = 999;
                let bestTime = null;
                for (const {svg, target} of moreSvgs) {
                    let container = target.parentElement;
                    for (let d = 0; d < 10; d++) {
                        if (!container || container.tagName === 'HTML' || container.tagName === 'BODY') break;
                        const hasUser = Array.from(container.querySelectorAll('a[href]')).some(
                            a => userPattern.test(a.getAttribute('href'))
                        );
                        const hasTime = container.querySelector('time[datetime]');
                        if (hasUser && hasTime) {
                            if (d < bestDepth) {
                                bestDepth = d;
                                bestTarget = target;
                                bestSvg = svg;
                                bestTime = hasTime;
                            }
                            break; // don't go higher for this SVG
                        }
                        container = container.parentElement;
                    }
                }
                if (!bestTarget) return false;

                if (olderThan && bestTime) {
                    const pd = new Date(bestTime.getAttribute('datetime'));
                    if (!isNaN(pd.getTime()) && pd > new Date(olderThan)) return false;
                }
                bestTarget.setAttribute('data-oc-item', '1');
                bestSvg.setAttribute('data-oc-processed', '1');
                return true;
            }
        """, {"username": username, "olderThan": self._older_than})

        if not candidate:
            return False
        try:
            self._page.locator('[data-oc-item="1"]').first.click(timeout=5000)
            self._page.evaluate("document.querySelectorAll('[data-oc-item]').forEach(e => e.removeAttribute('data-oc-item'))"
)
        except Exception:
            return False
        time.sleep(1.5)
        if not self._click_menu_delete():
            self._page.keyboard.press("Escape")
            time.sleep(0.5)
            return False
        time.sleep(1.2)
        if not self._click_confirm_delete():
            return False
        time.sleep(2)
        had_error = self._has_error_toast()
        self._dismiss_toasts()
        return not had_error

    def _collect_post_urls(self, username: str) -> list[str]:
        urls = self._page.evaluate(r"""
            (username) => {
                const escaped = username.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
                const pattern = new RegExp('^/@' + escaped + '/post/\\w+$');
                const base = window.location.origin;
                const result = new Set();
                for (const a of document.querySelectorAll('a[href]')) {
                    let h = a.getAttribute('href');
                    if (!h) continue;
                    if (h.startsWith('//')) h = 'https:' + h;
                    else if (h.startsWith('/')) h = base + h;
                    else if (!h.startsWith('http')) continue;
                    try { var u = new URL(h); } catch(e) { continue; }
                    if (!/threads\.(com|net)$/i.test(u.hostname)) continue;
                    const p = u.pathname.replace(/\/+$/, '');
                    if (pattern.test(p)) result.add(u.href);
                }
                return Array.from(result);
            }
        """, username)
        return urls

    def _scroll_page(self, times: int = 3):
        for _ in range(times):
            self._page.evaluate("window.scrollBy(0, 2000)")
            time.sleep(0.3)

    def delete_posts(self, max_deletes: int = 0) -> int:
        username = self.session.get("username", "")
        profile_url = f"https://www.threads.com/@{username}"
        console.print(f"[dim]  navigating to {profile_url}...[/]")
        try:
            self._page.goto(profile_url, wait_until="domcontentloaded", timeout=60000)
        except: pass
        time.sleep(4)
        if "login" in self._page.url.lower():
            console.print(f"[red]Not logged in (current URL: {self._page.url}).[/]")
            console.print("[yellow]Run [bold]threads-cleaner browser-login[/] to refresh the session.[/]")
            raise RuntimeError("Session expired or invalid")
        self._dismiss_popups()

        deleted = 0
        seen = set()
        scroll_stalls = 0

        while True:
            if max_deletes and deleted >= max_deletes:
                console.print(f"[dim]  hit limit of {max_deletes} posts[/]")
                break

            # Collect post URLs currently on the page
            urls = self._collect_post_urls(username)
            new = [u for u in urls if u not in seen]
            seen.update(new)

            if not new:
                if scroll_stalls >= 10:
                    break
                scroll_stalls += 1
                console.print(f"[dim]  scrolling for more posts... ({scroll_stalls}/10)[/]")
                self._scroll_page(3)
                time.sleep(2)
                continue

            scroll_stalls = 0

            for post_url in new:
                if max_deletes and deleted >= max_deletes:
                    break

                console.print(f"[dim]  opening post...[/]")
                try:
                    self._page.goto(post_url, wait_until="domcontentloaded", timeout=30000)
                except: pass
                time.sleep(3)
                self._dismiss_popups()
                if "login" in self._page.url.lower():
                    console.print("[red]Session expired.[/]")
                    return deleted

                if self._delete_item_on_thread(username):
                    deleted += 1
                    console.print(f"[green]OK[/] deleted post {deleted}")
                else:
                    console.print(f"[yellow]  could not delete post on this page[/]")

                # Go back to profile page
                try:
                    self._page.goto(profile_url, wait_until="domcontentloaded", timeout=30000)
                except: pass
                time.sleep(2)

        return deleted

    def delete_replies(self, max_deletes: int = 0) -> int:
        username = self.session.get("username", "")
        replies_url = f"https://www.threads.com/@{username}/replies/"
        console.print(f"[dim]  navigating to {replies_url}...[/]")
        try:
            self._page.goto(replies_url, wait_until="domcontentloaded", timeout=30000)
        except:
            pass
        time.sleep(4)
        if "login" in self._page.url.lower():
            console.print(f"[red]Not logged in (current URL: {self._page.url}).[/]")
            console.print("[yellow]Run [bold]threads-cleaner browser-login[/] to refresh the session.[/]")
            raise RuntimeError("Session expired or invalid")
        self._dismiss_popups()

        # Replies are shown directly on this page with their own More button
        deleted = 0
        scroll_stalls = 0

        while True:
            if max_deletes and deleted >= max_deletes:
                console.print(f"[dim]  hit limit of {max_deletes} replies[/]")
                break

            if self._delete_item_on_thread(username):
                deleted += 1
                console.print(f"[green]OK[/] deleted reply {deleted}")
                # Stay on the same page — reply was removed from DOM
                time.sleep(2)
                continue

            # No reply found on screen — scroll down for more
            scroll_stalls += 1
            if scroll_stalls >= 10:
                break
            console.print(f"[dim]  scrolling for more replies... ({scroll_stalls}/10)[/]")
            self._scroll_page(3)
            time.sleep(2)

        return deleted


def run_browser_delete(*, target="posts", max_deletes=None, dry_run=False, yes=False, headed=False, older_than=None):
    session = config.load_session()
    if not session:
        raise RuntimeError("Not logged in. Run:  threads-cleaner browser-login")
    label = f" (max {max_deletes})" if max_deletes else ""
    filter_label = f", older than {older_than}" if older_than else ""
    mode = "DRY RUN (no deletes)" if dry_run else "LIVE"
    console.print("[bold]Threads Cleaner - Browser Delete[/bold]\n"
                  f"  Mode: {mode}\n"
                  f"  Targets: {target}{label}{filter_label}\n")
    if not dry_run and not yes:
        result = console.input("[yellow]This will delete items. Continue? [y/N] [/]")
        if result.lower() != "y": return
    if dry_run:
        console.print("[blue]Dry run — nothing was deleted.[/]")
        return
    deleter = BrowserDeleter(session=session, headed=headed, older_than=older_than)
    try:
        deleter.start()
        total = 0
        remaining = max_deletes or 0
        if target in ("both", "replies"):
            n = deleter.delete_replies(remaining)
            total += n
            remaining = (remaining - n) if remaining else 0
        if target in ("both", "posts"):
            n = deleter.delete_posts(remaining)
            total += n
        console.print(f"\n[bold green]Done.[/] Deleted {total} item(s).")
    finally:
        deleter.stop()


def run_browser_login() -> dict:
    from playwright.sync_api import sync_playwright, TimeoutError as PwTimeout
    console.print("[bold]Threads Cleaner - Browser Login[/bold]\n")
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=False, args=["--no-sandbox"])
            ctx = browser.new_context(
                viewport={"width": 390, "height": 844},
                user_agent="Mozilla/5.0 (Linux; Android 14; Pixel 8 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.6367.83 Mobile Safari/537.36",
            )
            page = ctx.new_page()
            page.goto("about:blank")
            console.print("[yellow]Go to [bold]https://www.threads.net/[/bold] -> log in -> go to your profile -> wait[/]")
            try:
                page.wait_for_url("**/***@**", timeout=600000)
            except PwTimeout:
                browser.close()
                raise RuntimeError("Login timed out")
            time.sleep(2)
            cookies_raw = ctx.cookies()
            cookies = {c["name"]: c["value"] for c in cookies_raw if c["name"] in ("sessionid", "csrftoken", "ds_user_id", "rur")}
            if not cookies.get("sessionid"):
                browser.close()
                raise RuntimeError("No session cookie")
            sessionid = cookies["sessionid"]
            csrftoken = cookies.get("csrftoken", "")
            ds_user_id = cookies.get("ds_user_id", "")
            cookies["sessionid"] = sessionid
            cookies["csrftoken"] = csrftoken
            cookies["ds_user_id"] = ds_user_id
            # Extract username from the URL
            username = page.url.split("/@")[-1].split("/")[0].split("?")[0]
            user_id = ds_user_id or ""
            session = {"sessionid": sessionid, "csrftoken": csrftoken, "ds_user_id": user_id, "rur": cookies.get("rur", ""), "user_id": user_id, "username": username}
            config.save_session(session)
            browser.close()
    except Exception as e:
        msg = str(e)
        if "Executable doesn't exist" in msg or ("executable" in str(e).lower() and "playwright" in str(e).lower()):
            console.print("[red]Chromium browser not found.[/]")
            console.print("Run: [bold]threads-cleaner install-browser[/]")
            raise RuntimeError("Playwright browser not installed") from e
        raise
    console.print(f"[green]Session saved.[/] Logged in as [bold]@{username}[/]")
    return session
