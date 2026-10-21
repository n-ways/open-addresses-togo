#!/usr/bin/env python3
"""N-Ways address engine for Togo: reference implementation (Python standard library only).

Official addresses come first: where the State gives an address, N-Ways uses that data and shows it first.
Grand Lomé (the 13 communes: former commune of Lomé + Golfe + Agoè-Nyivé) is addressed by the DAGL: legacy
street codes now ("165 AMT"), DAGL street code/name + metric entrance number when released. Every compound
in Togo, Grand Lomé included, also has its N-Ways code: 2,768,053 codes, issued on 20 October 2026.

What it does (engine/SPEC.md describes each rule):
  * code areas: the 69 quartiers of Lomé and the cantons, split into named-place cells where a canton
    is too big for 4-digit numbers (model/areas/areas.json)
  * remembered form  "Fréau-Jardin 10 58"   plate name + 4 (or 5) digits;
                                            the plate name is at most 12 characters and 2 words
                                            (SPEC 3.2); the official name is an alias;
                                            unique nationally on its own: all areas whose names
                                            normalise alike (name_key) share one national number
                                            space per name, cut into frozen blocks, so the number
                                            alone says which same-named area it is
  * machine form     "TG-FRJ-1058-2"        + Damm check digit over name id + area index + number
                                            (for systems only: people never see or type it)
  * spot codes       "AMT-97-M8"            ~3.4 m geographic cells, Togo alphabet (Q replaced by K);
                                            any point in Togo, shared by link
  * compounds        structures grouped into compounds before numbering, numbered along a Hilbert
                     curve with gaps; provisional numbers for new homes
  * official data    Lomé street codes and DAGL entrance addresses imported and shown exactly as written
  * parsing          accepts remembered, spoken-style and machine forms; recognises a Lomé street code
                     ("165 AMT": number first, 1-3 digits) and never mistakes it for an N-Ways code

Run `python3 tg_engine.py --help` for the command line.
"""
import collections
import json
import math
import os
import re
import sys
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
AREAS_FILE = os.path.join(REPO, 'model', 'areas', 'areas.json')
sys.path.insert(0, HERE)
import plate_names  # noqa: E402  (plate-name limits, SPEC 3.2)

COUNTRY = 'TG'
# Togo's spot alphabet: no vowels, no 0/O 1/I/L; Q (foreign to both Ewe and Kabiyè, and read
# "ku" in French) is replaced by K, which both national languages use.
ALPHABET = '23456789CFGHJKMPRVWX'
BASE = len(ALPHABET)
CELL_DEG = 1.0 / 32768.0          # spot cell: 3.39 m north-south, 3.35-3.37 m east-west in Togo
FRAME_SNAP_DEG = 1.0 / 1024.0     # frame origins snap to this grid (stable, independent of edits)
SPOT_OUTLINE_M = 1100             # SPEC 5: a point in no outline is in Togo when an outline lies within this
SPOT_NEAR_CELLS = 200             # SPEC 5: ... and a frame within this many cells takes it (its nearest cell)
SPOT_M_PER_DEG = 110574.0         # metres per degree of latitude for those limits
HILBERT_ORDER = 16                # 65,536 x 65,536 curve over each area's box

# ---------------------------------------------------------------- check digit (Damm)
_DAMM = (
    (0, 3, 1, 7, 5, 9, 8, 6, 4, 2),
    (7, 0, 9, 2, 1, 5, 4, 8, 6, 3),
    (4, 2, 0, 6, 8, 7, 1, 3, 5, 9),
    (1, 7, 5, 0, 9, 8, 3, 4, 2, 6),
    (6, 1, 2, 3, 0, 4, 5, 9, 7, 8),
    (3, 6, 7, 4, 2, 0, 9, 5, 8, 1),
    (5, 8, 6, 9, 7, 2, 0, 1, 3, 4),
    (8, 9, 4, 5, 3, 6, 2, 0, 1, 7),
    (9, 4, 3, 8, 6, 1, 7, 2, 0, 5),
    (2, 5, 8, 1, 4, 3, 6, 7, 9, 0),
)


def damm(digits):
    """Damm check digit of a string of decimal digits."""
    i = 0
    for ch in digits:
        i = _DAMM[i][int(ch)]
    return i


def damm_ok(digits_with_check):
    return damm(digits_with_check) == 0


def check_digit(area, number):
    """Check digit of a compound code: Damm over the national name id (4 digits), the area index
    (4 digits) and the number. It binds name + number + area: the same number copied onto another
    area (same-named or not) fails the check."""
    return damm('%04d%04d%d' % (area['nameId'], area['index'], number))


class NotNumbered(ValueError):
    """Raised when a number is asked for in an area that holds none (the container canton of Lomé)."""


def require_nways(area):
    if not area.get('numberLength'):
        raise NotNumbered('%s (%s) is not a numbered area: its quartiers are' % (area['key'], area['name']))


# ---------------------------------------------------------------- geometry helpers
def _ring_contains(ring, x, y):
    inside = False
    j = len(ring) - 1
    for i in range(len(ring)):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


def polygon_contains(geom, lon, lat):
    polys = [geom['coordinates']] if geom['type'] == 'Polygon' else geom['coordinates']
    for poly in polys:
        if _ring_contains(poly[0], lon, lat) and not any(_ring_contains(h, lon, lat) for h in poly[1:]):
            return True
    return False


def metres(lat0):
    """Metres per degree of latitude and of longitude at latitude lat0 (WGS84, local)."""
    p = math.radians(lat0)
    m_lat = 111132.92 - 559.82 * math.cos(2 * p) + 1.175 * math.cos(4 * p)
    m_lon = 111412.84 * math.cos(p) - 93.5 * math.cos(3 * p)
    return m_lat, m_lon


