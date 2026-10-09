## Context

The whole design is in `design-the-link-emulator/design.md` (D4, D4a, D4b, D9) and its study
`spikes/calibration-sources.md`, which found what may be shipped: a cloud backbone's
region-to-region round trips (CC BY 4.0) and M-Lab's NDT measurements (CC0). This document
records only what this change decides on top of that.

## Goals / Non-Goals

**Goals:** the preset format and its schema; seven starter endpoints; the shipped path table;
the formula, fitted, with its error published; combining two ends into a `Link`; the CLI on
two ends.

**Non-Goals:** a path jitter or loss term (the shipped table has round trips only); fitting
against the read-only sources (a later check, below); the REST API and MCP faces of the same
functions (B3).

## Decisions

### P1. The data ships inside the package

`src/wanpire/data/` holds the schema (`schema/endpoint.schema.json`), the endpoints
(`endpoints/<id>.json`), the path table (`paths/backbone-rtt.json`) and the fitted factors
(`paths/route-factors.json`), read through `importlib.resources`. The design's sketch put them
in a top-level `presets/`; inside the package, an installed wanpire (a wheel, `pip install`)
finds them without knowing where the repository is.

Not taken: a top-level `presets/` read relative to the source tree (breaks once installed);
`/usr/share/wanpire` (needs the install script to find anything, and makes tests depend on it).

### P2. Validation in Python; the schema is published and tested

`presets.endpoint_from_dict` validates every preset and names the preset, the channel and the
setting when it refuses one; the figures go through the link model's own `Direction`, so a
channel cannot hold what the engine would refuse. The JSON Schema is published for people who
write their own presets, and a unit test checks every shipped preset against it with
`jsonschema` (a test dependency only).

Not taken: `jsonschema` at run time (a dependency for what twenty lines do, and its messages
are worse); no schema (the owner asked for a published one).

### P3. A channel carries only access figures

A channel may set delay, jitter, random or burst loss, and bandwidth, per direction. Reordering
and duplication are properties of a path or a fault, not of an access kind, and are left to
raw figures.

### P4. The path table: one cloud backbone, its sites mapped to coordinates

`tools/import_backbone_rtt.py` reads the published page's Markdown source (whose repository is
CC BY 4.0), takes its CSV matrix, and writes 54 sites (metro, approximate coordinates, world
region) and their 2,862 directional P50 round trips, with the source, the dataset date and the
attribution. A path between two sites is the **mean of its two directions** (they differ by a
millisecond or two; the engine splits the path evenly anyway).

A city is **anchored** at its nearest site when that site is within **1,000 km**, and the
table's figure is corrected by the formula's own difference between the ends and the sites
(`formula(ends) − formula(sites)`), so Los Angeles, anchored at the San Francisco Bay Area's
site 560 km away, gets the table's figure plus 2 ms to London. Two ends at the same site, or an
end farther than 1,000 km from every site, use the formula.

It is a backbone figure: the round trip between two data centres on one provider's network,
with no access link. That is exactly what wanpire adds the channels to.

Not taken: anchoring without the correction (Vancouver to New York would lose 6.5 ms); a
smaller radius (most of the seven cities would lose the table); the faster of the two
directions (a choice nobody can see the reason for).

### P5. The formula: a factor per pair of nine world regions, and a router term

    rtt = 2 × great_circle_km × route_factor(region_a, region_b) / 200 + router_ms

`tools/fit_route_factors.py` fits it against the table: pairs under 300 km left out (the router
term is all there is at metro distance); each region pair's factor is the median of what its
pairs imply, for region pairs with at least 5 pairs; the router term is chosen on a 0.5 ms grid
to minimise the median relative error. The result (`docs/route-factor-fit.md`, pair by pair in
`docs/route-factor-residuals.csv`):

