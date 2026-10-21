#!/usr/bin/env python3
"""Pick real OSM footprints (and OSM wall enclosures) around chosen points for the engine test vectors.
  python3 tools/pick_vectors.py BUILDINGS.geojsonseq CTX.geojsonseq OUT.json
Standard library only; one streaming pass over each file."""
import json, sys, math
WIN = {  # name: (lon, lat, radius m)
    'AMT': (1.2318, 6.1405, 120), 'BE': (1.2484, 6.1423, 120), 'TKL': (1.2247, 6.1517, 120),
    'KARA': (1.1977, 9.5489, 150), 'AGOE': (1.2130, 6.2470, 150),
    'KPALIME': (0.6297, 6.9007, 150), 'TSEVIE': (1.2133, 6.4261, 150),
}
def near(c, w):
    lon, lat, r = w
    return math.hypot((c[0] - lon) * 110600, (c[1] - lat) * 110600) <= r
out = {k: {'buildings': [], 'walls': []} for k in WIN}
def ring_of(g):
    if g['type'] == 'Polygon': return g['coordinates'][0]
    if g['type'] == 'MultiPolygon': return g['coordinates'][0][0]
    if g['type'] == 'LineString' and g['coordinates'][0] == g['coordinates'][-1]: return g['coordinates']
    return None
for path, kind in ((sys.argv[1], 'buildings'), (sys.argv[2], 'walls')):
    for line in open(path, encoding='utf-8'):
        line = line.lstrip('\x1e').strip()
        if not line: continue
        if kind == 'walls' and '"barrier"' not in line: continue
        f = json.loads(line)
        p = f['properties']
        if kind == 'walls' and p.get('barrier') not in ('wall', 'fence', 'hedge'): continue
        r = ring_of(f['geometry'])
        if not r: continue
        c = (sum(x for x, _ in r[:-1]) / (len(r) - 1), sum(y for _, y in r[:-1]) / (len(r) - 1))
        for k, w in WIN.items():
            if near(c, w):
                out[k][kind].append({'id': '%s/%s' % (p.get('@type', 'way'), p.get('@id')), 'tags': {t: p[t] for t in ('building', 'barrier', 'name', 'amenity', 'shop', 'building:levels') if t in p},
                                     'ring': [[round(x, 7), round(y, 7)] for x, y in r]})
json.dump(out, open(sys.argv[3], 'w'), indent=0)
print({k: (len(v['buildings']), len(v['walls'])) for k, v in out.items()})
