import re
from html import unescape
from urllib.parse import urlsplit, urlunsplit


def clean_text(value) -> str:
    if value is None:
        return ""
    text = unescape(str(value))
    text = re.sub(r"<[^>]+>", " ", text)
    return " ".join(text.split())


def normalize_company(value) -> str:
    return clean_text(value).strip(" ,.;")


def normalize_location(value) -> str:
    return clean_text(value).strip(" ,.;")


def normalize_url(value) -> str:
    url = clean_text(value)
    parts = urlsplit(url)
    if parts.scheme.lower() not in {"http", "https"} or not parts.netloc:
        return ""
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip("/"), parts.query, ""))


def normalize_skills(values) -> list[str]:
    if isinstance(values, str):
        values = re.split(r"[,;|]", values)
    if not isinstance(values, (list, tuple, set)):
        return []
    seen = set()
    result = []
    for value in values:
        skill = clean_text(value).strip(" ,.;")
        key = skill.casefold()
        if skill and key not in seen:
            result.append(skill)
            seen.add(key)
    return result
