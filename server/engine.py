"""The reference engine (engine/reference/tg_engine.py) as the server uses it.

Parsing, check digits, spot codes, plate names and numbering all come from the reference engine; this
module only loads it, keeps the area blocks in step with the database (blocks grow when a full area
takes an extra block), and adds the few helpers a server needs: the issuer's distance rules, the Plus
Code shown on a card, and the place line printed beside a code.
"""
import math
import os
import sys
import threading

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, 'engine', 'reference'))
import tg_engine as E  # noqa: E402
import border as B  # noqa: E402

SPEC = 'SPEC v1.0'

# The préfecture as people write it (the area table keeps the unaccented form).
PREFECTURE_NAMES = {'Agoe-Nyive': 'Agoè-Nyivé', 'Anie': 'Anié', 'Ave': 'Avé', 'Cinkasse': 'Cinkassé', 'Keran': 'Kéran',
                    'Kpele': 'Kpélé', 'Tandjoare': 'Tandjouaré', 'Tone': 'Tône', 'Plaine du Mo': 'Plaine du Mô',
                    'Lome Commune': 'Lomé'}


def prefecture_name(p):
    return PREFECTURE_NAMES.get(p, p)


def place_line(area):
    """What is printed beside a code: Lomé for the former commune, else the préfecture."""
    if area['kind'] == 'lome-quartier':
        return 'Lomé'
    if area.get('prefecture'):
        return prefecture_name(area['prefecture'])
    return 'Togo'


def unit_of(area):
    """The registry file an area's codes are published in: LOM for the 69 quartiers of the former
    commune of Lomé, else the préfecture key (the first three letters of the area key)."""
    if area['kind'] == 'lome-quartier':
        return 'LOM'
    return area['key'][:3]


def numbered(area):
    return bool(area.get('numberLength')) and bool(area.get('blocks'))


# ---------------------------------------------------------------- distances
# The issuer measures in a local plane, which is exact enough at the scale of a home. Two formulas
# are in use and each is kept where the issuer uses it, so that a deployment decides exactly as the
# N-Ways issuer does.
M_LAT = 110574.0
M_LON_EQ = 111320.0


def dist_nearest_area(lat1, lon1, lat2, lon2):
    """Distance used to pick the nearest numbered area (cos of the second latitude)."""
    return math.hypot((lat1 - lat2) * M_LAT, (lon1 - lon2) * M_LON_EQ * math.cos(math.radians(lat2)))


def dist_door(lat1, lng1, lat2, lng2):
    """Distance used for the 80 m door rule and for moving an entrance (mean latitude)."""
    dy = (lat2 - lat1) * 111320
    dx = (lng2 - lng1) * 111320 * math.cos(math.radians((lat1 + lat2) / 2))
    return math.hypot(dx, dy)


def dist_m(lat1, lon1, lat2, lon2):
    """Ground distance in metres for look-ups by point (WGS84 metres per degree at the point)."""
    m_lat, m_lon = E.metres((lat1 + lat2) / 2)
    return math.hypot((lat1 - lat2) * m_lat, (lon1 - lon2) * m_lon)


def ring_area(ring):
    """Area in m² of an outline [[lng, lat], ...] (open ring), as the issuer computes it."""
    if len(ring) < 3:
        return 0.0
    k = math.cos(math.radians(ring[0][1]))
    a = 0.0
    for i in range(len(ring)):
        j = (i + 1) % len(ring)
        xi, yi = ring[i][0] * M_LON_EQ * k, ring[i][1] * M_LAT
        xj, yj = ring[j][0] * M_LON_EQ * k, ring[j][1] * M_LAT
        a += xi * yj - xj * yi
    return abs(a) / 2


def ring_contains(ring, lng, lat):
    return E._ring_contains(ring, lng, lat)


def ring_centre(ring):
    return (sum(p[0] for p in ring) / len(ring), sum(p[1] for p in ring) / len(ring))


def round1(x):
    """One decimal, ties to even (the issuer's rounding)."""
    return round(x * 10) / 10


