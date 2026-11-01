"""Turn a RawPosting into an Opportunity, recording where each fact came from."""

import hashlib
import json
import re
from datetime import date
from typing import Callable

from dateutil import parser as date_parser

from . import classify, sections
from .ai import AiResult
from .config import Settings
from .models import Opportunity, RawPosting

DESCRIPTION_LIMIT = 20000
DEADLINE = re.compile(
    r"(?:application deadline|closing date|applications? close[s]?(?: on)?|\bclose on|apply by|deadline(?: for (?:applications|submissions))?)"
    r"\s*(?:is|was(?: the)?|:|-|–)?\s*(?:(?:mon|tues|wednes|thurs|fri|satur|sun)day,?\s+)?((?:\d{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]{3,9}(?:\s+\d{4})?)|(?:[A-Za-z]{3,9}\s+\d{1,2}(?:st|nd|rd|th)?(?:,?\s+\d{4})?)|(?:\d{1,2}/\d{1,2}/\d{4}))",
    re.I,
)


def deadlines_from(text: str | None, today: date | None = None) -> list[date]:
    """Every stated deadline, in page order. Recurring programmes often list several rounds."""
    today = today or date.today()
    found = []
    for m in DEADLINE.finditer(text or ""):
        try:
            parsed = date_parser.parse(m.group(1), dayfirst=True).date()
        except (ValueError, OverflowError):
            continue
        if not re.search(r"\d{4}", m.group(1)) and parsed < today:
            parsed = parsed.replace(year=parsed.year + 1)
        found.append(parsed)
    return found


def deadline_from(text: str | None, today: date | None = None) -> date | None:
    found = deadlines_from(text, today)
    return found[0] if found else None


def fingerprint(company: str, title: str, location: str | None) -> str:
    def norm(value: str) -> str:
        return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()
    return hashlib.sha256(f"{norm(company)}|{norm(title)}|{norm(location or '')}".encode()).hexdigest()


def _content_hash(opp: Opportunity) -> str:
    keys = ("title", "company_name", "category", "industry", "location", "region", "arrangement", "salary_min",
            "salary_max", "salary_period", "salary_text", "is_paid", "deadline", "duration", "description", "min_age",
            "max_age", "apply_url", "application_status", "responsibilities", "eligibility", "requirements", "programme_info")
    return hashlib.sha256(json.dumps({k: getattr(opp, k) for k in keys}, default=str).encode()).hexdigest()


def _confidence(raw: RawPosting, category_conf: float, region_known: bool, text: str | None) -> float:
    score = 0.3 if raw.origin == "structured" else 0.0
    score += 0.3 * category_conf
    score += 0.2 if region_known or raw.location else 0.0
    score += 0.2 if text and len(text) > 200 else 0.0
    return round(min(score, 1.0), 2)


def locate(raw: RawPosting) -> tuple[str | None, str | None] | None:
    """Pick the posting's UK location, or None when nothing listed is in the UK."""
    if raw.region:  # the source only lists UK opportunities and gave the region itself
        return raw.location, raw.region
    candidates = [raw.location, *raw.extra_locations]
    for candidate in candidates:
        if not candidate:
            continue
        is_uk, region = classify.uk_region(candidate, raw.country if candidate == raw.location else None)
        if is_uk:
            return candidate, region
    if not any(candidates) and raw.country:
        is_uk, region = classify.uk_region(None, raw.country)
        if is_uk:
            return None, region
    return None


AiExtractor = Callable[[str, str, str], AiResult]


