# N-Ways Addressing for Togo

**Status: issued on 20 October 2026.** Every compound in Togo has an N-Ways code: 2,768,053 of them, provisional until
residents confirm them. Togo has no postal code. Where the State gives an address (the street names and codes of the
former commune of Lomé today, the District Autonome du Grand Lomé's entrance addresses once released), that address is
the official one and is shown first, exactly as the State writes it, with the N-Ways code beside it. The whole
registry is published here, every code with its entrance and building profile.

A home's code is **the name of a quartier, village or canton people already say plus a number of four or five digits
said in pairs**:

| Code | Machine form | What it is |
|---|---|---|
| `Fréau-Jardin 10 58` | `TG-FRJ-1058-2` | a compound beside Lomé's Grand Marché, on Rue Mission Tové (shown first) |
| `Zongo 1 41 98` | `TG-KOZ0615-14198-6` | a compound in Kara; `Zongo 15 00` is the other Zongo, in Kloto |
| `Tokpo 11 00`, `Tokpo 24 17` | | two of the three places of one name, in Danyi and in Lacs: one national range, three blocks |
| `FRJ-54-4R` | | any point: its spot code, a 3.4 m cell |

The code is unique in the whole country on its own: every area with the same plate name shares one national range of
numbers, cut into frozen blocks of twice its compounds, so "Name NNNN" never needs a préfecture after it. People never
see or type a check digit: a Damm check over the name, the area and the number lives in the machine form, for systems.
The name is a **plate name** of at most 12 characters and 2 words ("Démakpoè" for "Agoè-Démakpoè", "Fiagbe" for
"Adjahun Fiagbe"); the official name still finds it. 76 areas carry a provisional plate name their commune may change
once; their codes are issued, and the number never changes. A Lomé street code ("165 AMT") is recognised as such and
never read as an N-Ways code. A spot code names any point to 3.4 m in the frame of its quartier or canton; a point in
no outline (a thin gap between outlines, or just over a border line) takes the frame of the nearest outline within
1,100 m that holds it, else the nearest edge cell of a frame at most 200 cells away ([SPEC §5](engine/SPEC.md)), so
every issued compound has a spot code.

## What is where

| Path | Contents |
|---|---|
| [docs/paper.md](docs/paper.md), [paper.fr.md](docs/paper.fr.md) and their PDFs | the research paper in English and French: background, data, the model with every formula and worked examples, implementation, evaluation, the designs rejected, and the benefits for citizens, logistics, emergency services and government |
| [docs/paper/](docs/paper/), [docs/figures/](docs/figures/) | the paper's typesetting (pandoc template, style, flag colours, references, build script) and its figures with their data |
| [docs/api.md](docs/api.md) | the registry server's API, every endpoint with a real request and response |
| [docs/existing-systems.md](docs/existing-systems.md) | the survey of existing systems: La Poste, Lomé's street codes, the DAGL's modernisation, private codes, land; verdict and sources |
| [docs/model.md](docs/model.md) | the design notes behind every choice |
| [engine/SPEC.md](engine/SPEC.md) | the engine specification (normative) |
| [engine/reference/](engine/reference/) | the reference engine (`tg_engine.py`, `plate_names.py`, and `border.py`, the national-border check every issued code passes; standard library only), its tests (`test_tg.py`) and the conformance vectors every engine must reproduce (`test_vectors.json`, `vectors.json`) |
| [engine/data/](engine/data/) | what a decoder ships: `register.json` (every area with its plate and official names, name id, blocks, box and point) and `units.json` (the quartier and canton polygons); `border.json`, Togo's national border (OpenStreetMap admin_level 2, simplified to about 50 m): no code is issued more than 300 m outside it |
| [registry/](registry/) | every issued code, one gzip CSV per préfecture (`LOM.csv.gz` is the former commune of Lomé), the frozen area table `areas.csv.gz` and `MANIFEST.json` (counts and SHA-256 of every file) |
| [server/](server/README.md) | the registry server: a ready-made HTTP API on the registry, its Docker files, OpenAPI description and tests |
| [model/](model/) | `areas/` (areas, the national name table, named places), `units/` (quartier and canton polygons), `stats/` (the figures of the paper), `design.json` |
| [tools/](tools/README.md) | the scripts that built the inputs, the areas, the compounds, the names and the registry |
| [GOVERNANCE.md](GOVERNANCE.md), [CONTRIBUTING.md](CONTRIBUTING.md), [SECURITY.md](SECURITY.md) | rules, roles and the issuer; how to propose a change; how to report a problem |
| [SOURCES.md](SOURCES.md), [LICENSING.md](LICENSING.md), [NOTICE](NOTICE), [CITATION.cff](CITATION.cff) | sources, licences and how to credit and cite |

## Run the reference engine

```sh
python3 engine/reference/test_tg.py                          # tests and conformance vectors
python3 engine/reference/tg_engine.py parse "Fréau-Jardin 10 58"
python3 engine/reference/tg_engine.py parse "TG-FRJ-1058-2"   # validate a machine code
python3 engine/reference/tg_engine.py parse "Zongo 1500"      # the Zongo of Kloto, from the number alone
python3 engine/reference/tg_engine.py parse "Tokpo 54 17"     # refused: in no block of the name
python3 engine/reference/tg_engine.py parse "165 AMT"         # a Lomé street code, not an N-Ways code
python3 engine/reference/tg_engine.py format FRJ 1058         # written, machine and spoken forms
python3 engine/reference/tg_engine.py spot 6.1317765 1.2234008  # spot code: FRJ-54-4R
python3 engine/reference/tg_engine.py decode FRJ-54-4R
python3 engine/reference/tg_engine.py where 6.1317765 1.2234008 # code area
```

Python 3.9 or newer, no packages (see [requirements.txt](requirements.txt)).

## Run the server

Anyone can serve the registry, with the same answers as N-Ways:

```sh
cd server && docker compose up -d             # imports the registry on first start, then serves :8080
curl -s "http://localhost:8080/v1/find?q=Fr%C3%A9au-Jardin%2010%2058"
```

or, without Docker, from the repository root:

```sh
python3 -m server import --registry registry --db data/addresses.sqlite   # verified against MANIFEST.json
python3 -m server serve --db data/addresses.sqlite --port 8080
python3 -m unittest server.test_server                                    # the server's tests
```

A deployment is read-only unless the State or N-WAYS LIMITED has designated it as the issuer: one issuer per country,
so that no number is ever given twice. Deployment behind TLS, configuration, backups, updates and the issuing rules:
[server/README.md](server/README.md). Every endpoint: [docs/api.md](docs/api.md).

## The papers

The research paper is [docs/paper.md](docs/paper.md) (English) and [docs/paper.fr.md](docs/paper.fr.md) (French),
typeset as `docs/n-ways-addressing-togo-en.pdf` and `docs/n-ways-addressing-togo-fr.pdf`. Its sources are pandoc
markdown with TeX mathematics; the figures are TikZ/pgfplots drawings in `docs/figures/`, each plotting a small table
computed from the published files, and the references are in `docs/paper/references.bib`.

```sh
python3 tools/paper-figures.py      # docs/figures/*.dat from registry/, engine/data/ and model/
sh docs/paper/build.sh              # figures (PDF and SVG), then both PDFs
```

The build needs pandoc 3, tectonic and pdftocairo (poppler). The statistics quoted in the paper are in
`model/stats/`.

## How the registry was made

```sh
python3 tools/prepare-inputs.py <work>              # quartiers, cantons, streets, enclosures, estates, gates, places
python3 tools/extract-buildings.py <work>           # every footprint inside Togo (DuckDB, 3 GB cap), with its unit and street
python3 tools/assign-areas.py <work>                # each footprint's code area
python3 tools/sort-buildings.py <work>              # sorted by area
python3 tools/issue_registry.py group <work>        # compounds and profiles, one area at a time
python3 tools/build-register.py <work> --freeze     # plate names, national ranges and blocks on the real compounds
python3 tools/issue_registry.py number <work> <work>/lotes.jsonl.gz
python3 tools/vectors.py                            # engine/reference/vectors.json
python3 tools/paper-stats.py <work> <work>/lotes.jsonl.gz
```

The issuer then wrote the codes, checking every number against the reference engine's, and exported `registry/`. The
register is frozen: a later run adds codes for new compounds and never renumbers an issued one. The inputs are open
datasets ([SOURCES.md](SOURCES.md)); [tools/README.md](tools/README.md) describes them.

## Licence and credit

Code (engine, server, tools): Apache License 2.0, with [NOTICE](NOTICE). Data (registry, model, engine data): ODbL 1.0.
Documents: CC BY 4.0. Credit every use: **"N-Ways Addressing for Togo, © N-WAYS LIMITED (nways.ng)"**, with a link to
this repository ([LICENSING.md](LICENSING.md)). Derived from OpenStreetMap (© OpenStreetMap contributors, ODbL), Google
Open Buildings (CC BY 4.0), Microsoft building footprints (CDLA Permissive 2.0, received through Overture Maps under ODbL) and the HDX/OCHA canton boundaries (CC BY-IGO).
