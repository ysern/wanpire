"""Rebuild wanpire's shipped path table from a cloud backbone's published round trips.

The source is the "network round-trip latency statistics" page of a public cloud's
documentation, whose source repository is licensed CC BY 4.0. The page ends with the whole
matrix as CSV (source region in the first column, destination regions across). Download the
page's Markdown source and run:

    python tools/import_backbone_rtt.py <page.md> src/wanpire/data/paths/backbone-rtt.json

Each site's coordinates below are its metro area's, approximate to a few tens of kilometres:
enough for a great-circle distance, which is all they are used for. A region the page adds
later and this list lacks is reported, and left out until it is given coordinates here.
"""

from __future__ import annotations

import csv
import io
import json
import re
import sys

SOURCE = {
    "name": "Microsoft Azure documentation, \"Azure network round-trip latency statistics\"",
    "url": "https://learn.microsoft.com/azure/networking/azure-network-latency",
    "source_repository": "https://github.com/MicrosoftDocs/azure-docs "
                         "(articles/networking/azure-network-latency.md)",
    "licence": "CC-BY-4.0",
    "attribution": "Round-trip figures from \"Azure network round-trip latency statistics\", "
                   "Microsoft, licensed under CC BY 4.0 "
                   "(https://creativecommons.org/licenses/by/4.0/). wanpire changed them: "
                   "regions are mapped to approximate coordinates and the matrix is re-shaped "
                   "to JSON.",
    "measure": "monthly P50 round trip between data centre regions on one backbone, "
               "probed every minute; directional",
}

# name in the source -> (site id, metro, latitude, longitude, world region)
SITES = {
    "Australia Central": ("au-central", "Canberra", -35.31, 149.13, "oceania"),
    "Australia Central 2": ("au-central-2", "Canberra", -35.31, 149.13, "oceania"),
    "Australia East": ("au-east", "Sydney", -33.87, 151.21, "oceania"),
    "Australia Southeast": ("au-southeast", "Melbourne", -37.81, 144.96, "oceania"),
    "Austria East": ("at-east", "Vienna", 48.21, 16.37, "europe"),
    "Belgium Central": ("be-central", "Brussels", 50.85, 4.35, "europe"),
    "Brazil South": ("br-south", "Sao Paulo", -23.55, -46.63, "south-america"),
    "Canada Central": ("ca-central", "Toronto", 43.65, -79.38, "north-america"),
    "Canada East": ("ca-east", "Quebec City", 46.81, -71.21, "north-america"),
    "Central India": ("in-central", "Pune", 18.52, 73.86, "south-asia"),
    "Central US": ("us-central", "Des Moines", 41.59, -93.62, "north-america"),
    "Denmark East": ("dk-east", "Copenhagen", 55.68, 12.57, "europe"),
    "East Asia": ("hk", "Hong Kong", 22.32, 114.17, "east-asia"),
    "East US": ("us-east", "Northern Virginia", 38.95, -77.45, "north-america"),
    "East US 2": ("us-east-2", "Southern Virginia", 36.67, -78.39, "north-america"),
    "France Central": ("fr-central", "Paris", 48.86, 2.35, "europe"),
    "France South": ("fr-south", "Marseille", 43.30, 5.37, "europe"),
    "Germany North": ("de-north", "Berlin", 52.52, 13.40, "europe"),
    "Germany West Central": ("de-west-central", "Frankfurt", 50.11, 8.68, "europe"),
    "Indonesia Central": ("id-central", "Jakarta", -6.21, 106.85, "southeast-asia"),
    "Israel Central": ("il-central", "Tel Aviv", 32.09, 34.78, "middle-east"),
    "Italy North": ("it-north", "Milan", 45.46, 9.19, "europe"),
    "Japan East": ("jp-east", "Tokyo", 35.68, 139.77, "east-asia"),
    "Japan West": ("jp-west", "Osaka", 34.69, 135.50, "east-asia"),
    "Jio India West": ("in-west-2", "Jamnagar", 22.47, 70.06, "south-asia"),
    "Korea Central": ("kr-central", "Seoul", 37.57, 126.98, "east-asia"),
    "Korea South": ("kr-south", "Busan", 35.18, 129.08, "east-asia"),
    "Malaysia West": ("my-west", "Kuala Lumpur", 3.14, 101.69, "southeast-asia"),
    "Mexico Central": ("mx-central", "Queretaro", 20.59, -100.39, "north-america"),
    "New Zealand North": ("nz-north", "Auckland", -36.85, 174.76, "oceania"),
    "North Central US": ("us-north-central", "Chicago", 41.88, -87.63, "north-america"),
    "North Europe": ("eu-north", "Dublin", 53.35, -6.26, "europe"),
    "Norway East": ("no-east", "Oslo", 59.91, 10.75, "europe"),
    "Norway West": ("no-west", "Stavanger", 58.97, 5.73, "europe"),
    "Poland Central": ("pl-central", "Warsaw", 52.23, 21.01, "europe"),
    "Qatar Central": ("qa-central", "Doha", 25.29, 51.53, "middle-east"),
    "South Africa North": ("za-north", "Johannesburg", -26.20, 28.05, "africa"),
    "South Africa West": ("za-west", "Cape Town", -33.92, 18.42, "africa"),
    "South Central US": ("us-south-central", "San Antonio", 29.42, -98.49, "north-america"),
    "South India": ("in-south", "Chennai", 13.08, 80.27, "south-asia"),
    "Southeast Asia": ("sg", "Singapore", 1.35, 103.82, "southeast-asia"),
    "Spain Central": ("es-central", "Madrid", 40.42, -3.70, "europe"),
    "Sweden Central": ("se-central", "Gavle", 60.67, 17.14, "europe"),
    "Switzerland North": ("ch-north", "Zurich", 47.38, 8.54, "europe"),
    "Switzerland West": ("ch-west", "Geneva", 46.20, 6.14, "europe"),
    "UAE Central": ("ae-central", "Abu Dhabi", 24.45, 54.38, "middle-east"),
    "UAE North": ("ae-north", "Dubai", 25.20, 55.27, "middle-east"),
    "UK South": ("uk-south", "London", 51.51, -0.13, "europe"),
    "UK West": ("uk-west", "Cardiff", 51.48, -3.18, "europe"),
    "West Central US": ("us-west-central", "Cheyenne", 41.14, -104.82, "north-america"),
    "West Europe": ("eu-west", "Amsterdam", 52.37, 4.90, "europe"),
    "West US": ("us-west", "San Francisco Bay Area", 37.78, -122.42, "north-america"),
    "West US 2": ("us-west-2", "Central Washington", 47.23, -119.85, "north-america"),
    "West US 3": ("us-west-3", "Phoenix", 33.45, -112.07, "north-america"),
}


