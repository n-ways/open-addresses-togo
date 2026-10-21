#!/usr/bin/env python3
"""Write engine/reference/test_vectors.json from real footprints (tools/pick_vectors.py output, or the
copy kept in engine/reference/testdata/footprints.json).
  python3 tools/make_vectors.py [PICKED.json]"""
import json, math, os, sys
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, 'engine', 'reference'))
import tg_engine as E
picked = json.load(open(sys.argv[1] if len(sys.argv) > 1 else os.path.join(REPO, 'engine', 'reference', 'testdata', 'footprints.json')))
picked = picked.get('windows', picked)
areas = E.Areas()
CENTRE = {'AMT': (1.2318, 6.1405), 'BE': (1.2484, 6.1423), 'TKL': (1.2247, 6.1517), 'AGOE': (1.2130, 6.2470),
          'KARA': (1.1977, 9.5489), 'KPALIME': (0.6297, 6.9007), 'TSEVIE': (1.2133, 6.4261)}
def cen(r): return (sum(x for x, _ in r[:-1]) / (len(r) - 1), sum(y for _, y in r[:-1]) / (len(r) - 1))
V = {'note': 'Real OpenStreetMap footprints (ODbL) in Grand Lomé (Amoutivé, Bè, Tokoin-Lycée, Agoè-Nyivé: the DAGL area, where the official address comes first) and outside it (Kara, Kpalimé, Tsévié). Expected values pin the reference engine.',
     'spots': [], 'areas': [], 'compounds': [], 'damm': [{'digits': '572', 'check': 4, 'source': 'published Damm example'}],
     'parse': [], 'provisional': [], 'sameName': [], 'plateNames': {'fits': [], 'officialToPlate': [], 'collideAfterShortening': [],
                                                                       'refused': []}}
for k, (lon0, lat0) in CENTRE.items():
    bs = picked[k]['buildings']
    b = min(bs, key=lambda b: math.hypot(cen(b['ring'])[0] - lon0, cen(b['ring'])[1] - lat0))
    lon, lat = cen(b['ring'])
    a = areas.at(lat, lon)
    spot = E.encode_spot(areas, lat, lon)
    dlat, dlon, cell = E.decode_spot(areas, spot)
    V['spots'].append({'window': k, 'osm': b['id'], 'lat': round(lat, 7), 'lon': round(lon, 7), 'spot': spot,
                       'decoded': [round(dlat, 7), round(dlon, 7)], 'cellM': [round(cell[0], 2), round(cell[1], 2)]})
    V['areas'].append({'osm': b['id'], 'lat': round(lat, 7), 'lon': round(lon, 7), 'area': a['key'], 'kind': a['kind'], 'name': a['name'],
                       'numberLength': a['numberLength'], 'official': bool(a.get('official'))})
    # group the window's structures into compounds, then number them as a first issue in that area
    structs = [{'id': s['id'], 'ring': s['ring']} for s in bs]
    walls = [w['ring'] for w in picked[k]['walls']]
    params = E.RURAL_NORTH if k == 'KARA' else E.URBAN
    comps = E.group_compounds(structs, walls, params)
    pts = []
    rings = {s['id']: s['ring'] for s in structs}
    for c in comps:
        clon, clat = cen(rings[c['main']])
        pts.append({'id': c['main'], 'lat': clat, 'lon': clon})
    rec = {'window': k, 'area': a['key'], 'official': bool(a.get('official')), 'params': params, 'structures': len(structs), 'walls': len(walls),
           'compounds': len(comps), 'byRule': {r: sum(1 for c in comps if c['rule'] == r) for r in ('enclosure', 'annex', 'hut-cluster', 'single')}}
    if a.get('official'):
        rec['first'] = [{'main': c['main'], 'members': c['members'], 'rule': c['rule']} for c in comps[:6]]
        V['compounds'].append(rec)
        continue
    nums = E.number_compounds(a, pts)
    sample = sorted(comps, key=lambda c: nums[c['main']])[:6]
    rec['first'] = [{'main': c['main'], 'members': c['members'], 'rule': c['rule'], 'number': nums[c['main']],
                     'remembered': E.remembered(a, nums[c['main']]), 'machine': E.machine(a, nums[c['main']]),
                     'spokenFr': E.spoken_fr(areas, a, nums[c['main']])} for c in sample]
    V['compounds'].append(rec)
    issued = [{'number': nums[p['id']], 'lat': p['lat'], 'lon': p['lon']} for p in pts]
    # a new home 25 m north-east of the reference building
    nlat, nlon = lat + 25 / 110600, lon + 25 / 110000
    if areas.at(nlat, nlon)['key'] == a['key']:
        V['provisional'].append({'area': a['key'], 'lat': round(nlat, 7), 'lon': round(nlon, 7), 'issuedInWindow': len(issued),
                                 'number': E.provisional_number(a, issued, nlat, nlon)})
