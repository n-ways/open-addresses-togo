#!/usr/bin/env python3
"""Tests for the Togo reference engine. Offline, standard library only.

  python3 engine/reference/test_tg.py        (from the repo root, or from this folder)
"""
import json
import math
import os
import random
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import tg_engine as E  # noqa: E402

V = E.load_json(os.path.join(HERE, 'test_vectors.json'))
FOOT = E.load_json(os.path.join(HERE, 'testdata', 'footprints.json'))['windows']
AREAS = E.Areas()


def cen(r):
    return (sum(x for x, _ in r[:-1]) / (len(r) - 1), sum(y for _, y in r[:-1]) / (len(r) - 1))


class Damm(unittest.TestCase):
    def test_published_example(self):
        for v in V['damm']:
            self.assertEqual(E.damm(v['digits']), v['check'])
            self.assertTrue(E.damm_ok(v['digits'] + str(v['check'])))

    def test_catches_single_errors_and_adjacent_swaps(self):
        rnd = random.Random(7)
        for _ in range(400):
            s = '%04d%d' % (rnd.randint(1, 2500), rnd.randint(1000, 99999))
            full = s + str(E.damm(s))
            for i in range(len(full)):
                for d in '0123456789':
                    if d != full[i]:
                        self.assertFalse(E.damm_ok(full[:i] + d + full[i + 1:]))
            for i in range(len(full) - 1):
                if full[i] != full[i + 1]:
                    self.assertFalse(E.damm_ok(full[:i] + full[i + 1] + full[i] + full[i + 2:]))


class Spots(unittest.TestCase):
    def test_vectors(self):
        for v in V['spots']:
            self.assertEqual(E.encode_spot(AREAS, v['lat'], v['lon']), v['spot'])
            lat, lon, cell = E.decode_spot(AREAS, v['spot'])
            self.assertAlmostEqual(lat, v['decoded'][0], places=6)
            self.assertAlmostEqual(lon, v['decoded'][1], places=6)
            m_lat, m_lon = E.metres(lat)
            self.assertLessEqual(abs(lat - v['lat']) * m_lat, cell[0] / 2 + 0.01)
            self.assertLessEqual(abs(lon - v['lon']) * m_lon, cell[1] / 2 + 0.01)

    def test_round_trip_random_points_in_lome_and_north(self):
        rnd = random.Random(3)
        for (lat0, lon0) in ((6.14, 1.23), (6.25, 1.21), (9.55, 1.19), (10.86, 0.21)):
            for _ in range(40):
                lat, lon = lat0 + rnd.uniform(-0.02, 0.02), lon0 + rnd.uniform(-0.02, 0.02)
                if AREAS.at(lat, lon) is None:
                    continue
                code = E.encode_spot(AREAS, lat, lon)
                dlat, dlon, cell = E.decode_spot(AREAS, code)
                self.assertEqual(E.encode_spot(AREAS, dlat, dlon), code)
                self.assertLess(math.hypot((dlat - lat) * 110600, (dlon - lon) * 110000), 3.0)

    def test_alphabet_has_no_q_or_vowels(self):
        self.assertNotIn('Q', E.ALPHABET)
        self.assertEqual(len(set(E.ALPHABET)), 20)
        for c in 'AEIOU01':
            self.assertNotIn(c, E.ALPHABET)


class Areas(unittest.TestCase):
    def test_vectors(self):
        for v in V['areas']:
            a = AREAS.at(v['lat'], v['lon'])
            self.assertEqual(a['key'], v['area'])
            self.assertEqual(a['numberLength'], v['numberLength'])

    def test_lome_quartier_codes_are_street_sign_codes(self):
        for k in ('AMT', 'BE', 'TKL', 'QAD', 'LO2', 'HDN', 'UB', 'RB'):
            self.assertEqual(AREAS.by_key[k]['kind'], 'lome-quartier')
            self.assertIn(AREAS.by_key[k]['numberLength'], (4, 5))   # Lomé's quartiers are numbered too

    def test_every_nways_area_has_4_or_5_digits(self):
        for a in AREAS.areas:
            if a.get('numberLength') is not None:
                self.assertIn(a['numberLength'], (4, 5))
                self.assertFalse(a.get('official'))


