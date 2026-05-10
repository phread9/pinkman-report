"""CLI entry point: generate a Pinkman Report from a Dutch address.

Usage:
    uv run --extra report python .claude/skills/pinkman-report/generate.py \\
        "Ida Gerhardtstraat 13, 1321 PR Almere"

By default the PDF is written to `generated_reports/<address-slug>.pdf` in the
current working directory. Pass --output to override.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# Allow running as a script from anywhere — make sibling modules importable.
sys.path.insert(0, str(Path(__file__).parent))

from funda import Funda

from collector import collect_report_data
from render import render_report
from resolver import resolve_address


DEFAULT_OUTPUT_DIR = Path("generated_reports")


def slugify_address(address: str) -> str:
    """Turn an address into a filename-safe slug.

    'Ida Gerhardtstraat 13, 1321 PR Almere' → 'ida_gerhardtstraat_13_1321_pr_almere'
    """
    s = address.lower().strip()
    s = re.sub(r"[,/\\]", " ", s)
    s = re.sub(r"\s+", "_", s)
    s = re.sub(r"[^a-z0-9_-]", "", s)
    return s.strip("_") or "report"


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a property report PDF from a Dutch address.")
    parser.add_argument("address", help="Full address, e.g. 'Ida Gerhardtstraat 13, 1321 PR Almere'")
    parser.add_argument(
        "-o", "--output",
        default=None,
        help=f"Output PDF path (default: {DEFAULT_OUTPUT_DIR}/<address-slug>.pdf)",
    )
    args = parser.parse_args()

    if args.output:
        output_path = Path(args.output)
    else:
        output_path = DEFAULT_OUTPUT_DIR / f"{slugify_address(args.address)}.pdf"

    print(f"→ Resolving {args.address!r}...", flush=True)
    with Funda() as funda:
        try:
            listing = resolve_address(funda, args.address)
        except (ValueError, LookupError) as e:
            print(f"✗ {e}", file=sys.stderr)
            return 1

        print(f"  found: {listing.get('title')} — €{listing.get('price'):,} (tinyId {listing.get('tiny_id')})", flush=True)
        print("→ Collecting price history + comparable sales...", flush=True)
        data = collect_report_data(funda, listing)
        print(f"  {len(data['history'])} price points, {len(data['comps'])} comps", flush=True)

    print(f"→ Rendering PDF...", flush=True)
    output = render_report(data, output_path)
    print(f"✓ Written: {output}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
