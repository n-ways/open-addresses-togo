# The registry server

A ready-made HTTP service for N-Ways Addressing for Togo. It loads the published registry (`registry/`: every issued
code of Togo, 2,768,053 at the export of 20 October 2026), serves it as a JSON API, and, on the one deployment
designated as the issuer, issues new codes by exactly the rules the N-Ways issuer applies. A ministry, a post office, a
municipality, a courier or a developer can run it without touching the code: two deployments on the same registry give
the same answers.

- Python 3.9 or newer, standard library only (`http.server`, `sqlite3`, `json`, `gzip`, `hashlib`). No packages.
- Parsing, check digits, spot codes, plate names and numbering come from the reference engine
  (`engine/reference/tg_engine.py`), not from a second implementation.
- One SQLite file (WAL mode) holds the registry, its indexes and a spatial index (R*Tree, or an integer grid where
  SQLite was built without it).
- The API is described in [docs/api.md](../docs/api.md) (every endpoint with a real request and response) and in
  [openapi.yaml](openapi.yaml) (OpenAPI 3.1).

## Run it

### With Docker

```sh
cd server
docker compose up -d
curl -s http://localhost:8080/v1/health
```

That is the whole deployment. The image carries the registry of this repository; on the first start, with an empty
`addresses` volume, the container imports it (about a minute: every file's SHA-256 and every count is checked against
`registry/MANIFEST.json`), then serves on port 8080. Later starts reuse the volume. The container runs as an
unprivileged user and reports its health to Docker from `/v1/health`.

### With Python

```sh
python3 -m server import --registry registry --db data/addresses.sqlite
python3 -m server serve --db data/addresses.sqlite --port 8080
```

Run both from the repository root. The import of the full registry takes about 30 seconds on a laptop, with at most
1.5 GB of memory, and makes a database of about 1.6 GB. `serve --registry registry` imports first when the database does not
exist yet.

### Behind a reverse proxy with TLS

The server speaks plain HTTP; put it behind a proxy that terminates TLS. With Caddy, which obtains and renews the
certificate itself:

```
adresses.example.tg {
    reverse_proxy 127.0.0.1:8080
}
```

With nginx:

```nginx
server {
    listen 443 ssl http2;
    server_name adresses.example.tg;
    ssl_certificate     /etc/letsencrypt/live/adresses.example.tg/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/adresses.example.tg/privkey.pem;
    client_max_body_size 64k;
    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
    }
}
```

Publish only the proxy's port; bind the server to `127.0.0.1` (`HOST=127.0.0.1`) or keep it on a private Docker
network. Issuing keys travel in the `Authorization` header and must only ever cross TLS.

## Configure

| Variable | Default | Meaning |
|---|---|---|
| `ADDRESSES_DB` | `data/addresses.sqlite` (`/data/addresses.sqlite` in the container) | the database file |
| `HOST` | `0.0.0.0` | the address to listen on |
| `PORT` | `8080` | the port to listen on |
| `ISSUE_KEYS` | empty | comma-separated bearer keys allowed to issue and change codes. **Empty means read-only**, which is right for every deployment except the designated issuer |
| `ISSUE_PER_DAY` | `5` | codes each key may issue in any 24 hours (the N-Ways issuer allows 5 per phone; raise it for an office key) |
| `CORS_ORIGINS` | empty | comma-separated origins allowed to call the API from a browser, or `*` |

With Docker, set them in the shell or in `server/.env` (never commit that file). Make each key a long random string,
for example `python3 -c "import secrets; print(secrets.token_urlsafe(32))"`, give one key to each office or system,
and remove a key from `ISSUE_KEYS` to revoke it. The database records which key issued a code by a fingerprint
(`key:` and 16 hex digits of its SHA-256), never the key itself.

## Back up

The database is the only state. Two backups, both safe while the server runs:

```sh
# a consistent copy of the database
python3 -m server backup --db data/addresses.sqlite --out backup/addresses-$(date +%F).sqlite
# the registry in the published format (what the issuer publishes; re-importable anywhere)
python3 -m server export --db data/addresses.sqlite --out backup/registry-$(date +%F)
```

In the container: `docker compose exec addresses python3 -m server export --db /data/addresses.sqlite --out /data/export`,
then copy `/data/export` out of the volume. A read-only deployment needs no backup: its database can always be rebuilt
from the published registry.

## Update to a newer registry

When a newer registry is published (a `git pull` of this repository, or a registry directory from the issuer):

```sh
python3 -m server import --registry registry --db data/addresses.sqlite
# then restart the server
```

The import builds a new database beside the old one, verifies every file and count against the new manifest, and only
then replaces the old file. A mismatch stops it with the old database untouched. Codes this deployment issued that the
new registry does not hold yet, and status or entrance changes made here, are carried over (and listed in the import
report). With Docker, rebuild the image and import into the volume:

```sh
docker compose build
docker compose run --rm addresses python3 -m server import --registry /app/registry --db /data/addresses.sqlite
docker compose up -d
```

