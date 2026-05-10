# Pinkman Report

A free, open-source PDF property report for any Dutch home. No subscription, no €250 "success fee," no €40/month dashboard. Pass an address — get a polished, data-driven valuation report.

The estimated market value typically lands within ~3% of leading paid services. The remaining gap is structural — paid services have access to Kadaster's full transaction history, we use Funda's listed + recently-sold pool. See [Limitations](#limitations).

> If you find this useful, consider giving it a star — it helps others discover the project.

## Why this exists

There's a new "AI-powered housing finder" every week, charging €40/month or a €250 success fee for a PDF. They all pull from the same one or two sources and wrap it in a fancy UI. The data is public. The math is comparable sales × neighborhood €/m². You shouldn't have to pay someone to refresh a webpage for you.

Here's the code, do it yourself.

## Prerequisites

You need three things on your machine:

| | Tool | Why | Install |
|---|---|---|---|
| 1 | **Python ≥ 3.10** | runtime | macOS ships it; otherwise [python.org](https://www.python.org/downloads/) |
| 2 | **uv** | Python package manager | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| 3 | **Pango** | PDF rendering library used by WeasyPrint | see below |

### Installing Pango

WeasyPrint generates the PDF and needs Pango for font/text layout. One command, varies by platform:

```bash
# macOS (Homebrew)
brew install pango

# Ubuntu / Debian
sudo apt install libpango-1.0-0 libpangoft2-1.0-0

# Fedora
sudo dnf install pango

# Arch
sudo pacman -S pango
```

That's it.

## Setup

```bash
# Clone
git clone <repo-url> pinkman-report
cd pinkman-report

# Install Python dependencies (one-time)
uv sync --extra report
```

`uv sync` reads `pyproject.toml` and installs everything into a local `.venv/`. The `--extra report` flag pulls in `weasyprint` + `jinja2` on top of the core pyfunda deps.

## Generate a report

This project ships as a [Claude Code](https://claude.com/claude-code) skill at `.claude/skills/pinkman-report/`. Open the repo in Claude Code and run:

```
/pinkman-report "Ida Gerhardtstraat 13, 1321 PR Almere"
```

Claude Code picks up the skill automatically and runs the pipeline. ~10 seconds later you have a PDF.

By default the file lands at:

```
generated_reports/ida_gerhardtstraat_13_1321_pr_almere.pdf
```

The directory is created automatically. The address must include a Dutch postcode (`1234 AB`); the property must have appeared on Funda at some point so the resolver can find it.

### Without Claude Code

If you're not using Claude Code, run the underlying script directly:

```bash
uv run --extra report python .claude/skills/pinkman-report/generate.py \
    "Ida Gerhardtstraat 13, 1321 PR Almere"
```

Same output, same default path. Pass `-o some/path.pdf` to override.

## What's in the report

A 6-page A4 PDF:

1. **Cover** — address, list price, year built, energy label
2. **Table of contents** — clickable jumps to each section
3. **Property details** — type, list price, year built, energy label, bedrooms, livable area, lot
4. **Price history** — past asking prices and yearly WOZ municipal valuations with year-over-year change (last 5 years)
5. **Estimated market value** — comp-based central estimate plus four condition scenarios (Looks new / Good / Reasonable / Needs maintenance)
6. **Recently listed in the area** — up to 8 currently-listed nearby comparable properties, sorted by distance, with list price and €/m². Ends with a summary row: the local market average €/m².

## How it works

The pipeline is plain Python (~600 lines), self-contained in `.claude/skills/pinkman-report/`:

```
address  →  resolver    parse + postcode-radius search + street/number match → Listing
         →  collector   listing detail + price history + ~8 nearby listed comps
         →  avm         distance-weighted mean €/m² × living_area = central estimate
         →  render      Jinja2 template + WeasyPrint → A4 PDF
```

1. **Resolve.** Parse the address, search Funda's mobile API by postcode, match the exact street + house number → recover the listing.
2. **Collect.** Fetch the full listing detail, pull price + WOZ history from Funda's price-history endpoint, and search nearby currently-listed properties filtered to similar size (±25%) and construction year (±12 years). Hydrate each comp for coordinates, lot area, and broker.
3. **Rank.** Sort comps by haversine distance from the subject; keep the closest 8.
4. **Value.** Compute the inverse-distance-squared weighted mean of comp €/m² × the subject's living area = central estimate. Closer comps dominate the result. Apply linear adjustments for the four condition tiers (1.025× / 1.000× / 0.975× / 0.925×).
5. **Render.** Pipe the data through a Jinja2 template into WeasyPrint → PDF.

Dependencies: [`pyfunda`](https://github.com/0xMH/pyfunda), `weasyprint`, `jinja2`. No ML model, no proprietary data, no subscription.

## Examples

In Claude Code:

```
/pinkman-report "Ida Gerhardtstraat 13, 1321 PR Almere"
/pinkman-report "Vondelstraat 1, 1054 GA Amsterdam"
/pinkman-report "Witte de Withstraat 5, 3012 BP Rotterdam"
```

Each run writes to `generated_reports/<address-slug>.pdf`.

Without Claude Code, the equivalent CLI form:

```bash
uv run --extra report python .claude/skills/pinkman-report/generate.py \
    "Vondelstraat 1, 1054 GA Amsterdam" \
    -o ~/Desktop/vondelstraat.pdf
```

## Limitations

- **Valuation is typically ~3% off paid services.** Paid valuation platforms have B2B access to Kadaster (the Dutch national land registry) and pull from 25+ historical transactions per valuation. We use Funda's currently-listed pool plus the recently-sold rolling window — at most 16 comps. With fewer comps the central €/m² has more sample variance, which translates to a uniform ~2–3% offset on the final number across all condition tiers. The math, multipliers, and tier ratios are correct; only the central €/m² shifts.
- **Sale prices are unavailable.** Funda exposes asking prices only — no realised sale prices. We use currently-listed comps as the market anchor.
- **The property must have been listed on Funda.** Properties never listed (long-term owner-occupied) cannot be resolved by address.
- **Comp pool is bounded.** The collector hydrates up to ~32 candidate listings per pool to keep generation under ~30 seconds.
- **No multi-year market trend chart.** Funda's index doesn't keep sold listings going back many years, so we show a current-snapshot of the market only.

## Built on pyfunda

This project is a fork of [pyfunda](https://github.com/0xMH/pyfunda), the Python wrapper for Funda's mobile API. All the heavy lifting of authenticating against Funda, matching TLS fingerprints, and parsing 70+ fields per listing lives there.

For details on the underlying API, request flow, available filters, and direct usage, see the upstream pyfunda README.

## Disclaimer

This is an unofficial tool and is not affiliated with, authorized, maintained, sponsored, or endorsed by Funda or any of its affiliates. Use at your own risk.

This project only accesses publicly available listing data through Funda's undocumented internal API. Use may violate Funda's Terms of Service. The authors are not responsible for any consequences of using this software.

This project is intended for personal use, research, and educational purposes only.

- The API is undocumented and may change or break at any time without notice.
- Please use responsibly and avoid excessive requests that could burden Funda's infrastructure.
- Scraped data may be subject to copyright and usage restrictions. Ensure your use complies with applicable laws.
- This is vibe-coded so use at your own risk cause am not gonna read python and CSS in 2026

## License

AGPL-3.0
