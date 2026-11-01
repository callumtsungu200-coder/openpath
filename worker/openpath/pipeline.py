"""Processes postings from any fetcher: normalise, store, deduplicate, then monitor."""

import logging
from collections import Counter

from . import ai as ai_module
from . import db
from .config import Settings
from .models import RawPosting
from .normalise import normalise

log = logging.getLogger("openpath.pipeline")


class ScanSession:
    def __init__(self, conn, source: dict, settings: Settings, ai_client=None):
        self.conn = conn
        self.source = source
        self.settings = settings
        self.ai_client = ai_client
        self.stats: Counter = Counter()
        self.seen_urls: set[str] = set()
        self._current_url: str | None = None
        self.last_error: str | None = None

    def _ai(self, title: str, company: str, text: str):
        return ai_module.extract(self.settings, title, company, text, client=self.ai_client)

    def _on_ai(self, result) -> None:
        self.stats["ai"] += 1
        db.log_ai(self.conn, self._current_url, self.settings.ai_model, "extract", result.status,
                  result.input_tokens, result.output_tokens, result.error)

    def _ai_available(self) -> bool:
        if not (self.settings.ai_enabled or self.ai_client):
            return False
        return self.stats["ai"] < self.settings.ai_max_calls_per_scan

    def process(self, raw: RawPosting) -> None:
        self.stats["found"] += 1
        self._current_url = raw.source_url
        # Every listed posting counts as seen, so a posting that fails below is never marked missing.
        self.seen_urls.add(raw.source_url)
        try:
            self._store(raw)
        except Exception as e:  # one bad posting must not lose the rest of the scan
            log.exception("Could not process %s", raw.source_url)
            self.stats["errors"] += 1
            self.last_error = f"{raw.source_url}: {type(e).__name__}: {e}"[:500]

    def _store(self, raw: RawPosting) -> None:
        opp = normalise(raw, self.source, self.settings,
                        ai=self._ai if self._ai_available() else None, on_ai=self._on_ai)
        if opp is None:
            self.stats["outside"] += 1
            # Not ours to keep: if it was stored earlier, it now counts as no longer listed.
            self.seen_urls.discard(raw.source_url)
            return
        outcome = db.upsert_opportunity(self.conn, self.source["id"], opp)
        self.stats[outcome] += 1
        if opp.verification == "pending":
            self.stats["pending"] += 1
        self.stats["duplicates"] += db.detect_duplicates(self.conn, opp)

    def finish_monitoring(self, complete: bool) -> None:
        # Only a complete scan is evidence that something disappeared.
        if complete:
            self.stats["removed"] += db.mark_missing(self.conn, self.source["id"], self.seen_urls)
