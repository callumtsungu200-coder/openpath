import json
from datetime import date

from openpath import normalise, work_experience as we
from openpath.config import Settings

SETTINGS = Settings("", "", None, "claude-opus-5-5", 5, 0.6, 0.6, "test")
TODAY = date(2026, 11, 1)


def page(item):
    return f'<script id="__NEXT_DATA__" type="application/json">{json.dumps({"props": {"pageProps": {"item": item}}})}</script>'


def programme(**overrides):
    return {
        "title": "AAT Virtual Work Experience", "internalId": "WEXP-1", "includeInSearchEngine": True,
        "ageRange": {"ageStart": None, "ageEnd": None},
        "partner": {"organisation": {"name": "AAT", "externalProfileUrl": "https://www.aat.org.uk/", "logo": {"url": "https://cdn.test/l.jpg"}}},
        "detail": {"cohortDetails": [{"status": "LIVE", "endDate": "2027-03-31T00:00:00.000Z"}, {"status": "EXPIRED", "endDate": "2022-01-01T00:00:00.000Z"}]},
        "content": {"intro": "Step into accounting.", "facts": ["This programme is open to anyone aged 13+", "Certificate of completion"]},
        "jobSector": {"name": "Accounting, banking and finance"},
    } | overrides


def test_springpod_live_programme():
    raw = we.parse_springpod_programme(page(programme()), "https://www.springpod.com/x/WEXP-1")
    opp = normalise.normalise(raw, {}, SETTINGS)
    assert opp.category == "work_experience" and opp.arrangement == "remote" and opp.location == "Online"
    assert opp.min_age == 13 and opp.max_age is None and str(opp.deadline) == "2027-03-31"
    assert opp.is_paid is False and opp.salary_text == "Free to join" and opp.industry == "Finance & Banking"
    assert opp.company_logo_url == "https://cdn.test/l.jpg" and opp.apply_url == opp.source_url


def test_springpod_skips_expired_hidden_and_us_only():
    expired = {"cohortDetails": [{"status": "EXPIRED", "endDate": "2022-01-01T00:00:00.000Z"}]}
    assert we.parse_springpod_programme(page(programme(detail=expired)), "u") is None
    assert we.parse_springpod_programme(page(programme(includeInSearchEngine=False)), "u") is None
    assert we.parse_springpod_programme(page(programme(title="Sports Career Tour (US Only)")), "u") is None
    assert we.parse_springpod_programme("<html></html>", "u") is None


def test_springpod_board_keeps_only_work_experience_and_never_the_gated_link():
    item = {"title": "Asda Early Careers", "internalId": "OP-1", "format": "IN_PERSON", "city": {"name": "london"},
            "applicationUrl": "https://gated.test/apply", "partner": {"organisation": {"name": "Asda"}},
            "type": {"name": "Work Experience (In Person)"}}
    raw = we.parse_springpod_opportunity(page(item), "https://www.springpod.com/opportunities/OP-1")
    opp = normalise.normalise(raw, {}, SETTINGS)
    assert opp.region == "London" and opp.arrangement == "in_person"
    assert opp.apply_url == "https://www.springpod.com/opportunities/OP-1"
    assert we.parse_springpod_opportunity(page(item | {"type": {"name": "Apprenticeship"}}), "u") is None


FINDER = """Work Experience Finder
Experience something different with Flogas.
with Flogas
Apply now
favorite_border
Application deadline: 1 February 2027
library_books
Overview
map
Remote
calendar_month
2 March - 4 March 2027 (3 days)
access_time
09:00 - 14:00
cake
16-19
domain
Energy & Utilities
\U0001F680 Go Beyond Traditional Work Experience.
Most programmes show you what a company does.
library_books
Skills you'll gain
Teamwork is not a summary line."""


