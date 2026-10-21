#!/usr/bin/env python3
"""Nearest-named-place code areas in the capital: compounds per area -> digits needed."""
import csv, json, math, sys, collections
slug, outdir, kinds = sys.argv[1], sys.argv[2], sys.argv[3].split(',')
st = json.load(open(f'{outdir}/capital-stats.json'))
ratio = st['compounds'] / st['buildings']
B = [(float(r['cx']), float(r['cy'])) for r in csv.DictReader(open(f'{outdir}/cap-buildings.csv'))]
x0 = min(b[0] for b in B); x1 = max(b[0] for b in B); y0 = min(b[1] for b in B); y1 = max(b[1] for b in B)
P = []
for l in open(f'adm/{slug}-pq.geojsonseq'):
    l = l.lstrip('\x1e').strip()
    if not l: continue
    f = json.loads(l); p = f['properties']
    if p.get('place') in kinds and f['geometry']['type'] == 'Point' and p.get('name'):
        x, y = f['geometry']['coordinates']
        if x0 - 0.01 <= x <= x1 + 0.01 and y0 - 0.01 <= y <= y1 + 0.01:
            P.append((x, y, p['name']))
G = collections.defaultdict(list); C = 0.01
for i, (x, y, n) in enumerate(P): G[(int(x / C), int(y / C))].append(i)
cnt = collections.Counter()
for x, y in B:
    gx, gy = int(x / C), int(y / C); best = None; r = 1
    while best is None or r <= 2:
        for dx in range(-r, r + 1):
            for dy in range(-r, r + 1):
                for i in G.get((gx + dx, gy + dy), []):
                    d = (P[i][0] - x) ** 2 + (P[i][1] - y) ** 2
                    if best is None or d < best[0]: best = (d, i)
        r += 1
        if r > 30: break
    cnt[best[1]] += 1
comp = sorted(v * ratio for v in cnt.values())
def q(p): return round(comp[min(len(comp) - 1, int(p * len(comp)))])
res = {'placeKinds': kinds, 'places': len(P), 'areasUsed': len(cnt), 'compoundRatio': round(ratio, 3),
       'compoundsPerArea': {'p10': q(.1), 'p50': q(.5), 'p90': q(.9), 'max': round(comp[-1])},
       'areasFitting': {'3 digits (<=450)': sum(1 for c in comp if c <= 450), '4 digits (<=4500)': sum(1 for c in comp if 450 < c <= 4500),
                        '5 digits (<=45000)': sum(1 for c in comp if 4500 < c <= 45000), 'over': sum(1 for c in comp if c > 45000)},
       'largest': [(P[i][2], round(v * ratio)) for i, v in cnt.most_common(8)]}
json.dump(res, open(f'{outdir}/capital-areas.json', 'w'), ensure_ascii=False, indent=1)
print(json.dumps(res, ensure_ascii=False))
