#!/usr/bin/env python3
"""Tests for the registry server. Standard library only, offline, on the fixture registry
(server/testdata/registry: the area table, every code of Plaine du Mô, and 24 compounds in no zone outline).

    python3 -m unittest server.test_server        (from the repository root)
    python3 server/test_server.py
"""
import gzip
import hashlib
import json
import os
import shutil
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from server import store as S  # noqa: E402
from server import issue as I  # noqa: E402
from server.api import App, ApiError, Handler  # noqa: E402
from server.engine import E  # noqa: E402

FIXTURE = os.path.join(HERE, 'testdata', 'registry')
GAP_UNITS = ('ANI', 'BMO', 'CIN', 'KPD', 'MMO')    # fixture files of issued compounds in no zone outline
CODES = 10072 + 24
PARITY = E.load_json(os.path.join(HERE, 'testdata', 'parity.json'))
KEY = 'test-key-1'


def _text(path):
    with open(path, encoding='utf-8') as f:
        return f.read()


def _rows(path):
    with gzip.open(path, 'rt', encoding='utf-8', newline='') as f:
        return f.read()


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix='tg-server-')
        cls.db = os.path.join(cls.tmp, 'addresses.sqlite')
        S.import_registry(FIXTURE, cls.db, log=lambda m: None)
        cls.app = App(cls.db, keys=[KEY], per_day=1000)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp)

    def get(self, path, **q):
        from urllib.parse import parse_qs, urlencode
        query = parse_qs(urlencode(q), keep_blank_values=True)
        return self.call('GET', path, query=query)

    def call(self, method, path, query=None, body=None, key=KEY):
        headers = {'Authorization': 'Bearer ' + key} if key else {}
        raw = json.dumps(body).encode('utf-8') if body is not None else b''
        try:
            status, payload, _ = self.app.handle(method, path, query or {}, headers, raw)
            return status, payload
        except ApiError as e:
            err = {'code': e.code, 'message': e.message}
            for k, v in (e.extra or {}).items():
                if not k[:1].isupper():
                    err[k] = v
            return e.status, {'error': err}

    def assertError(self, res, status, code):
        self.assertEqual(res[0], status, res)
        self.assertEqual(res[1]['error']['code'], code, res)
        self.assertTrue(res[1]['error']['message'])


class ImportExport(Base):
    def test_round_trip_is_byte_identical(self):
        out = os.path.join(self.tmp, 'export')
        con = S.connect(self.db, readonly=True)
        man = S.export_registry(con, out, log=lambda m: None)
        con.close()
        for name in ('areas.csv.gz', 'PMO.csv.gz') + tuple(u + '.csv.gz' for u in GAP_UNITS):
            self.assertEqual(_rows(os.path.join(FIXTURE, name)), _rows(os.path.join(out, name)), name)
        with open(os.path.join(FIXTURE, 'MANIFEST.json'), encoding='utf-8') as f:
            self.assertEqual(f.read(), _text(os.path.join(out, 'MANIFEST.json')))
        self.assertEqual(man['codes'], CODES)
        with gzip.open(os.path.join(out, 'PMO.csv.gz'), 'rb') as f:
            self.assertEqual(hashlib.sha256(f.read()).hexdigest(), man['sha256']['PMO.csv'])

    def test_a_changed_file_is_refused_and_the_database_kept(self):
        bad = os.path.join(self.tmp, 'bad')
        shutil.copytree(FIXTURE, bad)
        raw = _rows(os.path.join(bad, 'PMO.csv.gz')).replace('Boulohou 10 00', 'Boulohou 10 01', 1)
        with gzip.open(os.path.join(bad, 'PMO.csv.gz'), 'wt', encoding='utf-8', newline='') as f:
            f.write(raw)
        before = os.path.getmtime(self.db)
        with self.assertRaises(S.RegistryError) as e:
            S.import_registry(bad, self.db, log=lambda m: None)
        self.assertIn('SHA-256', str(e.exception))
        self.assertEqual(before, os.path.getmtime(self.db))
        self.assertFalse(os.path.exists(self.db + '.importing'))

    def test_a_wrong_count_is_refused(self):
        bad = os.path.join(self.tmp, 'badcount')
        shutil.copytree(FIXTURE, bad)
        man = E.load_json(os.path.join(bad, 'MANIFEST.json'))
        man['codes'] += 1
        man['byUnit']['PMO'] += 1
        with open(os.path.join(bad, 'MANIFEST.json'), 'w', encoding='utf-8') as f:
            json.dump(man, f)
        with self.assertRaises(S.RegistryError):
            S.import_registry(bad, os.path.join(self.tmp, 'other.sqlite'), log=lambda m: None)

    def test_reimport_is_safe_and_keeps_local_work(self):
        db = os.path.join(self.tmp, 'again.sqlite')
        S.import_registry(FIXTURE, db, log=lambda m: None)
        app = App(db, keys=[KEY], per_day=10)
        st = S.Store(db)
        row = I.issue(st, app.engine, 'key:x', {'lat': 8.80, 'lng': 0.70}, 10)
        I.change(st, app.engine, 'TG-PMO01-1000-7', {'status': 'confirmed'})
        st.close()
        rep = S.import_registry(FIXTURE, db, log=lambda m: None)
        self.assertEqual(rep['carriedOver'], {'issued': 1, 'changed': 1, 'conflicts': []})
        st = S.Store(db, readonly=True)
        self.assertIsNotNone(st.by_machine(row['machine']))
        self.assertEqual(st.by_machine('TG-PMO01-1000-7')['status'], 'confirmed')
        self.assertEqual(st.count(), CODES + 1)
        st.close()


