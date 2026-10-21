#!/usr/bin/env python3
"""The border the server ships: engine/data/border.json.

  python3 tools/make-border.py <work folder>

Reads <work>/country.geojson (tools/prepare-inputs.py: OpenStreetMap's admin_level 2 boundary of Togo),
simplifies every ring by Douglas-Peucker at 50 m in local metres, and writes the outline with
coordinates to 6 decimals and, in its properties, the source relation, the tolerance (300 m) and the
measured deviation of the simplified line from the original (`deviationM`: the largest distance of an
original vertex from its simplified edge, plus the rounding). engine/reference/border.py allows a point
only within 300 m minus that deviation of the simplified outline, so the 300 m stays true of the real
border. Standard library only.
"""
import json
import math
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, 'engine', 'reference'))
import border as B  # noqa: E402

SIMPLIFY_M = 50.0
OUT = os.path.join(REPO, 'engine', 'data', 'border.json')


def seg_d(p, a, b):
    vx, vy = b[0] - a[0], b[1] - a[1]
    ll = vx * vx + vy * vy
    t = min(1.0, max(0.0, ((p[0] - a[0]) * vx + (p[1] - a[1]) * vy) / ll)) if ll > 0 else 0.0
    return math.hypot(p[0] - a[0] - t * vx, p[1] - a[1] - t * vy)


def simplify(ring, eps):
    """Douglas-Peucker on a closed ring in local metres; returns the kept points (closed) and the
    largest distance of a dropped vertex from the edge that replaced it."""
    pts = ring[:-1] if ring[0] == ring[-1] else ring[:]
    lat0 = sum(p[1] for p in pts) / len(pts)
    m_lat, m_lon = B.metres(lat0)
    xy = [(p[0] * m_lon, p[1] * m_lat) for p in pts]
    far = max(range(len(xy)), key=lambda i: (xy[i][0] - xy[0][0]) ** 2 + (xy[i][1] - xy[0][1]) ** 2)
    xy.append(xy[0])
    keep = {0, far, len(xy) - 1}
    stack, dev = [(0, far), (far, len(xy) - 1)], 0.0
    while stack:
        i, j = stack.pop()
        best, k = -1.0, None
        for m in range(i + 1, j):
            d = seg_d(xy[m], xy[i], xy[j])
            if d > best:
                best, k = d, m
        if k is None:
            continue
        if best > eps:
            keep.add(k)
            stack += [(i, k), (k, j)]
        else:
            dev = max(dev, best)
    out = [pts[i % len(pts)] for i in sorted(keep)]
    return out, dev


def main(work):
    src = json.load(open(os.path.join(work, 'country.geojson'), encoding='utf-8'))
    feat = src['features'][0] if src.get('type') == 'FeatureCollection' else src
    geom = feat.get('geometry', feat)
    polys = [geom['coordinates']] if geom['type'] == 'Polygon' else geom['coordinates']
    out, dev, n0, n1 = [], 0.0, 0, 0
    for poly in polys:
        rings = []
        for ring in poly:
            n0 += len(ring)
            s, d = simplify(ring, SIMPLIFY_M)
            if len(s) >= 4:
                rings.append([[round(x, 6), round(y, 6)] for x, y in s])
                dev = max(dev, d)
                n1 += len(s)
        if rings:
            out.append(rings)
    # The deviation as the server measures it: every original vertex's distance to the simplified
    # outline, in the metres of engine/reference/border.py at that vertex, plus the rounding to 6
    # decimals (at most 0.08 m per axis), rounded up.
    simple = B.Border([r for p in out for r in p], tolerance_m=10 * SIMPLIFY_M)
    dev = max(dev, max(simple.edge_m(y, x) for p in polys for r in p for x, y in r))
    dev = math.ceil((dev + 0.2) * 10) / 10
    props = dict(feat.get('properties') or {})
    doc = {'type': 'Feature',
           'properties': {'name': 'Togo', 'source': 'OpenStreetMap admin_level 2 boundary of Togo' +
                          (' (relation %s)' % props['relation'] if props.get('relation') else ''),
                          'licence': 'ODbL 1.0, (c) OpenStreetMap contributors',
                          'simplifiedM': SIMPLIFY_M, 'deviationM': dev, 'toleranceM': B.BORDER_M,
                          'allowedM': round(B.BORDER_M - dev, 1)},
           'geometry': {'type': 'MultiPolygon', 'coordinates': out}}
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(doc, f, separators=(',', ':'))
        f.write('\n')
    print('%d -> %d vertices, deviation %.1f m, %d bytes: %s' % (n0, n1, dev, os.path.getsize(OUT), os.path.relpath(OUT, REPO)))


if __name__ == '__main__':
    if len(sys.argv) != 2:
        sys.exit(__doc__.split('\n\n')[1])
    main(os.path.abspath(sys.argv[1]))