class Compounds(unittest.TestCase):
    def test_grouping_and_first_issue_reproduce_vectors(self):
        for v in V['compounds']:
            w = FOOT[v['window']]
            structs = [{'id': s['id'], 'ring': s['ring']} for s in w['buildings']]
            comps = E.group_compounds(structs, [x['ring'] for x in w['walls']], v['params'])
            self.assertEqual(len(comps), v['compounds'])
            a = AREAS.by_key[v['area']]
            if v['official']:
                self.assertEqual([c['members'] for c in comps[:6]], [f['members'] for f in v['first']])
                continue
            rings = {s['id']: s['ring'] for s in structs}
            pts = [{'id': c['main'], 'lat': cen(rings[c['main']])[1], 'lon': cen(rings[c['main']])[0]} for c in comps]
            nums = E.number_compounds(a, pts)
            self.assertEqual(len(set(nums.values())), len(nums))
            for f in v['first']:
                self.assertEqual(nums[f['main']], f['number'])
                self.assertEqual(E.remembered(a, f['number']), f['remembered'])
                self.assertEqual(E.machine(a, f['number']), f['machine'])

    def test_grand_lome_has_codes_and_keeps_its_official_system(self):
        # every home of Grand Lomé has a code; the DAGL's address comes first where it is known
        for k in ('AMT', 'BE', 'HDN'):
            a = AREAS.by_key[k]
            self.assertTrue(a.get('officialSystem') and a.get('numberLength'))
            n = a['blocks'][0][0]
            self.assertTrue(E.machine(a, n).startswith('TG-%s-%d-' % (k, n)))
        self.assertTrue(all(a.get('officialSystem') for a in AREAS.areas
                            if a.get('prefecture') in ('Golfe', 'Agoe-Nyive', 'Lomé (ancienne commune)')))

    def test_official_addresses_attach_to_the_nearest_gate_and_keep_their_spelling(self):
        comps = [{'id': 'c1', 'gates': [{'n': 1, 'lat': 6.14046, 'lon': 1.23176}]},
                 {'id': 'c2', 'gates': [{'n': 1, 'lat': 6.14060, 'lon': 1.23190}]}]
        recs = [{'id': 'r1', 'lat': 6.14047, 'lon': 1.23177, 'number': 58, 'street': 'Rue Oukata-Waya 165 AMT', 'source': 'DAGL (example)'},
                {'id': 'r2', 'lat': 6.15000, 'lon': 1.24000, 'number': 12, 'street': 'Rue de test', 'source': 'DAGL (example)'}]
        links, unmatched = E.attach_official(comps, recs)
        self.assertEqual([(l['record'], l['compound']) for l in links], [('r1', 'c1')])
        self.assertEqual(links[0]['text'], '58, Rue Oukata-Waya 165 AMT')
        self.assertEqual(unmatched, ['r2'])

    def test_numbers_follow_the_curve_with_gaps(self):
        a = AREAS.by_key['KOZ0604']
        rnd = random.Random(1)
        pts = [{'id': i, 'lat': rnd.uniform(a['box'][1], a['box'][3]), 'lon': rnd.uniform(a['box'][0], a['box'][2])} for i in range(500)]
        nums = E.number_compounds(a, pts)
        order = sorted(pts, key=lambda p: E.hilbert_of(a, p['lat'], p['lon']))
        seq = [nums[p['id']] for p in order]
        self.assertEqual(seq, sorted(seq))
        self.assertGreater(seq[1] - seq[0], 1)          # infill gap
        self.assertLess(max(seq), E.tail_start(a))      # tail reserve untouched
        lo, hi = a['blocks'][0]
        self.assertTrue(all(lo <= n <= hi for n in seq))
        self.assertEqual(a['numberLength'], 4)

    def test_provisional_numbers(self):
        for v in V['provisional']:
            a = AREAS.by_key[v['area']]
            w = [k for k, c in zip(range(len(V['compounds'])), V['compounds']) if c['area'] == v['area']][0]
            c = V['compounds'][w]
            win = FOOT[c['window']]
            structs = [{'id': s['id'], 'ring': s['ring']} for s in win['buildings']]
            comps = E.group_compounds(structs, [x['ring'] for x in win['walls']], c['params'])
            rings = {s['id']: s['ring'] for s in structs}
            pts = [{'id': x['main'], 'lat': cen(rings[x['main']])[1], 'lon': cen(rings[x['main']])[0]} for x in comps]
            nums = E.number_compounds(a, pts)
            issued = [{'number': nums[p['id']], 'lat': p['lat'], 'lon': p['lon']} for p in pts]
            n = E.provisional_number(a, issued, v['lat'], v['lon'])
            self.assertEqual(n, v['number'])
            self.assertNotIn(n, {i['number'] for i in issued})
            self.assertEqual(len(str(n)), a['numberLength'])

    def test_full_area_takes_a_block_of_its_name(self):
        # You (BLI0404, 1000-1199) shares its name with BLI0403 (1200-2199): a full You takes the next
        # free run of the name's 4-digit part, sized for its compounds (SPEC 3.1 rules 4 and 7)
        self.assertEqual([E.block_size(n) for n in (1, 100, 101, 201, 1250)], [200, 200, 300, 500, 2500])
        a = dict(AREAS.by_key['BLI0404'])
        a['blocks'] = [list(b) for b in a['blocks']]
        lat, lon = a['point'][1], a['point'][0]
        issued = [{'number': n, 'lat': lat, 'lon': lon} for n in range(1000, 1200)]
        with self.assertRaises(E.AreaFull):
            E.provisional_number(a, issued, lat, lon)
        n = E.insert_number(AREAS, a, issued, lat + 0.0004, lon)
        self.assertEqual((n, a['blocks']), (2200, [[1000, 1199], [2200, 2699]]))
        issued.append({'number': n, 'lat': lat + 0.0004, 'lon': lon})
        self.assertEqual(E.insert_number(AREAS, a, issued, lat + 0.0008, lon), 2201)
        self.assertEqual(AREAS.by_key['BLI0404']['blocks'], [[1000, 1199]])   # the table itself is untouched

    def test_annex_joins_main_house(self):
        # a 6 x 8 m house and a 2 x 3 m kitchen 3 m away form one compound; a house 20 m away does not
        lat0, lon0 = 6.1400, 1.2300
        m_lat, m_lon = E.metres(lat0)

        def rect(x, y, w, h):
            pts = [(x, y), (x + w, y), (x + w, y + h), (x, y + h), (x, y)]
            return [[lon0 + px / m_lon, lat0 + py / m_lat] for px, py in pts]
        s = [{'id': 'house', 'ring': rect(0, 0, 6, 8)}, {'id': 'kitchen', 'ring': rect(9, 0, 2, 3)},
             {'id': 'neighbour', 'ring': rect(30, 0, 7, 9)}]
        comps = E.group_compounds(s)
        self.assertEqual(sorted(len(c['members']) for c in comps), [1, 2])
        walled = E.group_compounds(s, [rect(-2, -2, 15, 12)])
        self.assertIn(['house', 'kitchen'], [c['members'] for c in walled])
        self.assertEqual([c['rule'] for c in walled if 'house' in c['members']], ['enclosure'])


