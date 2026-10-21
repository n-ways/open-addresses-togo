#!/usr/bin/env python3
"""The small inputs of Togo's registry build, in a work folder.

Reads, read-only, the osmium exports of the OpenStreetMap extract of Togo (tools/README.md: admin,
bar, place and hw .geojsonseq in the work folder), the compound and gate layers of the N-Ways map
data (NWAYS_ROOT/data/valhalla), the N-Ways places table (NWAYS_DB; only categories are used) and this
repository's units (model/units), and writes:

  enclosures.geojson  closed walls, fences, hedges and retaining walls (40-6,000 m2): every
                      structure inside one is one compound (engine/SPEC.md 5, rule 2)
  estates.geojson     closed enclosures over 6,000 m2 and N-Ways' estate, government,
                      military and police compounds: parents, whose compounds keep their
                      own codes
  gates.csv           OpenStreetMap barrier=gate/entrance points, N-Ways gates
  places.csv          N-Ways places (POIs) in Togo
  units.geojson       the 69 quartiers of the former commune of Lomé first (OSM, their codes),
                      then the 373 cantons (HDX COD-AB, their p-codes)
  streets.csv         the named streets of the former commune of Lomé (OpenStreetMap: the 1997
                      street names and codes, "Rue 89 AFG"), the official street shown first there
  country.geojson     the national boundary (admin_level 2): a footprint outside it is
                      in a neighbouring country and gets no code

Every id is stable: osm:<type>/<id>, nways:<id>.

  python3 tools/prepare-inputs.py <work folder>
"""
import csv, json, math, os, subprocess, sys, unicodedata

ROOT = os.environ.get('NWAYS_ROOT') or sys.exit('set NWAYS_ROOT to the folder holding the map data (tools/README.md)')
DB = os.environ.get('NWAYS_DB') or sys.exit('set NWAYS_DB to the connection string of the places database (tools/README.md)')
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
work = os.path.abspath(sys.argv[1])
W = lambda f: os.path.join(work, f)
M = lambda f: os.path.join(REPO, 'model', f)
BOX = (-0.20, 5.90, 1.90, 11.20)
ENCL_MAX = 6000


def seq(path):
    for line in open(path, encoding='utf-8'):
        line = line.strip('\x1e\n ')
        if line:
            yield json.loads(line)


def oid(p):
    return f"osm:{p.get('@type', 'way')}/{p.get('@id')}"


def ring_area(ring):
    """Area of a lon/lat ring in m2 (local equirectangular)."""
    k = math.cos(math.radians(ring[0][1])) * 111320.0
    a = 0.0
    for i in range(len(ring) - 1):
        x1, y1 = ring[i][0] * k, ring[i][1] * 110574.0
        x2, y2 = ring[i + 1][0] * k, ring[i + 1][1] * 110574.0
        a += x1 * y2 - x2 * y1
    return abs(a) / 2


def polys(g):
    if g['type'] == 'Polygon':
        return [g['coordinates']]
    if g['type'] == 'MultiPolygon':
        return g['coordinates']
    if g['type'] == 'LineString' and len(g['coordinates']) >= 4 and g['coordinates'][0] == g['coordinates'][-1]:
        return [[g['coordinates']]]
    return []


def poly_area(ps):
    return sum(ring_area(p[0]) - sum(ring_area(h) for h in p[1:]) for p in ps)


def in_box(x, y):
    return BOX[0] <= x <= BOX[2] and BOX[1] <= y <= BOX[3]


def fold(s):
    return ''.join(c for c in unicodedata.normalize('NFKD', s or '') if not unicodedata.combining(c)).lower().replace('-', ' ').strip()


# ---------------------------------------------------------------- enclosures and estates
feats, est, seen = [], [], set()
for o in seq(W('bar.geojsonseq')):
    p, g = o['properties'], o['geometry']
    kind = p.get('barrier') if p.get('barrier') in ('wall', 'fence', 'hedge', 'retaining_wall') else None
    ps = polys(g)
    if not kind or not ps:
        continue
    i = oid(p)
    if i in seen:          # osmium writes a closed way twice (line and area)
        continue
    seen.add(i)
    a = poly_area(ps)
    if 40 <= a <= ENCL_MAX:
        feats.append({'type': 'Feature', 'properties': {'eid': i, 'kind': 'osm-' + kind, 'areaM2': round(a, 1)},
                      'geometry': {'type': 'MultiPolygon', 'coordinates': ps}})
    elif ENCL_MAX < a <= 2_000_000:
        est.append({'type': 'Feature', 'properties': {'estate': i, 'kind': 'walled', 'name': ''},
                    'geometry': {'type': 'MultiPolygon', 'coordinates': ps}})
json.dump({'type': 'FeatureCollection', 'features': feats}, open(W('enclosures.geojson'), 'w'))
for o in seq(os.path.join(ROOT, 'data', 'valhalla', 'compounds.geojsonseq')):
    p, g = o['properties'], o['geometry']
    ps = polys(g)
    if not ps or not in_box(*ps[0][0][0]) or p['kind'] not in ('estate', 'government', 'military', 'police'):
        continue
    est.append({'type': 'Feature', 'properties': {'estate': 'nways:' + str(p['id']), 'kind': p['kind'], 'name': p.get('name') or ''},
                'geometry': {'type': 'MultiPolygon', 'coordinates': ps}})
