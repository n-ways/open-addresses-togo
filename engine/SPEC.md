# Togo engine specification

This is the specification of the N-Ways address engine for Togo. The reference implementation is
`engine/reference/tg_engine.py` with `engine/reference/plate_names.py` (Python standard library); every other engine
(the issuer, the app, the registry server in `server/`, partner libraries) must give identical results on
`engine/reference/test_vectors.json` and `engine/reference/vectors.json`.

**Status.** Issued on 20 October 2026: 2,768,053 codes, one for every compound in Togo, frozen in
`engine/data/register.json` and published in `registry/`.

**Official addresses first.** Where the State already gives an address, the engine uses that data and shows it first,
as officially written. Grand Lomé (13 communes: the former commune of Lomé and the préfectures of Golfe and Agoè-Nyivé)
is addressed by the DAGL; there the official street (the former commune's 1997 street names and codes) and, once
released, the DAGL entrance address come first (§12). Every compound, Grand Lomé included, also has its N-Ways code,
which is short to say and tells apart the compounds of one door or street; the areas of Grand Lomé carry
`officialSystem`.

Terms: **area** = code area; **compound** = addressable plot; **structure** = one footprint; **entrance** = gate,
door, boutique door.

## 1. Data files

| File | Content | Licence of inputs |
|---|---|---|
| `model/areas/areas.json` | the frozen code-area table: index, key, kind, name (the plate name, §3.2), official name, spoken name, aliases, plate rule and council flag, unit id, box, point, number length, estimates; split cantons list their cells | derived from the files below |
| `model/areas/names.json` | national name table (§3.1): name id, name key, plate spellings and official names, blocks per area, free space, counts; the areas waiting for their commune's plate-name choice (`councilChoices`) | derived from areas.json |
| `model/units/keys.geojson` | 69 Lomé quartier polygons (OSM admin_level 10, `ref` = quartier code) and 40 HDX admin2 units | ODbL; CC BY-IGO |
| `model/units/cantons.geojson` | 373 canton polygons (HDX COD-AB Togo admin3, valid_on 2021-01-07), lightly thinned | CC BY-IGO |
| `model/areas/osm-places.csv` | named places used to split cantons | ODbL |
| `engine/data/register.json`, `engine/data/units.json` | what a decoder ships: every numbered area with its plate and official names, name id, blocks, box and point; the quartier and canton polygons | derived |
| `engine/data/border.json` | Togo's national border: OpenStreetMap's admin_level 2 boundary (relation 192782), simplified by Douglas-Peucker at 50 m (`tools/make-border.py`), with its measured deviation from the original line (`deviationM`); read by `engine/reference/border.py` (§1.1) | ODbL |
| `registry/<unit>.csv.gz`, `registry/areas.csv.gz`, `registry/MANIFEST.json` | every issued code, one file per préfecture (`LOM` the former commune of Lomé), the frozen area table, counts and SHA-256 | ODbL (contains OSM) |
| `server/` | the registry server: the registry as a JSON API, and issuing by §7 and §10 (§14) | Apache 2.0 (code) |

The phone keeps `areas.json` and the unit polygons (≈1 MB) for offline lookup, and the registry files of the areas
it has used.

### 1.1 The border decides

A code is only ever issued for a compound whose entrance lies inside Togo's national border, OpenStreetMap's
admin_level 2 boundary, or within `BORDER_M` = 300 m of it. The canton outlines (HDX COD-AB) and the quartier
outlines spill over the border in places (the canton of Lomé Commune reaches some 700 m into the neighbouring
country), and the spot-code rule (§5) reaches 1,100 m beyond any outline; neither decides. The build drops every
footprint and compound across the border (§6), and the issuer refuses a new code or a moved entrance there (§10).

- Distance outside the border: 0 inside it (even-odd over every ring); else the shortest distance to an edge, in
  local metres (`m_lat`, `m_lon` of §2 at the point).
- The build measures against the unsimplified boundary of the OpenStreetMap extract (`<work>/country.geojson`).
- A server measures against `engine/data/border.json`. A simplified line lies up to its deviation `d` from the
  original (50.3 m in the published file), so a point is allowed only when it lies within 300 m − `d` of the
  simplified outline (249.7 m): every point allowed is within 300 m of the real border; a point between 249.7 m
  and 300 m outside may be refused, never the reverse.
- Measured on the published registry: of the 2,768,053 issued codes, none has its entrance outside the border
  (0 more than 300 m outside, 0 outside at all).

## 2. Area lookup

1. If a Lomé quartier polygon contains the point, that quartier is the area.
2. Else the canton polygon that contains it. Canton `TG030501` (Lomé Commune) is a container: a point inside it but in
   no quartier polygon (gaps between OSM polygons) goes to the nearest quartier by its stored point.
3. If the canton is split (`cells` present), the area is the cell whose stored place point is nearest (local metres:
   `m_lat = 111132.92 − 559.82 cos 2φ + 1.175 cos 4φ`, `m_lon = 111412.84 cos φ − 93.5 cos 3φ`).

Point-in-polygon is even-odd on the outer ring, minus holes; boxes are tested first. The registry, not the lookup,
is authoritative for an issued compound: a compound keeps its area even if a later boundary correction would move it.

## 3. Area table rules (`tools/build_areas.py`)

- Index: quartiers 1–69 (sorted by code), cantons 101–473 (sorted by p-code), cells from 1001. Appended only.
- Quartier key = OSM `ref`. Canton key = préfecture key (3 letters, table in design.json) + last two digits of the
  p-code. Cell key = canton key + 2-digit rank of the cell's name (alphabetical, accents removed).
- Compounds estimate = structures × 0.79 (structures per area from `keys.csv` for quartiers, from a 10% national
  sample × 10 for cantons and cells).
- Grand Lomé: the 69 quartiers and the cantons of Golfe and Agoè-Nyivé (and their cells) carry `officialSystem`
  (system, holder, what N-Ways does) and are numbered like every other area; the canton "Lomé Commune" (`TG030501`) is a
  container of the quartiers and is not numbered itself.
- Counts at first issue: every footprint, with the quartier or canton holding it (tools/extract-buildings.py); the blocks
  are then sized on the compounds actually grouped (tools/build-register.py).
- Number length (other areas): 4 if compounds × 2 ≤ 9,000, else 5. A canton above the limit is split
  into named-place cells (all distinct names of OSM `place` = city, town, village, hamlet, suburb, quarter,
  neighbourhood, locality inside it); with fewer than two names it keeps 5 digits.
- Freeze: before first issue in an area the table may be rebuilt with better names; after it, the area's polygon,
  key, index and length never change.
- Then `tools/name_ranges.py` cleans place words, derives plate names (§3.2), assigns name ids and blocks (§3.1) and writes
  `officialName`, `name`, `plateRule`, `nameId`, `nameKey`, `blocks` and `numberLength` into areas.json and the table into
  names.json.

### 3.1 National name ranges (a remembered code is unique in Togo on its own)

Decoding never uses context: no préfecture, no position, no "which one?" question. Rules:

1. **Place word.** The name key is taken from the plate name (§3.2). The official name comes from
   `clean_place_name(osm name, canton name)`: drop "Résidence du chef du village de", "Écovillage",
   "Village (de|d')", "Quartier" at the start and ", Togo" / " village" at the end; drop a parenthesis (an "(aka: X)"
   becomes alias X); drop trailing part numbers (`1`, `2`, `I`–`IV`); title-case all-capital names (short acronyms in mixed
   names stay: "Agbonou CEET"); a junk name (`unknow`, `unknown`, `inconnu`) becomes the canton's name. The OSM name is kept
   as `osmName`, the cleaned name as `officialName`. A numbered area's name contains no digit.
2. **Name key** `name_key(s)`: map ɛ ɔ ŋ ƒ ʋ ɖ ɣ to e o n f v d g; NFKD and drop combining marks; upper case; non-letters and
   non-digits to spaces; drop a leading `LE`/`LA`/`LES`/`L`; drop trailing part numbers; remove spaces; replace `PH`→`F`,
   `QU`→`K`, `DJ`→`J`, `OU`→`U`, `W`→`U` (in this order); `C` before `A`, `O`, `U` or at the end → `K`; collapse doubled
   letters. Before the folding, the abbreviations a plate name may use are expanded: `ST` → `SAINT`, `STE` → `SAINTE`,
   `N.-D.` → `NOTRE DAME`. Typed input goes through steps 1 and 2 too.
3. **Name space.** Each name key owns 1000–9999 (4-digit part) and 10000–99999 (5-digit part).
4. **Blocks.** Block size of an area = max(200, ceil(compounds × 2 / 100) × 100), from the real count at first issue (the
   estimate before). Planning order within a name: block size ascending, then area index. A block is placed at the next
   free number of the 4-digit part if it fits there, else of the 5-digit part if, after it, at least `NAME_SPARE` =
   5,000 numbers of the name stay free; else the area needs a qualifier (rule 6). `numberLength` = digits of its block.
5. **Name id.** A frozen 4-digit ordinal per name key (alphabetical by key at the first build, appended afterwards).
6. **Qualifier.** A name whose blocks do not fit takes, for one or more of its areas, one established qualifier people
   already say, decided once and listed in `QUALIFIERS` (`tools/name_ranges.py`) and names.json; the qualified name is a
   new name key. None is needed today.
7. **Freeze.** Blocks are never moved, shrunk or renumbered. A new area with an existing name gets a new block from the
   name's free space (rule 4 at that time); a full area gets an extra block (appended to its `blocks`). Name ids, blocks
   and numbers are never reused.
8. **Aliases.** An alias whose key is another name's key is refused (it would make "Alias NNNN" ambiguous). The official
   name is an alias of its area when its key differs from the plate name's and is neither another plate name's key nor
   the official name of an area with another plate name; otherwise it is dropped as an alias and listed in names.json
   (`officialAliasesDropped`; none today).
9. **Invariant (checked when the table loads).** Within one name key, blocks are disjoint; every number belongs to at
   most one area.

Counts at first issue (20 October 2026, blocks on the real compounds): 1,379 numbered areas (69 quartiers, 215 cantons,
1,095 cells), 1,323 name keys; 50 keys repeat, over 106 areas holding 240,136 compounds; the largest shared range is
Lom-Nava (6 areas: 1000–1199, 1200–2899, 2900–5199, 5200–8399, 10000–17599, 17600–26699); 1,251 areas have 4 digits
(1,549,299 compounds), 128 have 5 (1,218,754), none has 3; the largest block is Sagbado's, 10000–92599 (41,259
compounds). No name needs a qualifier.

