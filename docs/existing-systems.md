# Togo: existing postal and address systems

Survey of 18 October 2026, repeated on 20 October 2026 before the codes were issued. "Opened" means the page or file
was read on that date; "snippet" means it was seen only in a search result. Every source is listed in
[SOURCES.md](../SOURCES.md); the paper ([paper.md](paper.md), section 2) gives the same findings with references.

At the second check the DAGL's modernised addresses were still not live and their data not released (the last public
step was the restitution of 17 December 2025); Togo still had no postal code; PostMap and TogoLink were unchanged; the
1997 street names and codes of the former commune of Lomé were in OpenStreetMap. Data protection: Loi 2019-014, with
the IPDCP as the authority.

## Verdict

**Togo has no postal codes.** Mail goes to post-office boxes. There is no national door-level address system
in use. Street addressing exists in the former commune of Lomé (since 1997: street codes made of a number and
the quartier code, for example "165 AMT") and is being modernised for the 13 communes of Grand Lomé by the
District Autonome du Grand Lomé (DAGL) with Edenmap (AFD funding, PEUL programme): a **door-level system is
being rolled out in Grand Lomé**, not yet live, format not published.

## What exists

| System | Who | State (2026-10-18) | Format | Open data | Source |
|---|---|---|---|---|---|
| P.O. boxes | Société des Postes du Togo (SPT, "La Poste du Togo") | live | `B.P. 526 LOME` (UPU sheet); in Lomé an office prefix: `01 BP 2274 Lomé 01` | none | UPU addressing sheet Togo, 03/2005 (opened); Togo Digital and La Poste Épargne listings (snippet) |
| Postal code | — | none published | — | — | UPU sheet has no postcode field (opened); USPS Postal Bulletin 12 Jun 2025: SPT asks senders to add phone and email, no postcode (opened) |
| PostMap app | SPT (© 2024) | live app | "digital, physical and postal addressing", "identify the postal code of an address"; the code format is not published anywhere found | no | App Store listing (opened) |
| Lomé street addressing | former commune of Lomé, first phase 1997 | legacy, partly signposted | street code = number + quartier code: "Rue Oukata-Waya 165 AMT", "Avenue de la Présidence 13.QAD", "Rue Batemoni 46BE"; numbers 1–~165 per quartier; 69 quartiers in 5 arrondissements, each with a 2–3 character code (AMT, BE, HDN, TKL, QAD, LO2, UB, RB…) | street names and quartier codes in OpenStreetMap (ODbL) | OSM wiki "Lomé" (opened, 2018); Overpass query of coded Lomé streets, 150 results (opened); thesis on street trade in Lomé (opened); Togo Presse 17 Dec 2025 (opened, dates the first phase to 1997) |
| Grand Lomé addressing modernisation | DAGL + Edenmap, AFD-funded (PEUL) | under way, restitution 17 Dec 2025; not live | roads "codées puis dénommées"; address points on the **metric system** tied to an entrance number; signs with the entrance number and the street code or name; door numbers certified; ~500,000 addresses, 16,000 streets of which ~13,000 unnamed, 13 communes, ~2.4 M people; citizen module planned with Togo Digital (certificate of domicile) | none announced | Togo Presse 17 Dec 2025 (opened); republicoftogo.com 18 Dec 2025 and 5 Jan 2026 (opened); edenmap.com (opened, method not described) |
| Decree on addressing of roads and public squares | Government (Council of Ministers 7 Jul 2022) | proposed decree (projet de décret) adopted; final number and Journal officiel publication not found | defines which roads and squares are addressed and the technical rules; addressing is a shared State / local-authority competence | — | republiquetogolaise.tg, 8 Jul 2022 (opened) |
| SPT Plus Codes call for interest | SPT | Sep–Oct 2020; outcome unknown (possibly PostMap) | Google Plus Codes + Google Maps app | — | Ecofin via osiris.sn (snippet) |
| SPT and what3words | SPT | plan announced in January 2019 for a national three-word postal addressing system; no evidence that it was implemented | three words | — | Togo First, 8 Jan 2019 (opened) |
| TogoLink | private (EDOH VIKPE) | live app since Aug 2025 | 5–7 character GPS code, custom codes for businesses | no: terms reserve all rights | App Store listing (opened); icilome.com 30 Sep 2025 (opened 2026-10-12) |
| Land titles and cadastre | OTR, DCCF (Direction du Cadastre, de la Conservation Foncière et de l'Enregistrement) | live e-services (e-foncier.otr.tg; plans parcellaires filed online since Aug 2026) | a registered property is designated by its **titre foncier** number (Code foncier art. 75) | no public parcel map found; cadastre data public except state secrets and personal data, read-only online access for a fee (art. 45–47) | Loi 2018-005 (FAOLEX text, opened); otr.tg (opened) |
| OpenStreetMap | contributors | live | 171 `addr:housenumber`, ~597 `addr:street`, 91 `addr:postcode` (probably P.O. boxes) in all Togo; ~24% of Lomé's highway ways named | ODbL | Overpass counts, 12 Oct 2026 |

## How addresses are actually used

People give a quartier, a landmark and a phone number ("Bè, en face d'Ecobank"); couriers call. P.O. boxes
are for organisations. Lomé's coded street signs exist in the old city, but the 2025 DAGL work found
~13,000 of 16,000 Grand Lomé streets still unnamed. The fast-growing north (Agoè-Nyivé, 882,695 inhabitants
in 2022) and the coastal strip east towards Baguida have almost no street identification.

## Administrative frame (for the model)

- 5 regions (Maritime, Plateaux, Centrale, Kara, Savanes) plus the District Autonome du Grand Lomé; 39
  préfectures; 117 communes created by Loi 2017-008 (amended by Loi 2019-001), mayors elected Sept 2025
  after the 17 Jul 2025 local elections; 394 cantons in 2019 (Wikipedia list, opened); FEWS NET's "233
  communes" is taken to be an error (snippet).
- 2024 constitution (Fifth Republic): parliamentary system, Senate partly elected by regional and municipal
  councillors; no change to the regions found (snippets; not checked against the text).
- RGPH-5 (2022): 8,095,498 inhabitants; Grand Lomé 2,188,376 (Golfe 1,305,681; Agoè-Nyivé 882,695); urban
  42.9% (KOACI 5 Apr 2023, opened; INSEED leaflet, snippet).
- Open boundaries used by N-Ways: HDX COD-AB Togo (admin1 regions, admin2 40 units incl. "Lomé Commune",
  admin3 373 cantons, valid_on 2021-01-07, CC BY-IGO); OpenStreetMap admin_level 10 for the 69 Lomé quartiers
  with their codes (ODbL). No open boundaries exist for the 117 communes.

## Data protection

Loi n° 2019-014 du 29 octobre 2019 relative à la protection des données à caractère personnel: prior
declaration of processing to the IPDCP (receipt within one month), authorisation for biometric, genetic,
health and criminal data, consent as main legal basis, rights of access, objection, rectification and
erasure; fines up to 100 M FCFA (droitmediasfinance.com summary, opened). The **IPDCP** (Instance de
Protection des Données à Caractère Personnel) started work on 28 Mar 2025, chaired by Lt-Col Bediani Beleï,
with an 11-point plan (CIO Mag, opened). Rules on transfers abroad: **not verified**.

## Land and surveying (for "Add my home")

Loi n° 2018-005 du 14 juin 2018 portant Code foncier et domanial (724 articles): national computerised
cadastre within the conservation service (art. 32–49); every plan parcellaire digital and "rattaché au
réseau géodésique national" (art. 40), which may be "mondial (GPS) ou local"; bornage contradictoire
mandatory for registration (art. 230) by a géomètre assermenté (art. 231); requests need a plan by a
géomètre agréé; **the cadastre "ne peut faire perdre ni conférer un droit de propriété" (art. 33)**;
customary tenure recognised (art. 627 ff.). The datum and projection used in practice (probably WGS84 / UTM
31N) and the existence of a CORS network are **not verified**; neither is the name of the surveyors' order.

## Emergency numbers

Police 117 (landline) / 161 (mobile), gendarmerie 172, fire 118 (French foreign ministry, page of 15 Sep 2026,
opened); civil protection 170 and security call centre 1014 (KOACI Dec 2024, snippet). 112: disputed.

## What N-Ways does with this: the State's address first, wherever one exists

| Area | Official system | Data obtainable? | N-Ways |
|---|---|---|---|
| Former commune of Lomé | 1997 street codes ("165 AMT"), DAGL modernisation | legacy names/codes partly in OSM (ODbL); DAGL databases not released: request a data-sharing agreement | the official street shown first (71,002 compounds within 30 m of a named street), then the N-Ways code ("Fréau-Jardin 10 58") |
| Rest of Grand Lomé (Golfe, Agoè-Nyivé) | DAGL + Edenmap (~500,000 addresses, metric entrance numbers) | not released: request | the N-Ways code; the DAGL address shown first as soon as it is released |
| Rest of Togo | none (P.O. boxes only) | — | the N-Ways code ("Zongo 1 41 98" in Kara) |

Every home has an N-Ways code, Grand Lomé included, with the official address first wherever one exists: the code is
short to say, works where the official system does not yet reach, and tells apart the compounds of one door or street.
The codes were issued on 20 October 2026: 2,768,053, one for every compound.

- Never calls its codes postcodes or official addresses; never competes with DAGL.
- P.O. boxes are not addresses: kept as a free-text pointer. No dependence on PostMap, what3words or TogoLink.
- Offers its compound registry, gate positions and door confirmations to DAGL, the communes, SPT and the State.

## Short place names

No documented short form of a code-area name was found (no commune or INSEED list of the abbreviations people use, such
as a quartier's initials); plate names (engine/SPEC.md 3.2) are therefore derived by rule from the full names, and 76
areas carry a provisional plate name their commune may change once (`councilChoices` in `model/areas/names.json`). Any documented short form found
later goes in `KNOWN` (`tools/name_ranges.py`) with its source.

## Not verified

The decree number and final adoption; the new DAGL code format and the entrance-numbering detail (odd/even,
starting point); any DAGL rollout after Jan 2026; the outcome of the SPT's what3words plan; the role of the urban-planning ministry and
of the national mapping service (DGCN); the 1996 start date (1997 confirmed); transfer rules under Loi 2019-014;
cadastral datum and CORS; the list of préfecture chefs-lieux used for plate names (`SEATS` in `tools/name_ranges.py`)
against the official text; the Ewe and Mina meaning of kopé, kondji, kodzi and kpota in each local name.
