#!/usr/bin/env python3
"""Conformance vectors for every port of the engine: engine/reference/vectors.json.

Computed by the reference engine (engine/reference/tg_engine.py) on the frozen area table
(model/areas/areas.json); every other engine (the issuer's, the app's, the registry server's) must
reproduce them value for value, and engine/reference/test_tg.py checks the reference against them.

  python3 tools/vectors.py
"""
import csv, glob, gzip, json, os, random, sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(REPO, 'engine', 'reference'))
import tg_engine as E  # noqa: E402


def decode(A, text):
    try:
        r = E.parse(A, text)
        if r['kind'] != 'compound':
            return {'text': text, 'error': r['kind']}
        a = A.by_key[r['area']]
        return {'text': text, 'machine': E.machine(a, r['number'])}
    except ValueError as e:
        return {'text': text, 'error': str(e)}


def spot_outside(A, lat, lon, machine=None):
    """A spot vector for a point in no quartier or canton outline (SPEC 5)."""
    v = {'lat': lat, 'lon': lon}
    try:
        code = E.encode_spot(A, lat, lon)
    except ValueError as e:
        v['error'] = str(e)
        return v
    f = A.by_key[code.split('-')[0]]
    dl, dn, _ = E.decode_spot(A, code)
    v.update({'zone': f['key'], 'clamped': E._frame_cells(f, lat, lon)[2] > 0, 'code': code, 'decoded': [dl, dn]})
    if machine:
        v['machine'] = machine
    return v


def spots_outside(A):
    """Points in no outline: issued compounds (every one that takes a frame's nearest cell, and a
    sample of the others) and points around the outlines, some of them refused."""
    rnd = random.Random(1105)
    issued = []
    for fn in sorted(glob.glob(os.path.join(REPO, 'registry', '*.csv.gz'))):
        if fn.endswith('areas.csv.gz'):
            continue
        with gzip.open(fn, 'rt', encoding='utf-8', newline='') as fh:
            for r in csv.DictReader(fh):
                lat, lon = float(r['entrance_lat']), float(r['entrance_lng'])
                if A.container(lon, lat) is None:
                    issued.append(spot_outside(A, lat, lon, r['machine']))
    clamped = [v for v in issued if v.get('clamped')]
    out = clamped + rnd.sample([v for v in issued if not v.get('clamped')], 150)
    cantons = [a for a in A.areas if a['kind'] in ('lome-quartier', 'canton') and a['unit'] in A._geoms]
    near, far = [], []
    while len(near) < 150 or len(far) < 40:
        a = rnd.choice(cantons)
        g = A._geoms[a['unit']]
        ring = (g['coordinates'] if g['type'] == 'Polygon' else rnd.choice(g['coordinates']))[0]
        x, y = rnd.choice(ring)
        lat, lon = y + rnd.uniform(-0.015, 0.015), x + rnd.uniform(-0.015, 0.015)
        if A.container(lon, lat) is not None:
            continue
        v = spot_outside(A, lat, lon)
        (far if 'error' in v else near).append(v)
    return out + near[:150] + far[:40]


