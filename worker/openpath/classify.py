"""Rule-based interpretation. Each function returns None rather than guessing."""

import re

UK_REGIONS: dict[str, tuple[str, ...]] = {
    "London": ("london", "canary wharf", "croydon", "shoreditch"),
    "South East": ("reading", "oxford", "brighton", "southampton", "portsmouth", "milton keynes",
                   "guildford", "maidstone", "canterbury", "slough", "crawley", "basingstoke"),
    "South West": ("bristol", "bath", "exeter", "plymouth", "gloucester", "cheltenham", "swindon",
                   "bournemouth"),
    "East of England": ("cambridge", "norwich", "ipswich", "chelmsford", "colchester", "luton",
                        "peterborough", "essex", "stevenage"),
    "West Midlands": ("birmingham", "coventry", "wolverhampton", "stoke-on-trent"),
    "East Midlands": ("nottingham", "leicester", "derby", "lincoln", "northampton"),
    "North West": ("manchester", "liverpool", "preston", "chester", "warrington", "blackpool"),
    "Yorkshire": ("leeds", "sheffield", "york", "hull", "bradford", "doncaster"),
    "North East": ("newcastle", "sunderland", "durham", "middlesbrough"),
    "Scotland": ("scotland", "edinburgh", "glasgow", "aberdeen", "dundee", "inverness"),
    "Wales": ("wales", "cardiff", "swansea", "newport"),
    "Northern Ireland": ("northern ireland", "belfast", "derry"),
}
UK_NATIONAL = re.compile(r"\b(uk|u\.k\.|united kingdom|great britain|england|gb|gbr)\b", re.I)
# Names shared with places abroad: they only count when the text does not name another country.
FOREIGN = re.compile(
    r"\b(usa|u\.s\.|united states|canada|ontario|australia|new south wales|new zealand|ireland(?<!northern ireland)|"
    r"germany|france|spain|portugal|netherlands|poland|italy|india|singapore|japan|korea|brazil|mexico|"
    r"dubai|uae|united arab emirates|bulgaria|lithuania|new york|nyc|ny|ca|tx|ma|ct|dc)\b",
    re.I,
)


POSTCODE_REGIONS: dict[str, tuple[str, ...]] = {
    "London": ("E", "EC", "N", "NW", "SE", "SW", "W", "WC", "BR", "CR", "DA", "EN", "HA", "IG", "KT", "RM", "SM", "TW", "UB"),
    "South East": ("BN", "CT", "GU", "HP", "ME", "MK", "OX", "PO", "RG", "RH", "SL", "SO", "TN"),
    "South West": ("BA", "BH", "BS", "DT", "EX", "GL", "PL", "SN", "SP", "TA", "TQ", "TR"),
    "East of England": ("AL", "CB", "CM", "CO", "IP", "LU", "NR", "PE", "SG", "SS", "WD"),
    "West Midlands": ("B", "CV", "DY", "HR", "ST", "SY", "TF", "WR", "WS", "WV"),
    "East Midlands": ("DE", "LE", "LN", "NG", "NN"),
    "Yorkshire": ("BD", "DN", "HD", "HG", "HU", "HX", "LS", "S", "WF", "YO"),
    "North West": ("BB", "BL", "CA", "CH", "CW", "FY", "L", "LA", "M", "OL", "PR", "SK", "WA", "WN"),
    "North East": ("DH", "DL", "NE", "SR", "TS"),
    "Scotland": ("AB", "DD", "DG", "EH", "FK", "G", "HS", "IV", "KA", "KW", "KY", "ML", "PA", "PH", "TD", "ZE"),
    "Wales": ("CF", "LD", "LL", "NP", "SA"),
    "Northern Ireland": ("BT",),
}
_POSTCODE_AREA_TO_REGION = {area: region for region, areas in POSTCODE_REGIONS.items() for area in areas}