class Reads(Base):
    def test_health_and_info(self):
        s, h = self.get('/v1/health')
        self.assertEqual((s, h['status'], h['country'], h['registryExported']), (200, 'ok', 'TG', '2026-10-20T16:41:57Z'))
        s, i = self.get('/v1/info')
        self.assertEqual([z['key'] for z in i['zones']], sorted(('PMO',) + GAP_UNITS))
        self.assertEqual(i['counts']['areas'], 1537)
        self.assertEqual(i['licences']['data'], 'ODbL-1.0')

    def test_card_has_every_registry_column(self):
        s, c = self.get('/v1/codes/TG-PMO01-1000-7')
        self.assertEqual(s, 200)
        self.assertEqual(list(c['registry']), S.CODE_COLUMNS)
        self.assertEqual(c['remembered'], 'Boulohou 10 00')
        self.assertEqual(c['area']['key'], 'PMO01')
        self.assertEqual(c['zone'], {'key': 'PMO', 'name': 'Plaine du Mô'})
        self.assertEqual(c['spotCode'], c['registry']['spot_code'])
        self.assertNotIn('-', c['remembered'].split(' ', 1)[1])   # people never see the check digit

    def test_card_errors(self):
        self.assertError(self.get('/v1/codes/TG-PMO01-1000-0'), 400, 'check_digit')
        self.assertError(self.get('/v1/codes/hello'), 400, 'bad_code')
        self.assertError(self.get('/v1/codes/TG-PMO01-3399-%d' % self._check('PMO01', 3399)), 404, 'not_issued')
        self.assertError(self.get('/v1/codes/TG-PMO01-9000-0'), 400, 'not_in_blocks')

    def _check(self, area, n):
        return E.check_digit(self.app.engine.area(area), n)

    def test_find_every_form(self):
        for q in ('Boulohou 10 00', 'boulohou 1000', 'BOULOHOU   10 00', 'Boulôhou 10 00', 'Boulohou 10.00', ' boulohou 10  00 ', 'TG-PMO01-1000-7', 'tg-pmo01-1000-7'):
            s, f = self.get('/v1/find', q=q)
            self.assertEqual((s, f['results'][0]['machine']), (200, 'TG-PMO01-1000-7'), q)
        s, f = self.get('/v1/find', q='PMO01-64M-RWM')
        self.assertEqual((s, f['kind'], f['results'][0]['machine']), (200, 'spot', 'TG-PMO01-1000-7'))

    def test_find_refuses(self):
        self.assertError(self.get('/v1/find', q='TG-PMO01-1000-8'), 400, 'check_digit')
        self.assertError(self.get('/v1/find', q='Nowhereville 10 00'), 404, 'unknown_name')
        self.assertError(self.get('/v1/find', q='Boulohou 99 99'), 404, 'not_in_blocks')
        self.assertError(self.get('/v1/find', q='Boulohou 33 99'), 404, 'not_issued')
        self.assertError(self.get('/v1/find', q='165 AMT'), 404, 'street_code')
        self.assertError(self.get('/v1/find', q='?'), 400, 'bad_query')
        self.assertError(self.get('/v1/find'), 400, 'bad_request')

    def test_at_and_near(self):
        s, a = self.get('/v1/at', lat='8.6292149', lng='0.6107818')
        self.assertEqual((s, a['status'], a['code']['machine'], a['distanceM']), (200, 'found', 'TG-PMO01-1000-7', 0.0))
        s, a = self.get('/v1/at', lat='8.80', lng='0.70')
        self.assertEqual((a['status'], a['area']['key']), ('none', 'PMO03'))
        self.assertError(self.get('/v1/at', lat='48.85', lng='2.35'), 404, 'outside')
        self.assertError(self.get('/v1/at', lat='x', lng='2'), 400, 'bad_request')
        s, n = self.get('/v1/near', lat='8.6292149', lng='0.6107818', radius='100', limit='5')
        self.assertEqual(n['results'][0]['machine'], 'TG-PMO01-1000-7')
        self.assertLessEqual(len(n['results']), 5)
        self.assertEqual([r['distanceM'] for r in n['results']], sorted(r['distanceM'] for r in n['results']))
        self.assertError(self.get('/v1/near', lat='8.6', lng='0.6', radius='501'), 400, 'bad_request')
        self.assertError(self.get('/v1/near', lat='8.6', lng='0.6', limit='101'), 400, 'bad_request')

    def test_verify(self):
        s, v = self.get('/v1/verify', code='TG-PMO01-1000-7')
        self.assertEqual((v['syntax'], v['checkDigit'], v['issued'], v['status']), (True, True, True, 'provisional'))
        s, v = self.get('/v1/verify', code='TG-PMO01-1000-1')
        self.assertEqual((v['checkDigit'], v['issued']), (False, False))
        s, v = self.get('/v1/verify', code='Boulohou 10 00')
        self.assertFalse(v['syntax'])
        self.assertError(self.get('/v1/verify'), 400, 'bad_request')

    def test_spot(self):
        s, p = self.get('/v1/spot', lat='6.1317765', lng='1.2234008')
        self.assertEqual(p['spotCode'], 'FRJ-54-4R')
        s, d = self.get('/v1/spot/decode', code='FRJ-54-4R')
        self.assertAlmostEqual(d['centre']['lat'], 6.1317765, places=4)
        self.assertError(self.get('/v1/spot/decode', code='FRJ-11-11'), 400, 'bad_code')
        self.assertError(self.get('/v1/spot', lat='0', lng='0'), 404, 'outside')
        # in no outline, beyond every frame: the nearest frame's edge cell (SPEC 5)
        s, p = self.get('/v1/spot', lat='7.1155382', lng='0.5922799')
        self.assertEqual((s, p['spotCode'], p['area']), (200, 'DNY05-32M-232', 'DNY05'))
        s, d = self.get('/v1/spot/decode', code='DNY05-32M-232')
        self.assertEqual((d['centre']['lat'], d['centre']['lng']), (7.1155243, 0.5976715))

    def test_zones_and_areas(self):
        s, z = self.get('/v1/zones')
        self.assertEqual(z['count'], 40)
        s, z = self.get('/v1/zones/PMO')
        self.assertEqual([a['key'] for a in z['areas']], ['PMO01', 'PMO02', 'PMO03', 'PMO04', 'PMO05'])
        self.assertEqual(sum(a['codes'] for a in z['areas']), 10072)
        self.assertError(self.get('/v1/zones/XYZ'), 404, 'not_found')
        s, a = self.get('/v1/areas/PMO01')
        self.assertEqual((a['plateName'], a['codes']), ('Boulohou', 1198))
        self.assertError(self.get('/v1/areas/NOPE'), 404, 'not_found')
        s, f = self.get('/v1/areas', name='Démakpoè')
        self.assertTrue(f['count'] >= 1)
        s, f = self.get('/v1/areas', name='Agoè-Démakpoè')     # the official name finds the plate name's area
        self.assertTrue(f['count'] >= 1)
        self.assertError(self.get('/v1/areas'), 400, 'bad_request')

    def test_paging(self):
        seen, after = [], ''
        while True:
            s, p = self.get('/v1/zones/PMO/codes', after=after, limit='1000')
            seen += [r['machine'] for r in p['results']]
            if not p['next']:
                break
            after = p['next']
        self.assertEqual(len(seen), 10072)
        self.assertEqual(seen, sorted(seen))
        self.assertError(self.get('/v1/zones/PMO/codes', limit='5000'), 400, 'bad_request')

    def test_unknown_endpoint_and_method(self):
        self.assertError(self.get('/v1/nothing'), 404, 'not_found')
        self.assertError(self.call('DELETE', '/v1/codes/TG-PMO01-1000-7'), 405, 'method_not_allowed')


