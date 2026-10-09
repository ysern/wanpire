"""Write wanpire's starter endpoint presets (src/wanpire/data/endpoints/*.json).

Each city's *generic* channel is measured: the access delay and the bandwidth come from
M-Lab's NDT city statistics (CC0), the daily medians of 2024-01-01 to 2024-03-26 (the last
period that statistics service publishes), summarised by their median. Its jitter and loss are
not in those statistics and are wanpire's estimates.

Every other channel is a *kind* of access with wanpire's own typical figures, the same in
every city, each with the reasoning that gives it. They are estimates, stated as such; better
figures with a redistributable source are welcome.

No provider is named: a channel is a generic kind.

    python tools/make_endpoints.py                 # write the presets from the figures below
    python tools/make_endpoints.py --mlab <dir>    # print the summary of downloaded M-Lab files

For --mlab, download each city's
https://statistics.measurementlab.net/v0/<continent>/<country>/<region>/<city>/2024/histogram_daily_stats.json
into <dir> as <City>.json.
"""

from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "src/wanpire/data/endpoints"
MLAB_PERIOD = ("2024-01-01", "2024-03-26")
MLAB_CITATION = ("The M-Lab NDT Data Set, 2024-01-01 to 2024-03-26, via the M-Lab statistics "
                 "service. https://www.measurementlab.net/tests/ndt/")

# id: (name, lat, lon, country, region, M-Lab path, (download Mbit/s, upload Mbit/s, min RTT ms))
CITIES = {
    "london": ("London", 51.507, -0.128, "GB", "europe",
               "EU/GB/GB-ENG/London", (50.9, 8.9, 5.6)),
    "los-angeles": ("Los Angeles", 34.052, -118.244, "US", "north-america",
                    "NA/US/US-CA/Los Angeles", (66.9, 10.5, 11.8)),
    "new-york": ("New York", 40.713, -74.006, "US", "north-america",
                 "NA/US/US-NY/New York", (69.2, 11.6, 6.0)),
    "vancouver": ("Vancouver", 49.283, -123.121, "CA", "north-america",
                  "NA/CA/CA-BC/Vancouver", (74.9, 16.4, 12.0)),
    "sydney": ("Sydney", -33.869, 151.209, "AU", "oceania",
               "OC/AU/AU-NSW/Sydney", (44.2, 10.1, 11.3)),
    "mumbai": ("Mumbai", 19.076, 72.878, "IN", "south-asia",
               "AS/IN/IN-MH/Mumbai", (28.9, 12.3, 8.6)),
    "tokyo": ("Tokyo", 35.676, 139.650, "JP", "east-asia",
              "AS/JP/JP-13/Tokyo", (43.7, 17.0, 10.7)),
}

ESTIMATE = "wanpire's estimate for this kind of access"

# kind: (description, down, up, basis). Figures are one way, the access link's own share.
KINDS = {
    "media-private-network": (
        "Media-industry private network: managed studio-to-studio links, low loss, "
        "guaranteed bandwidth",
        {"delay_ms": 1, "jitter_ms": 0.2, "loss_pct": 0.001, "rate_mbit": 1000},
        {"delay_ms": 1, "jitter_ms": 0.2, "loss_pct": 0.001, "rate_mbit": 1000},
        "A managed service on dedicated fibre to the provider's edge in the same metro, with a "
        "committed rate: about a millisecond, almost no variation, loss close to zero."),
    "enterprise-fibre": (
        "Dedicated enterprise fibre line: symmetric, uncontended, one or two hops to a backbone",
        {"delay_ms": 1, "jitter_ms": 0.3, "loss_pct": 0.01, "rate_mbit": 1000},
        {"delay_ms": 1, "jitter_ms": 0.3, "loss_pct": 0.01, "rate_mbit": 1000},
        "Uncontended point-to-point fibre: light in a few tens of kilometres of fibre plus "
        "one or two routers."),
    "business-fibre": (
        "Business fibre: symmetric, lightly contended",
        {"delay_ms": 2, "jitter_ms": 0.5, "loss_pct": 0.02, "rate_mbit": 500},
        {"delay_ms": 2, "jitter_ms": 0.5, "loss_pct": 0.02, "rate_mbit": 500},
        "Shared fibre access with a business-grade contention ratio and a symmetric plan."),
    "consumer-fibre": (
        "Consumer fibre to the home: fast down, slower up",
        {"delay_ms": 4, "jitter_ms": 1, "loss_pct": 0.05, "rate_mbit": 500},
        {"delay_ms": 4, "jitter_ms": 1, "loss_pct": 0.05, "rate_mbit": 100},
        "Passive optical access shared by a few dozen homes: a few milliseconds to the first "
        "major network, little variation; a typical asymmetric plan."),
    "cable": (
        "Cable broadband over coaxial lines",
        {"delay_ms": 8, "jitter_ms": 3, "loss_pct": 0.1, "rate_mbit": 300},
        {"delay_ms": 8, "jitter_ms": 3, "loss_pct": 0.1, "rate_mbit": 20},
        "The upstream's request-and-grant scheduling adds several milliseconds and most of the "
        "variation; upload is a small share of download."),
    "dsl": (
        "DSL over a telephone line",
        {"delay_ms": 12, "jitter_ms": 3, "loss_pct": 0.2, "rate_mbit": 40},
        {"delay_ms": 12, "jitter_ms": 3, "loss_pct": 0.2, "rate_mbit": 8},
        "Interleaving for error correction and the copper line's length add ten milliseconds "
        "or more; rates of a typical short-loop plan."),
    "fixed-wireless": (
        "Fixed wireless access: a rooftop antenna to a nearby mast",
        {"delay_ms": 15, "jitter_ms": 6, "loss_pct": 0.5, "rate_mbit": 50},
        {"delay_ms": 15, "jitter_ms": 6, "loss_pct": 0.5, "rate_mbit": 10},
        "A shared radio channel with scheduling, more variation than a wire, and some loss in "
        "rain or interference."),
    "mobile-4g": (
        "4G mobile broadband",
        {"delay_ms": 25, "jitter_ms": 8, "burst_loss_pct": 0.5, "burst_length": 3,
         "rate_mbit": 30},
        {"delay_ms": 25, "jitter_ms": 8, "burst_loss_pct": 0.5, "burst_length": 3,
         "rate_mbit": 8},
        "Radio scheduling and the mobile core add a few tens of milliseconds and much of the "
        "variation; losses the radio's retransmissions do not hide come in short bursts, at "
        "handovers and fades."),
    "mobile-5g": (
        "5G mobile broadband",
        {"delay_ms": 12, "jitter_ms": 5, "burst_loss_pct": 0.2, "burst_length": 2,
         "rate_mbit": 200},
        {"delay_ms": 12, "jitter_ms": 5, "burst_loss_pct": 0.2, "burst_length": 2,
         "rate_mbit": 30},
        "Shorter radio slots than 4G halve the access delay; most deployments still share the "
        "4G core, so not the single milliseconds of the standard's targets."),
    "satellite-leo": (
        "Low-orbit satellite broadband",
        {"delay_ms": 20, "jitter_ms": 8, "burst_loss_pct": 1, "burst_length": 5,
         "rate_mbit": 150},
        {"delay_ms": 20, "jitter_ms": 8, "burst_loss_pct": 1, "burst_length": 5,
         "rate_mbit": 15},
        "Satellites some 550 km up add only a few milliseconds of light; scheduling and the "
        "path to a ground station add the rest. Each switch to another satellite, every few "
        "tens of seconds, loses a burst of packets."),
    "satellite-geo": (
        "Geostationary satellite broadband",
        {"delay_ms": 290, "jitter_ms": 15, "burst_loss_pct": 0.5, "burst_length": 3,
         "rate_mbit": 50},
        {"delay_ms": 290, "jitter_ms": 15, "burst_loss_pct": 0.5, "burst_length": 3,
         "rate_mbit": 5},
        "35,786 km up and down again is at least 239 ms each way at the speed of light; "
        "the link's scheduling and the ground station add about 50 ms."),
}


