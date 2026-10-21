"""Togo's national border: a code is only ever issued for a point inside it or within 300 m of it.

The border is OpenStreetMap's admin_level 2 boundary of Togo. Zone outlines (the HDX cantons, the Lomé
quartiers) and the spot-code rule (engine/SPEC.md 5) may reach over it; they never decide. The build
(tools/extract-buildings.py, tools/assign-areas.py, tools/issue_registry.py) checks every footprint and
compound against the full boundary of the extract; the server checks every new code and every moved
entrance against `engine/data/border.json`, the same boundary simplified to about 50 m (SPEC 1, 6, 10).

A simplified outline lies up to its measured deviation (`deviationM`, stored in the file) from the true
line, so a point is allowed only when it lies within BORDER_M minus that deviation of the simplified
outline: everything allowed is within BORDER_M of the true border; a point between the two limits may be
refused, never the other way round.

Standard library only.

  python3 border.py <lat> <lng>        how far outside the border a point lies (0 inside), and the verdict
"""
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BORDER_FILE = os.path.join(os.path.dirname(HERE), 'data', 'border.json')
BORDER_M = 300.0        # how far outside the border line an entrance may lie
CELL_DEG = 0.02         # index cell


def metres(lat0):
    """Metres per degree of latitude and of longitude at latitude lat0 (WGS84, local)."""
    p = math.radians(lat0)
    return (111132.92 - 559.82 * math.cos(2 * p) + 1.175 * math.cos(4 * p),
            111412.84 * math.cos(p) - 93.5 * math.cos(3 * p))


def rings_of(obj):
    """Every ring (outer rings and holes) of a GeoJSON geometry, Feature or FeatureCollection."""
    if obj.get('type') == 'FeatureCollection':
        return [r for f in obj['features'] for r in rings_of(f)]
    if obj.get('type') == 'Feature':
        return rings_of(obj['geometry'])
    if obj['type'] == 'Polygon':
        return [r for r in obj['coordinates']]
    if obj['type'] == 'MultiPolygon':
        return [r for p in obj['coordinates'] for r in p]
    raise ValueError('the border must be a Polygon or MultiPolygon, not %s' % obj['type'])


class Border:
    """Point-in-border (even-odd over every ring) and distance outside it, indexed on a grid."""

    def __init__(self, rings, deviation_m=0.0, tolerance_m=BORDER_M):
        self.deviation_m = float(deviation_m)
        self.allowed_m = float(tolerance_m) - self.deviation_m
        if self.allowed_m < 0:
            raise ValueError('the outline deviates %.1f m from the border, more than the %.0f m tolerance' % (deviation_m, tolerance_m))
        self.edges = []
        for ring in rings:
            pts = [(float(p[0]), float(p[1])) for p in ring]
            if len(pts) > 1 and pts[0] == pts[-1]:
                pts = pts[:-1]
            for i in range(len(pts)):
                a, b = pts[i - 1], pts[i]
                if a != b:
                    self.edges.append((a[0], a[1], b[0], b[1]))
        if not self.edges:
            raise ValueError('the border has no edges')
        ys = [y for e in self.edges for y in (e[1], e[3])]
        m_lat, m_lon = metres(max(abs(y) for y in ys))
        self.reach_lat = self.allowed_m / m_lat * 1.01 + 1e-9
        self.reach_lon = self.allowed_m / m_lon * 1.01 + 1e-9
        self.bands, self.cells = {}, {}
        for k, (ax, ay, bx, by) in enumerate(self.edges):
            for band in range(self._c(min(ay, by)), self._c(max(ay, by)) + 1):
                self.bands.setdefault(band, []).append(k)
            for gx in range(self._c(min(ax, bx) - self.reach_lon), self._c(max(ax, bx) + self.reach_lon) + 1):
                for gy in range(self._c(min(ay, by) - self.reach_lat), self._c(max(ay, by) + self.reach_lat) + 1):
                    self.cells.setdefault((gx, gy), []).append(k)

    @staticmethod
    def _c(v):
        return int(math.floor(v / CELL_DEG))

    @classmethod
    def load(cls, path=BORDER_FILE, tolerance_m=BORDER_M):
        """The border of a GeoJSON file; a file written by tools/make-border.py carries its deviation."""
        with open(path, encoding='utf-8') as f:
            obj = json.load(f)
        props = obj.get('properties') or {}
        return cls(rings_of(obj), props.get('deviationM', 0.0), tolerance_m)

    def contains(self, lat, lng):
        inside = False
        for k in self.bands.get(self._c(lat), ()):
            ax, ay, bx, by = self.edges[k]
            if (ay > lat) != (by > lat) and lng < (bx - ax) * (lat - ay) / (by - ay) + ax:
                inside = not inside
        return inside

    def edge_m(self, lat, lng):
        """Distance in metres to the nearest edge, or infinity when none lies within the index reach."""
        m_lat, m_lon = metres(lat)
        best = math.inf
        for k in self.cells.get((self._c(lng), self._c(lat)), ()):
            ax, ay, bx, by = self.edges[k]
            ax, ay = (ax - lng) * m_lon, (ay - lat) * m_lat
            vx, vy = (bx - lng) * m_lon - ax, (by - lat) * m_lat - ay
            ll = vx * vx + vy * vy
            t = min(1.0, max(0.0, -(ax * vx + ay * vy) / ll)) if ll > 0 else 0.0
            d = math.hypot(ax + t * vx, ay + t * vy)
            if d < best:
                best = d
        return best

    def outside_m(self, lat, lng):
        """0 for a point inside the border; else its distance to the border in metres (infinity when
        it lies farther than the allowed distance)."""
        return 0.0 if self.contains(lat, lng) else self.edge_m(lat, lng)

    def allows(self, lat, lng):
        """The point may have a code: inside the border, or within the allowed distance of it."""
        return self.outside_m(lat, lng) <= self.allowed_m


_default = None


def default():
    """The border the server ships (engine/data/border.json), loaded once."""
    global _default
    if _default is None:
        _default = Border.load()
    return _default


if __name__ == '__main__':
    if len(sys.argv) != 3:
        sys.exit(__doc__.rsplit('\n\n', 1)[1])
    b = default()
    la, lo = float(sys.argv[1]), float(sys.argv[2])
    d = b.outside_m(la, lo)
    print(json.dumps({'outsideM': None if math.isinf(d) else round(d, 1), 'allowedM': round(b.allowed_m, 1), 'allowed': b.allows(la, lo)}))
