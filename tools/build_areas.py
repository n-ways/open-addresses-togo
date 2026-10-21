#!/usr/bin/env python3
"""Build Togo's frozen code-area table, model/areas/areas.json (standard library only).

Inputs (in this repo):
  model/units/keys.geojson     69 Lomé quartiers (OSM admin_level=10, ref = quartier code) + préfectures
  model/units/keys.csv         buildings per quartier (OSM + ML)
  model/units/cantons.geojson  373 cantons (HDX COD-AB Togo admin3, 2021)
  model/areas/osm-places.csv   named places (OpenStreetMap)
and the building centroids: at first issue every footprint (tools/extract-buildings.py writes
<work>/buildings-pts.csv: x = lon, y = lat and the unit, its quartier code or canton p-code), in the
design a 10% sample (CSV x,y; each point counts 10).

  python3 tools/build_areas.py <work>/buildings-pts.csv      every footprint, with its unit
  python3 tools/build_areas.py SAMPLE.csv                    the design's 10% sample

Rules (engine/SPEC.md "Code areas"):
  * Grand Lomé (69 quartiers of the former commune, cantons of Golfe and Agoè-Nyivé): the DAGL's
    addressing is official and comes first wherever it is known; every compound also gets its N-Ways
    code
  * canton areas: 4 digits when compounds x 2 <= 9,000; otherwise split into named-place cells
    (nearest place point inside the canton); a cell still too big gets 5 digits
  * compounds = buildings x 0.79 (Grand Lomé ratio from model/stats/capital-stats.json)
Indexes are frozen once published: quartiers 1-69, cantons 101+, cells 1001+; new areas are appended.
Afterwards tools/name_ranges.py (run at the end) cleans the place words and gives every name its national
range: same-named areas get disjoint blocks, so "Name NNNN" is unique in Togo on its own (SPEC 3.1).
"""
import csv, json, math, os, sys, re, unicodedata, collections

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, 'engine', 'reference'))
import tg_engine as E  # noqa: E402

RATIO = 0.79
# Where the State gives an address, that address is shown first. Grand Lomé (13 communes = préfectures of
# Golfe and Agoè-Nyivé, incl. the former commune of Lomé) is being addressed by the DAGL (street codes
# since 1997, metric entrance numbers 2025-26): its areas carry the official system.
GRAND_LOME = {'Golfe', 'Agoe-Nyive', 'Lome Commune'}
OFFICIAL = {'system': 'DAGL - adressage du Grand Lomé', 'holder': 'District Autonome du Grand Lomé (DAGL), with Edenmap',
            'now': 'legacy street codes (number + quartier code, e.g. 165 AMT)', 'later': 'DAGL street code/name + metric entrance number',
            'nways': 'the official address first wherever it is known; the N-Ways code beside it, with the gate pin and the building profile'}
CAP4 = 9000
PREF_KEYS = {
    'Agoe-Nyive': 'AGN', 'Agou': 'AGO', 'Akebou': 'AKB', 'Amou': 'AMO', 'Anie': 'ANI', 'Assoli': 'ASS', 'Ave': 'AVE',
    'Bas-Mono': 'BMO', 'Bassar': 'BAS', 'Binah': 'BIN', 'Blitta': 'BLI', 'Cinkasse': 'CIN', 'Dankpen': 'DAN',
    'Danyi': 'DNY', 'Doufelgou': 'DOU', 'Est-Mono': 'EMO', 'Golfe': 'GOL', 'Haho': 'HAH', 'Keran': 'KER',
    'Kloto': 'KLO', 'Kozah': 'KOZ', 'Kpele': 'KPE', 'Kpendjal': 'KPD', 'Lacs': 'LAC', 'Lome Commune': 'LOM',
    'Moyen-Mono': 'MMO', 'Naki-Ouest': 'NKO', 'Ogou': 'OGO', 'Oti': 'OTI', 'Oti-Sud': 'OTS', 'Plaine du Mo': 'PMO',
    'Sotouboua': 'SOT', 'Tandjoare': 'TDJ', 'Tchamba': 'TCB', 'Tchaoudjo': 'TCH', 'Tone': 'TON', 'Vo': 'VOG',
    'Wawa': 'WAW', 'Yoto': 'YOT', 'Zio': 'ZIO',
}
PLACE_KINDS = {'city', 'town', 'village', 'hamlet', 'suburb', 'quarter', 'neighbourhood', 'locality'}