def hilbert_index(order, x, y):
    """Position of cell (x, y) along a Hilbert curve covering 2**order x 2**order cells."""
    n = 1 << order
    d = 0
    s = n >> 1
    while s > 0:
        rx = 1 if x & s else 0
        ry = 1 if y & s else 0
        d += s * s * ((3 * rx) ^ ry)
        if ry == 0:
            if rx == 1:
                x = n - 1 - x
                y = n - 1 - y
            x, y = y, x
        s >>= 1
    return d


def load_json(path):
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def plain(s):
    return ''.join(c for c in unicodedata.normalize('NFKD', s) if not unicodedata.combining(c))


def norm_name(s):
    return re.sub(r'[^A-Z0-9]', '', plain(s).upper())


# Ewe / Kabiyè letters folded to their Latin base before accents are removed.
_AFRICAN = str.maketrans({'ɛ': 'e', 'Ɛ': 'E', 'ɔ': 'o', 'Ɔ': 'O', 'ŋ': 'n', 'Ŋ': 'N', 'ƒ': 'f', 'Ƒ': 'F', 'ʋ': 'v',
                          'Ʋ': 'V', 'ɖ': 'd', 'Ɖ': 'D', 'ɣ': 'g', 'Ɣ': 'G', 'ʼ': "'", '´': "'", '’': "'"})


def name_key(s):
    """National name key (SPEC 3.1): two place names with the same key are the same name for numbering,
    so they share one national number space. Folds case, accents, Ewe/Kabiyè letters, spaces, hyphens
    and apostrophes, a leading French article, trailing part numbers ('Zongo 1', 'Agbo Kope II'), and
    the spelling variants of French-written Ewe/Kabiyè names: PH=F, QU=K, DJ=J, OU=U=W, hard C=K,
    doubled letters single ('Copé' = 'Kopé', 'Djabdjoare' = 'Jabjoare', 'Nassiété' = 'Nasiete',
    'Ediwlou' = 'Ediwoulou'). The abbreviations a plate name may use are expanded first (St = Saint,
    Ste = Sainte, N.-D. = Notre-Dame), so the full form typed decodes too."""
    t = plain(s.translate(_AFRICAN)).upper()
    t = re.sub(r'\bN\.?\s*-?\s*D\.(?=\s|-|$)', 'NOTRE DAME', t)   # standard abbreviations of a plate name
    t = re.sub(r'[^A-Z0-9]+', ' ', t).strip()
    t = re.sub(r'\bSTE\b', 'SAINTE', t)
    t = re.sub(r'\bST\b', 'SAINT', t)
    t = re.sub(r'^(?:LE|LA|LES|L) ', '', t)
    t = re.sub(r'(?: (?:\d+|I|II|III|IV))+$', '', t)
    t = t.replace(' ', '')
    for a, b in (('PH', 'F'), ('QU', 'K'), ('DJ', 'J'), ('OU', 'U'), ('W', 'U')):
        t = t.replace(a, b)
    t = re.sub(r'C(?=[AOU]|$)', 'K', t)
    return re.sub(r'(.)\1+', r'\1', t)


_GENERIC_HEAD = re.compile(r"^(?:r[ée]sidence du chef du village de\s+|[ée]co-?village\s+|village\s+(?:de\s+|d')?|quartier\s+)", re.I)
_GENERIC_TAIL = re.compile(r"(?:\s*,\s*togo|\s+village)$", re.I)
_PART = re.compile(r'(?:\s+(?:\d+|I|II|III|IV))+$')
_JUNK = {'unknow', 'unknown', 'inconnu', 'noname', 'no name'}


def clean_place_name(name, fallback):
    """The place word people say, from an OpenStreetMap name: drops generic words ('Village de',
    'Quartier', ', Togo'), part numbers ('Zongo 1': a digit in the name would run into the code's
    number), fixes all-capital or lower-case names; a junk name ('unknow') becomes `fallback`
    (the canton's name). Returns (name, changed)."""
    n = (name or '').strip()
    if n.lower() in _JUNK or not n:
        return fallback, True
    m = n
    for _ in range(2):
        m = _GENERIC_HEAD.sub('', m).strip()
        m = _GENERIC_TAIL.sub('', m).strip()
    m = _PART.sub('', m).strip() or m
    m = re.sub(r'\s*\([^)]*\)', '', m).strip() or m   # 'Gniengou (AKA : Gningou)': the alias is kept apart
    m = m.replace('´', "'").replace('’', "'")
    whole_caps = m.isupper()
    words = []
    for w in m.split(' '):
        if len(w) > 1 and w.isupper() and (whole_caps or len(w) > 4):  # keep short acronyms in mixed names (CEET)
            w = '-'.join(x[:1] + x[1:].lower() for x in w.split('-'))
        words.append(w)
    m = ' '.join(words)
    if m and m[0].islower():
        m = m[0].upper() + m[1:]
    return m, m != n