kp = areas.at(6.9007, 0.6297)
ts = areas.at(6.4261, 1.2133)
for t in ['AMT 48 17', 'amoutivé 4817', '165 AMT', 'Rue 46BE', '13.QAD', 'Kara 24 17', 'kara 2417',
          'TG-KOZ0604-2417-%d' % E.check_digit(areas.by_key['KOZ0604'], 2417), 'TG-KOZ0604-2417-%d' % ((E.check_digit(areas.by_key['KOZ0604'], 2417) + 1) % 10),
          '%s %s' % (kp['name'], E.pairs(10 ** (kp['numberLength'] - 1) + 417)), '%s %s' % (ts['name'], E.pairs(10 ** (ts['numberLength'] - 1) + 3217)),
          'Kara 417']:
    try:
        V['parse'].append({'text': t, 'result': E.parse(areas, t)})
    except ValueError as e:
        V['parse'].append({'text': t, 'error': str(e)})
# Same name, different places (SPEC 3.1): the name + number alone pick one area anywhere in Togo.
# the texts come from the frozen blocks: the number 17 into each area's first block, the name as people type it
SAME_AREAS = [('Tokpo', 'DNY0417'), ('Tokpo', 'ZIO0216'), ('Tokpo', 'LAC0603'), ('Kamina', 'AKB0304'), ('Kamina', 'OGO0411'),
              ('Kamina', 'EMO04'), ('Bagou', 'TDJ01'), ('Bagou', 'TCB0601'), ('Avedje', 'AMO03'), ('Avédjé', 'ZIO0205'),
              ('Lom-Nava', 'OGO0612'), ('Lom-Nava', 'MMO0603'), ('Lom Nava', 'KLO0108'), ('lom nava', 'ZIO1501'), ('LOMNAVA', 'OGO0414'),
              ('Djanta Copé', 'HAH0803'), ('Djanta kopé', 'HAH0507')]
SAME = [('%s %s' % (nm, E.pairs(areas.by_key[k]['blocks'][0][0] + 17)), k) for nm, k in SAME_AREAS]
for t, key in SAME:
    r = E.parse(areas, t)
    a = areas.by_key[r['area']]
    assert r['area'] == key, (t, r)
    V['sameName'].append({'text': t, 'area': key, 'name': a['name'], 'nameId': a['nameId'], 'prefecture': a['prefecture'],
                          'block': a['blocks'][0], 'point': a['point'], 'machine': E.machine(a, r['number']),
                          'withCheck': '%s-%d' % (t, E.check_digit(a, r['number']))})
_b = lambda k: areas.by_key[k]['blocks'][0][0] + 17
for t in ['Tokpo 99 99', 'Kara 99 99', 'Bagou %s-%d' % (E.pairs(_b('TCB0601')), (E.check_digit(areas.by_key['TCB0601'], _b('TCB0601')) + 1) % 10),
          'Tokpo %s-%d' % (E.pairs(_b('ZIO0216')), E.check_digit(areas.by_key['ZIO0216'], _b('ZIO0216'))), 'Zongo 1 06 87', 'Village de Zomaï 10 00']:
    try:
        V['parse'].append({'text': t, 'result': E.parse(areas, t)})
    except ValueError as e:
        V['parse'].append({'text': t, 'error': str(e)})
