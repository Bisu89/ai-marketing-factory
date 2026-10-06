"""Video SHORT (9:16) của Tập 1: ghép lời đọc Hàn (scripts/ko_ep1_short_check.txt -> scripts/ep1_short_ko.md)
và dựng ngay_tan_ep1_short_scenes.csv + shot list.  Chạy từ thư mục _tools/.
Tập khác: copy file này, đổi tên file kiểm tra, danh sách SHOTS và tên tập."""
import csv
import re
import sys
from collections import OrderedDict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import ngay_tan_blocks as B  # noqa: E402

D = HERE.parent
STYLE, NEG, BG = B.STYLE, B.NEG, B.BG
RATIO_V = 'Tỷ lệ khung hình 9:16 dọc (video Shorts), chủ thể đặt giữa khung, chừa khoảng trống phía trên và phía dưới cho phụ đề.'
NEG_SFX = NEG.replace('chữ, logo, watermark', 'phụ đề, bóng thoại, mọi chữ khác ngoài chữ hiệu ứng đã chỉ định, logo, watermark')
HDR = ['STT', 'Ten file (filename.png)', 'Tags (dan khi import)', 'Prompt day du (copy nguyen vao ChatGPT)']

UNI = 'mặc quân phục dã chiến thượng sĩ và đội mũ nồi đen'
WET = 'áo khoác ướt mưa'
ROSTER = {
    'Taeho': 'KANG TAEHO (강태호)', 'Minseo': 'LEE MINSEO (이민서)', 'Choi': 'CHOI GANGSIK (최강식)',
    'Dahee': 'BAEK DAHEE (백다희)',
}
ZOMBIES = {
    'Kẻ Săn Mồi': 'KẺ SĂN MỒI (số 5 trong bảng: người đàn ông mặc đồ xám nhạt, đeo vòng tay nhựa)',
    'Dân Thường': 'KẺ LANG THANG biến thể số 11 DÂN THƯỜNG (người đàn ông mặc áo hoodie xám và quần jeans)',
    'Kẻ Lang Thang': 'KẺ LANG THANG (số 1 trong bảng)',
    'Nhân Viên Văn Phòng': 'KẺ LANG THANG biến thể số 14 NHÂN VIÊN VĂN PHÒNG (áo sơ mi, cà vạt đỏ)',
    'Công Nhân': 'KẺ LANG THANG biến thể số 15 CÔNG NHÂN (mũ bảo hộ, áo phản quang)',
    'Bác Sĩ': 'KẺ LANG THANG biến thể số 12 BÁC SĨ (áo blouse rách)',
}
HORDE = ['Kẻ Lang Thang', 'Dân Thường', 'Nhân Viên Văn Phòng', 'Công Nhân', 'Bác Sĩ']


def sfx_text(items):
    return ('Chữ hiệu ứng tiếng động kiểu truyện tranh Hàn Quốc, viết bằng Hangul, nét dày cách điệu, đặt đúng chỗ phát ra âm thanh: '
            + ', '.join(f'"{t}"' for t in items) + '. Chỉ có đúng các chữ hiệu ứng này, không có chữ nào khác.')


def make_prompt(shot, names, text, sfx):
    parts = []
    if names:
        humans = [n for n in names if n in ROSTER]
        monsters = [n for n in names if n not in ROSTER]
        head = ''
        if humans:
            mapping = '; '.join(f'{n} = {ROSTER[n]}' for n in humans)
            head += ('Dùng lại bảng nhân vật tổng hợp đã tạo ở đầu cuộc trò chuyện này (không cần đính kèm lại ảnh). '
                     f'Nhân vật được gọi theo tên ghi trong bảng: {mapping}. Giữ đúng khuôn mặt, kiểu tóc, trang phục và dáng người '
                     'của nhân vật có đúng tên đó trong bảng (trừ chỗ được nêu thay đổi bên dưới).')
        if monsters:
            zmap = '; '.join(f'{n} = {ZOMBIES[n]}' for n in monsters)
            head += (f' Quái vật được gọi theo tên và số ghi trong bảng quái vật tổng hợp đã tạo trước đó trong cuộc trò chuyện này: {zmap}. '
                     'Giữ đúng hình dáng của quái vật có đúng tên và số đó trong bảng.')
        parts.append(head.strip())
    parts.append(f'[{shot}] {text}')
    parts.append('Tất cả nhân vật trong ảnh đều là người trưởng thành.')
    if sfx:
        parts.append(sfx_text(sfx))
    parts += [STYLE, RATIO_V, NEG_SFX if sfx else NEG]
    return ' '.join(parts)


