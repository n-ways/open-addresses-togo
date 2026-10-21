# N-Ways address model for Togo: design notes

These notes explain the choices behind the model. The rules themselves are in [engine/SPEC.md](../engine/SPEC.md)
(normative) and the reasoning, measurements and impact in the papers ([paper.md](paper.md), [paper.fr.md](paper.fr.md));
where the three differ, the specification wins. The machine-readable summary is [model/design.json](../model/design.json);
the survey of existing systems is [existing-systems.md](existing-systems.md).

**Status.** Issued on 20 October 2026: 2,768,053 codes, one for every compound in Togo, Grand Lomé included, in 1,379
numbered code areas. The register of areas is frozen and every code is published in [`registry/`](../registry/).

## 0. Official addresses first

Where the State gives an address, that address is the official one. N-Ways imports it, shows it first exactly as the
State writes it, and never competes with it; the N-Ways code stands beside it. Every compound still has an N-Ways code,
in Grand Lomé too, for three reasons: the official system does not yet reach most doors; the code is short to say on
the phone; and it tells apart the compounds that share one official door or street.

| Area | Official system | Data | What N-Ways shows |
|---|---|---|---|
| Former commune of Lomé (69 quartiers) | street addressing since 1997: street code = number + quartier code ("165 AMT", "46BE", "13.QAD"), being modernised by the DAGL | street names and codes partly in OpenStreetMap (ODbL); the DAGL's databases are not released | the official street within 30 m first (71,002 compounds: "Rue Mission Tové, Lomé"), then the N-Ways code ("Fréau-Jardin 10 58") |
| Rest of Grand Lomé (Golfe and Agoè-Nyivé) | DAGL with Edenmap (December 2025): coded and named streets, metric entrance numbers, about 500,000 addresses | not yet released | the N-Ways code; the DAGL address first as soon as it is released |
| Rest of Togo | none: post-office boxes only, no postal code | — | the N-Ways code ("Kara 24 17", "Zongo 1 41 98") |

When an official system reaches a town outside Grand Lomé, its addresses take first place there the same way; the
N-Ways codes already issued stay valid beside them and are never reissued. A post-office box is not an address: it
stays a free-text line.

## 1. First criterion: easy to remember, easy to give

**The remembered form.** A place name people already say, then a number read in pairs, as Togolese phone numbers are:

| Code | Said aloud | Machine form (for systems) |
|---|---|---|
| `Kara 24 17` | "Kara, vingt-quatre, dix-sept" | `TG-KOZ0604-2417-7` |
| `Fiakomé 14 00` (Kpalimé) | "Fiakomé, quatorze, zéro zéro" | `TG-KLO0403-1400-1` |
| `Tsévié 1 32 00` (a 5-digit area) | "Tsévié, un, trente-deux, zéro zéro" | `TG-ZIO1502-13200-4` |

People remember a place name and four or five digits, nothing else. The machine form adds the area key and a Damm
check digit; it lives in the app, on forms and in partner systems, and nobody needs to learn it. People never see or
type the check digit.

**Unique in Togo on its own.** "Kara 24 17" is one compound in the whole country, whoever says it and wherever they are:
no préfecture, no "à Kara", no position of the phone is needed to decode it. Togo repeats place names (six Lom-Nava,
three Kamina, three Tokpo), so all areas sharing a name draw their numbers from one national range for that name (§3.1).

**Short enough to say.** The place name is the area's **plate name**: at most 12 characters and 2 words ("Démakpoè",
not "Agoè-Démakpoè"). The full official name is printed small for context and still decodes when typed (§3.2).

**The options, measured on Togo's counts.**

