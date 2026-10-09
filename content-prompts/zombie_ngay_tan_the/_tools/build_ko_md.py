"""Ghép scripts/ko_epN_check.txt (câu Hàn đánh số) + bookends thành scripts/epN_ko.md. Chạy: python build_ko_md.py [N] (mặc định Tập 1). Tiêu đề KO từng tập khai báo trong KO_TITLES."""
import os, re, sys
from collections import OrderedDict

from pathlib import Path
base = str(Path(__file__).resolve().parent.parent / 'scripts')
EP = int(sys.argv[1]) if len(sys.argv) > 1 else 1
KO_TITLES = {1: '쫓겨난 군인', 2: '죽음의 도시의 밤', 3: '화살과 약속'}


def read_pairs(name):
    pairs = []
    for line in open(os.path.join(base, name), encoding='utf-8'):
        line = line.rstrip('\n')
        if not line.strip():
            continue
        key, text = line.split('|', 1)
        pairs.append((key, text))
    return pairs


body = OrderedDict()
for key, text in read_pairs(f'ko_ep{EP}_check.txt'):
    para = key.rsplit('-', 1)[0]
    body.setdefault(para, []).append(text)

book = OrderedDict()
for key, text in read_pairs('ko_bookends_check.txt'):
    if key.startswith(f'E{EP}_'):
        part = 'INTRO' if 'INTRO' in key else 'OUTRO'
        book.setdefault(part, []).append(text)

out = []
out.append(f'## 종말의 날 | 제{EP}화 — {KO_TITLES[EP]} (한국어판, 본문은 여성 내레이션 / 소개·결말은 남성 목소리)')
out.append('## GIỚI THIỆU')
out.append(' '.join(book['INTRO']))
out.append('')
out.append('## TRUYỆN')
for para, sents in body.items():
    out.append(' '.join(sents))
    out.append('')
out.append('## KẾT')
out.append(' '.join(book['OUTRO']))
text = '\n'.join(out) + '\n'
open(os.path.join(base, f'ep{EP}_ko.md'), 'w', encoding='utf-8', newline='\n').write(text)

# corruption scan: only Hangul, ASCII, and common punctuation/space allowed (plus the Vietnamese header lines)
bad = set()
for ch in text:
    o = ord(ch)
    if ch in '\n ' or o < 128 or 0xAC00 <= o <= 0xD7A3 or ch in '“”‘’—…·':
        continue
    bad.add(ch)
print('paras', len(body), 'chars', len(text), 'non-Hangul/ASCII chars:', ''.join(sorted(bad)))
print(len(re.findall(r'[가-힣]+', text)), 'korean words')