class NationalNames(unittest.TestCase):
    """SPEC 3.1: a remembered code is unique nationally on its own, without préfecture or position."""

    def test_same_name_decodes_to_different_places(self):
        for v in V['sameName']:
            r = E.parse(AREAS, v['text'])
            self.assertEqual(r['area'], v['area'])
            self.assertEqual(E.parse(AREAS, v['machine'])['area'], v['area'])
            self.assertTrue(E.parse(AREAS, v['withCheck'])['checked'])
        by_name = {}
        for v in V['sameName']:
            by_name.setdefault(E.name_key(v['name']), []).append(v)
        for k, vs in by_name.items():
            self.assertGreater(len({v['area'] for v in vs}), 1, k)
            self.assertEqual(len({v['nameId'] for v in vs}), 1, k)
        # Tokpo in Danyi and Tokpo in Lacs are ~100 km apart; their codes differ only by the number
        a, b = AREAS.by_key['DNY0417'], AREAS.by_key['LAC0603']
        m_lat, m_lon = E.metres(7)
        self.assertGreater(math.hypot((a['point'][0] - b['point'][0]) * m_lon, (a['point'][1] - b['point'][1]) * m_lat), 50000)

    def test_every_name_key_owns_disjoint_blocks(self):
        groups = {}
        for a in AREAS.areas:
            if a.get('numberLength') and not a.get('official'):
                self.assertTrue(a['blocks'] and a['nameId'])
                groups.setdefault(E.name_key(a['name']), []).append(a)
        for k, g in groups.items():
            self.assertEqual(len({a['nameId'] for a in g}), 1, k)
            spans = sorted(tuple(b) for a in g for b in a['blocks'])
            for (lo, hi), (lo2, hi2) in zip(spans, spans[1:]):
                self.assertLess(hi, lo2, k)
            for a in g:
                for lo, hi in a['blocks']:
                    self.assertEqual(len(str(lo)), len(str(hi)))
                    self.assertEqual(len(str(lo)), a['numberLength'])
                    self.assertLessEqual(hi, 99999)
        self.assertEqual(len({a['nameId'] for g in groups.values() for a in g}), len(groups))

    def test_number_outside_every_block_is_refused(self):
        with self.assertRaises(ValueError):
            E.parse(AREAS, 'Tokpo 54 17')
        with self.assertRaises(ValueError):
            E.parse(AREAS, 'TG-DNY0417-2417-%d' % E.check_digit(AREAS.by_key['LAC0603'], 2417))

    def test_check_digit_binds_name_number_and_area(self):
        a, b = AREAS.by_key['DNY0417'], AREAS.by_key['ZIO0216']
        self.assertNotEqual(E.damm('%04d%04d%d' % (a['nameId'], a['index'], 1100)),
                            E.damm('%04d%04d%d' % (b['nameId'] + 1, a['index'], 1100)))
        good = E.machine(AREAS.by_key['TCB0601'], 15000)
        self.assertTrue(E.parse(AREAS, 'Bagou 1 50 00-' + good[-1])['checked'])
        with self.assertRaises(ValueError):
            E.parse(AREAS, 'Bagou 1 50 00-' + str((int(good[-1]) + 1) % 10))

    def test_name_folding(self):
        for x, y in (('Djanta Copé', 'Djanta kopé'), ('Lom-Nava', 'LOMNAVA'), ('Nassiété', 'Nasiete'),
                     ('Ediwlou', 'Ediwoulou'), ('Zongo 1', 'Zongo'), ('Avédjé', 'Avedje')):
            self.assertEqual(E.name_key(x), E.name_key(y))
        self.assertNotEqual(E.name_key('Kara'), E.name_key('Kamina'))
        self.assertEqual(E.clean_place_name('Village de ZOMAÏ', 'X')[0], 'Zomaï')
        self.assertEqual(E.clean_place_name('unknow', 'Agbandi')[0], 'Agbandi')
        for a in AREAS.areas:  # no digit in a numbered area's name: it would run into the code's number
            if a.get('numberLength'):
                self.assertFalse(any(c.isdigit() for c in a['name']), a['key'])