def region_from_postcode(postcode: str | None) -> str | None:
    m = re.match(r"\s*([A-Za-z]{1,2})\d", postcode or "")
    return _POSTCODE_AREA_TO_REGION.get(m.group(1).upper()) if m else None


def uk_region(location: str | None, country: str | None = None) -> tuple[bool, str | None]:
    """Return (is_uk, region). Region stays None for a UK location with no known city."""
    if country and country.strip().upper() not in {"GB", "GBR", "UK", "UNITED KINGDOM"}:
        return False, None
    if not location:
        return bool(country), None
    text = location.lower()
    foreign = bool(FOREIGN.search(location)) and "northern ireland" not in text
    if foreign and not UK_NATIONAL.search(location):
        return False, None
    for region, places in UK_REGIONS.items():
        if any(re.search(rf"\b{re.escape(p)}\b", text) for p in places):
            return True, region
    if UK_NATIONAL.search(location):
        return True, "UK wide" if re.search(r"remote|anywhere|nationwide", text) else None
    return bool(country), None


# Order matters: the first match wins, so specific programmes precede generic roles.
CATEGORY_RULES: tuple[tuple[str, str], ...] = (
    ("apprenticeship", r"\b(apprentice|apprenticeship|t[- ]level)\b"),
    ("insight_programme", r"\b(insight (day|week|programme|program|event)|spring (week|insight)|discovery (day|programme))\b"),
    ("work_experience", r"\b(work experience|work shadow|job shadow|taster (day|week))\b"),
    ("placement", r"\b(industrial placement|year in industry|placement year|sandwich placement|placement student|placement)\b"),
    ("internship", r"\b(intern|internship|summer analyst|off[- ]cycle)\b"),
    ("graduate_scheme", r"\b(graduate (scheme|programme|program|analyst|engineer|trainee|role)|new grad|grad scheme|graduate)\b"),
    ("volunteering", r"\b(volunteer|volunteering)\b"),
    ("scholarship", r"\b(scholarship|bursary|sponsorship programme)\b"),
    # Not bare "competition" or "associate": real titles include "Competition Counsel" and
    # "Associate Legal Counsel" on £64,000+.
    ("competition", r"\b((coding|case|essay|design|maths?|business|student) (competition|challenge)|hackathon)\b"),
    ("course", r"\b(bootcamp|boot camp|training course|free course)\b"),
    ("entry_level_job", r"\b(junior|entry[- ]level|trainee|assistant)\b"),
)
SENIOR = re.compile(r"\b(senior|sr\.?|lead|staff|principal|head of|director|vp|vice president|manager|chief)\b", re.I)


def categorise(title: str, employment_type: str | None = None) -> tuple[str, float]:
    """Return (category, confidence). Only the title and declared type are used, because
    long descriptions routinely mention internships or graduates in passing."""
    haystack = f"{title} {employment_type or ''}"
    senior = bool(SENIOR.search(title))
    for category, pattern in CATEGORY_RULES:
        if re.search(pattern, haystack, re.I):
            if senior and category in {"entry_level_job", "graduate_scheme", "placement"}:
                return "job", 0.8
            return category, 0.9
    return "job", 0.7


INDUSTRY_RULES: tuple[tuple[str, str], ...] = (
    ("Finance & Banking", r"\b(bank|banking|investment|trading|trader|quant|fintech|finance|financial|credit|payments?|insurance|actuar)\w*"),
    ("Law", r"\b(solicitor|paralegal|legal|law firm|barrister)\b"),
    ("Healthcare", r"\b(nhs|nurse|nursing|healthcare|clinical|pharmac|medical)\w*"),
    ("Engineering", r"\b(mechanical|civil|electrical|aerospace|manufacturing) engineer\w*"),
    ("Education", r"\b(teacher|teaching|tutor|school|education)\w*"),
    ("Media & Design", r"\b(designer|journalis|marketing|content|broadcast|creative|brand)\w*"),
    ("Technology", r"\b(software|developer|data|machine learning|ai|cloud|cyber|devops|engineer)\w*"),
    ("Public Sector", r"\b(civil service|government|council|public sector)\b"),
)


