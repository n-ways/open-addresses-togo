#!/usr/bin/env python3
"""Plate names: the short name of a code area used in the remembered code (engine/SPEC.md 3.2).

A code area keeps two names:
  * the OFFICIAL name: the full name from the map or the commune list, printed
    in small type on cards and plates for context, and accepted when typed;
  * the PLATE name: what people say and type in the remembered code
    ("Démakpoè 24 17"). At most MAX_CHARS characters (every character of the
    NFC form counts once: letters, spaces, hyphens, apostrophes; an accented
    letter is one) and at most MAX_WORDS words (a word is a part between
    spaces or hyphens that is not a linking word such as de, du, des).

derive() turns an official name into a plate name, in this order:
  1. a documented short form people already say (the KNOWN table of
     tools/name_ranges.py, every entry with a source) wins;
  2. clean: drop text in brackets, text after a slash, the second of two
     spellings joined by "ou"/"dit"/"alias", generic French words (Quartier,
     Lotissement, Cité, Zone, Village...), a word repeated in another local
     spelling, and a linking word left at either end once a generic word is
     gone ("Cité de Djagblé" -> "Djagblé", not "de Djagblé");
  3. if the cleaned name fits, it is the plate name;
  4. else candidates: every run of whole words of the cleaned name with at
     most MAX_WORDS content words and at most MAX_CHARS characters, never
     starting or ending on a linking word, never only generic or landform
     words, never a number alone. A word is never cut;
  5. candidates are ranked by distinctiveness (how rare their words are among
     all of Togo's area names) with a preference for the specific end of
     the name (the last content word: "Adjahun Fiagbe" -> "Fiagbe");
  6. the best candidate is taken automatically when it is clearly ahead
     (only candidate, or its score is at least CLEAR x the next one) and it is
     not a well-known town (the avoid set: préfecture seats, Lomé's
     quartiers, the big towns of the region); otherwise the area is flagged
     needsCouncilChoice with up to 3 candidates, the first one used
     provisionally so the area can be numbered. A single word longer than
     MAX_CHARS has no candidate: it is flagged and kept whole provisionally.

Area names are written in French spelling (Ewe, Mina, Kabiyè, Tem, Moba and other names), so the word
lists below are French; tools/name_ranges.py adds the Ewe and Mina settlement words.
"""
import collections
import re
import unicodedata

MAX_CHARS = 12
MAX_WORDS = 2
CLEAR = 1.5
MIN_LETTERS = 4   # an automatic short name has at least 4 letters ('Bè' alone needs the commune)

LINKING = {
    'fr': {'de', 'du', 'des', 'd', 'la', 'le', 'les', 'l', 'et', 'sur', 'en', 'au', 'aux', 'à'},
}
# Generic words: never the remembered part. Multi-word phrases first.
GENERIC = {
    'fr': ['village de', 'quartier', 'lotissement', 'cité', 'cite', 'zone', 'secteur', 'village', 'hameau',
           'campement'],
}
# Weak words: a plate name is never only these (dropping a generic word that
# leaves only them keeps the generic word: "Cité Verte" stays).
WEAK = {
    'fr': {'grand', 'grande', 'petit', 'petite', 'nouveau', 'nouvelle', 'ancien', 'ancienne', 'vieux', 'haut', 'haute',
           'bas', 'basse', 'nord', 'sud', 'est', 'ouest', 'centre', 'centrale', 'verte', 'vert', 'rouge', 'blanc',
           'blanche', 'saint', 'sainte', 'extension', 'plateau', 'entre'},
}
# Landform / settlement heads: real parts of a name, but the first to go when
# the name is too long ("Carrefour Agbalépédo" -> "Agbalépédo"); never a plate
# name alone.
HEADS = {
    'fr': {'carrefour', 'rue', 'avenue', 'route', 'cité', 'quartier', 'camp', 'marché', 'gare', 'cour', 'ville',
           'koro', 'kanda'},
}
SPLIT_ALT = re.compile(r'\s+(?:ou|or|dit|dite|alias|aka|a\.k\.a\.)\s+', re.I)


