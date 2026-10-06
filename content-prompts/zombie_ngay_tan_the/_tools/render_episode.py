"""Dựng thử một tập (video dài) trong app qua API: đăng ký ảnh -> tạo project -> beat plan (mỗi shot = 1 beat, đã gán ảnh) -> Factory run.

Dùng:  python render_episode.py 1 [ko|vi] [force] [short]   (short = video SHORT 9:16 từ ngay_tan_epN_short_*)
       python render_episode.py 1 [ko|vi] [force]   (force = tự chấp nhận cảnh báo Quality Gate để render; Tập 1; ko = template ngay_tan_ko, vi = template ngay_tan; mặc định ko)
Cần: backend đang chạy ở 127.0.0.1:8000; ảnh đã nằm trong ngay_tan_epN_images/ đúng tên file theo CSV;
     scripts/ko_epN_check.txt (câu Hàn đánh số), scripts/ko_bookends_check.txt (E{N}_INTRO/OUTRO), ngay_tan_epN_shotlist.md (cột Đoạn).
Ghi chú thiết kế:
 - Lời đọc được chia theo shot bằng cách rải đều các từ của mỗi đoạn cho các shot gắn với đoạn đó (ưu tiên ngắt ở dấu câu),
   nên đổi ảnh đúng nhịp mà không cắt TTS (các beat cùng giọng được gộp thành một lượt đọc, xem voice_generate.voice_runs).
 - Giới thiệu/kết là beat riêng đọc bằng giọng nam (Beat.voice_id), phần truyện bằng giọng nữ của template.
 - ai_metadata_enabled=False để không tốn tiền AI ở bước package.
"""
import csv
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import OrderedDict
from pathlib import Path

from PIL import Image

API = 'http://127.0.0.1:8000/api/v1'
HERE = Path(__file__).resolve().parent
D = HERE.parent
# Cấu hình theo ngôn ngữ. wps = từ/giây thực đo được, chỉ để ước lượng Beat.duration (Voice stage ghi đè bằng thời lượng thật).
# Quy tắc series: KO = giọng chính nữ + giới thiệu/kết nam; VI = giọng chính nam + giới thiệu/kết nữ.
LANGS = {
    'ko': {'template': 'ngay_tan_ko', 'bookend_voice': 'ko-KR-InJoonNeural', 'wps': 1.8, 'label': 'KO', 'short_speed': 1.2},
    'vi': {'template': 'ngay_tan', 'bookend_voice': 'vi-VN-HoaiMyNeural', 'wps': 3.6, 'label': 'VI', 'short_speed': 1.4},
}