### 3.2 Plate names (the name in the remembered code)

A name too long for a plate or one breath is not what people say: they keep its distinctive part ("Koissidamé" for
"Gboto Koissidamé"), so the code is built on that part.

Each numbered area has two names: `officialName`, the full name (printed small on cards and plates for context, never
required), and `name`, the **plate name** used in the remembered code. Rules (`engine/reference/plate_names.py`; Togo's
word lists and avoid set in `tools/name_ranges.py`, `plate_for`):

1. **Limit.** At most 12 characters (NFC; letters, spaces, hyphens and apostrophes each count one, an accented letter is
   one) and at most 2 words (a word is a part between spaces or hyphens; linking words de, du, des, d', la, le, les, l',
   et, sur, en, au, aux, à do not count: "Lom-Nava" is 2 words); no digit. `plate_fits(name)`.
2. **Derivation**, from the official name, in order: (a) a documented short form (`KNOWN`, with its source; none for Togo
   today); (b) clean: `X - Y` written `X-Y`; drop text in brackets, text after a slash, a second spelling joined by
   ou/dit/alias, and the generic words Village de, Quartier, Lotissement, Cité, Zone, Secteur, Village, Hameau,
   Campement (and "Campment"), Ferme, Résidence, Carrefour, Centre de formation rurale de, with a linking word left at
   either end; (c) if the cleaned name fits, it is the plate name; (d) else the best run of whole words that fits,
   ranked by how rare its words are among Togo's area names, with a preference for the end of the name; it is taken
   only when clearly ahead (score ≥ 1.5 × the next), at least 4 letters, and not equal to a town in the avoid set.
   A word is never cut.
