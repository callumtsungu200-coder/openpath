"""The fake API below follows the published OpenAPI definition of the Display Advert API v2.
The real service has not been called yet: it needs a key."""

import json
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest

from openpath import adapters, classify, normalise
from openpath.config import Settings

SETTINGS = Settings("", "", None, "claude-opus-5-5", 5, 0.6, 0.6, "test")
HELPER = Path(__file__).with_name("crawl_helper.py")


def vacancy(ref="VAC1", **overrides):
    return {
        "title": "Software Developer Apprentice",
        "description": "<p>Join our team and learn to build software for real customers across the UK.</p>",
        "fullDescription": "<p>You will write and test code alongside experienced developers every week.</p>",
        "trainingDescription": "<p>One day a week at college.</p>",
        "numberOfPositions": 2,
        "postedDate": "2026-10-20T00:00:00Z",
        "closingDate": "2027-02-01T23:59:59Z",
        "startDate": "2027-09-06T00:00:00Z",
        "wage": {"wageType": "ApprenticeshipMinimum", "wageAmount": None, "wageUnit": "Annually", "workingWeekDescription": "Monday to Friday"},
        "hoursPerWeek": 37.5,
        "expectedDuration": "21 months",
        "addresses": [{"addressLine1": "1 High Street", "addressLine3": "Leeds", "postcode": "LS1 4AP"}],
        "applicationUrl": "https://careers.example.test/apply/1",
        "employerName": "Acme Ltd",
        "employerWebsiteUrl": "https://acme.example.test",
        "employerContactName": "Sam Private",
        "employerContactEmail": "sam@acme.example.test",
        "employerContactPhone": "01000 000000",
        "employerDescription": "<p>We make things.</p>",
        "course": {"larsCode": 1, "title": "Software developer", "level": 4, "route": "Digital", "type": "Standard"},
        "apprenticeshipLevel": "Higher",
        "providerName": "Example College",
        "vacancyUrl": f"https://www.findapprenticeship.service.gov.uk/apprenticeship/{ref}",
        "vacancyReference": ref,
        "skills": ["Attention to detail"],
        "qualifications": [
            {"weighting": "Essential", "qualificationType": "GCSE", "subject": "Maths", "grade": "4"},
            {"weighting": "Desired", "qualificationType": "A Level", "subject": "Computing", "grade": "C"},
        ],
    } | overrides


def parsed(**overrides):
    raw = adapters.parse_apprenticeships({"vacancies": [vacancy(**overrides)]})[0]
    return raw, normalise.normalise(raw, {"industry": None}, SETTINGS)


def test_vacancy_maps_to_opportunity():
    _, opp = parsed()
    assert opp.category == "apprenticeship" and opp.verification == "verified"
    assert opp.location == "Leeds, LS1" and opp.region == "Yorkshire" and opp.industry == "Technology"
    assert opp.salary_text == "National Minimum Wage for apprentices" and opp.salary_min is None and opp.is_paid is True
    assert str(opp.deadline) == "2027-02-01" and opp.duration == "21 months"
    assert opp.requirements == ["GCSE Maths 4", "Desirable: A Level Computing C", "Attention to detail"]
    assert "Training provider: Example College" in opp.programme_info and "Course: Software developer, Level 4" in opp.programme_info
    assert opp.min_age == 16 and "16 or over" in opp.field_provenance["age"]


def test_links_go_to_the_real_application_and_advert():
    _, opp = parsed()
    assert opp.apply_url == "https://careers.example.test/apply/1"
    assert opp.source_url == "https://www.findapprenticeship.service.gov.uk/apprenticeship/VAC1"
    _, fallback = parsed(applicationUrl=None)
    assert fallback.apply_url == fallback.source_url


def test_contact_details_are_never_kept():
    raw, opp = parsed()
    for value in (repr(raw), repr(opp)):
        assert "Sam Private" not in value and "sam@acme" not in value and "01000" not in value


def test_custom_wage_uses_amount_and_competitive_invents_nothing():
    _, custom = parsed(wage={"wageType": "Custom", "wageAmount": 21000, "wageUnit": "Annually"})
    assert (custom.salary_min, custom.salary_period, custom.salary_text) == (21000, "year", None)
    _, competitive = parsed(wage={"wageType": "CompetitiveSalary", "wageAmount": None, "wageUnit": "Unspecified"})
    assert competitive.salary_text == "Competitive" and competitive.salary_min is None