| Option | Example | To remember | Verdict |
|---|---|---|---|
| Préfecture + 5 alphanumeric characters | `ZIO 7HK2X` | 3 letters and 5 random characters (Zio alone has 278,637 buildings, so 5 base-20 characters) | rejected: hard to memorise; letters are read differently in French, Ewe and Kabiyè |
| Digits only, national | `4817 229` | 7 digits with no place cue (2.77 million compounds × 2) | rejected: nothing anchors memory; one typo lands anywhere in the country |
| **Place name + 4 digits** | `Kara 24 17` | a known word and two pairs | **chosen**: 1,251 of the 1,379 areas take 4 digits |

**Arithmetic.** A 4-digit number without a leading zero has 9,000 values (1000–9999). Half is kept free for growth and
infill, so an area takes 4 digits when its compounds × 2 fit in its name's 4-digit part. At issue, 1,251 areas have 4
digits (1,549,299 compounds, 56%) and 128 have 5 (1,218,754): the largest towns and the dense cantons of Grand Lomé,
whose quartiers and villages are not yet named in the open data. Naming them (the INSEED locality lists of the RGPH-5,
the communes, people naming their quartier when they confirm a door) lets later areas be cut smaller, without changing
an issued code.

**Numbers in Togo's languages.** French is the language of numbers on phones, prices and plates, and phone numbers are
given in pairs ("90 12 34 56"), so codes are printed and spoken in pairs. Ewe and Kabiyè count in base ten; speakers
switch to French for long numbers.

**Never confused with a Lomé street code.** A street code is number first, 1–3 digits ("165 AMT"); an N-Ways code is a
place name first, then 4 or 5 digits. The engine recognises a street code and says so.

**Getting it.**

| Situation | Steps |
|---|---|
| Home already on the map (every compound at issue) | the app shows "Mon adresse : Kara 24 17", with the official address first where there is one |
| Standing at the gate | open the app, tap "C'est chez moi" |
| Sharing it | tap Share: WhatsApp or SMS gets the address and a link |
| On the gate | a plate or sticker with the remembered code and a QR code |
| A new house not on the map | Add my home (§8): a provisional code on the spot |
| A courier or a partner | looks the customer's code up in the API |

## 2. Code areas

| Kind | Numbered | Key | Source |
|---|---|---|---|
| Lomé quartier | 69 | quartier code: `AMT`, `BE`, `FRJ`, `TKL`… | OpenStreetMap admin_level 10 `ref` (ODbL) |
| Canton kept whole | 215 | préfecture key + the canton's two digits: `KOZ14` | HDX COD-AB admin3 (2021, CC BY-IGO) |
| Named-place cell of a split canton | 1,095 | canton key + 2 digits: `KOZ0604` | OpenStreetMap place points inside the canton |
| Split canton (container of its cells) | not numbered (158, including the canton "Lomé Commune") | `KOZ06`, `LOM01` | HDX COD-AB admin3 |

Préfecture keys are three letters, unique and distinct from every Lomé quartier code (`ZIO`, `KOZ` Kozah, `TCH`
Tchaoudjo, `TON` Tône, `KLO` Kloto, `VOG` Vo…; the full table is in design.json). A canton's two digits are the last two
of its HDX p-code (`TG020706` Lama → `KOZ06`).

**Why cantons.** The 117 communes (2019) have no open boundaries; the 39 préfectures are too big for short numbers; the
cantons are traditional chiefdoms people know by name, with open boundaries, and most fit 4 digits once split at their
named places. The commune becomes an attribute once its boundaries are published.

**Frozen.** Once codes are issued in an area its polygon, key, index and blocks never change. Renames, new cantons and
commune boundaries only add aliases (`aliases` in `model/areas/areas.json`); a new area cut from a full one keeps the
old codes where they are.

## 3. Numbers

- Length fixed per area: 4 digits (1000–9999) or 5 (10000–99999); never 1–3 digits; no leading zero.
- First issue: compounds sorted along a Hilbert curve over the area's box; a step `s = floor(capacity / (N × 1.5))`
  leaves `s − 1` free numbers after each compound for infill; the top third of the block is a tail reserve.
- A new compound: the free number between its neighbours on the curve closest to their midpoint; else the lowest free
  number of the tail reserve; else of the area's extra blocks; else a new block of its name.