3. **Qualifiers.** Weak words are never a plate name alone and never dropped automatically after the main word: the
   French list (haut, bas, nord, sud, nouveau, grand, petit…) plus the Ewe and Mina settlement words kopé (copé,
   cope), kondji (condji), kodzi (village) and kpota, kpotame (the outskirts): "Aklassou kopé" is a village of its own,
   not Aklassou.
4. **Avoid set.** A plate name may not equal (by name key) the chef-lieu of a préfecture (39; the region capitals are among
   them), the short forms Apéyémé, Adéta, Guérin, Gadzépé, a quartier of Lomé (69), or a town across the borders that
   Togolese travellers and traders name every day (Hillacondji, Aflao, Ho, Keta, Kpando, Kumasi, Tamale, Bolgatanga,
   Tema, Accra, Cotonou, Porto-Novo, Ouidah, Abomey, Bohicon, Parakou, Djougou, Natitingou, Ouagadougou, and the ends of
   the Abidjan–Lagos corridor), except the area's own town: its préfecture's seat, its canton, its own name.
5. **Commune's choice.** Otherwise the area is flagged `needsCouncilChoice` with up to 3 `plateCandidates` and a
   `plateReason`; the first candidate is its provisional plate name. A hyphen compound ("Agoè-Démakpoè", "Landa-Pozenda")
   offers its parts as candidates, the rarer part first ("Démakpoè": the shared "Agoè" names none of the Agoè quartiers).
   An area with no candidate (one word over 12 letters: "Koussocointougou") keeps its name provisionally. Codes are
   issued under the provisional name (nothing waits for anyone); the commune may choose once, and the old name stays an
   alias. Only an unflagged plate over the limit is an error (`PlateTooLong`).
