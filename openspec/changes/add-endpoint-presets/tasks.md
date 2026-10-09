## 1. Presets (no root)

- [x] 1.1 Failing tests: a valid preset loads; refusals (no channel, bad figures naming preset/channel/setting, unknown kind, no generic, no source, non-access setting, missing default, schema tag)
- [x] 1.2 Implement `presets.py`'s preset part until green

## 2. Path and formula (no root)

- [x] 2.1 Failing tests: great circle; the formula's region-pair factor and the global fallback
- [x] 2.2 Failing tests: path from the preset, from the table (anchored and corrected), from the formula; two ends at one site
- [x] 2.3 Failing tests: combining (the spec's London–Los Angeles case, burst loss kept, no rate, asymmetry, quadrature)
- [x] 2.4 Implement until green

## 3. The shipped data

- [x] 3.1 `tools/import_backbone_rtt.py`; import the CC BY table with its attribution
- [x] 3.2 `tools/fit_route_factors.py`; fit, write the factors, the residuals and the report; south-east Asia split out
- [x] 3.3 The published schema; `tools/make_endpoints.py` and the seven presets from M-Lab (CC0) and stated estimates
- [x] 3.4 Failing tests then `catalogue.py`: shipped presets valid against the schema, licences, the seven cities, resolving ends, the formula's median error below 15%

## 4. CLI

- [x] 4.1 Failing tests: `endpoints`, `preview` (text and JSON, no engine), `apply` from two ends equals `preview`, ends and figures exclusive, one end refused, unknown end
- [x] 4.2 Implement; package data in the wheel

## 5. Close

- [x] 5.1 Unit tests on the Pi; journal, open questions, README
