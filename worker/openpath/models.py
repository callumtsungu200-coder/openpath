from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any


@dataclass
class RawPosting:
    """What a source said, before any interpretation. None means not stated."""

    source_url: str
    title: str
    company_name: str
    external_id: str | None = None
    apply_url: str | None = None
    location: str | None = None
    extra_locations: list[str] = field(default_factory=list)
    country: str | None = None
    workplace: str | None = None
    employment_type: str | None = None
    department: str | None = None
    description_html: str | None = None
    salary_min: float | None = None
    salary_max: float | None = None
    salary_period: str | None = None
    salary_text: str | None = None
    deadline: date | None = None
    posted_at: datetime | None = None
    logo_url: str | None = None
    origin: str = "structured"  # 'structured' for APIs and schema.org, 'rules' for HTML guesses
    # Set by sources that state these directly, so rules do not have to infer them.
    region: str | None = None
    category: str | None = None
    industry: str | None = None
    is_paid: bool | None = None
    duration: str | None = None
    min_age: int | None = None
    max_age: int | None = None
    age_note: str | None = None
    application_status: str | None = None
    company_url: str | None = None
    company_description: str | None = None
    responsibilities: list[str] = field(default_factory=list)
    eligibility: list[str] = field(default_factory=list)
    requirements: list[str] = field(default_factory=list)
    programme_info: list[str] = field(default_factory=list)


@dataclass
class Opportunity:
    source_url: str
    title: str
    company_name: str
    external_id: str | None = None
    apply_url: str | None = None
    company_logo_url: str | None = None
    company_url: str | None = None
    company_description: str | None = None
    category: str = "other"
    industry: str | None = None
    location: str | None = None
    region: str | None = None
    arrangement: str | None = None
    employment_type: str | None = None
    salary_min: float | None = None
    salary_max: float | None = None
    salary_period: str | None = None
    salary_text: str | None = None
    is_paid: bool | None = None
    min_age: int | None = None
    max_age: int | None = None
    age_text: str | None = None
    deadline: date | None = None
    duration: str | None = None
    description: str | None = None
    responsibilities: list[str] = field(default_factory=list)
    eligibility: list[str] = field(default_factory=list)
    requirements: list[str] = field(default_factory=list)
    programme_info: list[str] = field(default_factory=list)
    posted_at: datetime | None = None
    extraction_method: str = "structured"
    confidence: float = 0.0
    field_provenance: dict[str, Any] = field(default_factory=dict)
    fingerprint: str = ""
    content_hash: str = ""
    verification: str = "pending"
    application_status: str | None = None
