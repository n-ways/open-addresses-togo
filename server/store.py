"""The SQLite store: import of the published registry, look-ups, and export in the published format.

One file holds everything (WAL mode). Each registry column is kept exactly as published, as text, so
that an export after an import reproduces the registry byte for byte; numeric copies of the point and
number serve the indexes and the spatial look-ups.
"""
import contextlib
import csv
import gzip
import hashlib
import io
import json
import math
import os
import sqlite3
import time

from . import COUNTRY

# Columns of a registry file (<zone>.csv) and of the area table (areas.csv), in published order.
CODE_COLUMNS = ['machine', 'home', 'written', 'zone', 'official_name', 'number', 'check', 'status', 'issued', 'issued_at',
                'entrance_lat', 'entrance_lng', 'entrance_kind', 'spot_code', 'official_address', 'class', 'use', 'kind',
                'structures', 'floor_area_m2', 'rule', 'estate']
AREA_COLUMNS = ['zone', 'index', 'kind', 'plate_name', 'official_name', 'prefecture', 'region', 'name_key', 'name_id',
                'blocks', 'needs_council_choice', 'official_system', 'place_lat', 'place_lon', 'box']

# SQL names of the registry columns (a few are SQL keywords).
_SQL = {'check': 'check_digit', 'index': 'idx', 'class': 'class_', 'use': 'use_', 'kind': 'kind'}


def sql_name(col):
    return _SQL.get(col, col)


CODE_SQL = [sql_name(c) for c in CODE_COLUMNS]
AREA_SQL = [sql_name(c) for c in AREA_COLUMNS]
GRID = 0.001    # degrees per cell of the fallback spatial index (about 110 m)


class RegistryError(Exception):
    """The registry on disk does not match its manifest, or the database cannot take it."""


def connect(path, readonly=False):
    if readonly and not os.path.exists(path):
        raise RegistryError('no database at %s' % path)
    # A read-only connection is a normal one with query_only set: SQLite's mode=ro cannot open a
    # WAL database whose -shm file does not exist yet.
    con = sqlite3.connect(path, timeout=30, check_same_thread=False)
    con.row_factory = sqlite3.Row
    con.execute('PRAGMA busy_timeout = 30000')
    if readonly:
        con.execute('PRAGMA query_only = ON')
    return con


def has_rtree(con):
    try:
        con.execute('CREATE VIRTUAL TABLE temp.rtree_probe USING rtree(id, a, b, c, d)')
        con.execute('DROP TABLE temp.rtree_probe')
        return True
    except sqlite3.OperationalError:
        return False


def grid_cell(lat, lng):
    return int(math.floor(lat / GRID)) * 1000000 + int(math.floor((lng + 180.0) / GRID))


SCHEMA = '''
CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE areas (
  ord INTEGER NOT NULL, %(areas)s,
  PRIMARY KEY (zone));
CREATE TABLE codes (
  id INTEGER PRIMARY KEY, %(codes)s,
  unit TEXT NOT NULL, name_id INTEGER NOT NULL, num INTEGER NOT NULL, lat REAL NOT NULL, lng REAL NOT NULL,
  anchor_lat REAL NOT NULL, anchor_lng REAL NOT NULL, official_key TEXT, cell INTEGER NOT NULL,
  local TEXT, issued_by TEXT, outline TEXT);
''' % {'areas': ', '.join('%s TEXT NOT NULL' % c for c in AREA_SQL),
       'codes': ', '.join('%s TEXT NOT NULL' % c for c in CODE_SQL)}

INDEXES = '''
CREATE UNIQUE INDEX codes_machine ON codes (machine);
CREATE UNIQUE INDEX codes_name_number ON codes (name_id, num);
CREATE INDEX codes_zone_number ON codes (zone, num);
CREATE INDEX codes_written ON codes (written);
CREATE INDEX codes_home ON codes (home);
CREATE INDEX codes_official ON codes (official_key);
CREATE INDEX codes_unit_order ON codes (unit, name_id, num);
CREATE INDEX codes_unit_machine ON codes (unit, machine);
CREATE INDEX codes_spot ON codes (spot_code);
CREATE INDEX codes_cell ON codes (cell);
CREATE INDEX codes_issued_by ON codes (issued_by, issued_at);
CREATE INDEX codes_local ON codes (local);
'''