- Never reused. Demolished → retired. Split compound → the part with the gate keeps the code. Merged → the older code
  survives and the other becomes an alias.
- The numbers of an area form its **block** in its name's national range (§3.1): Kara `1000–5799`, Tsévié
  `10000–55199`.

### 3.1 Same place names: one national range per name

Telling same-named places apart by context (a préfecture after a comma, the phone's position, an app asking "which
one?") is rejected: a code is said over the phone, written on a parcel and typed by someone far away. A remembered code
must be unique nationally **on its own**.

**One name, one national number space.** Every area's place name is folded to a **name key**; all areas with the same
key, anywhere in Togo, share one number space for that name, cut into **blocks**, one per area. "Name + number" falls in
exactly one block, so it decodes to exactly one area and one compound.

**The name key** (French-written Ewe, Kabiyè and other Togolese names). Fold case and accents; Ewe letters to their base
(ɛ→e, ɔ→o, ŋ→n, ƒ→f, ʋ→v, ɖ→d, ɣ→g); drop spaces, hyphens and apostrophes; drop a leading French article (le, la, les,
l'); drop trailing part numbers (Zongo 1, Tablo II); then fold the French spelling variants of the same sounds: PH=F,
QU=K, DJ=J, OU=U=W, hard C=K (Copé = Kopé), doubled letters single (Nassiété = Nasiete). "Djanta Copé" and "Djanta kopé",
"Ediwlou" and "Ediwoulou", "Lom-Nava" and "Lom Nava" are one name. Over-folding is harmless (two names merely share a
range); under-folding would break uniqueness, so the fold is generous. Generic words in OpenStreetMap names are cleaned
first ("Village de Zomaï" → Zomaï, "Quartier Badara" → Badara, "unknow" → the canton's name): 70 names are cleaned, and
no numbered area keeps a digit in its name (a "Zongo 1 06 87" would read as 10687).

**Blocks.** A name's space is 1000–9999 (4 digits), then 10000–99999 (5 digits). An area's block is its compounds × 2,
rounded up to a hundred, at least 200: the headroom for infill and the tail reserve. A block goes in the name's 4-digit
part while it fits, else in its 5-digit part; smaller blocks are placed first, so most areas keep 4 digits. A name always
keeps at least 5,000 numbers free for future same-named areas and extra blocks.

**At issue** (`model/areas/names.json`, built by `tools/name_ranges.py`): 1,323 name keys for 1,379 areas; 50 keys are
shared, by 106 areas holding 240,136 compounds; 34 shared names fit wholly in 4 digits, 16 have a 5-digit block. The
most repeated name is Lom-Nava, six areas: Ogou `1000–1199`, Lomé `1200–2899`, Moyen-Mono `2900–5199`, Kloto
`5200–8399`, Ogou `10000–17599`, Zio `17600–26699`. The largest single block is Sagbado's, `10000–92599` (41,259
compounds). No name needs a qualifier.

Examples. **Tokpo**: Danyi `1000–1199`, Zio `1200–1999`, Lacs `2000–4999`, so "Tokpo 11 00" is in Danyi and
"Tokpo 24 17" in Lacs, 140 km away. **Kamina**: Akébou `1000–4999`, Ogou `5000–9799`, Est-Mono `10000–20699`.
**Zongo**: Kloto `1000–2699` ("Zongo 15 00"), Kozah `10000–23299` ("Zongo 1 41 98"). A number in no block
("Tokpo 54 17") is refused, never guessed.

**A qualifier only when a name cannot fit.** If a name's blocks ever exceeded its space less the spare, one area of
that name would take the qualifier people already say with it (the neighbouring village or quartier), decided once,
listed in `tools/name_ranges.py` (`QUALIFIERS`) and `names.json`, and becoming a name of its own. None is needed.

**Frozen at issue.** Blocks were sized on the real compound counts at issue and are never moved or renumbered. A new
area with an existing name gets a new block from the name's free space; a full area gets an extra block the same way.
Name ids and blocks are appended, never reused. An alias may never be another name's key (the builder refuses it).

### 3.2 Plate names: short enough to say and to print

A name that does not fit on a plate or in one breath is not remembered: "Gboto Koissidamé 10 17" is shortened by people
to "Koissidamé", so the code is built on what they keep.

Each numbered area has two names. The **official name** is the full name (from OpenStreetMap or the canton list,
cleaned as in §3.1): printed in small type on cards and plates, and accepted when typed. The **plate name** is what
people say and type in the code: at most **12 characters** (letters, spaces, hyphens and apostrophes; an accented letter
counts as one) and at most **2 words** (de, du, des, d', la, le… do not count; a hyphen separates words: "Lom-Nava" is 2
words).

**How it is derived** (`engine/reference/plate_names.py`, with Togo's word lists in `tools/name_ranges.py`):

1. a short form people already say, when it is documented with a source (none was found for Togo's areas; see
   `existing-systems.md`);
2. clean: "Esso - Vallai" → Esso-Vallai; drop text in brackets or after a slash ("Dako/Daoude" → Dako) and French generic
   words (Quartier, Cité, Village de, Campement, Ferme, Résidence, Carrefour, "Centre de formation rurale de": "Cité de
   Djagblé" → Djagblé, "Centre de formation rurale de Tami" → Tami);
3. if the result fits, that is the plate name; otherwise the most distinctive one or two whole words, preferring the end
   of the name ("Gboto Koissidamé" → Koissidamé, "Adjahun Fiagbe" → Fiagbe), where Gboto or Agou name the canton or the
   préfecture. A word is never cut.

**Togo's words.** Kopé (copé), kondji (condji) and kodzi mean village in Ewe and Mina, kpota and kpotame the outskirts:
"Aklassou kopé" is a village of its own, not Aklassou, so these words, like haut and bas, are never dropped
automatically. A plate name may not equal a préfecture seat (the region capitals among them), a quartier of Lomé or a
well-known town across the borders (Aflao, Hillacondji, Cotonou, Lomé's neighbours on the Abidjan–Lagos corridor), unless
it is the area's own town.

**The commune's choice.** When the short form is a choice (it would drop kopé or haut; the name joins two villages with a
hyphen, "Landa-Pozenda"; it would equal a known town; or no word stands out) the area is flagged `needsCouncilChoice`
with up to three candidates, and the first is its plate name. Codes are issued under it, and the commune may choose
another once: the old name then stays an alias, and the numbers do not change. A single word over 12 letters
("Koussocointougou") has no candidate and keeps its name until the commune gives a short one.

**Typing the official name still works.** The official name is an alias of its area when it belongs to one plate name:
"Gboto Koissidamé 10 17" and "Koissidamé 10 17" are the same compound. An alias claimed by two plate names, or equal to
another plate name, is dropped and listed (none at issue).

**Shortening makes more names equal**, and the national ranges absorb it: "Centre de formation rurale de Tami" becomes
Tami, which already exists, so the training centre and the village are two blocks of the name Tami.

| Plate names at issue | Count |
|---|---|
| official names over the limit | 122 of 1,379 (121 over 12 characters, 14 over 2 words) |
| the official name as it is | 1,253 |
| shortened by rule | 50: 17 cleaned, 33 to their distinctive words |
| flagged for the commune | **76** (38 hyphen compounds, 25 single long words, 9 that would drop kopé, kondji, kpota or haut, 2 equal to a known town, 2 without a clear choice) |
| still over the limit until the commune chooses | 25 (single long words) |
| longest written codes | 22 characters ("Koussocointougou 10 00", while its commune chooses a shorter name); mean 14.5, median 14 |

The flagged areas, with candidates and reasons, are `councilChoices` in `model/areas/names.json`.

## 4. Check digit and machine form

`TG-<area key>-<number>-<check>`; the check is the Damm digit over the name's 4-digit national id, the area's 4-digit
index and the number: it binds name + number + area, so a number copied onto another area, same-named or not, fails.
Damm detects every single wrong digit and every swap of two neighbouring digits. A system that sends the remembered form
with the check after a dash ("Kamina 54 00-8") is checked too. Sub-units: `.n` = structure n of the compound, `/n` =
entrance n (`/1` is the gate).

## 5. Spot codes (any point)

A geographic grid of 1/32768° cells (3.37 m × 3.38 m in Lomé), framed on the quartier or canton: `FRJ-54-4R` (4
characters in a Lomé quartier), `KOZ06-36X-M4G` (6 in a canton). Characters interleave north and east indices in Togo's
alphabet `23456789CFGHJKMPRVWX`: no vowels (so no words in French, Ewe or Kabiyè), no 0/O or 1/I/L, and **K instead of
Q**: Q is used by neither Ewe nor Kabiyè and is read "ku" in French, while K exists in both. The grid is geographic because
Togo straddles UTM zones 30 and 31 at 0° longitude. Spot codes are computed offline and shared by link; nobody
memorises them.

The quartier and canton outlines are thinned open data: they leave thin gaps between them and stop at the border line,
and 4,415 issued compounds have their entrance outside every outline (at most 1,081 m from one). Such a point takes the
frame of the nearest outline within 1,100 m whose frame holds it (distance to the outline's edges, longitude scaled by
cos φ, ties to the lower key); if none holds it, the nearest outline whose frame lies at most 200 cells (≈ 675 m) away
gives it that frame's nearest edge cell, and the registry keeps the exact entrance. Each of the 4,415 takes its nearest
outline's frame; 13, in Danyi and Golfe, sit on an edge cell. Frames never move, a code decodes in the frame it names,
and every issued compound has a spot code. A point farther out is outside Togo (SPEC §5).

## 6. Compounds, structures, gates

The address unit is the compound: the fenced or walled plot with its portail. At issue, 3,816,753 footprints
form 2,768,053 compounds: 2,063,915 with one structure, 492,792 with two, 138,808 with three and 72,538 with four or
more (1.38 structures per compound).

Grouping rules, in order (confidence): a mapped wall, fence or hedge enclosure of at most 6,000 m² holds one compound
(0.85); a structure under 30 m² (kitchen, guardian's lodge, latrine, boutique) within 6 m of a larger one joins it
(0.6); in the rural north (Kara and Savanes: Kabiyè and Tamberma compounds of round rooms) structures under 35 m² within
3 m chain into one compound, at most 20 (0.5); otherwise one structure is one compound (0.4). People settle the rest
("ces bâtiments sont une seule maison", "voici le portail"); a grouping change never changes an issued code.

Particular cases: a **cour commune** is one compound of class multi-household; an **immeuble** is one compound, and flats
are not coded; **boutiques in the front wall** are entrances of the compound (`/2`, `/3`); a **cité or lotissement with
one gate** gets an estate entrance (estate gate → compound gate). Mapped walls are still rare: 3,236 barrier ways and
1,428 closed enclosures (median 634 m²) in Grand Lomé outside the former commune, and 96 mapped gates.

The entrance is the primary gate. Until people confirm one, the code's point is the centre of the compound's main
structure; mapped OpenStreetMap gates are used where they exist.

## 7. Building profile

| Attribute | How it is inferred | Source tag |
|---|---|---|
| Use class | OSM `building` and POI tags (0.85/0.75), N-Ways places inside the footprint (0.65), OSM landuse (0.5), size (0.3–0.4), default residential (0.45–0.55); people and partners confirm | `osm`, `places`, `landuse`, `size`, `default`, `people`, `partner` |
| Footprint m², perimeter m | geodesic, from the footprint | `osm`, `google`, `microsoft`, `people` |
| Height m | OSM `height` | `osm:height` |
| Floors | OSM `building:levels`, else OSM height ÷ 3 (at least 1); never from the modelled heights of the Google and Microsoft footprints | |
| Floor area | footprint × floors | derived |
| Entrances | gate, doors, boutique doors, with the official address attached where one exists | `osm`, `dagl`, `people` |
| Name | businesses and public buildings only | `places`, `osm` |
| Status | existing / under construction / ruin / demolished | `osm`, imagery, people |
| Cross-references | official address (DAGL street code or name and entrance number; legacy street code); a titre foncier only if the holder adds it | `dagl`, `people` |

Use classes for Togo: residential (concession or cour familiale; cour commune; villa; maison en bande or
"chambres-salon" rental rows; immeuble R+n; case ronde and Kabiyè compound room; takienta, the Tamberma tower-house of
Koutammakou), commercial (boutique, kiosque, marché, magasin or entrepôt), office, government, education, health,
religious (église, mosquée, couvent vodou), industrial (port zone, zone franche), hospitality, transport (gare routière),
mixed use, agricultural, under construction, ruin, unknown.

The evidence is thin today: 3,752,065 of the 3,816,753 structures (98.3 %) are residential, almost all by the default
rule, so the profile always shows its source and confidence, and every confirmation by a person or a partner counts.

Published: class, size, floors, entrances, status, the names of businesses and public buildings, the official address
and the N-Ways code. Never stored: the names of residents, households, phone numbers, identity numbers.

## 8. Add my home (new houses)

1. Stand at the portail: the position is averaged over a few seconds.
2. Draw the building on the imagery, or give the code of the compound when this is another of its doors.
3. Describe it: households, structures, floors, use.
4. A **provisional** code at once, by the issuer's rules (engine/SPEC.md §7 and §10), so it can go on the gate today.
5. **Confirmed** when at least two independent signals agree and none disagrees: journeys or deliveries ending at the
   gate, the household confirming on two different days, a partner record, or new imagery showing the buildings
   (engine/SPEC.md §9).

Safeguards: "Un code N-Ways est une adresse, pas un titre foncier" in the flow (in Togo the cadastre itself neither gives
nor takes property, Code foncier art. 33; only a géomètre agréé's plan and a titre foncier have legal weight); a building
that already has a code gets that code, not a second one; a drawn outline must be between 6 m² and 2 ha; offline, the
spot code is given at once and the compound code on the next connection.

## 9. Official data: import and sync

- **Lomé's street names and codes.** From OpenStreetMap (`ref` such as `165AMT`, names such as "Rue Oukata-Waya") and,
  when obtained, the commune's or the DAGL's street register. Shown exactly as written; spelling is never "corrected".
- **DAGL entrance addresses, when released.** Requested under a data-sharing agreement; N-Ways offers its compound
  registry, gate positions and door confirmations in return. Each record (street code or name, entrance number, point)
  is attached to the nearest gate within 15 m (`attach_official`); records left over are kept at their own point, never
  forced onto a compound. Each DAGL release replaces the previous one; a disagreement between a DAGL record and people's
  confirmations is reported to the DAGL, never overwritten.
- **Postal service (SPT).** The post-office box stays a free-text line; PostMap postal codes, if published, become an
  attribute.
- **Cadastre (OTR).** The titre foncier number is an optional cross-reference its holder may add; never inferred.

## 10. Privacy and law

Codes describe places, never people. Loi 2019-014 applies: N-Ways declares its processing to the IPDCP; consent for door
claims and photos; access, rectification and erasure in the app. No link to the ANID identity number (NIU).

## 11. Governance partners

DAGL (lead for Grand Lomé's addresses); the 117 communes (shared addressing competence); SPT; OTR (DCCF); Togo Digital
and the Ministry of Digital Economy; INSEED (locality lists); IPDCP; emergency services (police 117/161, gendarmerie
172, fire 118); couriers and moto-taxi apps. See [GOVERNANCE.md](../GOVERNANCE.md).
