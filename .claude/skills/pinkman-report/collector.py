"""Collect all data needed to build a Pinkman Report."""
from __future__ import annotations

import math
from typing import Any

from funda import Funda, Listing


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def _safe_history(funda: Funda, listing: Listing) -> list[dict]:
    try:
        return funda.get_price_history(listing)
    except Exception:
        return []


def collect_comps(
    funda: Funda,
    subject: Listing,
    *,
    n_target: int = 8,
    radius_km: int = 5,
    area_tolerance: float = 0.25,
    year_tolerance: int = 12,
    availability: str | None = None,
) -> list[dict]:
    """Find comps similar to the subject, hydrate with full detail, sort by distance.

    `availability=None` returns currently-listed comps (default).
    `availability="sold"` returns recently-sold comps.

    Returns a list of dicts (not Listing objects) augmented with `distance_km`.
    """
    subj_area = subject.get("living_area")
    subj_year = subject.get("construction_year")
    subj_lat = subject.get("latitude")
    subj_lon = subject.get("longitude")
    subj_postcode = (subject.get("postcode") or "").replace(" ", "")
    subj_object_type = subject.get("object_type")  # "House" or "Apartment"

    if not subj_area:
        raise ValueError("Subject listing has no living_area; cannot find similar comps.")

    area_min = max(40, int(subj_area * (1 - area_tolerance)))
    area_max = int(subj_area * (1 + area_tolerance))

    object_type_filter = None
    if subj_object_type:
        object_type_filter = ["house"] if subj_object_type.lower() == "house" else ["apartment"]

    # Pull a generous pool of comps (listed by default, or sold).
    pool: list[Listing] = []
    seen_ids: set[int] = set()
    for page in range(6):
        batch = funda.search_listing(
            location=subj_postcode,
            radius_km=radius_km,
            availability=availability,
            area_min=area_min,
            area_max=area_max,
            object_type=object_type_filter,
            page=page,
        )
        if not batch:
            break
        new_in_batch = 0
        for r in batch:
            gid = r.get("global_id")
            if gid and gid not in seen_ids:
                seen_ids.add(gid)
                pool.append(r)
                new_in_batch += 1
        if new_in_batch == 0:
            break

    # Hydrate each candidate to get coordinates + year built + lot area.
    # Cap how many we hydrate to keep API calls bounded.
    candidates: list[dict] = []
    subject_id = subject.get("global_id")
    for r in pool[: n_target * 4]:
        gid = r.get("global_id")
        if gid == subject_id:
            continue
        try:
            full = funda.get_listing(int(gid))
        except Exception:
            continue

        # Skip if year wildly different
        year = full.get("construction_year")
        if subj_year and year and abs(year - subj_year) > year_tolerance:
            continue

        lat = full.get("latitude")
        lon = full.get("longitude")
        dist = None
        if lat and lon and subj_lat and subj_lon:
            dist = haversine_km(subj_lat, subj_lon, lat, lon)

        # Last sold-history asking price as the "list price" if available
        history = _safe_history(funda, full)
        list_price = full.get("price")  # fallback
        for h in history:
            if h.get("status") == "asking_price":
                list_price = h.get("price") or list_price
                break

        # Broker name only appears in search results (`r`), not in get_listing()
        broker_name = r.get("broker_name") or r.get("broker")

        candidates.append({
            "global_id": full.get("global_id"),
            "title": full.get("title"),
            "postcode": full.get("postcode"),
            "city": full.get("city"),
            "neighbourhood": full.get("neighbourhood"),
            "url": full.get("url"),
            "list_price": list_price,
            "living_area": full.get("living_area"),
            "plot_area": full.get("plot_area"),
            "construction_year": year,
            "object_type": full.get("object_type"),
            "house_type": full.get("house_type"),
            "energy_label": full.get("energy_label"),
            "broker_id": full.get("broker_id"),
            "broker_name": broker_name,
            "broker_association": full.get("broker_association"),
            "distance_km": dist,
            "price_per_m2": (list_price / full.get("living_area")) if list_price and full.get("living_area") else None,
            "offered_since": full.get("offered_since"),
            "publish_date": r.get("publish_date"),
        })

    # Sort by distance (None last), then keep best n_target
    candidates.sort(key=lambda c: (c["distance_km"] is None, c["distance_km"] or 1e9))
    return candidates[:n_target]


def collect_report_data(funda: Funda, subject: Listing) -> dict[str, Any]:
    """Gather every piece of data the report template needs.

    Two comp pools are collected:
    - `comps`     — currently listed nearby properties, shown in the table
    - `avm_comps` — combined listed + sold comps, used for the AVM math

    Combining both pools for the AVM reduces sample variance: 8 comps from a
    single pool can swing the central estimate by 3-4% based on which closest
    comp happens to be in the sample. ~16 comps tightens that noise.
    """
    history = _safe_history(funda, subject)

    listed_comps = collect_comps(funda, subject, availability=None)
    sold_comps = collect_comps(funda, subject, availability="sold")

    # Combine pools for AVM, deduping by global_id (a property can't be both
    # listed and sold at the same time, but defensive dedup is cheap).
    seen_ids = {c.get("global_id") for c in listed_comps if c.get("global_id")}
    avm_comps = list(listed_comps) + [
        c for c in sold_comps if c.get("global_id") not in seen_ids
    ]

    return {
        "subject": dict(subject.to_dict()) if hasattr(subject, "to_dict") else dict(subject),
        "history": history,
        "comps": listed_comps,
        "avm_comps": avm_comps,
    }