class Issuing(Base):
    """Parity with the N-Ways issuer, cases in order (each sees the codes issued before it)."""

    def test_1_parity_with_the_issuer(self):
        for c in PARITY['cases']:
            body = {'lat': c['lat'], 'lng': c['lng']}
            if c.get('of'):
                body['of'] = c['of']
            s, card = self.call('POST', '/v1/codes', body=body)
            self.assertEqual(s, 201, (c['name'], card))
            self.assertEqual((card['area']['key'], card['number'], card['machine'], card['home'], card['remembered'], card['spotCode']),
                             (c['area'], c['number'], c['machine'], c['home'], c['remembered'], c['spot']), c['name'])
            self.assertEqual((card['status'], card['issued']), ('provisional', 'on-demand'))
            self.assertEqual(card['entrance']['kind'], 'door' if c.get('of') else 'centre')

    def test_2_extension_block(self):
        fill = PARITY['fill']
        st = S.Store(self.db)
        eng = self.app.engine
        a = eng.area(fill['area'])
        lo, hi = a['blocks'][0]
        with st.write():
            for n in range(lo, hi + 1):
                row = I._row(st, eng, a, n, eng.forms(a, n), a['point'][1], a['point'][0], 'centre', 0, 'fill', time.time(), None)
                row['local'] = None
                st.con.execute('INSERT INTO codes (%s) VALUES (%s)' % (', '.join(row), ', '.join('?' * len(row))), list(row.values()))
                st.con.execute('INSERT INTO codes_geo VALUES (last_insert_rowid(), ?, ?, ?, ?)', (row['lat'], row['lat'], row['lng'], row['lng']))
        st.close()
        for c in fill['issues']:
            s, card = self.call('POST', '/v1/codes', body={'lat': c['lat'], 'lng': c['lng']})
            self.assertEqual((s, card['machine'], card['remembered']), (201, c['machine'], c['remembered']), c['name'])
        s, area = self.get('/v1/areas/' + fill['area'])
        self.assertEqual(area['blocks'], [[lo, hi], fill['issues'][0]['newBlocks'][0]])
        out = os.path.join(self.tmp, 'export-blocks')
        con = S.connect(self.db, readonly=True)
        man = S.export_registry(con, out, log=lambda m: None)
        con.close()
        self.assertIn('%s,' % fill['area'], _rows(os.path.join(out, 'areas.csv.gz')))
        self.assertIn('1000-1199|2200-2699', _rows(os.path.join(out, 'areas.csv.gz')))
        self.assertIn(fill['issues'][1]['machine'], _rows(os.path.join(out, 'BLI.csv.gz')))
        self.assertNotEqual(man['exported'], '2026-10-20T16:41:57Z')

    def test_3_duplicates_are_refused(self):
        s, e = self.call('POST', '/v1/codes', body={'lat': 8.6292149, 'lng': 0.6107818})
        self.assertError((s, e), 409, 'exists')
        self.assertEqual(e['error']['existing']['machine'], 'TG-PMO01-1000-7')
        # an outline around an issued compound's point
        lat, lng = 8.6292149, 0.6107818
        d = 0.00008
        ring = [[lng - d, lat - d], [lng + d, lat - d], [lng + d, lat + d], [lng - d, lat + d], [lng - d, lat - d]]
        s, e = self.call('POST', '/v1/codes', body={'lat': lat + 0.00006, 'lng': lng, 'outline': ring})
        self.assertError((s, e), 409, 'exists')
        # a new building with its outline, then a second request inside that outline
        lat, lng = 8.79, 0.71
        ring = [[lng - d, lat - d], [lng + d, lat - d], [lng + d, lat + d], [lng - d, lat + d]]
        s, c = self.call('POST', '/v1/codes', body={'lat': lat, 'lng': lng, 'outline': ring})
        self.assertEqual(s, 201, c)
        self.assertEqual((c['building']['structures'], c['building']['class']), (1, 'residential'))
        self.assertGreater(c['building']['floorAreaM2'], 200)
        s, e = self.call('POST', '/v1/codes', body={'lat': lat + 0.00005, 'lng': lng + 0.00005})
        self.assertError((s, e), 409, 'exists')

    def test_4_refusals(self):
        tiny = [[0.62, 8.85], [0.62001, 8.85], [0.62001, 8.85001]]
        self.assertError(self.call('POST', '/v1/codes', body={'lat': 8.85, 'lng': 0.62, 'outline': tiny}), 422, 'bad_outline')
        self.assertError(self.call('POST', '/v1/codes', body={'lat': 48.85, 'lng': 2.35}), 422, 'outside')
        self.assertError(self.call('POST', '/v1/codes', body={'lat': 8.70, 'lng': 0.60, 'of': 'TG-PMO01-1000-7'}), 422, 'too_far')
        self.assertError(self.call('POST', '/v1/codes', body={'lat': 8.70, 'lng': 0.60, 'of': 'TG-PMO01-3399-0'}), 404, 'not_found')
        self.assertError(self.call('POST', '/v1/codes', body={'lat': 'x', 'lng': 0.6}), 400, 'bad_request')
        self.assertError(self.call('POST', '/v1/codes', body=None), 400, 'bad_request')
        self.assertError(self.call('POST', '/v1/codes', body={'lat': 8.7, 'lng': 0.6}, key=None), 401, 'unauthorized')
        self.assertError(self.call('POST', '/v1/codes', body={'lat': 8.7, 'lng': 0.6}, key='wrong'), 401, 'unauthorized')

    def test_5_daily_limit_and_read_only(self):
        app = App(self.db, keys=['k2'], per_day=1)
        st = S.Store(self.db)
        I.issue(st, app.engine, app._key({'Authorization': 'Bearer k2'}), {'lat': 8.62, 'lng': 0.52}, 1)
        st.close()
        try:
            app.handle('POST', '/v1/codes', {}, {'Authorization': 'Bearer k2'}, b'{"lat": 8.61, "lng": 0.46}')
            self.fail('no limit')
        except ApiError as e:
            self.assertEqual((e.status, e.code), (429, 'rate_limited'))
        ro = App(self.db, keys=[], per_day=5)
        with self.assertRaises(ApiError) as e:
            ro.handle('POST', '/v1/codes', {}, {}, b'{"lat": 8.61, "lng": 0.46}')
        self.assertEqual((e.exception.status, e.exception.code), (403, 'read_only'))

    def test_6_change_status_and_entrance(self):
        s, c = self.call('PATCH', '/v1/codes/TG-PMO01-1001-0', body={'status': 'confirmed'})
        self.assertEqual((s, c['status']), (200, 'confirmed'))
        s, c = self.call('PATCH', '/v1/codes/TG-PMO01-1001-0', body={'entrance': {'lat': 8.62935, 'lng': 0.61090}})
        self.assertEqual((c['entrance']['kind'], c['registry']['entrance_lat']), ('gate', '8.6293500'))
        self.assertError(self.call('PATCH', '/v1/codes/TG-PMO01-1001-0', body={'entrance': {'lat': 8.64, 'lng': 0.61}}), 422, 'too_far')
        self.assertError(self.call('PATCH', '/v1/codes/TG-PMO01-1001-0', body={'status': 'gone'}), 400, 'bad_request')
        s, c = self.call('PATCH', '/v1/codes/TG-PMO01-1001-0', body={'status': 'retired'})
        self.assertEqual(c['status'], 'retired')
        self.assertError(self.call('PATCH', '/v1/codes/TG-PMO01-1001-0', body={'status': 'confirmed'}), 409, 'retired')
        s, a = self.get('/v1/at', lat='8.62935', lng='0.61090')
        self.assertNotEqual(a.get('code', {}).get('machine'), 'TG-PMO01-1001-0')   # a retired code is never found by point
        self.assertError(self.call('PATCH', '/v1/codes/TG-PMO01-1001-1', body={'status': 'confirmed'}), 400, 'check_digit')


