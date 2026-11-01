"""Parse each source format into RawPosting. Pure functions, so tests need no network."""

import json
import re
from datetime import date, datetime
from urllib.parse import urljoin

import extruct
from dateutil import parser as date_parser

from . import classify, sections
from .models import RawPosting


def _datetime(value) -> datetime | None:
    if value in (None, ""):
        return None
    try:
        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(value / 1000)
        return date_parser.parse(str(value))
    except (ValueError, OverflowError, OSError):
        return None


def _date(value) -> date | None:
    parsed = _datetime(value)
    return parsed.date() if parsed else None


def api_url(adapter: str, board: str) -> str:
    return {
        "greenhouse": f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs?content=true",
        "lever": f"https://api.lever.co/v0/postings/{board}?mode=json",
        "ashby": f"https://api.ashbyhq.com/posting-api/job-board/{board}?includeCompensation=true",
    }[adapter]


def parse_greenhouse(payload: dict, company: str) -> list[RawPosting]:
    postings = []
    for job in payload.get("jobs", []):
        offices = [o.get("location") or o.get("name") for o in job.get("offices") or []]
        departments = job.get("departments") or []
        postings.append(RawPosting(
            source_url=job["absolute_url"],
            external_id=str(job["id"]),
            title=job["title"],
            company_name=job.get("company_name") or company,
            location=(job.get("location") or {}).get("name"),
            extra_locations=[o for o in offices if o],
            department=departments[0]["name"] if departments else None,
            description_html=job.get("content"),
            deadline=_date(job.get("application_deadline")),
            posted_at=_datetime(job.get("first_published")),
        ))
    return postings


def parse_lever(payload: list, company: str) -> list[RawPosting]:
    postings = []
    for job in payload:
        categories = job.get("categories") or {}
        lists = "".join(
            f"<h3>{item.get('text', '')}</h3><ul>{item.get('content', '')}</ul>" for item in job.get("lists") or []
        )
        salary = job.get("salaryRange") or {}
        is_gbp = salary.get("currency") == "GBP"
        postings.append(RawPosting(
            source_url=job["hostedUrl"],
            apply_url=job.get("applyUrl"),
            external_id=job["id"],
            title=job["text"],
            company_name=company,
            location=categories.get("location"),
            extra_locations=[l for l in categories.get("allLocations") or [] if l],
            workplace=job.get("workplaceType"),
            employment_type=categories.get("commitment"),
            department=categories.get("team"),
            description_html=f"{job.get('description', '')}{lists}{job.get('additional', '')}",
            salary_min=salary.get("min") if is_gbp else None,
            salary_max=salary.get("max") if is_gbp else None,
            salary_period={"per-year-salary": "year", "per-month-salary": "month",
                           "per-hour-wage": "hour", "per-day-wage": "day"}.get(salary.get("interval")) if is_gbp else None,
            posted_at=_datetime(job.get("createdAt")),
        ))
    return postings


def parse_ashby(payload: dict, company: str) -> list[RawPosting]:
    postings = []
    for job in payload.get("jobs", []):
        if job.get("isListed") is False:
            continue
        compensation = job.get("compensation") or {}
        summary = compensation.get("compensationTierSummary") if job.get("shouldDisplayCompensationOnJobPostings") else None
        secondary = [s.get("location") for s in job.get("secondaryLocations") or []]
        address = ((job.get("address") or {}).get("postalAddress") or {})
        postings.append(RawPosting(
            source_url=job["jobUrl"],
            apply_url=job.get("applyUrl"),
            external_id=job["id"],
            title=job["title"],
            company_name=company,
            location=job.get("location"),
            extra_locations=[s for s in secondary if s],
            country=None if secondary else address.get("addressCountry"),
            workplace=job.get("workplaceType") or ("Remote" if job.get("isRemote") else None),
            employment_type=job.get("employmentType"),
            department=job.get("department"),
            description_html=job.get("descriptionHtml"),
            salary_text=summary if summary and "£" in summary else None,
            posted_at=_datetime(job.get("publishedAt")),
        ))
    return postings


PARSERS = {"greenhouse": parse_greenhouse, "lever": parse_lever, "ashby": parse_ashby}