def nfc(s):
    return unicodedata.normalize('NFC', s)


def plain(s):
    s = ''.join(c for c in unicodedata.normalize('NFKD', s) if not unicodedata.combining(c))
    return s.lower().replace('’', "'").replace('`', "'")


def plate_length(s):
    """Characters as people count them on a plate: letters and spaces, an accented
    letter is one; a hyphen or apostrophe also counts as one."""
    return len(nfc(s).strip())


def _tokens(s):
    """Words with their separators: "Agoè-Démakpoè" -> ['Agoè', '-', 'Démakpoè'],
    "Cité d'Akodessewa" -> ['Cité', ' ', "d'", 'Akodessewa']."""
    out = []
    for part in re.split(r'(\s+|-)', nfc(s).strip()):
        if not part:
            continue
        if part.isspace():
            out.append(' ')
            continue
        m = re.match(r"^([dDlL]['’])(.+)$", part)
        if m:
            out += [m.group(1), m.group(2)]
        else:
            out.append(part)
    return out


def _is_link(w, lang):
    return plain(w).rstrip("'") in LINKING[lang]


def content_words(s, lang):
    return [w for w in _tokens(s) if w not in (' ', '-') and not _is_link(w, lang) and re.search(r'\w', w)]


def word_count(s, lang):
    return len(content_words(s, lang))


def fits(s, lang):
    return plate_length(s) <= MAX_CHARS and word_count(s, lang) <= MAX_WORDS and not re.search(r'\d', s)


def _join(tokens):
    s = ''
    for t in tokens:
        s += t
    return re.sub(r'\s+', ' ', s).strip(' -')


def _generic_patterns(lang, extra):
    phrases = sorted(set(GENERIC[lang]) | set(extra or ()), key=lambda p: -len(p))
    return [re.compile(r'(?<!\w)' + r'[\s-]+'.join(re.escape(w) for w in p.split()) + r'(?!\w)', re.I) for p in phrases]


def _strong(s, lang, weak_extra=()):
    weak = WEAK[lang] | set(weak_extra) | HEADS[lang]
    return any(plain(w) not in {plain(x) for x in weak} and not ROMAN.match(w) and len(w) >= 2 for w in content_words(s, lang))


def clean(official, lang, generic_extra=(), weak_extra=(), fold=None):
    """Step 2. Returns (cleaned name, [what was dropped])."""
    s, dropped = nfc(official).strip(), []
    s = re.sub(r'(?<=\w)\((\w+)\)(?=\w)', r'\1', s)  # "Kpa(l)imé" -> "Kpalimé"
    if '(' in s:
        t = re.sub(r'\s*\([^)]*\)?\s*', ' ', s).strip()
        if t:
            dropped.append('brackets'); s = t
    if '/' in s:
        t = s.split('/')[0].strip()
        if t and _strong(t, lang, weak_extra):
            dropped.append('after slash'); s = t
    parts = SPLIT_ALT.split(s)
    if len(parts) > 1 and _strong(parts[0], lang, weak_extra):
        dropped.append('second spelling'); s = parts[0].strip()
    for pat in _generic_patterns(lang, generic_extra):
        t = re.sub(r'\s+', ' ', pat.sub(' ', s)).strip(' -')
        if t != s and t and _strong(t, lang, weak_extra):
            dropped.append('generic: ' + pat.pattern); s = t
    # hyphenated scheme label: "X-Y" where X alone was generic is handled above;
    # a duplicated local spelling: two adjacent words that fold the same
    if fold:
        ws = s.split()
        keep = [w for i, w in enumerate(ws) if i == 0 or fold(w) != fold(ws[i - 1])]
        if len(keep) < len(ws):
            dropped.append('duplicate spelling'); s = ' '.join(keep)
    s = re.sub(r'\s+', ' ', s).strip(' -,')
    # a linking word left at either end by a dropped generic word: "Cité de Djagblé" -> "Djagblé"
    us = _units(s, lang) if any(x.startswith('generic') for x in dropped) else []
    while len(us) > 1 and _is_link(us[0], lang):
        us = us[1:]
    while len(us) > 1 and _is_link(us[-1], lang):
        us = us[:-1]
    if us and _join_units(us) != s:
        s = _join_units(us)
    return s, dropped