def official_key(text):
    """Folded form of an official address for look-ups: case, accents, punctuation and a trailing
    ', Lomé' do not matter."""
    if not text:
        return None
    from .engine import E
    t = E.plain(text).upper()
    t = ''.join(ch if ch.isalnum() else ' ' for ch in t)
    words = t.split()
    if words and words[-1] == 'LOME' and len(words) > 1:
        words = words[:-1]
    return ' '.join(words) or None


# ---------------------------------------------------------------- reading the published files
class _HashingLines:
    """Lines of a gzip file, decoded as UTF-8, with the SHA-256 of the uncompressed bytes."""

    def __init__(self, path):
        self.path = path
        self.sha = hashlib.sha256()
        self.size = 0

    def __iter__(self):
        with gzip.open(self.path, 'rb') as f:
            rest = b''
            while True:
                chunk = f.read(1 << 20)
                if not chunk:
                    break
                self.sha.update(chunk)
                self.size += len(chunk)
                buf = rest + chunk
                lines = buf.split(b'\n')
                rest = lines.pop()
                for line in lines:
                    yield line.decode('utf-8') + '\n'
            if rest:
                yield rest.decode('utf-8')


def read_manifest(registry):
    p = os.path.join(registry, 'MANIFEST.json')
    if not os.path.exists(p):
        raise RegistryError('%s: no MANIFEST.json' % registry)
    with open(p, encoding='utf-8') as f:
        man = json.load(f)
    if man.get('country') != COUNTRY:
        raise RegistryError('%s is the registry of %r, not %s' % (registry, man.get('country'), COUNTRY))
    return man


def _rows(path, columns):
    lines = _HashingLines(path)
    reader = csv.reader(iter(lines))
    header = next(reader, None)
    if header != columns:
        raise RegistryError('%s: unexpected columns %s' % (os.path.basename(path), header))
    return lines, reader