APPRENTICESHIP_API = "https://api.apprenticeships.education.gov.uk/vacancies"
APPRENTICESHIP_ROUTES = {
    "Digital": "Technology",
    "Engineering and manufacturing": "Engineering",
    "Legal, finance and accounting": "Finance & Banking",
    "Health and science": "Healthcare",
    "Care services": "Healthcare",
    "Childcare and education": "Education",
    "Education and early years": "Education",
    "Creative and design": "Media & Design",
    "Sales, marketing and procurement": "Sales & Marketing",
    "Business and administration": "Business",
    "Construction and the built environment": "Construction",
    "Protective services": "Public Sector",
}
WAGE_TEXT = {
    "ApprenticeshipMinimum": "National Minimum Wage for apprentices",
    "NationalMinimum": "National Minimum Wage",
    "CompetitiveSalary": "Competitive",
}
WAGE_PERIOD = {"Weekly": "week", "Monthly": "month", "Annually": "year"}
APPRENTICESHIP_AGE_NOTE = "Apprenticeship rule in England: you must be 16 or over"


def _neat(text: str | None) -> str | None:
    """Some adverts arrive in capitals: "CLARKE JEFFERYS INSURANCE BROKERS LTD"."""
    if not text or not text.isupper():
        return text
    titled = re.sub(r"'S\b", "'s", text.title())
    return re.sub(r"\b(Plc|Llp|Nhs|Uk|Cic)\b", lambda m: m.group(1).upper(), titled)


def _apprenticeship_location(job: dict) -> tuple[str | None, str | None]:
    addresses = job.get("addresses") or []
    if job.get("isNationalVacancy"):
        return "Recruiting nationally", "UK wide"
    if not addresses:
        return None, None
    first = addresses[0]
    postcode = first.get("postcode") or ""
    # Real adverts fill these from the top, so the last usable line is the town or county.
    # Countries and street addresses say little, and the postcode area follows anyway.
    lines = (first.get(f"addressLine{i}") for i in (4, 3, 2, 1))
    town = _neat(next((l.strip() for l in lines if l and not re.fullmatch(r"\s*(united kingdom|uk|england|\d.*)\s*", l, re.I)), None))
    outward = postcode.split()[0] if postcode else None
    place = ", ".join(p for p in (town, outward) if p) or None
    if place and len(addresses) > 1:
        extra = len(addresses) - 1
        place += f" and {extra} other location{'s' if extra > 1 else ''}"
    return place, classify.region_from_postcode(postcode)


def _apprenticeship_programme(job: dict) -> list[str]:
    course = job.get("course") or {}
    wage = job.get("wage") or {}
    level = f"Level {course['level']}" if course.get("level") and "level" not in (course.get("title") or "").lower() else None
    facts = [
        f"Course: {', '.join(p for p in (course.get('title'), level) if p)}" if course.get("title") else None,
        f"Training provider: {job['providerName']}" if job.get("providerName") else None,
        f"Pay basis: {WAGE_TEXT[wage['wageType']]}" if wage.get("wageType") in WAGE_TEXT else None,
        f"Starts: {_date(job['startDate']).strftime('%d %B %Y').lstrip('0')}" if _date(job.get("startDate")) else None,
        f"Hours: {job['hoursPerWeek']:g} a week" if job.get("hoursPerWeek") else None,
        f"Working week: {wage['workingWeekDescription']}" if wage.get("workingWeekDescription") else None,
        f"Positions available: {job['numberOfPositions']}" if job.get("numberOfPositions") else None,
    ]
    return [f for f in facts if f]


def parse_apprenticeships(payload: dict) -> list[RawPosting]:
    """GOV.UK Display Advert API v2. Contact names, emails and phone numbers are deliberately
    not read: applicants apply through the advert, and OpenPath should not hold that data."""
    postings = []
    for job in payload.get("vacancies") or []:
        url = job.get("vacancyUrl")
        if not url or not job.get("title") or not job.get("employerName"):
            continue
        wage = job.get("wage") or {}
        custom = wage.get("wageType") == "Custom" and wage.get("wageAmount") is not None
        # The figure for minimum-wage adverts is only in this text: "£14,560 a year".
        stated = classify.salary_from(None, wage.get("wageAdditionalInformation")) if not custom else None
        location, region = _apprenticeship_location(job)
        route = (job.get("course") or {}).get("route")
        qualifications = job.get("qualifications") or []
        def named(weighting):
            return [" ".join(p for p in (q.get("qualificationType"), q.get("subject"), q.get("grade")) if p)
                    for q in qualifications if q.get("weighting") == weighting]
        desired = [f"Desirable: {q}" for q in named("Desired")]
        description = "".join(
            f"<h3>{heading}</h3>{job[key]}" if heading else job[key]
            for heading, key in (
                (None, "description"), ("About the role", "fullDescription"), ("Training", "trainingDescription"),
                ("Further training", "additionalTrainingDescription"), ("After this apprenticeship", "outcomeDescription"),
                ("Benefits", "companyBenefitsInformation"), ("Things to consider", "thingsToConsider"),
                ("Where you will work", "isNationalVacancyDetails"),
            ) if job.get(key)
        )
        postings.append(RawPosting(
            source_url=url,
            apply_url=job.get("applicationUrl") or url,
            external_id=job.get("vacancyReference"),
            title=job["title"],
            company_name=_neat(job["employerName"]),
            location=location,
            region=region or "England",
            description_html=description or None,
            salary_min=wage["wageAmount"] if custom else stated["min"] if stated else None,
            salary_max=stated["max"] if stated else None,
            salary_period=WAGE_PERIOD.get(wage.get("wageUnit")) if custom else stated["period"] if stated else None,
            salary_text=None if custom or stated else WAGE_TEXT.get(wage.get("wageType")),
            deadline=_date(job.get("closingDate")),
            posted_at=_datetime(job.get("postedDate")),
            employment_type=f"{job['apprenticeshipLevel']} apprenticeship" if job.get("apprenticeshipLevel") else None,
            category="apprenticeship",
            industry=APPRENTICESHIP_ROUTES.get(route, route),
            is_paid=True,  # employers must pay apprentices, and every wage type here is a paid one
            duration=job.get("expectedDuration"),
            min_age=16,
            age_note=APPRENTICESHIP_AGE_NOTE,
            company_url=job.get("employerWebsiteUrl"),
            company_description=sections.to_text(job.get("employerDescription")),
            requirements=[*named("Essential"), *desired, *(job.get("skills") or [])],
            programme_info=_apprenticeship_programme(job),
        ))
    return postings


