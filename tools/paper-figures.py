#!/usr/bin/env python3
"""The data behind the paper's figures, from the published files only.

  python3 tools/paper-figures.py

Reads registry/*.csv.gz, engine/data/register.json, model/units/cantons.geojson and
model/stats/building-stats.json, and writes the small tables that docs/figures/*.tex plot:

  density.dat        compounds per 0.04-degree cell (about 4.4 km) (cell centre, log10 count)
  regions.dat        region outlines (cantons dissolved by region), NaN rows between rings
  towns.dat          the towns labelled on the map
  area-sizes.dat     code areas by compound count (log-spaced bins), split by number length
  frj.dat            Fréau-Jardin's compounds in number order, in Hilbert-grid and spot-cell units
  blocks.dat         the blocks of the names Lom-Nava and Tokpo, with first-issue layout
  sources.dat        footprints by region and source; compounds by number length

Standard library only; one pass over the registry, one row at a time.
"""
import collections, csv, glob, gzip, json, math, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
OUT = os.path.join(REPO, 'docs', 'figures')
sys.path.insert(0, os.path.join(REPO, 'engine', 'reference'))
import tg_engine as E  # noqa: E402

CELL = 0.04
TOWNS = [('Lomé', 6.137, 1.212), ('Tsévié', 6.426, 1.213), ('Aného', 6.228, 1.592), ('Kpalimé', 6.900, 0.630),
         ('Atakpamé', 7.527, 1.126), ('Sokodé', 8.983, 1.133), ('Bassar', 9.250, 0.785), ('Kara', 9.551, 1.186),
         ('Mango', 10.359, 0.471), ('Dapaong', 10.862, 0.205)]


def write(name, header, rows):
    with open(os.path.join(OUT, name), 'w', encoding='utf-8') as f:
        f.write(header + '\n')
        for r in rows:
            f.write(' '.join(str(x) for x in r) + '\n')


def dp(pts, tol):
    """Douglas-Peucker simplification of an open polyline."""
    if len(pts) < 3:
        return pts
    if pts[0] == pts[-1]:  # a closed ring: split it at the point farthest from its start
        far = max(range(len(pts)), key=lambda i: (pts[i][0] - pts[0][0]) ** 2 + (pts[i][1] - pts[0][1]) ** 2)
        return dp(pts[:far + 1], tol)[:-1] + dp(pts[far:], tol)
    (x0, y0), (x1, y1) = pts[0], pts[-1]
    dx, dy = x1 - x0, y1 - y0
    norm = math.hypot(dx, dy) or 1e-12
    best, idx = 0.0, 0
    for i in range(1, len(pts) - 1):
        d = abs(dy * (pts[i][0] - x0) - dx * (pts[i][1] - y0)) / norm
        if d > best:
            best, idx = d, i
    if best <= tol:
        return [pts[0], pts[-1]]
    return dp(pts[:idx + 1], tol)[:-1] + dp(pts[idx:], tol)


def outlines(features, group, tol=0.004):
    """Dissolve polygons by `group`: keep the edges used once within a group, chain them into lines."""
    rings = []
    by = collections.defaultdict(list)
    for f in features:
        by[group(f)].append(f['geometry'])
    for _, geoms in sorted(by.items()):
        count = collections.Counter()
        for g in geoms:
            polys = [g['coordinates']] if g['type'] == 'Polygon' else g['coordinates']
            for poly in polys:
                for ring in poly:
                    for a, b in zip(ring, ring[1:]):
                        a, b = (round(a[0], 6), round(a[1], 6)), (round(b[0], 6), round(b[1], 6))
                        if a != b:
                            count[(min(a, b), max(a, b))] += 1
        nxt = collections.defaultdict(list)
        for (a, b), c in count.items():
            if c == 1:
                nxt[a].append(b)
                nxt[b].append(a)
        seen = set()
        for start in sorted(nxt):
            for b0 in nxt[start]:
                if (start, b0) in seen:
                    continue
                line, a, b = [start], start, b0
                while True:
                    seen.add((a, b))
                    seen.add((b, a))
                    line.append(b)
                    cand = [c for c in nxt[b] if (b, c) not in seen]
                    if not cand:
                        break
                    a, b = b, cand[0]
                xs, ys = [p[0] for p in line], [p[1] for p in line]
                if max(xs) - min(xs) + max(ys) - min(ys) > 0.03:  # drop the slivers of unmatched edges
                    rings.append(dp(line, tol))
    return rings


