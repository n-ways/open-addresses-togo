#!/usr/bin/env python3
"""National name ranges for Togo (engine/SPEC.md 3.1): make every remembered code unique nationally.

A remembered code is a place name + a number ("Kara 24 17"). Togo repeats place names (four
"Lom-Nava", three "Kamina", "Bagou" in Tandjouaré and in Tchamba...). So all code areas whose names
fold to one national name key (tg_engine.name_key) draw their numbers from ONE national range for that
name, cut into blocks, one per area; the name + number alone decide the area, anywhere in Togo.

  python3 tools/name_ranges.py            rewrite model/areas/areas.json (names, nameId, blocks,
                                          numberLength) and model/areas/names.json; print the counts

Rules:
  * clean the place word (tg_engine.clean_place_name): 'Village de X' -> 'X', 'Zongo 1' -> 'Zongo',
    'unknow' -> the canton's name; the OpenStreetMap name is kept as osmName, the cleaned full name
    as officialName
  * plate name (engine/reference/plate_names.py, SPEC 3.2): the name in the remembered code, at most
    12 characters and 2 words; derived from officialName with Togo's word lists below; an area
    whose short form is a choice is flagged needsCouncilChoice with up to 3 candidates (the first
    one is used provisionally); the official name stays an alias when it maps to one plate name
  * a name's national space: a 4-digit part 1000-9999 and a 5-digit part 10000-99999
  * block of an area = its compounds x 2 (the per-area headroom of 0.1), rounded up to a hundred,
    at least 200 numbers; allocated at first issue from the real count, frozen, never renumbered
  * a block goes in the 4-digit part while it fits, else in the 5-digit part; areas are planned
    smallest block first (most areas keep 4 digits); a name always keeps >= 5,000 numbers spare
    (NAME_SPARE) for future same-named areas and for extra blocks of full areas
  * a name whose blocks do not fit with that spare takes one established qualifier per area, decided
    once and listed in names.json (QUALIFIERS); none is needed with today's counts
  * name ids: frozen 4-digit ordinals (alphabetical by key on the first build, appended afterwards);
    the check digit is Damm over name id + area index + number
"""
import collections, json, math, os, re, sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, 'engine', 'reference'))
import tg_engine as E  # noqa: E402
import plate_names as PN  # noqa: E402

AREAS = os.path.join(REPO, 'model', 'areas', 'areas.json')
NAMES = os.path.join(REPO, 'model', 'areas', 'names.json')
PART4 = (1000, 9999)
PART5 = (10000, 99999)
NAME_SPARE = 5000
MIN_BLOCK = 200
# Established qualifiers, decided once per name when its blocks cannot fit: {area key: 'Name Qualifier'}.
QUALIFIERS = {}