# ---------------------------------------------------------------- import
def import_registry(registry, db_path, log=print):
    """Import every file of `registry` into a new database, verify it against the manifest, and
    only then put it in place of `db_path`. Codes this deployment issued or changed, and that the
    new registry does not already hold as such, are carried over. Returns a report dict."""
    man = read_manifest(registry)
    want = man.get('sha256') or {}
    if 'areas.csv' not in want:
        raise RegistryError('MANIFEST.json lists no areas.csv')
    units = sorted(k[:-4] for k in want if k != 'areas.csv')
    for name in want:
        if not os.path.exists(os.path.join(registry, name + '.gz')):
            raise RegistryError('%s.gz is listed in MANIFEST.json but missing' % name)
    d = os.path.dirname(os.path.abspath(db_path))
    os.makedirs(d, exist_ok=True)
    tmp = db_path + '.importing'
    for p in (tmp, tmp + '-wal', tmp + '-shm', tmp + '-journal'):
        if os.path.exists(p):
            os.remove(p)
    con = connect(tmp)
    started = time.time()
    try:
        con.execute('PRAGMA journal_mode = OFF')
        con.execute('PRAGMA synchronous = OFF')
        con.execute('PRAGMA cache_size = -65536')
        con.executescript(SCHEMA)
        rtree = has_rtree(con)
        if rtree:
            con.execute('CREATE VIRTUAL TABLE codes_geo USING rtree(id, min_lat, max_lat, min_lng, max_lng)')
        # areas
        path = os.path.join(registry, 'areas.csv.gz')
        lines, reader = _rows(path, AREA_COLUMNS)
        name_ids = {}
        n_areas = 0
        for i, row in enumerate(reader):
            if len(row) != len(AREA_COLUMNS):
                raise RegistryError('areas.csv line %d: %d fields' % (i + 2, len(row)))
            con.execute('INSERT INTO areas (ord, %s) VALUES (?, %s)' % (', '.join(AREA_SQL), ', '.join('?' * len(row))), [i] + row)
            name_ids[row[0]] = int(row[8] or 0)
            n_areas += 1
        if lines.sha.hexdigest() != want['areas.csv']:
            raise RegistryError('areas.csv: SHA-256 %s, MANIFEST.json says %s' % (lines.sha.hexdigest(), want['areas.csv']))
        log('areas.csv: %d areas, SHA-256 verified' % n_areas)
        # codes, one file per zone
        total = 0
        counts = {}
        ins = 'INSERT INTO codes (%s, unit, name_id, num, lat, lng, anchor_lat, anchor_lng, official_key, cell) VALUES (%s)' % (
            ', '.join(CODE_SQL), ', '.join('?' * (len(CODE_SQL) + 9)))
        for unit in units:
            path = os.path.join(registry, unit + '.csv.gz')
            lines, reader = _rows(path, CODE_COLUMNS)
            n = 0
            batch = []
            for row in reader:
                if len(row) != len(CODE_COLUMNS):
                    raise RegistryError('%s.csv line %d: %d fields' % (unit, n + 2, len(row)))
                zone = row[3]
                if zone not in name_ids:
                    raise RegistryError('%s.csv: code %s is in area %s, which areas.csv does not list' % (unit, row[0], zone))
                lat, lng = float(row[10]), float(row[11])
                batch.append(row + [unit, name_ids[zone], int(row[5]), lat, lng, lat, lng, official_key(row[14]), grid_cell(lat, lng)])
                n += 1
                if len(batch) >= 20000:
                    con.executemany(ins, batch)
                    batch = []
            if batch:
                con.executemany(ins, batch)
            got = lines.sha.hexdigest()
            if got != want[unit + '.csv']:
                raise RegistryError('%s.csv: SHA-256 %s, MANIFEST.json says %s' % (unit, got, want[unit + '.csv']))
            if (man.get('byUnit') or {}).get(unit) != n:
                raise RegistryError('%s.csv: %d codes, MANIFEST.json says %s' % (unit, n, (man.get('byUnit') or {}).get(unit)))
            counts[unit] = n
            total += n
            log('%s.csv: %d codes, SHA-256 verified' % (unit, n))
        if total != man.get('codes'):
            raise RegistryError('%d codes in the files, MANIFEST.json says %s' % (total, man.get('codes')))
        log('indexing %d codes' % total)
        con.executescript(INDEXES)
        if rtree:
            con.execute('INSERT INTO codes_geo SELECT id, lat, lat, lng, lng FROM codes')
        meta = {'manifest': json.dumps(man, ensure_ascii=False, sort_keys=True), 'imported_at': _now(),
                'spatial': 'rtree' if rtree else 'grid', 'changed': '0', 'schema': '1'}
        for k, v in meta.items():
            con.execute('INSERT INTO meta (key, value) VALUES (?, ?)', (k, v))
        con.commit()
        carried = _carry_over(db_path, con, log) if os.path.exists(db_path) else {'issued': 0, 'changed': 0, 'conflicts': []}
        con.commit()
        con.execute('PRAGMA journal_mode = WAL')
        con.execute('ANALYZE')
        con.commit()
    except BaseException:
        con.close()
        for p in (tmp, tmp + '-wal', tmp + '-shm'):
            if os.path.exists(p):
                os.remove(p)
        raise
    con.close()
    for p in (db_path + '-wal', db_path + '-shm'):
        if os.path.exists(p):
            os.remove(p)
    os.replace(tmp, db_path)
    return {'codes': total, 'areas': n_areas, 'zones': counts, 'exported': man.get('exported'),
            'spatial': 'rtree' if rtree else 'grid', 'carriedOver': carried, 'seconds': round(time.time() - started, 1)}


