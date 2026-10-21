"""The JSON API (/v1) over HTTP.

Every response is JSON. Errors are {"error": {"code": "...", "message": "..."}} with the matching HTTP
status. Reads need no key; issuing and changing codes need a bearer key from ISSUE_KEYS, and are
refused outright when the deployment has none (a read-only deployment).
"""
import hashlib
import hmac
import json
import re
import sys
import time
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlsplit

from . import API_VERSION, COUNTRY, COUNTRY_NAME
from . import issue as I
from . import store as S
from .engine import E, SPEC, Engine, dist_m, numbered, parse_blocks, place_line, plus_code, prefecture_name, unit_of

AT_M = 12.0          # /v1/at: a code within this distance of the point is the compound there
SPOT_ON_HOME_M = 15.0
NEAR_MAX_M = 500.0
NEAR_MAX_N = 100
PAGE_MAX = 1000
BODY_MAX = 65536
LICENCES = {'data': 'ODbL-1.0', 'code': 'Apache-2.0', 'documents': 'CC-BY-4.0'}
CREDIT_URL = 'https://github.com/n-ways/open-addresses-togo'


class ApiError(Exception):
    def __init__(self, status, code, message, extra=None):
        Exception.__init__(self, message)
        self.status, self.code, self.message, self.extra = status, code, message, extra


# ---------------------------------------------------------------- representations
def area_json(eng, a, counts=None):
    if a is None:
        return None
    out = {'key': a['key'], 'index': a['index'], 'kind': a['kind'], 'plateName': a['name'],
           'officialName': a.get('officialName') or None, 'aliases': a.get('aliases') or [],
           'prefecture': prefecture_name(a.get('prefecture') or '') or None,
           'region': a.get('region') or ('Maritime' if a['kind'] == 'lome-quartier' else None),
           'zone': unit_of(a), 'place': place_line(a), 'numbered': numbered(a),
           'nameKey': a.get('nameKey'), 'nameId': a.get('nameId'),
           'blocks': [list(b) for b in a.get('blocks') or []], 'numberLength': a.get('numberLength'),
           'nameProvisional': bool(a.get('needsCouncilChoice')), 'officialSystem': _official_system(a),
           'point': {'lat': a['point'][1], 'lng': a['point'][0]}, 'box': a['box']}
    if a['kind'] == 'cell':
        p = eng.area_by_index(a.get('parent'))
        out['canton'] = {'key': p['key'], 'name': p['name']} if p else None
    if a.get('cells'):
        out['cells'] = [eng.area_by_index(i)['key'] for i in a['cells'] if eng.area_by_index(i)]
    if counts is not None:
        out['codes'] = counts.get(a['key'], 0)
    return out


def _official_system(a):
    s = a.get('officialSystem')
    if isinstance(s, dict):
        return s.get('system')
    return s or None


def registry_json(row):
    """Every registry column, by its published name, exactly as published."""
    return {c: row[S.sql_name(c)] for c in S.CODE_COLUMNS}


def card(eng, row):
    a = eng.area(row['zone'])
    lat, lng = float(row['entrance_lat']), float(row['entrance_lng'])
    number = int(row['number'])
    return {
        'machine': row['machine'],
        'remembered': row['written'],
        'home': row['home'],
        'spoken': E.spoken_fr(eng.areas, a, number) if a else None,
        'plateName': a['name'] if a else None,
        'number': number,
        'check': int(row['check_digit']),
        'status': row['status'],
        'issued': row['issued'],
        'issuedAt': row['issued_at'],
        'officialAddress': row['official_address'] or None,
        'place': place_line(a) if a else None,
        'entrance': {'lat': lat, 'lng': lng, 'kind': row['entrance_kind']},
        'spotCode': row['spot_code'],
        'plusCode': plus_code(lat, lng),
        'area': area_json(eng, a) if a else None,
        'zone': {'key': row['unit'], 'name': zone_name(eng, row['unit'])},
        'building': {'class': row['class_'] or None, 'use': row['use_'] or None, 'kind': row['kind'] or None,
                     'structures': int(row['structures'] or 0), 'floorAreaM2': float(row['floor_area_m2'] or 0),
                     'rule': row['rule'] or None, 'estate': row['estate'] or None},
        'registry': registry_json(row),
        'credit': row_credit(),
    }