class Gaps(Base):
    """A compound in a gap between zone outlines is in Togo when the spot-code rule gives it a spot code
    (engine/SPEC.md 5): it is found by location, can be issued a code, and its entrance can move there."""

    def gap_rows(self):
        import csv
        rows = []
        for u in GAP_UNITS:
            with gzip.open(os.path.join(FIXTURE, u + '.csv.gz'), 'rt', encoding='utf-8', newline='') as f:
                rows += list(csv.DictReader(f))
        return rows

    def test_1_every_gap_compound_is_found_by_location(self):
        rows = self.gap_rows()
        self.assertGreaterEqual(len(rows), 20)
        eng = self.app.engine
        for r in rows:
            lat, lng = float(r['entrance_lat']), float(r['entrance_lng'])
            self.assertIsNone(eng.areas.container(lng, lat), r['machine'])
            self.assertTrue(eng.in_country(lat, lng), r['machine'])
            s, a = self.get('/v1/at', lat=r['entrance_lat'], lng=r['entrance_lng'])
            self.assertEqual((s, a['status'], a['code']['machine'], a['code']['spotCode']),
                             (200, 'found', r['machine'], r['spot_code']), r['machine'])
            self.assertEqual(a['area']['key'], r['zone'], r['machine'])

    def test_2_a_free_point_in_a_gap(self):
        lat, lng = 7.7950482, 1.6411889    # 33 m north of the entrance of TG-ANI0101-3072-0, in no outline
        self.assertIsNone(self.app.engine.areas.container(lng, lat))
        s, a = self.get('/v1/at', lat=str(lat), lng=str(lng))
        self.assertEqual((s, a['status'], a['area']['key'], a['newCodeArea'], a['spotCode']),
                         (200, 'none', 'ANI0101', 'ANI0101', 'ANI01-23G4-RP68'))
        s, c = self.call('POST', '/v1/codes', body={'lat': lat, 'lng': lng})
        self.assertEqual((s, c['area']['key'], c['spotCode']), (201, 'ANI0101', 'ANI01-23G4-RP68'), c)
        s, a = self.get('/v1/at', lat=str(lat), lng=str(lng))
        self.assertEqual((a['status'], a['code']['machine']), ('found', c['machine']))

    def test_3_an_entrance_moves_within_a_gap(self):
        lat, lng = 7.2486, 1.6392    # 25 m from Doloume 15 05's entrance, in no outline
        self.assertIsNone(self.app.engine.areas.container(lng, lat))
        s, c = self.call('PATCH', '/v1/codes/TG-MMO0303-1505-7', body={'entrance': {'lat': lat, 'lng': lng}})
        self.assertEqual(s, 200, c)
        self.assertEqual((c['entrance']['lat'], c['entrance']['lng'], c['entrance']['kind']), (lat, lng, 'gate'))

    def test_4_a_point_far_outside_is_refused(self):
        for lat, lng in ((5.8, 1.3), (6.3, 1.9), (11.3, 0.5), (48.85, 2.35)):
            self.assertFalse(self.app.engine.in_country(lat, lng))
            self.assertError(self.get('/v1/at', lat=str(lat), lng=str(lng)), 404, 'outside')
            self.assertError(self.call('POST', '/v1/codes', body={'lat': lat, 'lng': lng}), 422, 'outside')