def industry_for(title: str, source_industry: str | None) -> str | None:
    """A posting's own title wins only when the source has no sector of its own."""
    if source_industry:
        return source_industry
    for industry, pattern in INDUSTRY_RULES:
        if re.search(pattern, title, re.I):
            return industry
    return None


ARRANGEMENT_WORDING = (
    # Not "hybrid model": real adverts use it for training, often on its own line under a heading.
    ("hybrid", r"\b(hybrid (role|working|position)|work(ing)? hybrid)\b"),
    ("remote", r"\b(fully remote|100% remote|remote[- ]first role|work from anywhere in the uk)\b"),
    ("in_person", r"\b(fully on[- ]?site|office[- ]based role|in[- ]person role(?! play))\b"),
)
ABOUT_TRAINING = re.compile(r"\b(course|training|qualification|delivery|delivered|learners?|college|tutor|teams session)\b", re.I)


def arrangement_from(workplace: str | None, location: str | None, text: str | None) -> str | None:
    declared = (workplace or "").lower().replace("-", "").replace("_", "").replace(" ", "")
    if declared in {"remote", "telecommute"}:
        return "remote"
    if declared == "hybrid":
        return "hybrid"
    if declared in {"onsite", "inperson", "office"}:
        return "in_person"
    loc = (location or "").lower()
    if "hybrid" in loc:
        return "hybrid"
    if "remote" in loc:
        return "remote"
    if text:
        for arrangement, pattern in ARRANGEMENT_WORDING:
            for m in re.finditer(pattern, text, re.I):
                # "The course will be a hybrid model" describes the training, not the job.
                if not ABOUT_TRAINING.search(_sentence_around(text, m.start(), m.end())):
                    return arrangement
    return None


AGE_RANGE = re.compile(r"\b(?:aged?|ages?)\s*(?:between\s*)?(\d{2})\s*(?:-|–|to|and)\s*(\d{2})\b", re.I)
AGE_MIN = re.compile(
    r"\b(?:must be|be at least|aged?|applicants? (?:must be )?(?:aged )?)\s*(?:at least\s*|over\s*)?(\d{2})\s*(?:\+|or (?:over|older|above)|years? (?:of age )?or (?:over|older))",
    re.I,
)
AGE_OVER = re.compile(r"\b(?:must be|be)\s*(?:over|at least)\s*(\d{2})(?:\s*years)?\b", re.I)
AGE_MAX = re.compile(r"\b(?:aged?|under|up to)\s*(\d{2})\s*(?:or under|or younger|and under)\b", re.I)


# Real adverts mention ages for pay, pensions and funding: "if you are aged 21 or over, your pay
# rises" and "pension for employees aged 22+" do not limit who can apply.
AGE_NOT_ELIGIBILITY = re.compile(
    r"\b(pay|paid|wages?|salary|per hour|hourly|an hour|£|pension|if you are|employees|funding|funded|levy|"
    r"grants?|incentive|bursary|residing|residents?|children|pupils|customers|clients|patients|volunteering|"
    r"supporting|support|help|helping|working with|who have|subject to)\b|£",
    re.I,
)
# A range caps the age too, and a wrong cap hides real opportunities, so it needs firmer wording.
AGE_RANGE_REQUIRED = re.compile(r"\b(must be|open to|only|restricted to)\b", re.I)
AGE_REQUIRED = re.compile(r"\b(must|applicants?|candidates?|essential|required|requirement|need to be|have to be|minimum age|young people)\b", re.I)


def _sentence_around(text: str, start: int, end: int) -> str:
    left = max(text.rfind(c, 0, start) for c in ".!?\n") + 1
    rights = [i for i in (text.find(c, end) for c in ".!?\n") if i != -1]
    return text[left:min(rights) if rights else len(text)]


