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
        self._tried_positions: set[tuple[int, int]] = set()

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

    def _find_and_click_more(self, *, username: str | None = None) -> bool:
        tried_list = [[p[0], p[1]] for p in self._tried_positions]
        result = self._page.evaluate(r"""
            ({tried, username}) => {
                const triedMap = {};
                for (const [tx, ty] of tried) {
                    const k = Math.round(tx/10)*10 + ',' + Math.round(ty/10)*10;
                    triedMap[k] = true;
                }

                // Build pattern for matching profile links
                const escaped = username ? username.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') : '';
                const profilePattern = username ? new RegExp('/@' + escaped + '(/|$|\\?|#)') : null;

                const all = document.querySelectorAll(
                    'svg[aria-label="More"], button[aria-label="More"], [aria-label="More"], svg[aria-label="More options"]'
                );
                const candidates = [];

                for (const icon of all) {
                    if (icon.offsetParent === null) continue;
                    const r = icon.getBoundingClientRect();
                    if (r.width < 5 || r.height < 5) continue;
                    if (r.y < 100) continue;
                    const cx = r.x + r.width / 2, cy = r.y + r.height / 2;
                    const k = Math.round(cx/10)*10 + ',' + Math.round(cy/10)*10;
                    if (triedMap[k]) continue;

                    // Check if this specific More button is inside the user's own reply section.
                    // Walk up only 3 levels — level 4 reaches the thread card (false positive).
                    let inUserPost = false;
                    if (username && profilePattern) {
                        let el = icon;
                        for (let i = 0; i < 3; i++) {
                            el = el.parentElement;
                            if (!el) break;
                            const avatarImg = el.querySelector('a[href] img');
                            if (avatarImg) {
                                const link = avatarImg.closest('a');
                                if (link && profilePattern.test(link.getAttribute('href'))) {
                                    inUserPost = true;
                                    break;
                                }
                            }
                        }
                        if (!inUserPost) continue;
                    }

                    // Dispatch directly on the icon or its immediate button parent (max 2 levels up).
                    // DO NOT walk up to the card — event.target must be the button, not the card.
                    let target = icon;
                    for (let i = 0; i < 2; i++) {
                        const p = target.parentElement;
                        if (!p) break;
                        if (p.tagName === 'BUTTON' || p.getAttribute('role') === 'button') {
                            target = p;
                            break;
                        }
                        target = p;
                    }
                    candidates.push({cx, cy, target});
                }

                if (candidates.length === 0) return null;
                candidates.sort((a, b) => b.cy - a.cy);
                const chosen = candidates[0];

                // Dispatch events directly — bypasses overlays
                const evtOpts = {bubbles: true, cancelable: true, composed: true};
                chosen.target.dispatchEvent(new PointerEvent('pointerdown', evtOpts));
                chosen.target.dispatchEvent(new PointerEvent('pointerup', evtOpts));
                chosen.target.dispatchEvent(new MouseEvent('click', evtOpts));

                return {x: chosen.cx, y: chosen.cy};
            }
        """, {"tried": tried_list, "username": username})
        if result is None:
            return False
        k = round(result["x"] / 10) * 10, round(result["y"] / 10) * 10
        self._tried_positions.add(k)
        return True

    def _click_menu_delete(self) -> bool:
        pos = self._page.evaluate("""
            (() => {
                const exact = ['Delete', 'Delete reply', 'Remove'];
                const popup = document.querySelector('[role="menu"], [role="dialog"], [role="alertdialog"]');
                const scope = popup || document.body;
                const all = scope.querySelectorAll('span, div, button, [role="button"]');
                for (const el of all) {
                    if (el.offsetParent === null) continue;
                    const txt = (el.innerText || el.textContent || '').trim();
                    if (exact.includes(txt)) {
                        const r = el.getBoundingClientRect();
                        return {x: r.x + r.width / 2, y: r.y + r.height / 2};
                    }
                }
                return null;
            })()
        """)
        if pos is None:
            return False
        self._page.mouse.click(pos["x"], pos["y"])
        return True

    def _click_confirm_delete(self) -> bool:
        pos = self._page.evaluate("""
            (() => {
                const exact = ['Delete', 'Delete reply', 'Remove'];
                const all = document.querySelectorAll('span, div, button, [role="button"]');
                for (const el of all) {
                    if (el.offsetParent === null) continue;
                    if (el.closest('[role="menu"]')) continue;
                    const txt = (el.innerText || el.textContent || '').trim();
                    if (exact.includes(txt)) {
                        const r = el.getBoundingClientRect();
                        return {x: r.x + r.width / 2, y: r.y + r.height / 2};
                    }
                }
                return null;
            })()
        """)
        if pos is None:
            return False
        self._page.mouse.click(pos["x"], pos["y"])
        return True

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

    def _delete_next_item(self, *, username: str | None = None) -> bool:
        self._dismiss_toasts()
        if not self._find_and_click_more(username=username):
            return False
        time.sleep(1.2)
        if not self._click_menu_delete():
            self._page.keyboard.press("Escape")
            time.sleep(0.5)
            return False
        time.sleep(1.2)
        if self._click_confirm_delete():
            time.sleep(2)
            had_error = self._has_error_toast()
            self._dismiss_toasts()
            return not had_error
        time.sleep(2.5)
        had_error = self._has_error_toast()
        self._dismiss_toasts()
        if not had_error:
            return True
        return False

    def _scroll_down(self):
        # Click in content area first so wheel events reach the right element
        self._page.mouse.click(200, 600)
        time.sleep(0.2)
        # Natural mouse wheel scroll — generates real scroll events for lazy loading
        for _ in range(3):
            self._page.mouse.wheel(0, 2000)
            time.sleep(0.3)
        time.sleep(3)
        # Also check for any "Show more" / "Load more" buttons
        try:
            btn = self._page.locator('button:has-text("Show more"), button:has-text("Load more"), button:has-text("View more"), a:has-text("Show more")').first
            if btn.is_visible(timeout=500):
                btn.click(timeout=1000)
                time.sleep(3)
        except: pass

    def _svg_count(self) -> int:
        return self._page.evaluate("document.querySelectorAll('svg[aria-label=\"More\"], button[aria-label=\"More\"], [aria-label=\"More\"]').length")

    def _delete_loop(self, label: str, max_deletes: int = 0, *, username: str | None = None) -> int:
        deleted = 0
        consecutive_fails = 0
        total_fails = 0
        scrolls_without_new_svg = 0
        scrolls_since_last_delete = 0
        while True:
            if max_deletes and deleted >= max_deletes:
                console.print(f"[dim]  hit limit of {max_deletes} {label}[/]")
                break
            ok = self._delete_next_item(username=username)
            if ok:
                deleted += 1
                consecutive_fails = 0
                total_fails = 0
                scrolls_without_new_svg = 0
                scrolls_since_last_delete = 0
                if deleted % 5 == 0:
                    svgs = self._svg_count()
                    console.print(f"[green]✓[/] deleted {deleted} {label}  [dim]({svgs} SVGs)[/]")
                continue
            consecutive_fails += 1
            total_fails += 1
            if total_fails > 500:
                console.print(f"[red]gave up after {total_fails} failures[/]")
                break
            if consecutive_fails >= 2:
                svgs_before = self._svg_count()
                self._scroll_down()
                svgs_after = self._svg_count()
                scrolls_since_last_delete += 1
                if scrolls_since_last_delete > 50:
                    console.print(f"[red]no deletions in {scrolls_since_last_delete} scrolls, giving up[/]")
                    break
                if svgs_after > svgs_before:
                    scrolls_without_new_svg = 0
                    console.print(f"[blue]↓[/] scrolled — {svgs_after} SVGs (was {svgs_before})")
                else:
                    scrolls_without_new_svg += 1
                    console.print(f"[yellow]↓[/] scrolled — no new SVGs ({scrolls_without_new_svg}/20)")
                    if scrolls_without_new_svg >= 20:
                        console.print(f"[red]reached end of {label}[/]")
                        break
                consecutive_fails = 0
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

        # Scroll the replies page to load more thread entries
        console.print("[dim]  scrolling replies page to load threads...[/]")
        for s in range(6):
            self._page.mouse.click(200, 600)
            time.sleep(0.2)
            for _ in range(3):
                self._page.mouse.wheel(0, 2000)
                time.sleep(0.3)
            time.sleep(2)
            # Check for load more buttons
            try:
                btn = self._page.locator('button:has-text("Show more"), button:has-text("Load more"), button:has-text("View more")').first
                if btn.is_visible(timeout=500):
                    btn.click(timeout=1000)
                    time.sleep(2)
            except: pass
        time.sleep(2)

        # Collect thread URLs from the replies page
        all_links = self._page.evaluate(r"""
            () => {
                const paths = new Set();
                for (const a of document.querySelectorAll('a[href]')) {
                    let h = a.getAttribute('href');
                    if (!h) continue;
                    if (h.startsWith('//')) h = 'https:' + h;
                    else if (h.startsWith('/')) h = window.location.origin + h;
                    try { var u = new URL(h); } catch(e) { continue; }
                    if (!/threads\.(com|net)$/i.test(u.hostname)) continue;
                    paths.add(u.pathname);
                }
                return Array.from(paths).slice(0, 30);
            }
        """)
        console.print(f"[dim]  page links (first 30): {all_links}[/]")

        thread_urls = self._page.evaluate(r"""
            () => {
                const urls = new Set();
                const base = window.location.origin;
                for (const a of document.querySelectorAll('a[href]')) {
                    let h = a.getAttribute('href');
                    if (!h) continue;
                    if (h.startsWith('//')) h = 'https:' + h;
                    else if (h.startsWith('/')) h = base + h;
                    else if (!h.startsWith('http')) continue;
                    try { var u = new URL(h); } catch(e) { continue; }
                    if (!/threads\.(com|net)$/i.test(u.hostname)) continue;
                    const p = u.pathname.replace(/\/+$/, '');
                    // Only keep actual thread URLs: /@username/post/POSTID
                    if (!/^\/@\w+\/post\/\w+$/.test(p)) continue;
                    urls.add(u.href);
                }
                return Array.from(urls);
            }
        """)
        console.print(f"[dim]  found {len(thread_urls)} thread-like links: {thread_urls[:5]}{'...' if len(thread_urls) > 5 else ''}[/]")
        console.print(f"[dim]  found {len(thread_urls)} threads with replies[/]")

        deleted = 0
        for idx, thread_url in enumerate(thread_urls):
            if max_deletes and deleted >= max_deletes:
                console.print(f"[dim]  hit limit of {max_deletes} replies[/]")
                break

            console.print(f"[dim]  ({idx+1}/{len(thread_urls)}) opening thread...[/]")
            try:
                self._page.goto(thread_url, wait_until="domcontentloaded", timeout=30000)
            except:
                pass
            time.sleep(3)
            self._dismiss_popups()
            if "login" in self._page.url.lower():
                console.print("[red]Session expired.[/]")
                break

            if self._delete_next_item(username=username):
                deleted += 1
                console.print(f"[green]✓[/] deleted reply {deleted}")
            else:
                console.print(f"[yellow]  no reply found on this thread[/]")

            # Go back to replies page
            try:
                self._page.goto(replies_url, wait_until="domcontentloaded", timeout=30000)
            except:
                pass
            time.sleep(2)

        return deleted

def run_browser_delete(*, include_replies=False, max_deletes=None, dry_run=False, yes=False, headed=False):
    session = config.load_session()
    if not session:
        raise RuntimeError("Not logged in. Run:  threads-cleaner browser-login")
    targets = "replies" if include_replies else "posts"
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
        if include_replies:
            total += deleter.delete_replies(max_deletes or 0)
        else:
            total += deleter.delete_posts(max_deletes or 0)
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