class PlateNames(unittest.TestCase):
    """SPEC 3.2: the plate name (the name in the remembered code) has at most 12 characters and 2 words."""

    def test_limit(self):
        for v in V['plateNames']['fits']:
            self.assertEqual(E.plate_names.plate_length(v['name']), v['length'], v['name'])
            self.assertEqual(E.plate_names.word_count(v['name'], 'fr'), v['words'], v['name'])
            self.assertEqual(E.plate_fits(v['name']), v['fits'], v['name'])

    def test_every_issuable_plate_fits(self):
        for a in AREAS.areas:
            if a.get('numberLength') and not a.get('official'):
                self.assertIn('officialName', a)
                if not a.get('needsCouncilChoice'):
                    self.assertTrue(E.plate_fits(a['name']), a['key'])
                if a.get('needsCouncilChoice'):
                    self.assertLessEqual(len(a['plateCandidates']), 3)
                    if a['plateCandidates']:
                        self.assertEqual(a['name'], a['plateCandidates'][0])

    def test_official_name_decodes_like_the_plate(self):
        for v in V['plateNames']['officialToPlate']:
            a = AREAS.by_key[v['area']]
            self.assertEqual(a['name'], v['plate'])
            self.assertGreater(E.plate_names.plate_length(v['officialName']), E.plate_names.plate_length(v['plate']))
            self.assertEqual(E.parse(AREAS, v['officialTyped'])['area'], v['area'])
            self.assertEqual(E.parse(AREAS, v['remembered'])['area'], v['area'])
            self.assertEqual(E.parse(AREAS, v['machine'])['area'], v['area'])

    def test_names_equal_after_shortening_decode_apart(self):
        vs = V['plateNames']['collideAfterShortening']
        for v in vs:
            self.assertEqual(E.parse(AREAS, v['text'])['area'], v['area'])
            self.assertEqual(E.parse(AREAS, v['machine'])['area'], v['area'])
        by = {}
        for v in vs:
            by.setdefault(E.name_key(v['plate']), set()).add(v['area'])
        for k, s in by.items():
            self.assertGreater(len(s), 1, k)

    def test_refused(self):
        for v in V['plateNames']['refused']:
            if 'text' in v:
                with self.assertRaises(ValueError):
                    E.parse(AREAS, v['text'])
            else:
                # an area waiting for its commune issues codes under its provisional name
                a = AREAS.by_key[v['area']]
                self.assertTrue(a.get('needsCouncilChoice'))
                self.assertTrue(E.remembered(a, a['blocks'][0][0]).startswith(a['name']))

    def test_abbreviation_expands_in_the_name_key(self):
        self.assertEqual(E.name_key('St Joseph'), E.name_key('Saint-Joseph'))
        self.assertEqual(E.name_key('Ste Marie'), E.name_key('Sainte Marie'))


