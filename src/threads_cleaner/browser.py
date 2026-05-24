from __future__ import annotations

import time

from rich.console import Console

from threads_cleaner import config

console = Console()


class BrowserDeleter:
    def __init__(self, session: dict, *, headed: bool = False):
        self.session = session
        self._headed = headed
        self._browser = None
        self._context = None
        self._page = None
        self._pw = None

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
        from playwright.sync_api import sync_playwright
        self._pw = sync_playwright().start()
        try:
            self._browser = self._pw.chromium.launch(
                headless=not self._headed,
                args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
            )
        except Exception as e:
            msg = str(e)
            if "Executable doesn't exist" in msg or "executable" in msg.lower() and "playwright" in msg.lower():
                console.print("[red]Chromium browser not found.[/]")
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

    def _find_and_click_more(self) -> bool:
        result = self._page.evaluate("""
            (() => {
                const selectors = [
                    'svg[aria-label="More"]',
                    'button[aria-label="More"]',
                    '[aria-label="More"]',
                    'svg[aria-label="More options"]',
                ];
                for (const sel of selectors) {
                    const icons = document.querySelectorAll(sel);
                    for (const icon of icons) {
                        if (icon.offsetParent === null) continue;
                        if (icon.dataset.tried) continue;
                        const r = icon.getBoundingClientRect();
                        if (r.width < 5 || r.height < 5) continue;
                        if (r.y < 100) continue;
                        return {x: r.x + r.width / 2, y: r.y + r.height / 2};
                    }
                }
                return null;
            })()
        """)
        if result is None:
            return False
        self._page.mouse.click(result["x"], result["y"])
        time.sleep(0.3)
        return True

    def _click_menu_delete(self) -> bool:
        return self._page.evaluate("""
            (() => {
                const exact = ['Delete', 'Delete reply', 'Remove'];
                // On mobile web the popup is a bottom sheet, not [role="menu"].
                // Search any visible popup first, then fall back to whole page.
                const popup = document.querySelector('[role="menu"], [role="dialog"], [role="alertdialog"]');
                const scope = popup || document.body;
                const all = scope.querySelectorAll('span, div, button, [role="button"]');
                for (const el of all) {
                    if (el.offsetParent === null) continue;
                    const txt = (el.innerText || el.textContent || '').trim();
                    if (exact.includes(txt)) {
                        el.click();
                        return true;
                    }
                }
                // No delete option — mark current More as tried.
                const selectors2 = [
                    'svg[aria-label="More"]',
                    'button[aria-label="More"]',
                    '[aria-label="More"]',
                    'svg[aria-label="More options"]',
                ];
                for (const sel of selectors2) {
                    const icons = document.querySelectorAll(sel);
                    for (const icon of icons) {
                        if (icon.offsetParent === null) continue;
                        if (icon.dataset.tried) continue;
                        const r = icon.getBoundingClientRect();
                        if (r.width < 5 || r.height < 5) continue;
                        if (r.y < 100) continue;
                        icon.dataset.tried = '1';
                        break;
                    }
                }
                return false;
            })()
        """)

    def _click_confirm_delete(self) -> bool:
        return self._page.evaluate("""
            (() => {
                const exact = ['Delete', 'Delete reply', 'Remove'];
                const all = document.querySelectorAll('span, div, button, [role="button"]');
                for (const el of all) {
                    if (el.offsetParent === null) continue;
                    const txt = (el.innerText || el.textContent || '').trim();
                    if (exact.includes(txt)) {
                        // Must NOT be inside the menu (which we already dismissed)
                        if (!el.closest('[role="menu"]')) {
                            el.click();
                            return true;
                        }
                    }
                }
                return false;
            })()
        """)

    def _mark_current_more_tried(self):
        self._page.evaluate("""
            const selectors = [
                'svg[aria-label="More"]',
                'button[aria-label="More"]',
                '[aria-label="More"]',
                'svg[aria-label="More options"]',
            ];
            for (const sel of selectors) {
                const icons = document.querySelectorAll(sel);
                for (const icon of icons) {
                    if (icon.offsetParent === null) continue;
                    if (icon.dataset.tried) continue;
                    const r = icon.getBoundingClientRect();
                    if (r.width < 5 || r.height < 5) continue;
                    if (r.y < 100) continue;
                    icon.dataset.tried = '1';
                    break;
                }
            }
        """)

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

    def _delete_next_item(self) -> bool:
        self._dismiss_toasts()
        if not self._find_and_click_more():
            return False
        time.sleep(1.2)
        if not self._click_menu_delete():
            # _click_menu_delete() already marked the SVG as tried
            self._page.keyboard.press("Escape")
            time.sleep(0.5)
            return False
        time.sleep(1.2)
        if self._click_confirm_delete():
            time.sleep(2)
            had_error = self._has_error_toast()
            self._dismiss_toasts()
            return not had_error
        # No confirmation dialog — on mobile web the delete might
        # have gone through immediately. Check for errors.
        time.sleep(2.5)
        had_error = self._has_error_toast()
        self._dismiss_toasts()
        if not had_error:
            return True  # assume deleted
        self._page.keyboard.press("Escape")
        time.sleep(0.5)
        self._mark_current_more_tried()
        return False

    def _delete_loop(self, label: str, max_deletes: int = 0) -> int:
        deleted = 0
        consecutive_fails = 0
        total_fails = 0
        while True:
            if max_deletes and deleted >= max_deletes:
                console.print(f"[dim]  hit limit of {max_deletes} {label}[/]")
                break
            ok = self._delete_next_item()
            if ok:
                deleted += 1
                consecutive_fails = 0
                total_fails = 0
                if deleted % 10 == 0:
                    console.print(f"[dim]  deleted {deleted} {label}...[/]")
                continue
            consecutive_fails += 1
            total_fails += 1
            if total_fails > 60:
                console.print(f"[dim]  gave up after {total_fails} failures[/]")
                break
            if consecutive_fails >= 5:
                before = self._page.evaluate("window.scrollY")
                self._page.evaluate("window.scrollBy(0, 5000)")
                time.sleep(2)
                after = self._page.evaluate("window.scrollY")
                if after == before:
                    console.print(f"[dim]  reached end of {label}[/]")
                    break
                consecutive_fails = 0
            else:
                self._page.evaluate("window.scrollBy(0, 300)")
                time.sleep(0.8)
        return deleted

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
        return self._delete_loop("posts", max_deletes)

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
        return self._delete_loop("replies", max_deletes)

def run_browser_delete(*, include_replies=False, max_deletes=None, dry_run=False, yes=False, headed=False):
    session = config.load_session()
    if not session:
        raise RuntimeError("Not logged in. Run:  threads-cleaner browser-login")
    targets = "posts" + (" + replies" if include_replies else "")
    label = f" (max {max_deletes})" if max_deletes else ""
    mode = "DRY RUN (no deletes)" if dry_run else "LIVE"
    console.print("[bold]Threads Cleaner - Browser Delete[/bold]\n"
                  f"  Mode: {mode}\n"
                  f"  Targets: {targets}{label}\n")
    if not dry_run and not yes:
        result = console.input("[yellow]This will delete items. Continue? [y/N] [/]")
        if result.lower() != "y": return
    if dry_run:
        console.print("[blue]Dry run — nothing was deleted.[/]")
        return
    deleter = BrowserDeleter(session=session, headed=headed)
    try:
        deleter.start()
        total = 0
        total += deleter.delete_posts(max_deletes or 0)
        if include_replies:
            remaining = (max_deletes - total) if max_deletes else 0
            total += deleter.delete_replies(remaining)
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