def test_finder_detail():
    raw = we.parse_finder_detail("Experience something different with Flogas.", FINDER, "https://f.test/opportunity-detail/A1")
    opp = normalise.normalise(raw, {}, SETTINGS)
    assert opp.company_name == "Flogas" and opp.arrangement == "remote" and str(opp.deadline) == "2027-02-01"
    assert (opp.min_age, opp.max_age) == (16, 19) and opp.duration == "3 days" and opp.industry == "Energy"
    assert "Hours: 09:00 - 14:00" in opp.programme_info and opp.is_paid is False
    assert opp.description.startswith("Go Beyond") and "Teamwork" not in opp.description


def test_finder_in_person_location_and_unready_page():
    text = "T\nwith Acme\nApply now\nmap\nLeeds, LS1 4AP\ncalendar_month\n1 May 2027 (1 day)\ncake\n14-19\ndomain\nLaw\nLearn the law."
    opp = normalise.normalise(we.parse_finder_detail("T", text, "https://f.test/2"), {}, SETTINGS)
    assert opp.arrangement == "in_person" and opp.region == "Yorkshire" and opp.deadline is None and opp.industry == "Law"
    assert we.parse_finder_detail("Missing", text, "u") is None
    assert we.parse_finder_detail("Loading opportunity...", "Loading opportunity...\nwith x", "u") is None


def official(html, **page_fields):
    return we.parse_programme_page(html, {"title": "T", "company": "C", "region": "London", "location": "London"} | page_fields, "https://o.test/p", TODAY)


def test_page_with_future_deadline_is_open():
    raw = official("<main><p>Application deadline: Monday 15 March 2027</p><p>This is for students in Year 10 or Year 12 only.</p></main>")
    assert raw.application_status == "open" and raw.deadline == date(2027, 3, 15)
    assert raw.eligibility == ["This is for students in Year 10 or Year 12 only."]


def test_last_rounds_date_means_closed_not_expired():
    raw = official("<main><p>Deadline for submissions was the 1st Feb 2026</p></main>")
    assert raw.application_status == "closed" and raw.deadline is None


def test_stated_closed_beats_silence_and_silence_is_unknown():
    assert official("<p>Our work experience applications are currently closed and will reopen in early 2027.</p>").application_status == "closed"
    assert official("<p>We welcome students who enjoy science and want to learn.</p>").application_status is None


def test_page_text_is_excerpted_and_noise_dropped():
    raw = official('<head><meta name="description" content="A short official summary of the programme, long enough to be real."></head><nav>Year 10 menu</nav><p>We use cookies for students aged 16 and over on this site.</p>')
    assert raw.description_html == "<p>A short official summary of the programme, long enough to be real.</p>" and raw.eligibility == []


def test_future_round_outranks_an_old_date():
    raw = official("<p>Applications open on Monday 2 November and close on Wednesday 4 November 2026.</p><p>Deadline was 1 February 2026.</p>")
    assert raw.deadline == date(2026, 11, 4) and raw.application_status is None


def test_reopening_later_means_closed_today():
    assert official("<p>Applications will re-open in January 2027 for next summer's programme.</p>").application_status == "closed"


def test_page_ages_come_from_eligibility_wording():
    raw = official("<p>This programme is open to students who are 14 to 19 years old and based in Staffordshire.</p>")
    assert (raw.min_age, raw.max_age) == (14, 19)
    raw = official("<p>This free programme is tailored for school students aged 16 and older, with no experience needed.</p>")
    assert (raw.min_age, raw.max_age) == (16, None)
    assert official("<p>Students aged 16 and older earn more per hour than they do in Year 10 here.</p>").min_age is None


def test_headings_are_not_eligibility():
    raw = official("<h1>Year 12 Work Experience Programme</h1><p>Work experience for Year 12 (STEM) | Study at Bristol</p>", title="Year 12 Work Experience Programme")
    assert raw.eligibility == []


def test_curated_fields_are_used_as_given():
    raw = official("<p>x</p>", arrangement="remote", paid=False, pay="Free to join", category="insight_programme")
    assert raw.workplace == "remote" and raw.is_paid is False and raw.category == "insight_programme"