def _carry_over(old_path, con, log):
    """Copy into the new database what this deployment did since its last import: codes it issued
    (when the new registry does not hold them yet) and status or entrance changes it made."""
    old = connect(old_path, readonly=True)
    out = {'issued': 0, 'changed': 0, 'conflicts': []}
    try:
        if not old.execute("SELECT 1 FROM sqlite_master WHERE name = 'codes'").fetchone():
            return out
        rtree = con.execute("SELECT value FROM meta WHERE key = 'spatial'").fetchone()[0] == 'rtree'
        for r in old.execute('SELECT * FROM codes WHERE local IS NOT NULL ORDER BY id'):
            r = dict(r)
            now = con.execute('SELECT id FROM codes WHERE machine = ?', (r['machine'],)).fetchone()
            if r['local'] == 'issued' and now is None:
                clash = con.execute('SELECT machine FROM codes WHERE name_id = ? AND num = ?', (r['name_id'], r['num'])).fetchone()
                if clash:
                    out['conflicts'].append('%s: number taken by %s in the new registry' % (r['machine'], clash[0]))
                    continue
                cols = [c for c in r if c != 'id']
                cur = con.execute('INSERT INTO codes (%s) VALUES (%s)' % (', '.join(cols), ', '.join('?' * len(cols))), [r[c] for c in cols])
                if rtree:
                    con.execute('INSERT INTO codes_geo VALUES (?, ?, ?, ?, ?)', (cur.lastrowid, r['lat'], r['lat'], r['lng'], r['lng']))
                area = old.execute('SELECT blocks FROM areas WHERE zone = ?', (r['zone'],)).fetchone()
                mine = con.execute('SELECT blocks FROM areas WHERE zone = ?', (r['zone'],)).fetchone()
                if area and mine and len(area[0]) > len(mine[0]) and area[0].startswith(mine[0]):
                    con.execute('UPDATE areas SET blocks = ? WHERE zone = ?', (area[0], r['zone']))
                out['issued'] += 1
            elif r['local'] == 'changed' and now is not None:
                con.execute('''UPDATE codes SET status = ?, entrance_lat = ?, entrance_lng = ?, entrance_kind = ?, spot_code = ?,
                    lat = ?, lng = ?, cell = ?, local = 'changed' WHERE id = ?''',
                            (r['status'], r['entrance_lat'], r['entrance_lng'], r['entrance_kind'], r['spot_code'],
                             r['lat'], r['lng'], r['cell'], now[0]))
                if rtree:
                    con.execute('UPDATE codes_geo SET min_lat = ?, max_lat = ?, min_lng = ?, max_lng = ? WHERE id = ?',
                                (r['lat'], r['lat'], r['lng'], r['lng'], now[0]))
                out['changed'] += 1
        if out['issued'] or out['changed']:
            con.execute("UPDATE meta SET value = '1' WHERE key = 'changed'")
            log('carried over %d codes issued here and %d changes made here' % (out['issued'], out['changed']))
        for c in out['conflicts']:
            log('not carried over: ' + c)
    finally:
        old.close()
    return out


def _now():
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())


# ---------------------------------------------------------------- export
def _go_csv_field(s):
    """A CSV field quoted exactly as the N-Ways exporter writes it (RFC 4180, quoted only when
    needed: a comma, a quote, a line break, or a leading space)."""
    if s == '':
        return s
    if s == '\\.' or any(c in s for c in ',"\r\n') or s[0] in ' \t\n\v\f\r\x85\xa0':
        return '"' + s.replace('"', '""') + '"'
    return s


def _csv_line(fields):
    return ','.join(_go_csv_field(f) for f in fields) + '\n'


def _write_gz(path, lines):
    """Write lines to path (gzip, no name or time in the header) and return the SHA-256 of the
    uncompressed bytes."""
    sha = hashlib.sha256()
    tmp = path + '.tmp'
    with open(tmp, 'wb') as raw:
        with gzip.GzipFile(filename='', mode='wb', fileobj=raw, mtime=0) as gz:
            buf = []
            size = 0
            for line in lines:
                b = line.encode('utf-8')
                buf.append(b)
                size += len(b)
                if size > (1 << 20):
                    chunk = b''.join(buf)
                    sha.update(chunk)
                    gz.write(chunk)
                    buf, size = [], 0
            chunk = b''.join(buf)
            sha.update(chunk)
            gz.write(chunk)
    os.replace(tmp, path)
    return sha.hexdigest()


