# The address API

This is the HTTP API of the registry server in [`server/`](../server/README.md). Every example below is a real request
made to a server running on the full published registry (2,768,053 codes), with the response it returned. The
issuing examples were made on a scratch copy of that database, so the numbers they show were never handed out.

```sh
BASE=http://localhost:8080        # your deployment
READONLY=http://localhost:8080    # a deployment without issuing keys (for the 403 example)
KEY=...                           # one of ISSUE_KEYS, only on the designated issuer
```

The machine-readable description is [`server/openapi.yaml`](../server/openapi.yaml) (OpenAPI 3.1).

## Conventions

- Every response is JSON (`application/json; charset=utf-8`), field names in camelCase, stable across releases.
  The one exception is `registry` on a code card, which repeats the published registry row under its CSV column
  names, as published.
- Errors have one shape, with the HTTP status that fits:

  ```json
  {"error": {"code": "check_digit", "message": "The check digit of TG-FRJ-1058-3 does not match: the code was mistyped."}}
  ```

  | Status | `error.code` | When |
  |---|---|---|
  | 400 | `bad_request`, `bad_query`, `bad_code`, `check_digit`, `not_in_blocks` | a parameter is missing or malformed; a machine code with a wrong check digit or a number outside its area's blocks |
  | 401 | `unauthorized` | issuing or changing without a valid bearer key |
  | 403 | `read_only` | issuing or changing on a deployment that has no issuing keys |
  | 404 | `not_found`, `not_issued`, `not_in_blocks`, `unknown_name`, `street_code`, `outside` | nothing matches; a valid code nobody holds; a point outside Togo |
  | 405 | `method_not_allowed` | the path exists but not with that method (`Allow` lists the methods) |
  | 409 | `exists`, `retired`, `area_full` | the building already has a code (`error.existing` holds its card); a retired code cannot change; the name's range is used up |
  | 413 | `too_large` | a body over 64 kB |
  | 422 | `outside`, `too_far`, `bad_outline` | a point outside Togo; a door more than 80 m from its code; an outline under 6 m² or over 2 ha |
  | 429 | `rate_limited` | the key has issued its daily allowance (`ISSUE_PER_DAY`) |
  | 500 | `internal` | a server fault (logged) |

- People never see a check digit. The `remembered` form ("Fréau-Jardin 10 58") is what is written on a plate, said and
  typed; the `machine` form ("TG-FRJ-1058-2") carries the check digit and is for systems.
- A **zone** is one file of the registry: a préfecture (`KOZ` is Kozah), or `LOM`, the 69 quartiers of the former
  commune of Lomé. An **area** is a code area inside it: a quartier, a canton, or a named-place cell of a canton. In the
  registry rows, the column `zone` holds the area key; in the API, `area` is the area and `zone` the file.
