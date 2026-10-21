#!/usr/bin/env python3
import csv, json, sys, collections
slug, outdir, ratio, kinds = sys.argv[1], sys.argv[2], float(sys.argv[3]), sys.argv[4].split(',')
B = [(float(r['x']), float(r['y'])) for r in csv.DictReader(open(f'{outdir}/sample.csv'))]
P = []
for l in open(f'adm/{slug}-pq.geojsonseq'):
    l = l.lstrip('\x1e').strip()
    if not l: continue
    f = json.loads(l); p = f['properties']
    if p.get('place') in kinds and f['geometry']['type'] == 'Point' and p.get('name'):
        P.append((*f['geometry']['coordinates'], p['name'], p['place']))
C = 0.02
G = collections.defaultdict(list)
for i, p in enumerate(P): G[(int(p[0] // C), int(p[1] // C))].append(i)
cnt = collections.Counter(); far = 0
for x, y in B:
    gx, gy = int(x // C), int(y // C); best = None
    for r in range(0, 40):
        for dx in range(-r, r + 1):
            for dy in (range(-r, r + 1) if abs(dx) == r else (-r, r)):
                for i in G.get((gx + dx, gy + dy), []):
                    d = (P[i][0] - x) ** 2 + (P[i][1] - y) ** 2
                    if best is None or d < best[0]: best = (d, i)
        if best is not None and r >= 1: break
    if best is None: far += 1; continue
    cnt[best[1]] += 1
comp = sorted(v * 10 * ratio for v in cnt.values())
def q(p): return round(comp[min(len(comp) - 1, int(p * len(comp)))])
tot = sum(comp)
fit = collections.Counter()
for c in comp: fit['3' if c <= 450 else '4' if c <= 4500 else '5' if c <= 45000 else '6+'] += 1
share = collections.Counter()
for c in comp: share['3' if c <= 450 else '4' if c <= 4500 else '5' if c <= 45000 else '6+'] += c
res = {'placeKinds': kinds, 'placePoints': len(P), 'areasWithBuildings': len(cnt), 'compoundRatio': ratio,
       'estCompounds': round(tot), 'compoundsPerArea': {'p10': q(.1), 'p50': q(.5), 'p90': q(.9), 'p99': q(.99), 'max': round(comp[-1])},
       'areasByDigits': dict(fit), 'compoundShareByDigits': {k: round(v / tot, 3) for k, v in share.items()},
       'largest': [(P[i][2], P[i][3], round(v * 10 * ratio)) for i, v in cnt.most_common(12)]}
json.dump(res, open(f'{outdir}/national-areas.json', 'w'), ensure_ascii=False, indent=1)
print(json.dumps(res, ensure_ascii=False))
