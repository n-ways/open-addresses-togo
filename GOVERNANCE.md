# Governance: N-Ways Addressing for Togo

Status: issued on 20 October 2026 (2,768,053 codes); the repository and the registry are public.

## Rules that do not change

1. **Official addresses first.** Where a State address system exists (Grand Lomé: the DAGL), N-Ways uses its data and
   shows it first, exactly as officially written. Every home also has its N-Ways code, to be said on the phone and to
   tell apart the homes behind one door or along one street.
2. N-Ways codes are "adresses N-Ways", never postcodes or official addresses, until an authority adopts them.
3. A code never moves and is never reissued. Areas are frozen at first issue; renames add aliases.
4. **One issuer.** Codes are issued by one issuer for the whole country: N-WAYS LIMITED, or the body the State
   designates. Any other deployment of the registry server (`server/`) runs read-only. Two issuers working from the
   same registry would hand out the same free number to two different homes (`server/README.md`, "One issuer").
5. Codes describe places, never people.
6. Corrections are settled by the agreement of independent signals (people at the door, deliveries, partners, imagery),
   by rules that are published; nothing waits in a queue for a manual decision.

## Roles

| Role | Who | Does |
|---|---|---|
| Maintainer and issuer | N-WAYS LIMITED (until a hand-over) | engine, specification, area table, issuing, registry releases |
| Official address authority, Grand Lomé | District Autonome du Grand Lomé (DAGL), with Edenmap | its data are authoritative; N-Ways imports them and never overrides them |
| Communes (117) | mayors' offices | shared addressing competence; names of quartiers and villages, and the plate names flagged for their choice; commune boundaries |
| Postal operator | Société des Postes du Togo (SPT) | post-office boxes; PostMap codes if published |
| Cadastre | OTR, DCCF | titre foncier references, added only by the title holder |
| Statistics | INSEED | locality lists (RGPH-5) for naming code areas |
| Digital government | Togo Digital, Ministry of Digital Economy | citizen services; a possible link to the DAGL's citizen module |
| Data protection | IPDCP | prior declaration (Loi 2019-014) |
| Emergency services | police 117/161, gendarmerie 172, fire 118 | users of codes and official addresses |
| Partners and deployments | couriers, moto-taxi apps, utilities, administrations running `server/` | look-ups; corrections through the issuer |

## How things change

- **Area table.** Frozen since the first issue: areas are only appended (a new area cut from a full one keeps the old
  codes where they are), and blocks are only added (an extra block for a full area, from its name's free space).
- **Plate names.** The 76 areas flagged `needsCouncilChoice` may receive their commune's choice once; the old name
  stays an alias and no number changes.
- **Engine and specification.** No change may alter an issued code. Other changes need the conformance vectors to pass
  (`engine/reference/test_tg.py`) and the server tests (`server/test_server.py`); a change to the machine contract
  bumps the SPEC version string.
- **Registry.** Every release is a complete export with its `MANIFEST.json` (counts and SHA-256 of every file).
- **Official data.** Each DAGL release replaces the previous import; disagreements are reported to the DAGL.

How to propose a change: [CONTRIBUTING.md](CONTRIBUTING.md). How to report a problem: [SECURITY.md](SECURITY.md).

## Hand-over

The repository, the issuer role and the registry can be transferred to the DAGL, a grouping of communes or a State
body that adopts the system, with the maintainers' rights. The new issuer imports the last published registry
(`python3 -m server import`) and the previous issuer stops issuing the same day. Licences: [LICENSING.md](LICENSING.md).