# ---------------------------------------------------------------- areas
class Areas:
    """The frozen code-area table (model/areas/areas.json) with point lookup."""

    def __init__(self, path=AREAS_FILE):
        data = load_json(path)
        self.version = data.get('version')
        self.areas = data['areas']
        self.by_key = {a['key']: a for a in self.areas}
        self.by_index = {a['index']: a for a in self.areas}
        self.by_name = {}
        for a in self.areas:
            for n in [a['name']] + a.get('aliases', []):
                k = name_key(n)
                if a not in self.by_name.setdefault(k, []):
                    self.by_name[k].append(a)
        self._check_blocks()
        self._check_plates()
        self._geoms = {}
        units = os.path.join(REPO, 'model', 'units')
        for fname, idfield in (('keys.geojson', 'id'), ('cantons.geojson', 'pcode')):
            p = os.path.join(units, fname)
            if os.path.exists(p):
                for f in load_json(p)['features']:
                    self._geoms[f['properties'][idfield]] = f['geometry']

    def _check_blocks(self):
        """Every numbered area has a name id and blocks; same-named areas never overlap (SPEC 3.1)."""
        for k, group in self.by_name.items():
            seen = []
            for a in group:
                if not a.get('numberLength'):
                    continue
                for lo, hi in a['blocks']:
                    for lo2, hi2, other in seen:
                        if lo <= hi2 and lo2 <= hi and other is not a:
                            raise ValueError('blocks of %s and %s overlap under name %s' % (a['key'], other['key'], k))
                    seen.append((lo, hi, a))

    def _check_plates(self):
        """A numbered area's plate name fits the limit (SPEC 3.2), unless the area is still waiting for
        its commune's choice (needsCouncilChoice): then no code is issued until it fits."""
        for a in self.areas:
            if a.get('numberLength') and not plate_fits(a['name']) \
                    and not a.get('needsCouncilChoice'):
                raise ValueError('plate name %r of %s is over %d characters or %d words'
                                 % (a['name'], a['key'], plate_names.MAX_CHARS, plate_names.MAX_WORDS))

    def numbered(self, name):
        """The numbered (non-official) areas whose name or alias has this name key."""
        return [a for a in self.by_name.get(name_key(name), []) if a.get('numberLength')]

    def decode(self, name, number):
        """The one area that owns `number` under `name` anywhere in Togo, or None (number in no block)."""
        for a in self.numbered(name):
            if block_of(a, number):
                return a
        return None

    def container(self, lon, lat):
        """The quartier or canton polygon that contains the point (quartiers first)."""
        for kind in ('lome-quartier', 'canton'):
            for a in self.areas:
                if a['kind'] != kind:
                    continue
                x0, y0, x1, y1 = a['box']
                if not (x0 <= lon <= x1 and y0 <= lat <= y1):
                    continue
                g = self._geoms.get(a['unit'])
                if g and polygon_contains(g, lon, lat):
                    return a
        return None

    def at(self, lat, lon):
        """The code area for a point: quartier, canton, or a named-place cell of a split canton."""
        a = self.container(lon, lat)
        if a is None:
            return None
        if a.get('cells'):
            m_lat, m_lon = metres(lat)
            best = None
            for idx in a['cells']:
                c = self.by_index[idx]
                d = ((c['point'][0] - lon) * m_lon) ** 2 + ((c['point'][1] - lat) * m_lat) ** 2
                if best is None or d < best[0]:
                    best = (d, c)
            return best[1]
        return a

    def frame_area(self, area):
        """Spot codes use the frame of the quartier or canton (cells share their canton's frame)."""
        return self.by_index[area['parent']] if area['kind'] == 'cell' else area


# ---------------------------------------------------------------- spot codes
def _frame(area):
    x0, y0, x1, y1 = area['box']
    ox = math.floor(x0 / FRAME_SNAP_DEG) * FRAME_SNAP_DEG
    oy = math.floor(y0 / FRAME_SNAP_DEG) * FRAME_SNAP_DEG
    nx = max(1, math.ceil(math.log((x1 - ox) / CELL_DEG + 1, BASE)))
    ny = max(1, math.ceil(math.log((y1 - oy) / CELL_DEG + 1, BASE)))
    return ox, oy, nx, ny


def _digits(v, n):
    out = []
    for _ in range(n):
        out.append(v % BASE)
        v //= BASE
    return out[::-1]


def _interleave(ys, xs):
    m = max(len(ys), len(xs))
    ys = [None] * (m - len(ys)) + ys
    xs = [None] * (m - len(xs)) + xs
    out = []
    for a, b in zip(ys, xs):
        if a is not None:
            out.append(a)
        if b is not None:
            out.append(b)
    return out


def edge_d2(geom, lat, lon):
    """Squared distance from a point to the nearest edge of any ring of an outline, in degrees of
    latitude, longitude differences scaled by cos(latitude) (SPEC 5)."""
    c = math.cos(lat * math.pi / 180)
    polys = [geom['coordinates']] if geom['type'] == 'Polygon' else geom['coordinates']
    best = math.inf
    for poly in polys:
        for ring in poly:
            j = len(ring) - 1
            for i in range(len(ring)):
                ax, ay = (ring[j][0] - lon) * c, ring[j][1] - lat
                vx, vy = (ring[i][0] - lon) * c - ax, (ring[i][1] - lat) - ay
                ll = vx * vx + vy * vy
                t = 0.0
                if ll > 0:
                    t = min(1.0, max(0.0, -(ax * vx + ay * vy) / ll))
                px, py = ax + t * vx, ay + t * vy
                d = px * px + py * py
                if d < best:
                    best = d
                j = i
    return best


def _frame_cells(f, lat, lon):
    """The cell (ix, iy) of a point in an area's frame, and the cells by which it lies beyond the
    frame on the farther axis (0 inside)."""
    ox, oy, nx, ny = _frame(f)
    ix = math.floor((lon - ox) / CELL_DEG)
    iy = math.floor((lat - oy) / CELL_DEG)

    def beyond(v, n):
        return -v if v < 0 else max(0, v - (BASE ** n - 1))
    return ix, iy, max(beyond(ix, nx), beyond(iy, ny))


def spot_frame(areas, lat, lon):
    """The frame area of a point in no quartier or canton outline (SPEC 5): among the quartiers and
    cantons whose outline lies within SPOT_OUTLINE_M, the one with the nearest outline whose frame
    holds the point; else, among those whose frame lies at most SPOT_NEAR_CELLS cells away, the one
    with the nearest outline; ties to the lower key. None: the point is outside Togo."""
    lim = SPOT_OUTLINE_M / SPOT_M_PER_DEG
    lim = lim * lim
    c = math.cos(lat * math.pi / 180)
    best = None
    for f in areas.areas:
        if f['kind'] not in ('lome-quartier', 'canton'):
            continue
        g = areas._geoms.get(f['unit'])
        if g is None:
            continue
        x0, y0, x1, y1 = f['box']
        bx, by = max(x0 - lon, 0.0, lon - x1) * c, max(y0 - lat, 0.0, lat - y1)
        if bx * bx + by * by > lim * 1.01:
            continue    # the outline is farther than its box
        _, _, over = _frame_cells(f, lat, lon)
        if over > SPOT_NEAR_CELLS:
            continue
        d = edge_d2(g, lat, lon)
        if d > lim:
            continue
        rank = (over > 0, d, f['key'])
        if best is None or rank < best[0]:
            best = (rank, f)
    return best[1] if best else None


