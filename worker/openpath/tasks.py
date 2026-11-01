"""Celery tasks. Redis is the broker, beat is the scheduler, and each scan gets its own process."""

import socket
import subprocess
import sys

import httpx
import redis
from celery import Celery
from celery.schedules import crontab

from . import __version__, db
from .config import load_settings

settings = load_settings()
app = Celery("openpath", broker=settings.redis_url)
app.conf.update(
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_time_limit=60 * 30,
    task_soft_time_limit=60 * 28,
    timezone="Europe/London",
    task_ignore_result=True,
    beat_schedule={
        "dispatch-due-sources": {"task": "openpath.tasks.dispatch_due_sources", "schedule": 300.0},
        "heartbeat": {"task": "openpath.tasks.heartbeat", "schedule": 60.0},
        "recheck-links": {"task": "openpath.tasks.recheck_stale_links", "schedule": 3600.0},
        "expire-deadlines": {"task": "openpath.tasks.expire_deadlines", "schedule": crontab(hour=0, minute=10)},
    },
)


def _conn():
    return db.connect(settings.database_url)


@app.task
def dispatch_due_sources() -> int:
    with _conn() as conn:
        queued = 0
        for source in db.due_sources(conn):
            if db.claim_source(conn, source["id"], source["scan_interval_minutes"]):
                scan_source.delay(source["slug"])
                queued += 1
        return queued


@app.task
def scan_source(slug: str) -> None:
    subprocess.run([sys.executable, "-m", "openpath.scan", slug], check=False, timeout=60 * 27)


@app.task
def expire_deadlines() -> int:
    with _conn() as conn:
        return db.expire_past_deadlines(conn)


@app.task
def recheck_stale_links(limit: int = 50) -> int:
    """Crawled postings are only confirmed if a link is followed again, so check the stalest."""
    with _conn() as conn:
        rows = conn.execute(
            """select o.id, o.source_url from opportunities o join sources s on s.id = o.source_id
               where o.status = 'active' and s.adapter in ('jsonld_crawl', 'rendered')
                 and coalesce(o.last_verified_at, o.discovered_at) < now() - interval '24 hours'
               order by coalesce(o.last_verified_at, o.discovered_at) limit %s""",
            (limit,),
        ).fetchall()
        checked = 0
        with httpx.Client(follow_redirects=True, timeout=20, headers={"User-Agent": settings.user_agent}) as client:
            for row in rows:
                try:
                    code = client.get(row["source_url"]).status_code
                except httpx.HTTPError:
                    continue
                if code in (404, 410):
                    conn.execute("update opportunities set status = 'removed', updated_at = now() where id = %s", (row["id"],))
                    conn.execute("insert into opportunity_events (opportunity_id, kind, detail) values (%s, 'removed', %s)",
                                 (row["id"], f"Source link returned {code}"))
                elif code < 400:
                    conn.execute("update opportunities set last_verified_at = now(), last_seen_at = now() where id = %s", (row["id"],))
                checked += 1
        return checked


@app.task
def heartbeat() -> None:
    try:
        redis_ok = bool(redis.Redis.from_url(settings.redis_url, socket_timeout=3).ping())
    except redis.RedisError:
        redis_ok = False
    with _conn() as conn:
        db.heartbeat(conn, f"celery@{socket.gethostname()}", __version__, redis_ok, settings.ai_enabled)
