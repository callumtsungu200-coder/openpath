"""Parsers for work experience sources. Pure functions, so tests need no network.

Facts come only from the page being read. Curated source entries supply just what a page
cannot state reliably: which organisation runs it, and where it is based.
"""

import json
import re
from datetime import date

from bs4 import BeautifulSoup
from dateutil import parser as date_parser

from . import classify, sections
from .models import RawPosting
from .normalise import deadlines_from

SUMMARY_LIMIT = 900
SECTOR_RULES = (
    (r"financ|bank|account", "Finance & Banking"),
    (r"digital|comput|technolog|software|\bit\b|data", "Technology"),
    (r"health|medic|care\b|dental|pharma|nurs", "Healthcare"),
    (r"engineer|manufactur|aerospace", "Engineering"),
    (r"\blaw\b|legal", "Law"),
    (r"creative|media|design|film|theatre|journalis|marketing", "Media & Design"),
    (r"educat|teach", "Education"),
    (r"construct|built|property|architect", "Construction"),
    (r"hospitality|catering", "Catering and hospitality"),
    (r"energy|utilit", "Energy"),
    (r"business|manag|consult", "Business"),
)
CLOSED = re.compile(
    r"applications? (?:for [^.\n]{0,60} )?(?:are|is|have) (?:now |currently )?(?:been )?closed|closed for applications|"
    r"applications? closed\b|deadline for (?:submissions|applications) was|applications? (?:will|are due to) re-?open|"
    r"application process [^.\n]{0,40}has now closed",
    re.I,
)
FUTURE_OPENING = re.compile(r"applications? open on\b", re.I)
OPEN = re.compile(r"applications? (?:for [^.\n]{0,60} )?(?:are|is) (?:now |currently )?open\b|now accepting applications|apply now\b", re.I)
ELIGIBILITY = re.compile(r"\b(year 1[0-3]|years? 1[0-3]|s[456]\b|aged? \d\d|\d\d\s?(?:-|–|to)\s?\d\d[- ]years?|sixth[- ]form|state school|free school meals)\b", re.I)
DETAIL = re.compile(r"\b(deadline|applications? (?:open|close|will)|closes?|paid|stipend|bursary|voucher|virtual|online|in[- ]person|\d+[- ]days?|\d+[- ]weeks?|free of charge|free\b)", re.I)
NOISE = re.compile(r"cookie|privacy|javascript|newsletter|sign up to|©|free school meals eligibility check", re.I)


def sector_label(name: str | None) -> str | None:
    if not name:
        return None
    for pattern, label in SECTOR_RULES:
        if re.search(pattern, name, re.I):
            return label
    return name


def _sitemap_locs(xml: str) -> list[str]:
    # Springpod formats its tags across lines: "<loc\n >https://...</loc\n >".
    return [u.strip() for u in re.findall(r"<loc\s*>\s*(.*?)\s*</loc\s*>", xml, re.S)]


def _next_data(html: str) -> dict | None:
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
    try:
        return json.loads(m.group(1))["props"]["pageProps"] if m else None
    except (ValueError, KeyError):
        return None


def _date(value) -> date | None:
    try:
        return date_parser.parse(value).date() if value else None
    except (ValueError, OverflowError):
        return None


def _partner_name(item: dict) -> tuple[str | None, dict]:
    partner = item.get("partner") or {}
    org = partner.get("organisation") or partner.get("institution") or {}
    return org.get("name"), org


def parse_springpod_programme(html: str, url: str) -> RawPosting | None:
    """A virtual programme, or None if it has no live cohort, so people are not sent to dead ones."""
    props = _next_data(html)
    item = (props or {}).get("item")
    if not item or item.get("includeInSearchEngine") is False:
        return None
    title = item.get("title") or ""
    name, org = _partner_name(item)
    if not title or not name or re.search(r"\bUS only\b", title, re.I):
        return None
    cohorts = (item.get("detail") or {}).get("cohortDetails") or []
    live = [c for c in cohorts if c.get("status") == "LIVE"]
    if not live:
        return None
    ends = [d for d in (_date(c.get("endDate")) for c in live) if d]
    content = item.get("content") or {}
    facts = [f for f in (content.get("facts") or []) if isinstance(f, str)]
    age = next((re.search(r"aged? (\d\d)\+", f) for f in facts if re.search(r"aged? \d\d\+", f)), None)
    range_start = (item.get("ageRange") or {}).get("ageStart")
    overview = (content.get("overview") or {}).get("value") or ""
    summary = re.sub(r"^Overview\s+", "", " ".join(overview.split()))
    logo = (org.get("logo") or {}).get("url") or (item.get("logo") or {}).get("url")
    return RawPosting(
        source_url=url,
        external_id=item.get("internalId"),
        title=title,
        company_name=name,
        location="Online",
        region="UK wide",
        workplace="remote",
        employment_type="Virtual programme",
        description_html=f"<p>{(content.get('intro') or summary[:SUMMARY_LIMIT])}</p>" if (content.get("intro") or summary) else None,
        salary_text="Free to join",
        is_paid=False,
        deadline=max(ends) if ends else None,
        category="work_experience",
        industry=sector_label((item.get("jobSector") or {}).get("name")),
        min_age=int(age.group(1)) if age else range_start,
        age_note="Stated by the source",
        logo_url=logo,
        company_url=org.get("externalProfileUrl"),
        programme_info=[f for f in facts if "aged" not in f],
        application_status="open",
    )


