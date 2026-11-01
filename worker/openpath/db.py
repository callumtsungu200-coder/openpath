"""All database writes. The worker talks to Postgres directly and bypasses RLS."""

import os
import re
from difflib import SequenceMatcher
from pathlib import Path

import psycopg
import yaml
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from .models import Opportunity

NEAR_DUPLICATE_SCORE = 0.96
MISSING_SCANS_BEFORE_REMOVAL = 2
BACKOFF_MAX_MINUTES = 24 * 60

UPSERT_COLUMNS = (
    "apply_url", "external_id", "fingerprint", "content_hash", "title", "company_name", "company_logo_url",
    "company_url", "company_description", "application_status",
    "category", "industry", "location", "region", "arrangement", "employment_type", "salary_min", "salary_max",
    "salary_period", "salary_text", "is_paid", "min_age", "max_age", "age_text", "deadline", "duration",
    "description", "responsibilities", "eligibility", "requirements", "programme_info", "extraction_method",
    "confidence", "posted_at",
)


def connect(database_url: str) -> psycopg.Connection:
    # No server-side prepared statements: they break behind Supabase's transaction pooler and PGlite.
    return psycopg.connect(database_url, row_factory=dict_row, autocommit=True, prepare_threshold=None)


def sync_sources(conn: psycopg.Connection, path: Path) -> int:
    entries = yaml.safe_load(path.read_text(encoding="utf-8"))
    for s in entries:
        needed = s.get("requires_env")
        missing = bool(needed and not os.environ.get(needed))
        conn.execute(
            """insert into sources (slug, name, adapter, url, config, company_name, company_url, logo_url,
                                    company_description, industry, scan_interval_minutes)
               values (%(slug)s, %(name)s, %(adapter)s, %(url)s, %(config)s, %(company_name)s, %(company_url)s,
                       %(logo_url)s, %(company_description)s, %(industry)s, %(interval)s)
               on conflict (slug) do update set name = excluded.name, adapter = excluded.adapter, url = excluded.url,
                 config = excluded.config, company_name = excluded.company_name, company_url = excluded.company_url,
                 logo_url = excluded.logo_url, company_description = excluded.company_description,
                 industry = excluded.industry, scan_interval_minutes = excluded.scan_interval_minutes""",
            {"slug": s["slug"], "name": s["name"], "adapter": s["adapter"], "url": s["url"],
             "config": Jsonb(s.get("config") or {}), "company_name": s.get("company_name"),
             "company_url": s.get("company_url"), "logo_url": s.get("logo_url"),
             "company_description": s.get("company_description"), "industry": s.get("industry"),
             "interval": s.get("scan_interval_minutes", 360)},
        )
        # A source that cannot run must not look monitored, on the admin page or the public stats.
        if needed:
            conn.execute(
                "update sources set enabled = %s, last_error = %s where slug = %s",
                (not missing, f"Paused until {needed} is set" if missing else None, s["slug"]),
            )
    return len(entries)


def get_source(conn, slug_or_id: str | int) -> dict | None:
    column = "id" if isinstance(slug_or_id, int) else "slug"
    return conn.execute(f"select * from sources where {column} = %s", (slug_or_id,)).fetchone()


def due_sources(conn) -> list[dict]:
    return conn.execute("select * from sources where enabled and next_scan_at <= now() order by next_scan_at").fetchall()


def claim_source(conn, source_id: int, interval_minutes: int) -> bool:
    """Push next_scan_at forward so overlapping dispatchers cannot queue the same scan twice."""
    row = conn.execute(
        """update sources set next_scan_at = now() + make_interval(mins => %s)
           where id = %s and enabled and next_scan_at <= now() returning id""",
        (interval_minutes, source_id),
    ).fetchone()
    return row is not None


def start_run(conn, source_id: int) -> int:
    return conn.execute("insert into scan_runs (source_id) values (%s) returning id", (source_id,)).fetchone()["id"]