6. **Rule recorded.** `plateRule` = `as-is`, `cleaned`, `abbreviated` (St, Ste, N.-D.), `known`, `distinctive` or `council`.
7. **Uniqueness.** Same-key plate names share one national range (§3.1); "Tami 10 17" (official "Centre de formation
   rurale de Tami") and "Tami 15 17" (the village) are different blocks of the name Tami.
8. **Check when the table loads.** A numbered area whose plate name does not fit and that is not flagged is an error.

Counts at first issue: 1,253 plate names are the official name, 17 cleaned, 33 shortened to their distinctive words,
76 flagged for the commune (38 hyphen compounds, 25 single long words with no candidate, 9 that would drop a qualifier,
2 equal to a known town, 2 without a clear choice); 25 stay over the limit provisionally; 145,645 codes were issued under
a provisional plate name; 95 official names are aliases.

## 4. Compound codes

### 4.1 Forms

- Remembered and written: plate name (§3.2), a space, the number grouped in pairs from the right (`Fréau-Jardin 10 58`,
  `Tsévié 1 91 72`). No check digit is ever shown to people or asked of them: a plate, a card or a form carries the
  name and the number only, and the check lives in the machine form. A decoder accepts one after a dash from systems
  that send it (`Kamina 54 00-8`).
- Machine: `TG-<key>-<number>-<check>`; optional `.n` structure, `/n` entrance (`/1` = gate).
- Spoken French: place name, then each pair in words (`quarante-huit, dix-sept`; 71 = "soixante et onze",
  91 = "quatre-vingt-onze").

### 4.2 Check digit

Damm over the string `%04d(name id) + %04d(area index) + number`. Table: the standard order-10 quasigroup (in
`tg_engine._DAMM`; "572" → 4). A code is valid iff Damm over name id + index + number + check = 0. It binds name + number
+ area: it detects every single-digit error and every adjacent transposition in the digits, and a number copied onto
another area, same-named or not.

### 4.3 Parsing

Accepted, case- and accent-insensitive: the machine form (the number must lie in one of the area's blocks); `<place
name> <4–5 digits>[-<check>]` with spaces or dots inside the number; the place name may be the plate name or the
official name. A remembered code is decoded nationally: name key →
the numbered areas of that key → the one whose block holds the number. A number in no block is refused ("no N-Ways
address"), never guessed; with a check digit the result is `checked: true`, a wrong one is refused. There is no `ambiguous` result:
same-named areas are told apart by the number alone (§3.1). A Lomé
street code (number of 1–3 digits, then a quartier code: `165 AMT`, `46BE`, `13.QAD`, optionally preceded by
rue/avenue/boulevard/impasse) is returned as `lome-street-code`, never as an N-Ways code.

## 5. Spot codes

- Cell: 1/32768° in latitude and longitude (3.37 × 3.35–3.38 m in Togo).
- Frame: the quartier or canton box (cells use their canton's frame); origin = box SW corner floored to a multiple of
  1/1024°; characters per axis `n = ceil(log20(extent/cell + 1))`.
- Indices: `ix = floor((lon − ox)/cell)`, `iy = floor((lat − oy)/cell)`, written in base 20 with the alphabet
  `23456789CFGHJKMPRVWX`, most significant first; the two axes interleave north first; when one axis has more
  characters its extra leading characters come first.
- Text: `<frame key>-<first half>-<second half>`; decode returns the cell centre.
- Lomé quartiers give 4 characters (`AMT-97-M8`), cantons 6 or 7 (`KOZ06-36X-M4G`). A point between Lomé's quartier
  polygons belongs to its nearest quartier but lies outside that quartier's box: its spot code uses the containing
  canton's frame, so every code decodes back to its own cell.
- **A point in no outline.** The quartier and canton outlines leave thin gaps between them, and a compound may stand
  just over a border line. Such a point takes its frame from the quartiers and cantons (the container `TG030501`
  included) whose outline lies within `SPOT_OUTLINE_M` = 1,100 m: among those whose frame holds it
  (`0 ≤ ix < 20^nx`, `0 ≤ iy < 20^ny`, with `floor`), the one with the nearest outline; if no frame holds it, among
  those whose frame lies at most `SPOT_NEAR_CELLS` = 200 cells (≈ 675 m) away on each axis, the one with the nearest
  outline, and the point takes that frame's nearest edge cell (`ix`, `iy` clamped into the frame). Ties go to the
  lower key. The distance to an outline is the shortest distance to an edge of any of its rings, in degrees of
  latitude with longitude differences multiplied by `cos φ` (`tg_engine.edge_d2`); 1,100 m is 1,100 / 110,574 of a
  degree. Any other point is outside Togo. A spot code is a position, not a licence to issue: a point with one may
  still lie across the national border, where no code is issued (§1.1). Frames never move: the rule only chooses among existing frames. Decoding
  uses the frame the code names; for a point on an edge cell the decoded centre is that cell's, and the registry
  keeps the exact entrance.
- Measured on the issued registry: 4,415 compounds have their entrance in no outline; the farthest lies 1,081 m from
  the nearest outline. Each takes the frame of its nearest outline: 4,402 lie inside that frame, and 13 (in Danyi
  and Golfe) lie at most 177 cells beyond it and take its edge cell. Every issued compound has a spot code.

## 6. Building the registry (first issue in an area)

1. **Structures**: all footprints whose centroid is in the area: OpenStreetMap, then Google Open Buildings /
   Microsoft footprints (via Overture) where OSM has none, then people's outlines. Drop footprints < 4 m². Drop
   every footprint whose centroid lies outside the national border (§1.1; `tools/extract-buildings.py` keeps only
   those inside it, and `tools/assign-areas.py` drops any more than 300 m outside), and every compound whose point
   does (`tools/issue_registry.py group`); `tools/issue_registry.py number` refuses to write a lote across it.
2. **Profiles** (§8) computed per structure.
3. **Compounds** — group before numbering, in this order:
   1. enclosure: structures whose centroid is inside one closed OSM `barrier=wall|fence|hedge` ring (or an imported
      parcel, or a people-confirmed outline) of ≤ 6,000 m² form one compound (confidence 0.85; 0.9 for parcels and
      people). Larger walled sites (estates, schools, camps) are not compounds: grouping continues inside them and the
      site's gate becomes an estate entrance.
   2. annex: a structure < 30 m² joins the nearest structure ≥ 30 m² whose footprint is ≤ 6 m away (8 m in the rural
      north: Kara and Savanes regions) (0.6).
   3. hut cluster (rural north only): huts < 35 m² that belong to no house (not an annex, not in an enclosure) and are
      ≤ 3 m apart chain into one compound of at most 20 (0.5): a cluster never joins two houses.
   Production: `tg_engine.group_footprints` (the same rules on a 40 m grid, footprints in stable-id order).
   4. single: each remaining structure is one compound (0.4).
   Gap = smallest distance between footprints in local metres (0 when they touch).
4. **Gate**: an OSM `barrier=gate`/N-Ways gate within 3 m of the compound boundary; else the boundary point nearest the
   access road (proposed, confidence 0.3) until confirmed.
5. **Numbering** — over compounds: representative point = gate if known, else the centroid of the largest structure;
   Hilbert index (order 16) of the point in the area box; sort by (index, id); number_i = low + i × s with
   `s = max(1, floor(capacity / (N × 1.5)))`, low = the first number of the area's block, capacity = the block size
   (§3.1). Numbers ≥ `low + floor(2 × capacity / 3)` are the tail reserve. Refuse if N × 2 > capacity (allocate the
   block from the real count first).
6. Write the codes; structures inside a compound get `.1` (largest) … in descending area. The issuer writes them
   after checking every number against the reference's, and exports `registry/`.

## 7. New compounds and changes

- **Provisional number** (Add my home, new footprint, people splitting a compound): Hilbert index of the gate; the
  issued compounds before and after it on the curve (numbers below the tail reserve) bound a free interval; choose the
  free number closest to its midpoint; if none, the lowest free tail-reserve number; if none, the first free number of
  the area's extra blocks; if none, the area is full and gets an extra block from its name's free space (§3.1 rule 7;
  existing codes stay).
- Status `provisional` until confirmed (§9); provisional codes are reserved, never re-issued even if abandoned (they
  become `retired`).
- Regrouping (people say two compounds are one home, or one compound is two) never changes an issued code: merged →
  the older code is kept and the other becomes an alias; split → the part with the gate keeps the code.
- Demolition → `retired`. Renamed quartier/canton → alias added. Corrected footprint → same code.

## 8. Building profile

Per structure (JSON):

```json
{"id": "TG-FRJ-1058-2.1", "class": "residential", "subclass": "cour commune", "classConfidence": 0.55,
 "classSource": "default", "footprintM2": 118.4, "perimeterM": 46.1, "heightM": null, "heightSource": null,
 "floors": null, "floorsSource": null, "floorAreaM2": null, "footprintSource": "google",
 "entrances": [{"n": 1, "kind": "gate", "lat": 6.13178, "lon": 1.22340, "confirmed": "2027-01-12", "official": null}],
 "name": null, "status": "existing", "crossRefs": {"titreFoncier": null}, "lastConfirmed": "2027-01-12"}
```

- Class inference evidence and confidences: OSM `building` tag 0.85; OSM POI tag on the footprint 0.75; N-Ways place
  point inside 0.65; OSM landuse 0.5; size rules 0.3–0.4 (< 6 m² annex/kiosk; > 2,500 m² large shed); default
  residential 0.45 (0.55 inside residential landuse); +0.05 per agreeing extra source; a residential + commercial
  pair becomes `mixed` (0.6). People and partners override once agreed.
- Floors: OSM `building:levels`; else OSM `height` / 3 (rounded, at least 1); else unknown. The Google/Microsoft `h` is
  a rendering filler (36 values spread evenly over 3.5–7 m) and never gives floors.
- Areas and perimeters: geodesic on WGS84.
- Compound profile: class (`residential-one-household` when one dwelling ≥ 30 m², `residential-multi-household` when
  two or more, or a row building with aspect ≥ 3, `residential-multi-storey` when a dwelling has ≥ 3 floors, `mixed`,
  `commercial`, `institutional`, `industrial`, `other`), plot area (enclosure/outline), structure count, floor area,
  gates.
- Never stored: occupants, households' names, phones, ID numbers. Names only for businesses and public buildings.

## 9. Confirmation (consensus, never a review queue)

A provisional compound, a grouping or a gate becomes confirmed when at least two independent signals agree and none
disagrees: arrivals/deliveries ending at the gate (N-Ways trips), the household confirming twice on different days, a
courier delivery, a partner record, new imagery or footprints showing the structures. A neighbour dispute freezes the
item (still provisional) until signals settle it. Unvisited doors and closed businesses are re-asked.

## 10. Add my home (the issuer's checks)

Input: the entrance position (averaged fixes), optionally the building's outline as drawn on the map (`[lng, lat]`
points), or `of`: the machine code of the compound this is another door of. The issuer, in this order:

1. refuses a point outside Togo: one in no quartier or canton outline that has no spot code either (§5); a compound
   in a gap between outlines, or just over a border line, is in Togo and can be issued a code (its area by rule 4);
   and, whatever the outlines and spot codes say, refuses a point more than 300 m outside the national border
   (§1.1: `422 outside`); moving an entrance passes the same two tests;
2. for a new compound: refuses when a structure of a live code holds the point, or when a live code's entrance or
   structure lies within 3 m of it (the building already has its code, which is returned); with an outline, refuses an
   area under 6 m² or over 20,000 m², and an outline that overlaps a live code's structure by more than half of the
   smaller of the two;
3. for another door: refuses when the code does not exist or its entrance is more than 80 m away; the door takes that
   code's area;
4. otherwise takes the area of the nearest live code within 250 m (a new house joins its neighbours), else the area of
   the point (§2), else the numbered area whose place point is nearest;
5. numbers by §7, writes the code `provisional` with its entrance (`centre`, or `door` for another door) and, with an
   outline, one residential structure;
6. limits each phone (or issuing key) to 5 codes in 24 hours.

In Grand Lomé the official address attaches when it exists. Offline, the spot code is shown at once and the number is
assigned on the next connection. The registry server (`server/`) applies the same steps on the published registry,
which carries one point per compound: there the structure tests of step 2 use the code points and the outlines it
issued itself.

## 11. Offline behaviour

On the phone: area lookup, spot encode/decode, parsing, check digits and formatting work with `areas.json` and the
unit polygons only. Compound lookup needs the area's registry file (tens of kB per area), cached after first use.

## 12. Official addresses (Grand Lomé)

- Sources: legacy Lomé street codes and names (OpenStreetMap `ref`/`name`, ODbL; the commune/DAGL street register when
  obtained); DAGL entrance addresses (street code/name, entrance number, point) when released under a data-sharing
  agreement.
- Text: built from the official fields only, in the official spelling: `<number>, <street name or code>, <quartier>,
  <commune>` (`official_text`); never re-spelt, re-cased or translated.
- Attachment (`attach_official`): each record to the nearest compound gate within 15 m; one record per entrance (nearest
  wins); leftover records are kept at their own point and reported, never forced onto a compound.
- Sync: each official release replaces the previous one; N-Ways keeps history; when people's confirmations disagree with
  an official record (gate elsewhere, record on a demolished house), N-Ways reports it to the holder and keeps showing
  the official record.
- Display: the official address first; then the N-Ways code, the gate pin, the profile and the spot code.
- Before DAGL data: in the former commune of Lomé the official street within 30 m of the compound
  (`coverage: official-street`, "Rue 89 AFG, Lomé"); a DAGL entrance address, once released, replaces it. The N-Ways
  code never changes.
- Other towns: if a government address system reaches a town outside Grand Lomé, its areas become official the same
  way; N-Ways codes already issued there become aliases of the official addresses (never deleted, never reissued).

## 13. Conformance

`python3 engine/reference/test_tg.py` must pass: Damm example and error detection, spot round-trips and vectors from
real OSM footprints in Amoutivé, Bè, Tokoin-Lycée, Agoè-Nyivé, Kara, Kpalimé and Tsévié, area lookup, attachment of
official records, provisional numbers, parsing (incl. Lomé street codes), French spoken form, floors, and national names:
same-named areas (Tokpo ×3, Kamina ×3, Lom-Nava) decoding to different places from the name and number alone, disjoint
blocks per name key, numbers outside every block refused, the check digit binding name + number + area, name folding and
cleaning (vectors `sameName` in test_vectors.json); plate names (vectors `plateNames`): the limit, every plate name within
it or flagged, a long official name and its plate name decoding to the same area, and names equal only after shortening
decoding to different places.

`engine/reference/vectors.json` (`tools/vectors.py`, from the frozen register) holds name keys, forms of real codes,
typed texts and what they decode to (or why they are refused), spot codes across the country (dense in Lomé), the
numbering of a real area with 60 inserts, Hilbert indices and pair groupings, and spot codes of points in no outline
(`spotsOutside`: issued compounds, every one on an edge cell among them, points around the outlines and points
refused as outside Togo); `test_tg.py` checks the reference against
every value. The issuer's engine reproduces every value, and checked all 2,768,053 numbers against the reference's
before writing any.

## 14. Registry server

`server/` is a ready-made HTTP service on the published registry (Python standard library and SQLite; `server/README.md`,
the API in `docs/api.md` and `server/openapi.yaml`). `python3 -m server import` verifies every file of `registry/`
against `MANIFEST.json` before loading it; `export` writes the registry back byte for byte; `serve` answers look-ups by
code, name, official address, spot code and point. A deployment issues codes (§7, §10) only when the State or N-WAYS
LIMITED has designated it as the issuer; every other deployment is read-only. One issuer per country is a requirement
of §7, not a policy: two issuers starting from the same registry would give the same free number to two compounds.
`server/test_server.py` checks the server's numbers and forms against the issuer's on real points
(`server/testdata/parity.json`).