def parse(markdown: str) -> tuple[str, list[list[str]]]:
    date = re.search(r"dataset dates from \*([^*]+)\*", markdown)
    block = re.search(r"```csv\n(.*?)```", markdown, re.S)
    if not block:
        raise SystemExit("no ```csv block found in the page")
    rows = list(csv.reader(io.StringIO(block.group(1))))
    return (date.group(1) if date else "unknown"), rows


def build(markdown: str) -> dict:
    date, rows = parse(markdown)
    header = rows[0][1:]
    missing = sorted(({r[0] for r in rows[1:]} | set(header)) - set(SITES))
    if missing:
        print(f"left out, no coordinates: {', '.join(missing)}", file=sys.stderr)
    rtt: dict[str, dict[str, float]] = {}
    for row in rows[1:]:
        if row[0] not in SITES:
            continue
        src = SITES[row[0]][0]
        for name, cell in zip(header, row[1:]):
            if cell.strip() and name in SITES:
                rtt.setdefault(src, {})[SITES[name][0]] = float(cell)
    sites = {
        sid: {"source_name": name, "metro": metro, "lat": lat, "lon": lon, "region": region}
        for name, (sid, metro, lat, lon, region) in SITES.items()
    }
    return {
        "schema": "wanpire-path-table/1",
        "source": {**SOURCE, "dataset_date": date},
        "sites": sites,
        "rtt_ms": rtt,
    }


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print(__doc__, file=sys.stderr)
        return 2
    with open(argv[1], encoding="utf-8") as f:
        table = build(f.read())
    with open(argv[2], "w", encoding="utf-8", newline="\n") as f:
        json.dump(table, f, indent=1, ensure_ascii=False)
        f.write("\n")
    n = sum(len(v) for v in table["rtt_ms"].values())
    print(f"{len(table['sites'])} sites, {n} directional figures, "
          f"dataset {table['source']['dataset_date']}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
