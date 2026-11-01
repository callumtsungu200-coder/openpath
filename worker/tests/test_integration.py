"""Runs against a real database: set OPENPATH_TEST_DATABASE_URL (the local server works)."""

import os
import uuid
from datetime import date, timedelta

import pytest

from openpath import db
from openpath.config import Settings
from openpath.models import RawPosting
from openpath.normalise import normalise
from openpath.pipeline import ScanSession

URL = os.environ.get("OPENPATH_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not URL, reason="OPENPATH_TEST_DATABASE_URL is not set")
SETTINGS = Settings(URL or "", "", None, "claude-opus-5-5", 5, 0.6, 0.6, "test")
BODY = "<p>" + "A real description of this opportunity. " * 10 + "</p>"


@pytest.fixture
def conn():
    connection = db.connect(URL)
    yield connection
    connection.execute("delete from sources where slug like 'itest-%'")
    connection.close()


def make_source(conn, company):
    slug = f"itest-{uuid.uuid4().hex[:8]}"
    return conn.execute(
        """insert into sources (slug, name, adapter, url, company_name) values (%s, %s, 'greenhouse', 'https://x.test', %s)
           returning *""",
        (slug, slug, company),
    ).fetchone()


def posting(company, url, title="Engineer", body=BODY, location="London", **kw):
    return RawPosting(source_url=url, title=title, company_name=company, location=location, description_html=body, **kw)


def scan(conn, source, postings):
    session = ScanSession(conn, source, SETTINGS)
    for raw in postings:
        session.process(raw)
    session.finish_monitoring(complete=True)
    return session.stats


def row(conn, url):
    return conn.execute("select * from opportunities where source_url = %s", (url,)).fetchone()


def test_lifecycle_new_unchanged_changed_missing_removed_relisted(conn):
    company = f"Co {uuid.uuid4().hex}"
    source = make_source(conn, company)
    url = f"https://x.test/{uuid.uuid4().hex}"

    assert scan(conn, source, [posting(company, url)])["created"] == 1
    first = row(conn, url)
    assert first["status"] == "active" and first["verification"] == "verified" and first["last_verified_at"]

    assert scan(conn, source, [posting(company, url)])["unchanged"] == 1
    assert scan(conn, source, [posting(company, url, title="Lead Engineer")])["updated"] == 1
    assert row(conn, url)["title"] == "Lead Engineer"

    # One missed scan is not enough, because a source can glitch.
    assert scan(conn, source, [])["removed"] == 0
    assert row(conn, url)["status"] == "active"
    assert scan(conn, source, [])["removed"] == 1
    assert row(conn, url)["status"] == "removed"

    assert scan(conn, source, [posting(company, url, title="Lead Engineer")])["updated"] == 1
    assert row(conn, url)["status"] == "active"


def test_incomplete_scan_never_removes(conn):
    company = f"Co {uuid.uuid4().hex}"
    source = make_source(conn, company)
    url = f"https://x.test/{uuid.uuid4().hex}"
    scan(conn, source, [posting(company, url)])
    for _ in range(3):
        ScanSession(conn, source, SETTINGS).finish_monitoring(complete=False)
    assert row(conn, url)["status"] == "active" and row(conn, url)["missing_scans"] == 0


def test_exact_duplicate_across_sources_merges(conn):
    company = f"Co {uuid.uuid4().hex}"
    a, b = make_source(conn, company), make_source(conn, company)
    url_a, url_b = f"https://a.test/{uuid.uuid4().hex}", f"https://b.test/{uuid.uuid4().hex}"
    scan(conn, a, [posting(company, url_a)])
    assert scan(conn, b, [posting(company, url_b)])["duplicates"] == 1
    assert row(conn, url_b)["status"] == "duplicate" and row(conn, url_b)["duplicate_of"] == row(conn, url_a)["id"]
    assert row(conn, url_a)["status"] == "active"


def test_near_duplicate_goes_to_review_and_other_city_does_not(conn):
    company = f"Co {uuid.uuid4().hex}"
    source = make_source(conn, company)
    base = f"https://x.test/{uuid.uuid4().hex}"
    scan(conn, source, [posting(company, f"{base}/1", title="Graduate Software Engineer")])
    stats = scan(conn, source, [
        posting(company, f"{base}/1", title="Graduate Software Engineer"),
        posting(company, f"{base}/2", title="Graduate Software Engineers"),
        posting(company, f"{base}/3", title="Graduate Software Engineer", location="Leeds"),
    ])
    assert stats["duplicates"] == 1
    assert row(conn, f"{base}/2")["status"] == "active"
    assert row(conn, f"{base}/3")["status"] == "active"


def test_different_roles_are_not_flagged_as_duplicates(conn):
    company = f"Co {uuid.uuid4().hex}"
    source = make_source(conn, company)
    base = f"https://x.test/{uuid.uuid4().hex}"
    stats = scan(conn, source, [
        posting(company, f"{base}/1", title="Backend Software Engineer"),
        posting(company, f"{base}/2", title="Senior Backend Software Engineer"),
        posting(company, f"{base}/3", title="Backend Software Engineer - iOS"),
    ])
    assert stats["duplicates"] == 0


def test_posting_that_moves_abroad_is_retired(conn):
    company = f"Co {uuid.uuid4().hex}"
    source = make_source(conn, company)
    url = f"https://x.test/{uuid.uuid4().hex}"
    scan(conn, source, [posting(company, url)])
    moved = posting(company, url, location="Berlin")
    scan(conn, source, [moved])
    scan(conn, source, [moved])
    assert row(conn, url)["status"] == "removed"


def test_past_deadline_expires(conn):
    company = f"Co {uuid.uuid4().hex}"
    source = make_source(conn, company)
    url = f"https://x.test/{uuid.uuid4().hex}"
    scan(conn, source, [posting(company, url, deadline=date.today() - timedelta(days=1))])
    assert db.expire_past_deadlines(conn) >= 1
    assert row(conn, url)["status"] == "expired"


def test_uncertain_posting_is_pending_and_hidden_from_public(conn):
    company = f"Co {uuid.uuid4().hex}"
    source = make_source(conn, company)
    url = f"https://x.test/{uuid.uuid4().hex}"
    raw = posting(company, url, body=None, origin="rules")
    assert normalise(raw, {}, SETTINGS).verification == "pending"
    scan(conn, source, [raw])
    assert row(conn, url)["verification"] == "pending"
    with conn.transaction():
        conn.execute("set local role anon")
        public = conn.execute("select count(*) as n from opportunities where source_url = %s", (url,)).fetchone()
        result = conn.execute("select search_opportunities(q => %s) as r", (company,)).fetchone()["r"]
    assert public["n"] == 0 and result["total"] == 0


def test_anon_cannot_read_internal_tables_or_admin_functions(conn):
    import psycopg
    for statement in ("select * from sources", "select * from scan_runs", "select admin_overview()"):
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            with conn.transaction():
                conn.execute("set local role anon")
                conn.execute(statement)


def test_failed_scan_backs_off(conn):
    source = make_source(conn, "Co")
    run = db.start_run(conn, source["id"])
    db.finish_run(conn, run, source, "failed", {}, "boom")
    after = db.get_source(conn, source["slug"])
    assert after["consecutive_failures"] == 1 and after["last_status"] == "failed" and after["last_error"] == "boom"
    wait = conn.execute("select extract(epoch from next_scan_at - now()) / 60 as m from sources where id = %s", (source["id"],)).fetchone()["m"]
    assert float(wait) > source["scan_interval_minutes"]
