"""Fit the great-circle formula's route factors against the shipped path table.

    rtt = 2 × great_circle_km × route_factor(region_a, region_b) / 200 + router_ms

One router term for every pair, one route factor per unordered pair of world regions. For each
candidate router term (0 to 10 ms in half-millisecond steps) every region pair's factor is the
median of what its pairs imply; the router term kept is the one with the smallest median
relative error. A region pair with fewer than MIN_PAIRS pairs uses the global factor. Pairs
closer than MIN_KM are left out: at metro distances the router term is everything.

Run from the repository's root:

    python tools/fit_route_factors.py

It writes the fitted parameters (src/wanpire/data/paths/route-factors.json), the error left
over pair by pair (docs/route-factor-residuals.csv) and a summary (docs/route-factor-fit.md).
The error is reported twice: in-sample, and holding out each site in turn (refitting without
it, then predicting its pairs), which is closer to how the formula is used: for places the
table does not have.
"""

from __future__ import annotations

import csv
import itertools
import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from wanpire.presets import FIBRE_KM_PER_MS, great_circle_km, region_pair  # noqa: E402

TABLE = ROOT / "src/wanpire/data/paths/backbone-rtt.json"
OUT = ROOT / "src/wanpire/data/paths/route-factors.json"
RESIDUALS = ROOT / "docs/route-factor-residuals.csv"
REPORT = ROOT / "docs/route-factor-fit.md"
MIN_KM = 300
MIN_PAIRS = 5
ROUTERS = [i / 2 for i in range(0, 21)]


def pairs_of(table: dict) -> list[dict]:
    sites, rtt = table["sites"], table["rtt_ms"]
    out = []
    for a, b in itertools.combinations(sorted(sites), 2):
        x = [v for v in (rtt.get(a, {}).get(b), rtt.get(b, {}).get(a)) if v]
        if not x:
            continue
        sa, sb = sites[a], sites[b]
        km = great_circle_km(sa["lat"], sa["lon"], sb["lat"], sb["lon"])
        if km < MIN_KM:
            continue
        out.append({"a": a, "b": b, "km": km, "rtt": sum(x) / len(x),
                    "regions": region_pair(sa["region"], sb["region"])})
    return out


def implied(p: dict, router: float) -> float:
    return (p["rtt"] - router) * FIBRE_KM_PER_MS / (2 * p["km"])


def predict(p: dict, router: float, factors: dict, glob: float) -> float:
    return 2 * p["km"] * factors.get(p["regions"], glob) / FIBRE_KM_PER_MS + router


def fit_at(pairs: list[dict], router: float) -> tuple[dict, float]:
    glob = statistics.median(implied(p, router) for p in pairs)
    groups: dict = {}
    for p in pairs:
        groups.setdefault(p["regions"], []).append(p)
    factors = {k: statistics.median(implied(p, router) for p in g)
               for k, g in groups.items() if len(g) >= MIN_PAIRS}
    return factors, glob


def rel_error(p, router, factors, glob) -> float:
    return abs(predict(p, router, factors, glob) - p["rtt"]) / p["rtt"]


def fit(pairs: list[dict]) -> tuple[float, dict, float]:
    best = None
    for router in ROUTERS:
        factors, glob = fit_at(pairs, router)
        err = statistics.median(rel_error(p, router, factors, glob) for p in pairs)
        if best is None or err < best[0]:
            best = (err, router, factors, glob)
    return best[1], best[2], best[3]


def pct(xs: list[float], q: float) -> float:
    xs = sorted(xs)
    return xs[round(q * (len(xs) - 1))]


