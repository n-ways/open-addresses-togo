"""Issuing a code for a new compound or another door, and changing an issued code.

These are the issuer's rules, kept decision for decision, so a designated deployment hands out the
numbers the N-Ways issuer would hand out from the same registry:

  * a point outside Togo gets no code, and neither does one more than 300 m across the national border
    (OpenStreetMap's admin_level 2 boundary), even where a zone outline or the spot-code rule reaches over it;
  * a new compound gets no code if a live code lies within 3 m of the point, or if its outline is
    under 6 m² or over 20,000 m², or covers a code already issued (the building already has one);
  * another door (`of`) must be within 80 m of the code it belongs to and takes that code's area;
  * otherwise the area is the area of the nearest live code within 250 m (a new house joins its
    neighbours), else the code area the point lies in, else the nearest numbered area;
  * the number comes from the reference engine (`insert_number`): between the new compound's
    neighbours on the area's Hilbert curve, else in the tail reserve, else in the area's extra
    blocks, else in a new block of the name (which is stored and exported with the area table);
  * the code is provisional and marked `on-demand`; each key may issue a limited number a day.

The published registry carries one point per compound, not the building outlines, so the
"already has a code" checks compare against those points, and against the outlines of codes this
deployment issued itself.
"""
import json
import threading
import time

from . import store as S
from .engine import E, dist_door, numbered, ring_area, ring_centre, ring_contains, round1, unit_of

EXISTS_M = 3.0          # a live code this close to the point: the building already has its code
PLACE_NEAR_M = 250.0    # a new compound takes the area of the nearest live code within this distance
DOOR_MAX_M = 80.0       # another door of a code must be this close to it
MOVE_MAX_M = 80.0       # an entrance may be moved this far
MIN_AREA_M2 = 6.0
MAX_AREA_M2 = 20000.0

ABROAD = ("That point lies more than 300 m across Togo's national border, in a neighbouring country, "
          "so it cannot have an N-Ways Togo code.")

_lock = threading.Lock()   # one issue at a time in this process (and BEGIN IMMEDIATE across processes)


class Refused(Exception):
    def __init__(self, status, code, message, card=None):
        Exception.__init__(self, message)
        self.status, self.code, self.message, self.card = status, code, message, card


def _number(v, name, lo, hi):
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        raise Refused(400, 'bad_request', '%s must be a number.' % name)
    v = float(v)
    if not (lo <= v <= hi):
        raise Refused(400, 'bad_request', '%s must be between %g and %g.' % (name, lo, hi))
    return v


def _outline(v):
    if v is None:
        return None
    if not isinstance(v, list) or len(v) > 500:
        raise Refused(400, 'bad_request', 'outline must be a list of [lng, lat] points (at most 500).')
    ring = []
    for p in v:
        if not isinstance(p, list) or len(p) != 2:
            raise Refused(400, 'bad_request', 'outline must be a list of [lng, lat] points.')
        ring.append([_number(p[0], 'outline lng', -180, 180), _number(p[1], 'outline lat', -90, 90)])
    return ring


def place_for(st, eng, lat, lng):
    """The area a new compound takes."""
    near = st.nearest(lat, lng, PLACE_NEAR_M)
    if near is not None:
        a = eng.area(near[1]['zone'])
        if a is not None:
            return a
    a = eng.area_at(lat, lng)
    if a is not None and numbered(a):
        return a
    return eng.nearest_area(lat, lng)


