"""Dựng thử một tập (video dài) trong app qua API: đăng ký ảnh -> tạo project -> beat plan (mỗi shot = 1 beat, đã gán ảnh) -> Factory run.

Dùng:  python render_episode.py 1            (Tập 1, bản Hàn, template ngay_tan_ko)
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
BOOKEND_VOICE = 'ko-KR-InJoonNeural'
TEMPLATE = 'ngay_tan_ko'
WPS_KO = 1.8  # từ/giây thực đo được, chỉ để ước lượng Beat.duration (Voice stage ghi đè bằng thời lượng thật)


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


def parse_shotlist(ep):
    shots = []
    for line in open(D / f'ngay_tan_ep{ep}_shotlist.md', encoding='utf-8'):
        m = re.match(r'\|\s*(\d+)\s*\|\s*(\S+\.png)\s*\|\s*([^|]*?)\s*\|', line)
        if m:
            shots.append((m.group(2), [p.strip() for p in m.group(3).split(',')]))
    return shots


def csv_tags(ep):
    rows = list(csv.reader(open(D / f'ngay_tan_ep{ep}_scenes_v3.csv', encoding='utf-8-sig')))[1:]
    return {r[1]: [t.strip() for t in r[2].split(',') if t.strip()] for r in rows}


def register_assets(ep, shots, tags):
    img_dir = D / f'ngay_tan_ep{ep}_images'
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
            'tags': tags.get(fn, []), 'source': f'ngay_tan_ep{ep}',
        })
        ids[fn] = created['id']
    print(f'Ảnh: {len(ids)} (đã có/đăng ký)')
    return ids


def allocate(ep, shots):
    """Chia lời đọc phần truyện cho từng shot. Trả về list narration (cùng thứ tự shots)."""
    paras = OrderedDict()
    for k, t in read_pairs(f'ko_ep{ep}_check.txt'):
        paras.setdefault(k.rsplit('-', 1)[0], []).append(t)
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
        return idx > 0 and re.search(r'[.!?,"”]$', words[idx - 1]) is not None

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


def main(ep):
    shots = parse_shotlist(ep)
    tags = csv_tags(ep)
    ids = register_assets(ep, shots, tags)
    narr, script_body = allocate(ep, shots)

    book = {'INTRO': [], 'OUTRO': []}
    for k, t in read_pairs('ko_bookends_check.txt'):
        if k.startswith(f'E{ep}_'):
            book['INTRO' if 'INTRO' in k else 'OUTRO'].append(t)
    intro, outro = ' '.join(book['INTRO']), ' '.join(book['OUTRO'])
    assert intro and outro, 'thiếu giới thiệu/kết KO trong ko_bookends_check.txt'

    beats = []

    def add(text, asset_id, btype, hint, voice=None):
        n = len(beats) + 1
        beats.append({
            'id': f'b{n:03d}', 'order': n, 'type': btype, 'narration': text,
            'duration': round(min(120.0, max(1.5, len(text.split()) / WPS_KO)), 2),
            'visual_hint': hint, 'asset_id': asset_id, 'voice_id': voice,
        })

    add(intro, ids[shots[1][0]], 'HOOK', 'intro', BOOKEND_VOICE)
    for (fn, _), text in zip(shots, narr):
        add(text, ids[fn], 'BODY', re.sub(r'^\d+_|\.png$', '', fn).replace('_', ' '))
    add(outro, ids[shots[-1][0]], 'ENDING', 'outro', BOOKEND_VOICE)

    name = f'Ngày Tàn T{ep} (KO) [test render]'
    proj = call('POST', '/projects', {
        'name': name, 'script_text': script_body, 'template_id': TEMPLATE, 'visual_generation_mode': 'library',
        'content_language': 'ko', 'ai_metadata_enabled': False,
    })
    pid = proj['id']
    print('Project', pid, name, '| beats:', len(beats))
    draft = call('GET', f'/projects/{pid}')
    plan = {
        'video_id': draft.get('video_id'), 'script_text': script_body, 'beats': beats, 'project_name': name,
        'config': draft['config'], 'idea': draft.get('idea'), 'content_brief': draft.get('content_brief'),
        'script_locked': True,
    }
    call('PUT', f'/projects/{pid}/beat-plan', plan)
    run = call('POST', f'/projects/{pid}/factory-run')
    print('Factory run', run['id'], run['status'])
    last = None
    while True:
        time.sleep(15)
        r = call('GET', f'/factory-runs/{run["id"]}')
        if r['status'] != last:
            print(time.strftime('%H:%M:%S'), r['status'], flush=True)
            last = r['status']
        if r['status'] in ('COMPLETED', 'FAILED', 'NEEDS_REVIEW', 'READY_TO_RENDER', 'CANCELLED') or r.get('completed_at'):
            print(json.dumps({k: r.get(k) for k in (
                'status', 'failed_stage', 'error_code', 'error_message', 'render_job_id', 'quality_status', 'quality_score',
                'qa_status', 'qa_score')}, ensure_ascii=False))
            break


if __name__ == '__main__':
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 1)