class Border(Base):
    """The national border decides (engine/SPEC.md 10, rule 1): a point more than 300 m across it is refused even
    where a zone outline or the spot-code rule reaches it; a point inside, or just over the line, is accepted."""

    ACROSS = ((6.13, 1.1945),    # 557 m across, inside the Lomé Commune canton outline (LOM01), which reaches over the line
              (6.13, 1.187))     # 1.4 km across, in no outline but with a spot code

    def test_1_the_border_file(self):
        b = self.app.engine.border
        self.assertLess(os.path.getsize(os.path.join(os.path.dirname(HERE), 'engine', 'data', 'border.json')), 1 << 20)
        self.assertLessEqual(b.deviation_m, 60)
        self.assertAlmostEqual(b.allowed_m, 300 - b.deviation_m)
        self.assertTrue(b.contains(6.13, 1.2035))
        self.assertFalse(b.contains(6.3, 1.9))

    def test_2_a_point_across_the_border_is_refused(self):
        eng = self.app.engine
        for lat, lng in self.ACROSS:
            self.assertTrue(eng.in_country(lat, lng))      # the outlines and spot codes alone would take it
            self.assertGreater(eng.border.outside_m(lat, lng), 300)
            self.assertError(self.call('POST', '/v1/codes', body={'lat': lat, 'lng': lng}), 422, 'outside')
            s, a = self.get('/v1/at', lat=str(lat), lng=str(lng))
            self.assertEqual((s, a['status'], a['newCodeArea']), (200, 'none', None))

    def test_3_a_point_inside_is_accepted(self):
        for lat, lng in ((6.13, 1.2035),     # Lomé, Nyékonakpoé, inside the border
                         (6.125, 1.199)):    # 50 m over the line: within the 300 m
            self.assertTrue(self.app.engine.in_border(lat, lng))
            s, c = self.call('POST', '/v1/codes', body={'lat': lat, 'lng': lng})
            self.assertEqual(s, 201, c)
            self.assertEqual(c['status'], 'provisional')

    def test_4_an_entrance_cannot_move_across_the_border(self):
        s, c = self.call('POST', '/v1/codes', body={'lat': 6.125, 'lng': 1.1975})     # 214 m over the line
        self.assertEqual(s, 201, c)
        moved = {'entrance': {'lat': 6.125, 'lng': 1.1968}}     # 77 m farther west: 290 m over the line
        self.assertError(self.call('PATCH', '/v1/codes/' + c['machine'], body=moved), 422, 'outside')
        s, d = self.call('PATCH', '/v1/codes/' + c['machine'], body={'entrance': {'lat': 6.125, 'lng': 1.198}})   # 55 m back east
        self.assertEqual((s, d.get('entrance', {}).get('kind')), (200, 'gate'), d)


