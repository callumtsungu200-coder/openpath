"""Runs the Scrapy and Playwright crawlers for real against a throwaway local website."""

import json
import subprocess
import sys
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

HELPER = Path(__file__).with_name("crawl_helper.py")


def job_ld(title):
    return json.dumps({
        "@context": "https://schema.org", "@type": "JobPosting", "title": title,
        "hiringOrganization": {"@type": "Organization", "name": "Fixture Co"},
        "jobLocation": {"@type": "Place", "address": {"addressLocality": "Leeds", "addressCountry": "GB"}},
    })


@pytest.fixture
def site(tmp_path):
    (tmp_path / "robots.txt").write_text("User-agent: *\nDisallow: /jobs/private\n")
    (tmp_path / "careers.html").write_text(
        '<a href="/jobs/one.html">One</a><a href="/jobs/private.html">Private</a><a href="/about.html">About</a>')
    jobs = tmp_path / "jobs"
    jobs.mkdir()
    (jobs / "one.html").write_text(f'<script type="application/ld+json">{job_ld("Static Apprentice")}</script>')
    (jobs / "private.html").write_text(f'<script type="application/ld+json">{job_ld("Blocked By Robots")}</script>')
    (tmp_path / "about.html").write_text(f'<script type="application/ld+json">{job_ld("Not A Followed Link")}</script>')
    # A page with nothing in its HTML until JavaScript runs.
    (tmp_path / "js-careers.html").write_text(
        "<div id=root></div><script>"
        f"const s=document.createElement('script');s.type='application/ld+json';s.textContent={json.dumps(job_ld('Rendered Intern'))};"
        "document.head.appendChild(s);</script>")
    handler = partial(SimpleHTTPRequestHandler, directory=str(tmp_path))
    handler.log_message = lambda *a: None
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()


def run(adapter, url):
    result = subprocess.run([sys.executable, str(HELPER), adapter, url], capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stderr[-2000:]
    return json.loads(result.stdout.strip().splitlines()[-1])


def test_scrapy_crawl_follows_listing_links_and_obeys_robots(site):
    out = run("jsonld_crawl", f"{site}/careers.html")
    assert out["status"] == "success"
    assert [i["title"] for i in out["items"]] == ["Static Apprentice"]
    assert out["items"][0]["company"] == "Fixture Co" and out["items"][0]["location"] == "Leeds"


def test_scrapy_finding_nothing_is_not_success(site):
    assert run("jsonld_crawl", f"{site}/js-careers.html")["status"] == "partial"


def test_scrapy_robots_block_is_failure(site):
    assert run("jsonld_crawl", f"{site}/jobs/private.html")["status"] == "failed"


def test_playwright_reads_javascript_built_page(site):
    out = run("rendered", f"{site}/js-careers.html")
    assert out["status"] == "success"
    assert [i["title"] for i in out["items"]] == ["Rendered Intern"]


def test_playwright_obeys_robots(site):
    out = run("rendered", f"{site}/jobs/private.html")
    assert out["status"] == "failed" and "robots" in out["error"].lower()