def box(geom):
    polys = [geom['coordinates']] if geom['type'] == 'Polygon' else geom['coordinates']
    xs = [p[0] for poly in polys for p in poly[0]]
    ys = [p[1] for poly in polys for p in poly[0]]
    return [round(min(xs), 6), round(min(ys), 6), round(max(xs), 6), round(max(ys), 6)]


def centroid(geom):
    polys = [geom['coordinates']] if geom['type'] == 'Polygon' else geom['coordinates']
    ring = max((p[0] for p in polys), key=len)
    return [round(sum(p[0] for p in ring) / len(ring), 6), round(sum(p[1] for p in ring) / len(ring), 6)]


def main(sample_path):
    units = os.path.join(REPO, 'model', 'units')
    keys = json.load(open(os.path.join(units, 'keys.geojson'), encoding='utf-8'))['features']
    counts = {r['id']: int(r['buildings_total']) for r in csv.DictReader(open(os.path.join(units, 'keys.csv'), encoding='utf-8'))}
    cantons = json.load(open(os.path.join(units, 'cantons.geojson'), encoding='utf-8'))['features']
    places = [r for r in csv.DictReader(open(os.path.join(REPO, 'model', 'areas', 'osm-places.csv'), encoding='utf-8')) if r['place'] in PLACE_KINDS]
    rows = list(csv.DictReader(open(sample_path)))
    full = 'unit' in rows[0]
    F = 1 if full else 10        # each point stands for F buildings
    xk, yk = ('lon', 'lat') if 'lon' in rows[0] else ('x', 'y')
    sample = [(float(r[xk]), float(r[yk]), r.get('unit') or '') for r in rows]
    del rows
    if full:
        counts = collections.Counter(u for _, _, u in sample)

    areas = []
    quartiers = sorted([f for f in keys if f['properties']['kind'] == 'lome-quartier'], key=lambda f: f['properties']['id'])
    for i, f in enumerate(quartiers, start=1):
        p = f['properties']
        comp = round(counts.get(p['id'], 0) * RATIO)
        areas.append({'index': i, 'key': p['id'], 'kind': 'lome-quartier', 'name': p['name'], 'spoken': p['name'],
                      'aliases': [], 'unit': p['id'], 'prefecture': 'Lomé (ancienne commune)', 'box': box(f['geometry']),
                      'point': centroid(f['geometry']), 'estBuildings': counts.get(p['id'], 0), 'estCompounds': comp,
                      'officialSystem': OFFICIAL, 'numberLength': 4 if comp * 2 <= CAP4 else 5})
    geoms = {}
    canton_rows = []
    for i, f in enumerate(sorted(cantons, key=lambda f: f['properties']['pcode']), start=101):
        p = f['properties']
        pk = PREF_KEYS[p['prefecture']]
        key = pk + p['pcode'][-2:]
        a = {'index': i, 'key': key, 'kind': 'canton', 'name': p['name'], 'spoken': p['name'], 'aliases': [],
             'unit': p['pcode'], 'prefecture': p['prefecture'], 'region': p['region'], 'box': box(f['geometry']),
             'point': centroid(f['geometry'])}
        geoms[i] = f['geometry']
        canton_rows.append(a)
        areas.append(a)
    # buildings per canton: every footprint with its unit, or the 10% sample by polygon
    per = collections.Counter()
    members = collections.defaultdict(list)
    by_unit = {a['unit']: a['index'] for a in canton_rows}
    for x, y, u in sample:
        if full:
            if u in by_unit:
                per[by_unit[u]] += 1
                members[by_unit[u]].append((x, y))
            continue
        for a in canton_rows:
            x0, y0, x1, y1 = a['box']
            if x0 <= x <= x1 and y0 <= y <= y1 and E.polygon_contains(geoms[a['index']], x, y):
                per[a['index']] += 1
                members[a['index']].append((x, y))
                break
    next_cell = 1001
    for a in canton_rows:
        b = per[a['index']] * F
        a['estBuildings'] = b
        a['estCompounds'] = round(b * RATIO)
        if a['unit'] == 'TG030501':  # former commune of Lomé: covered by the 69 quartier areas
            a['numberLength'] = None
            a['officialSystem'] = OFFICIAL
            a['cells'] = [q['index'] for q in areas if q['kind'] == 'lome-quartier']
            a['note'] = 'Lomé commune: points fall in a quartier polygon, or in the nearest quartier'
            continue
        if a['prefecture'] in GRAND_LOME:  # Grand Lomé: the DAGL address comes first; N-Ways codes beside it
            a['officialSystem'] = OFFICIAL
        if a['estCompounds'] * 2 <= CAP4:
            a['numberLength'] = 4
            continue
        pts = []
        seen = set()
        for r in places:
            x, y = float(r['lon']), float(r['lat'])
            x0, y0, x1, y1 = a['box']
            if x0 <= x <= x1 and y0 <= y <= y1 and E.polygon_contains(geoms[a['index']], x, y):
                k = E.norm_name(r['name'])
                if k not in seen:
                    seen.add(k)
                    pts.append((r['name'], r['place'], x, y))
        if len(pts) < 2:
            a['numberLength'] = 4 if a['estCompounds'] * 2 <= CAP4 else 5
            a['note'] = 'too few named places to split; split when village names are collected'
            continue
        m_lat, m_lon = E.metres((a['box'][1] + a['box'][3]) / 2)
        cnt = collections.Counter()
        for x, y in members[a['index']]:
            j = min(range(len(pts)), key=lambda k: ((pts[k][2] - x) * m_lon) ** 2 + ((pts[k][3] - y) * m_lat) ** 2)
            cnt[j] += 1
        a['numberLength'] = None
        a['cells'] = []
        pts_sorted = sorted(range(len(pts)), key=lambda k: E.norm_name(pts[k][0]))
        for rank, j in enumerate(pts_sorted, start=1):
            name, kind, x, y = pts[j]
            comp = round(cnt[j] * F * RATIO)
            cell = {'index': next_cell, 'key': '%s%02d' % (a['key'], rank) if rank < 100 else '%s%03d' % (a['key'], rank),
                    'kind': 'cell', 'name': name, 'spoken': name, 'aliases': [], 'placeKind': kind, 'parent': a['index'],
                    'prefecture': a['prefecture'], 'region': a.get('region'), 'point': [x, y], 'box': a['box'],
                    'estBuildings': cnt[j] * F, 'estCompounds': comp, 'numberLength': 4 if comp * 2 <= CAP4 else 5}
            if a.get('officialSystem'):
                cell['officialSystem'] = OFFICIAL
            if cell['numberLength'] == 5:
                cell['note'] = 'split further when quartier/village names are collected'
            a['cells'].append(next_cell)
            areas.append(cell)
            next_cell += 1
    out = {'country': 'TG', 'version': '1.0', 'frozen': False,
           'note': 'Indexes and keys freeze at first issue; afterwards areas are only appended.',
           'compoundRatio': RATIO, 'capacity4': CAP4, 'areas': areas}
    json.dump(out, open(os.path.join(REPO, 'model', 'areas', 'areas.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
    num = [a for a in areas if a.get('numberLength')]
    comps = sum(a['estCompounds'] for a in num)
    c4 = sum(a['estCompounds'] for a in num if a['numberLength'] == 4)
    print(json.dumps({'codeAreas': len(num), 'quartiers': len(quartiers), 'cantons': len(canton_rows),
                      'splitCantons': sum(1 for a in canton_rows if a.get('cells') and a['unit'] != 'TG030501'),
                      'cells': sum(1 for a in areas if a['kind'] == 'cell'),
                      'areas4': sum(1 for a in num if a['numberLength'] == 4), 'areas5': sum(1 for a in num if a['numberLength'] == 5),
                      'estCompounds': comps, 'shareOfCompoundsIn4digitAreas': round(c4 / comps, 3),
                      'largest5': sorted(((a['estCompounds'], a['key'], a['name']) for a in num if a['numberLength'] == 5), reverse=True)[:15]},
                     ensure_ascii=False, indent=1))
    import name_ranges
    name_ranges.main()


if __name__ == '__main__':
    main(sys.argv[1])
