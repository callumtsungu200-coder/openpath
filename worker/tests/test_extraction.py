from datetime import date
from types import SimpleNamespace

import pytest

from openpath import adapters, ai, classify, normalise, sections
from openpath.config import Settings
from openpath.models import RawPosting
from openpath.scan import classify_outcome

SETTINGS = Settings("", "", "key", "claude-opus-5-5", 5, 0.6, 0.6, "test")


@pytest.mark.parametrize("location,expected", [
    ("London", (True, "London")),
    ("London, UK", (True, "London")),
    ("Remote - UK", (True, "UK wide")),
    ("Manchester, United Kingdom", (True, "North West")),
    ("New York, NY", (False, None)),
    ("London, Ontario, Canada", (False, None)),
    ("Berlin", (False, None)),
    ("Belfast", (True, "Northern Ireland")),
    ("Dublin, Ireland", (False, None)),
])
def test_uk_region(location, expected):
    assert classify.uk_region(location) == expected


@pytest.mark.parametrize("title,expected", [
    ("Software Engineering Apprentice", "apprenticeship"),
    ("Summer Internship 2027", "internship"),
    ("Spring Insight Week", "insight_programme"),
    ("Graduate Analyst Programme", "graduate_scheme"),
    ("Junior Data Analyst", "entry_level_job"),
    ("Senior Associate", "job"),
    ("Staff Engineer", "job"),
    ("International Payments Lead", "job"),  # must not match "intern"
])
def test_categorise(title, expected):
    assert classify.categorise(title)[0] == expected


@pytest.mark.parametrize("text,expected", [
    ("Applicants must be aged 16-18 at the start.", (16, 18)),
    ("Applicants must be aged 16-18", (16, 18)),
    ("You must be 18 or over to apply.", (18, None)),
    ("Must be at least 21 years old", (21, None)),
    ("For young people aged 24 or under", (None, 24)),
    ("We have 25 offices and 18 teams.", (None, None)),
    ("Founded 20 years ago.", (None, None)),
    # Wording from real adverts that does not limit who can apply:
    ("If you are aged 21 or over, after 12 months in post, there will be a further pay rise.", (None, None)),
    ("Workplace pension (for employees aged 22+, details to be discussed at interview)", (None, None)),
    ("Individuals aged 19+ and residing within the West Midlands may qualify.", (None, None)),
    ("Age 18 to 20 is paid £10.85 per hour.", (None, None)),
    ("You would work as a Support Worker, supporting young people aged 16-18 who are in care.", (None, None)),
    ("Applicants aged 16-18 are subject to entry grades of a 4 or above.", (None, None)),
    ("Help young people aged 16 to 25 take their first steps into the screen industries.", (None, None)),
    # And wording that does:
    ("For this Foundation Apprenticeship you must be aged 16-21 to apply.", (16, 21)),
    ("Youth Guarantee apprenticeship open to those aged 18-21.", (18, 21)),
    ("You must be aged 19 or above for this position due to insurance restrictions.", (19, None)),
    ("Things to consider\nEssential: Age 18+\nFull UK Driving Licence", (18, None)),
    ("Must be 21 years of age or older (due to insurance requirements)", (21, None)),
])
def test_age_requires_explicit_statement(text, expected):
    assert classify.age_from(text)[:2] == expected


@pytest.mark.parametrize("text,expected", [
    ("The course will be a hybrid model with face to face visits.", None),
    ("The qualification is fully remote and completed within working hours.", None),
    ("Assessed by multiple choice, and then in-person role plays and shadowing.", None),
    ("Benefits: Hybrid working (4 days in the York office).", "hybrid"),
    ("This is a fully office-based role, not remote.", "in_person"),
])
def test_arrangement_describes_the_job_not_the_training(text, expected):
    assert classify.arrangement_from(None, "Leeds", text) == expected


def test_salary_ignores_non_pay_figures():
    assert classify.salary_from("We raised £50,000,000 in funding.") is None
    assert classify.salary_from("Our customers saved £400 last year.") is None
    found = classify.salary_from("The salary is £28,000 - £32,000 per annum.")
    assert (found["min"], found["max"], found["period"]) == (28000, 32000, "year")
    found = classify.salary_from("Pay: £12.50 per hour.")
    assert (found["min"], found["period"]) == (12.5, "hour")


def test_deadline_only_from_explicit_wording():
    assert normalise.deadline_from("Closing date: 14 March 2027") == date(2027, 3, 14)
    assert normalise.deadline_from("We started on 14 March 2020") is None


