#!/usr/bin/env python3
"""Capital statistics: building profile inference + compound grouping (v0 rules).

  analyse.py OUTDIR PARAMS_JSON

PARAMS: {"annex_m2": 30, "attach_m": 6, "hut_m2": 0|40, "hut_gap_m": 3, "hut_max": 25,
         "encl_max_m2": 6000}
Writes OUTDIR/capital-stats.json
"""
import csv, json, math, sys, collections, statistics

out, params = sys.argv[1], json.loads(sys.argv[2])
A_ANNEX, D_ATTACH = params['annex_m2'], params['attach_m']
HUT_M2, HUT_GAP, HUT_MAX = params.get('hut_m2', 0), params.get('hut_gap_m', 3), params.get('hut_max', 25)
ENCL_MAX = params.get('encl_max_m2', 6000)

B = {}
for r in csv.DictReader(open(f'{out}/cap-buildings.csv')):
    i = int(r['id'])
    a, p = float(r['area'] or 0), float(r['perim'] or 0)
    h = None
    try:
        h = float((r['height'] or '').replace('m', '').strip()) if r['height'] else None
    except ValueError:
        h = None
    lv = None
    try:
        lv = int(float(r['levels'])) if r['levels'] else None
    except ValueError:
        lv = None
    B[i] = dict(src=r['src'], cx=float(r['cx']), cy=float(r['cy']), area=a, perim=p, btag=r['btag'] or None,
                levels=lv, h=h, named=r['named'] == '1', poi=r['poi'] or None, cats=r['cats'] or None,
                eid=int(r['eid']) if r['eid'] else None, ea=float(r['ea']) if r['ea'] else None, landuse=r['landuse'] or None)

# ---------- class inference ----------
BTAG = {
    'house': 'residential', 'residential': 'residential', 'detached': 'residential', 'apartments': 'residential',
    'hut': 'residential', 'stilt_house': 'residential', 'semidetached_house': 'residential', 'terrace': 'residential',
    'dormitory': 'residential', 'bungalow': 'residential',
    'commercial': 'commercial', 'retail': 'commercial', 'kiosk': 'commercial', 'supermarket': 'commercial', 'shop': 'commercial',
    'office': 'office', 'hotel': 'hospitality',
    'school': 'education', 'college': 'education', 'university': 'education', 'kindergarten': 'education',
    'hospital': 'health', 'clinic': 'health',
    'church': 'religious', 'mosque': 'religious', 'chapel': 'religious', 'cathedral': 'religious', 'temple': 'religious', 'religious': 'religious',
    'government': 'government', 'public': 'government', 'civic': 'government', 'townhall': 'government', 'military': 'government', 'barracks': 'government', 'fire_station': 'government',
    'industrial': 'industrial', 'warehouse': 'industrial', 'hangar': 'industrial', 'factory': 'industrial', 'manufacture': 'industrial', 'storage_tank': 'industrial',
    'train_station': 'transport', 'transportation': 'transport', 'garage': 'transport', 'garages': 'transport', 'parking': 'transport',
    'farm': 'agricultural', 'barn': 'agricultural', 'stable': 'agricultural', 'greenhouse': 'agricultural', 'cowshed': 'agricultural',
    'construction': 'under_construction', 'ruins': 'ruin', 'shed': 'annex', 'roof': 'annex', 'toilets': 'annex',
}
CAT = {
    'shop': 'commercial', 'supermarket': 'commercial', 'market': 'commercial', 'pharmacy': 'health', 'bank': 'commercial',
    'pos': 'commercial', 'phones': 'commercial', 'salon': 'commercial', 'mechanic': 'commercial', 'carwash': 'commercial',
    'vulcanizer': 'commercial', 'petrol': 'commercial', 'food': 'commercial', 'bar': 'commercial', 'cafe': 'commercial',
    'fastfood': 'commercial', 'hotel': 'hospitality', 'school': 'education', 'hospital': 'health', 'church': 'religious',
    'mosque': 'religious', 'police': 'government', 'office': 'office', 'motorpark': 'transport', 'attraction': 'leisure',
    'parking': 'transport', 'charging': 'transport',
}
LANDUSE = {'industrial': 'industrial', 'commercial': 'commercial', 'retail': 'commercial', 'military': 'government',
           'religious': 'religious', 'farmyard': 'agricultural', 'farmland': 'agricultural', 'education': 'education',
           'railway': 'transport', 'port': 'transport'}