def _first(value):
    return value[0] if isinstance(value, list) and value else value


def _job_location(job: dict) -> tuple[str | None, str | None]:
    loc = _first(job.get("jobLocation")) or {}
    if isinstance(loc, str):
        return loc, None
    address = loc.get("address") or {}
    if isinstance(address, str):
        return address, None
    country = address.get("addressCountry")
    if isinstance(country, dict):
        country = country.get("name")
    parts = [address.get("addressLocality"), address.get("addressRegion")]
    return ", ".join(p for p in parts if p) or None, country


def _job_salary(job: dict) -> dict:
    salary = job.get("baseSalary")
    if not isinstance(salary, dict) or salary.get("currency", "GBP") != "GBP":
        return {}
    value = salary.get("value")
    if isinstance(value, dict):
        low, high = value.get("minValue", value.get("value")), value.get("maxValue")
        unit = str(value.get("unitText", "")).upper()
    else:
        low, high, unit = value, None, ""
    try:
        low = float(low) if low is not None else None
        high = float(high) if high is not None else None
    except (TypeError, ValueError):
        return {}
    period = {"YEAR": "year", "MONTH": "month", "WEEK": "week", "DAY": "day", "HOUR": "hour"}.get(unit)
    return {"salary_min": low, "salary_max": high, "salary_period": period}


def _walk(node):
    if isinstance(node, list):
        for item in node:
            yield from _walk(item)
    elif isinstance(node, dict):
        yield node
        yield from _walk(node.get("@graph", []))


def parse_jsonld_page(html: str, url: str, fallback_company: str | None) -> list[RawPosting]:
    """Read schema.org JobPosting data, the markup employers publish for search engines."""
    try:
        data = extruct.extract(html, base_url=url, syntaxes=["json-ld"], uniform=False)["json-ld"]
    except (json.JSONDecodeError, ValueError, TypeError):
        return []
    postings = []
    for node in _walk(data):
        kinds = node.get("@type")
        if "JobPosting" not in (kinds if isinstance(kinds, list) else [kinds]):
            continue
        title = node.get("title")
        org = _first(node.get("hiringOrganization")) or {}
        company = (org.get("name") if isinstance(org, dict) else org) or fallback_company
        if not title or not company:
            continue
        location, country = _job_location(node)
        employment = _first(node.get("employmentType"))
        remote = str(node.get("jobLocationType", "")).upper() == "TELECOMMUTE"
        identifier = node.get("identifier")
        logo = org.get("logo") if isinstance(org, dict) else None
        postings.append(RawPosting(
            source_url=urljoin(url, node.get("url") or url),
            external_id=str(identifier.get("value")) if isinstance(identifier, dict) else (str(identifier) if identifier else None),
            title=title,
            company_name=company,
            location=location or ("United Kingdom" if remote and country in (None, "GB", "UK") else None),
            country=country,
            workplace="remote" if remote else None,
            employment_type=str(employment) if employment else None,
            description_html=node.get("description"),
            deadline=_date(node.get("validThrough")),
            posted_at=_datetime(node.get("datePosted")),
            logo_url=_first(logo).get("url") if isinstance(_first(logo), dict) else _first(logo),
            **_job_salary(node),
        ))
    return postings
