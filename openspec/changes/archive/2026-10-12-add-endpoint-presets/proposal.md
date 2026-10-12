## Why

The engine applies a link given as raw figures. People do not think of a link as "150 ms, 1%
loss"; they think of it as *London on consumer fibre to Los Angeles on 4G*. The design (D4)
settled that a link is described by its two ends, each an endpoint preset with access
channels, and that the path between them comes from measured figures where they may be
shipped, and from a calibrated great-circle formula elsewhere. Nothing of that exists yet.

## What Changes

- **Endpoint presets**: a JSON format with a published JSON Schema
  (`presets/schema/endpoint.schema.json`): a place, its coordinates and world region, its
  channels, a default channel, and optional measured paths to named other ends. Every figure
  names its source.
- **Channels by generic kind**, never a provider: `generic`, `media-private-network`,
  `enterprise-fibre`, `business-fibre`, `consumer-fibre`, `cable`, `dsl`, `fixed-wireless`,
  `mobile-4g`, `mobile-5g`, `satellite-leo`, `satellite-geo`.
- **A shipped path table** from redistributable data only: a cloud backbone's published
  region-to-region round trips (CC BY 4.0, with its attribution), with each site's
  coordinates, imported by a script anyone can re-run.
- **The great-circle formula** as the fallback, with a route factor per pair of world regions
  and a router term, **fitted** against that table by a script; the fit's parameters and the
  error left over pair by pair are committed.
- **Combining two ends into a `Link`**: the path from an endpoint's own measured path, then the
  table (anchored at each end's nearest site), then the formula; channel delays add, jitters
  add in quadrature, losses compound (burstiness kept), bandwidth is the narrower end.
- **The CLI** takes two endpoints, each with an optional channel
  (`wanpire preview london:consumer-fibre los-angeles:mobile-4g`, and `apply` the same way),
  and shows how the link was worked out.
- **A starter set** of seven endpoints: London, Los Angeles, New York, Vancouver, Sydney,
  Mumbai, Tokyo. Their *generic* channel's access delay and bandwidth come from M-Lab's NDT
  city statistics (CC0); the other kinds' figures are wanpire's own typical estimates, each
  with the reasoning that gives it.

## Decided and assumed

Decided by the design: the format is JSON with a schema; table first, formula second; how two
ends combine (A6, A7, A8). Assumed here (also in `docs/open-questions.md`): the path is the
mean of the table's two directions; a city is anchored at a table site only within 1,000 km,
and the anchor's offset is corrected by the formula's difference; the fit uses only the
shipped table (checking it against the read-only sources comes later); channel kinds other
than *generic* carry estimates, not measurements.

## Capabilities

### New Capabilities

- `endpoint-presets`: the endpoint and channel format, its schema, loading and validating
  presets, the starter set, and choosing a channel.
- `path-delay`: the shipped path table, the formula and its fit, and combining two endpoints
  and their channels into a link.

### Modified Capabilities

None. (The CLI gains endpoint arguments; the engine itself is unchanged.)

## Impact

- New: `src/wanpire/presets.py`, `src/wanpire/data/` (schema, endpoints, path table, fitted
  factors, shipped inside the package so an installed wanpire finds them),
  `tools/import_backbone_rtt.py`, `tools/fit_route_factors.py`, `tools/make_endpoints.py`.
- `cli.py` gains `preview` and endpoint arguments to `apply`.
- No new runtime dependency; `jsonschema` joins the test extras to check shipped files against
  the published schema.