def infer(b):
    ev = []
    if b['btag'] and b['btag'] not in ('yes',):
        c = BTAG.get(b['btag'])
        if c:
            ev.append((c, 0.85, 'osm:building'))
    if b['poi']:
        ev.append((CAT.get(b['poi'], 'commercial'), 0.75, 'osm:poi-tag'))
    if b['cats']:
        cs = [CAT.get(c, 'commercial') for c in b['cats'].split('|')]
        top = collections.Counter(cs).most_common(1)[0][0]
        ev.append((top, 0.65, 'places:inside'))
    if b['landuse'] in LANDUSE:
        ev.append((LANDUSE[b['landuse']], 0.5, 'osm:landuse'))
    if not ev:
        if b['area'] < 6:
            ev.append(('annex', 0.4, 'size'))
        elif b['area'] > 2500:
            ev.append(('industrial', 0.3, 'size'))  # large sheds: warehouses, factories, markets
        else:
            ev.append(('residential', 0.55 if b['landuse'] == 'residential' else 0.45, 'default'))
    ev.sort(key=lambda e: -e[1])
    cls, conf, src = ev[0]
    if len({e[0] for e in ev}) > 1 and cls == 'residential' and any(e[0] == 'commercial' for e in ev):
        cls, conf, src = 'mixed', 0.6, 'agreement'
    agree = sum(1 for e in ev[1:] if e[0] == cls)
    conf = min(0.95, conf + 0.05 * agree)
    return cls, round(conf, 2), src


def floors(b):
    if b['levels']:
        return max(1, b['levels']), 'osm:building:levels'
    if b['h'] is not None and b['h'] > 0:
        return max(1, int((b['h'] - 1.5) / 3.0 + 0.5)), ('osm:height' if b['src'] == 'osm' else 'ml:h')
    return 1, 'default'


def aspect(a, p):
    q = p / 4.0
    d = q * q - a
    if a <= 0 or d <= 0:
        return 1.0
    s = math.sqrt(d)
    return (q + s) / max(q - s, 1e-6)


for b in B.values():
    b['cls'], b['conf'], b['csrc'] = infer(b)
    b['floors'], b['fsrc'] = floors(b)
    b['floor_area'] = b['area'] * b['floors']
    b['aspect'] = aspect(b['area'], b['perim'])

# ---------- compound grouping ----------
parent = {i: i for i in B}
rule = {i: 'single' for i in B}


def find(x):
    while parent[x] != x:
        parent[x] = parent[parent[x]]
        x = parent[x]
    return x


def union(a, b):
    ra, rb = find(a), find(b)
    if ra != rb:
        parent[rb] = ra


size_of = collections.Counter()
# 1. enclosures
by_e = collections.defaultdict(list)
for i, b in B.items():
    if b['eid'] is not None and b['ea'] and b['ea'] <= ENCL_MAX:
        by_e[b['eid']].append(i)
estates = 0
for e, ms in by_e.items():
    for m in ms[1:]:
        union(ms[0], m)
    for m in ms:
        rule[m] = 'enclosure'
estates = sum(1 for i, b in B.items() if b['eid'] and b['ea'] and b['ea'] > ENCL_MAX)

near = collections.defaultdict(list)
for r in csv.DictReader(open(f'{out}/cap-pairs.csv')):
    a, b, g = int(r['a']), int(r['b']), float(r['gap'])
    near[a].append((g, b))
    near[b].append((g, a))
# 2. annexes attach to the nearest main structure
for i, b in B.items():
    if rule[i] != 'single' or b['area'] >= A_ANNEX:
        continue
    cands = sorted((g, j) for g, j in near[i] if g <= D_ATTACH and B[j]['area'] >= A_ANNEX)
    if cands:
        union(cands[0][1], i)
        rule[i] = 'annex'
        if rule[cands[0][1]] == 'single':
            rule[cands[0][1]] = 'annex-host'
# 3. hut clusters (round huts and small rooms, compounds without walls)
if HUT_M2:
    members = collections.Counter(find(i) for i in B)
    for i, b in B.items():
        if b['area'] >= HUT_M2 or rule[i] == 'enclosure':
            continue
        for g, j in near[i]:
            if g <= HUT_GAP and B[j]['area'] < HUT_M2 and rule[j] != 'enclosure':
                ri, rj = find(i), find(j)
                if ri != rj and members[ri] + members[rj] <= HUT_MAX:
                    parent[rj] = ri
                    members[ri] += members[rj]
                    rule[i] = rule[i] if rule[i] != 'single' else 'hut-cluster'
                    rule[j] = rule[j] if rule[j] != 'single' else 'hut-cluster'