class Forms(unittest.TestCase):
    def test_parse_vectors(self):
        for v in V['parse']:
            if 'error' in v:
                with self.assertRaises(ValueError):
                    E.parse(AREAS, v['text'])
            else:
                self.assertEqual(E.parse(AREAS, v['text']), v['result'])

    def test_street_code_is_never_read_as_a_compound_code(self):
        for t in ('165 AMT', '3HDN', '13.QAD', '128 OTN'):
            self.assertEqual(E.parse(AREAS, t)['kind'], 'lome-street-code')

    def test_bad_check_digit_is_refused(self):
        a = AREAS.by_key['KOZ0604']
        good = E.machine(a, 2417)
        bad = good[:-1] + str((int(good[-1]) + 1) % 10)
        with self.assertRaises(ValueError):
            E.parse(AREAS, bad)

    def test_spoken_french(self):
        a = AREAS.by_key['KOZ0604']
        self.assertEqual(E.spoken_fr(AREAS, a, 2417), 'Kara, vingt-quatre, dix-sept')
        self.assertEqual(E.spoken_fr(AREAS, a, 7191), 'Kara, soixante et onze, quatre-vingt-onze')
        self.assertEqual(E.pairs(13217), '1 32 17')

    def test_floors(self):
        self.assertEqual(E.floors_from_height(5.3), 2)
        self.assertEqual(E.floors_from_height(3.0), 1)
        self.assertEqual(E.floors_from_height(10.5), 4)