def test_sections_split_by_heading():
    html = "<h3>What you'll do</h3><ul><li>Build APIs</li></ul><p><strong>Requirements</strong></p><ul><li>Some Python</li></ul>"
    parts = sections.split_sections(html)
    assert parts["responsibilities"] == ["Build APIs"]
    assert parts["requirements"] == ["Some Python"]


def test_greenhouse_double_encoded_content_is_decoded():
    assert "Hello" in sections.to_text("&lt;p&gt;Hello&lt;/p&gt;")


def test_parse_greenhouse_and_normalise_keeps_unknowns_empty():
    payload = {"jobs": [{"absolute_url": "https://x/1", "id": 1, "title": "Backend Engineer", "company_name": "Monzo",
                         "location": {"name": "London"}, "offices": [], "departments": [], "content": "&lt;p&gt;" + "word " * 60 + "&lt;/p&gt;"}]}
    raw = adapters.parse_greenhouse(payload, "Monzo")[0]
    opp = normalise.normalise(raw, {"industry": "Finance & Banking"}, SETTINGS)
    assert opp.region == "London" and opp.category == "job"
    assert opp.salary_min is None and opp.deadline is None and opp.min_age is None and opp.arrangement is None
    assert opp.verification == "verified"


def test_non_uk_posting_is_dropped():
    raw = RawPosting(source_url="https://x/2", title="Engineer", company_name="X", location="Barcelona")
    assert normalise.normalise(raw, {}, SETTINGS) is None


def test_title_naming_a_foreign_city_overrides_a_wrong_office():
    raw = RawPosting(source_url="https://x/4", title="Researcher - New York", company_name="X", location="London, UK")
    assert normalise.normalise(raw, {}, SETTINGS) is None


def test_salary_in_title_and_no_invented_period():
    found = classify.salary_from(None, "Graduate Analyst - £50,000 + Share Options")
    assert (found["min"], found["period"]) == (50000, None)


def test_secondary_uk_location_counts():
    raw = RawPosting(source_url="https://x/3", title="Engineer", company_name="X", location="Berlin", extra_locations=["London"])
    assert normalise.normalise(raw, {}, SETTINGS).location == "London"


def test_jsonld_reads_jobposting_and_salary():
    html = """<html><script type="application/ld+json">{"@context":"https://schema.org","@type":"JobPosting",
      "title":"Marketing Apprentice","hiringOrganization":{"@type":"Organization","name":"Acme"},
      "validThrough":"2027-02-01","description":"<p>Learn marketing</p>",
      "baseSalary":{"@type":"MonetaryAmount","currency":"GBP","value":{"@type":"QuantitativeValue","value":21000,"unitText":"YEAR"}},
      "jobLocation":{"@type":"Place","address":{"addressLocality":"Leeds","addressCountry":"GB"}}}</script></html>"""
    raw = adapters.parse_jsonld_page(html, "https://acme.test/job/1", None)[0]
    assert (raw.title, raw.company_name, raw.location, raw.salary_min, raw.deadline) == (
        "Marketing Apprentice", "Acme", "Leeds", 21000.0, date(2027, 2, 1))


def test_ai_evidence_guard_drops_unquoted_claims():
    source = "Applicants must be 18 or over. Closes 1 March 2027."
    data = {"category": "internship",
            "min_age": {"value": 18, "evidence": "must be 18 or over"},
            "max_age": {"value": 24, "evidence": "under 24 only"},  # hallucinated
            "deadline_iso": {"value": "2027-03-01", "evidence": "Closes 1 March 2027"},
            "salary_text": {"value": "£30,000", "evidence": None},
            "duration": {"value": None, "evidence": None},
            "arrangement": {"value": None, "evidence": None}}
    assert ai.keep_supported(data, source) == {"category": "internship", "min_age": 18, "deadline_iso": "2027-03-01"}


def _fake_client(stop_reason, text):
    response = SimpleNamespace(stop_reason=stop_reason, content=[SimpleNamespace(type="text", text=text)],
                               usage=SimpleNamespace(input_tokens=10, output_tokens=5))
    return SimpleNamespace(beta=SimpleNamespace(messages=SimpleNamespace(create=lambda **kw: response)))


def test_ai_refusal_and_truncation_yield_no_fields():
    assert ai.extract(SETTINGS, "t", "c", "x", client=_fake_client("refusal", "")).status == "refused"
    assert ai.extract(SETTINGS, "t", "c", "x", client=_fake_client("max_tokens", "{")).status == "error"


def test_scan_outcomes():
    assert classify_outcome({"complete": True}, {"found": 3}) == ("success", None)
    assert classify_outcome({"complete": True}, {"found": 0})[0] == "partial"
    assert classify_outcome({"complete": False}, {"found": 0})[0] == "failed"
    assert classify_outcome({"error": "boom"}, {"found": 0}) == ("failed", "boom")