groups = collections.defaultdict(list)
for i in B:
    groups[find(i)].append(i)

CONF = {'enclosure': 0.85, 'annex': 0.6, 'annex-host': 0.6, 'hut-cluster': 0.5, 'single': 0.4}


def compound_class(ms):
    dw = [m for m in ms if B[m]['cls'] in ('residential',) and B[m]['area'] >= A_ANNEX]
    com = [m for m in ms if B[m]['cls'] in ('commercial', 'office', 'hospitality')]
    inst = [m for m in ms if B[m]['cls'] in ('education', 'health', 'religious', 'government')]
    ind = [m for m in ms if B[m]['cls'] == 'industrial']
    rows = [m for m in dw if B[m]['aspect'] >= 3.0 and B[m]['area'] >= 40]
    if inst:
        return 'institutional'
    if any(B[m]['cls'] == 'mixed' for m in ms) or (dw and com):
        return 'mixed'
    if com and not dw:
        return 'commercial'
    if ind and not dw:
        return 'industrial'
    if dw:
        tall = [m for m in dw if B[m]['floors'] >= 3]
        if tall:
            return 'residential-multi-storey'
        if len(dw) >= 2 or rows:
            return 'residential-multi-household'
        return 'residential-one-household'
    return 'other'


def q(xs, ps=(0.1, 0.25, 0.5, 0.75, 0.9)):
    xs = sorted(xs)
    if not xs:
        return {}
    return {f'p{int(p*100)}': round(xs[min(len(xs) - 1, int(p * len(xs)))], 1) for p in ps}


comp_stats = collections.Counter()
struct_hist = collections.Counter()
comp_rule = collections.Counter()
enc_areas = []
comp_floor = []
for root, ms in groups.items():
    n = len(ms)
    struct_hist['1' if n == 1 else '2' if n == 2 else '3-5' if n <= 5 else '6-10' if n <= 10 else '11+'] += 1
    comp_stats[compound_class(ms)] += 1
    r = max((rule[m] for m in ms), key=lambda x: CONF[x])
    comp_rule[r] += 1
    comp_floor.append(sum(B[m]['floor_area'] for m in ms))
    if B[ms[0]]['eid'] is not None and rule[ms[0]] == 'enclosure':
        enc_areas.append(B[ms[0]]['ea'])

cls_mix = collections.Counter(b['cls'] for b in B.values())
cls_src = collections.Counter(b['csrc'] for b in B.values())
n = len(B)
stats = {
    'buildings': n,
    'bySource': dict(collections.Counter(b['src'] for b in B.values())),
    'classMix': {k: {'count': v, 'share': round(v / n, 4)} for k, v in cls_mix.most_common()},
    'classEvidence': dict(cls_src.most_common()),
    'meanClassConfidence': round(statistics.mean(b['conf'] for b in B.values()), 3),
    'footprintM2': q([b['area'] for b in B.values()]),
    'perimeterM': q([b['perim'] for b in B.values()]),
    'heightM': q([b['h'] for b in B.values() if b['h'] is not None]),
    'withHeight': round(sum(1 for b in B.values() if b['h'] is not None) / n, 4),
    'floors': dict(collections.Counter(min(b['floors'], 6) for b in B.values()).most_common()),
    'floorSource': dict(collections.Counter(b['fsrc'] for b in B.values()).most_common()),
    'floorAreaTotalM2': round(sum(b['floor_area'] for b in B.values())),
    'footprintAreaTotalM2': round(sum(b['area'] for b in B.values())),
    'sizeBands': dict(collections.Counter(
        ('<10' if b['area'] < 10 else '10-30' if b['area'] < 30 else '30-80' if b['area'] < 80 else '80-200' if b['area'] < 200
         else '200-1000' if b['area'] < 1000 else '1000+') for b in B.values())),
    'compounds': len(groups),
    'structuresPerCompound': dict(struct_hist),
    'compoundsByRule': dict(comp_rule),
    'compoundClass': dict(comp_stats.most_common()),
    'mappedEnclosureAreaM2': q(enc_areas),
    'compoundFloorAreaM2': q(comp_floor),
    'buildingsInEstateEnclosures': estates,
    'params': params,
}
json.dump(stats, open(f'{out}/capital-stats.json', 'w'), indent=1)
print(json.dumps({k: stats[k] for k in ('buildings', 'compounds', 'structuresPerCompound', 'compoundsByRule', 'compoundClass', 'classMix', 'footprintM2', 'heightM', 'withHeight', 'floors')}, indent=0))
