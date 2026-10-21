#!/usr/bin/env python3
"""The frozen register of Togo's code areas, at first issue (engine/SPEC.md 3).

  python3 tools/build-register.py <work> [--freeze]

1. Every numbered area's compound count becomes the real one (<work>/area-counts.json, written by
   tools/issue_registry.py group); tools/name_ranges.py then sizes and places the blocks of every
   name on those counts (SPEC 3.1 rule 4).
2. Writes engine/data/register.json (what the engines load: every area with its kind, key, index,
   names, name id and key, blocks, box, place point, parent and cells, the official system where the
   State addresses, the names table) and engine/data/units.json (the quartier and canton polygons
   for the point lookup), and model/stats/register.json (the counts in the papers).
   With --freeze the table is marked frozen: from then on keys, indexes, boxes and blocks never move.
"""
import collections, datetime, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(REPO, 'engine', 'reference'))

work = os.path.abspath(sys.argv[1])
freeze = '--freeze' in sys.argv
AREAS = os.path.join(REPO, 'model', 'areas', 'areas.json')

counts = json.load(open(os.path.join(work, 'area-counts.json')))
data = json.load(open(AREAS, encoding='utf-8'))
for a in data['areas']:
    if a.get('numberLength'):
        a['estCompounds'] = counts.get(a['key'], 0)
        a['compounds'] = counts.get(a['key'], 0)
if freeze:
    data['frozen'] = True
    data['version'] = '1.0'
    data['note'] = 'Frozen at first issue on 20 October 2026: keys, indexes, boxes and blocks never move; areas are only appended.'
json.dump(data, open(AREAS, 'w', encoding='utf-8'), ensure_ascii=False, indent=0)

import name_ranges  # noqa: E402
name_ranges.main()

data = json.load(open(AREAS, encoding='utf-8'))
names = json.load(open(os.path.join(REPO, 'model', 'areas', 'names.json'), encoding='utf-8'))
KEEP = ('index', 'key', 'kind', 'name', 'officialName', 'aliases', 'unit', 'prefecture', 'region', 'box', 'point', 'parent',
        'cells', 'numberLength', 'nameId', 'nameKey', 'blocks', 'needsCouncilChoice', 'plateCandidates', 'compounds')
areas = []
for a in data['areas']:
    r = {k: a[k] for k in KEEP if k in a}
    if a.get('officialSystem'):
        r['officialSystem'] = a['officialSystem']['system']
    areas.append(r)
reg = {'about': 'N-Ways Addressing for Togo: the frozen register of code areas (engine/SPEC.md 3). Built by tools/build-register.py.',
       'frozen': bool(data.get('frozen')), 'builtAt': datetime.date.today().isoformat(), 'areas': areas,
       'names': [{'id': n['id'], 'key': n['key']} for n in names['names']]}
os.makedirs(os.path.join(REPO, 'engine', 'data'), exist_ok=True)
json.dump(reg, open(os.path.join(REPO, 'engine', 'data', 'register.json'), 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
units = {}
for fname, idf in (('keys.geojson', 'id'), ('cantons.geojson', 'pcode')):
    for f in json.load(open(os.path.join(REPO, 'model', 'units', fname), encoding='utf-8'))['features']:
        if fname == 'keys.geojson' and f['properties'].get('kind') != 'lome-quartier':
            continue
        g = f['geometry']
        polys = [g['coordinates']] if g['type'] == 'Polygon' else g['coordinates']
        units[f['properties'][idf]] = [[[[round(x, 6), round(y, 6)] for x, y in ring] for ring in poly] for poly in polys]
json.dump(units, open(os.path.join(REPO, 'engine', 'data', 'units.json'), 'w'), separators=(',', ':'))

num = [a for a in data['areas'] if a.get('numberLength')]
dig = collections.Counter()
for a in num:
    dig[len(str(a['blocks'][0][0]))] += a.get('compounds', 0)
stats = {'areas': len(num), 'areasWithCompounds': sum(1 for a in num if a.get('compounds')),
         'compounds': sum(a.get('compounds', 0) for a in num),
         'grandLome': {'areas': sum(1 for a in num if a.get('officialSystem')),
                       'compounds': sum(a.get('compounds', 0) for a in num if a.get('officialSystem'))},
         'nameKeys': len({a['nameKey'] for a in num}),
         'sharedNames': sum(1 for k, v in collections.Counter(a['nameKey'] for a in num).items() if v > 1),
         'areasInSharedNames': sum(v for k, v in collections.Counter(a['nameKey'] for a in num).items() if v > 1),
         'areasByDigits': dict(sorted(collections.Counter(len(str(a['blocks'][0][0])) for a in num).items())),
         'compoundsByDigits': dict(sorted(dig.items())),
         'needsCouncilChoice': sum(1 for a in num if a.get('needsCouncilChoice')),
         'largestArea': max(({'key': a['key'], 'name': a['name'], 'compounds': a.get('compounds', 0)} for a in num), key=lambda x: x['compounds'])}
json.dump(stats, open(os.path.join(REPO, 'model', 'stats', 'register.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print(json.dumps(stats, ensure_ascii=False))
