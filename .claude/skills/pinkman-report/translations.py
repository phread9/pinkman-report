"""Dutch → English translations for fields surfaced in the report."""
from __future__ import annotations

import re


HOUSE_TYPE = {
    "eengezinswoning": "Single-family home",
    "tussenwoning": "Terraced house",
    "hoekwoning": "Corner house",
    "geschakelde woning": "Linked house",
    "twee-onder-een-kapwoning": "Semi-detached house",
    "tweekapper": "Semi-detached house",
    "vrijstaande woning": "Detached house",
    "vrijstaand": "Detached house",
    "appartement": "Apartment",
    "herenhuis": "Townhouse",
    "bungalow": "Bungalow",
    "villa": "Villa",
    "woonhuis": "House",
    "portiekwoning": "Walk-up apartment",
    "galerijflat": "Gallery flat",
    "maisonnette": "Maisonette",
    "studio": "Studio",
}

OBJECT_TYPE = {
    "House": "House",
    "Apartment": "Apartment",
    "house": "House",
    "apartment": "Apartment",
}

# Dutch month abbreviations / full names → English
DUTCH_MONTHS = {
    "januari": "January", "februari": "February", "maart": "March",
    "april": "April", "mei": "May", "juni": "June", "juli": "July",
    "augustus": "August", "september": "September", "oktober": "October",
    "november": "November", "december": "December",
    "jan": "Jan", "feb": "Feb", "mrt": "Mar", "apr": "Apr",
    "jun": "Jun", "jul": "Jul", "aug": "Aug", "sep": "Sep",
    "okt": "Oct", "nov": "Nov", "dec": "Dec",
}


def translate_house_type(value: str | None) -> str | None:
    if not value:
        return None
    key = value.strip().lower()
    return HOUSE_TYPE.get(key, value.capitalize())


def translate_date(value: str | None) -> str | None:
    """Replace Dutch month names in a date string with English equivalents.

    'Mei 1, 2026' → 'May 1, 2026'
    '1 jan, 2026' → '1 Jan, 2026'
    """
    if not value:
        return value
    out = value
    # Sort by length so longer names ("oktober") match before shorter ("okt")
    for nl, en in sorted(DUTCH_MONTHS.items(), key=lambda kv: -len(kv[0])):
        out = re.sub(rf"(?i)\b{re.escape(nl)}\b", en, out)
    # Title-case the first letter if the original was capitalised
    if value and value[0].isupper():
        out = out[:1].upper() + out[1:]
    return out
