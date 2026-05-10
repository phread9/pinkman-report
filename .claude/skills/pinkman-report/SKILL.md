---
name: pinkman-report
description: Generate a Pinkman Report — a free open-source PDF property report for a Dutch home. Use when the user provides a Netherlands street address (e.g. "Ida Gerhardtstraat 13, 1321 PR Almere") and wants a property valuation report PDF. Pulls listing data, price history, and comparable sales from Funda via pyfunda, runs a comp-based AVM, and renders to PDF with WeasyPrint.
---

# pinkman-report

Generates a polished property report PDF for any Dutch address: cover page, property details, price/WOZ history, estimated market value with condition scenarios, and recently listed comps. The estimated market value typically lands within ~3% of leading paid services — the gap is structural (paid services pull from Kadaster's full transaction history; we use Funda's listed + recently-sold pool).

## Inputs

A single Dutch address string with street + house number + postcode + city. Example:

```
Ida Gerhardtstraat 13, 1321 PR Almere
```

The postcode is required (Dutch format `1234 AB`); city is optional, used only as a sanity check.

## How to invoke

```bash
uv run --extra report python .claude/skills/pinkman-report/generate.py \
    "Ida Gerhardtstraat 13, 1321 PR Almere"
```

By default the PDF is written to `generated_reports/<address-slug>.pdf` (e.g. `generated_reports/ida_gerhardtstraat_13_1321_pr_almere.pdf`). Pass `--output path.pdf` to override.

The `--extra report` flag pulls in `weasyprint` and `jinja2` (declared as an optional extra in `pyproject.toml` so pyfunda's core install stays light).

## What the report contains

1. **Cover** — address, list price, year built, energy label
2. **Table of contents** — clickable links to each section with auto-resolved page numbers
3. **Property details** — type, list price, year built, energy label, bedrooms, livable area, lot area
4. **Price history** — past asking prices and yearly WOZ municipal valuations with YoY deltas (last 5 years)
5. **Estimated market value** — comp-based AVM central estimate + four condition scenarios ("Looks new" through "Needs maintenance")
6. **Recently listed in the area** — up to 8 currently-listed comparable properties, sorted by distance, with list price and €/m². Ends with a summary row showing the local market average €/m².

## Architecture

```
.claude/skills/pinkman-report/
  SKILL.md           ← this file
  generate.py        ← CLI entry point
  resolver.py        ← address string → Funda Listing
  collector.py       ← gathers listing detail + history + comps
  avm.py             ← comp-based valuation logic
  render.py          ← Jinja2 + WeasyPrint → PDF
  templates/
    report.html      ← document structure
    styles.css       ← print stylesheet (A4)
```

The flow:

```
address  →  resolver  →  Listing
           ↓
           collector  →  {subject, history, comps, neighborhood_stats}
           ↓
           avm        →  central_value + scenarios + bid_summary
           ↓
           render     →  PDF
```

## Known limitations

- **Sale prices are unavailable.** Funda exposes asking prices only — no realised sale prices. The "Estimated value today" column for each comp is computed from the neighborhood median €/m², not from actual transaction data.
- **The property must have been listed on Funda** at some point (currently or sold). Properties never listed (long-term owner-occupied) cannot be resolved.
- **Comp pool is bounded.** The collector hydrates up to ~32 candidate listings to find 8 valid comps; large API runs are intentionally avoided to keep generation under ~30 seconds.
- **No historical market trend chart.** Funda's index doesn't keep sold listings going back many years, so we show a current-snapshot of the market only.

## When to use

Trigger this skill when the user:
- Pastes a Dutch address and asks for a valuation, report, or PDF
- Says "generate a Pinkman Report" / "make me a property report"
- Asks for comparable sales analysis on a specific property