def parse_springpod_opportunity(html: str, url: str) -> RawPosting | None:
    """In-person work experience from the public board. Other types are out of scope here.
    Springpod shows the rest behind a free account, so applicants are sent to its page."""
    props = _next_data(html)
    item = (props or {}).get("item")
    if not item or not re.search(r"work experience", (item.get("type") or {}).get("name") or "", re.I):
        return None
    name, org = _partner_name(item)
    if not item.get("title") or not name:
        return None
    place = ((item.get("city") or {}).get("name") or "").title() or None
    _, region = classify.uk_region(place)
    return RawPosting(
        source_url=url,
        external_id=item.get("internalId"),
        title=item["title"],
        company_name=name,
        location=place or "UK",
        region=region or "UK wide",
        workplace={"IN_PERSON": "in_person", "HYBRID": "hybrid", "REMOTE": "remote"}.get(item.get("format")),
        category="work_experience",
        logo_url=(org.get("logo") or {}).get("url"),
        company_url=org.get("externalProfileUrl"),
    )


FINDER_RULE = "Futures For All's programme is for 14 to 19-year-olds in state schools and colleges"
FINDER_SECTION_END = {"library_books", "business", "help", "What other students thought"}


def parse_finder_detail(title: str, body: str, url: str, today: date | None = None) -> RawPosting | None:
    """Text of a Work Experience Finder detail page, where each value is the line after an
    icon's name: "map" then "Remote", "cake" then "14-19"."""
    lines = [line.strip() for line in body.splitlines() if line.strip()]
    if not title or title.lower().startswith("loading") or title not in lines:
        return None
    lines = lines[lines.index(title) + 1:]

    def after(marker: str) -> str | None:
        return lines[lines.index(marker) + 1] if marker in lines and lines.index(marker) + 1 < len(lines) else None

    org = re.fullmatch(r"with (.+)", lines[0]) if lines else None
    deadline = next((m for m in (re.fullmatch(r"Application deadline:\s*(\d{1,2} \w+ \d{4})", l) for l in lines) if m), None)
    where, dates, hours, sector = after("map"), after("calendar_month"), after("access_time"), after("domain")
    ages = re.fullmatch(r"(\d{2})\s*-\s*(\d{2})", after("cake") or "")
    remote = bool(where and re.fullmatch(r"remote(?: opportunity)?", where, re.I))
    _, region = classify.uk_region(where) if where and not remote else (None, None)
    summary = []
    if "domain" in lines:
        for line in lines[lines.index("domain") + 2:]:
            if line in FINDER_SECTION_END or sum(map(len, summary)) > SUMMARY_LIMIT:
                break
            summary.append(re.sub(r"[^\w\s,.;:'’£&()/!?-]", "", line).strip())
    return RawPosting(
        source_url=url,
        external_id=url.rsplit("/", 1)[-1],
        title=title,
        company_name=org.group(1).strip() if org else "Futures For All",
        location="Online" if remote else (where or "See listing"),
        region="UK wide" if remote else (region or classify.region_from_postcode(where) or "UK wide"),
        workplace="remote" if remote else "in_person" if where else None,
        employment_type="Work experience placement",
        description_html="".join(f"<p>{line}</p>" for line in summary if line) or None,
        salary_text="Free to take part",
        is_paid=False,
        deadline=_date(deadline.group(1)) if deadline else None,
        duration=(re.search(r"\((\d+ \w+)\)", dates or "") or [None, None])[1],
        category="work_experience",
        industry=sector_label(sector.split(", ")[0]) if sector else None,
        min_age=int(ages.group(1)) if ages else None,
        max_age=int(ages.group(2)) if ages else None,
        age_note="Stated by the source",
        eligibility=[FINDER_RULE],
        programme_info=[f for f in (f"Dates: {dates}" if dates else None, f"Hours: {hours}" if hours else None) if f],
        application_status="open",
    )


