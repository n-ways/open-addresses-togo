#!/usr/bin/env python3
"""Every Togolese footprint's code area (engine/SPEC.md 2).

  python3 tools/assign-areas.py <work folder>

Reads <work>/buildings-pts.csv (tools/extract-buildings.py: bid, lon, lat, unit, dens) and
model/areas/areas.json, and applies the area lookup of the engine (tg_engine.Areas.at) from the unit
the extraction found:
  1. a Lomé quartier: that quartier;
  2. a canton: the canton, or, when it is split into named-place cells, the cell whose place point is
     nearest; the canton of the former commune of Lomé (TG030501) is a container: a footprint in it
     but in no quartier polygon takes the nearest quartier;
  3. no unit (a few footprints between the polygons, on the coast or the border): the nearest
     numbered area's place point in the country.
Footprints are streamed; standard library only.

The border decides (engine/SPEC.md 6, 10): a footprint whose centre lies more than 300 m outside Togo's
national border (<work>/country.geojson, OpenStreetMap admin_level 2, unsimplified; engine/reference/border.py)
is dropped and gets no area, whatever unit or nearest area it would take: it is in a neighbouring country.
tools/extract-buildings.py already keeps only footprints inside the border; this is the second guard.

Writes <work>/area-of.csv (bid, aid = the area key, dens) and <work>/area-counts-raw.json.
"""
import collections, csv, json, math, os, sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, 'engine', 'reference'))
import tg_engine as E  # noqa: E402
import border as B  # noqa: E402

work = os.path.abspath(sys.argv[1])
W = lambda f: os.path.join(work, f)
data = json.load(open(os.path.join(REPO, 'model', 'areas', 'areas.json'), encoding='utf-8'))
areas = data['areas']
by_index = {a['index']: a for a in areas}
by_unit = {a['unit']: a for a in areas if a['kind'] in ('lome-quartier', 'canton')}
numbered = [a for a in areas if a.get('numberLength')]
border = B.Border.load(W('country.geojson'))


def nearest(cands, lat, lon):
    m_lat, m_lon = E.metres(lat)
    return min(cands, key=lambda c: (((c['point'][0] - lon) * m_lon) ** 2 + ((c['point'][1] - lat) * m_lat) ** 2, c['index']))


counts, stats = collections.Counter(), collections.Counter()
with open(W('buildings-pts.csv'), encoding='utf-8', newline='') as f, open(W('area-of.csv'), 'w', newline='') as o:
    w = csv.writer(o)
    w.writerow(['bid', 'aid', 'dens'])
    for r in csv.DictReader(f):
        lat, lon = float(r['lat']), float(r['lon'])
        if not border.allows(lat, lon):
            stats['acrossBorder'] += 1
            continue
        a = by_unit.get(r['unit'])
        if a is None:
            a = nearest(numbered, lat, lon)
            stats['noUnit'] += 1
        elif a.get('cells'):
            a = nearest([by_index[i] for i in a['cells']], lat, lon)
        if not a.get('numberLength'):
            raise SystemExit('footprint %s lands in %s, which has no numbers' % (r['bid'], a['key']))
        counts[a['key']] += 1
        w.writerow([r['bid'], a['key'], r['dens']])
json.dump(dict(sorted(counts.items())), open(W('area-counts-raw.json'), 'w'))
print(sum(counts.values()), 'footprints,', len(counts), 'areas with footprints of', len(numbered), ',', stats['noUnit'], 'with no unit,', stats['acrossBorder'], 'dropped across the national border')