def export_registry(con, out_dir, log=print):
    """Write the registry in the published format: areas.csv.gz, one <zone>.csv.gz per zone that
    holds codes, and MANIFEST.json."""
    os.makedirs(out_dir, exist_ok=True)
    meta = dict(con.execute('SELECT key, value FROM meta').fetchall())
    man_in = json.loads(meta['manifest'])
    sha = {}

    def area_lines():
        yield _csv_line(AREA_COLUMNS)
        for r in con.execute('SELECT %s FROM areas ORDER BY ord' % ', '.join(AREA_SQL)):
            yield _csv_line(list(r))
    sha['areas.csv'] = _write_gz(os.path.join(out_dir, 'areas.csv.gz'), area_lines())
    counts = {}
    units = [r[0] for r in con.execute('SELECT DISTINCT unit FROM codes ORDER BY unit')]
    for unit in units:
        n = [0]

        def code_lines(unit=unit, n=n):
            yield _csv_line(CODE_COLUMNS)
            for r in con.execute('SELECT %s FROM codes WHERE unit = ? ORDER BY name_id, num' % ', '.join(CODE_SQL), (unit,)):
                n[0] += 1
                yield _csv_line(list(r))
        sha[unit + '.csv'] = _write_gz(os.path.join(out_dir, unit + '.csv.gz'), code_lines())
        counts[unit] = n[0]
        log('%s.csv: %d codes' % (unit, n[0]))
    changed = meta.get('changed') == '1'
    man = {'byUnit': counts, 'codes': sum(counts.values()), 'country': COUNTRY, 'credit': man_in.get('credit'),
           'engine': man_in.get('engine'), 'exported': _now() if changed else man_in.get('exported'),
           'licence': man_in.get('licence'), 'sha256': sha}
    with open(os.path.join(out_dir, 'MANIFEST.json'), 'w', encoding='utf-8') as f:
        f.write(json.dumps(man, ensure_ascii=False, indent=2, sort_keys=True) + '\n')
    return man