def encode_spot(areas, lat, lon):
    """Spot code of any point in Togo: '<frame key>-<chars>'. Works offline."""
    a = areas.at(lat, lon)
    if a is None:
        # a point in no outline (between two outlines, or just over a border line) takes the
        # frame of the nearest outline that holds it, else the nearest cell of a near frame
        f = spot_frame(areas, lat, lon)
        if f is None:
            raise ValueError('point is outside Togo: in no quartier or canton outline, and no outline within %d m '
                             'has a frame within %d cells' % (SPOT_OUTLINE_M, SPOT_NEAR_CELLS))
        ox, oy, nx, ny = _frame(f)
        ix, iy, _ = _frame_cells(f, lat, lon)
        ix, iy = min(max(ix, 0), BASE ** nx - 1), min(max(iy, 0), BASE ** ny - 1)
    else:
        f = areas.frame_area(a)
        x0, y0, x1, y1 = f['box']
        if not (x0 <= lon <= x1 and y0 <= lat <= y1):
            # a point between Lomé's quartier polygons takes its nearest quartier as code area, but
            # lies outside that quartier's box: its spot code uses the containing canton's frame
            f = areas.container(lon, lat) or f
        ox, oy, nx, ny = _frame(f)
        ix = int((lon - ox) / CELL_DEG)
        iy = int((lat - oy) / CELL_DEG)
    chars = ''.join(ALPHABET[d] for d in _interleave(_digits(iy, ny), _digits(ix, nx)))
    half = (len(chars) + 1) // 2
    return '%s-%s-%s' % (f['key'], chars[:half], chars[half:])


def decode_spot(areas, code):
    """(lat, lon) of the centre of a spot cell, and the cell size in metres."""
    m = re.fullmatch(r'\s*(?:TG-)?([A-Z0-9]+)-([%s]+)-([%s]+)\s*' % (ALPHABET, ALPHABET), code.upper())
    if not m:
        raise ValueError('not a Togo spot code: %r' % code)
    f = areas.by_key.get(m.group(1))
    if f is None:
        raise ValueError('unknown area key %r' % m.group(1))
    ox, oy, nx, ny = _frame(f)
    chars = m.group(2) + m.group(3)
    if len(chars) != nx + ny:
        raise ValueError('spot code for %s has %d characters, expected %d' % (f['key'], len(chars), nx + ny))
    order = []
    mx = max(nx, ny)
    for i in range(mx):
        if i >= mx - ny:
            order.append('y')
        if i >= mx - nx:
            order.append('x')
    iy = ix = 0
    for axis, ch in zip(order, chars):
        v = ALPHABET.index(ch)
        if axis == 'y':
            iy = iy * BASE + v
        else:
            ix = ix * BASE + v
    lat = oy + (iy + 0.5) * CELL_DEG
    lon = ox + (ix + 0.5) * CELL_DEG
    m_lat, m_lon = metres(lat)
    return lat, lon, (CELL_DEG * m_lat, CELL_DEG * m_lon)


# ---------------------------------------------------------------- compound codes: forms
_UNITS = ['zéro', 'un', 'deux', 'trois', 'quatre', 'cinq', 'six', 'sept', 'huit', 'neuf', 'dix', 'onze', 'douze',
          'treize', 'quatorze', 'quinze', 'seize']
_TENS = {2: 'vingt', 3: 'trente', 4: 'quarante', 5: 'cinquante', 6: 'soixante'}


def french_0_99(n):
    if n <= 16:
        return _UNITS[n]
    if n < 20:
        return 'dix-' + _UNITS[n - 10]
    t, u = divmod(n, 10)
    if t in (7, 9):
        base = 'soixante' if t == 7 else 'quatre-vingt'
        rest = 10 + u
        if t == 7 and u == 1:
            return 'soixante et onze'
        return base + '-' + french_0_99(rest)
    if t == 8:
        return 'quatre-vingts' if u == 0 else 'quatre-vingt-' + _UNITS[u]
    if u == 0:
        return _TENS[t]
    if u == 1:
        return _TENS[t] + ' et un'
    return _TENS[t] + '-' + _UNITS[u]


def pairs(number):
    """Digits grouped as people read phone numbers: 4817 -> '48 17'; 13217 -> '1 32 17'."""
    s = str(number)
    head = len(s) % 2
    groups = ([s[:head]] if head else []) + [s[i:i + 2] for i in range(head, len(s), 2)]
    return ' '.join(groups)


def spoken_fr(areas, area, number):
    """How the app's voice (and a person on the phone) says the code in French."""
    place = area.get('spoken') or area['name']
    words = []
    for g in pairs(number).split():
        n = int(g)
        words.append(('zéro ' if g.startswith('0') and len(g) == 2 else '') + french_0_99(n))
    return '%s, %s' % (place, ', '.join(words))


def plate_fits(name):
    """SPEC 3.2: a plate name has at most 12 characters (letters, spaces, hyphens, apostrophes; an
    accented letter is one) and at most 2 words (linking words such as de, du, des do not count; a
    hyphen separates words), and no digit."""
    return plate_names.fits(name, 'fr')


class PlateTooLong(ValueError):
    """Raised when a code is asked for under a plate name over the limit (SPEC 3.2)."""