# Plate names (SPEC 3.2): at most 12 characters and 2 words; the official name decodes as an alias.
for t in ['Kara', 'Mission-Tové', 'Yiboè Avédzé', 'Lom-Nava', "N'tare", 'Lassa Samala Haut', 'Koussocointougou',
          'Danyi Afiadenyigba', 'Gboto Koissidamé', 'Zongo 1']:
    V['plateNames']['fits'].append({'name': t, 'length': E.plate_names.plate_length(t),
                                    'words': E.plate_names.word_count(t, 'fr'), 'fits': E.plate_fits(t)})
for key in ['YOT0401', 'TON1601', 'AGO0803', 'ZIO0602', 'OTI0503', 'DNY0406']:
    a = areas.by_key[key]
    n = a['blocks'][0][0] + 17
    by_plate = E.parse(areas, '%s %s' % (a['name'], E.pairs(n)))
    by_official = E.parse(areas, '%s %s' % (a['officialName'], E.pairs(n)))
    assert by_plate == by_official and by_plate['area'] == key, (key, by_plate, by_official)
    V['plateNames']['officialToPlate'].append({'area': key, 'officialName': a['officialName'], 'plate': a['name'],
                                               'rule': a['plateRule'], 'officialTyped': '%s %s' % (a['officialName'], E.pairs(n)),
                                               'remembered': E.remembered(a, n), 'machine': E.machine(a, n)})
# Plate names that became equal only after shortening: the number still tells the places apart.
for t, key in [('%s %s' % (nm, E.pairs(_b(k))), k) for nm, k in
               [('Tami', 'TON1601'), ('Tami', 'TON1605'), ('Nangbéto', 'OGO0104'), ('Nangbéto', 'OGO0105'), ('Datcha', 'OGO0202'), ('Datcha', 'OGO0201')]]:
    r = E.parse(areas, t)
    a = areas.by_key[r['area']]
    assert r['area'] == key, (t, r)
    V['plateNames']['collideAfterShortening'].append({'text': t, 'area': key, 'officialName': a['officialName'], 'plate': a['name'],
                                                      'nameId': a['nameId'], 'block': a['blocks'][0], 'point': a['point'],
                                                      'machine': E.machine(a, r['number'])})
# The official name is an alias of its own area only; a plate over the limit gets no code.
# an official name typed with a number of the other area of its plate name is refused
for t in ['%s %s' % (areas.by_key['TON1601']['officialName'], E.pairs(_b('TON1605'))),
          '%s %s' % (areas.by_key['OGO0105']['officialName'] if areas.by_key['OGO0105'].get('officialName') != areas.by_key['OGO0105']['name'] else areas.by_key['OGO0104']['officialName'],
                     E.pairs(_b('OGO0104') if areas.by_key['OGO0105'].get('officialName') != areas.by_key['OGO0105']['name'] else _b('OGO0105')))]:
    try:
        E.parse(areas, t)
        raise SystemExit('should be refused: %s' % t)
    except ValueError as e:
        V['plateNames']['refused'].append({'text': t, 'error': str(e)})
# an area waiting for its commune issues codes under its provisional name (nothing waits for anyone)
a = areas.by_key['KER0606']
V['plateNames']['provisional'] = {'area': 'KER0606', 'officialName': a['officialName'], 'needsCouncilChoice': a.get('needsCouncilChoice'),
                                  'remembered': E.remembered(a, a['blocks'][0][0]), 'machine': E.machine(a, a['blocks'][0][0])}
json.dump(V, open(os.path.join(REPO, 'engine', 'reference', 'test_vectors.json'), 'w'), ensure_ascii=False, indent=1)
print(json.dumps({'spots': V['spots'], 'compounds': [{k2: c[k2] for k2 in ('window', 'area', 'structures', 'walls', 'compounds', 'byRule')} for c in V['compounds']], 'parse': V['parse'], 'prov': V['provisional'], 'sameName': V['sameName']}, ensure_ascii=False, indent=0))