# ---------------------------------------------------------------- Plus Codes (shown on a card)
_OLC = '23456789CFGHJMPQRVWX'


def plus_code(lat, lng):
    """The 11-character Open Location Code of a point, for people who use Plus Codes."""
    def r6(x):
        return round(x * 1e6) / 1e6
    lat = min(90.0, max(-90.0, lat))
    lng = ((lng + 180) % 360 + 360) % 360 - 180
    lat_v = int(math.floor(r6((lat + 90) * 25000000)))
    lng_v = int(math.floor(r6((lng + 180) * 8192000)))
    tail = ''
    for _ in range(5):
        tail = _OLC[(lat_v % 5) * 4 + lng_v % 4] + tail
        lat_v //= 5
        lng_v //= 4
    head = ''
    for _ in range(5):
        head = _OLC[lat_v % 20] + _OLC[lng_v % 20] + head
        lat_v //= 20
        lng_v //= 20
    full = head + tail
    return full[:8] + '+' + full[8:11]


# ---------------------------------------------------------------- the area table
def parse_blocks(text):
    """'1000-4799|10000-10199' -> [[1000, 4799], [10000, 10199]]."""
    out = []
    for part in (text or '').split('|'):
        if part:
            lo, hi = part.split('-')
            out.append([int(lo), int(hi)])
    return out


def format_blocks(blocks):
    return '|'.join('%d-%d' % (lo, hi) for lo, hi in blocks)


class Engine:
    """The reference engine's area table, with the blocks the database holds."""

    def __init__(self):
        self.areas = E.Areas()
        self.border = B.default()
        self.lock = threading.Lock()

    def sync_blocks(self, blocks_by_zone):
        """Set every area's blocks to the database's (extra blocks added after first issue)."""
        with self.lock:
            for key, text in blocks_by_zone.items():
                a = self.areas.by_key.get(key)
                if a is not None and text:
                    b = parse_blocks(text)
                    if b != a.get('blocks'):
                        a['blocks'] = b

    def area(self, key):
        return self.areas.by_key.get(key)

    def area_by_index(self, index):
        return self.areas.by_index.get(index)

    def in_country(self, lat, lng):
        """The point is in Togo: in a quartier or canton outline, or close enough to one to have a
        spot code (SPEC 5), as the compounds in the gaps between outlines are."""
        return self.areas.container(lng, lat) is not None or E.spot_frame(self.areas, lat, lng) is not None

    def in_border(self, lat, lng):
        """The point may have a code: inside Togo's national border (OpenStreetMap admin_level 2) or within
        300 m of it (engine/reference/border.py, engine/data/border.json). Zone outlines and spot codes
        reach over the border in places; this decides."""
        return self.border.allows(lat, lng)

    def area_at(self, lat, lng):
        """The code area of a point (quartier, canton, or a named-place cell), or None outside Togo."""
        return self.areas.at(lat, lng)

    def nearest_area(self, lat, lng):
        """The numbered area whose place point is nearest (the issuer's last resort for a new code)."""
        best, bd = None, float('inf')
        for a in sorted(self.areas.areas, key=lambda x: x['index']):
            if not numbered(a):
                continue
            d = dist_nearest_area(a['point'][1], a['point'][0], lat, lng)
            if d < bd:
                best, bd = a, d
        return best

    def spot(self, lat, lng):
        return E.encode_spot(self.areas, lat, lng)

    def spot_point(self, code):
        return E.decode_spot(self.areas, code)

    def parse(self, text):
        return E.parse(self.areas, text)

    def forms(self, area, number):
        """Machine, remembered (written), home and spoken forms of a code, and its check digit."""
        return {'machine': E.machine(area, number), 'home': '%s %d' % (area['name'], number),
                'remembered': E.remembered(area, number), 'spoken': E.spoken_fr(self.areas, area, number),
                'check': E.check_digit(area, number)}

    def by_name(self, name):
        """Areas whose plate name, official name or alias has the same national name key."""
        return list(self.areas.by_name.get(E.name_key(name), []))