def require_plate(area):
    # An area waiting for its commune's choice issues codes under its provisional name, so that no home
    # waits for a decision to have an address: only an unflagged long name is an error.
    if not plate_fits(area['name']) and not area.get('needsCouncilChoice'):
        raise PlateTooLong('%s: plate name %r is over %d characters or %d words; the commune chooses a short '
                           'name before first issue (candidates: %s)' % (area['key'], area['name'], plate_names.MAX_CHARS,
                                                                          plate_names.MAX_WORDS,
                                                                          ', '.join(area.get('plateCandidates') or []) or 'none'))


def remembered(area, number):
    """What people remember and write: the plate name, then the number in pairs."""
    require_nways(area)
    require_plate(area)
    return '%s %s' % (area['name'], pairs(number))


def machine(area, number, structure=None, entrance=None):
    require_nways(area)
    require_plate(area)
    code = 'TG-%s-%d-%d' % (area['key'], number, check_digit(area, number))
    if structure:
        code += '.%d' % structure
    if entrance:
        code += '/%d' % entrance
    return code


STREET_CODE = re.compile(r'^\s*(?:rue|avenue|av\.?|bd|boulevard|impasse)?\s*(\d{1,3})\s*[.\s]?\s*([A-Z]{2,3}\d?)\s*$', re.I)


def parse(areas, text):
    """Read a code as people type or say it. Returns a dict with kind and fields.

    kinds: 'compound' (area, number, structure, entrance, checked), 'spot', 'lome-street-code'
    (Lomé street codes are number first, 1-3 digits: '165 AMT'; never an N-Ways code).
    """
    t = text.strip()
    u = plain(t).upper()
    m = re.fullmatch(r'TG-([A-Z0-9]+)-(\d{4,5})-(\d)(?:\.(\d+))?(?:/(\d+))?', u)
    if m:
        a = areas.by_key.get(m.group(1))
        if a is None:
            raise ValueError('unknown area key %r' % m.group(1))
        require_nways(a)
        n = int(m.group(2))
        _check_block(a, n)
        if check_digit(a, n) != int(m.group(3)):
            raise ValueError('check digit does not match: mistyped code?')
        return {'kind': 'compound', 'area': a['key'], 'number': n, 'structure': int(m.group(4)) if m.group(4) else None,
                'entrance': int(m.group(5)) if m.group(5) else None, 'checked': True}
    if re.fullmatch(r'(?:TG-)?[A-Z0-9]+-[%s]+-[%s]+' % (ALPHABET, ALPHABET), u) and not re.search(r'-\d{4,5}-\d$', u):
        try:
            lat, lon, _ = decode_spot(areas, u)
            return {'kind': 'spot', 'lat': lat, 'lon': lon}
        except ValueError:
            pass
    s = STREET_CODE.match(u)
    if s and s.group(2).upper() in areas.by_key:
        return {'kind': 'lome-street-code', 'street': int(s.group(1)), 'quartier': s.group(2).upper(),
                'note': 'Lomé street code (street %s of quartier %s), not an N-Ways code' % (s.group(1), s.group(2).upper())}
    m = re.fullmatch(r'(.+?)[\s,·:-]+((?:\d[\s.]?){3}\d(?:[\s.]?\d)?)(?:\s*-\s*(\d))?', u)
    if not m:
        raise ValueError('not a Togo N-Ways code: %r' % text)
    place = clean_place_name(m.group(1).strip(), m.group(1).strip())[0]
    digits = re.sub(r'\D', '', m.group(2))
    n = int(digits)
    if not areas.numbered(place):
        raise ValueError('unknown place %r' % place)
    # The name + number alone decide the area, anywhere in Togo: same-named areas own disjoint blocks
    # of the name's national range (SPEC 3.1). No préfecture, no position, no context.
    a = areas.decode(place, n)
    if a is None:
        raise ValueError('no N-Ways address %s %s: that number is in no block of the name %r' % (place, pairs(n), place))
    out = {'kind': 'compound', 'area': a['key'], 'number': n, 'structure': None, 'entrance': None, 'checked': False}
    if m.group(3) is not None:
        if check_digit(a, n) != int(m.group(3)):
            raise ValueError('check digit does not match: mistyped code?')
        out['checked'] = True
    return out


def _check_block(a, n):
    if not block_of(a, n):
        raise ValueError('%s has no number %d (its numbers: %s)' % (a['key'], n, ', '.join('%d-%d' % tuple(b) for b in a['blocks'])))



# ---------------------------------------------------------------- compounds: grouping
def _local(poly, lat0, lon0):
    m_lat, m_lon = metres(lat0)
    return [((x - lon0) * m_lon, (y - lat0) * m_lat) for x, y in poly]


def _area_m2(pts):
    s = 0.0
    for i in range(len(pts) - 1):
        s += pts[i][0] * pts[i + 1][1] - pts[i + 1][0] * pts[i][1]
    return abs(s) / 2.0


def _seg_dist(p, a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    L = dx * dx + dy * dy
    t = 0.0 if L == 0 else max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / L))
    qx, qy = a[0] + t * dx, a[1] + t * dy
    return math.hypot(p[0] - qx, p[1] - qy)


def gap_m(pa, pb):
    """Smallest distance in metres between two footprints (0 if they touch or overlap)."""
    if any(_ring_contains(pb, x, y) for x, y in pa) or any(_ring_contains(pa, x, y) for x, y in pb):
        return 0.0
    d = min(_seg_dist(p, pb[i], pb[i + 1]) for p in pa for i in range(len(pb) - 1))
    return min(d, min(_seg_dist(p, pa[i], pa[i + 1]) for p in pb for i in range(len(pa) - 1)))


URBAN = {'annex_m2': 30.0, 'attach_m': 6.0, 'hut_m2': 0.0}
RURAL_NORTH = {'annex_m2': 30.0, 'attach_m': 8.0, 'hut_m2': 35.0, 'hut_gap_m': 3.0, 'hut_max': 20}