PAGE_AGE_RANGE = re.compile(r"\b(?:aged?|are|from)\s*(\d{2})\s*(?:-|–|to)\s*(\d{2})\b|\b(\d{2})\s*(?:-|–|to)\s*(\d{2})[- ]year", re.I)
PAGE_AGE_MIN = re.compile(r"\baged?\s*(\d{2})\s*(?:\+|(?:and|or) (?:older|over|above))", re.I)


def _page_ages(eligibility: list[str]) -> tuple[int | None, int | None, str | None]:
    """Eligibility sentences only, and only plausible school and college ages, so
    "14 to 19 years old" counts while a statistic elsewhere on the page does not."""
    for sentence in eligibility:
        if classify.AGE_NOT_ELIGIBILITY.search(sentence):
            continue
        m = PAGE_AGE_RANGE.search(sentence)
        if m:
            low, high = (int(g) for g in m.groups() if g)
            if 11 <= low < high <= 25:
                return low, high, sentence
        m = PAGE_AGE_MIN.search(sentence)
        if m and 11 <= int(m.group(1)) <= 25:
            return int(m.group(1)), None, sentence
    return None, None, None


def _useful_sentences(text: str, title: str) -> tuple[list[str], list[str]]:
    eligibility, details = [], []
    for raw in re.split(r"(?<=[.!?])\s+|\n", text):
        sentence = raw.strip()
        # Under-length lines are headings and menu items, not statements.
        if not 30 <= len(sentence) <= 240 or NOISE.search(sentence) or " | " in sentence or sentence.lower() == title.lower():
            continue
        if ELIGIBILITY.search(sentence):
            if sentence not in eligibility:
                eligibility.append(sentence)
        elif len(sentence) >= 45 and DETAIL.search(sentence) and sentence not in details:
            details.append(sentence)
    return eligibility[:5], details[:5]


def parse_programme_page(html: str, page: dict, url: str, today: date | None = None) -> RawPosting:
    """An official programme page. Only short excerpts are kept: the page itself is the
    authority, and every listing sends the reader to it."""
    today = today or date.today()
    soup = BeautifulSoup(html, "html.parser")
    meta = soup.find("meta", attrs={"name": "description"}) or soup.find("meta", property="og:description")
    summary = " ".join((meta.get("content") or "").split()) if meta else ""
    if len(summary) < 60:  # some sites fill this tag with a label such as "Open-access"
        summary = ""
    for tag in soup(["script", "style", "noscript", "nav", "footer", "header", "form"]):
        tag.decompose()
    text = re.sub(r"\s*\n\s*", "\n", soup.get_text("\n"))
    # A recurring page often still shows last round's date: that is a closed round, not an expiry.
    # A later round on the same page outranks it.
    deadlines = deadlines_from(text, today)
    upcoming = sorted(d for d in deadlines if d >= today)
    deadline = upcoming[0] if upcoming else None
    if CLOSED.search(text) and not upcoming:
        status = "closed"
    elif deadlines and not upcoming:
        status = "closed"
    elif FUTURE_OPENING.search(text) and upcoming:
        status = None  # rounds are listed, but which is open today is for the page to say
    else:
        status = "open" if OPEN.search(text) or upcoming else None
    eligibility, details = _useful_sentences(text, page["title"])
    min_age, max_age, age_note = _page_ages(eligibility)
    if not summary:
        summary = next((s for s in (*details, *eligibility) if len(s) > 60), "")
    return RawPosting(
        source_url=url,
        title=page["title"],
        company_name=page["company"],
        location=page.get("location", "Online" if page.get("arrangement") == "remote" else None),
        region=page.get("region", "UK wide"),
        workplace=page.get("arrangement"),
        employment_type=page.get("kind"),
        description_html=f"<p>{summary[:SUMMARY_LIMIT]}</p>" if summary else None,
        deadline=deadline,
        min_age=min_age,
        max_age=max_age,
        age_note=f'"{age_note}"' if age_note else None,
        category=page.get("category", "work_experience"),
        industry=page.get("industry"),
        is_paid=page.get("paid"),
        salary_text=page.get("pay"),
        company_url=page.get("company_url"),
        eligibility=eligibility,
        programme_info=details,
        application_status=status,
    )