# A word that binds to the next one: never cut between them ("Saint | Joseph",
# "Notre | Dame", "Jean | Paul").
BINDING = {'saint', 'sainte', 'st', 'ste', 'st.', 'notre', 'mont', 'el', 'el-hadji', 'elhadji', 'hadj', 'jean', 'pierre',
           'marie', 'paul', 'jacques', 'louis', 'mohamed'}
# Standard abbreviations of a binding prefix, tried before any word is
# dropped ("Sainte Thérèse" -> "Ste Thérèse"): the name key expands them back,
# so the full form typed still decodes.
ABBREV = {'fr': [('Sainte', 'Ste'), ('Saint', 'St'), ('Notre-Dame', 'N.-D.')]}
ROMAN = re.compile(r'^(?:[ivx]+|\d+[a-z]?|[a-z])$', re.I)


def _units(s, lang):
    """Space-separated units; an elided linking word becomes its own unit
    ("d'Akodessewa" -> "d'", "Akodessewa"); a hyphen compound stays one unit."""
    out = []
    for u in nfc(s).split():
        m = re.match(r"^([dDlL]['’])(.+)$", u)
        out += [m.group(1), m.group(2)] if m else [u]
    return out


def _join_units(us):
    s = ''
    for i, u in enumerate(us):
        s += u if (i == 0 or re.search(r"['’]$", us[i - 1])) else ' ' + u
    return s


def candidates(cleaned, lang, freq, weak_extra=()):
    """Steps 4-5. -> [(span, score, notes)], best first. notes: 'qualifier'
    (drops a trailing qualifier such as Haut, Bas, Kopé: never taken
    without the council), 'weak' (only weak or landform words)."""
    us = _units(cleaned, lang)
    link = [_is_link(u, lang) for u in us]
    weak = {plain(x) for x in WEAK[lang] | set(weak_extra)}
    heads = {plain(x) for x in HEADS[lang]}
    words = lambda u: [w for w in re.split(r'-', u) if w]
    strong_pos = [i for i, u in enumerate(us) if not link[i] and any(plain(w) not in weak | heads and not ROMAN.match(w) for w in words(u))]
    first_strong = strong_pos[0] if strong_pos else None
    quals = {i for i, u in enumerate(us) if not link[i] and first_strong is not None and i > first_strong
             and all(plain(w) in weak or ROMAN.match(w) for w in words(u))}
    content = [i for i in range(len(us)) if not link[i]]
    last = content[-1] if content else None
    out = {}
    for a in range(len(us)):
        for b in range(a, len(us)):
            if link[a] or link[b]:
                continue
            p = a - 1
            while p >= 0 and link[p]:
                p -= 1
            if p >= 0 and plain(us[p]) in BINDING:
                continue  # never "Joseph" out of "Saint Joseph"
            if plain(us[b]) in BINDING:
                continue
            span = _join_units(us[a:b + 1])
            if not fits(span, lang):
                continue
            ws = [w for u in us[a:b + 1] if not _is_link(u, lang) for w in words(u)]
            notes = []
            if not any(plain(w) not in weak | heads and not ROMAN.match(w) for w in ws):
                notes.append('weak')
            if any(q < a or q > b for q in quals):
                notes.append('qualifier')
            score = sum(1.0 / max(1, freq.get(plain(w), 1)) for w in ws if plain(w) not in weak | heads)
            score += 0.25 * sum(1 for w in ws if plain(w) in weak)
            if b == last:
                score *= 1.5
            if notes:
                score *= 0.1
            if span not in out or out[span][0] < score:
                out[span] = (score, notes)
    out = {k: v for k, v in out.items() if 'weak' not in v[1]}  # "Grand", "Bas" alone are never a name
    return sorted(((s, v[0], v[1]) for s, v in out.items()), key=lambda t: (-t[1], plate_length(t[0]), t[0]))


