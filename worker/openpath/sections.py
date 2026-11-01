"""Split a posting's HTML into the sections the detail page shows."""

import html as html_lib
import re

from bs4 import BeautifulSoup

SECTION_PATTERNS = {
    "responsibilities": r"responsib|what you('|’)?ll (do|be doing)|the role|your role|day[- ]to[- ]day|what you will do|your impact|you will",
    "requirements": r"requirement|what (we('|’)?re looking for|you('|’)?ll need|you need|we look for)|you (should )?have|about you|skills|qualifications|experience",
    "eligibility": r"eligib|who can apply|right to work|entry criteria|you must",
    "programme_info": r"programme|program\b|training|what you('|’)?ll learn|benefit|what we offer|perks",
}
HEADING_TAGS = ["h1", "h2", "h3", "h4", "h5", "h6"]
DURATION = re.compile(
    r"\b(\d{1,2}(?:\s*(?:-|–|to)\s*\d{1,2})?[- ](?:day|week|month|year)s?)(?:[- ]long)?\b"
    r"(?=[^.]{0,40}\b(programme|program|internship|placement|apprenticeship|scheme|contract|fixed[- ]term|duration|rotation)\b)"
    r"|\b(?:duration|lasts?|fixed[- ]term(?: contract)?(?: of| for)?)[:\s]+(\d{1,2}\s*(?:day|week|month|year)s?)\b",
    re.I,
)


def _unescape(raw: str) -> str:
    # Greenhouse double-encodes its HTML.
    return html_lib.unescape(raw) if "&lt;" in raw else raw


def to_text(raw_html: str | None) -> str | None:
    if not raw_html:
        return None
    soup = BeautifulSoup(_unescape(raw_html), "html.parser")
    for tag in soup(["script", "style"]):
        tag.decompose()
    for tag in soup.find_all(["p", "li", "div", "br", *HEADING_TAGS]):
        tag.append("\n")
    lines = [re.sub(r"[ \t\xa0]+", " ", line).strip() for line in soup.get_text().splitlines()]
    text = "\n".join(line for line in lines if line)
    return text or None


def _is_heading(el) -> bool:
    if el.name in HEADING_TAGS:
        return True
    if el.name == "p":
        text = el.get_text(" ", strip=True)
        strong = el.find(["strong", "b"])
        return bool(strong) and len(text) < 80 and strong.get_text(" ", strip=True) == text
    return False


def split_sections(raw_html: str | None) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {k: [] for k in SECTION_PATTERNS}
    if not raw_html:
        return result
    soup = BeautifulSoup(_unescape(raw_html), "html.parser")
    current: str | None = None
    for el in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6", "p", "li"]):
        if _is_heading(el):
            heading = el.get_text(" ", strip=True).lower()
            current = next((k for k, p in SECTION_PATTERNS.items() if re.search(p, heading)), None)
            continue
        if el.name == "p" and el.find_parent("li"):
            continue
        if current and el.name == "li":
            item = re.sub(r"\s+", " ", el.get_text(" ", strip=True))
            if 3 < len(item) < 500 and item not in result[current]:
                result[current].append(item)
    return result


def duration_from(text: str | None) -> str | None:
    if not text:
        return None
    m = DURATION.search(text)
    return (m.group(1) or m.group(3)) if m else None
