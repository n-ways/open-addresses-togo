"""Command line: import, serve, export, backup.

    python3 -m server import --registry registry --db data/addresses.sqlite
    python3 -m server serve  --db data/addresses.sqlite --port 8080
    python3 -m server export --db data/addresses.sqlite --out out/registry
    python3 -m server backup --db data/addresses.sqlite --out backup/addresses.sqlite

Settings may also come from the environment: ADDRESSES_DB, PORT, HOST, ISSUE_KEYS (comma-separated
bearer keys; none means read-only), ISSUE_PER_DAY (codes per key per 24 hours) and CORS_ORIGINS
(comma-separated origins, or *). `serve --registry DIR` imports DIR first when the database does not
exist yet, which is how the container starts.
"""
import argparse
import json
import os
import sys

from . import store as S

DEFAULT_DB = os.path.join('data', 'addresses.sqlite')


def _env_list(name):
    return [x.strip() for x in (os.environ.get(name) or '').split(',') if x.strip()]


def main(argv=None):
    ap = argparse.ArgumentParser(prog='python3 -m server', description='N-Ways Addressing for Togo: registry server.')
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('import', help='import the published registry into a database (verified against MANIFEST.json)')
    p.add_argument('--registry', default='registry')
    p.add_argument('--db', default=os.environ.get('ADDRESSES_DB') or DEFAULT_DB)
    p = sub.add_parser('serve', help='serve the JSON API')
    p.add_argument('--db', default=os.environ.get('ADDRESSES_DB') or DEFAULT_DB)
    p.add_argument('--host', default=os.environ.get('HOST') or '0.0.0.0')
    p.add_argument('--port', type=int, default=int(os.environ.get('PORT') or 8080))
    p.add_argument('--registry', help='import this registry first if the database does not exist yet')
    p = sub.add_parser('export', help='write the registry in the published format')
    p.add_argument('--db', default=os.environ.get('ADDRESSES_DB') or DEFAULT_DB)
    p.add_argument('--out', required=True)
    p = sub.add_parser('backup', help='write a consistent copy of the database (safe while the server runs)')
    p.add_argument('--db', default=os.environ.get('ADDRESSES_DB') or DEFAULT_DB)
    p.add_argument('--out', required=True)
    a = ap.parse_args(argv)

    def log(msg):
        sys.stderr.write(msg + '\n')

    if a.cmd == 'import':
        try:
            rep = S.import_registry(a.registry, a.db, log=log)
        except S.RegistryError as e:
            log('import refused: %s (the database was left as it was)' % e)
            return 1
        print(json.dumps(rep, ensure_ascii=False, indent=2))
        return 0
    if a.cmd == 'export':
        if not os.path.exists(a.db):
            log('no database at %s' % a.db)
            return 1
        con = S.connect(a.db, readonly=True)
        try:
            man = S.export_registry(con, a.out, log=log)
        finally:
            con.close()
        print(json.dumps({'codes': man['codes'], 'zones': len(man['byUnit']), 'out': a.out}, indent=2))
        return 0
    if a.cmd == 'backup':
        if os.path.exists(a.out):
            log('%s exists: choose a new file' % a.out)
            return 1
        os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
        src = S.connect(a.db, readonly=True)
        dst = S.connect(a.out)
        try:
            src.backup(dst)
        finally:
            dst.close()
            src.close()
        print(json.dumps({'backup': a.out, 'bytes': os.path.getsize(a.out)}, indent=2))
        return 0
    if a.cmd == 'serve':
        if not os.path.exists(a.db):
            if not a.registry:
                log('no database at %s: run `python3 -m server import` first, or pass --registry' % a.db)
                return 1
            log('no database at %s: importing %s first' % (a.db, a.registry))
            try:
                S.import_registry(a.registry, a.db, log=log)
            except S.RegistryError as e:
                log('import refused: %s' % e)
                return 1
        from .api import App, serve
        try:
            per_day = int(os.environ.get('ISSUE_PER_DAY') or 5)
        except ValueError:
            log('ISSUE_PER_DAY must be a whole number')
            return 1
        app = App(a.db, keys=_env_list('ISSUE_KEYS'), per_day=per_day, cors=_env_list('CORS_ORIGINS'))
        serve(app, a.host, a.port)
        return 0
    return 2


if __name__ == '__main__':
    sys.exit(main())