def brief(eng, row, d=None):
    out = {'machine': row['machine'], 'remembered': row['written'], 'status': row['status'],
           'entrance': {'lat': float(row['entrance_lat']), 'lng': float(row['entrance_lng']), 'kind': row['entrance_kind']},
           'spotCode': row['spot_code'], 'officialAddress': row['official_address'] or None, 'area': row['zone']}
    if d is not None:
        out['distanceM'] = round(d, 1)
    return out


def row_credit():
    return 'N-Ways Addressing for Togo, © N-WAYS LIMITED (nways.ng)'


_ZONE_NAMES = {}


def zone_name(eng, unit):
    if not _ZONE_NAMES:
        for a in eng.areas.areas:
            u = unit_of(a)
            if u not in _ZONE_NAMES and a.get('prefecture'):
                _ZONE_NAMES[u] = prefecture_name(a['prefecture'])
    return _ZONE_NAMES.get(unit, unit)


def zone_region(eng, unit):
    for a in eng.areas.areas:
        if unit_of(a) == unit and a.get('region'):
            return a['region']
    return 'Maritime' if unit == 'LOM' else None


# ---------------------------------------------------------------- the application
class App:
    def __init__(self, db, keys=(), per_day=5, cors=()):
        self.db = db
        self.keys = [k for k in keys if k]
        self.per_day = per_day
        self.cors = list(cors)
        self.engine = Engine()
        st = S.Store(db, readonly=True)
        try:
            self.engine.sync_blocks(st.blocks_by_zone())
            st.meta()
        finally:
            st.close()
        self.routes = [
            ('GET', r'/v1/health', self.health),
            ('GET', r'/v1/info', self.info),
            ('GET', r'/v1/find', self.find),
            ('GET', r'/v1/at', self.at),
            ('GET', r'/v1/near', self.near),
            ('GET', r'/v1/verify', self.verify),
            ('GET', r'/v1/spot', self.spot),
            ('GET', r'/v1/spot/decode', self.spot_decode),
            ('GET', r'/v1/zones', self.zones),
            ('GET', r'/v1/zones/(?P<key>[^/]+)', self.zone),
            ('GET', r'/v1/zones/(?P<key>[^/]+)/codes', self.zone_codes),
            ('GET', r'/v1/areas', self.areas_search),
            ('GET', r'/v1/areas/(?P<key>[^/]+)', self.area),
            ('GET', r'/v1/codes/(?P<machine>[^/]+)', self.code),
            ('POST', r'/v1/codes', self.issue),
            ('PATCH', r'/v1/codes/(?P<machine>[^/]+)', self.change),
        ]
        self.routes = [(m, re.compile(p + r'/?$'), f) for m, p, f in self.routes]

    # -------------------------------------------------------------- dispatch
    def handle(self, method, path, query, headers, body):
        """Returns (status, payload, extra headers)."""
        allowed = [m for m, rx, _ in self.routes if rx.match(path)]
        for m, rx, fn in self.routes:
            mt = rx.match(path)
            if mt and m == method:
                st = S.Store(self.db, readonly=(method == 'GET'))
                try:
                    out = fn(st, query=query, headers=headers, body=body, **{k: unquote(v) for k, v in mt.groupdict().items()})
                finally:
                    st.close()
                if isinstance(out, tuple):
                    return out[0], out[1], {}
                return 200, out, {}
        if allowed:
            raise ApiError(405, 'method_not_allowed', '%s is not allowed on %s; use %s.' % (method, path, ', '.join(sorted(set(allowed)))),
                           {'Allow': ', '.join(sorted(set(allowed)))})
        raise ApiError(404, 'not_found', 'No endpoint %s. See /v1/info and docs/api.md.' % path)

    # -------------------------------------------------------------- helpers
    @staticmethod
    def _q(query, name, required=True):
        v = query.get(name, [None])[0]
        if v is not None:
            v = v.strip()
        if required and not v:
            raise ApiError(400, 'bad_request', 'The query parameter %s is required.' % name)
        return v

    def _float(self, query, name, lo, hi, default=None):
        v = self._q(query, name, required=default is None)
        if v is None or v == '':
            return default
        try:
            x = float(v)
        except ValueError:
            raise ApiError(400, 'bad_request', '%s must be a number, not %r.' % (name, v))
        if not (lo <= x <= hi) or x != x:
            raise ApiError(400, 'bad_request', '%s must be between %g and %g.' % (name, lo, hi))
        return x

    def _int(self, query, name, lo, hi, default):
        v = self._q(query, name, required=False)
        if not v:
            return default
        if not re.fullmatch(r'\d+', v):
            raise ApiError(400, 'bad_request', '%s must be a whole number.' % name)
        x = int(v)
        if not (lo <= x <= hi):
            raise ApiError(400, 'bad_request', '%s must be between %d and %d.' % (name, lo, hi))
        return x

    def _key(self, headers):
        if not self.keys:
            raise ApiError(403, 'read_only', 'This deployment is read-only: it does not issue or change codes. '
                                             'Only the issuer the State or N-WAYS LIMITED has designated does.')
        auth = headers.get('Authorization') or ''
        m = re.match(r'Bearer\s+(\S+)$', auth.strip())
        if not m:
            raise ApiError(401, 'unauthorized', 'Send the issuing key as "Authorization: Bearer <key>".', {'WWW-Authenticate': 'Bearer'})
        got = m.group(1).encode('utf-8')
        for k in self.keys:
            if hmac.compare_digest(got, k.encode('utf-8')):
                return 'key:' + hashlib.sha256(k.encode('utf-8')).hexdigest()[:16]
        raise ApiError(401, 'unauthorized', 'That key is not one of this deployment\'s issuing keys.', {'WWW-Authenticate': 'Bearer'})

    @staticmethod
    def _json(body):
        if not body:
            raise ApiError(400, 'bad_request', 'The request needs a JSON body.')
        try:
            return json.loads(body.decode('utf-8'))
        except (ValueError, UnicodeDecodeError):
            raise ApiError(400, 'bad_request', 'The body is not valid JSON.')

    def _machine(self, text):
        """The canonical machine form of `text`, refusing a wrong check digit or a number in no block."""
        t = text.strip()
        if not re.fullmatch(r'TG-[A-Z0-9]+-\d{4,5}-\d(?:\.\d+)?(?:/\d+)?', E.plain(t).upper()):
            raise ApiError(400, 'bad_code', '%r is not a machine code; it looks like TG-FRJ-1058-2.' % text)
        try:
            p = self.engine.parse(t)
        except ValueError as e:
            code = _parse_error_code(str(e))
            if code == 'check_digit':
                raise ApiError(400, code, 'The check digit of %s does not match: the code was mistyped.' % t)
            raise ApiError(400, code, _sentence(str(e)))
        return 'TG-%s-%d-%d' % (p['area'], p['number'], E.check_digit(self.engine.area(p['area']), p['number']))

    # -------------------------------------------------------------- endpoints
    def health(self, st, **_):
        man = st.manifest()
        return {'status': 'ok', 'country': COUNTRY, 'codes': st.count(), 'registryExported': man.get('exported'),
                'changedSinceImport': st.meta().get('changed') == '1', 'issuing': bool(self.keys)}

    def info(self, st, **_):
        man = st.manifest()
        by_unit = st.counts_by_unit()
        zones = [{'key': u, 'name': zone_name(self.engine, u), 'region': zone_region(self.engine, u), 'codes': n}
                 for u, n in sorted(by_unit.items())]
        areas = self.engine.areas.areas
        return {'country': COUNTRY, 'name': COUNTRY_NAME, 'api': API_VERSION, 'engine': man.get('engine'), 'spec': SPEC,
                'registryExported': man.get('exported'), 'importedAt': st.meta().get('imported_at'),
                'counts': {'codes': st.count(), 'byStatus': st.counts_by_status(), 'zones': len(zones),
                           'areas': len(areas), 'numberedAreas': sum(1 for a in areas if numbered(a))},
                'zones': zones, 'licences': LICENCES, 'credit': row_credit(), 'creditUrl': CREDIT_URL,
                'issuing': bool(self.keys), 'issuePerDay': self.per_day if self.keys else 0,
                'forms': {'remembered': 'Fréau-Jardin 10 58', 'machine': 'TG-FRJ-1058-2', 'spot': 'FRJ-54-4R'}}

    def code(self, st, machine, **_):
        m = self._machine(machine)
        r = st.by_machine(m)
        if r is None:
            raise ApiError(404, 'not_issued', '%s is a valid code, but no compound has it.' % m)
        return card(self.engine, r)

    def find(self, st, query, **_):
        q = ' '.join(self._q(query, 'q').split())
        if len(q) > 200:
            raise ApiError(400, 'bad_request', 'q is at most 200 characters.')
        u = E.plain(q).upper()
        # 1. machine form
        if re.fullmatch(r'TG-[A-Z0-9]+-\d{4,5}-\d(?:\.\d+)?(?:/\d+)?', u):
            m = self._machine(q)
            r = st.by_machine(m)
            if r is None:
                raise ApiError(404, 'not_issued', '%s is a valid code, but no compound has it.' % m)
            return {'query': q, 'kind': 'machine', 'count': 1, 'results': [card(self.engine, r)]}
        err = ''
        try:
            p = self.engine.parse(q)
        except ValueError as e:
            p, err = None, str(e)
        if p and p['kind'] == 'spot':
            near = st.nearest(p['lat'], p['lon'], SPOT_ON_HOME_M)
            if near is None:
                raise ApiError(404, 'not_found', 'The spot %s is not on a compound with a code (nothing within %d m of %.6f, %.6f).'
                               % (q, SPOT_ON_HOME_M, p['lat'], p['lon']), {'point': {'lat': round(p['lat'], 7), 'lng': round(p['lon'], 7)}})
            return {'query': q, 'kind': 'spot', 'point': {'lat': round(p['lat'], 7), 'lng': round(p['lon'], 7)}, 'count': 1,
                    'results': [dict(card(self.engine, near[1]), distanceM=round(near[0], 1))]}
        if p and p['kind'] == 'compound':
            r = st.by_zone_number(p['area'], p['number'])
            a = self.engine.area(p['area'])
            if r is None:
                raise ApiError(404, 'not_issued', '%s %s is in the range of %s (%s), but no compound has it yet.'
                               % (a['name'], E.pairs(p['number']), a['name'], place_line(a)))
            return {'query': q, 'kind': 'remembered', 'count': 1, 'results': [card(self.engine, r)]}
        # official address (Grand Lomé streets) or a street code
        key = S.official_key(q)
        if key:
            n = st.count_official(key)
            if n:
                rows = st.by_official(key, 100)
                return {'query': q, 'kind': 'official', 'count': n, 'results': [card(self.engine, r) for r in rows]}
        if p and p['kind'] == 'lome-street-code':
            raise ApiError(404, 'street_code', '%s is a Lomé street code (street %d of quartier %s), not an N-Ways code. '
                           'Search the full official address, such as "Rue 89 AFG", or find the building with /v1/at.'
                           % (q, p['street'], p['quartier']))
        if 'check digit' in err:
            raise ApiError(400, 'check_digit', 'The check digit of %s does not match: the code was mistyped.' % q)
        if err.startswith('unknown place'):
            raise ApiError(404, 'unknown_name', 'No code area of Togo is called %s, and no official address matches %r.'
                           % (err.split(' ', 2)[2], q))
        if err.startswith('no N-Ways address'):
            raise ApiError(404, 'not_in_blocks', _sentence(err))
        raise ApiError(400, 'bad_query', 'Give a code as people say it ("Fréau-Jardin 10 58"), a machine code ("TG-FRJ-1058-2"), '
                       'a spot code ("FRJ-54-4R") or an official address ("Rue Mission Tové").')

    def at(self, st, query, **_):
        lat = self._float(query, 'lat', -90, 90)
        lng = self._float(query, 'lng', -180, 180)
        if not self.engine.in_country(lat, lng):
            raise ApiError(404, 'outside', 'The point %.6f, %.6f is outside Togo.' % (lat, lng))
        new = I.place_for(st, self.engine, lat, lng)
        # a point in a gap between outlines has no containing area: it takes the one a new code would
        a = self.engine.area_at(lat, lng) or new
        near = st.nearest(lat, lng, AT_M)
        if near is not None:
            return {'status': 'found', 'distanceM': round(near[0], 1), 'code': card(self.engine, near[1]),
                    'area': area_json(self.engine, a)}
        if not self.engine.in_border(lat, lng):
            new = None      # across the national border: no code can be issued here
        return {'status': 'none', 'area': area_json(self.engine, a), 'newCodeArea': new['key'] if new else None,
                'spotCode': self.engine.spot(lat, lng)}

    def near(self, st, query, **_):
        lat = self._float(query, 'lat', -90, 90)
        lng = self._float(query, 'lng', -180, 180)
        radius = self._float(query, 'radius', 1, NEAR_MAX_M, default=100.0)
        limit = self._int(query, 'limit', 1, NEAR_MAX_N, NEAR_MAX_N)
        hits = []
        for r in st.in_box(lat, lng, radius):
            d = dist_m(lat, lng, r['lat'], r['lng'])
            if d <= radius:
                hits.append((d, r['machine'], r))
        hits.sort(key=lambda x: (x[0], x[1]))
        return {'point': {'lat': lat, 'lng': lng}, 'radiusM': radius, 'count': min(len(hits), limit), 'more': len(hits) > limit,
                'results': [brief(self.engine, r, d) for d, _, r in hits[:limit]]}

    def verify(self, st, query, **_):
        code = self._q(query, 'code')
        u = E.plain(code).upper().replace(' ', '')
        out = {'code': code, 'syntax': False, 'checkDigit': None, 'inBlocks': None, 'issued': False, 'status': None, 'machine': None}
        m = re.fullmatch(r'TG-([A-Z0-9]+)-(\d{4,5})-(\d)(?:\.\d+)?(?:/\d+)?', u)
        if not m:
            out['reason'] = 'not a machine code (TG-<area>-<number>-<check>)'
            return out
        out['syntax'] = True
        a = self.engine.area(m.group(1))
        if a is None or not numbered(a):
            out['reason'] = 'no code area %s' % m.group(1)
            return out
        n = int(m.group(2))
        want = E.check_digit(a, n)
        out['checkDigit'] = want == int(m.group(3))
        out['inBlocks'] = E.block_of(a, n) is not None
        if not out['checkDigit']:
            out['reason'] = 'the check digit does not match: a mistyped code'
            return out
        if not out['inBlocks']:
            out['reason'] = '%s has no number %d' % (a['key'], n)
            return out
        out['machine'] = 'TG-%s-%d-%d' % (a['key'], n, want)
        r = st.by_machine(out['machine'])
        if r is not None:
            out.update({'issued': True, 'status': r['status'], 'remembered': r['written']})
        else:
            out['reason'] = 'valid, but not issued'
        return out

    def spot(self, st, query, **_):
        lat = self._float(query, 'lat', -90, 90)
        lng = self._float(query, 'lng', -180, 180)
        try:
            code = self.engine.spot(lat, lng)
        except ValueError:
            raise ApiError(404, 'outside', 'The point %.6f, %.6f is outside Togo.' % (lat, lng))
        clat, clng, cell = self.engine.spot_point(code)
        return {'spotCode': code, 'point': {'lat': lat, 'lng': lng}, 'centre': {'lat': round(clat, 7), 'lng': round(clng, 7)},
                'cellM': [round(cell[0], 2), round(cell[1], 2)], 'area': code.split('-')[0]}

    def spot_decode(self, st, query, **_):
        code = self._q(query, 'code')
        try:
            lat, lng, cell = self.engine.spot_point(code)
        except ValueError as e:
            raise ApiError(400, 'bad_code', _sentence(str(e)))
        a = self.engine.area(code.strip().upper().replace('TG-', '', 1).split('-')[0])
        return {'spotCode': code.strip().upper(), 'centre': {'lat': round(lat, 7), 'lng': round(lng, 7)},
                'cellM': [round(cell[0], 2), round(cell[1], 2)], 'frame': area_json(self.engine, a)}

    def zones(self, st, **_):
        by_unit = st.counts_by_unit()
        areas = {}
        for a in self.engine.areas.areas:
            areas.setdefault(unit_of(a), []).append(a)
        return {'count': len(areas), 'zones': [
            {'key': u, 'name': zone_name(self.engine, u), 'region': zone_region(self.engine, u), 'codes': by_unit.get(u, 0),
             'areas': len(areas[u]), 'numberedAreas': sum(1 for a in areas[u] if numbered(a))} for u in sorted(areas)]}

    def _zone_areas(self, key):
        k = key.upper()
        out = [a for a in self.engine.areas.areas if unit_of(a) == k]
        if not out:
            raise ApiError(404, 'not_found', 'No zone %s. /v1/zones lists them.' % key)
        return k, out

    def zone(self, st, key, **_):
        k, areas = self._zone_areas(key)
        counts = st.counts_by_zone(k)
        return {'key': k, 'name': zone_name(self.engine, k), 'region': zone_region(self.engine, k), 'codes': sum(counts.values()),
                'areas': [area_json(self.engine, a, counts) for a in sorted(areas, key=lambda a: a['index'])]}

    def zone_codes(self, st, key, query, **_):
        k, _ = self._zone_areas(key)
        after = self._q(query, 'after', required=False) or ''
        limit = self._int(query, 'limit', 1, PAGE_MAX, 100)
        rows = st.zone_page(k, after, limit + 1)
        more = len(rows) > limit
        rows = rows[:limit]
        return {'zone': k, 'after': after or None, 'limit': limit, 'count': len(rows),
                'next': rows[-1]['machine'] if more else None, 'results': [registry_json(r) for r in rows]}

    def area(self, st, key, **_):
        a = self.engine.area(key.upper()) if not key.isdigit() else self.engine.area_by_index(int(key))
        if a is None:
            raise ApiError(404, 'not_found', 'No code area %s. Search one by name with /v1/areas?name=.' % key)
        out = area_json(self.engine, a)
        out['codes'] = st.count('WHERE zone = ?', (a['key'],))
        out['byStatus'] = dict(st.con.execute('SELECT status, count(*) FROM codes WHERE zone = ? GROUP BY status', (a['key'],)).fetchall())
        if numbered(a):
            used = [r[0] for r in st.con.execute('SELECT num FROM codes WHERE zone = ? ORDER BY num', (a['key'],))]
            out['numbers'] = {'lowest': used[0] if used else None, 'highest': used[-1] if used else None,
                              'tailReserveFrom': E.tail_start(a), 'free': sum(hi - lo + 1 for lo, hi in a['blocks']) - len(used)}
        return out

    def areas_search(self, st, query, **_):
        name = self._q(query, 'name')
        found = self.engine.by_name(name)
        exact = True
        if not found:
            k = E.name_key(name)
            if len(k) >= 3:
                found = [a for a in self.engine.areas.areas if E.name_key(a['name']).startswith(k)
                         or E.name_key(a.get('officialName') or '').startswith(k)][:50]
                exact = False
        counts = st.counts_by_zone()
        return {'name': name, 'nameKey': E.name_key(name), 'match': 'name' if exact else 'prefix', 'count': len(found),
                'results': [area_json(self.engine, a, counts) for a in sorted(found, key=lambda a: a['index'])]}

    def issue(self, st, headers, body, **_):
        who = self._key(headers)
        data = self._json(body)
        try:
            row = I.issue(st, self.engine, who, data, self.per_day, card=lambda r: card(self.engine, r))
        except I.Refused as e:
            raise ApiError(e.status, e.code, e.message, {'existing': e.card} if e.card else None)
        return 201, card(self.engine, row)

    def change(self, st, machine, headers, body, **_):
        self._key(headers)
        m = self._machine(machine)
        data = self._json(body)
        try:
            row = I.change(st, self.engine, m, data)
        except I.Refused as e:
            raise ApiError(e.status, e.code, e.message)
        return card(self.engine, row)