def group_compounds(structures, enclosures=(), params=URBAN):
    """Group structures (footprints) into compounds. Returns a list of compounds:
    {'members': [ids], 'rule': enclosure|annex|hut-cluster|single, 'confidence': float}.

    structures: [{'id', 'ring': [[lon, lat], ...]}]; enclosures: [[[lon, lat], ...]] (closed walls/fences).
    Rules, in order (SPEC "Compounds"): one enclosure -> one compound; small annexes join the nearest main
    structure; small huts chain into one compound (rural north only); otherwise one structure, one compound.
    """
    if not structures:
        return []
    lat0 = sum(p[1] for s in structures for p in s['ring']) / sum(len(s['ring']) for s in structures)
    lon0 = sum(p[0] for s in structures for p in s['ring']) / sum(len(s['ring']) for s in structures)
    S = {}
    for s in structures:
        pts = _local(s['ring'], lat0, lon0)
        cx = sum(p[0] for p in pts[:-1]) / (len(pts) - 1)
        cy = sum(p[1] for p in pts[:-1]) / (len(pts) - 1)
        S[s['id']] = {'pts': pts, 'area': _area_m2(pts), 'c': (cx, cy)}
    E = [_local(e, lat0, lon0) for e in enclosures]
    parent = {i: i for i in S}
    rule = {i: 'single' for i in S}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    for e in E:
        if _area_m2(e) > 6000:
            continue  # an estate or institution wall: compounds are found inside it
        inside = [i for i, s in S.items() if _ring_contains(e, *s['c'])]
        for i in inside[1:]:
            union(inside[0], i)
        for i in inside:
            rule[i] = 'enclosure'
    ids = sorted(S)
    near = {i: [] for i in ids}
    for a_i, a in enumerate(ids):
        for b in ids[a_i + 1:]:
            if math.dist(S[a]['c'], S[b]['c']) > 60:
                continue
            g = gap_m(S[a]['pts'], S[b]['pts'])
            if g <= 12:
                near[a].append((g, b))
                near[b].append((g, a))
    for i in ids:
        if rule[i] != 'single' or S[i]['area'] >= params['annex_m2']:
            continue
        c = sorted((g, j) for g, j in near[i] if g <= params['attach_m'] and S[j]['area'] >= params['annex_m2'])
        if c:
            union(c[0][1], i)
            rule[i] = 'annex'
            if rule[c[0][1]] == 'single':
                rule[c[0][1]] = 'annex'
    if params.get('hut_m2'):
        size = {i: 1 for i in ids}
        for i in ids:
            if S[i]['area'] >= params['hut_m2'] or rule[i] == 'enclosure':
                continue
            for g, j in near[i]:
                if g <= params['hut_gap_m'] and S[j]['area'] < params['hut_m2'] and rule[j] == 'single' and rule[i] in ('single', 'hut-cluster'):
                    # huts chain only with huts that belong to no house: a cluster never joins two houses
                    ri, rj = find(i), find(j)
                    if ri != rj and size[ri] + size[rj] <= params['hut_max']:
                        parent[rj] = ri
                        size[ri] += size[rj]
                        for k in (i, j):
                            if rule[k] == 'single':
                                rule[k] = 'hut-cluster'
    groups = {}
    for i in ids:
        groups.setdefault(find(i), []).append(i)
    conf = {'enclosure': 0.85, 'annex': 0.6, 'hut-cluster': 0.5, 'single': 0.4}
    out = []
    for root, ms in groups.items():
        r = max((rule[m] for m in ms), key=lambda x: conf[x])
        main = max(ms, key=lambda m: S[m]['area'])
        out.append({'members': sorted(ms, key=lambda m: -S[m]['area']), 'main': main, 'rule': r, 'confidence': conf[r]})
    return sorted(out, key=lambda c: str(c['main']))