def main():
    reg = E.load_json(os.path.join(REPO, 'engine', 'data', 'register.json'))
    areas = E.Areas()
    stats = E.load_json(os.path.join(REPO, 'model', 'stats', 'building-stats.json'))

    # 1. density of compounds
    cells = collections.Counter()
    frj = []
    for path in sorted(glob.glob(os.path.join(REPO, 'registry', '*.csv.gz'))):
        if path.endswith('areas.csv.gz'):
            continue
        with gzip.open(path, 'rt', encoding='utf-8', newline='') as f:
            for r in csv.DictReader(f):
                lat, lon = float(r['entrance_lat']), float(r['entrance_lng'])
                cells[(math.floor(lon / CELL), math.floor(lat / CELL))] += 1
                if r['zone'] == 'FRJ':
                    frj.append((int(r['number']), lat, lon))
    write('density.dat', 'lon lat logn',
          [('%.3f' % ((x + 0.5) * CELL), '%.3f' % ((y + 0.5) * CELL), '%.3f' % math.log10(n))
           for (x, y), n in sorted(cells.items())])

    cantons = E.load_json(os.path.join(REPO, 'model', 'units', 'cantons.geojson'))['features']
    rows = []
    for line in outlines(cantons, lambda f: f['properties']['region']):
        rows.extend(('%.4f' % x, '%.4f' % y) for x, y in line)
        rows.append(('nan', 'nan'))
    write('regions.dat', 'lon lat', rows)
    write('towns.dat', 'lon lat name', [(lon, lat, name) for name, lat, lon in TOWNS])

    # 2. code areas by size
    edges = [10 ** (k / 4.0) for k in range(0, 19)]  # 1 .. 31,623 compounds, quarter decades
    edges.append(10 ** 4.75)
    hist = collections.defaultdict(lambda: [0, 0])
    for a in reg['areas']:
        c = a.get('compounds') or 0
        if not a.get('numberLength') or c <= 0:
            continue
        k = int(math.floor(math.log10(c) * 4))
        hist[k][0 if a['numberLength'] == 4 else 1] += 1
    write('area-sizes.dat', 'logc four five',
          [('%.3f' % ((k + 0.5) / 4.0), hist[k][0], hist[k][1]) for k in range(0, 19)])

    # 3 and 5. Fréau-Jardin: Hilbert grid and spot cells
    a = areas.by_key['FRJ']
    x0, y0, x1, y1 = a['box']
    ox, oy, nx, ny = E._frame(a)
    n = (1 << E.HILBERT_ORDER) - 1
    frj.sort()
    write('frj.dat', 'number hx hy sx sy',
          [(num, '%.1f' % ((lon - x0) / (x1 - x0) * n), '%.1f' % ((lat - y0) / (y1 - y0) * n),
            '%.2f' % ((lon - ox) / E.CELL_DEG), '%.2f' % ((lat - oy) / E.CELL_DEG)) for num, lat, lon in frj])

    # 4. blocks of two names
    rows = []
    for name in ('Lom-Nava', 'Tokpo'):
        group = sorted(areas.by_name[E.name_key(name)], key=lambda x: x['blocks'][0][0])
        for j, g in enumerate(group):
            ra = next(r for r in reg['areas'] if r['key'] == g['key'])
            lo, hi = g['blocks'][0]
            c = ra['compounds']
            cap = hi - lo + 1
            step = max(1, int(cap // (c * 1.5)))
            part = 4 if hi <= 9999 else 5
            row = {('Lom-Nava', 4): 0, ('Lom-Nava', 5): 1, ('Tokpo', 4): 2}[(name, part)]
            pref = (g.get('prefecture') or '').split(' (')[0]
            rows.append((row, part, j % 2, name, g['key'], pref.replace(' ', '~'), c, lo, hi,
                         lo + (c - 1) * step, lo + int(cap * 2 // 3)))
    write('blocks.dat', 'row part alt name key prefecture compounds lo hi last tail', rows)

    # 6 and 7. sources and digits by region
    order = ['Grand Lomé', 'Maritime', 'Plateaux', 'Centrale', 'Kara', 'Savanes']
    rows = []
    for i, r in enumerate(order):
        v = stats['regions'][r]
        rows.append((i, r.replace(' ', '~'), v['fromOpenStreetMap'], v['structures'] - v['fromOpenStreetMap'],
                     v['compoundsByDigits']['4'], v['compoundsByDigits']['5'], v['compounds']))
    write('sources.dat', 'i region osm ml four five compounds', rows)


if __name__ == '__main__':
    main()
