"""Resolve a Dutch address string to a Funda Listing."""
from __future__ import annotations

import re
import unicodedata

from funda import Funda, Listing


_POSTCODE = re.compile(r"\b(\d{4})\s*([A-Za-z]{2})\b")


def parse_address(address: str) -> dict:
    """Split a Dutch address like 'Ida Gerhardtstraat 13, 1321 PR Almere' into parts.

    Returns dict with keys: street, house_number, house_number_ext, postcode, city.
    """
    pc_match = _POSTCODE.search(address)
    if not pc_match:
        raise ValueError(f"Could not find Dutch postcode (1234 AB) in: {address!r}")

    postcode = (pc_match.group(1) + pc_match.group(2)).upper()
    before_pc = address[:pc_match.start()].rstrip(" ,")
    after_pc = address[pc_match.end():].strip(" ,")

    # before_pc looks like "Ida Gerhardtstraat 13"
    m = re.match(r"^(.+?)\s+(\d+)\s*([A-Za-z]?)$", before_pc.strip())
    if not m:
        raise ValueError(f"Could not parse street + number from: {before_pc!r}")
    street, number, ext = m.group(1).strip(), m.group(2), (m.group(3) or "").strip()

    return {
        "street": street,
        "house_number": int(number),
        "house_number_ext": ext or None,
        "postcode": postcode,
        "city": after_pc or None,
    }


def _norm(s: str) -> str:
    """Lowercase + strip diacritics for fuzzy matching."""
    nfkd = unicodedata.normalize("NFKD", s or "")
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower().strip()


def resolve_address(funda: Funda, address: str, max_pages: int = 4) -> Listing:
    """Find a listing on Funda matching the given address.

    Tries available + sold, paginating up to `max_pages` per status.
    Matches on normalised street name + exact house number.
    """
    parts = parse_address(address)
    pc_compact = parts["postcode"].replace(" ", "")
    target_street = _norm(parts["street"])
    target_number = parts["house_number"]

    for availability in (None, "sold"):
        for page in range(max_pages):
            results = funda.search_listing(
                location=pc_compact,
                radius_km=1,
                availability=availability,
                page=page,
            )
            if not results:
                break
            for r in results:
                title = _norm(r.get("title") or "")
                if not title.startswith(target_street):
                    continue
                # Title is "Streetname 13" — extract the number
                m = re.search(r"(\d+)", title[len(target_street):])
                if not m:
                    continue
                if int(m.group(1)) == target_number:
                    # Hydrate to full listing detail
                    return funda.get_listing(int(r.get("global_id")))

    raise LookupError(
        f"No Funda listing found for {address!r}. "
        "The property may never have been listed on Funda."
    )