def _sentence(s):
    s = s.strip()
    return (s[:1].upper() + s[1:]).rstrip('.') + '.'


def _parse_error_code(msg):
    if 'check digit' in msg:
        return 'check_digit'
    if 'has no number' in msg:
        return 'not_in_blocks'
    if 'unknown area' in msg or 'not a numbered area' in msg:
        return 'unknown_area'
    return 'bad_code'


# ---------------------------------------------------------------- HTTP
class Handler(BaseHTTPRequestHandler):
    app = None
    server_version = 'n-ways-addresses-tg'
    sys_version = ''
    protocol_version = 'HTTP/1.1'

    def _send(self, status, payload, extra=None):
        body = json.dumps(payload, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store' if self.command != 'GET' else 'public, max-age=60')
        self.send_header('X-Content-Type-Options', 'nosniff')
        origin = self.headers.get('Origin')
        cors = self.app.cors
        if origin and ('*' in cors or origin in cors):
            self.send_header('Access-Control-Allow-Origin', '*' if '*' in cors else origin)
            self.send_header('Vary', 'Origin')
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != 'HEAD':
            self.wfile.write(body)

    def _run(self):
        started = time.time()
        status = 500
        try:
            parts = urlsplit(self.path)
            n = int(self.headers.get('Content-Length') or 0)
            if n > BODY_MAX:
                raise ApiError(413, 'too_large', 'The body is over %d bytes.' % BODY_MAX)
            body = self.rfile.read(n) if n else b''
            method = 'GET' if self.command == 'HEAD' else self.command
            status, payload, extra = self.app.handle(method, parts.path, parse_qs(parts.query, keep_blank_values=True),
                                                     self.headers, body)
            self._send(status, payload, extra)
        except ApiError as e:
            status = e.status
            payload = {'error': {'code': e.code, 'message': e.message}}
            headers = {}
            if e.extra:
                for k, v in e.extra.items():
                    if k[:1].isupper():
                        headers[k] = v
                    else:
                        payload['error'][k] = v
            self._send(status, payload, headers)
        except Exception:
            traceback.print_exc(file=sys.stderr)
            status = 500
            self._send(500, {'error': {'code': 'internal', 'message': 'Something went wrong on the server. It has been logged.'}})
        finally:
            sys.stderr.write('%s %s %s %d %.0fms\n' % (self.log_date_time_string(), self.command, self.path.split('?')[0], status,
                                                      (time.time() - started) * 1000))

    do_GET = do_POST = do_PATCH = do_PUT = do_DELETE = do_HEAD = _run

    def do_OPTIONS(self):
        origin = self.headers.get('Origin')
        cors = self.app.cors
        self.send_response(204)
        if origin and ('*' in cors or origin in cors):
            self.send_header('Access-Control-Allow-Origin', '*' if '*' in cors else origin)
            self.send_header('Access-Control-Allow-Methods', 'GET, POST, PATCH, OPTIONS')
            self.send_header('Access-Control-Allow-Headers', 'Authorization, Content-Type')
            self.send_header('Access-Control-Max-Age', '86400')
            self.send_header('Vary', 'Origin')
        self.send_header('Content-Length', '0')
        self.end_headers()

    def log_message(self, fmt, *args):
        pass


def serve(app, host, port):
    handler = type('H', (Handler,), {'app': app})
    httpd = ThreadingHTTPServer((host, port), handler)
    httpd.daemon_threads = True
    sys.stderr.write('N-Ways Addressing for Togo: serving %s on http://%s:%d/v1 (%s)\n'
                     % (app.db, host, port, 'issuing' if app.keys else 'read-only'))
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
