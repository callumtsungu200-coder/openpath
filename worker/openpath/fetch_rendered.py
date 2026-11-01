"""Playwright fetcher for career sites that build their listings with JavaScript."""

import re
import time
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

from . import adapters

LISTING_HINT = re.compile(r"job|career|vacanc|opportunit|apprentice|intern|graduate|position|role|early-", re.I)
SKIP = re.compile(r"\.(pdf|jpe?g|png|gif|svg|zip|docx?)$|/(login|signin|privacy|cookies?|terms)\b", re.I)
REQUEST_DELAY_SECONDS = 1.5


def looks_like_listing(url: str, pattern: re.Pattern | None = None) -> bool:
    if SKIP.search(urlparse(url).path):
        return False
    return bool((pattern or LISTING_HINT).search(url))


def _robots(url: str, user_agent: str):
    parsed = urlparse(url)
    robots = RobotFileParser(f"{parsed.scheme}://{parsed.netloc}/robots.txt")
    robots.read()
    return lambda target: robots.can_fetch(user_agent, target)


def crawl_finder(source: dict, session, user_agent: str) -> dict:
    """Futures For All's Work Experience Finder only exists once rendered, and its cards open
    their pages by click, so each is visited the way a person would."""
    from playwright.sync_api import Error as PlaywrightError
    from playwright.sync_api import sync_playwright

    from .work_experience import parse_finder_detail

    start = source["url"]
    outcome: dict = {"complete": False, "error": None}
    if not _robots(start, user_agent)(start):
        outcome["error"] = "Blocked by robots.txt"
        return outcome

    def open_page(page, number: int) -> None:
        page.goto(start, wait_until="domcontentloaded", timeout=60000)
        page.get_by_text("View Opportunity", exact=True).first.wait_for(timeout=30000)
        if number > 1:
            first = page.get_by_text("View Opportunity", exact=True).first.locator("xpath=ancestor::*[contains(@class,'flip-card')][1]").inner_text()
            page.get_by_role("button", name=str(number), exact=True).click(timeout=8000)
            page.wait_for_function("t => { const c=document.querySelector('.flip-card'); return c && c.innerText !== t; }", arg=first, timeout=20000)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_context(user_agent=user_agent, viewport={"width": 1280, "height": 1000}).new_page()
        try:
            open_page(page, 1)
            match = re.search(r"(\d+) results", page.inner_text("body"))
            expected = int(match.group(1)) if match else None
            seen: set[str] = set()
            number = 1
            failed = False
            while True:
                count = page.get_by_text("View Opportunity", exact=True).count()
                for index in range(count):
                    for attempt in (1, 2):
                        try:
                            if index or attempt > 1:
                                open_page(page, number)
                            page.get_by_text("View Opportunity", exact=True).nth(index).click()
                            page.wait_for_url("**/opportunity-detail/**", timeout=20000)
                            # The page fills in stages: the heading says "Loading opportunity..." at first,
                            # and the description arrives after the fields above it.
                            page.wait_for_function("""() => { const h=document.querySelector('h1'); const b=document.body.innerText;
                                return h && h.innerText.trim() && !/^loading/i.test(h.innerText.trim()) && b.includes('Application deadline') || b.includes('calendar_month'); }""", timeout=25000)
                            page.wait_for_timeout(1500)
                            session.stats["pages"] += 1
                            if page.url not in seen:
                                seen.add(page.url)
                                raw = parse_finder_detail(page.locator("h1").first.inner_text().strip(), page.inner_text("body"), page.url)
                                session.process(raw) if raw else session.skip()
                            break
                        except PlaywrightError:
                            if attempt == 2:
                                failed = True
                                session.stats["link_errors"] += 1
                    time.sleep(REQUEST_DELAY_SECONDS)
                number += 1
                try:
                    open_page(page, number)
                except PlaywrightError:
                    break
            # Fewer listings than the site says means the walk missed some, so it proves nothing.
            outcome["complete"] = True
            if failed or (expected is not None and len(seen) < expected):
                outcome["truncated"] = True
        except PlaywrightError as e:
            outcome["error"] = f"{type(e).__name__}: {e}"[:500]
        finally:
            browser.close()
    return outcome


def crawl(source: dict, session, user_agent: str) -> dict:
    """Render the listing page and linked pages, feeding any JobPosting data to the session."""
    from playwright.sync_api import Error as PlaywrightError
    from playwright.sync_api import sync_playwright

    config = source.get("config") or {}
    max_pages = int(config.get("max_pages", 60))
    pattern = re.compile(config["link_pattern"], re.I) if config.get("link_pattern") else None
    start = source["url"]
    host = urlparse(start).netloc
    allowed = _robots(start, user_agent)
    outcome: dict = {"complete": False, "error": None}
    if not allowed(start):
        outcome["error"] = "Blocked by robots.txt"
        return outcome

    queue, visited = [start], set()
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_context(user_agent=user_agent).new_page()
        try:
            while queue and len(visited) < max_pages:
                url = queue.pop(0)
                if url in visited or not allowed(url):
                    continue
                visited.add(url)
                try:
                    page.goto(url, wait_until="networkidle", timeout=45000)
                except PlaywrightError as e:
                    if url == start:
                        outcome["error"] = f"{type(e).__name__}: {e}"[:500]
                        return outcome
                    session.stats["link_errors"] += 1
                    continue
                session.stats["pages"] += 1
                if url == start:
                    outcome["complete"] = True
                for raw in adapters.parse_jsonld_page(page.content(), page.url, source["company_name"]):
                    session.process(raw)
                for href in page.eval_on_selector_all("a[href]", "els => els.map(e => e.getAttribute('href'))"):
                    target = urljoin(page.url, href).split("#")[0]
                    if urlparse(target).netloc == host and target not in visited and looks_like_listing(target, pattern):
                        queue.append(target)
                time.sleep(REQUEST_DELAY_SECONDS)
        finally:
            browser.close()
    if queue:
        outcome["truncated"] = True
    return outcome
