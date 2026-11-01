"""Run one source's scan. Scrapy's reactor can only start once per process, so scans run
in their own process: `python -m openpath.scan <slug>`. Celery tasks launch that."""

import logging
import socket
import sys
import traceback

from . import __version__, db, fetch_rendered
from .config import Settings, load_settings
from .pipeline import ScanSession
from .spiders import (ApprenticeshipApiSpider, BoardApiSpider, JsonLdCrawlSpider, ProgrammePagesSpider, SpringpodSpider,
                      crawl_settings)

log = logging.getLogger("openpath.scan")
SPIDERS = {"greenhouse": BoardApiSpider, "lever": BoardApiSpider, "ashby": BoardApiSpider, "jsonld_crawl": JsonLdCrawlSpider,
           "gov_apprenticeships": ApprenticeshipApiSpider, "springpod": SpringpodSpider, "programme_pages": ProgrammePagesSpider}


def _run_scrapy(source: dict, session: ScanSession, settings: Settings) -> dict:
    from scrapy.crawler import CrawlerProcess

    outcome: dict = {"complete": False, "error": None}
    process = CrawlerProcess(settings=crawl_settings(settings.user_agent))
    extra = {"api_key": settings.apprenticeship_api_key} if source["adapter"] == "gov_apprenticeships" else {}
    process.crawl(SPIDERS[source["adapter"]], source=source, session=session, outcome=outcome, **extra)
    process.start()
    return outcome


def classify_outcome(outcome: dict, stats) -> tuple[str, str | None]:
    """A scan that yields nothing from a site that answered is suspicious, not a success."""
    if outcome.get("error"):
        return "failed", outcome["error"]
    if not outcome.get("complete"):
        return "failed", "No response was processed. The URL may be blocked by robots.txt."
    if stats["found"] == 0:
        return "partial", "The source responded but listed nothing readable."
    if outcome.get("truncated"):
        return "partial", "Stopped at the page limit."
    return "success", None


def run_scan(slug: str, settings: Settings | None = None) -> dict:
    settings = settings or load_settings()
    conn = db.connect(settings.database_url)
    source = db.get_source(conn, slug)
    if source is None:
        raise SystemExit(f"Unknown source: {slug}. Run: openpath sources sync")
    db.heartbeat(conn, f"scanner@{socket.gethostname()}", __version__, None, settings.ai_enabled)
    run_id = db.start_run(conn, source["id"])
    session = ScanSession(conn, source, settings)
    try:
        if source["adapter"] == "gov_apprenticeships" and not settings.apprenticeship_api_key:
            outcome = {"error": "FIND_APPRENTICESHIP_API_KEY is not set"}
        elif source["adapter"] == "futures_finder":
            outcome = fetch_rendered.crawl_finder(source, session, settings.user_agent)
        elif source["adapter"] == "rendered":
            outcome = fetch_rendered.crawl(source, session, settings.user_agent)
        else:
            outcome = _run_scrapy(source, session, settings)
        status, error = classify_outcome(outcome, session.stats)
        if status == "success" and session.stats["errors"]:
            status, error = "partial", f"{session.stats['errors']} postings failed. Last: {session.last_error}"
        # Partial and failed scans never count as evidence that a posting has gone.
        session.finish_monitoring(complete=status == "success")
        db.expire_past_deadlines(conn)
    except Exception as e:
        log.error("Scan of %s crashed\n%s", slug, traceback.format_exc())
        status, error = "failed", f"{type(e).__name__}: {e}"[:500]
    db.finish_run(conn, run_id, source, status, session.stats, error)
    conn.close()
    return {"source": slug, "status": status, "error": error, **session.stats}


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    result = run_scan(sys.argv[1])
    print(result)
    sys.exit(0 if result["status"] != "failed" else 1)
