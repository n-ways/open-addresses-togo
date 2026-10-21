#!/usr/bin/env python3
"""The compounds of Togo for issuing their codes (engine/SPEC.md 6, 8).

Reads <work>/buildings.csv (tools/sort-buildings.py, sorted by code area) one area at a time.

  python3 tools/issue_registry.py group <work>     compounds and profiles: <work>/compounds.jsonl.gz,
                                                    <work>/area-counts.json, <work>/group-stats.json
  python3 tools/build-register.py <work> --freeze  plate names, national ranges, blocks, frames
  python3 tools/issue_registry.py number <work> <lotes.jsonl.gz>
                                                    numbers every area's compounds inside its block
                                                    and writes the lotes, préfecture by préfecture,
                                                    for the issuer, which numbers them again and
                                                    refuses any difference

Grouping: tg_engine.group_footprints (SPEC 6 step 3: enclosure, annex, hut cluster in the rural north
of Kara and Savanes, single). The border decides: a compound whose point lies more than 300 m outside
Togo's national border (<work>/country.geojson, OpenStreetMap admin_level 2; engine/reference/border.py) is
dropped by `group`, and `number` refuses to write any lote across it. Numbering: tg_engine.number_compounds over the area's box and first
block (SPEC 6 step 5), at the centre of the compound's largest structure.

Each lote line: {"key": the main structure's stable id, "muni": the préfecture key ("KOZ", "LOM" for
the 69 quartiers of the former commune of Lomé), "zone": the area key ("KOZ0604"), "areaId": its
index, "nameId", "number", "lat", "lon", "anchor", "anchorKind", "gate", "coverage": "official-street"
in the former commune of Lomé where a named street is within 30 m, else "nways", "official": "Rue 89
AFG, Lomé" or null, "estate", "rule", "dens", "label": the area key, "structures": [...]} (largest first). Structure ids:
OpenStreetMap "osm:way/<id>"; a Google/Microsoft footprint "nw:" + the first 12 hex characters
of the SHA-1 of its centre to 1e-6 degrees and its area to 1 m2.
"""
import collections, csv, gzip, hashlib, json, os, re, sys

csv.field_size_limit(1 << 30)
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(REPO, 'engine', 'reference'))
import tg_engine as E  # noqa: E402
import border as B  # noqa: E402

AREAS = {a['key']: a for a in json.load(open(os.path.join(REPO, 'model', 'areas', 'areas.json'), encoding='utf-8'))['areas']}

TAGS = ['building', 'amenity', 'shop', 'office', 'religion', 'tourism', 'healthcare', 'man_made', 'government', 'craft',
        'building:levels', 'height', 'name', 'roof:material', 'building:material']
NUM = re.compile(r'-?\d+(?:\.\d+)?')


def structure_id(r):
    if r['src'] == 'osm':
        return 'osm:' + r['oid']
    return 'nw:' + hashlib.sha1(f"{float(r['lat']):.6f},{float(r['lon']):.6f},{round(float(r['area']))}".encode()).hexdigest()[:12]


def ring_of(wkt):
    """The outer ring of a footprint's first polygon, as (lon, lat) pairs, closing point dropped."""
    s = wkt[wkt.index('('):]
    first = s.lstrip('(').split(')')[0]
    nums = [float(x) for x in NUM.findall(first)]
    pts = list(zip(nums[0::2], nums[1::2]))
    return pts[:-1] if len(pts) > 1 and pts[0] == pts[-1] else pts


def areas_of(path):
    cur, rows = None, []
    with open(path, encoding='utf-8', newline='') as f:
        for r in csv.DictReader(f):
            if r['aid'] != cur:
                if rows:
                    yield cur, rows
                cur, rows = r['aid'], []
            rows.append(r)
    if rows:
        yield cur, rows


def height(r):
    try:
        return float(r['height'].replace('m', '').strip()) if r['height'] else None
    except ValueError:
        return None