# (slug, đoạn kịch bản, shot, names, text, sfx, tag VI, tag KO)
SHOTS = [
    ('mo_dau_taeho_quan_phuc_nghiem_nghi', ['INTRO'], 'Cận mặt dọc', ['Taeho'],
     f'Taeho {UNI}, gương mặt nghiêm nghị nhìn thẳng ống kính, phía sau là ô kính phòng thí nghiệm nhuộm ánh đỏ cảnh báo, không khí căng thẳng mở đầu.', None,
     'taeho, quân phục, mở đầu, ánh đỏ', '강태호, 군복, 오프닝, 붉은 빛'),
    ('linh_co_giat_sau_kinh_doc', ['P01'], 'Cảnh dọc', ['Kẻ Săn Mồi'],
     f'Nhìn từ ngoài kính: KẺ SĂN MỒI (số 5 trong bảng) khi còn là người, người đàn ông mặc đồ xám nhạt đeo vòng tay nhựa, co giật dữ dội trên giường bệnh, mắt bắt đầu phủ trắng đục; một bác sĩ giữ vai; không máu me. {BG["lab"]}',
     ['쾅!'], 'co giật, thử nghiệm, sau kính, lính', '경련, 시험, 유리 너머, 병사'),
    ('minseo_nhet_the_nho_vao_tay_doc', ['P02'], 'Cận cảnh dọc hai bàn tay', ['Taeho', 'Minseo'],
     f'Cận cảnh hai bàn tay: bàn tay Minseo nhét một chiếc thẻ nhớ nhỏ vào lòng bàn tay Taeho (đang {UNI}) rồi khép các ngón tay anh lại, nền hành lang phòng thí nghiệm mờ.', None,
     'thẻ nhớ, bàn tay, minseo, taeho', '메모리카드, 손, 이민서, 강태호'),
    ('choi_can_mat_lanh_lung_doc', ['P03'], 'Cận mặt dọc', ['Choi'],
     f'Cận mặt Choi ngồi sau bàn làm việc, ánh mắt tính toán lạnh lẽo nhìn xuống, nửa mặt chìm trong bóng. {BG["vp"]}', None,
     'choi, đại tá, lạnh lùng, văn phòng', '최강식, 대령, 냉정, 사무실'),
    ('taeho_bi_tuoc_quan_ham_doc', ['P03'], 'Trung cảnh dọc', ['Taeho', 'Choi'],
     f'Taeho {UNI}, đứng thẳng bất động khi quân hàm thượng sĩ bị gỡ khỏi vai; Choi đứng phía sau bàn nhìn anh. {BG["vp"]}', None,
     'tước quân hàm, taeho, choi, loại ngũ', '계급 박탈, 강태호, 최강식, 전역'),
    ('taeho_lai_xe_hop_nhan_doc', ['P04'], 'Cảnh dọc', ['Taeho'],
     'Taeho một mình lái xe lúc hoàng hôn, ánh cam tím hắt lên kính xe, trên ghế phụ là một hộp nhẫn nhỏ mở nắp, vẻ mặt trống rỗng.', None,
     'lái xe, hoàng hôn, hộp nhẫn, taeho', '운전, 황혼, 반지 상자, 강태호'),
    ('taeho_dung_ngoai_cua_nghe_len_doc', ['P05'], 'Trung cảnh dọc', ['Taeho'],
     f'Taeho ({WET}) đứng chết lặng ngoài cánh cửa nhà Dahee, bàn tay còn chạm tay nắm, ánh đèn cổng ấm, mưa phùn. {BG["nha"]}', None,
     'nghe lén, cửa, mưa, taeho', '엿듣다, 문, 비, 강태호'),
    ('dahee_va_choi_trong_nha_doc', ['P05'], 'Cảnh cắt vào trong nhà', ['Dahee', 'Choi'],
     'Cảnh cắt vào bên trong nhà (Taeho không nhìn thấy): Dahee đứng cúi đầu nói rất nhỏ, hai tay nắm chặt, Choi ngồi trên ghế sofa nghe, ánh đèn phòng khách ấm nhưng không khí lạnh.', None,
     'dahee, choi, phòng khách, báo cáo', '백다희, 최강식, 거실, 보고'),
    ('taeho_tha_nhan_xuong_ranh_doc', ['P06'], 'Cận cảnh dọc', ['Taeho'],
     'Cận cảnh bàn tay Taeho thả chiếc nhẫn cầu hôn xuống rãnh nước bên vỉa hè, nước mưa lấp lánh phản chiếu đèn đường, mặt anh mờ phía sau quay đi.', ['퐁당'],
     'thả nhẫn, rãnh nước, taeho', '반지, 배수구, 강태호'),
    ('ke_san_moi_dap_vo_kinh_doc', ['P07'], 'Cảnh dọc hành động', ['Kẻ Săn Mồi'],
     f'KẺ SĂN MỒI (số 5 trong bảng, vừa biến đổi) lao vào ô kính khiến kính rạn nứt, một bác sĩ ngã xuống phía sau; đèn báo động đỏ nhấp nháy. {BG["lab_do"]} Cảnh tiết chế, không chi tiết máu me.',
     ['쾅!', '쨍그랑!'], 'đập kính, báo động, bác sĩ ngã, zombie', '유리를 깨다, 경보, 의사, 좀비'),
    ('xe_cuu_thuong_roi_cong_doc', ['P08'], 'Cảnh dọc', None,
     'Cổng chính khu quân sự Cheonma ban đêm: một xe cứu thương bật đèn đỏ chạy ra khỏi cổng, một chiếc xe buýt đổi ca theo sau, trạm gác chưa kịp đóng cổng, hàng rào thép gai, đèn pha quét.',
     ['삐뽀삐뽀'], 'xe cứu thương, xe buýt, cổng, lây lan', '구급차, 버스, 정문, 확산'),
    ('nguoi_nhiem_dap_kinh_xe_doc', ['P09'], 'Cảnh dọc nhìn từ trong xe', ['Taeho', 'Dân Thường'],
     f'Nhìn từ trong xe: Kẻ Lang Thang biến thể Dân Thường đập hai tay lên kính chắn gió, chất lỏng đen sẫm loãng chảy từ cổ xuống áo; ở góc dưới Taeho siết cán dao găm, kính xe rạn nứt. {BG["vanh_dai"]}',
     ['쾅! 쾅!'], 'người nhiễm, đập kính xe, taeho, dao', '감염자, 앞유리, 강태호, 칼'),
    ('dan_quai_bao_vay_doc', ['P10'], 'Toàn cảnh dọc', HORDE,
     f'Toàn cảnh dọc: chiếc xe nhỏ của Taeho dừng giữa đường vành đai tối, hàng chục Kẻ Lang Thang tiến lại từ mọi hướng (trộn các biến thể Dân Thường, Nhân Viên Văn Phòng, Công Nhân, Bác Sĩ), phía xa là ánh sáng thành phố mờ trong khói. {BG["vanh_dai"]}',
     ['터벅터벅'], 'đàn zombie, bao vây, kết', '좀비 떼, 포위, 엔딩'),
    ('ket_taeho_nhin_len_nen_toi', ['OUTRO'], 'Cận mặt dọc', ['Taeho'],
     'Cận mặt Taeho ngước nhìn lên, ánh đèn pha hắt viền sáng quanh khuôn mặt, nền tối gần như đen, ánh mắt vừa sợ vừa quyết, khoảng trống phía dưới để chèn lời kêu gọi xem tiếp.', None,
     'kết, taeho, ánh mắt, cliffhanger', '엔딩, 강태호, 눈빛, 클리프행어'),
]