def issue(st, eng, who, body, per_day, now=None, card=None):
    """Issue a code. `who` identifies the key (never the key itself); `card(row)` renders a code
    for a refusal that names an existing one. Returns the new code's row."""
    if not isinstance(body, dict):
        raise Refused(400, 'bad_request', 'Send a JSON object: {"lat": ..., "lng": ..., "outline": [[lng, lat], ...], "of": "TG-..."}.')
    lat = _number(body.get('lat'), 'lat', -90, 90)
    lng = _number(body.get('lng'), 'lng', -180, 180)
    ring = _outline(body.get('outline'))
    of = body.get('of')
    if of is not None and not isinstance(of, str):
        raise Refused(400, 'bad_request', 'of must be a machine code such as TG-FRJ-1058-2.')
    of = (of or '').strip()
    now = now or time.time()
    since = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(now - 86400))
    n = st.issued_by_since(who, since)
    if n >= per_day:
        raise Refused(429, 'rate_limited', 'This key has issued %d codes in the last 24 hours, its daily limit. Try again later.' % n)
    with _lock, st.write():
        eng.sync_blocks(st.blocks_by_zone())
        if not eng.in_country(lat, lng):
            raise Refused(422, 'outside', 'That point is outside Togo, so it cannot have an N-Ways Togo code.')
        if not eng.in_border(lat, lng):
            raise Refused(422, 'outside', ABROAD)
        area_m2, wkt_ring = 0.0, None
        if not of:
            hit = st.nearest(lat, lng, EXISTS_M)
            if hit is None:
                for r in st.local_outlines_near(lat, lng, 200):
                    if ring_contains(json.loads(r['outline']), lng, lat):
                        hit = (0.0, r)
                        break
            if hit is not None:
                raise Refused(409, 'exists', 'This building already has its code: %s.' % hit[1]['written'], card and card(hit[1]))
            if ring is not None and len(ring) >= 3:
                if ring[0] == ring[-1]:
                    ring = ring[:-1]
                area_m2 = ring_area(ring)
                if len(ring) < 3 or area_m2 < MIN_AREA_M2 or area_m2 > MAX_AREA_M2:
                    raise Refused(422, 'bad_outline', "That outline is %.0f m², but a home's is between 6 m² and 2 ha. Draw the building again." % area_m2)
                wkt_ring = ring
                hit = _overlap(st, ring)
                if hit is not None:
                    raise Refused(409, 'exists', 'This building already has its code: %s.' % hit['written'], card and card(hit))
        if of:
            parent = st.by_machine(of.upper())
            if parent is None:
                raise Refused(404, 'not_found', 'There is no code %s to add a door to.' % of)
            if dist_door(float(parent['entrance_lat']), float(parent['entrance_lng']), lat, lng) > DOOR_MAX_M:
                raise Refused(422, 'too_far', 'That door is more than 80 m from %s. Stand at the door and try again.' % parent['written'])
            area = eng.area(parent['zone'])
        else:
            area = place_for(st, eng, lat, lng)
        if area is None:
            raise Refused(422, 'outside', 'There is no code area for this point.')
        a = dict(area)
        a['blocks'] = [list(b) for b in area['blocks']]
        issued = st.zone_numbers(a['key'])
        nb = len(a['blocks'])
        try:
            number = E.insert_number(eng.areas, a, issued, lat, lng)
        except E.AreaFull:
            raise Refused(409, 'area_full', '%s has used every number of its name. Its commune chooses a qualifier before more homes there get a code.' % a['name'])
        new_blocks = a['blocks'][nb:]
        forms = eng.forms(a, number)
        row = _row(st, eng, a, number, forms, lat, lng, 'door' if of else 'centre', area_m2, who, now, wkt_ring)
        cols = list(row)
        cur = st.con.execute('INSERT INTO codes (%s) VALUES (%s)' % (', '.join(cols), ', '.join('?' * len(cols))), [row[c] for c in cols])
        if st.rtree():
            st.con.execute('INSERT INTO codes_geo VALUES (?, ?, ?, ?, ?)', (cur.lastrowid, lat, lat, lng, lng))
        if new_blocks:
            from .engine import format_blocks
            st.con.execute('UPDATE areas SET blocks = ? WHERE zone = ?', (format_blocks(a['blocks']), a['key']))
        st.con.execute("UPDATE meta SET value = '1' WHERE key = 'changed'")
    if new_blocks:
        eng.sync_blocks({a['key']: '|'.join('%d-%d' % tuple(b) for b in a['blocks'])})
    return st.by_machine(forms['machine'])


def _overlap(st, ring):
    """A live code inside the outline, or a code issued here whose outline mostly covers it."""
    cx, cy = ring_centre(ring)
    lngs = [p[0] for p in ring]
    lats = [p[1] for p in ring]
    from .engine import dist_m
    reach = max(dist_m(cy, cx, la, lo) for lo, la in zip(lngs, lats)) + 1
    best = None
    for r in st.in_box(cy, cx, reach):
        inside = ring_contains(ring, r['lng'], r['lat'])
        if not inside and r.get('outline'):
            other = json.loads(r['outline'])
            ox, oy = ring_centre(other)
            inside = ring_contains(other, cx, cy) or ring_contains(ring, ox, oy)
        if inside and (best is None or r['machine'] < best['machine']):
            best = r
    return best