- Reads are open. `POST` and `PATCH` need `Authorization: Bearer <key>` and work only on the deployment the State or
  N-WAYS LIMITED has designated as the issuer (see [server/README.md](../server/README.md#one-issuer)).

## GET /v1/health

Liveness and the registry in service.

```sh
curl -s "$BASE/v1/health"
```

`200`

```json
{
  "status": "ok",
  "country": "TG",
  "codes": 2768053,
  "registryExported": "2026-10-20T16:41:57Z",
  "changedSinceImport": false,
  "issuing": true
}
```


## GET /v1/info

The country, the zones with their counts, the licences, the credit line and the engine.

```sh
curl -s "$BASE/v1/info"
```

`200`

```json
{
  "country": "TG",
  "name": "Togo",
  "api": "1",
  "engine": "internal/addressing/tg (SPEC v1.0)",
  "spec": "SPEC v1.0",
  "registryExported": "2026-10-20T16:41:57Z",
  "importedAt": "2026-10-21T13:37:13Z",
  "counts": {
    "codes": 2768053,
    "byStatus": {"provisional": 2768053},
    "zones": 40,
    "areas": 1537,
    "numberedAreas": 1379
  },
  "zones": [
    {"key": "AGN", "name": "Agoè-Nyivé", "region": "Maritime", "codes": 224630},
    {"key": "AGO", "name": "Agou", "region": "Plateaux", "codes": 39214},
    {"key": "AKB", "name": "Akebou", "region": "Plateaux", "codes": 18606},
    {"key": "AMO", "name": "Amou", "region": "Plateaux", "codes": 57385},
    {"key": "ANI", "name": "Anié", "region": "Plateaux", "codes": 58828},
    {"key": "ASS", "name": "Assoli", "region": "Kara", "codes": 20616},
    {"key": "AVE", "name": "Avé", "region": "Maritime", "codes": 58626},
    {"key": "BAS", "name": "Bassar", "region": "Kara", "codes": 52690},
    {"key": "BIN", "name": "Binah", "region": "Kara", "codes": 31758},
    {"key": "BLI", "name": "Blitta", "region": "Centrale", "codes": 66731},
    {"key": "BMO", "name": "Bas-Mono", "region": "Maritime", "codes": 39486},
    {"key": "CIN", "name": "Cinkassé", "region": "Savanes", "codes": 34047},
    {"key": "DAN", "name": "Dankpen", "region": "Kara", "codes": 43748},
    {"key": "DNY", "name": "Danyi", "region": "Plateaux", "codes": 18217},
    {"key": "DOU", "name": "Doufelgou", "region": "Kara", "codes": 36505},
    {"key": "EMO", "name": "Est-Mono", "region": "Plateaux", "codes": 61549},
    {"key": "GOL", "name": "Golfe", "region": "Maritime", "codes": 143884},
    {"key": "HAH", "name": "Haho", "region": "Plateaux", "codes": 123898},
    {"key": "KER", "name": "Kéran", "region": "Kara", "codes": 34363},
    {"key": "KLO", "name": "Kloto", "region": "Plateaux", "codes": 60047},
    {"key": "KOZ", "name": "Kozah", "region": "Kara", "codes": 116897},
    {"key": "KPD", "name": "Kpendjal", "region": "Savanes", "codes": 27573},
    {"key": "KPE", "name": "Kpélé", "region": "Plateaux", "codes": 37451},
    {"key": "LAC", "name": "Lacs", "region": "Maritime", "codes": 88557},
    {"key": "LOM", "name": "Lomé (ancienne commune)", "region": "Maritime", "codes": 176951},
    {"key": "MMO", "name": "Moyen-Mono", "region": "Plateaux", "codes": 35513},
    {"key": "NKO", "name": "Naki-Ouest", "region": "Savanes", "codes": 37746},
    {"key": "OGO", "name": "Ogou", "region": "Plateaux", "codes": 100639},
    {"key": "OTI", "name": "Oti", "region": "Savanes", "codes": 41142},
    {"key": "OTS", "name": "Oti-Sud", "region": "Savanes", "codes": 37616},
    {"key": "PMO", "name": "Plaine du Mô", "region": "Centrale", "codes": 10072},
    {"key": "SOT", "name": "Sotouboua", "region": "Centrale", "codes": 59204},
    {"key": "TCB", "name": "Tchamba", "region": "Centrale", "codes": 72162},
    {"key": "TCH", "name": "Tchaoudjo", "region": "Centrale", "codes": 89994},
    {"key": "TDJ", "name": "Tandjouaré", "region": "Savanes", "codes": 48391},
    {"key": "TON", "name": "Tône", "region": "Savanes", "codes": 121567},
    {"key": "VOG", "name": "Vo", "region": "Maritime", "codes": 108596},
    {"key": "WAW", "name": "Wawa", "region": "Plateaux", "codes": 37596},
    {"key": "YOT", "name": "Yoto", "region": "Maritime", "codes": 72312},
    {"key": "ZIO", "name": "Zio", "region": "Maritime", "codes": 223246}
  ],
  "licences": {"data": "ODbL-1.0", "code": "Apache-2.0", "documents": "CC-BY-4.0"},
  "credit": "N-Ways Addressing for Togo, © N-WAYS LIMITED (nways.ng)",
  "creditUrl": "https://github.com/n-ways/open-addresses-togo",
  "issuing": true,
  "issuePerDay": 5,
  "forms": {"remembered": "Fréau-Jardin 10 58", "machine": "TG-FRJ-1058-2", "spot": "FRJ-54-4R"}
}
```


## GET /v1/codes/{machine}

The full card of a code: every registry column, the forms, the area and zone, the spot code and the Plus Code of the
entrance. The machine form may be typed in any case.

```sh
curl -s "$BASE/v1/codes/TG-FRJ-1058-2"
```

`200`

```json
{
  "machine": "TG-FRJ-1058-2",
  "remembered": "Fréau-Jardin 10 58",
  "home": "Fréau-Jardin 1058",
  "spoken": "Fréau-Jardin, dix, cinquante-huit",
  "plateName": "Fréau-Jardin",
  "number": 1058,
  "check": 2,
  "status": "provisional",
  "issued": "bulk",
  "issuedAt": "2026-10-20T16:33:18Z",
  "officialAddress": "Rue Mission Tové, Lomé",
  "place": "Lomé",
  "entrance": {"lat": 6.1317765, "lng": 1.2234008, "kind": "centre"},
  "spotCode": "FRJ-54-4R",
  "plusCode": "6FR346JF+P96",
  "area": {
    "key": "FRJ",
    "index": 32,
    "kind": "lome-quartier",
    "plateName": "Fréau-Jardin",
    "officialName": "Fréau-Jardin",
    "aliases": [],
    "prefecture": "Lomé (ancienne commune)",
    "region": "Maritime",
    "zone": "LOM",
    "place": "Lomé",
    "numbered": true,
    "nameKey": "FREAUJARDIN",
    "nameId": 1352,
    "blocks": [[1000, 1499]],
    "numberLength": 4,
    "nameProvisional": false,
    "officialSystem": "DAGL - adressage du Grand Lomé",
    "point": {"lat": 6.131712, "lng": 1.223315},
    "box": [1.22204, 6.13038, 1.22759, 6.13306]
  },
  "zone": {"key": "LOM", "name": "Lomé (ancienne commune)"},
  "building": {
    "class": "residential",
    "use": "residential",
    "kind": "building",
    "structures": 1,
    "floorAreaM2": 19.5,
    "rule": "single",
    "estate": null
  },
  "registry": {
    "machine": "TG-FRJ-1058-2",
    "home": "Fréau-Jardin 1058",
    "written": "Fréau-Jardin 10 58",
    "zone": "FRJ",
    "official_name": "Fréau-Jardin",
    "number": "1058",
    "check": "2",
    "status": "provisional",
    "issued": "bulk",
    "issued_at": "2026-10-20T16:33:18Z",
    "entrance_lat": "6.1317765",
    "entrance_lng": "1.2234008",
    "entrance_kind": "centre",
    "spot_code": "FRJ-54-4R",
    "official_address": "Rue Mission Tové, Lomé",
    "class": "residential",
    "use": "residential",
    "kind": "building",
    "structures": "1",
    "floor_area_m2": "19.5",
    "rule": "single",
    "estate": ""
  },
  "credit": "N-Ways Addressing for Togo, © N-WAYS LIMITED (nways.ng)"
}
```


A wrong check digit is refused, never corrected:

```sh
curl -s "$BASE/v1/codes/TG-FRJ-1058-3"
```

`400`

```json
{
  "error": {
    "code": "check_digit",
    "message": "The check digit of TG-FRJ-1058-3 does not match: the code was mistyped."
  }
}
```


A valid code that no compound holds:

```sh
curl -s "$BASE/v1/codes/TG-FRJ-1499-8"
```

`404`

```json
{"error": {"code": "not_issued", "message": "TG-FRJ-1499-8 is a valid code, but no compound has it."}}
```


## GET /v1/find?q=

One box for everything people type: a code as they say or write it (any spacing, case or accents, the number whole
or in pairs), a machine code, a spot code, or an official address of Grand Lomé. A remembered code needs nothing
else: the name and the number alone decide the area anywhere in Togo.

```sh
curl -s "$BASE/v1/find?q=Zongo%201%2041%2098"
```

`200`

```json
{
  "query": "Zongo 1 41 98",
  "kind": "remembered",
  "count": 1,
  "results": [
    {
      "machine": "TG-KOZ0615-14198-6",
      "remembered": "Zongo 1 41 98",
      "home": "Zongo 14198",
      "spoken": "Zongo, un, quarante et un, quatre-vingt-dix-huit",
      "plateName": "Zongo",
      "number": 14198,
      "check": 6,
      "status": "provisional",
      "issued": "bulk",
      "issuedAt": "2026-10-20T16:32:48Z",
      "officialAddress": null,
      "place": "Kozah",
      "entrance": {"lat": 9.5510797, "lng": 1.186049, "kind": "centre"},
      "spotCode": "KOZ06-454-R32",
      "plusCode": "6FX3H52P+CCM",
      "area": {
        "key": "KOZ0615",
        "index": 1182,
        "kind": "cell",
        "plateName": "Zongo",
        "officialName": "Zongo",
        "aliases": [],
        "prefecture": "Kozah",
        "region": "Kara",
        "zone": "KOZ",
        "place": "Kozah",
        "numbered": true,
        "nameKey": "ZONGO",
        "nameId": 1228,
        "blocks": [[10000, 23299]],
        "numberLength": 5,
        "nameProvisional": false,
        "officialSystem": null,
        "point": {"lat": 9.54376, "lng": 1.182208},
        "box": [1.13982, 9.52559, 1.2627, 9.65524],
        "canton": {"key": "KOZ06", "name": "Lama"}
      },
      "zone": {"key": "KOZ", "name": "Kozah"},
      "building": {
        "class": "residential",
        "use": "residential",
        "kind": "compound",
        "structures": 2,
        "floorAreaM2": 72.1,
        "rule": "annex",
        "estate": null
      },
      "registry": {
        "machine": "TG-KOZ0615-14198-6",
        "home": "Zongo 14198",
        "written": "Zongo 1 41 98",
        "zone": "KOZ0615",
        "official_name": "Zongo",
        "number": "14198",
        "check": "6",
        "status": "provisional",
        "issued": "bulk",
        "issued_at": "2026-10-20T16:32:48Z",
        "entrance_lat": "9.5510797",
        "entrance_lng": "1.1860490",
        "entrance_kind": "centre",
        "spot_code": "KOZ06-454-R32",
        "official_address": "",
        "class": "residential",
        "use": "residential",
        "kind": "compound",
        "structures": "2",
        "floor_area_m2": "72.1",
        "rule": "annex",
        "estate": ""
      },
      "credit": "N-Ways Addressing for Togo, © N-WAYS LIMITED (nways.ng)"
    }
  ]
}
```


```sh
curl -s "$BASE/v1/find?q=tg-koz0615-14198-6"
```

`200`

```json
{
  "query": "tg-koz0615-14198-6",
  "kind": "machine",
  "count": 1,
  "results": [
    {
      "machine": "TG-KOZ0615-14198-6",
      "remembered": "Zongo 1 41 98",
      "home": "Zongo 14198",
      "spoken": "Zongo, un, quarante et un, quatre-vingt-dix-huit",
      "plateName": "Zongo",
      "number": 14198,
      "check": 6,
      "status": "provisional",
      "issued": "bulk",
      "issuedAt": "2026-10-20T16:32:48Z",
      "officialAddress": null,
      "place": "Kozah",
      "entrance": {"lat": 9.5510797, "lng": 1.186049, "kind": "centre"},
      "spotCode": "KOZ06-454-R32",
      "plusCode": "6FX3H52P+CCM",
      "area": {
        "key": "KOZ0615",
        "index": 1182,
        "kind": "cell",
        "plateName": "Zongo",
        "officialName": "Zongo",
        "aliases": [],
        "prefecture": "Kozah",
        "region": "Kara",
        "zone": "KOZ",
        "place": "Kozah",
        "numbered": true,
        "nameKey": "ZONGO",
        "nameId": 1228,
        "blocks": [[10000, 23299]],
        "numberLength": 5,
        "nameProvisional": false,
        "officialSystem": null,
        "point": {"lat": 9.54376, "lng": 1.182208},
        "box": [1.13982, 9.52559, 1.2627, 9.65524],
        "canton": {"key": "KOZ06", "name": "Lama"}
      },
      "zone": {"key": "KOZ", "name": "Kozah"},
      "building": {
        "class": "residential",
        "use": "residential",
        "kind": "compound",
        "structures": 2,
        "floorAreaM2": 72.1,
        "rule": "annex",
        "estate": null
      },
      "registry": {
        "machine": "TG-KOZ0615-14198-6",
        "home": "Zongo 14198",
        "written": "Zongo 1 41 98",
        "zone": "KOZ0615",
        "official_name": "Zongo",
        "number": "14198",
        "check": "6",
        "status": "provisional",
        "issued": "bulk",
        "issued_at": "2026-10-20T16:32:48Z",
        "entrance_lat": "9.5510797",
        "entrance_lng": "1.1860490",
        "entrance_kind": "centre",
        "spot_code": "KOZ06-454-R32",
        "official_address": "",
        "class": "residential",
        "use": "residential",
        "kind": "compound",
        "structures": "2",
        "floor_area_m2": "72.1",
        "rule": "annex",
        "estate": ""
      },
      "credit": "N-Ways Addressing for Togo, © N-WAYS LIMITED (nways.ng)"
    }
  ]
}
```


A spot code finds the compound whose entrance lies within 15 m of the spot's centre:

```sh
curl -s "$BASE/v1/find?q=FRJ-54-4R"
```

`200`

```json
{
  "query": "FRJ-54-4R",
  "kind": "spot",
  "point": {"lat": 6.1317902, "lng": 1.2234039},
  "count": 1,
  "results": [
    {
      "machine": "TG-FRJ-1058-2",
      "remembered": "Fréau-Jardin 10 58",
      "home": "Fréau-Jardin 1058",
      "spoken": "Fréau-Jardin, dix, cinquante-huit",
      "plateName": "Fréau-Jardin",
      "number": 1058,
      "check": 2,
      "status": "provisional",
      "issued": "bulk",
      "issuedAt": "2026-10-20T16:33:18Z",
      "officialAddress": "Rue Mission Tové, Lomé",
      "place": "Lomé",
      "entrance": {"lat": 6.1317765, "lng": 1.2234008, "kind": "centre"},
      "spotCode": "FRJ-54-4R",
      "plusCode": "6FR346JF+P96",
      "area": {
        "key": "FRJ",
        "index": 32,
        "kind": "lome-quartier",
        "plateName": "Fréau-Jardin",
        "officialName": "Fréau-Jardin",
        "aliases": [],
        "prefecture": "Lomé (ancienne commune)",
        "region": "Maritime",
        "zone": "LOM",
        "place": "Lomé",
        "numbered": true,
        "nameKey": "FREAUJARDIN",
        "nameId": 1352,
        "blocks": [[1000, 1499]],
        "numberLength": 4,
        "nameProvisional": false,
        "officialSystem": "DAGL - adressage du Grand Lomé",
        "point": {"lat": 6.131712, "lng": 1.223315},
        "box": [1.22204, 6.13038, 1.22759, 6.13306]
      },
      "zone": {"key": "LOM", "name": "Lomé (ancienne commune)"},
      "building": {
        "class": "residential",
        "use": "residential",
        "kind": "building",
        "structures": 1,
        "floorAreaM2": 19.5,
        "rule": "single",
        "estate": null
      },
      "registry": {
        "machine": "TG-FRJ-1058-2",
        "home": "Fréau-Jardin 1058",
        "written": "Fréau-Jardin 10 58",
        "zone": "FRJ",
        "official_name": "Fréau-Jardin",
        "number": "1058",
        "check": "2",
        "status": "provisional",
        "issued": "bulk",
        "issued_at": "2026-10-20T16:33:18Z",
        "entrance_lat": "6.1317765",
        "entrance_lng": "1.2234008",
        "entrance_kind": "centre",
        "spot_code": "FRJ-54-4R",
        "official_address": "Rue Mission Tové, Lomé",
        "class": "residential",
        "use": "residential",
        "kind": "building",
        "structures": "1",
        "floor_area_m2": "19.5",
        "rule": "single",
        "estate": ""
      },
      "credit": "N-Ways Addressing for Togo, © N-WAYS LIMITED (nways.ng)",
      "distanceM": 1.5
    }
  ]
}
```


An official address returns every compound at it (here two; at most 100 are listed, `count` gives the total):

```sh
curl -s "$BASE/v1/find?q=Rue%2058%20TKH"
```

`200`

```json
{
  "query": "Rue 58 TKH",
  "kind": "official",
  "count": 2,
  "results": [
    {
      "machine": "TG-TKO-2848-2",
      "remembered": "Tokoin-Ouest 28 48",
      "home": "Tokoin-Ouest 2848",
      "spoken": "Tokoin-Ouest, vingt-huit, quarante-huit",
      "plateName": "Tokoin-Ouest",
      "number": 2848,
      "check": 2,
      "status": "provisional",
      "issued": "bulk",
      "issuedAt": "2026-10-20T16:33:22Z",
      "officialAddress": "Rue 58 TKH, Lomé",
      "place": "Lomé",
      "entrance": {"lat": 6.1415538, "lng": 1.2081512, "kind": "centre"},
      "spotCode": "TKO-2FM-GJ",
      "plusCode": "6FR346R5+J7C",
      "area": {
        "key": "TKO",
        "index": 62,
        "kind": "lome-quartier",
        "plateName": "Tokoin-Ouest",
        "officialName": "Tokoin-Ouest",
        "aliases": [],
        "prefecture": "Lomé (ancienne commune)",
        "region": "Maritime",
        "zone": "LOM",
        "place": "Lomé",
        "numbered": true,
        "nameKey": "TOKOINUEST",
        "nameId": 1399,
        "blocks": [[1000, 5699]],
        "numberLength": 4,
        "nameProvisional": false,
        "officialSystem": "DAGL - adressage du Grand Lomé",
        "point": {"lat": 6.144757, "lng": 1.20207},
        "box": [1.19943, 6.13662, 1.20971, 6.1512]
      },
      "zone": {"key": "LOM", "name": "Lomé (ancienne commune)"},
      "building": {
        "class": "commercial",
        "use": "commercial",
        "kind": "building",
        "structures": 1,
        "floorAreaM2": 85.7,
        "rule": "single",
        "estate": null
      },
      "registry": {
        "machine": "TG-TKO-2848-2",
        "home": "Tokoin-Ouest 2848",
        "written": "Tokoin-Ouest 28 48",
        "zone": "TKO",
        "official_name": "Tokoin-Ouest",
        "number": "2848",
        "check": "2",
        "status": "provisional",
        "issued": "bulk",
        "issued_at": "2026-10-20T16:33:22Z",
        "entrance_lat": "6.1415538",
        "entrance_lng": "1.2081512",
        "entrance_kind": "centre",
        "spot_code": "TKO-2FM-GJ",
        "official_address": "Rue 58 TKH, Lomé",
        "class": "commercial",
        "use": "commercial",
        "kind": "building",
        "structures": "1",
        "floor_area_m2": "85.7",
        "rule": "single",
        "estate": ""
      },
      "credit": "N-Ways Addressing for Togo, © N-WAYS LIMITED (nways.ng)"
    },
    {
      "machine": "TG-TKO-3317-8",
      "remembered": "Tokoin-Ouest 33 17",
      "home": "Tokoin-Ouest 3317",
      "spoken": "Tokoin-Ouest, trente-trois, dix-sept",
      "plateName": "Tokoin-Ouest",
      "number": 3317,
      "check": 8,
      "status": "provisional",
      "issued": "bulk",
      "issuedAt": "2026-10-20T16:33:22Z",
      "officialAddress": "Rue 58 TKH, Lomé",
      "place": "Lomé",
      "entrance": {"lat": 6.1402284, "lng": 1.2092527, "kind": "centre"},
      "spotCode": "TKO-29R-9C",
      "plusCode": "6FR346R5+3PR",
      "area": {
        "key": "TKO",
        "index": 62,
        "kind": "lome-quartier",
        "plateName": "Tokoin-Ouest",
        "officialName": "Tokoin-Ouest",
        "aliases": [],
        "prefecture": "Lomé (ancienne commune)",
        "region": "Maritime",
        "zone": "LOM",
        "place": "Lomé",
        "numbered": true,
        "nameKey": "TOKOINUEST",
        "nameId": 1399,
        "blocks": [[1000, 5699]],
        "numberLength": 4,
        "nameProvisional": false,
        "officialSystem": "DAGL - adressage du Grand Lomé",
        "point": {"lat": 6.144757, "lng": 1.20207},
        "box": [1.19943, 6.13662, 1.20971, 6.1512]
      },
      "zone": {"key": "LOM", "name": "Lomé (ancienne commune)"},
      "building": {
        "class": "residential",
        "use": "residential",
        "kind": "building",
        "structures": 1,
        "floorAreaM2": 111.9,
        "rule": "single",
        "estate": null
      },
      "registry": {
        "machine": "TG-TKO-3317-8",
        "home": "Tokoin-Ouest 3317",
        "written": "Tokoin-Ouest 33 17",
        "zone": "TKO",
        "official_name": "Tokoin-Ouest",
        "number": "3317",
        "check": "8",
        "status": "provisional",
        "issued": "bulk",
        "issued_at": "2026-10-20T16:33:22Z",
        "entrance_lat": "6.1402284",
        "entrance_lng": "1.2092527",
        "entrance_kind": "centre",
        "spot_code": "TKO-29R-9C",
        "official_address": "Rue 58 TKH, Lomé",
        "class": "residential",
        "use": "residential",
        "kind": "building",
        "structures": "1",
        "floor_area_m2": "111.9",
        "rule": "single",
        "estate": ""
      },
      "credit": "N-Ways Addressing for Togo, © N-WAYS LIMITED (nways.ng)"
    }
  ]
}
```


```sh
curl -s "$BASE/v1/find?q=TG-FRJ-1058-3"
```

`400`

```json
{
  "error": {
    "code": "check_digit",
    "message": "The check digit of TG-FRJ-1058-3 does not match: the code was mistyped."
  }
}
```


A number outside every block of the name cannot be a code:

```sh
curl -s "$BASE/v1/find?q=Tokpo%2054%2017"
```

`404`

```json
{
  "error": {
    "code": "not_in_blocks",
    "message": "No N-Ways address Tokpo 54 17: that number is in no block of the name 'Tokpo'."
  }
}
```


A Lomé street code is recognised as such and never read as an N-Ways code:

```sh
curl -s "$BASE/v1/find?q=165%20AMT"
```

`404`

```json
{
  "error": {
    "code": "street_code",
    "message": "165 AMT is a Lomé street code (street 165 of quartier AMT), not an N-Ways code. Search the full official address, such as \"Rue 89 AFG\", or find the building with /v1/at."
  }
}
```


```sh
curl -s "$BASE/v1/find?q=Atlantis%2010%2058"
```

`404`

```json
{
  "error": {
    "code": "unknown_name",
    "message": "No code area of Togo is called 'Atlantis', and no official address matches 'Atlantis 10 58'."
  }
}
```


## GET /v1/at?lat=&lng=

The code of the compound at a point: the nearest live code whose entrance lies within 12 m. Otherwise `status` is
`none`, with the code area the point lies in, the area a new code there would take (`newCodeArea`, by the issuer's
rule) and the point's spot code. A point in no quartier or canton outline that has a spot code (a compound in a gap
between outlines, or just over a border line, SPEC §5) is in Togo: it is answered like any other, and its `area` is
the one a new code there would take. Only a point without a spot code answers `404 outside`. A point more than
300 m across the national border answers `newCodeArea: null`: no code can be issued there.

```sh
curl -s "$BASE/v1/at?lat=6.1317765&lng=1.2234008"
```

`200`

```json
{
  "status": "found",
  "distanceM": 0.0,
  "code": {
    "machine": "TG-FRJ-1058-2",
    "remembered": "Fréau-Jardin 10 58",
    "home": "Fréau-Jardin 1058",
    "spoken": "Fréau-Jardin, dix, cinquante-huit",
    "plateName": "Fréau-Jardin",
    "number": 1058,
    "check": 2,
    "status": "provisional",
    "issued": "bulk",
    "issuedAt": "2026-10-20T16:33:18Z",
    "officialAddress": "Rue Mission Tové, Lomé",
    "place": "Lomé",
    "entrance": {"lat": 6.1317765, "lng": 1.2234008, "kind": "centre"},
    "spotCode": "FRJ-54-4R",
    "plusCode": "6FR346JF+P96",
    "area": {
      "key": "FRJ",
      "index": 32,
      "kind": "lome-quartier",
      "plateName": "Fréau-Jardin",
      "officialName": "Fréau-Jardin",
      "aliases": [],
      "prefecture": "Lomé (ancienne commune)",
      "region": "Maritime",
      "zone": "LOM",
      "place": "Lomé",
      "numbered": true,
      "nameKey": "FREAUJARDIN",
      "nameId": 1352,
      "blocks": [[1000, 1499]],
      "numberLength": 4,
      "nameProvisional": false,
      "officialSystem": "DAGL - adressage du Grand Lomé",
      "point": {"lat": 6.131712, "lng": 1.223315},
      "box": [1.22204, 6.13038, 1.22759, 6.13306]
    },
    "zone": {"key": "LOM", "name": "Lomé (ancienne commune)"},
    "building": {
      "class": "residential",
      "use": "residential",
      "kind": "building",
      "structures": 1,
      "floorAreaM2": 19.5,
      "rule": "single",
      "estate": null
    },
    "registry": {
      "machine": "TG-FRJ-1058-2",
      "home": "Fréau-Jardin 1058",
      "written": "Fréau-Jardin 10 58",
      "zone": "FRJ",
      "official_name": "Fréau-Jardin",
      "number": "1058",
      "check": "2",
      "status": "provisional",
      "issued": "bulk",
      "issued_at": "2026-10-20T16:33:18Z",
      "entrance_lat": "6.1317765",
      "entrance_lng": "1.2234008",
      "entrance_kind": "centre",
      "spot_code": "FRJ-54-4R",
      "official_address": "Rue Mission Tové, Lomé",
      "class": "residential",
      "use": "residential",
      "kind": "building",
      "structures": "1",
      "floor_area_m2": "19.5",
      "rule": "single",
      "estate": ""
    },
    "credit": "N-Ways Addressing for Togo, © N-WAYS LIMITED (nways.ng)"
  },
  "area": {
    "key": "FRJ",
    "index": 32,
    "kind": "lome-quartier",
    "plateName": "Fréau-Jardin",
    "officialName": "Fréau-Jardin",
    "aliases": [],
    "prefecture": "Lomé (ancienne commune)",
    "region": "Maritime",
    "zone": "LOM",
    "place": "Lomé",
    "numbered": true,
    "nameKey": "FREAUJARDIN",
    "nameId": 1352,
    "blocks": [[1000, 1499]],
    "numberLength": 4,
    "nameProvisional": false,
    "officialSystem": "DAGL - adressage du Grand Lomé",
    "point": {"lat": 6.131712, "lng": 1.223315},
    "box": [1.22204, 6.13038, 1.22759, 6.13306]
  }
}
```


```sh
curl -s "$BASE/v1/at?lat=6.1320&lng=1.2240"
```

`200`

```json
{
  "status": "none",
  "area": {
    "key": "FRJ",
    "index": 32,
    "kind": "lome-quartier",
    "plateName": "Fréau-Jardin",
    "officialName": "Fréau-Jardin",
    "aliases": [],
    "prefecture": "Lomé (ancienne commune)",
    "region": "Maritime",
    "zone": "LOM",
    "place": "Lomé",
    "numbered": true,
    "nameKey": "FREAUJARDIN",
    "nameId": 1352,
    "blocks": [[1000, 1499]],
    "numberLength": 4,
    "nameProvisional": false,
    "officialSystem": "DAGL - adressage du Grand Lomé",
    "point": {"lat": 6.131712, "lng": 1.223315},
    "box": [1.22204, 6.13038, 1.22759, 6.13306]
  },
  "newCodeArea": "FRJ",
  "spotCode": "FRJ-55-FR"
}
```


```sh
curl -s "$BASE/v1/at?lat=5.8&lng=1.3"
```

`404`

```json
{"error": {"code": "outside", "message": "The point 5.800000, 1.300000 is outside Togo."}}
```


## GET /v1/near?lat=&lng=&radius=&limit=

Live codes within `radius` metres (default 100, at most 500), nearest first, at most `limit` (default and maximum
100). `more` is true when the radius holds more than were listed.

```sh
curl -s "$BASE/v1/near?lat=6.1317765&lng=1.2234008&radius=25&limit=3"
```

`200`

```json
{
  "point": {"lat": 6.1317765, "lng": 1.2234008},
  "radiusM": 25.0,
  "count": 3,
  "more": false,
  "results": [
    {
      "machine": "TG-FRJ-1058-2",
      "remembered": "Fréau-Jardin 10 58",
      "status": "provisional",
      "entrance": {"lat": 6.1317765, "lng": 1.2234008, "kind": "centre"},
      "spotCode": "FRJ-54-4R",
      "officialAddress": "Rue Mission Tové, Lomé",
      "area": "FRJ",
      "distanceM": 0.0
    },
    {
      "machine": "TG-FRJ-1061-8",
      "remembered": "Fréau-Jardin 10 61",
      "status": "provisional",
      "entrance": {"lat": 6.1319606, "lng": 1.2233874, "kind": "centre"},
      "spotCode": "FRJ-54-CP",
      "officialAddress": "Rue Mission Tové, Lomé",
      "area": "FRJ",
      "distanceM": 20.4
    },
    {
      "machine": "TG-FRJ-1062-6",
      "remembered": "Fréau-Jardin 10 62",
      "status": "provisional",
      "entrance": {"lat": 6.131964, "lng": 1.2232843, "kind": "centre"},
      "spotCode": "FRJ-54-CJ",
      "officialAddress": "Rue Mission Tové, Lomé",
      "area": "FRJ",
      "distanceM": 24.4
    }
  ]
}
```


```sh
curl -s "$BASE/v1/near?lat=6.1317765&lng=1.2234008&radius=900"
```

`400`

```json
{"error": {"code": "bad_request", "message": "radius must be between 1 and 500."}}
```


## GET /v1/verify?code=

Checks a machine code without failing: syntax, check digit, block, and whether it is issued.

```sh
curl -s "$BASE/v1/verify?code=TG-FRJ-1058-2"
```

`200`

```json
{
  "code": "TG-FRJ-1058-2",
  "syntax": true,
  "checkDigit": true,
  "inBlocks": true,
  "issued": true,
  "status": "provisional",
  "machine": "TG-FRJ-1058-2",
  "remembered": "Fréau-Jardin 10 58"
}
```


Two digits swapped (1085 for 1058) are caught by the check digit:

```sh
curl -s "$BASE/v1/verify?code=TG-FRJ-1085-2"
```

`200`

```json
{
  "code": "TG-FRJ-1085-2",
  "syntax": true,
  "checkDigit": false,
  "inBlocks": true,
  "issued": false,
  "status": null,
  "machine": null,
  "reason": "the check digit does not match: a mistyped code"
}
```


## GET /v1/spot?lat=&lng= and GET /v1/spot/decode?code=

Spot codes name any point in Togo to about 3.4 m, offline, from the area table alone. A point in no quartier or
canton outline (a thin gap between outlines, or just over a border line) takes the frame of the nearest outline within
1,100 m that holds it, else the nearest edge cell of a frame at most 200 cells away (SPEC §5); any other point answers
`404 outside`.

```sh
curl -s "$BASE/v1/spot?lat=6.1317765&lng=1.2234008"
```

`200`

```json
{
  "spotCode": "FRJ-54-4R",
  "point": {"lat": 6.1317765, "lng": 1.2234008},
  "centre": {"lat": 6.1317902, "lng": 1.2234039},
  "cellM": [3.37, 3.38],
  "area": "FRJ"
}
```


```sh
curl -s "$BASE/v1/spot/decode?code=FRJ-54-4R"
```

`200`

```json
{
  "spotCode": "FRJ-54-4R",
  "centre": {"lat": 6.1317902, "lng": 1.2234039},
  "cellM": [3.37, 3.38],
  "frame": {
    "key": "FRJ",
    "index": 32,
    "kind": "lome-quartier",
    "plateName": "Fréau-Jardin",
    "officialName": "Fréau-Jardin",
    "aliases": [],
    "prefecture": "Lomé (ancienne commune)",
    "region": "Maritime",
    "zone": "LOM",
    "place": "Lomé",
    "numbered": true,
    "nameKey": "FREAUJARDIN",
    "nameId": 1352,
    "blocks": [[1000, 1499]],
    "numberLength": 4,
    "nameProvisional": false,
    "officialSystem": "DAGL - adressage du Grand Lomé",
    "point": {"lat": 6.131712, "lng": 1.223315},
    "box": [1.22204, 6.13038, 1.22759, 6.13306]
  }
}
```


```sh
curl -s "$BASE/v1/spot/decode?code=FRJ-54"
```

`400`

```json
{"error": {"code": "bad_code", "message": "Not a Togo spot code: 'FRJ-54'."}}
```


## GET /v1/zones and GET /v1/zones/{key}

```sh
curl -s "$BASE/v1/zones"
```

`200`

```json
{
  "count": 40,
  "zones": [
    {
      "key": "AGN",
      "name": "Agoè-Nyivé",
      "region": "Maritime",
      "codes": 224630,
      "areas": 14,
      "numberedAreas": 12
    },
    {"key": "AGO", "name": "Agou", "region": "Plateaux", "codes": 39214, "areas": 51, "numberedAreas": 47},
    {"key": "AKB", "name": "Akebou", "region": "Plateaux", "codes": 18606, "areas": 13, "numberedAreas": 12},
    {"key": "AMO", "name": "Amou", "region": "Plateaux", "codes": 57385, "areas": 43, "numberedAreas": 38},
    {"key": "ANI", "name": "Anié", "region": "Plateaux", "codes": 58828, "areas": 49, "numberedAreas": 44},
    {"key": "ASS", "name": "Assoli", "region": "Kara", "codes": 20616, "areas": 11, "numberedAreas": 9},
    {"key": "AVE", "name": "Avé", "region": "Maritime", "codes": 58626, "areas": 66, "numberedAreas": 61},
    {"key": "BAS", "name": "Bassar", "region": "Kara", "codes": 52690, "areas": 36, "numberedAreas": 33},
    {"key": "BIN", "name": "Binah", "region": "Kara", "codes": 31758, "areas": 17, "numberedAreas": 16},
    {"key": "BLI", "name": "Blitta", "region": "Centrale", "codes": 66731, "areas": 51, "numberedAreas": 45},
    {"key": "BMO", "name": "Bas-Mono", "region": "Maritime", "codes": 39486, "areas": 27, "numberedAreas": 24},
    {"key": "CIN", "name": "Cinkassé", "region": "Savanes", "codes": 34047, "areas": 11, "numberedAreas": 10},
    {"key": "DAN", "name": "Dankpen", "region": "Kara", "codes": 43748, "areas": 24, "numberedAreas": 22},
    {"key": "DNY", "name": "Danyi", "region": "Plateaux", "codes": 18217, "areas": 23, "numberedAreas": 22},
    {"key": "DOU", "name": "Doufelgou", "region": "Kara", "codes": 36505, "areas": 21, "numberedAreas": 19},
    {"key": "EMO", "name": "Est-Mono", "region": "Plateaux", "codes": 61549, "areas": 39, "numberedAreas": 34},
    {"key": "GOL", "name": "Golfe", "region": "Maritime", "codes": 143884, "areas": 12, "numberedAreas": 10},
    {"key": "HAH", "name": "Haho", "region": "Plateaux", "codes": 123898, "areas": 72, "numberedAreas": 65},
    {"key": "KER", "name": "Kéran", "region": "Kara", "codes": 34363, "areas": 28, "numberedAreas": 26},
    {"key": "KLO", "name": "Kloto", "region": "Plateaux", "codes": 60047, "areas": 42, "numberedAreas": 39},
    {"key": "KOZ", "name": "Kozah", "region": "Kara", "codes": 116897, "areas": 50, "numberedAreas": 44},
    {"key": "KPD", "name": "Kpendjal", "region": "Savanes", "codes": 27573, "areas": 33, "numberedAreas": 30},
    {"key": "KPE", "name": "Kpélé", "region": "Plateaux", "codes": 37451, "areas": 15, "numberedAreas": 14},
    {"key": "LAC", "name": "Lacs", "region": "Maritime", "codes": 88557, "areas": 39, "numberedAreas": 33},
    {
      "key": "LOM",
      "name": "Lomé (ancienne commune)",
      "region": "Maritime",
      "codes": 176951,
      "areas": 70,
      "numberedAreas": 69
    },
    {
      "key": "MMO",
      "name": "Moyen-Mono",
      "region": "Plateaux",
      "codes": 35513,
      "areas": 27,
      "numberedAreas": 24
    },
    {
      "key": "NKO",
      "name": "Naki-Ouest",
      "region": "Savanes",
      "codes": 37746,
      "areas": 39,
      "numberedAreas": 33
    },
    {"key": "OGO", "name": "Ogou", "region": "Plateaux", "codes": 100639, "areas": 102, "numberedAreas": 94},
    {"key": "OTI", "name": "Oti", "region": "Savanes", "codes": 41142, "areas": 36, "numberedAreas": 31},
    {"key": "OTS", "name": "Oti-Sud", "region": "Savanes", "codes": 37616, "areas": 43, "numberedAreas": 37},
    {
      "key": "PMO",
      "name": "Plaine du Mô",
      "region": "Centrale",
      "codes": 10072,
      "areas": 5,
      "numberedAreas": 5
    },
    {
      "key": "SOT",
      "name": "Sotouboua",
      "region": "Centrale",
      "codes": 59204,
      "areas": 22,
      "numberedAreas": 19
    },
    {"key": "TCB", "name": "Tchamba", "region": "Centrale", "codes": 72162, "areas": 30, "numberedAreas": 26},
    {
      "key": "TCH",
      "name": "Tchaoudjo",
      "region": "Centrale",
      "codes": 89994,
      "areas": 39,
      "numberedAreas": 33
    },
    {
      "key": "TDJ",
      "name": "Tandjouaré",
      "region": "Savanes",
      "codes": 48391,
      "areas": 25,
      "numberedAreas": 23
    },
    {"key": "TON", "name": "Tône", "region": "Savanes", "codes": 121567, "areas": 57, "numberedAreas": 49},
    {"key": "VOG", "name": "Vo", "region": "Maritime", "codes": 108596, "areas": 61, "numberedAreas": 53},
    {"key": "WAW", "name": "Wawa", "region": "Plateaux", "codes": 37596, "areas": 30, "numberedAreas": 27},
    {"key": "YOT", "name": "Yoto", "region": "Maritime", "codes": 72312, "areas": 51, "numberedAreas": 45},
    {"key": "ZIO", "name": "Zio", "region": "Maritime", "codes": 223246, "areas": 113, "numberedAreas": 102}
  ]
}
```


```sh
curl -s "$BASE/v1/zones/PMO"
```

`200`

```json
{
  "key": "PMO",
  "name": "Plaine du Mô",
  "region": "Centrale",
  "codes": 10072,
  "areas": [
    {
      "key": "PMO01",
      "index": 122,
      "kind": "canton",
      "plateName": "Boulohou",
      "officialName": "Boulohou",
      "aliases": [],
      "prefecture": "Plaine du Mô",
      "region": "Centrale",
      "zone": "PMO",
      "place": "Plaine du Mô",
      "numbered": true,
      "nameKey": "BULOHU",
      "nameId": 330,
      "blocks": [[1000, 3399]],
      "numberLength": 4,
      "nameProvisional": false,
      "officialSystem": null,
      "point": {"lat": 8.698434, "lng": 0.660819},
      "box": [0.5768, 8.57173, 0.78811, 8.8044],
      "codes": 1198
    },
    {
      "key": "PMO02",
      "index": 123,
      "kind": "canton",
      "plateName": "Djarkpanga",
      "officialName": "Djarkpanga",
      "aliases": [],
      "prefecture": "Plaine du Mô",
      "region": "Centrale",
      "zone": "PMO",
      "place": "Plaine du Mô",
      "numbered": true,
      "nameKey": "JARKPANGA",
      "nameId": 565,
      "blocks": [[1000, 7499]],
      "numberLength": 4,
      "nameProvisional": false,
      "officialSystem": null,
      "point": {"lat": 8.79375, "lng": 0.53383},
      "box": [0.4323, 8.67846, 0.62349, 8.87867],
      "codes": 3217
    },
    {
      "key": "PMO03",
      "index": 124,
      "kind": "canton",
      "plateName": "Kagnigbara",
      "officialName": "Kagnigbara",
      "aliases": [],
      "prefecture": "Plaine du Mô",
      "region": "Centrale",
      "zone": "PMO",
      "place": "Plaine du Mô",
      "numbered": true,
      "nameKey": "KAGNIGBARA",
      "nameId": 588,
      "blocks": [[1000, 3799]],
      "numberLength": 4,
      "nameProvisional": false,
      "officialSystem": null,
      "point": {"lat": 8.901347, "lng": 0.644198},
      "box": [0.57804, 8.79432, 0.74211, 9.01481],
      "codes": 1353
    },
    {
      "key": "PMO04",
      "index": 125,
      "kind": "canton",
      "plateName": "Saiboude",
      "officialName": "Saiboude",
      "aliases": [],
      "prefecture": "Plaine du Mô",
      "region": "Centrale",
      "zone": "PMO",
      "place": "Plaine du Mô",
      "numbered": true,
      "nameKey": "SAIBUDE",
      "nameId": 977,
      "blocks": [[1000, 3899]],
      "numberLength": 4,
      "nameProvisional": false,
      "officialSystem": null,
      "point": {"lat": 8.571141, "lng": 0.536497},
      "box": [0.45624, 8.51329, 0.64206, 8.62241],
      "codes": 1403
    },
    {
      "key": "PMO05",
      "index": 126,
      "kind": "canton",
      "plateName": "Tindjassi",
      "officialName": "Tindjassi",
      "aliases": [],
      "prefecture": "Plaine du Mô",
      "region": "Centrale",
      "zone": "PMO",
      "place": "Plaine du Mô",
      "numbered": true,
      "nameKey": "TINJASI",
      "nameId": 1110,
      "blocks": [[1000, 6899]],
      "numberLength": 4,
      "nameProvisional": false,
      "officialSystem": null,
      "point": {"lat": 8.685854, "lng": 0.498598},
      "box": [0.37674, 8.52841, 0.71574, 8.79508],
      "codes": 2901
    }
  ]
}
```


```sh
curl -s "$BASE/v1/zones/XYZ"
```

`404`

```json
{"error": {"code": "not_found", "message": "No zone XYZ. /v1/zones lists them."}}
```


## GET /v1/zones/{key}/codes?after=&limit=

Every code of a zone, as published, in machine-code order. Pass the `next` of one page as `after` to get the next
(`limit` 1–1000, default 100). Walking every page of every zone reproduces the registry.

```sh
curl -s "$BASE/v1/zones/LOM/codes?limit=2"
```

`200`

```json
{
  "zone": "LOM",
  "after": null,
  "limit": 2,
  "count": 2,
  "next": "TG-ABG-1001-9",
  "results": [
    {
      "machine": "TG-ABG-1000-8",
      "home": "Ablogamé 1000",
      "written": "Ablogamé 10 00",
      "zone": "ABG",
      "official_name": "Ablogamé",
      "number": "1000",
      "check": "8",
      "status": "provisional",
      "issued": "bulk",
      "issued_at": "2026-10-20T16:33:10Z",
      "entrance_lat": "6.1339852",
      "entrance_lng": "1.2631986",
      "entrance_kind": "centre",
      "spot_code": "ABG-27C-4R",
      "official_address": "",
      "class": "residential",
      "use": "residential",
      "kind": "building",
      "structures": "1",
      "floor_area_m2": "137.3",
      "rule": "single",
      "estate": ""
    },
    {
      "machine": "TG-ABG-1001-9",
      "home": "Ablogamé 1001",
      "written": "Ablogamé 10 01",
      "zone": "ABG",
      "official_name": "Ablogamé",
      "number": "1001",
      "check": "9",
      "status": "provisional",
      "issued": "bulk",
      "issued_at": "2026-10-20T16:33:10Z",
      "entrance_lat": "6.1338987",
      "entrance_lng": "1.2634564",
      "entrance_kind": "centre",
      "spot_code": "ABG-26F-X6",
      "official_address": "",
      "class": "residential",
      "use": "residential",
      "kind": "building",
      "structures": "1",
      "floor_area_m2": "68.7",
      "rule": "single",
      "estate": ""
    }
  ]
}
```


```sh
curl -s "$BASE/v1/zones/LOM/codes?after=TG-ABG-1002-7&limit=2"
```

`200`

```json
{
  "zone": "LOM",
  "after": "TG-ABG-1002-7",
  "limit": 2,
  "count": 2,
  "next": "TG-ABG-1004-3",
  "results": [
    {
      "machine": "TG-ABG-1003-5",
      "home": "Ablogamé 1003",
      "written": "Ablogamé 10 03",
      "zone": "ABG",
      "official_name": "Ablogamé",
      "number": "1003",
      "check": "5",
      "status": "provisional",
      "issued": "bulk",
      "issued_at": "2026-10-20T16:33:10Z",
      "entrance_lat": "6.1336560",
      "entrance_lng": "1.2619700",
      "entrance_kind": "centre",
      "spot_code": "ABG-268-HR",
      "official_address": "",
      "class": "residential",
      "use": "residential",
      "kind": "compound",
      "structures": "3",
      "floor_area_m2": "83.2",
      "rule": "annex",
      "estate": ""
    },
    {
      "machine": "TG-ABG-1004-3",
      "home": "Ablogamé 1004",
      "written": "Ablogamé 10 04",
      "zone": "ABG",
      "official_name": "Ablogamé",
      "number": "1004",
      "check": "3",
      "status": "provisional",
      "issued": "bulk",
      "issued_at": "2026-10-20T16:33:10Z",
      "entrance_lat": "6.1337168",
      "entrance_lng": "1.2618647",
      "entrance_kind": "centre",
      "spot_code": "ABG-268-KJ",
      "official_address": "",
      "class": "residential",
      "use": "residential",
      "kind": "building",
      "structures": "1",
      "floor_area_m2": "13.9",
      "rule": "single",
      "estate": ""
    }
  ]
}
```


## GET /v1/areas/{key} and GET /v1/areas?name=

An area by key (or index), with its blocks and counts; or every area whose plate name, official name or alias has
the same national name key as `name` (when none does, areas whose name starts with it).

```sh
curl -s "$BASE/v1/areas/FRJ"
```

`200`

```json
{
  "key": "FRJ",
  "index": 32,
  "kind": "lome-quartier",
  "plateName": "Fréau-Jardin",
  "officialName": "Fréau-Jardin",
  "aliases": [],
  "prefecture": "Lomé (ancienne commune)",
  "region": "Maritime",
  "zone": "LOM",
  "place": "Lomé",
  "numbered": true,
  "nameKey": "FREAUJARDIN",
  "nameId": 1352,
  "blocks": [[1000, 1499]],
  "numberLength": 4,
  "nameProvisional": false,
  "officialSystem": "DAGL - adressage du Grand Lomé",
  "point": {"lat": 6.131712, "lng": 1.223315},
  "box": [1.22204, 6.13038, 1.22759, 6.13306],
  "codes": 209,
  "byStatus": {"provisional": 209},
  "numbers": {"lowest": 1000, "highest": 1208, "tailReserveFrom": 1333, "free": 291}
}
```


The official name finds the area whose plate name is shorter:

```sh
curl -s "$BASE/v1/areas?name=Ago%C3%A8-D%C3%A9makpo%C3%A8"
```

`200`

```json
{
  "name": "Agoè-Démakpoè",
  "nameKey": "AGOEDEMAKPOE",
  "match": "name",
  "count": 1,
  "results": [
    {
      "key": "AGN0202",
      "index": 1510,
      "kind": "cell",
      "plateName": "Démakpoè",
      "officialName": "Agoè-Démakpoè",
      "aliases": ["Agoè-Démakpoè"],
      "prefecture": "Agoè-Nyivé",
      "region": "Maritime",
      "zone": "AGN",
      "place": "Agoè-Nyivé",
      "numbered": true,
      "nameKey": "DEMAKPOE",
      "nameId": 1342,
      "blocks": [[10000, 41899]],
      "numberLength": 5,
      "nameProvisional": true,
      "officialSystem": "DAGL - adressage du Grand Lomé",
      "point": {"lat": 6.248365, "lng": 1.200472},
      "box": [1.15138, 6.19819, 1.25012, 6.26983],
      "canton": {"key": "AGN02", "name": "Agoenyive"},
      "codes": 15945
    }
  ]
}
```


Three areas share the name Tokpo; each owns its own block of the national range, so 'Tokpo 11 00' and 'Tokpo 24 17' never collide:

```sh
curl -s "$BASE/v1/areas?name=Tokpo"
```

`200`

```json
{
  "name": "Tokpo",
  "nameKey": "TOKPO",
  "match": "name",
  "count": 3,
  "results": [
    {
      "key": "LAC0603",
      "index": 1321,
      "kind": "cell",
      "plateName": "Tokpo",
      "officialName": "Tokpo",
      "aliases": [],
      "prefecture": "Lacs",
      "region": "Maritime",
      "zone": "LAC",
      "place": "Lacs",
      "numbered": true,
      "nameKey": "TOKPO",
      "nameId": 1125,
      "blocks": [[2000, 4999]],
      "numberLength": 4,
      "nameProvisional": false,
      "officialSystem": null,
      "point": {"lat": 6.296773, "lng": 1.64689},
      "box": [1.62052, 6.29014, 1.66767, 6.3616],
      "canton": {"key": "LAC06", "name": "Ganave/Fiata"},
      "codes": 1483
    },
    {
      "key": "ZIO0216",
      "index": 1431,
      "kind": "cell",
      "plateName": "Tokpo",
      "officialName": "Tokpo",
      "aliases": [],
      "prefecture": "Zio",
      "region": "Maritime",
      "zone": "ZIO",
      "place": "Zio",
      "numbered": true,
      "nameKey": "TOKPO",
      "nameId": 1125,
      "blocks": [[1200, 1999]],
      "numberLength": 4,
      "nameProvisional": false,
      "officialSystem": null,
      "point": {"lat": 6.868421, "lng": 1.033689},
      "box": [0.91671, 6.58907, 1.27038, 6.87107],
      "canton": {"key": "ZIO02", "name": "Agbelouve"},
      "codes": 373
    },
    {
      "key": "DNY0417",
      "index": 1623,
      "kind": "cell",
      "plateName": "Tokpo",
      "officialName": "Tokpo",
      "aliases": [],
      "prefecture": "Danyi",
      "region": "Plateaux",
      "zone": "DNY",
      "place": "Danyi",
      "numbered": true,
      "nameKey": "TOKPO",
      "nameId": 1125,
      "blocks": [[1000, 1199]],
      "numberLength": 4,
      "nameProvisional": false,
      "officialSystem": null,
      "point": {"lat": 7.191681, "lng": 0.717384},
      "box": [0.64548, 7.1505, 0.80082, 7.38985],
      "canton": {"key": "DNY04", "name": "Elavagnon/Atigba"},
      "codes": 30
    }
  ]
}
```


```sh
curl -s "$BASE/v1/areas/NOPE"
```

`404`

```json
{"error": {"code": "not_found", "message": "No code area NOPE. Search one by name with /v1/areas?name=."}}
```


## POST /v1/codes (issuer only)

Issues a code for a compound that has none, or for another door of a compound (`of`). Body: `lat`, `lng`, optional
`outline` (`[[lng, lat], ...]`, the building as drawn on the map) and optional `of` (the machine code of the
compound the door belongs to). A point in a gap between outlines that has a spot code can be issued a code; a point
without one is refused as `422 outside`, and so is a point more than 300 m across the national border, even where a
zone outline or a spot code reaches it: a building in a neighbouring country never gets a Togo code. The rules are the N-Ways issuer's, listed in [server/README.md](../server/README.md#issuing-rules).
The answer is the new card, status `provisional`, `issued: on-demand`.

```sh
curl -s -X POST -H "Authorization: Bearer $KEY" -H 'Content-Type: application/json' \
     -d '{"lat": 6.132, "lng": 1.224}' "$BASE/v1/codes"
```

`201`

```json
{
  "machine": "TG-FRJ-1333-8",
  "remembered": "Fréau-Jardin 13 33",
  "home": "Fréau-Jardin 1333",
  "spoken": "Fréau-Jardin, treize, trente-trois",
  "plateName": "Fréau-Jardin",
  "number": 1333,
  "check": 8,
  "status": "provisional",
  "issued": "on-demand",
  "issuedAt": "2026-10-21T13:44:12Z",
  "officialAddress": null,
  "place": "Lomé",
  "entrance": {"lat": 6.132, "lng": 1.224, "kind": "centre"},
  "spotCode": "FRJ-55-FR",
  "plusCode": "6FR346JF+RJ2",
  "area": {
    "key": "FRJ",
    "index": 32,
    "kind": "lome-quartier",
    "plateName": "Fréau-Jardin",
    "officialName": "Fréau-Jardin",
    "aliases": [],
    "prefecture": "Lomé (ancienne commune)",
    "region": "Maritime",
    "zone": "LOM",
    "place": "Lomé",
    "numbered": true,
    "nameKey": "FREAUJARDIN",
    "nameId": 1352,
    "blocks": [[1000, 1499]],
    "numberLength": 4,
    "nameProvisional": false,
    "officialSystem": "DAGL - adressage du Grand Lomé",
    "point": {"lat": 6.131712, "lng": 1.223315},
    "box": [1.22204, 6.13038, 1.22759, 6.13306]
  },
  "zone": {"key": "LOM", "name": "Lomé (ancienne commune)"},
  "building": {
    "class": null,
    "use": "residential",
    "kind": "building",
    "structures": 0,
    "floorAreaM2": 0.0,
    "rule": null,
    "estate": null
  },
  "registry": {
    "machine": "TG-FRJ-1333-8",
    "home": "Fréau-Jardin 1333",
    "written": "Fréau-Jardin 13 33",
    "zone": "FRJ",
    "official_name": "Fréau-Jardin",
    "number": "1333",
    "check": "8",
    "status": "provisional",
    "issued": "on-demand",
    "issued_at": "2026-10-21T13:44:12Z",
    "entrance_lat": "6.1320000",
    "entrance_lng": "1.2240000",
    "entrance_kind": "centre",
    "spot_code": "FRJ-55-FR",
    "official_address": "",
    "class": "",
    "use": "residential",
    "kind": "building",
    "structures": "0",
    "floor_area_m2": "0.0",
    "rule": "",
    "estate": ""
  },
  "credit": "N-Ways Addressing for Togo, © N-WAYS LIMITED (nways.ng)"
}
```


Another door of a compound, within 80 m of it:

```sh
curl -s -X POST -H "Authorization: Bearer $KEY" -H 'Content-Type: application/json' \
     -d '{"lat": 6.13185, "lng": 1.22355, "of": "TG-FRJ-1058-2"}' "$BASE/v1/codes"
```

`201`

```json
{
  "machine": "TG-FRJ-1334-6",
  "remembered": "Fréau-Jardin 13 34",
  "home": "Fréau-Jardin 1334",
  "spoken": "Fréau-Jardin, treize, trente-quatre",
  "plateName": "Fréau-Jardin",
  "number": 1334,
  "check": 6,
  "status": "provisional",
  "issued": "on-demand",
  "issuedAt": "2026-10-21T13:44:12Z",
  "officialAddress": null,
  "place": "Lomé",
  "entrance": {"lat": 6.13185, "lng": 1.22355, "kind": "door"},
  "spotCode": "FRJ-55-63",
  "plusCode": "6FR346JF+PCV",
  "area": {
    "key": "FRJ",
    "index": 32,
    "kind": "lome-quartier",
    "plateName": "Fréau-Jardin",
    "officialName": "Fréau-Jardin",
    "aliases": [],
    "prefecture": "Lomé (ancienne commune)",
    "region": "Maritime",
    "zone": "LOM",
    "place": "Lomé",
    "numbered": true,
    "nameKey": "FREAUJARDIN",
    "nameId": 1352,
    "blocks": [[1000, 1499]],
    "numberLength": 4,
    "nameProvisional": false,
    "officialSystem": "DAGL - adressage du Grand Lomé",
    "point": {"lat": 6.131712, "lng": 1.223315},
    "box": [1.22204, 6.13038, 1.22759, 6.13306]
  },
  "zone": {"key": "LOM", "name": "Lomé (ancienne commune)"},
  "building": {
    "class": null,
    "use": "residential",
    "kind": "door",
    "structures": 0,
    "floorAreaM2": 0.0,
    "rule": null,
    "estate": null
  },
  "registry": {
    "machine": "TG-FRJ-1334-6",
    "home": "Fréau-Jardin 1334",
    "written": "Fréau-Jardin 13 34",
    "zone": "FRJ",
    "official_name": "Fréau-Jardin",
    "number": "1334",
    "check": "6",
    "status": "provisional",
    "issued": "on-demand",
    "issued_at": "2026-10-21T13:44:12Z",
    "entrance_lat": "6.1318500",
    "entrance_lng": "1.2235500",
    "entrance_kind": "door",
    "spot_code": "FRJ-55-63",
    "official_address": "",
    "class": "",
    "use": "residential",
    "kind": "door",
    "structures": "0",
    "floor_area_m2": "0.0",
    "rule": "",
    "estate": ""
  },
  "credit": "N-Ways Addressing for Togo, © N-WAYS LIMITED (nways.ng)"
}
```


With the building's outline, its floor area enters the profile:

```sh
curl -s -X POST -H "Authorization: Bearer $KEY" -H 'Content-Type: application/json' \
     -d '{"lat": 6.13265, "lng": 1.2243, "outline": [[1.22423, 6.13258], [1.22437, 6.13258], [1.22437, 6.13272], [1.22423, 6.13272], [1.22423, 6.13258]]}' "$BASE/v1/codes"
```

`201`

```json
{
  "machine": "TG-FRJ-1335-1",
  "remembered": "Fréau-Jardin 13 35",
  "home": "Fréau-Jardin 1335",
  "spoken": "Fréau-Jardin, treize, trente-cinq",
  "plateName": "Fréau-Jardin",
  "number": 1335,
  "check": 1,
  "status": "provisional",
  "issued": "on-demand",
  "issuedAt": "2026-10-21T13:44:12Z",
  "officialAddress": null,
  "place": "Lomé",
  "entrance": {"lat": 6.13265, "lng": 1.2243, "kind": "centre"},
  "spotCode": "FRJ-66-G7",
  "plusCode": "6FR346MF+3P7",
  "area": {
    "key": "FRJ",
    "index": 32,
    "kind": "lome-quartier",
    "plateName": "Fréau-Jardin",
    "officialName": "Fréau-Jardin",
    "aliases": [],
    "prefecture": "Lomé (ancienne commune)",
    "region": "Maritime",
    "zone": "LOM",
    "place": "Lomé",
    "numbered": true,
    "nameKey": "FREAUJARDIN",
    "nameId": 1352,
    "blocks": [[1000, 1499]],
    "numberLength": 4,
    "nameProvisional": false,
    "officialSystem": "DAGL - adressage du Grand Lomé",
    "point": {"lat": 6.131712, "lng": 1.223315},
    "box": [1.22204, 6.13038, 1.22759, 6.13306]
  },
  "zone": {"key": "LOM", "name": "Lomé (ancienne commune)"},
  "building": {
    "class": "residential",
    "use": "residential",
    "kind": "building",
    "structures": 1,
    "floorAreaM2": 239.9,
    "rule": null,
    "estate": null
  },
  "registry": {
    "machine": "TG-FRJ-1335-1",
    "home": "Fréau-Jardin 1335",
    "written": "Fréau-Jardin 13 35",
    "zone": "FRJ",
    "official_name": "Fréau-Jardin",
    "number": "1335",
    "check": "1",
    "status": "provisional",
    "issued": "on-demand",
    "issued_at": "2026-10-21T13:44:12Z",
    "entrance_lat": "6.1326500",
    "entrance_lng": "1.2243000",
    "entrance_kind": "centre",
    "spot_code": "FRJ-66-G7",
    "official_address": "",
    "class": "residential",
    "use": "residential",
    "kind": "building",
    "structures": "1",
    "floor_area_m2": "239.9",
    "rule": "",
    "estate": ""
  },
  "credit": "N-Ways Addressing for Togo, © N-WAYS LIMITED (nways.ng)"
}
```


A building that already has its code; the error carries the existing card:

```sh
curl -s -X POST -H "Authorization: Bearer $KEY" -H 'Content-Type: application/json' \
     -d '{"lat": 6.1317765, "lng": 1.2234008}' "$BASE/v1/codes"
```

`409`

```json
{
  "error": {
    "code": "exists",
    "message": "This building already has its code: Fréau-Jardin 10 58.",
    "existing": {
      "machine": "TG-FRJ-1058-2",
      "remembered": "Fréau-Jardin 10 58",
      "home": "Fréau-Jardin 1058",
      "spoken": "Fréau-Jardin, dix, cinquante-huit",
      "plateName": "Fréau-Jardin",
      "number": 1058,
      "check": 2,
      "status": "provisional",
      "issued": "bulk",
      "issuedAt": "2026-10-20T16:33:18Z",
      "officialAddress": "Rue Mission Tové, Lomé",
      "place": "Lomé",
      "entrance": {"lat": 6.1317765, "lng": 1.2234008, "kind": "centre"},
      "spotCode": "FRJ-54-4R",
      "plusCode": "6FR346JF+P96",
      "area": {
        "key": "FRJ",
        "index": 32,
        "kind": "lome-quartier",
        "plateName": "Fréau-Jardin",
        "officialName": "Fréau-Jardin",
        "aliases": [],
        "prefecture": "Lomé (ancienne commune)",
        "region": "Maritime",
        "zone": "LOM",
        "place": "Lomé",
        "numbered": true,
        "nameKey": "FREAUJARDIN",
        "nameId": 1352,
        "blocks": [[1000, 1499]],
        "numberLength": 4,
        "nameProvisional": false,
        "officialSystem": "DAGL - adressage du Grand Lomé",
        "point": {"lat": 6.131712, "lng": 1.223315},
        "box": [1.22204, 6.13038, 1.22759, 6.13306]
      },
      "zone": {"key": "LOM", "name": "Lomé (ancienne commune)"},
      "building": {
        "class": "residential",
        "use": "residential",
        "kind": "building",
        "structures": 1,
        "floorAreaM2": 19.5,
        "rule": "single",
        "estate": null
      },
      "registry": {
        "machine": "TG-FRJ-1058-2",
        "home": "Fréau-Jardin 1058",
        "written": "Fréau-Jardin 10 58",
        "zone": "FRJ",
        "official_name": "Fréau-Jardin",
        "number": "1058",
        "check": "2",
        "status": "provisional",
        "issued": "bulk",
        "issued_at": "2026-10-20T16:33:18Z",
        "entrance_lat": "6.1317765",
        "entrance_lng": "1.2234008",
        "entrance_kind": "centre",
        "spot_code": "FRJ-54-4R",
        "official_address": "Rue Mission Tové, Lomé",
        "class": "residential",
        "use": "residential",
        "kind": "building",
        "structures": "1",
        "floor_area_m2": "19.5",
        "rule": "single",
        "estate": ""
      },
      "credit": "N-Ways Addressing for Togo, © N-WAYS LIMITED (nways.ng)"
    }
  }
}
```


```sh
curl -s -X POST -H "Authorization: Bearer $KEY" -H 'Content-Type: application/json' \
     -d '{"lat": 6.14, "lng": 1.2234, "of": "TG-FRJ-1058-2"}' "$BASE/v1/codes"
```

`422`

```json
{
  "error": {
    "code": "too_far",
    "message": "That door is more than 80 m from Fréau-Jardin 10 58. Stand at the door and try again."
  }
}
```


```sh
curl -s -X POST -H "Authorization: Bearer $KEY" -H 'Content-Type: application/json' \
     -d '{"lat": 5.8, "lng": 1.3}' "$BASE/v1/codes"
```

`422`

```json
{
  "error": {
    "code": "outside",
    "message": "That point is outside Togo, so it cannot have an N-Ways Togo code."
  }
}
```


```sh
curl -s -X POST -H 'Content-Type: application/json' \
     -d '{"lat": 6.132, "lng": 1.224}' "$BASE/v1/codes"
```

`401`

```json
{"error": {"code": "unauthorized", "message": "Send the issuing key as \"Authorization: Bearer <key>\"."}}
```


With a key that is not in `ISSUE_KEYS`:

```sh
curl -s -X POST -H "Authorization: Bearer not-a-key" -H 'Content-Type: application/json' \
     -d '{"lat": 6.132, "lng": 1.224}' "$BASE/v1/codes"
```

`401`

```json
{"error": {"code": "unauthorized", "message": "That key is not one of this deployment's issuing keys."}}
```


On a deployment without issuing keys:

```sh
curl -s -X POST -H "Authorization: Bearer $KEY" -H 'Content-Type: application/json' \
     -d '{"lat": 6.132, "lng": 1.224}' "$READONLY/v1/codes"
```

`403`

```json
{
  "error": {
    "code": "read_only",
    "message": "This deployment is read-only: it does not issue or change codes. Only the issuer the State or N-WAYS LIMITED has designated does."
  }
}
```


## PATCH /v1/codes/{machine} (issuer only)

Confirms a code (`provisional` → `confirmed`), puts it back to `provisional`, retires it (`retired`: the number is
never given again), or moves its entrance by at most 80 m (the entrance becomes a `gate`, and its spot code follows).

```sh
curl -s -X PATCH -H "Authorization: Bearer $KEY" -H 'Content-Type: application/json' \
     -d '{"status": "confirmed"}' "$BASE/v1/codes/TG-FRJ-1333-8"
```

`200`

```json
{
  "machine": "TG-FRJ-1333-8",
  "remembered": "Fréau-Jardin 13 33",
  "home": "Fréau-Jardin 1333",
  "spoken": "Fréau-Jardin, treize, trente-trois",
  "plateName": "Fréau-Jardin",
  "number": 1333,
  "check": 8,
  "status": "confirmed",
  "issued": "on-demand",
  "issuedAt": "2026-10-21T13:44:12Z",
  "officialAddress": null,
  "place": "Lomé",
  "entrance": {"lat": 6.132, "lng": 1.224, "kind": "centre"},
  "spotCode": "FRJ-55-FR",
  "plusCode": "6FR346JF+RJ2",
  "area": {
    "key": "FRJ",
    "index": 32,
    "kind": "lome-quartier",
    "plateName": "Fréau-Jardin",
    "officialName": "Fréau-Jardin",
    "aliases": [],
    "prefecture": "Lomé (ancienne commune)",
    "region": "Maritime",
    "zone": "LOM",
    "place": "Lomé",
    "numbered": true,
    "nameKey": "FREAUJARDIN",
    "nameId": 1352,
    "blocks": [[1000, 1499]],
    "numberLength": 4,
    "nameProvisional": false,
    "officialSystem": "DAGL - adressage du Grand Lomé",
    "point": {"lat": 6.131712, "lng": 1.223315},
    "box": [1.22204, 6.13038, 1.22759, 6.13306]
  },
  "zone": {"key": "LOM", "name": "Lomé (ancienne commune)"},
  "building": {
    "class": null,
    "use": "residential",
    "kind": "building",
    "structures": 0,
    "floorAreaM2": 0.0,
    "rule": null,
    "estate": null
  },
  "registry": {
    "machine": "TG-FRJ-1333-8",
    "home": "Fréau-Jardin 1333",
    "written": "Fréau-Jardin 13 33",
    "zone": "FRJ",
    "official_name": "Fréau-Jardin",
    "number": "1333",
    "check": "8",
    "status": "confirmed",
    "issued": "on-demand",
    "issued_at": "2026-10-21T13:44:12Z",
    "entrance_lat": "6.1320000",
    "entrance_lng": "1.2240000",
    "entrance_kind": "centre",
    "spot_code": "FRJ-55-FR",
    "official_address": "",
    "class": "",
    "use": "residential",
    "kind": "building",
    "structures": "0",
    "floor_area_m2": "0.0",
    "rule": "",
    "estate": ""
  },
  "credit": "N-Ways Addressing for Togo, © N-WAYS LIMITED (nways.ng)"
}
```


```sh
curl -s -X PATCH -H "Authorization: Bearer $KEY" -H 'Content-Type: application/json' \
     -d '{"entrance": {"lat": 6.13195, "lng": 1.22405}}' "$BASE/v1/codes/TG-FRJ-1333-8"
```

`200`

```json
{
  "machine": "TG-FRJ-1333-8",
  "remembered": "Fréau-Jardin 13 33",
  "home": "Fréau-Jardin 1333",
  "spoken": "Fréau-Jardin, treize, trente-trois",
  "plateName": "Fréau-Jardin",
  "number": 1333,
  "check": 8,
  "status": "confirmed",
  "issued": "on-demand",
  "issuedAt": "2026-10-21T13:44:12Z",
  "officialAddress": null,
  "place": "Lomé",
  "entrance": {"lat": 6.13195, "lng": 1.22405, "kind": "gate"},
  "spotCode": "FRJ-55-9V",
  "plusCode": "6FR346JF+QJM",
  "area": {
    "key": "FRJ",
    "index": 32,
    "kind": "lome-quartier",
    "plateName": "Fréau-Jardin",
    "officialName": "Fréau-Jardin",
    "aliases": [],
    "prefecture": "Lomé (ancienne commune)",
    "region": "Maritime",
    "zone": "LOM",
    "place": "Lomé",
    "numbered": true,
    "nameKey": "FREAUJARDIN",
    "nameId": 1352,
    "blocks": [[1000, 1499]],
    "numberLength": 4,
    "nameProvisional": false,
    "officialSystem": "DAGL - adressage du Grand Lomé",
    "point": {"lat": 6.131712, "lng": 1.223315},
    "box": [1.22204, 6.13038, 1.22759, 6.13306]
  },
  "zone": {"key": "LOM", "name": "Lomé (ancienne commune)"},
  "building": {
    "class": null,
    "use": "residential",
    "kind": "building",
    "structures": 0,
    "floorAreaM2": 0.0,
    "rule": null,
    "estate": null
  },
  "registry": {
    "machine": "TG-FRJ-1333-8",
    "home": "Fréau-Jardin 1333",
    "written": "Fréau-Jardin 13 33",
    "zone": "FRJ",
    "official_name": "Fréau-Jardin",
    "number": "1333",
    "check": "8",
    "status": "confirmed",
    "issued": "on-demand",
    "issued_at": "2026-10-21T13:44:12Z",
    "entrance_lat": "6.1319500",
    "entrance_lng": "1.2240500",
    "entrance_kind": "gate",
    "spot_code": "FRJ-55-9V",
    "official_address": "",
    "class": "",
    "use": "residential",
    "kind": "building",
    "structures": "0",
    "floor_area_m2": "0.0",
    "rule": "",
    "estate": ""
  },
  "credit": "N-Ways Addressing for Togo, © N-WAYS LIMITED (nways.ng)"
}
```


```sh
curl -s -X PATCH -H "Authorization: Bearer $KEY" -H 'Content-Type: application/json' \
     -d '{"entrance": {"lat": 6.134, "lng": 1.224}}' "$BASE/v1/codes/TG-FRJ-1333-8"
```

`422`

```json
{
  "error": {
    "code": "too_far",
    "message": "The new entrance is 228 m from the code; an entrance can move at most 80 m. Issue a new code for another building."
  }
}
```


```sh
curl -s -X PATCH -H "Authorization: Bearer $KEY" -H 'Content-Type: application/json' \
     -d '{"status": "retired"}' "$BASE/v1/codes/TG-FRJ-1333-8"
```

`200`

```json
{
  "machine": "TG-FRJ-1333-8",
  "remembered": "Fréau-Jardin 13 33",
  "home": "Fréau-Jardin 1333",
  "spoken": "Fréau-Jardin, treize, trente-trois",
  "plateName": "Fréau-Jardin",
  "number": 1333,
  "check": 8,
  "status": "retired",
  "issued": "on-demand",
  "issuedAt": "2026-10-21T13:44:12Z",
  "officialAddress": null,
  "place": "Lomé",
  "entrance": {"lat": 6.13195, "lng": 1.22405, "kind": "gate"},
  "spotCode": "FRJ-55-9V",
  "plusCode": "6FR346JF+QJM",
  "area": {
    "key": "FRJ",
    "index": 32,
    "kind": "lome-quartier",
    "plateName": "Fréau-Jardin",
    "officialName": "Fréau-Jardin",
    "aliases": [],
    "prefecture": "Lomé (ancienne commune)",
    "region": "Maritime",
    "zone": "LOM",
    "place": "Lomé",
    "numbered": true,
    "nameKey": "FREAUJARDIN",
    "nameId": 1352,
    "blocks": [[1000, 1499]],
    "numberLength": 4,
    "nameProvisional": false,
    "officialSystem": "DAGL - adressage du Grand Lomé",
    "point": {"lat": 6.131712, "lng": 1.223315},
    "box": [1.22204, 6.13038, 1.22759, 6.13306]
  },
  "zone": {"key": "LOM", "name": "Lomé (ancienne commune)"},
  "building": {
    "class": null,
    "use": "residential",
    "kind": "building",
    "structures": 0,
    "floorAreaM2": 0.0,
    "rule": null,
    "estate": null
  },
  "registry": {
    "machine": "TG-FRJ-1333-8",
    "home": "Fréau-Jardin 1333",
    "written": "Fréau-Jardin 13 33",
    "zone": "FRJ",
    "official_name": "Fréau-Jardin",
    "number": "1333",
    "check": "8",
    "status": "retired",
    "issued": "on-demand",
    "issued_at": "2026-10-21T13:44:12Z",
    "entrance_lat": "6.1319500",
    "entrance_lng": "1.2240500",
    "entrance_kind": "gate",
    "spot_code": "FRJ-55-9V",
    "official_address": "",
    "class": "",
    "use": "residential",
    "kind": "building",
    "structures": "0",
    "floor_area_m2": "0.0",
    "rule": "",
    "estate": ""
  },
  "credit": "N-Ways Addressing for Togo, © N-WAYS LIMITED (nways.ng)"
}
```


```sh
curl -s -X PATCH -H "Authorization: Bearer $KEY" -H 'Content-Type: application/json' \
     -d '{"status": "confirmed"}' "$BASE/v1/codes/TG-FRJ-1333-8"
```

`409`

```json
{
  "error": {
    "code": "retired",
    "message": "Fréau-Jardin 13 33 is retired. A retired code is never used again; issue a new one."
  }
}
```


## Other errors

```sh
curl -s -X DELETE -H "Authorization: Bearer $KEY" "$BASE/v1/codes/TG-FRJ-1058-2"
```

`405`

```json
{
  "error": {
    "code": "method_not_allowed",
    "message": "DELETE is not allowed on /v1/codes/TG-FRJ-1058-2; use GET, PATCH."
  }
}
```


```sh
curl -s "$BASE/v1/addresses"
```

`404`

```json
{"error": {"code": "not_found", "message": "No endpoint /v1/addresses. See /v1/info and docs/api.md."}}
```