def main() -> int:
    table = json.loads(TABLE.read_text(encoding="utf-8"))
    pairs = pairs_of(table)
    router, factors, glob = fit(pairs)

    held_out = {}
    for site in table["sites"]:
        rest = [p for p in pairs if site not in (p["a"], p["b"])]
        f, g = fit_at(rest, router)
        for p in pairs:
            if site in (p["a"], p["b"]):
                held_out.setdefault((p["a"], p["b"]), []).append(rel_error(p, router, f, g))
    held = {k: max(v) for k, v in held_out.items()}

    rows = []
    for p in pairs:
        pred = predict(p, router, factors, glob)
        rows.append({**p, "pred": pred, "err": (pred - p["rtt"]) / p["rtt"],
                     "held": held[(p["a"], p["b"])]})

    groups: dict = {}
    for r in rows:
        groups.setdefault(r["regions"], []).append(r)

    src = table["source"]
    OUT.write_text(json.dumps({
        "schema": "wanpire-route-factors/1",
        "fitted_on": f"{src['name']}, dataset {src['dataset_date']} ({src['licence']})",
        "method": "tools/fit_route_factors.py: median implied factor per region pair, "
                  f"router term chosen on a grid; pairs under {MIN_KM} km left out; "
                  f"region pairs with fewer than {MIN_PAIRS} pairs use the global factor",
        "router_ms": router,
        "global_factor": round(glob, 3),
        "factors": {f"{k[0]}/{k[1]}": {"factor": round(v, 3), "pairs": len(groups[k])}
                    for k, v in sorted(factors.items())},
    }, indent=1) + "\n", encoding="utf-8", newline="\n")

    with RESIDUALS.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["site_a", "site_b", "regions", "great_circle_km", "table_rtt_ms",
                    "formula_rtt_ms", "error_pct", "held_out_error_pct"])
        for r in sorted(rows, key=lambda r: -abs(r["err"])):
            w.writerow([r["a"], r["b"], "/".join(r["regions"]), f"{r['km']:.0f}",
                        f"{r['rtt']:.1f}", f"{r['pred']:.1f}", f"{100 * r['err']:+.1f}",
                        f"{100 * r['held']:.1f}"])

    def line(name, rs, factor):
        e = [abs(r["err"]) * 100 for r in rs]
        h = [r["held"] * 100 for r in rs]
        return (f"| {name} | {len(rs)} | {factor} | {statistics.median(e):.1f} | "
                f"{pct(e, 0.9):.1f} | {statistics.median(h):.1f} | {pct(h, 0.9):.1f} |")

    naive = [abs(2 * r["km"] * 1.6 / FIBRE_KM_PER_MS - r["rtt"]) / r["rtt"] * 100 for r in rows]
    lines = [
        "# The formula's fit, and the error left over",
        "",
        "Generated by `tools/fit_route_factors.py`; do not edit by hand.",
        "",
        f"Fitted on {src['name']}, dataset {src['dataset_date']}, {src['licence']} "
        f"({len(table['sites'])} sites, {len(rows)} pairs at least {MIN_KM} km apart, each "
        "the mean of its two directions).",
        "",
        f"    rtt = 2 × great_circle_km × route_factor / 200 + {router:g} ms",
        "",
        f"Global factor {glob:.3f}. All pairs: median error **{statistics.median(abs(r['err']) for r in rows) * 100:.1f}%** "
        f"in-sample, **{statistics.median(r['held'] for r in rows) * 100:.1f}%** with each site held out. "
        f"For comparison, one factor of 1.6 and no router term: {statistics.median(naive):.1f}%.",
        "",
        "Errors are |formula − table| / table, in per cent. *Held out*: the factor refitted "
        "without one of the pair's sites (the worse of the two), which is how the formula is "
        "used, for places the table lacks.",
        "",
        "| Region pair | Pairs | Factor | Median % | 90th % | Held-out median % | Held-out 90th % |",
        "|---|---|---|---|---|---|---|",
        line("all", rows, f"{glob:.3f} (global)"),
    ]
    for k in sorted(groups):
        fac = f"{factors[k]:.3f}" if k in factors else f"{glob:.3f} (global)"
        lines.append(line(f"{k[0]} / {k[1]}", groups[k], fac))
    worst = sorted(rows, key=lambda r: -abs(r["err"]))[:10]
    lines += ["", "The ten worst pairs in-sample (all of them in `docs/route-factor-residuals.csv`):",
              "", "| Pair | km | Table ms | Formula ms | Error |", "|---|---|---|---|---|"]
    for r in worst:
        lines.append(f"| {r['a']} – {r['b']} | {r['km']:.0f} | {r['rtt']:.0f} | "
                     f"{r['pred']:.0f} | {100 * r['err']:+.0f}% |")
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print(f"router {router} ms, global {glob:.3f}, {len(factors)} region pairs fitted, "
          f"median error {statistics.median(abs(r['err']) for r in rows) * 100:.1f}% "
          f"(held out {statistics.median(r['held'] for r in rows) * 100:.1f}%)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