BTAG = {
    'house': 'residential', 'residential': 'residential', 'detached': 'residential', 'apartments': 'residential',
    'hut': 'residential', 'terrace': 'residential', 'semidetached_house': 'residential', 'dormitory': 'residential',
    'commercial': 'commercial', 'retail': 'commercial', 'kiosk': 'commercial', 'supermarket': 'commercial',
    'office': 'office', 'hotel': 'hospitality', 'school': 'education', 'college': 'education', 'university': 'education',
    'kindergarten': 'education', 'hospital': 'health', 'clinic': 'health', 'church': 'religious', 'mosque': 'religious',
    'chapel': 'religious', 'cathedral': 'religious', 'government': 'government', 'public': 'government', 'civic': 'government',
    'military': 'government', 'industrial': 'industrial', 'warehouse': 'industrial', 'hangar': 'industrial',
    'factory': 'industrial', 'garage': 'transport', 'garages': 'transport', 'train_station': 'transport',
    'farm': 'agricultural', 'barn': 'agricultural', 'construction': 'under_construction', 'ruins': 'ruin',
    'shed': 'annex', 'roof': 'annex',
}
CATS = {'shop': 'commercial', 'supermarket': 'commercial', 'market': 'commercial', 'pharmacy': 'health', 'bank': 'commercial',
        'phones': 'commercial', 'salon': 'commercial', 'mechanic': 'commercial', 'food': 'commercial', 'bar': 'commercial',
        'cafe': 'commercial', 'fastfood': 'commercial', 'petrol': 'commercial', 'hotel': 'hospitality', 'school': 'education',
        'hospital': 'health', 'church': 'religious', 'mosque': 'religious', 'police': 'government', 'office': 'office',
        'motorpark': 'transport'}


def profile(r):
    """Use class, confidence, source and floors of one footprint (SPEC 8). Floors come from
    OpenStreetMap only: the Google/Microsoft height is a rendering filler and gives none."""
    b = (r['building'] or '').lower()
    ev = []
    if b and b != 'yes' and b in BTAG:
        ev.append((BTAG[b], 0.85, 'osm:building'))
    if r['amenity'] or r['shop'] or r['office'] or r['government'] or r['tourism'] or r['healthcare']:
        tag = ('health' if r['amenity'] in ('hospital', 'clinic', 'doctors', 'pharmacy') or r['healthcare'] else
               'education' if r['amenity'] in ('school', 'kindergarten', 'college', 'university') else
               'religious' if r['amenity'] == 'place_of_worship' else
               'government' if r['government'] or r['amenity'] in ('townhall', 'courthouse', 'police', 'post_office') else
               'hospitality' if r['tourism'] in ('hotel', 'guest_house', 'hostel', 'motel') else
               'office' if r['office'] else 'commercial')
        ev.append((tag, 0.75, 'osm:tag'))
    if r['poi']:
        cs = [CATS.get(c, 'commercial') for c in r['poi'].split('|')]
        ev.append((max(sorted(set(cs)), key=cs.count), 0.65, 'nways:places-inside'))
    a = float(r['area'])
    if not ev:
        ev.append(('annex', 0.4, 'size') if a < 6 else ('industrial', 0.3, 'size') if a > 2500 else ('residential', 0.45, 'default'))
    ev.sort(key=lambda e: -e[1])
    cls, conf, src = ev[0]
    if cls == 'residential' and any(e[0] in ('commercial', 'office') for e in ev):
        cls, conf, src = 'mixed', 0.6, 'agreement'
    conf = min(0.95, conf + 0.05 * sum(1 for e in ev[1:] if e[0] == cls))
    floors, fsrc = None, None
    try:
        if r['building:levels']:
            floors, fsrc = max(1, int(round(float(r['building:levels'])))), 'osm:building:levels'
    except ValueError:
        pass
    if floors is None and r['src'] == 'osm' and height(r):
        floors, fsrc = E.floors_from_height(height(r)), 'osm:height'
    return {'useClass': cls, 'useConfidence': round(conf, 2), 'useSource': src, 'floors': floors, 'floorsSource': fsrc}


