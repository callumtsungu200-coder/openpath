"""Scrapy spiders: one for public job board APIs, one for crawling career sites."""

import json
import re
from urllib.parse import urlparse

import scrapy

from . import adapters
from .fetch_rendered import looks_like_listing


class BoardApiSpider(scrapy.Spider):
    name = "board_api"

    def __init__(self, source: dict, session, outcome: dict, **kwargs):
        super().__init__(**kwargs)
        self.source = source
        self.session = session
        self.outcome = outcome

    async def start(self):
        url = adapters.api_url(self.source["adapter"], self.source["config"]["board"])
        yield scrapy.Request(url, callback=self.parse_board, errback=self.on_error, dont_filter=True)

    def parse_board(self, response):
        self.session.stats["pages"] += 1
        # From bytes: JSON is UTF-8, while response.text would guess and garble "£".
        payload = json.loads(response.body)
        company = self.source["company_name"] or self.source["name"]
        for raw in adapters.PARSERS[self.source["adapter"]](payload, company):
            self.session.process(raw)
        self.outcome["complete"] = True

    def on_error(self, failure):
        self.outcome["error"] = f"{failure.type.__name__}: {failure.getErrorMessage()}"[:500]


class ApprenticeshipApiSpider(scrapy.Spider):
    """GOV.UK Display Advert API v2. The limit is 150 requests per 5 minutes, and the crawl
    settings stay well under it. The scan only counts as complete once every page has arrived."""

    name = "gov_apprenticeships"

    def __init__(self, source: dict, session, outcome: dict, api_key: str, **kwargs):
        super().__init__(**kwargs)
        self.source = source
        self.session = session
        self.outcome = outcome
        self.api_key = api_key
        config = source.get("config") or {}
        self.base_url = config.get("base_url", adapters.APPRENTICESHIP_API).rstrip("/")
        self.page_size = min(int(config.get("page_size", 100)), 100)  # the API's maximum

    def _page(self, number: int) -> scrapy.Request:
        return scrapy.Request(
            f"{self.base_url}/vacancy?PageNumber={number}&PageSize={self.page_size}&IncludeDetails=true&Sort=AgeDesc",
            headers={"Ocp-Apim-Subscription-Key": self.api_key, "X-Version": "2", "Accept": "application/json"},
            callback=self.parse_page, errback=self.on_error, cb_kwargs={"number": number}, dont_filter=True,
        )

    async def start(self):
        yield self._page(1)

    def parse_page(self, response, number: int):
        self.session.stats["pages"] += 1
        payload = json.loads(response.body)
        for raw in adapters.parse_apprenticeships(payload):
            self.session.process(raw)
        if number < int(payload.get("totalPages") or 0):
            yield self._page(number + 1)
        else:
            self.outcome["complete"] = True

    def on_error(self, failure):
        status = failure.value.response.status if hasattr(failure.value, "response") else None
        self.outcome["error"] = {
            401: "The API rejected FIND_APPRENTICESHIP_API_KEY",
            429: "The API's rate limit was reached",
        }.get(status, f"{failure.type.__name__}: {failure.getErrorMessage()}")[:500]


class JsonLdCrawlSpider(scrapy.Spider):
    """Follows same-site links from a careers page and reads JobPosting markup."""

    name = "jsonld_crawl"

    def __init__(self, source: dict, session, outcome: dict, **kwargs):
        super().__init__(**kwargs)
        self.source = source
        self.session = session
        self.outcome = outcome
        config = source.get("config") or {}
        self.max_pages = int(config.get("max_pages", 200))
        self.link_pattern = re.compile(config["link_pattern"], re.I) if config.get("link_pattern") else None
        self.host = urlparse(source["url"]).netloc
        self.requested = 0

    async def start(self):
        yield scrapy.Request(self.source["url"], callback=self.parse_page, errback=self.on_error)

    def parse_page(self, response):
        self.session.stats["pages"] += 1
        if response.url == self.source["url"] or response.request.url == self.source["url"]:
            self.outcome["complete"] = True
        if not hasattr(response, "text"):
            return
        for raw in adapters.parse_jsonld_page(response.text, response.url, self.source["company_name"]):
            self.session.process(raw)
        for href in response.css("a::attr(href)").getall():
            url = response.urljoin(href).split("#")[0]
            if urlparse(url).netloc != self.host or not looks_like_listing(url, self.link_pattern):
                continue
            if self.requested >= self.max_pages:
                self.outcome["truncated"] = True
                return
            self.requested += 1
            yield scrapy.Request(url, callback=self.parse_page, errback=self.on_link_error)

    def on_error(self, failure):
        self.outcome["error"] = f"{failure.type.__name__}: {failure.getErrorMessage()}"[:500]

    def on_link_error(self, failure):
        self.session.stats["link_errors"] += 1


def crawl_settings(user_agent: str) -> dict:
    return {
        "USER_AGENT": user_agent,
        "ROBOTSTXT_OBEY": True,
        "AUTOTHROTTLE_ENABLED": True,
        "AUTOTHROTTLE_START_DELAY": 1.0,
        "DOWNLOAD_DELAY": 1.0,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "RETRY_TIMES": 2,
        "DOWNLOAD_TIMEOUT": 45,
        "LOG_LEVEL": "WARNING",
        "LOG_INSTALL_ROOT_HANDLER": False,
        "TELNETCONSOLE_ENABLED": False,
        "EXTENSIONS": {"scrapy.extensions.remote_control.RemoteControl": None},
        "HTTPCACHE_ENABLED": False,
    }