class Http(Base):
    """One real HTTP round trip: headers, status codes and the error shape."""

    def test_over_http(self):
        from server.api import ThreadingHTTPServer
        handler = type('H', (Handler,), {'app': App(self.db, keys=[], per_day=5, cors=['*'])})
        httpd = ThreadingHTTPServer(('127.0.0.1', 0), handler)
        t = threading.Thread(target=httpd.serve_forever, daemon=True)
        t.start()
        base = 'http://127.0.0.1:%d' % httpd.server_address[1]
        try:
            req = urllib.request.Request(base + '/v1/find?q=Boulohou%2010%2000', headers={'Origin': 'https://example.org'})
            with urllib.request.urlopen(req) as r:
                self.assertEqual(r.headers['Content-Type'], 'application/json; charset=utf-8')
                self.assertEqual(r.headers['Access-Control-Allow-Origin'], '*')
                self.assertEqual(json.load(r)['results'][0]['machine'], 'TG-PMO01-1000-7')
            req = urllib.request.Request(base + '/v1/codes', data=b'{}', method='POST', headers={'Content-Type': 'application/json'})
            with self.assertRaises(urllib.error.HTTPError) as e:
                urllib.request.urlopen(req)
            with e.exception as err:
                self.assertEqual(err.code, 403)
                self.assertEqual(json.load(err)['error']['code'], 'read_only')
        finally:
            httpd.shutdown()
            httpd.server_close()


if __name__ == '__main__':
    unittest.main()