def finish_run(conn, run_id: int, source: dict, status: str, stats: dict, error: str | None) -> None:
    failed = status == "failed"
    failures = source["consecutive_failures"] + 1 if failed else 0
    # Failing sites get exponentially less traffic rather than being retried on schedule.
    delay = min(source["scan_interval_minutes"] * (2 ** min(failures, 8)), BACKOFF_MAX_MINUTES) if failed else source["scan_interval_minutes"]
    conn.execute(
        """update scan_runs set status = %(status)s, finished_at = now(), error = %(error)s,
             pages_fetched = %(pages)s, items_found = %(found)s, items_outside_uk = %(outside)s,
             items_created = %(created)s, items_updated = %(updated)s, items_unchanged = %(unchanged)s,
             items_removed = %(removed)s, items_pending = %(pending)s, duplicates_found = %(duplicates)s,
             ai_calls = %(ai)s where id = %(id)s""",
        {"status": status, "error": error, "id": run_id, "pages": stats.get("pages", 0), "found": stats.get("found", 0),
         "outside": stats.get("outside", 0), "created": stats.get("created", 0), "updated": stats.get("updated", 0),
         "unchanged": stats.get("unchanged", 0), "removed": stats.get("removed", 0), "pending": stats.get("pending", 0),
         "duplicates": stats.get("duplicates", 0), "ai": stats.get("ai", 0)},
    )
    conn.execute(
        """update sources set last_scan_at = now(), last_status = %s, last_error = %s,
             consecutive_failures = %s, next_scan_at = now() + make_interval(mins => %s) where id = %s""",
        (status, error, failures, delay, source["id"]),
    )


def _record_event(conn, opportunity_id, kind: str, detail: str | None = None) -> None:
    conn.execute("insert into opportunity_events (opportunity_id, kind, detail) values (%s, %s, %s)",
                 (opportunity_id, kind, detail))


def _params(opp: Opportunity) -> dict:
    return {c: getattr(opp, c) for c in UPSERT_COLUMNS}


def upsert_opportunity(conn, source_id: int, opp: Opportunity) -> str:
    """Store a posting and return created, updated or unchanged."""
    existing = conn.execute(
        "select id, content_hash, status, verification, extraction_method from opportunities where source_url = %s",
        (opp.source_url,),
    ).fetchone()
    params = _params(opp) | {"source_id": source_id, "source_url": opp.source_url,
                             "verification": opp.verification, "provenance": Jsonb(opp.field_provenance)}

    if existing is None:
        columns = ", ".join(UPSERT_COLUMNS)
        values = ", ".join(f"%({c})s" for c in UPSERT_COLUMNS)
        row = conn.execute(
            f"""insert into opportunities (source_id, source_url, verification, field_provenance, last_verified_at, {columns})
                values (%(source_id)s, %(source_url)s, %(verification)s::verification_status, %(provenance)s,
                        case when %(verification)s::text = 'verified' then now() end, {values}) returning id""",
            params,
        ).fetchone()
        _record_event(conn, row["id"], "discovered")
        return "created"

    if existing["status"] in ("rejected", "duplicate"):
        conn.execute("update opportunities set last_seen_at = now() where id = %s", (existing["id"],))
        return "unchanged"

    # A posting seen again is live. Its verification stands unless its content changed.
    reappeared = existing["status"] in ("removed", "expired")
    if existing["content_hash"] == opp.content_hash and not reappeared:
        conn.execute(
            """update opportunities set last_seen_at = now(), missing_scans = 0,
                 last_verified_at = case when verification = 'verified' then now() else last_verified_at end
               where id = %s""",
            (existing["id"],),
        )
        return "unchanged"

    # Changed content is judged afresh, so an old approval does not carry over to new text.
    assignments = ", ".join(f"{c} = %({c})s" for c in UPSERT_COLUMNS)
    conn.execute(
        f"""update opportunities set {assignments}, field_provenance = %(provenance)s,
              verification = %(verification)s::verification_status,
              status = 'active', missing_scans = 0, last_seen_at = now(), updated_at = now(),
              last_verified_at = case when %(verification)s::text = 'verified' then now() else last_verified_at end
            where id = %(id)s""",
        params | {"id": existing["id"]},
    )
    _record_event(conn, existing["id"], "updated", "Listed again" if reappeared else "Source details changed")
    return "updated"