def cmd_group(work):
    counts, stats, seen = {}, collections.Counter(), set()
    border = B.Border.load(os.path.join(work, 'country.geojson'))
    with gzip.open(os.path.join(work, 'compounds.jsonl.gz'), 'wt', encoding='utf-8') as out:
        for aid, rows in areas_of(os.path.join(work, 'buildings.csv')):
            fs = []
            for r in rows:
                ring = ring_of(r['wkt'])
                fs.append({'id': structure_id(r), 'ring': ring + ring[:1], 'area': float(r['area']), 'eid': r['eid'] or None,
                           'lat': float(r['lat']), 'lon': float(r['lon']), 'row': r})
            n = 0
            area = AREAS[aid]
            params = E.RURAL_NORTH if area.get('region') in ('Kara', 'Savanes') else E.URBAN
            for ms, rule in E.group_footprints(fs, params):
                sts = []
                for i in ms:
                    f, r = fs[i], fs[i]['row']
                    p = profile(r)
                    sts.append({'id': f['id'], 'src': r['src'], 'lat': round(f['lat'], 7), 'lon': round(f['lon'], 7),
                                'areaM2': round(f['area'], 1), 'perimeterM': round(float(r['perim'] or 0), 1),
                                'tags': {t: r[t] for t in TAGS if r.get(t)}, 'places': [x for x in (r['poi'] or '').split('|') if x],
                                'class': p['useClass'], 'confidence': p['useConfidence'], 'classSource': p['useSource'],
                                'floors': p['floors'], 'floorsSource': p['floorsSource'], 'wkt': r['wkt']})
                key = sts[0]['id']
                if not border.allows(fs[ms[0]]['lat'], fs[ms[0]]['lon']):
                    stats['acrossBorder'] += 1      # in a neighbouring country: no code
                    continue
                if key in seen:
                    stats['duplicateKey'] += 1
                    continue
                seen.add(key)
                main = fs[ms[0]]['row']
                streets = collections.Counter(fs[k]['row']['street'] for k in ms if fs[k]['row']['street'])
                street = min(streets, key=lambda x: (-streets[x], x)) if streets else None
                rec = {'key': key, 'aid': aid, 'lat': round(fs[ms[0]]['lat'], 7), 'lon': round(fs[ms[0]]['lon'], 7), 'rule': rule,
                       'enclosed': rule == 'enclosure', 'estate': main['estate'] or None, 'dens': int(main['dens'] or 0),
                       'label': aid, 'official': f'{street}, Lomé' if street else None, 'structures': sts}
                out.write(json.dumps(rec, ensure_ascii=False, separators=(',', ':')) + '\n')
                n += 1
                stats['rule:' + rule] += 1
                stats['structures'] += len(sts)
                stats[f'size:{min(len(sts), 7)}'] += 1
            counts[aid] = n
            stats['compounds'] += n
    json.dump(counts, open(os.path.join(work, 'area-counts.json'), 'w'))
    json.dump(dict(stats), open(os.path.join(work, 'group-stats.json'), 'w'), indent=1)
    print(json.dumps(dict(stats)))


def muni_of(a):
    return 'LOM' if a['kind'] == 'lome-quartier' else a['key'][:3]


def cmd_number(work, out_path):
    counts = collections.Counter()
    border = B.Border.load(os.path.join(work, 'country.geojson'))
    by_area = collections.defaultdict(list)
    with gzip.open(os.path.join(work, 'compounds.jsonl.gz'), 'rt', encoding='utf-8') as f:
        for line in f:
            c = json.loads(line)
            if not border.allows(c['lat'], c['lon']):
                raise SystemExit('compound %s (%s) lies %.0f m outside the national border: no lote is written' %
                                 (c['key'], c['aid'], border.outside_m(c['lat'], c['lon'])))
            by_area[c['aid']].append(c)
    order = sorted(by_area, key=lambda k: (muni_of(AREAS[k]), AREAS[k]['index']))
    with gzip.open(out_path, 'wt', encoding='utf-8') as out:
        for aid in order:
            a = AREAS[aid]
            cs = by_area.pop(aid)
            nums = E.number_compounds(a, [{'id': c['key'], 'lat': c['lat'], 'lon': c['lon']} for c in cs])
            for c in sorted(cs, key=lambda c: nums[c['key']]):
                rec = {'key': c['key'], 'muni': muni_of(a), 'zone': aid, 'areaId': a['index'], 'nameId': a['nameId'],
                       'number': nums[c['key']], 'lat': c['lat'], 'lon': c['lon'], 'anchor': [c['lat'], c['lon']], 'anchorKind': 'centre',
                       'gate': None, 'coverage': 'official-street' if c['official'] else 'nways', 'official': c['official'],
                       'enclosed': c['enclosed'], 'estate': c['estate'], 'rule': c['rule'], 'dens': c['dens'], 'label': aid,
                       'structures': c['structures']}
                out.write(json.dumps(rec, ensure_ascii=False, separators=(',', ':')) + '\n')
                counts['compounds'] += 1
                counts[f'digits:{len(str(rec["number"]))}'] += 1
                counts['officialStreet'] += bool(c['official'])
    print(json.dumps(counts))


if __name__ == '__main__':
    if sys.argv[1] == 'group':
        cmd_group(os.path.abspath(sys.argv[2]))
    elif sys.argv[1] == 'number':
        cmd_number(os.path.abspath(sys.argv[2]), sys.argv[3])
