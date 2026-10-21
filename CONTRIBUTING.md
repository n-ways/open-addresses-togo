# Contributing

Corrections and improvements are welcome from communes, administrations, couriers, researchers and residents.

## What can change, and how

| You want to | Do this |
|---|---|
| Report a wrong entrance, a demolished building, two homes under one code, or one home under two | In the N-Ways app, answer "this code is wrong" at the place; agreeing reports settle it by the published rules (engine/SPEC.md §9). Systems can send the same through the issuer's API. |
| Give a commune's choice of plate name for an area flagged `needsCouncilChoice` | Write to hello@nways.ng from the commune, naming the area key (for example `AKN`) and the chosen name. The old name stays an alias; no number changes. |
| Correct a place name, a spelling or an alias | Open an issue with the area key, the correct form and its source (a commune list, INSEED, a signboard photograph). |
| Propose a change to the engine, the specification, the server or the tools | Open a pull request. It must keep every issued code as it is, pass `python3 engine/reference/test_tg.py` and `python3 -m unittest server.test_server`, and update `engine/SPEC.md` when it changes a rule. |
| Add a documented short form of a place name | Add it to `KNOWN` in `tools/name_ranges.py` with its source, and cite the source in `SOURCES.md`. |
| Correct the papers or the documents | Open a pull request on `docs/`; give a source for any fact. |

## Rules

- **Issued codes never change.** No pull request may renumber, move or reuse a code, or change what a published code
  decodes to.
- **One issuer.** New codes are issued only by the designated issuer (N-WAYS LIMITED, or the body the State
  designates). A deployment of `server/` that is not the issuer runs read-only; please do not run an issuing
  deployment of your own, even for tests on real data: two issuers hand out the same numbers twice. For development,
  issue on a copy of the database.
- **Places, not people.** Never add names of residents, phone numbers or identity numbers to any file.
- **Sources.** Every new fact in the documents or data carries a source in `SOURCES.md`.
- **Licences.** Code contributions are under Apache 2.0, data under ODbL 1.0, documents under CC BY 4.0
  ([LICENSING.md](LICENSING.md)).

## Running the checks

```sh
python3 engine/reference/test_tg.py          # the reference engine and the conformance vectors
python3 -m unittest server.test_server       # the registry server, its API and parity with the issuer
```

Both use Python 3.9 or newer and nothing else.
