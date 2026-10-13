import json, os, sys
sys.path.insert(0, os.environ['TEMP'] + '/rv')
B = 'manhua-series/dai-quan-gia-la-ma-hoang/'
HASH = ["#DaiQuanGiaLaMaHoang", "#ReviewManhua", "#Manhua", "#TuTien", "#XuyenKhong", "#ReviewTruyen"]
SERIES = 'Đại Quản Gia Là Ma Hoàng'
PAGEMAP = {}
PAGE_EPS = (81, 82, 83, 84, 85, 86, 87, 88)


def pm(n, page):
    if n not in PAGEMAP:
        PAGEMAP[n] = sorted(json.load(open(f'manhua-recap/dqgl_ep{n}/_recap/panel_pages.json')).items())
    best = None
    for pn, pg in PAGEMAP[n]:
        if int(pg[:3]) <= page:
            best = pn
        if int(pg[:3]) == page:
            return pn
    return best


_cache = {}


def script(n):
    if n not in _cache:
        if n == 'L':
            _cache[n] = json.load(open(B + 'long_1_10/script.json', encoding='utf-8'))
        else:
            _cache[n] = json.loads(open(B + f'ep{n}/script.json', encoding='utf-8-sig').read(), strict=False)
    return _cache[n]


def beat(n, i, text=None, kind=None):
    b = script(n)['beats'][i]
    if n == 'L':
        panel = b['panel']
    else:
        pn = b['panel']
        if n in PAGE_EPS:
            pn = pm(n, int(pn[1:4]))
        panel = f'{"dqg_ep" if 11 <= n <= 14 else "dqgl_ep"}{n}/{pn}'
    return dict(panel=panel, type='BUILD', kind=kind or b['kind'], narration=text or b['narration'])


def mk(sid, chapters, title, desc, entries, thumb):
    beats = []
    for e in entries:
        if isinstance(e, dict):
            beats.append(e)
        else:
            beats.append(beat(*e))
    for b in beats:
        b['narration'] = b['narration'].replace('Ngưng Hương', 'Ngưng Nhi').replace('Lý Quỷ', 'U Quỷ Thất')
    for i, b in enumerate(beats):
        b['type'] = 'HOOK' if i == 0 else 'ENDING' if i == len(beats) - 1 else 'BUILD'
    assert len(title) <= 70, (sid, len(title))
    words = sum(len(b['narration'].split()) for b in beats)
    s = dict(title=title, chapters=chapters, source_dir='manhua-recap/dqgl_ep1',
             written_by='Claude, best-of Short, 2026-10-13', description=desc, hashtags=HASH,
             thumbnail=dict(text=thumb[0], prompt=thumb[1]), beats=beats)
    d = B + f'best_of/{sid}'
    os.makedirs(d, exist_ok=True)
    json.dump(s, open(d + '/script.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    return len(beats), words, sum(b['kind'] == 'commentary' for b in beats)


def N(panel, text, kind='recap'):
    return dict(panel=panel, type='BUILD', kind=kind, narration=text)