def _row(st, eng, a, number, forms, lat, lng, kind, area_m2, who, now, ring):
    """The registry row of a new code, every field formatted as the N-Ways exporter writes it."""
    if area_m2 > 0:
        structures, cls, floor_area = 1, 'residential', round1(round1(area_m2) * 1)
    else:
        structures, cls, floor_area = 0, '', 0.0
    raw = {'machine': forms['machine'], 'home': forms['home'], 'written': forms['remembered'], 'zone': a['key'],
           'official_name': a.get('officialName') or '', 'number': str(number), 'check': str(forms['check']),
           'status': 'provisional', 'issued': 'on-demand', 'issued_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(now)),
           'entrance_lat': '%.7f' % lat, 'entrance_lng': '%.7f' % lng, 'entrance_kind': kind, 'spot_code': eng.spot(lat, lng),
           'official_address': '', 'class': cls, 'use': 'residential', 'kind': 'door' if kind == 'door' else 'building',
           'structures': str(structures), 'floor_area_m2': '%.1f' % floor_area, 'rule': '', 'estate': ''}
    row = {S.sql_name(k): v for k, v in raw.items()}
    row.update({'unit': unit_of(a), 'name_id': a['nameId'], 'num': number, 'lat': float(raw['entrance_lat']),
                'lng': float(raw['entrance_lng']), 'anchor_lat': lat, 'anchor_lng': lng, 'official_key': None,
                'cell': S.grid_cell(lat, lng), 'local': 'issued', 'issued_by': who,
                'outline': json.dumps(ring) if ring else None})
    return row


def change(st, eng, machine, body):
    """Set a code's status or move its entrance. Returns the changed row."""
    if not isinstance(body, dict) or not ({'status', 'entrance'} & set(body)):
        raise Refused(400, 'bad_request', 'Send {"status": "confirmed" | "provisional" | "retired"} and/or {"entrance": {"lat": ..., "lng": ...}}.')
    status = body.get('status')
    if status is not None and status not in ('confirmed', 'provisional', 'retired'):
        raise Refused(400, 'bad_request', 'status is confirmed, provisional or retired.')
    ent = body.get('entrance')
    if ent is not None:
        if not isinstance(ent, dict):
            raise Refused(400, 'bad_request', 'entrance is {"lat": ..., "lng": ...}.')
        elat = _number(ent.get('lat'), 'entrance lat', -90, 90)
        elng = _number(ent.get('lng'), 'entrance lng', -180, 180)
    with _lock, st.write():
        r = st.by_machine(machine)
        if r is None:
            raise Refused(404, 'not_found', 'There is no code %s.' % machine)
        if r['status'] == 'retired':
            raise Refused(409, 'retired', '%s is retired. A retired code is never used again; issue a new one.' % r['written'])
        sets = {}
        if status is not None and status != r['status']:
            sets['status'] = status
        if ent is not None:
            d = dist_door(float(r['entrance_lat']), float(r['entrance_lng']), elat, elng)
            if d > MOVE_MAX_M:
                raise Refused(422, 'too_far', 'The new entrance is %.0f m from the code; an entrance can move at most 80 m. Issue a new code for another building.' % d)
            if not eng.in_country(elat, elng):
                raise Refused(422, 'outside', 'That point is outside Togo.')
            if not eng.in_border(elat, elng):
                raise Refused(422, 'outside', ABROAD)
            sets.update({'entrance_lat': '%.7f' % elat, 'entrance_lng': '%.7f' % elng, 'entrance_kind': 'gate',
                         'spot_code': eng.spot(elat, elng), 'lat': float('%.7f' % elat), 'lng': float('%.7f' % elng),
                         'cell': S.grid_cell(elat, elng)})
        if sets:
            if r['local'] != 'issued':
                sets['local'] = 'changed'
            st.con.execute('UPDATE codes SET %s WHERE id = ?' % ', '.join('%s = ?' % k for k in sets), list(sets.values()) + [r['id']])
            if 'lat' in sets and st.rtree():
                st.con.execute('UPDATE codes_geo SET min_lat = ?, max_lat = ?, min_lng = ?, max_lng = ? WHERE id = ?',
                               (sets['lat'], sets['lat'], sets['lng'], sets['lng'], r['id']))
            st.con.execute("UPDATE meta SET value = '1' WHERE key = 'changed'")
    return st.by_machine(machine)