# --- lời đọc Hàn -> markdown ---
body = OrderedDict()
book = {'INTRO': [], 'OUTRO': []}
ko_first = {}
for line in open(D / 'scripts' / 'ko_ep1_short_check.txt', encoding='utf-8'):
    line = line.rstrip('\n')
    if not line.strip():
        continue
    key, text = line.split('|', 1)
    head = key.rsplit('-', 1)[0]
    if head in book:
        book[head].append(text)
        ko_first.setdefault(head, text)
    else:
        body.setdefault(head, []).append(text)
        ko_first.setdefault(head, text)

md = ['## 종말의 날 | 제1화 숏츠 (9:16, 약 66초 실측) — 본문 여성 내레이션 / 소개·결말 남성 목소리', '## GIỚI THIỆU',
      ' '.join(book['INTRO']), '', '## TRUYỆN']
for sents in body.values():
    md += [' '.join(sents), '']
md += ['## KẾT', ' '.join(book['OUTRO'])]
text_md = '\n'.join(md) + '\n'
(D / 'scripts' / 'ep1_short_ko.md').write_text(text_md, encoding='utf-8', newline='\n')

# --- CSV + shot list ---
rows = []
for i, (slug, pids, shot, names, text, sfx, tvi, tko) in enumerate(SHOTS, 1):
    tags = f'ngay_tan, tap1, short, 9x16, vi, ko, rieng_short_tap1, {tvi}, {tko}'
    rows.append((f'S{i:02d}_{slug}.png', tags, make_prompt(shot, names, text, sfx)))