`python3 -m server export` writes the registry back in exactly the published format: after an import, the exported
files are byte for byte the published ones (the tests check this), and `MANIFEST.json` is identical as long as nothing
was issued or changed.

## One issuer

**A country has one issuer of codes.** A deployment issues codes only if the State or N-WAYS LIMITED has designated
it as the issuer; every other deployment runs read-only, with `ISSUE_KEYS` empty.

The reason is arithmetic, not policy. A new code takes the next free number of its area: the free number nearest the
middle of the gap between its neighbours on the area's curve, or the next one of the tail reserve. Two servers that
issue independently start from the same registry, see the same gap, and hand out the same number to two different
homes. Nothing in either server can detect it, because each is right on its own data; the collision only appears when
the two registries meet, and by then both homes have plates. One issuer, with every other deployment reading its
published registry, makes a duplicate impossible. If the designated issuer changes (the State takes over issuing from
N-WAYS LIMITED, for example), the new issuer imports the last registry of the old one and the old one stops issuing on
the same day.

Inside one deployment, issuing is serialised: one issue at a time in a process, and an immediate SQLite write lock
across processes, so several server processes on one database are safe.

## Issuing rules

`POST /v1/codes` applies the N-Ways issuer's rules, in this order:

1. The key must be valid and have issued fewer than `ISSUE_PER_DAY` codes in the last 24 hours (`429` otherwise).
2. The point must be in Togo (`422 outside`): in a quartier or canton outline, or in no outline but with a spot code
   (a compound in a gap between outlines or just over a border line, engine/SPEC.md §5); and, whatever the outlines
   say, inside the national border or within 300 m of it (`422 outside`). The border decides: the canton outlines
   and the spot-code rule reach over it in places, and a building in a neighbouring country never gets a Togo code
   (`engine/data/border.json`, checked by `engine/reference/border.py`, engine/SPEC.md §10). Moving an entrance
   (`PATCH`) applies the same tests to the new entrance.
3. For a new compound (no `of`): no live code may lie within 3 m of the point (`409 exists`, with that code's card).
   With an outline, the outline must be between 6 m² and 20,000 m² (`422 bad_outline`), and must not hold an issued
   code's point or overlap an outline issued here (`409 exists`).
4. For another door (`of`): the code must exist and its entrance be within 80 m of the point (`404`, `422 too_far`);
   the door takes that code's area.
5. Otherwise the area is the area of the nearest live code within 250 m, so a new house joins its neighbours; else the
   code area the point lies in (engine/SPEC.md §2); else the numbered area whose place point is nearest.
6. The number is the reference engine's `insert_number`: between the new compound's neighbours on the area's Hilbert
   curve (numbers below the tail reserve), as near the middle as possible; else the lowest free number of the tail
   reserve; else of the area's extra blocks; else the first number of a new block of the name (engine/SPEC.md §3.1
   rule 7), which is stored with the area and appears in `areas.csv` on export. Retired numbers count as used.
7. The code is written with status `provisional`, `issued: on-demand`, its entrance at the point (`centre`, or `door`
   with `of`), its spot code, and, with an outline, one residential structure of that floor area.

`PATCH /v1/codes/{machine}` confirms a code, returns it to provisional, retires it (its number is never given again),
or moves its entrance by at most 80 m. A retired code cannot change.

The published registry gives one point per compound and no building outlines, so the "already has a code" checks of
step 3, and the look-up by point of `/v1/at` (12 m), measure from those points; the N-Ways issuer also tests the
footprints it holds. Numbers, areas, forms and spot codes do not depend on footprints: the tests check them against
the N-Ways issuer's own results for the same points (`testdata/parity.json`).

## Test

```sh
python3 -m unittest server.test_server      # from the repository root; about 3 seconds
```

The tests run on `testdata/registry`, a fixture made of real files: the full area table, every code of Plaine du
Mô (10,072), and 24 issued compounds of five other zones whose entrances lie in no quartier or canton outline. They
cover the import and export round trip (byte-identical), refused imports (a changed file, a wrong
count), a safe re-import that keeps local work, every endpoint with its errors, parity with the N-Ways issuer on 20
points issued one after another (`testdata/parity.json`), an extension block for a full area, the duplicate checks,
the daily limit, the read-only mode, and points in the gaps between outlines (found by location, issued, an entrance
moved there) against points far outside, which stay refused, and points across the national border, refused even
where a zone outline or a spot code reaches them.

## Files

| File | What it does |
|---|---|
| `__main__.py` | the command line: `import`, `serve`, `export`, `backup` |
| `store.py` | the SQLite schema, the verified import, the export in the published format, the look-ups |
| `engine.py` | the reference engine and the national border as the server uses them, with the area blocks kept in step with the database |
| `issue.py` | issuing and changing codes |
| `api.py` | the HTTP server and the endpoints |
| `openapi.yaml` | the API description (OpenAPI 3.1) |
| `Dockerfile`, `docker-compose.yml` | the container |
| `test_server.py`, `testdata/` | the tests and their fixture |