# ---- plate names (SPEC 3.2): Togo's word lists for engine/reference/plate_names.py
LANG = 'fr'   # area names are written in French spelling (Ewe, Kabiyè, Tem, Moba... names)
# Documented short forms {official name: (plate name, source)}. None is documented for Togo's code
# areas outside Grand Lomé (docs/existing-systems.md); add one only with a source.
KNOWN = {}
# French generic words found in Togo's OSM names (on top of the list in plate_names.py).
GENERIC_EXTRA = ['centre de formation rurale de', 'campment', 'ferme', 'résidence', 'carrefour']
# Ewe / Mina settlement words: kopé (copé, cope) = village, kondji (condji) = village (Mina, Gen),
# kodzi = village, kpota / kpotame = the outskirts, behind. "Aklassou kopé" is a village of its own,
# not Aklassou: dropping the word changes the place, so it is a qualifier (never dropped without
# the commune), like haut / bas.
WEAK_EXTRA = {'kope', 'cope', 'kondji', 'condji', 'kodzi', 'kpota', 'kpotame'}
# Chefs-lieux of the 39 préfectures (each also the seat of its first commune; the five region
# capitals are among them: Tsévié, Atakpamé, Sokodé, Kara, Dapaong).
SEATS = {
    'Agoe-Nyive': 'Agoè-Nyivé', 'Agou': 'Agou-Gadzépé', 'Akebou': 'Kougnohou', 'Amou': 'Amlamé', 'Anie': 'Anié',
    'Assoli': 'Bafilo', 'Ave': 'Kévé', 'Bas-Mono': 'Afagnan', 'Bassar': 'Bassar', 'Binah': 'Pagouda', 'Blitta': 'Blitta',
    'Cinkasse': 'Cinkassé', 'Dankpen': 'Guérin-Kouka', 'Danyi': 'Danyi-Apéyémé', 'Doufelgou': 'Niamtougou',
    'Est-Mono': 'Elavagnon', 'Golfe': 'Lomé', 'Haho': 'Notsé', 'Keran': 'Kandé', 'Kloto': 'Kpalimé', 'Kozah': 'Kara',
    'Kpele': 'Kpélé-Adéta', 'Kpendjal': 'Mandouri', 'Lacs': 'Aného', 'Lome Commune': 'Lomé', 'Moyen-Mono': 'Tohoun',
    'Naki-Ouest': 'Naki-Est', 'Ogou': 'Atakpamé', 'Oti': 'Mango', 'Oti-Sud': 'Gando', 'Plaine du Mo': 'Djarkpanga',
    'Sotouboua': 'Sotouboua', 'Tandjoare': 'Tandjouaré', 'Tchamba': 'Tchamba', 'Tchaoudjo': 'Sokodé', 'Tone': 'Dapaong',
    'Vo': 'Vogan', 'Wawa': 'Badou', 'Yoto': 'Tabligbo', 'Zio': 'Tsévié',
}
# Seats also known by their short form (the area of the seat itself may use it).
SEAT_SHORT = {'Danyi-Apéyémé': ['Apéyémé'], 'Kpélé-Adéta': ['Adéta'], 'Guérin-Kouka': ['Guérin'], 'Agou-Gadzépé': ['Gadzépé']}
# Towns across the borders that Togolese travellers and traders name every day (the border posts,
# the towns of the neighbouring regions, the capitals of the three neighbours and the ends of the
# Abidjan-Lagos corridor): a plate must not equal one of them.
OTHER_TOWNS = ['Hillacondji', 'Aflao', 'Ho', 'Keta', 'Kpando', 'Kumasi',
               'Tamale', 'Bolgatanga', 'Tema', 'Accra', 'Cotonou', 'Porto-Novo', 'Ouidah', 'Abomey', 'Bohicon',
               'Parakou', 'Djougou', 'Natitingou', 'Lagos', 'Abidjan', 'Ouagadougou']
# The 69 quartiers of Lomé are known nationwide too ("Akodessewa 24 17" must not point outside Lomé).
LOME_QUARTIERS = [f['properties']['name'] for f in json.load(open(os.path.join(REPO, 'model', 'units', 'keys.geojson'),
                  encoding='utf-8'))['features'] if f['properties']['kind'] == 'lome-quartier']
AVOID = {E.name_key(t) for t in list(SEATS.values()) + sum(SEAT_SHORT.values(), []) + OTHER_TOWNS + LOME_QUARTIERS}