with open(D / 'ngay_tan_ep1_short_scenes.csv', 'w', encoding='utf-8-sig', newline='') as f:
    w = csv.writer(f, lineterminator='\r\n')
    w.writerow(HDR)
    for i, (fn, tags, prompt) in enumerate(rows, 1):
        w.writerow([i, fn, tags, prompt])

sl = ['# Ngày Tàn — Tập 1: video SHORT (9:16) — danh sách ảnh', '',
      f'{len(SHOTS)} ảnh dọc cho khoảng 66 giây giọng Hàn đo thật (≈ {66 // len(SHOTS)}–5 giây/ảnh). Lời đọc: `scripts/ep1_short_vi.txt` (VI), `scripts/ep1_short_ko.md` (KO).', '',
      '| STT | File | Đoạn | Câu KO | Chữ hiệu ứng |', '|---|---|---|---|---|']
for i, (slug, pids, shot, names, text, sfx, tvi, tko) in enumerate(SHOTS, 1):
    sl.append(f'| {i} | S{i:02d}_{slug}.png | {", ".join(pids)} | {ko_first.get(pids[0], "")} | {"có" if sfx else ""} |')
(D / 'ngay_tan_ep1_short_shotlist.md').write_text('\n'.join(sl) + '\n', encoding='utf-8', newline='\n')

bad = set()
for fn, tags, prompt in rows:
    for ch in tags + prompt + text_md:
        o = ord(ch)
        if 0xAC00 <= o <= 0xD7A3 or o < 0x250 or 0x1E00 <= o <= 0x1EFF or ch in '“”‘’—…·–~':
            continue
        bad.add((ch, hex(o)))
print(len(rows), 'ảnh short; ký tự lạ:', bad, '; từ Hàn:', len(re.findall(r'[가-힣]+', text_md)))