def word_freq(names, lang):
    """How many official names each folded content word appears in."""
    c = collections.Counter()
    for n in names:
        for w in set(plain(x) for x in content_words(n, lang)):
            c[w] += 1
    return c


def _derive(official, lang, freq, known=None, avoid=(), generic_extra=(), weak_extra=(), fold=None, avoid_key=None):
    """-> {'plate', 'official', 'rule', 'needsCouncilChoice', 'candidates', 'dropped'}.
    known: {official name: (plate, source)} documented short forms.
    avoid: folded names of well-known towns elsewhere a plate must not equal
    (the caller removes the area's own town). avoid_key: the fold for it."""
    key = avoid_key or plain
    avoid = {key(a) for a in avoid}
    res = {'official': official, 'needsCouncilChoice': False, 'candidates': [], 'dropped': []}
    if known and official in known:
        p, src = known[official]
        res.update(plate=p, rule='known', source=src)
        return res
    cl, dropped = clean(official, lang, generic_extra, weak_extra, fold)
    res['dropped'] = dropped
    if fits(cl, lang):
        res.update(plate=cl, rule='as-is' if cl == nfc(official).strip() else 'cleaned')
        if res['rule'] == 'cleaned' and key(cl) in avoid:
            res.update(needsCouncilChoice=True, candidates=[cl], reason='equals a well-known town elsewhere')
        return res
    if plain(cl).split()[0] in ('entre', 'between'):
        cs = candidates(cl, lang, freq, weak_extra)
        res.update(plate=cs[0][0] if cs else cl, rule='council', needsCouncilChoice=True,
                   candidates=[c[0] for c in cs[:3]], reason='a name "between X and Y" needs a choice')
        return res
    for full, short in ABBREV[lang]:
        ab = re.sub(r'(?<!\w)' + re.escape(full) + r'(?!\w)', short, cl)
        if ab != cl and fits(ab, lang):
            res.update(plate=ab, rule='abbreviated')
            if key(ab) in avoid:
                res.update(needsCouncilChoice=True, candidates=[ab], reason='equals a well-known town elsewhere')
            return res
    cs = candidates(cl, lang, freq, weak_extra)
    if not cs:
        res.update(plate=cl, rule='council', needsCouncilChoice=True, candidates=[],
                   reason='no run of whole words fits %d characters and %d words' % (MAX_CHARS, MAX_WORDS))
        return res
    best = cs[0]
    nxt = cs[1][1] if len(cs) > 1 else 0.0
    res['candidates'] = [c[0] for c in cs[:3]]
    letters = sum(1 for ch in best[0] if ch.isalpha())
    if not best[2] and best[1] >= CLEAR * nxt and key(best[0]) not in avoid and letters >= MIN_LETTERS:
        res.update(plate=best[0], rule='distinctive')
        return res
    why = ('equals a well-known town elsewhere' if key(best[0]) in avoid else
           'every short form drops a qualifier (Haut, Bas, Kopé...)' if 'qualifier' in best[2] else
           'only weak words fit' if 'weak' in best[2] else
           'too short to be a name on its own' if letters < MIN_LETTERS else 'no clear choice')
    res.update(plate=best[0], rule='council', needsCouncilChoice=True, reason=why)
    return res


def _cap(s, lang):
    us = s.split(' ')
    return ' '.join(u[:1].upper() + u[1:] if u and u.islower() and not _is_link(u, lang) else u for u in us)


def derive(official, lang, freq, **kw):
    """See _derive: also capitalises a lower-case word of the plate name
    ("Zongo kpota" -> "Zongo Kpota"); the official name is never changed."""
    r = _derive(official, lang, freq, **kw)
    r['plate'] = _cap(r['plate'], lang)
    r['candidates'] = [_cap(c, lang) for c in r['candidates']]
    return r


if __name__ == '__main__':
    import sys
    lang = sys.argv[1]
    for n in sys.argv[2:]:
        print(derive(n, lang, collections.Counter()))
