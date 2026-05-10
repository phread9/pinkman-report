"""Render report data through Jinja2 + WeasyPrint to PDF."""
from __future__ import annotations

import re
from datetime import date, datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from weasyprint import HTML

from avm import estimate_value
from translations import translate_date, translate_house_type


TEMPLATE_DIR = Path(__file__).parent / "templates"
SEARCH_RADIUS_KM = 5
HISTORY_YEARS = 5  # cap how far back the price history table goes


# Dutch energy-label scale, top → bottom (most efficient → least).
# Used to render the colored chip on the property-details page.
ENERGY_LABEL_RANK = [
    "A++++", "A+++", "A++", "A+", "A", "B", "C", "D", "E", "F", "G",
]


def _energy_label_class(label: str | None) -> str:
    """Normalise a label like 'A+++' into a CSS-friendly class suffix."""
    if not label:
        return "unknown"
    cleaned = label.strip().upper().replace(" ", "")
    plus_count = cleaned.count("+")
    base = cleaned.replace("+", "")
    if plus_count:
        return f"{base.lower()}-plus-{plus_count}"
    return base.lower()


_DUTCH_DATE = re.compile(r"(\d{1,2})\s+([A-Za-z]+)[\.,]?\s+(\d{4})")
_DUTCH_MONTH = {
    "jan": 1, "feb": 2, "mrt": 3, "apr": 4, "mei": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "okt": 10, "nov": 11, "dec": 12,
}


def _parse_history_year(entry: dict) -> int | None:
    """Extract a year from a history entry — prefer ISO timestamp, fall back to date string."""
    ts = entry.get("timestamp")
    if ts:
        try:
            return datetime.fromisoformat(ts.replace("Z", "+00:00")).year
        except ValueError:
            pass
    date_str = entry.get("date") or ""
    m = _DUTCH_DATE.search(date_str)
    if m:
        return int(m.group(3))
    return None


def _filter_recent_history(history: list[dict], years: int) -> list[dict]:
    """Keep only entries from the last `years` calendar years."""
    current_year = date.today().year
    cutoff = current_year - years
    out = []
    for h in history:
        y = _parse_history_year(h)
        if y is None or y >= cutoff:
            out.append(h)
    return out


def _annotate_history_deltas(history: list[dict]) -> list[dict]:
    """Add YoY-style delta_pct relative to the next-older entry of the same kind."""
    out = []
    last_by_status: dict[str, float] = {}
    chronological = list(reversed(history))
    deltas: dict[int, float | None] = {}
    for i, h in enumerate(chronological):
        status = h.get("status")
        price = h.get("price")
        prev = last_by_status.get(status)
        if prev and price:
            deltas[i] = ((price - prev) / prev) * 100
        else:
            deltas[i] = None
        if price:
            last_by_status[status] = price

    for i, h in enumerate(chronological):
        h2 = dict(h)
        h2["delta_pct"] = deltas[i]
        out.append(h2)
    out.reverse()
    return out


def _localize_subject(subject: dict) -> dict:
    """Replace Dutch fields on the subject with English versions."""
    s = dict(subject)
    s["house_type"] = translate_house_type(s.get("house_type"))
    s["offered_since"] = translate_date(s.get("offered_since"))
    return s


def _localize_comps(comps: list[dict]) -> list[dict]:
    out = []
    for c in comps:
        c2 = dict(c)
        c2["house_type"] = translate_house_type(c.get("house_type"))
        c2["offered_since"] = translate_date(c.get("offered_since"))
        out.append(c2)
    return out


def _localize_history(history: list[dict]) -> list[dict]:
    out = []
    for h in history:
        h2 = dict(h)
        h2["date"] = translate_date(h.get("date"))
        out.append(h2)
    return out


def render_report(
    report_data: dict,
    output_path: str | Path,
) -> Path:
    """Render the report to PDF and return the output path."""
    subject = _localize_subject(report_data["subject"])
    history = report_data["history"]
    comps = _localize_comps(report_data["comps"])
    # AVM uses a wider pool (listed + sold combined) to reduce sample variance.
    # Falls back to the displayed comps if the collector didn't provide a pool.
    avm_comps = _localize_comps(report_data.get("avm_comps") or report_data["comps"])

    avm = estimate_value(subject, avm_comps)
    history_recent = _filter_recent_history(history, HISTORY_YEARS)
    history_with_deltas = _localize_history(_annotate_history_deltas(history_recent))

    # Simple average €/m² across the comps shown — surfaced as a summary
    # row at the bottom of the "Recently Listed" table.
    valid_ppm = [c["price_per_m2"] for c in comps if c.get("price_per_m2")]
    comps_avg_ppm = sum(valid_ppm) / len(valid_ppm) if valid_ppm else None

    env = Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIR)),
        autoescape=select_autoescape(["html"]),
    )
    template = env.get_template("report.html")
    html_str = template.render(
        subject=subject,
        history=history_with_deltas,
        history_years=HISTORY_YEARS,
        comps=comps,
        comps_avg_ppm=comps_avg_ppm,
        avm=avm,
        search_radius_km=SEARCH_RADIUS_KM,
        generated_on=date.today().strftime("%B %-d, %Y"),
        energy_label_class=_energy_label_class(subject.get("energy_label")),
    )

    output_path = Path(output_path).expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    HTML(string=html_str, base_url=str(TEMPLATE_DIR)).write_pdf(str(output_path))
    return output_path