class ConformanceVectors(unittest.TestCase):
    """engine/reference/vectors.json, which every port reproduces value for value (SPEC 13)."""

    @classmethod
    def setUpClass(cls):
        cls.V = E.load_json(os.path.join(HERE, 'vectors.json'))

    def test_name_keys(self):
        for text, key in self.V['nameKeys']:
            self.assertEqual(E.name_key(text), key, text)

    def test_forms(self):
        for f in self.V['forms']:
            a = AREAS.by_key[f['zone']]
            self.assertEqual((E.check_digit(a, f['number']), E.remembered(a, f['number']), E.machine(a, f['number'])),
                             (f['check'], f['written'], f['machine']))
            self.assertEqual('%s %d' % (a['name'], f['number']), f['home'])

    def test_decodings(self):
        for f in self.V['found']:
            try:
                r = E.parse(AREAS, f['text'])
                got = ({'machine': E.machine(AREAS.by_key[r['area']], r['number'])} if r['kind'] == 'compound'
                       else {'error': r['kind']})
            except ValueError as e:
                got = {'error': str(e)}
            self.assertEqual(got, {k: v for k, v in f.items() if k != 'text'}, f['text'])

    def test_spots(self):
        for s in self.V['spots']:
            self.assertEqual(AREAS.at(s['lat'], s['lon'])['key'], s['area'])
            self.assertEqual(E.encode_spot(AREAS, s['lat'], s['lon']), s['code'])
            lat, lon, _ = E.decode_spot(AREAS, s['code'])
            self.assertEqual([lat, lon], s['decoded'])

    def test_spots_outside(self):
        """Points in no outline take the nearest outline within 1,100 m whose frame holds them, or
        the nearest cell of a frame within 200 cells; issued compounds among them (SPEC 5)."""
        issued = clamped = refused = 0
        for s in self.V['spotsOutside']:
            self.assertIsNone(AREAS.container(s['lon'], s['lat']))
            if 'error' in s:
                refused += 1
                with self.assertRaises(ValueError):
                    E.encode_spot(AREAS, s['lat'], s['lon'])
                continue
            issued += 'machine' in s
            clamped += s['clamped']
            self.assertEqual(E.spot_frame(AREAS, s['lat'], s['lon'])['key'], s['zone'])
            self.assertEqual(E.encode_spot(AREAS, s['lat'], s['lon']), s['code'])
            lat, lon, _ = E.decode_spot(AREAS, s['code'])
            self.assertEqual([lat, lon], s['decoded'])
            if not s['clamped']:
                self.assertEqual(E.encode_spot(AREAS, lat, lon), s['code'])
        self.assertGreaterEqual(issued, 150)
        self.assertGreaterEqual(clamped, 20)
        self.assertGreaterEqual(refused, 40)

    def test_numbering_and_inserts(self):
        n = self.V['numbering']
        a = AREAS.by_key[n['zone']]
        self.assertEqual(E.number_compounds(a, n['compounds']), n['numbers'])
        issued = [{'number': n['numbers'][c['id']], 'lat': c['lat'], 'lon': c['lon']} for c in n['compounds']]
        for ins in n['inserts']:
            got = E.provisional_number(a, issued, ins['lat'], ins['lon'])
            self.assertEqual(got, ins['number'])
            issued.append({'number': got, 'lat': ins['lat'], 'lon': ins['lon']})

    def test_hilbert_and_pairs(self):
        for x, y, d in self.V['hilbert']:
            self.assertEqual(E.hilbert_index(16, x, y), d)
        for n, text in self.V['pairs']:
            self.assertEqual(E.pairs(n), text)


class NationalBorder(unittest.TestCase):
    """engine/data/border.json and border.py (SPEC 10, rule 1): the border decides, not the zone outlines."""

    def test_border(self):
        import border as B
        b = B.default()
        self.assertLessEqual(b.deviation_m, 60)
        self.assertAlmostEqual(b.allowed_m, B.BORDER_M - b.deviation_m)
        self.assertTrue(b.allows(6.1317765, 1.2234008))        # Fréau-Jardin, Lomé
        self.assertTrue(b.allows(10.8636, 0.2063))             # Dapaong
        self.assertTrue(b.allows(6.125, 1.199))                # 50 m over the line
        self.assertFalse(b.allows(6.13, 1.1945))               # 557 m over, inside the Lomé Commune canton outline
        self.assertFalse(b.allows(6.3, 1.9))                   # a neighbouring country
        self.assertIsNotNone(AREAS.at(6.13, 1.1945))           # the outline alone would have taken it


if __name__ == '__main__':
    unittest.main(verbosity=1)