def detect_duplicates(conn, opp: Opportunity) -> int:
    """Exact matches across sources merge automatically. Near matches go to an admin."""
    me = conn.execute("select id, source_id, status from opportunities where source_url = %s", (opp.source_url,)).fetchone()
    if me is None or me["status"] != "active":
        return 0
    exact = conn.execute(
        """select id from opportunities where fingerprint = %s and id <> %s and status = 'active'
             and source_id <> %s order by discovered_at, id limit 1""",
        (opp.fingerprint, me["id"], me["source_id"]),
    ).fetchone()
    if exact:
        conn.execute("update opportunities set status = 'duplicate', duplicate_of = %s, updated_at = now() where id = %s",
                     (exact["id"], me["id"]))
        return 1
    found = 0
    peers = conn.execute(
        "select id, title, location from opportunities where company_name = %s and id <> %s and status = 'active'",
        (opp.company_name, me["id"]),
    ).fetchall()
    title = _dedupe_key(opp.title)
    for peer in peers:
        # Same role in another city is a separate opportunity, not a duplicate.
        if (peer["location"] or "") != (opp.location or ""):
            continue
        peer_title = _dedupe_key(peer["title"])
        score = SequenceMatcher(None, title, peer_title).ratio()
        # Extra words usually mean a different role ("Senior X", "X - iOS"), so only spelling-level
        # differences or the same words reordered are worth an administrator's time.
        if score >= NEAR_DUPLICATE_SCORE or sorted(title.split()) == sorted(peer_title.split()):
            cur = conn.execute(
                """insert into duplicate_candidates (opportunity_id, candidate_id, score)
                   select %(a)s, %(b)s, %(s)s where not exists (
                     select 1 from duplicate_candidates
                     where (opportunity_id, candidate_id) in ((%(a)s, %(b)s), (%(b)s, %(a)s)))""",
                {"a": me["id"], "b": peer["id"], "s": round(score, 3)},
            )
            found += cur.rowcount
    return found


def _dedupe_key(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", title.lower()).strip()


def mark_missing(conn, source_id: int, seen_urls: set[str]) -> int:
    """After a complete scan, postings the source no longer lists count a miss.
    Two consecutive misses are required so a transient glitch cannot remove anything."""
    rows = conn.execute("select id, source_url, missing_scans from opportunities where source_id = %s and status = 'active'",
                        (source_id,)).fetchall()
    removed = 0
    for row in rows:
        if row["source_url"] in seen_urls:
            continue
        misses = row["missing_scans"] + 1
        if misses >= MISSING_SCANS_BEFORE_REMOVAL:
            conn.execute("update opportunities set status = 'removed', missing_scans = %s, updated_at = now() where id = %s",
                         (misses, row["id"]))
            _record_event(conn, row["id"], "removed", "No longer listed by the source")
            removed += 1
        else:
            conn.execute("update opportunities set missing_scans = %s where id = %s", (misses, row["id"]))
    return removed


def expire_past_deadlines(conn) -> int:
    rows = conn.execute(
        """update opportunities set status = 'expired', updated_at = now()
           where status = 'active' and deadline < current_date returning id"""
    ).fetchall()
    for row in rows:
        _record_event(conn, row["id"], "expired", "Application deadline passed")
    return len(rows)


def heartbeat(conn, worker: str, version: str, redis_ok: bool | None, ai_enabled: bool) -> None:
    conn.execute(
        """insert into worker_heartbeats (worker, last_seen_at, version, redis_ok, ai_enabled)
           values (%s, now(), %s, %s, %s)
           on conflict (worker) do update set last_seen_at = now(), version = excluded.version,
             redis_ok = excluded.redis_ok, ai_enabled = excluded.ai_enabled""",
        (worker, version, redis_ok, ai_enabled),
    )


def log_ai(conn, url: str | None, model: str, purpose: str, status: str,
           input_tokens: int | None, output_tokens: int | None, error: str | None) -> None:
    conn.execute(
        """insert into ai_runs (opportunity_url, model, purpose, status, input_tokens, output_tokens, error)
           values (%s, %s, %s, %s, %s, %s, %s)""",
        (url, model, purpose, status, input_tokens, output_tokens, error),
    )