def test_shapes_seen_in_the_live_api():
    wage = {"wageType": "ApprenticeshipMinimum", "wageUnit": "Annually", "wageAdditionalInformation": "\u00a314,560 a year"}
    address = {"addressLine1": "HUCKLEBERRY FARM", "addressLine2": "HEATHFIELD", "addressLine3": "BLETCHINGDON", "addressLine4": "KIDLINGTON", "postcode": "OX5 3DU"}
    course = {"title": "Business administrator (level 3)", "level": 3, "route": "Business and administration"}
    _, opp = parsed(wage=wage, addresses=[address], course=course, applicationUrl=None, employerName="CLARKE JEFFERYS INSURANCE BROKERS LTD")
    assert (opp.salary_min, opp.salary_period, opp.salary_text) == (14560, "year", None)
    assert opp.location == "Kidlington, OX5" and opp.region == "South East"
    assert opp.company_name == "Clarke Jefferys Insurance Brokers Ltd"
    assert "Course: Business administrator (level 3)" in opp.programme_info
    assert "Pay basis: National Minimum Wage for apprentices" in opp.programme_info
    assert opp.apply_url == opp.source_url


def test_streets_and_countries_are_not_used_as_the_town():
    assert parsed(addresses=[{"addressLine1": "Mill Lane", "addressLine2": "Stockport", "addressLine3": "United Kingdom", "postcode": "SK22 1AA"}])[1].location == "Stockport, SK22"
    assert parsed(addresses=[{"addressLine1": "225-227 Clink Street", "postcode": "SE1 9DG"}])[1].location == "SE1"


def test_multiple_and_national_locations():
    two = [{"addressLine3": "Leeds", "postcode": "LS1 4AP"}, {"addressLine3": "York", "postcode": "YO1 1AA"}]
    assert parsed(addresses=two)[1].location == "Leeds, LS1 and 1 other location"
    _, national = parsed(isNationalVacancy=True, addresses=[], isNationalVacancyDetails="Work across England")
    assert national.location == "Recruiting nationally" and national.region == "UK wide"


def test_place_names_that_look_foreign_stay_in_england():
    _, opp = parsed(addresses=[{"addressLine3": "Carlisle", "postcode": "CA1 1AA"}])
    assert opp is not None and opp.region == "North West"


@pytest.mark.parametrize("postcode,region", [("SW1A 1AA", "London"), ("M1 1AA", "North West"), ("S1 2HE", "Yorkshire"), ("CO1 1AA", "East of England"), ("ZZ1 1AA", None), ("", None)])
def test_postcode_regions(postcode, region):
    assert classify.region_from_postcode(postcode) == region


@pytest.fixture
def api():
    seen = []
    state = {"fail_page": None}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            url = urlparse(self.path)
            if url.path == "/robots.txt":
                self.send_response(404)
                self.end_headers()
                return
            query = parse_qs(url.query)
            page = int(query["PageNumber"][0])
            seen.append(self.path)
            if self.headers.get("Ocp-Apim-Subscription-Key") != "good-key":
                status, body = 401, {}
            elif self.headers.get("X-Version") != "2":
                status, body = 404, {}
            elif page == state["fail_page"]:
                status, body = 400, {}
            else:
                status, body = 200, {"vacancies": [vacancy(f"VAC{page}")], "total": 2, "totalFiltered": 2, "totalPages": 2}
            data = json.dumps(body).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}", seen, state
    server.shutdown()


def run(base, key):
    config = json.dumps({"base_url": base, "key": key, "page_size": 100})
    result = subprocess.run([sys.executable, str(HELPER), "gov_apprenticeships", "https://x.test", config],
                            capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stderr[-2000:]
    return json.loads(result.stdout.strip().splitlines()[-1])


def test_reads_every_page_with_the_required_headers(api):
    base, seen, _ = api
    out = run(base, "good-key")
    assert out["status"] == "success" and [i["title"] for i in out["items"]] == ["Software Developer Apprentice"] * 2
    assert len(seen) == 2 and all("IncludeDetails=true" in s and "PageSize=100" in s for s in seen)


def test_bad_key_is_a_clear_failure(api):
    out = run(api[0], "wrong")
    assert out["status"] == "failed" and "rejected" in out["error"]


def test_a_failed_page_means_the_scan_is_not_complete(api):
    base, _, state = api
    state["fail_page"] = 2
    out = run(base, "good-key")
    assert out["status"] == "failed" and len(out["items"]) == 1
