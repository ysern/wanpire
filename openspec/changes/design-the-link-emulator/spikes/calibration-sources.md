# Study: public city-to-city measurements, and whether we may ship them

**Status:** done, 2026-10-10. Sources found and their licences read; the table is not built yet.

## Question

Which public sources give round-trip time, jitter, loss or throughput between major cities,
or for the access links in a city? For each: may wanpire *redistribute* its figures in an MIT
repository, or may they only be *read* to calibrate the formula?

## Why it matters

The rule for wanpire's data: **only figures whose licence allows redistribution go into the
shipped city-pair table**, each with its source and date. Figures that may only be read are
used to fit the great-circle formula and are not copied.

## Method

Each source's own licence or terms page was read on 2026-10-10. "Redistributable" below means
redistributable inside an MIT-licensed repository *without asking*, which also implies that
downstream users may use it commercially.

## Findings

| Source | What it measures | Licence or terms | Redistributable in wanpire? |
|---|---|---|---|
| **Microsoft Azure, "network round-trip latency statistics"** (learn.microsoft.com, source in the public `azure-docs` repository) | Monthly median RTT between about 60 cloud regions, probed every minute; dataset of 30 July 2026 | The docs repository is **CC BY 4.0** | **Yes, with attribution.** City-to-city between data centres on one backbone: a *path* figure, without any access link |
| **M-Lab NDT** (measurementlab.net) | Per test: client's throughput, RTT, loss and retransmission to the nearest M-Lab server; billions of tests, geolocated to city | **CC0** (no rights reserved); a citation is requested | **Yes.** An *access-link* figure per city and kind of connection, not city-to-city |
| **RIPE Atlas** (atlas.ripe.net) | Ping and traceroute between ~12,000 probes and anchors; anyone may query public results | RIPE Atlas Terms and Conditions v3.5: data for research and network operations; **"any commercial use … is subject to prior permission"**; a default, revocable permission exists for those who credit RIPE Atlas | **No, read only**, unless the RIPE NCC agrees in writing. MIT lets anyone use the table commercially, which is what needs permission |
| **WonderNetwork global ping statistics** (wondernetwork.com/pings) | Average of 30 pings between ~280 cities, daily | No licence. The page asks not to scrape, offers one day's download, and says "for other uses please reach out … please backlink and let us know" | **No, read only.** Shipping would need their permission |
| **Ookla Open Data** (Speedtest performance tiles) | Download, upload, latency per ~600 m tile, fixed and mobile, quarterly | **CC BY-NC-SA 4.0** | **No.** Redistributable, but NonCommercial and ShareAlike are incompatible with an MIT table. Read only |
| **Cloudflare Radar** | Country and network quality, latency, traffic | **CC BY-NC 4.0** for data (CC BY 4.0 for embedded charts only) | **No**, NonCommercial. Read only |
| **TeleGeography Submarine Cable Map** | Cable routes and landing points | Map images CC BY-SA 4.0; **the underlying data is subscription-only** | **No.** Useful only to reason about route factors |
| **Globalping** (jsDelivr) | On-demand ping from community probes | Client code MIT; no licence stated for results | **Unclear, treated as read only** |

### What this means for the table

- **The shipped city-pair table can be built from the Azure latency statistics** (CC BY 4.0),
  with one row per region pair mapped to its city, the dataset's date and the attribution the
  licence asks for. It is a backbone figure: each end's channel adds its own access delay,
  which is exactly how wanpire combines a link.
- **The channels' typical figures can come from M-Lab** (CC0): median RTT to the nearest server,
  loss and throughput per city and kind of access.
- **RIPE Atlas and WonderNetwork calibrate the formula** and are not copied. Their wider
  coverage (many more cities, consumer paths rather than a cloud backbone) is what makes them
  good for fitting the route factor.
- A first sanity check of the formula against the CC BY table: London (UK South) to the US
  West coast (West US) is about 8,630 km on the great circle, so light in fibre needs 86 ms
  for the round trip; the table says 140 ms, a route factor of about 1.6. That is in line with
  the factor of 1.5 to 2 commonly quoted for intercontinental paths. The fit itself is B2's
  work.

### Not settled

- Whether naming a cloud provider as a *data source* conflicts with "no provider is named".
  Assumed not: the rule is about channels in presets, and CC BY *requires* the attribution.
  Recorded as an assumption in `docs/open-questions.md`.
- Asking RIPE NCC and WonderNetwork for permission to ship derived figures is the owner's call.