def plate_for(official, own, freq):
    """Plate name of one area (SPEC 3.2). own: names of the area's own town (its préfecture seat,
    its canton), removed from the avoid set."""
    pre = re.sub(r'\s*-\s*', '-', official)        # "Esso - Vallai" -> "Esso-Vallai"
    own = [o for o in own if o] + [x for o in own for x in SEAT_SHORT.get(o, [])] + [official]
    own += [x.strip() for o in own for x in re.split(r'/', o)]   # canton "Elavagnon/Atigba": both are its towns
    avoid = AVOID - {E.name_key(o) for o in own}
    r = PN.derive(pre, LANG, freq, known=KNOWN, avoid=avoid, generic_extra=GENERIC_EXTRA, weak_extra=WEAK_EXTRA,
                  avoid_key=E.name_key)
    if r['rule'] == 'as-is' and pre != official:
        r['rule'] = 'cleaned'
    if r['needsCouncilChoice'] and not r['candidates'] and '-' in r['plate']:
        # one hyphen compound over the limit ("Landa-Pozenda"): each part is a word of its own, so a
        # part may be the plate name, but which one is the commune's choice
        parts = []
        for x in r['plate'].split('-'):
            if (PN.fits(x, LANG) and len(x) >= PN.MIN_LETTERS and PN.plain(x) not in PN.WEAK[LANG] | WEAK_EXTRA
                    and E.name_key(x) not in avoid and E.name_key(x) not in {E.name_key(p) for p in parts}):
                parts.append(x[:1].upper() + x[1:])
        if parts:
            # the rarer part first: in "Agoè-Démakpoè", "Agoè-Kitidjan" … the shared "Agoè" names none
            # of them, the second part is what people say ("à Démakpoè")
            order = {x: i for i, x in enumerate(parts)}
            parts.sort(key=lambda x: (freq.get(PN.plain(x), 0), order[x]))
            r['candidates'] = parts[:3]
            r['plate'] = parts[0]
            r['reason'] = 'two names joined by a hyphen: the commune chooses one'
    if PN.plate_length(r['plate']) > PN.MAX_CHARS or PN.word_count(r['plate'], LANG) > PN.MAX_WORDS:
        r['overLimit'] = True
    return r


def block_size(compounds):
    return max(MIN_BLOCK, int(math.ceil(compounds * 2 / 100.0)) * 100)