json.dump({'type': 'FeatureCollection', 'features': est}, open(W('estates.geojson'), 'w'))

# ---------------------------------------------------------------- gates
with open(W('gates.csv'), 'w', newline='') as f:
    w = csv.writer(f)
    w.writerow(['gid', 'src', 'barrier', 'lon', 'lat'])
    for o in seq(W('bar.geojsonseq')):
        p, g = o['properties'], o['geometry']
        if g['type'] == 'Point' and (p.get('barrier') in ('gate', 'lift_gate', 'sliding_gate', 'swing_gate', 'entrance') or p.get('entrance')):
            w.writerow([oid(p), 'osm', p.get('barrier') or 'entrance', *g['coordinates']])
    for o in seq(os.path.join(ROOT, 'data', 'valhalla', 'gates.geojsonseq')):
        p, g = o['properties'], o['geometry']
        if g['type'] == 'Point' and in_box(*g['coordinates']):
            w.writerow(['nways:' + str(p.get('id')), 'nways', p.get('barrier') or p.get('kind') or 'gate', *g['coordinates']])

# ---------------------------------------------------------------- N-Ways places (POIs)
with open(W('places.csv'), 'w') as f:
    subprocess.run(['psql', DB, '-Atc', """COPY (SELECT p.id, p.name, p.category, p.source, ST_X(p.location::geometry) lon, ST_Y(p.location::geometry) lat
        FROM places p JOIN regions r ON ST_Intersects(r.geom, p.location::geometry) WHERE r.country='TG' ORDER BY p.id) TO STDOUT WITH CSV HEADER"""],
                   stdout=f, check=True)

# ---------------------------------------------------------------- units
units = []
for fe in json.load(open(M('units/keys.geojson'), encoding='utf-8'))['features']:
    p = fe['properties']
    if p.get('kind') == 'lome-quartier':
        units.append({'type': 'Feature', 'properties': {'unit': p['id'], 'name': p['name'], 'rank': 0}, 'geometry': fe['geometry']})
for fe in json.load(open(M('units/cantons.geojson'), encoding='utf-8'))['features']:
    p = fe['properties']
    units.append({'type': 'Feature', 'properties': {'unit': p['pcode'], 'name': p['name'], 'rank': 1}, 'geometry': fe['geometry']})
json.dump({'type': 'FeatureCollection', 'features': units}, open(W('units.geojson'), 'w'), ensure_ascii=False)

# ---------------------------------------------------------------- the former commune of Lomé's streets
import re
quart = [f for f in units if f['properties']['rank'] == 0]
qx = [c[0] for f in quart for p in polys(f['geometry']) for c in p[0]]
qy = [c[1] for f in quart for p in polys(f['geometry']) for c in p[0]]
qb = (min(qx), min(qy), max(qx), max(qy))
SKIP = ('footway', 'path', 'steps', 'track', 'cycleway', 'proposed', 'construction', 'motorway_link', 'trunk_link')
nst = 0
with open(W('streets.csv'), 'w', newline='') as f:
    w = csv.writer(f)
    w.writerow(['sid', 'name', 'highway', 'wkt'])
    for o in seq(W('hw.geojsonseq')):
        p, g = o['properties'], o['geometry']
        nm = (p.get('name') or '').strip()
        nm = re.sub(r'^(AVENUE|RUE|BOULEVARD|ROUTE|IMPASSE)\b', lambda m: m.group(1).capitalize(), nm)
        ref = (p.get('ref') or '').strip()
        if ref and re.fullmatch(r'\d{1,3}\s*[A-Z]{2,3}\d?', ref) and ref.replace(' ', '') not in nm.replace(' ', ''):
            nm = f'{nm} ({ref})' if nm else f'Rue {ref}'
        if not nm or p.get('highway') in SKIP or g['type'] != 'LineString':
            continue
        cs = g['coordinates']
        if not any(qb[0] <= x <= qb[2] and qb[1] <= y <= qb[3] for x, y in cs):
            continue
        w.writerow([oid(p), nm, p.get('highway'), 'LINESTRING(' + ','.join(f'{x:.7f} {y:.7f}' for x, y in cs) + ')'])
        nst += 1
print(nst, 'named streets in the former commune of Lomé')

for o in seq(W('admin.geojsonseq')):
    if o['properties'].get('admin_level') == '2' and o['properties'].get('ISO3166-1') in ('TG', None) and 'Togo' in (o['properties'].get('name:fr') or o['properties'].get('name') or ''):
        json.dump({'type': 'FeatureCollection', 'features': [{'type': 'Feature', 'properties': {'name': 'Togo', 'relation': o['properties'].get('@id')}, 'geometry': o['geometry']}]},
                  open(W('country.geojson'), 'w'))
        break
else:
    sys.exit('no admin_level 2 boundary for Togo in admin.geojsonseq')
print(len(feats), 'enclosures,', len(est), 'estates,', len(units), 'units')
