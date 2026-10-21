"""N-Ways Addressing for Togo: the registry server.

A self-contained HTTP service (Python standard library only) that serves the published registry
(registry/) as a JSON API and, where the deployment is the designated issuer, issues new codes by the
same rules as the N-Ways issuer. See server/README.md.

    python3 -m server import --registry registry --db data/addresses.sqlite
    python3 -m server serve  --db data/addresses.sqlite --port 8080
    python3 -m server export --db data/addresses.sqlite --out out/registry
"""

COUNTRY = 'TG'
COUNTRY_NAME = 'Togo'
API_VERSION = '1'
