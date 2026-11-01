"""Runs one crawler in its own process, because Scrapy's reactor cannot restart. Prints JSON."""

import json
import sys
from collections import Counter

from openpath import fetch_rendered
from openpath.scan import classify_outcome
from openpath.spiders import ApprenticeshipApiSpider, JsonLdCrawlSpider, crawl_settings


class Collector:
    def __init__(self):
        self.stats = Counter()
        self.items = []

    def process(self, raw):
        self.stats["found"] += 1
        self.items.append({"title": raw.title, "company": raw.company_name, "location": raw.location, "url": raw.source_url})


def main():
    adapter, url = sys.argv[1], sys.argv[2]
    config = json.loads(sys.argv[3]) if len(sys.argv) > 3 else {}
    source = {"adapter": adapter, "url": url, "company_name": "Fallback Ltd", "config": config}
    session = Collector()
    if adapter == "rendered":
        outcome = fetch_rendered.crawl(source, session, "OpenPathBot/test")
    else:
        from scrapy.crawler import CrawlerProcess
        outcome = {"complete": False, "error": None}
        settings = crawl_settings("OpenPathBot/test") | {"DOWNLOAD_DELAY": 0, "AUTOTHROTTLE_ENABLED": False}
        process = CrawlerProcess(settings=settings)
        if adapter == "gov_apprenticeships":
            process.crawl(ApprenticeshipApiSpider, source=source, session=session, outcome=outcome, api_key=config["key"])
        else:
            process.crawl(JsonLdCrawlSpider, source=source, session=session, outcome=outcome)
        process.start()
    status, error = classify_outcome(outcome, session.stats)
    print(json.dumps({"status": status, "error": error, "items": session.items, "pages": session.stats["pages"]}))


if __name__ == "__main__":
    main()