# ---------------------------------------------------------------- look-ups
class Store:
    """Read and write access for one request (one connection each)."""

    def __init__(self, path, readonly=False):
        self.path = path
        self.con = connect(path, readonly=readonly)
        self.con.isolation_level = None   # transactions are explicit (write())
        self._meta = None

    def close(self):
        self.con.close()

    def meta(self):
        if self._meta is None:
            self._meta = dict(self.con.execute('SELECT key, value FROM meta').fetchall())
        return self._meta

    def manifest(self):
        return json.loads(self.meta()['manifest'])

    def rtree(self):
        return self.meta().get('spatial') == 'rtree'

    def count(self, where='', args=()):
        return self.con.execute('SELECT count(*) FROM codes ' + where, args).fetchone()[0]

    def counts_by_status(self):
        return dict(self.con.execute('SELECT status, count(*) FROM codes GROUP BY status').fetchall())

    def counts_by_unit(self):
        return dict(self.con.execute('SELECT unit, count(*) FROM codes GROUP BY unit').fetchall())

    def counts_by_zone(self, unit=None):
        if unit:
            return dict(self.con.execute('SELECT zone, count(*) FROM codes WHERE unit = ? GROUP BY zone', (unit,)).fetchall())
        return dict(self.con.execute('SELECT zone, count(*) FROM codes GROUP BY zone').fetchall())

    def area_rows(self):
        return [dict(r) for r in self.con.execute('SELECT * FROM areas ORDER BY ord')]

    def area_row(self, zone):
        r = self.con.execute('SELECT * FROM areas WHERE zone = ?', (zone,)).fetchone()
        return dict(r) if r else None

    def blocks_by_zone(self):
        return dict(self.con.execute("SELECT zone, blocks FROM areas WHERE blocks <> ''").fetchall())

    def by_machine(self, machine):
        r = self.con.execute('SELECT * FROM codes WHERE machine = ?', (machine,)).fetchone()
        return dict(r) if r else None

    def by_zone_number(self, zone, number):
        r = self.con.execute('SELECT * FROM codes WHERE zone = ? AND num = ?', (zone, number)).fetchone()
        return dict(r) if r else None

    def by_official(self, key, limit):
        return [dict(r) for r in self.con.execute('SELECT * FROM codes WHERE official_key = ? ORDER BY name_id, num LIMIT ?', (key, limit))]

    def count_official(self, key):
        return self.con.execute('SELECT count(*) FROM codes WHERE official_key = ?', (key,)).fetchone()[0]

    def zone_page(self, unit, after, limit):
        return [dict(r) for r in self.con.execute('SELECT * FROM codes WHERE unit = ? AND machine > ? ORDER BY machine LIMIT ?',
                                                  (unit, after, limit))]

    def zone_numbers(self, zone):
        """Every number the area holds (retired ones too) with the point it was numbered from."""
        return [{'number': r[0], 'lat': r[1], 'lon': r[2]}
                for r in self.con.execute('SELECT num, anchor_lat, anchor_lng FROM codes WHERE zone = ?', (zone,))]

    def in_box(self, lat, lng, metres, live_only=True):
        """Codes whose point lies within a box of +/- `metres` around a point."""
        from .engine import E
        m_lat, m_lon = E.metres(lat)
        dlat, dlng = metres / m_lat, metres / m_lon
        live = " AND c.status <> 'retired'" if live_only else ''
        if self.rtree():
            q = '''SELECT c.* FROM codes_geo g JOIN codes c ON c.id = g.id
                   WHERE g.min_lat <= ? AND g.max_lat >= ? AND g.min_lng <= ? AND g.max_lng >= ?''' + live
            rows = self.con.execute(q, (lat + dlat, lat - dlat, lng + dlng, lng - dlng))
        else:
            cells = []
            for i in range(int(math.floor((lat - dlat) / GRID)), int(math.floor((lat + dlat) / GRID)) + 1):
                for j in range(int(math.floor((lng - dlng + 180) / GRID)), int(math.floor((lng + dlng + 180) / GRID)) + 1):
                    cells.append(i * 1000000 + j)
            rows = []
            for k in range(0, len(cells), 500):
                part = cells[k:k + 500]
                rows.extend(self.con.execute('SELECT c.* FROM codes c WHERE c.cell IN (%s)%s' % (','.join('?' * len(part)), live), part))
        return [dict(r) for r in rows]

    def nearest(self, lat, lng, max_m, live_only=True):
        """The code whose point is nearest, within max_m metres (ties to the lower machine form)."""
        from .engine import dist_m
        best = None
        for r in self.in_box(lat, lng, max_m, live_only):
            d = dist_m(lat, lng, r['lat'], r['lng'])
            if d <= max_m and (best is None or (d, r['machine']) < (best[0], best[1]['machine'])):
                best = (d, r)
        return best

    def issued_by_since(self, who, since):
        return self.con.execute("SELECT count(*) FROM codes WHERE issued_by = ? AND issued = 'on-demand' AND issued_at >= ?",
                                (who, since)).fetchone()[0]

    def local_outlines_near(self, lat, lng, metres):
        rows = self.in_box(lat, lng, metres)
        return [r for r in rows if r.get('outline')]

    @contextlib.contextmanager
    def write(self):
        """One write transaction, taken before reading what it depends on (BEGIN IMMEDIATE), so two
        server processes on one database never hand out the same number."""
        self.con.execute('BEGIN IMMEDIATE')
        try:
            yield self.con
        except BaseException:
            self.con.execute('ROLLBACK')
            raise
        else:
            self.con.execute('COMMIT')
