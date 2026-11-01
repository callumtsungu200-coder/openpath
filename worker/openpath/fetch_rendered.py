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