def group_footprints(fs, params=URBAN):
    """Production grouping of one code area: the rules of group_compounds, at country scale.

    fs: dicts with id (stable structure id), ring ([lon, lat] closed), area (m2), eid (the smallest
    closed enclosure of at most 6,000 m2 holding the centre, or None). Footprints are taken in id order,
    neighbours found on a 40 m grid, so the result never depends on the data's order. Rules, in order:
      enclosure    every footprint inside one enclosure is one compound;
      annex        a footprint under annex_m2 joins the nearest footprint of at least annex_m2 within
                   attach_m, outline to outline (only annexes join, and only to a building);
      hut-cluster  (rural north) huts under hut_m2 that belong to no house chain within hut_gap_m, at
                   most hut_max per compound: a cluster never joins two houses;
      single       everything else.
    Returns [(member indexes largest first, rule)] sorted by the main footprint's id."""
    if not fs:
        return []
    lat0 = sum(f['ring'][0][1] for f in fs) / len(fs)
    lon0 = sum(f['ring'][0][0] for f in fs) / len(fs)
    order = sorted(range(len(fs)), key=lambda i: fs[i]['id'])
    pts = [_local(f['ring'], lat0, lon0) for f in fs]
    cent = [(sum(p[0] for p in q[:-1]) / max(1, len(q) - 1), sum(p[1] for p in q[:-1]) / max(1, len(q) - 1)) for q in pts]
    parent = list(range(len(fs)))
    rule = ['single'] * len(fs)

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    first_in = {}
    for i in order:
        e = fs[i].get('eid')
        if e:
            r = first_in.setdefault(e, i)
            parent[find(i)] = find(r)
            rule[i] = 'enclosure'
    CELL = 40.0
    grid = collections.defaultdict(list)
    for i in order:
        grid[(int(cent[i][0] // CELL), int(cent[i][1] // CELL))].append(i)

    def around(i, reach):
        cx, cy = int(cent[i][0] // CELL), int(cent[i][1] // CELL)
        k = int(reach // CELL) + 2
        for dx in range(-k, k + 1):
            for dy in range(-k, k + 1):
                for j in grid.get((cx + dx, cy + dy), ()):
                    if j != i and math.dist(cent[i], cent[j]) <= 60:
                        yield j
    for i in order:
        if rule[i] != 'single' or fs[i]['area'] >= params['annex_m2']:
            continue
        best = None
        for j in around(i, params['attach_m']):
            if fs[j]['area'] < params['annex_m2']:
                continue
            g = gap_m(pts[i], pts[j])
            if g <= params['attach_m'] and (best is None or (g, fs[j]['id']) < (best[0], fs[best[1]]['id'])):
                best = (g, j)
        if best:
            parent[find(i)] = find(best[1])
            rule[i] = 'annex'
            if rule[best[1]] == 'single':
                rule[best[1]] = 'annex'
    if params.get('hut_m2'):
        size = collections.Counter(find(i) for i in range(len(fs)))
        for i in order:
            if fs[i]['area'] >= params['hut_m2'] or rule[i] not in ('single', 'hut-cluster'):
                continue
            for j in sorted(around(i, params['hut_gap_m']), key=lambda j: fs[j]['id']):
                if fs[j]['area'] >= params['hut_m2'] or rule[j] not in ('single', 'hut-cluster'):
                    continue
                if gap_m(pts[i], pts[j]) > params['hut_gap_m']:
                    continue
                ri, rj = find(i), find(j)
                if ri != rj and size[ri] + size[rj] <= params['hut_max']:
                    parent[rj] = ri
                    size[ri] += size[rj]
                    rule[i] = rule[j] = 'hut-cluster'
    groups = collections.defaultdict(list)
    for i in order:
        groups[find(i)].append(i)
    conf = {'enclosure': 0.85, 'annex': 0.6, 'hut-cluster': 0.5, 'single': 0.4}
    out = []
    for ms in groups.values():
        ms.sort(key=lambda i: (-fs[i]['area'], fs[i]['id']))
        out.append((ms, max((rule[m] for m in ms), key=lambda x: conf[x])))
    return sorted(out, key=lambda g: fs[g[0][0]]['id'])


# ---------------------------------------------------------------- compounds: numbering
def block_of(area, number):
    """The block [lo, hi] of the area that holds `number`, or None."""
    for lo, hi in area.get('blocks') or []:
        if lo <= number <= hi:
            return lo, hi
    return None


def first_block(area):
    lo, hi = area['blocks'][0]
    return lo, hi


def capacity(area):
    """Numbers in the area's first block (its share of the name's national range)."""
    lo, hi = first_block(area)
    return hi - lo + 1


def hilbert_of(area, lat, lon):
    f = area
    x0, y0, x1, y1 = f['box']
    n = (1 << HILBERT_ORDER) - 1
    fx = 0.0 if x1 == x0 else (lon - x0) / (x1 - x0)
    fy = 0.0 if y1 == y0 else (lat - y0) / (y1 - y0)
    x = min(n, max(0, int(fx * n)))
    y = min(n, max(0, int(fy * n)))
    return hilbert_index(HILBERT_ORDER, x, y)


def number_compounds(area, compounds):
    """First issue in an area. compounds: [{'id', 'lat', 'lon'}] (gate, else main-structure centroid).
    Returns {id: number}. Numbers follow the Hilbert curve; step s leaves s-1 free numbers after each
    compound for infill; the top third of the range is kept as tail reserve."""
    require_nways(area)
    require_plate(area)
    lo, _ = first_block(area)
    cap = capacity(area)
    n = len(compounds)
    if n * 2 > cap:
        raise ValueError('%s: %d compounds need a block of %d numbers, the block has %d (allocate the block from the '
                         'real count before first issue)' % (area['key'], n, n * 2, cap))
    step = max(1, int(cap // (n * 1.5))) if n else 1
    order = sorted(compounds, key=lambda c: (hilbert_of(area, c['lat'], c['lon']), str(c['id'])))
    return {c['id']: lo + i * step for i, c in enumerate(order)}


def tail_start(area):
    lo, _ = first_block(area)
    return lo + int(capacity(area) * 2 // 3)


def provisional_number(area, issued, lat, lon):
    """Number for a new compound (Add my home, new footprint). issued: [{'number', 'lat', 'lon'}] already
    in this area (including retired numbers, which are never reused). The new number lies between its
    Hilbert neighbours' numbers, as close to the midpoint as possible; otherwise the lowest free
    tail-reserve number."""
    require_nways(area)
    require_plate(area)
    h = hilbert_of(area, lat, lon)
    used = {c['number'] for c in issued}
    seq = sorted(((hilbert_of(area, c['lat'], c['lon']), c['number']) for c in issued if c['number'] < tail_start(area)))
    lo, hi = first_block(area)
    before = [num for hh, num in seq if hh <= h]
    after = [num for hh, num in seq if hh > h]
    a = before[-1] if before else lo - 1
    b = after[0] if after else tail_start(area)
    if b - a > 1:
        mid = (a + b) // 2
        for d in range(0, b - a):
            for cand in (mid - d, mid + d):
                if a < cand < b and cand not in used:
                    return cand
    for cand in range(tail_start(area), hi + 1):
        if cand not in used:
            return cand
    for lo2, hi2 in area['blocks'][1:]:  # extra blocks given later from the name's spare space
        for cand in range(lo2, hi2 + 1):
            if cand not in used:
                return cand
    raise AreaFull('%s is full: give it an extra block from the spare space of its name (SPEC 3.1)' % area['key'])


class AreaFull(ValueError):
    """Raised when an area has no free number left in any of its blocks."""


MIN_BLOCK = 200
NAME_PARTS = ((1000, 9999), (10000, 99999))   # the 4-digit and the 5-digit part of a name's national range


def block_size(compounds):
    """Size of a block: twice the compounds, rounded up to whole hundreds, at least 200 (SPEC 3.1 rule 4)."""
    return max(MIN_BLOCK, int(math.ceil(compounds * 2 / 100.0)) * 100)


def next_block(areas, area, compounds):
    """An extra block for a full area (SPEC 3.1 rule 7): the next free run of block_size(compounds)
    numbers after every block of the name, in the name's 4-digit part if it fits there, else in its
    5-digit part. The block is appended to area['blocks'] and returned; None when the name has no room.
    `areas` gives the other areas of the name (same nameKey), whose blocks count as used."""
    size = block_size(compounds)
    used = []
    for a in areas.areas:
        if a.get('numberLength') and a.get('blocks') and a.get('nameKey') == area.get('nameKey'):
            used.extend(area['blocks'] if a['key'] == area['key'] else a['blocks'])
    for lo, hi in NAME_PARTS:
        top = lo - 1
        for b in used:
            if lo <= b[1] <= hi and b[1] > top:
                top = b[1]
        if top + size <= hi:
            block = [top + 1, top + size]
            area['blocks'] = list(area['blocks']) + [block]
            return block
    return None


def insert_number(areas, area, issued, lat, lon):
    """Number of a new compound once the area has codes: provisional_number, and when the area is
    full, the first number of a new block of its name (next_block). issued: every number the area
    holds, retired ones included. Raises AreaFull when the name's range has no room left."""
    try:
        return provisional_number(area, issued, lat, lon)
    except AreaFull:
        block = next_block(areas, area, len(issued) + 1)
        if block is None:
            raise
        return block[0]


# ---------------------------------------------------------------- official addresses (Grand Lomé)
def official_text(rec):
    """The address exactly as the official source writes it. rec: {'number', 'street', 'streetCode',
    'quartier', 'commune', 'source'}; nothing is re-spelt, re-cased or translated."""
    parts = []
    if rec.get('number'):
        parts.append(str(rec['number']))
    street = rec.get('street') or rec.get('streetCode')
    if street:
        parts.append(street)
    head = ', '.join(parts)
    tail = ', '.join(x for x in (rec.get('quartier'), rec.get('commune')) if x)
    return head + (', ' + tail if tail and head else tail)


def attach_official(compounds, records, max_m=15.0):
    """Attach official address records (with a point) to compound entrances.

    compounds: [{'id', 'gates': [{'n', 'lat', 'lon'}]}]; records: [{'id', 'lat', 'lon', ...official fields}].
    Each record goes to the nearest gate within max_m metres; a gate takes at most one record (the
    nearest). Records left over are reported, never forced onto a compound. Returns (links, unmatched)."""
    gates = [(c['id'], g) for c in compounds for g in c['gates']]
    cand = []
    for r in records:
        m_lat, m_lon = metres(r['lat'])
        for cid, g in gates:
            d = math.hypot((g['lat'] - r['lat']) * m_lat, (g['lon'] - r['lon']) * m_lon)
            if d <= max_m:
                cand.append((d, r['id'], cid, g['n']))
    links, used_r, used_g = [], set(), set()
    for d, rid, cid, gn in sorted(cand):
        if rid in used_r or (cid, gn) in used_g:
            continue
        used_r.add(rid)
        used_g.add((cid, gn))
        rec = next(x for x in records if x['id'] == rid)
        links.append({'record': rid, 'compound': cid, 'entrance': gn, 'distanceM': round(d, 1), 'text': official_text(rec),
                      'source': rec.get('source')})
    unmatched = [r['id'] for r in records if r['id'] not in used_r]
    return links, unmatched


# ---------------------------------------------------------------- profile helpers
def floors_from_height(h):
    """Estimated storeys from an OpenStreetMap height in metres. Never from the Google/Microsoft 'h',
    a rendering filler (36 values spread evenly over 3.5-7 m)."""
    return max(1, int(round(h / 3.0)))


# ---------------------------------------------------------------- command line
def main(argv):
    import argparse
    ap = argparse.ArgumentParser(description='N-Ways address engine for Togo (reference).')
    sub = ap.add_subparsers(dest='cmd', required=True)
    s = sub.add_parser('spot', help='spot code of a point')
    s.add_argument('lat', type=float)
    s.add_argument('lon', type=float)
    d = sub.add_parser('decode', help='decode a spot code')
    d.add_argument('code')
    w = sub.add_parser('where', help='code area of a point')
    w.add_argument('lat', type=float)
    w.add_argument('lon', type=float)
    p = sub.add_parser('parse', help='read a code as typed or said')
    p.add_argument('text')
    f = sub.add_parser('format', help='forms of a compound code')
    f.add_argument('area')
    f.add_argument('number', type=int)
    a = ap.parse_args(argv)
    areas = Areas()
    if a.cmd == 'spot':
        print(encode_spot(areas, a.lat, a.lon))
    elif a.cmd == 'decode':
        lat, lon, cell = decode_spot(areas, a.code)
        print('%.7f %.7f  (cell %.2f m x %.2f m)' % (lat, lon, cell[0], cell[1]))
    elif a.cmd == 'where':
        ar = areas.at(a.lat, a.lon)
        print(json.dumps({k: ar[k] for k in ('key', 'kind', 'name', 'numberLength', 'index')} if ar else None, ensure_ascii=False))
    elif a.cmd == 'parse':
        print(json.dumps(parse(areas, a.text), ensure_ascii=False))
    elif a.cmd == 'format':
        ar = areas.by_key[a.area]
        require_nways(ar)
        _check_block(ar, a.number)
        print(remembered(ar, a.number))
        print(machine(ar, a.number))
        print(spoken_fr(areas, ar, a.number))


if __name__ == '__main__':
    try:
        main(sys.argv[1:])
    except ValueError as e:   # a refused code or point: say why, without a traceback
        sys.exit('refused: %s' % e)