def call(method, path, body=None):
    data = None if body is None else json.dumps(body).encode('utf-8')
    req = urllib.request.Request(API + path, data=data, method=method, headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            raw = r.read()
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as e:
        raise SystemExit(f'HTTP {e.code} {method} {path}: {e.read().decode("utf-8", "ignore")[:800]}')


def read_pairs(name):
    out = []
    for line in open(D / 'scripts' / name, encoding='utf-8'):
        line = line.rstrip('\n')
        if line.strip():
            k, t = line.split('|', 1)
            out.append((k, t))
    return out


def sfx(kind):
    return '_short' if kind == 'short' else ''


def parse_shotlist(ep, kind='long'):
    shots = []
    for line in open(D / f'ngay_tan_ep{ep}{sfx(kind)}_shotlist.md', encoding='utf-8'):
        m = re.match(r'\|\s*(\d+)\s*\|\s*(\S+\.png)\s*\|\s*([^|]*?)\s*\|', line)
        if m:
            shots.append((m.group(2), [p.strip() for p in m.group(3).split(',')]))
    return shots


def csv_tags(ep, kind='long'):
    fname = f'ngay_tan_ep{ep}_short_scenes.csv' if kind == 'short' else f'ngay_tan_ep{ep}_scenes_v3.csv'
    rows = list(csv.reader(open(D / fname, encoding='utf-8-sig')))[1:]
    return {r[1]: [t.strip() for t in r[2].split(',') if t.strip()] for r in rows}


def register_assets(ep, shots, tags, kind='long'):
    img_dir = D / f'ngay_tan_ep{ep}{sfx(kind)}_images'
    ids = {}
    for fn, _ in shots:
        path = img_dir / fn
        if not path.exists():
            raise SystemExit(f'Thiếu ảnh: {path}')
        found = call('GET', '/assets?q=' + urllib.parse.quote(fn))
        exact = [a for a in found if a.get('filename') == fn]
        if exact:
            ids[fn] = exact[0]['id']
            continue
        with Image.open(path) as im:
            w, h = im.size
        created = call('POST', '/assets', {
            'filename': fn, 'path': str(path), 'type': 'image', 'width': w, 'height': h,
            'tags': tags.get(fn, []), 'source': f'ngay_tan_ep{ep}{sfx(kind)}',
        })
        ids[fn] = created['id']
    print(f'Ảnh: {len(ids)} (đã có/đăng ký)')
    return ids


def vi_sections(ep, kind='long'):
    """Đọc scripts/epN_audiobook_v*.txt (bản Việt, bản mới nhất) -> (đoạn phần truyện, giới thiệu, kết).
    Bản Việt có đúng cùng số đoạn với bản Hàn (P01..PNN theo thứ tự) nên dùng chung shot list."""
    if kind == 'short':
        path = D / 'scripts' / f'ep{ep}_short_vi.txt'
    else:
        path = sorted((D / 'scripts').glob(f'ep{ep}_audiobook_v*.txt'))[-1]
    text = path.read_text(encoding='utf-8')
    body = text[text.index('## TRUYỆN') + len('## TRUYỆN'):text.index('## KẾT')]
    intro = text[text.index('## GIỚI THIỆU') + len('## GIỚI THIỆU'):text.index('## TRUYỆN')]
    outro = text[text.index('## KẾT') + len('## KẾT'):]
    clean = lambda t: ' '.join(ln.strip() for ln in t.splitlines() if ln.strip() and not ln.strip().startswith('##'))
    paras = [p.strip() for p in re.split(r'\n\s*\n', body) if p.strip() and not p.strip().startswith('##')]
    return paras, clean(intro), clean(outro)


def allocate(ep, shots, lang='ko', kind='long'):
    """Chia lời đọc phần truyện cho từng shot. Trả về list narration (cùng thứ tự shots)."""
    paras = OrderedDict()
    if lang == 'ko':
        for k, t in read_pairs(f'ko_ep{ep}{sfx(kind)}_check.txt'):
            head = k.rsplit('-', 1)[0]
            if head in ('INTRO', 'OUTRO'):
                continue
            paras.setdefault(head, []).append(t)
    else:
        vi_paras, _, _ = vi_sections(ep, kind)
        for i, ptxt in enumerate(vi_paras, 1):
            paras[f'P{i:02d}'] = [ptxt]
    words, pstart = [], {}
    for pid, sents in paras.items():
        pstart[pid] = len(words)
        words += ' '.join(sents).split()
    plen = {pid: len(' '.join(s).split()) for pid, s in paras.items()}

    anchors = OrderedDict()
    for i, (_, pids) in enumerate(shots):
        anchors.setdefault(pids[0], []).append(i)
    starts = [0] * len(shots)
    for pid, idxs in anchors.items():
        m = len(idxs)
        for j, i in enumerate(idxs):
            starts[i] = pstart[pid] + round(plen[pid] * j / m)
    starts[0] = 0

    def natural(idx):  # ranh giới tự nhiên: từ trước đó kết thúc câu/mệnh đề
        return idx > 0 and re.search(r'[.!?,"”…]$', words[idx - 1]) is not None

    for i in range(1, len(starts)):
        s = starts[i]
        best = s
        for off in range(0, 7):
            for cand in (s - off, s + off):
                if 0 < cand < len(words) and natural(cand):
                    best = cand
                    break
            else:
                continue
            break
        starts[i] = best
    for i in range(1, len(starts)):
        starts[i] = max(starts[i], starts[i - 1] + 2)
    for i in range(len(starts) - 1, 0, -1):
        starts[i] = min(starts[i], len(words) - 2 * (len(starts) - i))
    ends = starts[1:] + [len(words)]
    out = [' '.join(words[a:b]) for a, b in zip(starts, ends)]
    assert all(out), 'có shot không có lời đọc'
    return out, ' '.join(' '.join(s) for s in paras.values())


def main(ep, lang='ko', force=False, kind='long'):
    cfg = LANGS[lang]
    short = kind == 'short'
    shots = parse_shotlist(ep, kind)
    tags = csv_tags(ep, kind)
    ids = register_assets(ep, shots, tags, kind)
    if short:  # shot INTRO/OUTRO mang chính lời giới thiệu/kết; phần truyện chia cho các shot còn lại
        intro_shot = next(s for s in shots if s[1][0] == 'INTRO')
        outro_shot = next(s for s in shots if s[1][0] == 'OUTRO')
        body_shots = [s for s in shots if s[1][0] not in ('INTRO', 'OUTRO')]
    else:
        body_shots = shots
    narr, script_body = allocate(ep, body_shots, lang, kind)

    if lang == 'ko' and short:
        book = {'INTRO': [], 'OUTRO': []}
        for k, t in read_pairs(f'ko_ep{ep}_short_check.txt'):
            if k.rsplit('-', 1)[0] in book:
                book[k.rsplit('-', 1)[0]].append(t)
        intro, outro = ' '.join(book['INTRO']), ' '.join(book['OUTRO'])
    elif lang == 'ko':
        book = {'INTRO': [], 'OUTRO': []}
        for k, t in read_pairs('ko_bookends_check.txt'):
            if k.startswith(f'E{ep}_'):
                book['INTRO' if 'INTRO' in k else 'OUTRO'].append(t)
        intro, outro = ' '.join(book['INTRO']), ' '.join(book['OUTRO'])
    else:
        _, intro, outro = vi_sections(ep, kind)
    assert intro and outro, 'thiếu giới thiệu/kết'

    beats = []

    def add(text, asset_id, btype, hint, voice=None):
        n = len(beats) + 1
        beats.append({
            'id': f'b{n:03d}', 'order': n, 'type': btype, 'narration': text,
            'duration': round(min(120.0, max(1.5, len(text.split()) / cfg['wps'])), 2),
            'visual_hint': hint, 'asset_id': asset_id, 'voice_id': voice,
        })

    add(intro, ids[(intro_shot if short else shots[1])[0]], 'HOOK', 'intro', cfg['bookend_voice'])
    for (fn, _), text in zip(body_shots, narr):
        add(text, ids[fn], 'BODY', re.sub(r'^S?\d+_|\.png$', '', fn).replace('_', ' '))
    add(outro, ids[(outro_shot if short else shots[-1])[0]], 'ENDING', 'outro', cfg['bookend_voice'])

    name = f'Ngày Tàn T{ep} ({cfg["label"]}) ' + ('SHORT ' if short else '') + '[test render]'
    proj = call('POST', '/projects', {
        'name': name, 'script_text': script_body, 'template_id': cfg['template'], 'visual_generation_mode': 'library',
        'content_language': lang, 'ai_metadata_enabled': False,
    })
    pid = proj['id']
    print('Project', pid, name, '| beats:', len(beats))
    draft = call('GET', f'/projects/{pid}')
    if short:  # video dọc 9:16, không thêm thẻ outro (lời kết đã nằm trong beat cuối)
        draft['config']['render']['profile'] = 'SOCIAL_VERTICAL'
        draft['config']['voice']['speed'] = cfg['short_speed']  # short đọc nhanh hơn video dài (KO 1.2, VI 1.4); chỉ đặt trong project, không đổi template
        draft['config']['outro']['enabled'] = False
    plan = {
        'video_id': draft.get('video_id'), 'script_text': script_body, 'beats': beats, 'project_name': name,
        'config': draft['config'], 'idea': draft.get('idea'), 'content_brief': draft.get('content_brief'),
        'script_locked': True,
    }
    call('PUT', f'/projects/{pid}/beat-plan', plan)
    run = call('POST', f'/projects/{pid}/factory-run')
    print('Factory run', run['id'], run['status'])
    last = None
    forced = False
    while True:
        time.sleep(15)
        r = call('GET', f'/factory-runs/{run["id"]}')
        if r['status'] != last:
            print(time.strftime('%H:%M:%S'), r['status'], flush=True)
            last = r['status']
        if r['status'] == 'NEEDS_REVIEW' and force and not forced and not r.get('failed_stage'):
            # Quality Gate chỉ có cảnh báo (pacing/độ phân giải ảnh): chấp nhận để render tiếp.
            forced = True
            call('POST', f'/factory-runs/{run["id"]}/continue?force=true')
            print('Chấp nhận cảnh báo Quality Gate (force) -> render', flush=True)
            last = None
            continue
        if r['status'] in ('COMPLETED', 'FAILED', 'NEEDS_REVIEW', 'READY_TO_RENDER', 'CANCELLED') or r.get('completed_at'):
            print(json.dumps({k: r.get(k) for k in (
                'status', 'failed_stage', 'error_code', 'error_message', 'render_job_id', 'quality_status', 'quality_score',
                'qa_status', 'qa_score')}, ensure_ascii=False))
            break

if __name__ == '__main__':
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 1, sys.argv[2] if len(sys.argv) > 2 else 'ko', 'force' in sys.argv[3:],
         'short' if 'short' in sys.argv[3:] else 'long')
