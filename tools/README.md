# Tools: how Togo's registry was built

These scripts built the areas, the compounds, the names and the registry from open map data. They are published so
that every step can be read and checked; nobody needs them to use the codes, the engine or the server, which work from
`registry/`, `model/` and `engine/data/` alone.

The inputs are read-only and listed in [SOURCES.md](../SOURCES.md): an OpenStreetMap extract of Togo, the Google Open
Buildings and Microsoft footprints (via Overture Maps) and the HDX canton boundaries, kept under a data folder given by
`NWAYS_ROOT` (`data/osm/togo-latest.osm.pbf`, `data/detail/countries/togo/buildings-src.geojsonseq`,
`data/detail/ml/TG.parquet`, and the compound and gate layers in `data/valhalla/`), and a places table used only to
classify buildings, read through `NWAYS_DB` (a PostgreSQL connection string; tables `regions` and `places`). The tools
stop with a message when either is not set. Run one heavy step at a time: DuckDB runs with `memory_limit='3GB'` and
spills to the work folder; the grouping reads the footprints one code area at a time.

| Step | Script | Writes |
|---|---|---|
| 1 | osmium exports (below) | `admin`, `bar`, `place`, `hw` `.geojsonseq` in the work folder |
| 2 | `prepare-inputs.py <work>` | `units.geojson` (the 69 quartiers of Lomé, then the 373 cantons), `streets.csv` (the named streets of the former commune of Lomé, with their codes), `enclosures.geojson`, `estates.geojson`, `gates.csv`, `places.csv`, `country.geojson` (the national border: OpenStreetMap's admin_level 2 boundary of Togo) |
| 2b | `make-border.py <work>` | `engine/data/border.json`: `country.geojson` simplified at 50 m, with its measured deviation, for the server |
| 3 | `extract-buildings.py <work>` | `buildings-raw.csv` (every footprint whose centre is inside the national border, with its enclosure, estate, unit and nearest official street within 30 m), `buildings-pts.csv` (centre, unit, density), `enclosure-gates.csv` |
| 4 | `assign-areas.py <work>` | `area-of.csv` (each footprint's code area: its quartier, its canton, or the nearest named-place cell); a footprint more than 300 m outside the border is dropped |
| 5 | `sort-buildings.py <work>` | `buildings.csv`, sorted by area |
| 6 | `issue_registry.py group <work>` | `compounds.jsonl.gz` (compounds and profiles; huts clustered only in Kara and Savanes; a compound whose point is more than 300 m outside the border is dropped), `area-counts.json`, `group-stats.json` |
| 7 | `build-register.py <work> --freeze` | plate names, national ranges and blocks on the real compounds (`name_ranges.py`): `model/areas/*.json`, `engine/data/register.json`, `engine/data/units.json`, `model/stats/register.json` |
| 8 | `issue_registry.py number <work> <work>/lotes.jsonl.gz` | the lotes, area by area, with the reference's numbers and Lomé's official street; it stops, writing nothing usable, if any compound lies more than 300 m outside the border |
| 9 | the issuer, on `<work>/lotes.jsonl.gz` | the codes, after checking every number against the reference's; then the export of the registry, gzipped into `registry/` (the format `python3 -m server export` writes) |
| 10 | `vectors.py`, `paper-stats.py <work> <work>/lotes.jsonl.gz` | `engine/reference/vectors.json`, `model/stats/building-stats.json` |
| 11 | `paper-figures.py` (no arguments; reads only the published files) | the data of the paper's figures, `docs/figures/*.dat` |

### The border decides

A code is only ever issued for a building whose entrance lies inside Togo's national border, OpenStreetMap's
admin_level 2 boundary (`country.geojson`), or within 300 m of it (engine/SPEC.md §1.1). The canton and quartier
outlines spill over the border in places, and the nearest-area fallback of step 4 would give a code area to any
footprint; neither decides. Four steps enforce it, each against the unsimplified boundary with
`engine/reference/border.py`: `extract-buildings.py` keeps only footprints whose centre is inside the border,
`assign-areas.py` drops any footprint more than 300 m outside it, `issue_registry.py group` drops any compound
whose point is, and `issue_registry.py number` refuses to write a lote across it. The server applies the same rule
to every new code and moved entrance with `engine/data/border.json` (step 2b). On the published registry, no code
has its entrance outside the border.

`build_areas.py` built the code areas (quartiers, cantons and named-place cells); `name_ranges.py` holds Togo's plate-name rules and the national name table; `make_vectors.py` writes the design vectors (`engine/reference/test_vectors.json`) from the frozen blocks. The statistics scripts of the design (`stats.py`, `analyse.py`, `places-areas.py`, `national-areas.py`, `pick_vectors.py`) produced `model/stats/capital-*.json`, `model/stats/national-areas.json` and the test footprints; they are kept as the record of how those figures were obtained.

### osmium exports

```
P=data/osm/togo-latest.osm.pbf
osmium tags-filter -o b.osm.pbf $P r/boundary=administrative
osmium export -a type,id -f geojsonseq --geometry-types=polygon -o admin.geojsonseq b.osm.pbf
osmium tags-filter -o bar.osm.pbf $P w/barrier=wall,fence,hedge,retaining_wall n/barrier=gate,entrance,lift_gate,sliding_gate,swing_gate n/entrance
osmium export -a type,id -f geojsonseq -o bar.geojsonseq bar.osm.pbf
osmium tags-filter -o place.osm.pbf $P n/place
osmium export -a type,id -f geojsonseq -o place.geojsonseq place.osm.pbf
osmium tags-filter -o hw.osm.pbf $P w/highway
osmium export -a type,id -f geojsonseq -o hw.geojsonseq hw.osm.pbf
```