def main():
    data = json.load(open(AREAS, encoding='utf-8'))
    areas = data['areas']
    by_index = {a['index']: a for a in areas}
    cleaned = []
    for a in areas:
        if a.get('official'):
            continue
        if a.get('officialName') in a['aliases']:   # rebuilt below
            a['aliases'].remove(a['officialName'])
        fallback = by_index[a['parent']].get('officialName', by_index[a['parent']]['name']) if a['kind'] == 'cell' else a.get('officialName', a['name'])
        src = a.get('osmName', a.get('officialName', a['name']))
        name, changed = E.clean_place_name(src, fallback)
        if a['key'] in QUALIFIERS:
            name, changed = QUALIFIERS[a['key']], True
        aka = re.search(r'\((?:aka|dit|ou)\s*:?\s*([^)]+)\)', src, re.I)
        if aka and aka.group(1).strip() not in a['aliases']:
            a['aliases'].append(aka.group(1).strip())
        if changed:
            a.setdefault('osmName', src)
            cleaned.append((a['key'], a['osmName'], name))
        a['officialName'] = name
    numbered = [a for a in areas if a.get('numberLength') and not a.get('official')]
    # plate names (SPEC 3.2)
    freq = PN.word_freq([a['officialName'] for a in numbered], LANG)
    before = {'chars': sum(1 for a in numbered if PN.plate_length(a['officialName']) > PN.MAX_CHARS),
              'words': sum(1 for a in numbered if PN.word_count(a['officialName'], LANG) > PN.MAX_WORDS)}
    before['either'] = sum(1 for a in numbered if not PN.fits(a['officialName'], LANG))
    for k in ('plateName', 'plateRule', 'needsCouncilChoice', 'plateCandidates', 'plateReason', 'plateSource', 'aliasDropped'):
        for a in areas:
            a.pop(k, None)
    for a in numbered:
        canton = by_index[a['parent']] if a['kind'] == 'cell' else a
        r = plate_for(a['officialName'], [SEATS.get(a['prefecture'], ''), canton.get('officialName', canton['name'])], freq)
        a['name'] = a['spoken'] = r['plate']
        a['plateRule'] = r['rule']
        if r.get('source'):
            a['plateSource'] = r['source']
        if r['needsCouncilChoice']:
            a['needsCouncilChoice'] = True
            a['plateCandidates'] = r['candidates'][:3]
            a['plateReason'] = r.get('reason', '')
    for a in areas:  # unnumbered areas keep their name as it is
        if not (a.get('numberLength') and not a.get('official')):
            a.pop('officialName', None)
    # the official name decodes too, as an alias, when it maps to one plate name
    plate_keys = {E.name_key(a['name']) for a in numbered}
    claims = collections.defaultdict(set)
    for a in numbered:
        k = E.name_key(a['officialName'])
        if k != E.name_key(a['name']):
            claims[k].add(E.name_key(a['name']))
    dropped_aliases = []
    for a in numbered:
        k = E.name_key(a['officialName'])
        if k == E.name_key(a['name']):
            continue
        if k in plate_keys or len(claims[k]) > 1:
            a['aliasDropped'] = ('the official name is another plate name' if k in plate_keys
                                 else 'the official name maps to two plate names')
            dropped_aliases.append((a['key'], a['officialName'], a['aliasDropped']))
        elif a['officialName'] not in a['aliases']:
            a['aliases'].append(a['officialName'])
    groups = collections.defaultdict(list)
    for a in numbered:
        groups[E.name_key(a['name'])].append(a)
    holder = {k: g for k, g in groups.items()}
    for a in numbered:  # an alias may not be another name's key: it would make "Alias NNNN" ambiguous
        for al in a['aliases']:
            k = E.name_key(al)
            if k != E.name_key(a['name']) and k in holder:
                raise SystemExit('alias %r of %s collides with the name of %s' % (al, a['key'], holder[k][0]['key']))
    old, retired = {}, {}
    if os.path.exists(NAMES):
        prev = json.load(open(NAMES, encoding='utf-8'))
        old = {n['key']: n['id'] for n in prev['names']}
        retired = {r['key']: r['id'] for r in prev.get('retiredNameIds', [])}
    next_id = max(list(old.values()) + list(retired.values()), default=0) + 1
    names = []
    overflow = []
    for key in sorted(groups):
        if key in old:
            nid = old[key]
        else:
            nid = next_id
            next_id += 1
        used4 = used5 = 0
        members = sorted(groups[key], key=lambda a: (block_size(a['estCompounds']), a['index']))
        blocks = []
        for a in members:
            b = block_size(a['estCompounds'])
            if used4 + b <= PART4[1] - PART4[0] + 1:
                lo = PART4[0] + used4
                used4 += b
                L = 4
            elif used5 + b <= PART5[1] - PART5[0] + 1 - NAME_SPARE:
                lo = PART5[0] + used5
                used5 += b
                L = 5
            else:
                overflow.append((key, a['key'], a['estCompounds']))
                continue
            a['nameId'] = nid
            a['nameKey'] = key
            a['blocks'] = [[lo, lo + b - 1]]
            a['numberLength'] = L
            blocks.append({'area': a['key'], 'index': a['index'], 'name': a['name'], 'prefecture': a['prefecture'],
                           'estCompounds': a['estCompounds'], 'block': [lo, lo + b - 1], 'digits': L})
        names.append({'id': nid, 'key': key, 'spellings': sorted({a['name'] for a in members}),
                      'officialNames': sorted({a['officialName'] for a in members}), 'areas': len(members),
                      'estCompounds': sum(a['estCompounds'] for a in members), 'blocks': sorted(blocks, key=lambda x: x['block']),
                      'free4': PART4[1] - PART4[0] + 1 - used4, 'free5': PART5[1] - PART5[0] + 1 - used5})
    if overflow:
        raise SystemExit('names that need a qualifier (add to QUALIFIERS): %r' % overflow)
    for a in areas:  # official and unnumbered areas carry no name id or blocks
        if not (a.get('numberLength') and not a.get('official')):
            for k in ('nameId', 'nameKey', 'blocks'):
                a.pop(k, None)
    data['nameRanges'] = {'file': 'model/areas/names.json', 'rule': 'engine/SPEC.md 3.1'}
    json.dump(data, open(AREAS, 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
    rep = [n for n in names if n['areas'] > 1]
    largest = max(rep, key=lambda n: max(b['block'][1] for b in n['blocks']))
    top = max(max(b['block'][1] for b in n['blocks']) for n in rep)
    stats = {
        'numberedAreas': len(numbered), 'names': len(names), 'repeatedNames': len(rep),
        'areasUnderRepeatedNames': sum(n['areas'] for n in rep),
        'compoundsUnderRepeatedNames': sum(n['estCompounds'] for n in rep),
        'repeatedNamesAll4digit': sum(1 for n in rep if all(b['digits'] == 4 for b in n['blocks'])),
        'repeatedNamesWith5digitBlock': sum(1 for n in rep if any(b['digits'] == 5 for b in n['blocks'])),
        'largestSharedRange': {'name': largest['spellings'][0], 'key': largest['key'], 'areas': largest['areas'],
                               'estCompounds': largest['estCompounds'], 'highestNumber': top, 'digits': len(str(top)),
                               'blocks': [(b['area'], b['block'], b['digits']) for b in largest['blocks']]},
        'mostAreas': max(rep, key=lambda n: n['areas'])['spellings'],
        'areas4digits': sum(1 for a in numbered if a['numberLength'] == 4),
        'areas5digits': sum(1 for a in numbered if a['numberLength'] == 5),
        'shareOfCompoundsIn4digitAreas': round(sum(a['estCompounds'] for a in numbered if a['numberLength'] == 4)
                                               / sum(a['estCompounds'] for a in numbered), 3),
        'qualifiers': QUALIFIERS, 'cleanedNames': len(cleaned),
        'plateNames': {
            'limit': {'chars': PN.MAX_CHARS, 'words': PN.MAX_WORDS},
            'officialNamesOverLimit': before,
            'byRule': dict(collections.Counter(a['plateRule'] for a in numbered)),
            'needsCouncilChoice': sum(1 for a in numbered if a.get('needsCouncilChoice')),
            'stillOverLimit': sum(1 for a in numbered if not PN.fits(a['name'], LANG)),
            'officialAliasesDropped': len(dropped_aliases),
            'longestRemembered': max(('%s %s' % (a['name'], E.pairs(a['blocks'][0][1])) for a in numbered),
                                     key=lambda t: (PN.plate_length(t), t)),
            'longestRememberedNotFlagged': max(('%s %s' % (a['name'], E.pairs(a['blocks'][0][1])) for a in numbered
                                                if not a.get('needsCouncilChoice')), key=lambda t: (PN.plate_length(t), t)),
        },
    }
    out = {'country': 'TG', 'version': data['version'], 'frozen': False,
           'note': 'National name ranges (engine/SPEC.md 3.1). A name\'s blocks are frozen at first issue in each area '
                   'and never renumbered; new same-named areas and extra blocks come from the free space.',
           'parts': {'4': PART4, '5': PART5}, 'nameSpare': NAME_SPARE, 'minBlock': MIN_BLOCK,
           'blockRule': 'estimated compounds x 2 rounded up to 100 (>= 200); at first issue from the real count',
           'stats': stats, 'cleanedNames': [{'area': k, 'osm': o, 'name': n} for k, o, n in cleaned],
           'plateRule': 'engine/SPEC.md 3.2; tools/name_ranges.py plate_for; engine/reference/plate_names.py',
           'councilChoices': [{'area': a['key'], 'prefecture': a['prefecture'], 'officialName': a['officialName'],
                               'provisional': a['name'], 'candidates': a['plateCandidates'], 'reason': a['plateReason'],
                               'overLimit': not PN.fits(a['name'], LANG)}
                              for a in numbered if a.get('needsCouncilChoice')],
           'officialAliasesDropped': [{'area': k, 'officialName': o, 'why': w} for k, o, w in dropped_aliases],
           'retiredNameIds': sorted([{'key': k, 'id': i} for k, i in list(old.items()) + list(retired.items())
                                     if k not in groups], key=lambda r: r['id']),
           'names': names}
    json.dump(out, open(NAMES, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(json.dumps(stats, ensure_ascii=False, indent=1))
    for n in sorted(rep, key=lambda n: -n['estCompounds']):
        print('%-12s %d areas %6d compounds  %s' % (n['key'], n['areas'], n['estCompounds'],
              ' | '.join('%s %s %d-%d' % (b['area'], b['name'], b['block'][0], b['block'][1]) for b in n['blocks'])))


if __name__ == '__main__':
    main()