def generic(city: str) -> dict:
    name, *_, mlab, (down, up, rtt) = CITIES[city]
    delay = round(rtt / 2, 1)
    jitter = max(0.5, round(delay * 0.3, 1))
    url = ("https://statistics.measurementlab.net/v0/"
           + mlab.replace(" ", "%20") + "/2024/histogram_daily_stats.json")
    return {
        "kind": "generic",
        "description": f"A typical connection in {name}: the median of what people there "
                       "measured, whatever their kind of access",
        "down": {"delay_ms": delay, "jitter_ms": jitter, "loss_pct": 0.1, "rate_mbit": down},
        "up": {"delay_ms": delay, "jitter_ms": jitter, "loss_pct": 0.1, "rate_mbit": up},
        "sources": [
            {"name": "M-Lab NDT city statistics: median download, upload and minimum round "
                     "trip to the nearest server (delay is half that round trip)",
             "url": url, "date": MLAB_PERIOD[1], "licence": "CC0-1.0",
             "citation": MLAB_CITATION},
            {"name": ESTIMATE, "licence": "MIT",
             "basis": "Jitter (30% of the access delay) and loss (0.1%): the statistics give "
                      "neither."},
        ],
    }


def preset(city: str) -> dict:
    name, lat, lon, country, region, *_ = CITIES[city]
    channels = {"generic": generic(city)}
    for kind, (desc, down, up, basis) in KINDS.items():
        channels[kind] = {"kind": kind, "description": desc, "down": down, "up": up,
                          "sources": [{"name": ESTIMATE, "licence": "MIT", "basis": basis}]}
    return {
        "schema": "wanpire-endpoint/1",
        "id": city,
        "name": name,
        "location": {"lat": lat, "lon": lon, "country": country, "region": region},
        "default_channel": "generic",
        "channels": channels,
    }


def summarise(directory: str) -> None:
    for f in sorted(Path(directory).glob("*.json")):
        days = {r["date"]: r for r in json.loads(f.read_text(encoding="utf-8"))}
        v = list(days.values())

        def med(k):
            return round(statistics.median(x[k] for x in v), 1)

        print(f"{f.stem}: {min(days)} to {max(days)}, {len(days)} days: download "
              f"{med('download_MED')}, upload {med('upload_MED')}, min RTT "
              f"{med('download_minRTT_MED')}")


def main(argv: list[str]) -> int:
    if len(argv) == 3 and argv[1] == "--mlab":
        summarise(argv[2])
        return 0
    OUT.mkdir(parents=True, exist_ok=True)
    for city in CITIES:
        path = OUT / f"{city}.json"
        path.write_text(json.dumps(preset(city), indent=2, ensure_ascii=False) + "\n",
                        encoding="utf-8", newline="\n")
    print(f"{len(CITIES)} presets written to {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