| | Median error | 90th percentile |
|---|---|---|
| One factor of 1.6, no router term (the design's first guess) | 14.5% | |
| Fitted, in-sample | 6.7% | 19.4% |
| Fitted, each site held out in turn | 8.9% | 22.9% |

Router term 7.5 ms, global factor 1.546; 37 region pairs fitted. The held-out figure is the
honest one: it is how the formula is used, for places the table lacks.

**South-east Asia is a region of its own.** With Singapore, Kuala Lumpur and Jakarta inside
"east Asia", Europe to east Asia had a median error of 19.5% and a 90th percentile of 43%:
Europe reaches Singapore by the short route through the Red Sea (factor 1.5) and Tokyo or
Seoul by long ones (factor 2.4). Splitting them brought the overall median from 7.3% to 6.7%.

**Where it is still wrong**, and why, from the residuals:

- Neighbours across a short sea (Dubai–Doha, 376 km: table 15 ms, formula 26): the router
  term dominates. Small absolute error, large relative one.
- São Paulo to South Africa (6,344 km: table 304 ms, formula 106): this backbone does not use
  the South Atlantic cable and goes through Europe or the US. The formula cannot know a route;
  the region pair has too few pairs to fit and uses the global factor.
- Southern France to south-east Asia (+55% to +64%): Marseille is a cable landing with a
  straight route east; the Europe/south-east Asia factor is pulled up by the rest of Europe.

Not taken: one global factor (14.5%); a factor per site pair (that is the table itself); a
least-squares fit (pulled by the outliers above; the median is robust to them).

**Fitted on the shipped table only.** The design meant the read-only sources (RIPE Atlas,
WonderNetwork) to calibrate the formula too: they cover consumer paths and many more cities.
Their figures are not copied; checking the fitted factors against them is left for a later
change (open question A22).

### P6. Combining: the near end is the device under test's

`combine(near_channel, far_channel, path_rtt)`: *down* is the far end sending (its *up*) to the
near end receiving (its *down*), *up* the reverse; each direction gets half the path. Delays
add; jitters add in quadrature and keep the default normal distribution; losses compound
`1 − Π(1 − l)`, and if either side's loss is bursty the total is burst loss with the longer
mean burst; the rate is the narrower. Figures are rounded to 0.1 ms and 0.001%.

### P7. The starter set: one measured channel per city, eleven estimated kinds

`tools/make_endpoints.py` writes the seven presets. Every city has all twelve kinds.

- **generic** comes from M-Lab's NDT city statistics (CC0): over 2024-01-01 to 2024-03-26 (the
  last period its statistics service publishes), the median of the daily median download,
  upload and minimum round trip to the nearest server. The channel's one-way delay is half
  that round trip. Jitter (30% of the delay) and loss (0.1%) are estimates; the statistics give
  neither. These are single-stream TCP results, so the rates are lower than plan speeds.
- **The other eleven kinds** are wanpire's own typical figures, the same in every city, each
  with the reasoning that gives it (`basis`), licensed with the code. A geostationary
  satellite's 290 ms each way is physics (35,786 km up and down at the speed of light is 239 ms)
  plus scheduling; the rest are typical published orders of magnitude, not measurements.

Not taken: per-city figures for each kind (no redistributable source splits by kind); naming
the M-Lab figures as the kind *consumer-fibre* (they mix every kind of access).

### P8. The CLI

- `wanpire endpoints` lists the shipped endpoints and their channels (the default marked).
- `wanpire preview <near> <far> [--json]` prints the link and how each part was found, with
  the table's attribution when the table was used. It needs no root and touches nothing.
- `wanpire apply --adapter <outbound> <near> <far>` applies exactly what `preview` prints. Two
  ends and raw figures exclude each other.
- An end is `<endpoint>[:<channel>]`; `<endpoint>` is a shipped id or a preset file's path
  (a Windows drive letter is not taken for a channel).

## Risks / Trade-offs

- **One provider's backbone is not the public internet.** Its paths are well engineered and
  often shorter than a consumer's. → The channels add the access part; the residuals and the
  later check against the read-only sources say how far off it is.
- **The channel kinds are estimates.** → Stated in every file, with their reasoning; a user
  can override any of them with a preset of their own.
- **M-Lab's statistics end in March 2024.** → The date is in every generic channel; the tool
  can re-summarise newer downloads.
- **Region coordinates are approximate** (a metro, not a building). → Tens of kilometres are
  well under a millisecond.