def main():
    rnd = random.Random(246)
    A = E.Areas()
    num = [a for a in A.areas if a.get('numberLength') and a.get('blocks')]
    words = sorted({a['name'] for a in num} | {a.get('officialName') or a['name'] for a in num})
    tricky = ['Kopé', 'Copé', 'Djabdjoare', 'Jabjoare', 'Nassiété', 'Nasiete', 'Ediwlou', 'Ediwoulou', 'Zongo 1', 'Agbo Kope II',
              'Le Kpota', 'St Joseph', 'Saint-Joseph', 'N.-D. des Lacs', 'Notre-Dame des Lacs', 'Agoè-Démakpoè', 'Bè', 'Tokoin Lycée',
              'Ʋɔgan', 'Vogan', 'Kpalimé', 'KPALIME', 'Lom-Nava', 'Lomnava']
    keys = [[w, E.name_key(w)] for w in tricky + rnd.sample(words, 600)]
    forms, found = [], []
    for a in rnd.sample(num, 500):
        lo, hi = a['blocks'][0]
        n = rnd.randint(lo, hi)
        forms.append({'zone': a['key'], 'number': n, 'check': E.check_digit(a, n), 'home': '%s %d' % (a['name'], n),
                      'written': E.remembered(a, n), 'machine': E.machine(a, n)})
        for text in ('%s %d' % (a['name'], n), E.remembered(a, n), '%s %d-%d' % (a['name'], n, E.check_digit(a, n)), E.machine(a, n)):
            found.append(decode(A, text))
    off = [a for a in num if a.get('officialName') and E.name_key(a['officialName']) != E.name_key(a['name']) and a['officialName'] in a.get('aliases', [])]
    for a in rnd.sample(off, min(120, len(off))):
        found.append(decode(A, '%s %d' % (a['officialName'], a['blocks'][0][0] + 1)))
    for a in rnd.sample(num, 60):
        n = a['blocks'][0][0] + 3
        found.append(decode(A, '%s %d-%d' % (a['name'], n, (E.check_digit(a, n) + 1) % 10)))
        found.append(decode(A, 'TG-%s-%d-%d' % (a['key'], n, (E.check_digit(a, n) + 1) % 10)))
    found += [decode(A, t) for t in ('Nulle Part 1234', '165 AMT', 'Rue 46BE', '13.QAD')]
    spots = []
    while len(spots) < 400:
        lat, lon = rnd.uniform(6.1, 11.1), rnd.uniform(-0.1, 1.8)
        a = A.at(lat, lon)
        if a is None:
            continue
        code = E.encode_spot(A, lat, lon)
        dl, dn, _ = E.decode_spot(A, code)
        spots.append({'lat': lat, 'lon': lon, 'area': a['key'], 'code': code, 'decoded': [dl, dn]})
    for _ in range(80):    # Lomé, densely
        lat, lon = rnd.uniform(6.12, 6.22), rnd.uniform(1.17, 1.32)
        a = A.at(lat, lon)
        if a is None:
            continue
        code = E.encode_spot(A, lat, lon)
        dl, dn, _ = E.decode_spot(A, code)
        spots.append({'lat': lat, 'lon': lon, 'area': a['key'], 'code': code, 'decoded': [dl, dn]})
    big = max(num, key=lambda a: a['blocks'][0][1] - a['blocks'][0][0])
    x0, y0, x1, y1 = big['box']
    comps = [{'id': 'c%02d' % k, 'lat': y0 + rnd.uniform(0, y1 - y0), 'lon': x0 + rnd.uniform(0, x1 - x0)} for k in range(41)]
    nums = E.number_compounds(big, comps)
    issued = [{'number': nums[c['id']], 'lat': c['lat'], 'lon': c['lon']} for c in comps]
    inserts = []
    for _ in range(60):
        lat, lon = y0 + rnd.uniform(0, y1 - y0), x0 + rnd.uniform(0, x1 - x0)
        n = E.provisional_number(big, issued, lat, lon)
        inserts.append({'lat': lat, 'lon': lon, 'number': n})
        issued.append({'number': n, 'lat': lat, 'lon': lon})
    hil = [[x, y, E.hilbert_index(16, x, y)] for x, y in ((0, 0), (1, 0), (65535, 65535), (12345, 54321), (40000, 2))]
    out = {'note': 'Computed by engine/reference/tg_engine.py on the frozen area table; every port must match.',
           'nameKeys': keys, 'forms': forms, 'found': found, 'spots': spots,
           'numbering': {'zone': big['key'], 'compounds': comps, 'numbers': nums, 'inserts': inserts},
           'spotsOutside': spots_outside(A), 'hilbert': hil, 'pairs': [[n, E.pairs(n)] for n in (1000, 4817, 13217, 10000, 99999)]}
    json.dump(out, open(os.path.join(REPO, 'engine', 'reference', 'vectors.json'), 'w'), ensure_ascii=False, indent=0)
    print(len(keys), 'name keys,', len(forms), 'forms,', len(found), 'decodings,', len(spots), 'spots,',
          len(out['spotsOutside']), 'spots in no outline,', len(inserts), 'inserts')


if __name__ == '__main__':
    main()