def age_from(text: str | None) -> tuple[int | None, int | None, str | None]:
    """Only explicit statements about an applicant's age count, within plausible limits."""
    if not text:
        return None, None, None
    for pattern, kind in ((AGE_RANGE, "range"), (AGE_MIN, "min"), (AGE_OVER, "min"), (AGE_MAX, "max")):
        for m in pattern.finditer(text):
            numbers = [int(g) for g in m.groups()]
            if any(n < 13 or n > 70 for n in numbers):
                continue
            sentence = _sentence_around(text, m.start(), m.end())
            if AGE_NOT_ELIGIBILITY.search(sentence):
                continue
            # A bare "aged 18+" is too often a passing remark, so a limit must read as a requirement.
            if not (AGE_RANGE_REQUIRED if kind == "range" else AGE_REQUIRED).search(sentence):
                continue
            quote = m.group(0).strip()
            if kind == "range":
                return numbers[0], numbers[1], quote
            return (numbers[0], None, quote) if kind == "min" else (None, numbers[0], quote)
    return None, None, None


SALARY = re.compile(
    r"£\s?(\d[\d,]*(?:\.\d+)?)(k)?\s*(?:(?:-|–|to)\s*£?\s?(\d[\d,]*(?:\.\d+)?)(k)?)?"
    r"(?:\s*(?:per|a|/|p\.?)\s*(year|annum|yr|a\b|month|week|day|hour|hr))?",
    re.I,
)
PERIODS = {"year": "year", "annum": "year", "yr": "year", "a": "year", "month": "month",
           "week": "week", "day": "day", "hour": "hour", "hr": "hour"}
SALARY_CONTEXT = re.compile(r"salary|compensation|pay\b|paid|per annum|per hour|package|stipend|wage|\bOTE\b", re.I)
NOT_PAY = re.compile(r"\b(funding|raised|revenue|valuation|bonus|million|billion|investment|loans?|turnover)\b|£\s?\d[\d,.]*\s?(m|bn)\b", re.I)


def _parse_salary(sentence: str) -> dict | None:
    m = SALARY.search(sentence)
    if not m:
        return None
    low = float(m.group(1).replace(",", "")) * (1000 if m.group(2) else 1)
    high = float(m.group(3).replace(",", "")) * (1000 if m.group(4) else 1) if m.group(3) else None
    if m.group(3) and m.group(4) and not m.group(2) and low < 1000:
        low *= 1000  # "£30-35k"
    # The period stays None unless stated: an intern's "£50,000" may well be pro rata.
    period = PERIODS.get((m.group(5) or "").lower())
    if low < 5 or (period == "year" and low < 5000) or (not period and low < 1000):
        return None
    return {"min": low, "max": high, "period": period, "text": m.group(0).strip()}


def salary_from(text: str | None, title: str | None = None) -> dict | None:
    """Find a stated GBP salary. In a description, a figure counts only in a sentence that
    talks about pay. A figure in the job title is taken as pay."""
    if title and "£" in title and not NOT_PAY.search(title):
        found = _parse_salary(title)
        if found:
            return found
    if not text:
        return None
    for sentence in re.split(r"(?<=[.!?\n])\s+", text):
        if "£" not in sentence or not SALARY_CONTEXT.search(sentence) or NOT_PAY.search(sentence):
            continue
        found = _parse_salary(sentence)
        if found:
            return found
    return None


UNPAID = re.compile(r"\b(unpaid|voluntary (role|position)|expenses only)\b", re.I)


def is_paid_from(salary_known: bool, category: str, text: str | None) -> bool | None:
    if salary_known:
        return True
    if text and UNPAID.search(text):
        return False
    if text and re.search(r"\b(paid (internship|placement|role|programme)|competitive (salary|pay)|you will be paid)\b", text, re.I):
        return True
    # UK law requires employers to pay employees, so an ordinary job is paid even with no figure.
    if category in {"job", "entry_level_job", "graduate_scheme"}:
        return True
    return None