def normalise(raw: RawPosting, source: dict, settings: Settings,
              ai: AiExtractor | None = None, on_ai: Callable[[AiResult], None] | None = None) -> Opportunity | None:
    """Return None for postings outside the UK. `ai` is only called for uncertain postings."""
    located = locate(raw)
    # Boards sometimes file a role under the wrong office: "Researcher - New York" listed as London.
    title_place = re.split(r"\s[-–]\s", raw.title)[-1] if re.search(r"\s[-–]\s", raw.title) else ""
    if located is None or (not raw.region and classify.FOREIGN.fullmatch(title_place.strip())):
        return None
    location, region = located
    if location:
        location = re.sub(rf"\s*-\s*{re.escape(raw.company_name)}$", "", location, flags=re.I)

    text = sections.to_text(raw.description_html)
    parts = sections.split_sections(raw.description_html)
    category, category_conf = (raw.category, 1.0) if raw.category else classify.categorise(raw.title, raw.employment_type)
    provenance: dict[str, str] = {}

    salary = {"min": raw.salary_min, "max": raw.salary_max, "period": raw.salary_period, "text": raw.salary_text}
    if salary["min"] is not None or salary["text"]:
        provenance["salary"] = "Stated by the source"
    else:
        found = classify.salary_from(text, raw.title)
        if found:
            salary = found
            provenance["salary"] = "read from listing text"

    deadline = raw.deadline
    if deadline:
        provenance["deadline"] = "Stated by the source"
    else:
        deadline = deadline_from(text)
        if deadline:
            provenance["deadline"] = "read from description"

    min_age, max_age, age_text = classify.age_from(text)
    if age_text:
        provenance["age"] = "read from description"
        min_age = min_age if min_age is not None else raw.min_age
    elif raw.min_age is not None:
        min_age = raw.min_age
        provenance["age"] = raw.age_note or "Stated by the source"
    if raw.max_age is not None and not age_text:
        max_age = raw.max_age
        provenance["age"] = raw.age_note or "Stated by the source"

    arrangement = classify.arrangement_from(raw.workplace, location, text)
    if arrangement:
        provenance["arrangement"] = "Stated by the source" if raw.workplace else "read from description"

    duration = raw.duration or sections.duration_from(text)
    if duration:
        provenance["duration"] = "Stated by the source" if raw.duration else "read from description"

    opp = Opportunity(
        source_url=raw.source_url,
        title=raw.title.strip(),
        company_name=raw.company_name.strip(),
        external_id=raw.external_id,
        apply_url=raw.apply_url or raw.source_url,
        company_logo_url=raw.logo_url,
        company_url=raw.company_url,
        company_description=raw.company_description,
        application_status=raw.application_status,
        category=category,
        industry=raw.industry or classify.industry_for(raw.title, source.get("industry")),
        location=location,
        region=region,
        arrangement=arrangement,
        employment_type=raw.employment_type,
        salary_min=salary["min"],
        salary_max=salary["max"],
        salary_period=salary["period"],
        salary_text=salary["text"],
        min_age=min_age,
        max_age=max_age,
        age_text=age_text,
        deadline=deadline,
        duration=duration,
        description=text[:DESCRIPTION_LIMIT] if text else None,
        responsibilities=raw.responsibilities or parts["responsibilities"],
        eligibility=raw.eligibility or parts["eligibility"],
        requirements=raw.requirements or parts["requirements"],
        programme_info=raw.programme_info or parts["programme_info"],
        posted_at=raw.posted_at,
        extraction_method=raw.origin,
    )
    opp.confidence = _confidence(raw, category_conf, region is not None, text)

    if ai and text and opp.confidence < settings.ai_confidence_threshold:
        result = ai(opp.title, opp.company_name, text[:DESCRIPTION_LIMIT])
        if on_ai:
            on_ai(result)
        if result.status == "success":
            _apply_ai(opp, result.fields, provenance)

    salary_known = opp.salary_min is not None or bool(opp.salary_text)
    opp.is_paid = raw.is_paid if raw.is_paid is not None else classify.is_paid_from(salary_known, opp.category, text)
    if opp.is_paid and not salary_known and raw.is_paid is None:
        provenance["paid"] = "Assumed from the type of role, no figure stated"
    opp.field_provenance = provenance
    opp.fingerprint = fingerprint(opp.company_name, opp.title, opp.location)
    opp.content_hash = _content_hash(opp)
    opp.verification = "verified" if opp.confidence >= settings.auto_verify_confidence else "pending"
    return opp


def _apply_ai(opp: Opportunity, fields: dict, provenance: dict[str, str]) -> None:
    """Claude only fills gaps. It never overrides a value the source stated directly."""
    opp.extraction_method = "ai"
    opp.confidence = max(opp.confidence, 0.65)
    if fields.get("category"):
        opp.category = fields["category"]
    if opp.min_age is None and "min_age" in fields:
        opp.min_age = fields["min_age"]
        provenance["age"] = "AI, quote checked against source"
    if opp.max_age is None and "max_age" in fields:
        opp.max_age = fields["max_age"]
        provenance["age"] = "AI, quote checked against source"
    if opp.deadline is None and "deadline_iso" in fields:
        try:
            opp.deadline = date.fromisoformat(fields["deadline_iso"])
            provenance["deadline"] = "AI, quote checked against source"
        except ValueError:
            pass
    if not opp.salary_text and opp.salary_min is None and "salary_text" in fields:
        opp.salary_text = fields["salary_text"]
        provenance["salary"] = "AI, quote checked against source"
    if opp.duration is None and "duration" in fields:
        opp.duration = fields["duration"]
        provenance["duration"] = "AI, quote checked against source"
    if opp.arrangement is None and "arrangement" in fields:
        opp.arrangement = fields["arrangement"]
        provenance["arrangement"] = "AI, quote checked against source"
