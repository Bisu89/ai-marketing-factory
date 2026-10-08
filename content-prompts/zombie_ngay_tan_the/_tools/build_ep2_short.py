"""Video SHORT (9:16) của Tập 2: ghép lời đọc Hàn (scripts/ko_ep2_short_check.txt -> scripts/ep2_short_ko.md)
và dựng ngay_tan_ep2_short_scenes.csv + shot list.  Chạy từ thư mục _tools/.
Bản Tập 1: build_ep1_short.py."""
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

JW = 'áo sơ mi công sở màu sáng hơi rách, tóc rối, một vệt máu khô trên má và trên tay áo'
YR = 'có thêm một vệt máu trên tay áo, đeo balô'
ROSTER = {
    'Taeho': 'KANG TAEHO (강태호)', 'Jiwoo': 'SEO JIWOO (서지우)', 'Yerin': 'HAN YERIN (한예린)',
    'Areum': 'SEO AREUM (서아름)',
}
ZOMBIES = {
    'Thể Cuồng': 'THỂ CUỒNG (số 2 trong bảng)',
    'Dân Thường': 'KẺ LANG THANG biến thể số 11 DÂN THƯỜNG (người đàn ông mặc áo hoodie xám và quần jeans)',
}
BG2 = {
    'cong_truong': 'Cổng trường trung học ban đêm, cánh cổng sắt mở một nửa, sân trường tối, tòa nhà chính phía sau.',
    'hanh_lang': 'Hành lang tầng hai của trường học ban đêm, tối đen, đèn hành lang tắt, cánh cửa các lớp đóng.',
    'van_thu': 'Phòng văn thư nhỏ trong trường, bàn kéo chắn ngang cửa, vài chai nước, một túi xách.',
    'pho_dem': 'Đường phố thành phố ban đêm, một chiếc xe buýt nằm ngang giữa đường, cửa hàng tiện lợi bốc khói, đèn giao thông vẫn chuyển màu.',
    'cap_cuu': 'Khu cấp cứu bệnh viện hỗn loạn: người nằm trên cáng, người ngồi dưới sàn, nhân viên y tế chạy qua lại, đèn huỳnh quang trắng lạnh.',
    'ham_xe': 'Hầm gửi xe ngầm với vài bóng đèn khẩn cấp nhấp nháy, hàng chục xe bỏ lại, trụ bê tông nối tiếp nhau, ống nước nhỏ giọt.',
    'cung': 'Trung tâm huấn luyện bắn cung quốc gia ban đêm: tòa nhà vòm lớn, tường kính cao, bãi xe rộng, đèn đường vàng, ánh trăng.',
}


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
    ('mo_dau_taeho_dem_mat_song', ['INTRO'], 'Cận mặt dọc', ['Taeho'],
     'Taeho cầm điện thoại không có tín hiệu, gương mặt cảnh giác nhìn thẳng ống kính, phía sau là thành phố ban đêm mờ trong khói, vài ánh đèn cứu thương đỏ xa xa.', None,
     'taeho, mất sóng, mở đầu, đêm', '강태호, 통신 두절, 오프닝, 밤'),
    ('taeho_roi_xe_vanh_dai_doc', ['P01'], 'Cảnh dọc', ['Taeho'],
     f'Taeho đeo balô, tay cầm dao quân dụng, rời chiếc xe nứt kính bỏ lại giữa đường, vài bóng người tiến tới phía sau. {B.BG["vanh_dai"]}', None,
     'bỏ xe, đường vành đai, taeho', '차를 버리다, 순환도로, 강태호'),
    ('cong_truong_nghe_tieng_goi_doc', ['P02'], 'Cảnh dọc', ['Taeho'],
     f'Taeho đứng trước cánh cổng trường mở một nửa, quay đầu về phía tòa nhà chính tối om khi nghe thấy tiếng gọi yếu ớt từ tầng hai. {BG2["cong_truong"]}', None,
     'cổng trường, tiếng gọi, taeho', '교문, 부르는 소리, 강태호'),
    ('the_cuong_lao_toi_hanh_lang_doc', ['P03'], 'Cảnh dọc hành động', ['Thể Cuồng'],
     f'THỂ CUỒNG, một người trưởng thành mặc bộ đồng phục nhân viên bảo vệ của trường, quay phắt lại và lao thẳng về phía người xem dọc hành lang tối, mắt trắng đục, miệng há ra. {BG2["hanh_lang"]}',
     ['쾅!'], 'thể cuồng, hành lang, lao tới', '광폭 감염자, 복도, 돌진'),
    ('jiwoo_cam_keo_sau_cua_he_doc', ['P04'], 'Trung cảnh dọc', ['Jiwoo'],
     f'Jiwoo đứng sau cánh cửa hé, hai tay nắm chặt một cây kéo với mũi kéo chĩa ra ngoài, ánh mắt sợ hãi nhưng quyết liệt; {JW}. {BG2["van_thu"]}', None,
     'jiwoo, cây kéo, phòng văn thư', '서지우, 가위, 서무실'),
    ('jiwoo_nhin_man_hinh_dien_thoai_doc', ['P05'], 'Cận cảnh dọc', ['Jiwoo'],
     f'Cận cảnh Jiwoo nhìn màn hình điện thoại không có tín hiệu, ánh mắt nghẹn lại khi nghĩ về em gái; {JW}.', None,
     'jiwoo, điện thoại, em gái', '서지우, 휴대전화, 동생'),
    ('taeho_va_jiwoo_di_pho_dem_doc', ['P05'], 'Toàn cảnh dọc', ['Taeho', 'Jiwoo'],
     f'Taeho đi trước, Jiwoo đi sát phía sau ({JW}), cả hai đi dọc con phố tối; Taeho cầm dao, Jiwoo ngoái nhìn về phía có tiếng động. {BG2["pho_dem"]}', None,
     'taeho, jiwoo, phố đêm, đi cùng', '강태호, 서지우, 밤거리, 동행'),
    ('benh_vien_cap_cuu_hon_loan_doc', ['P06'], 'Cảnh dọc', None,
     f'Khu cấp cứu bệnh viện hỗn loạn nhìn từ cửa vào, cáng nằm la liệt, nhân viên y tế chạy qua chạy lại, một cánh cửa kính tự động đóng mở liên tục. {BG2["cap_cuu"]}',
     ['웅성웅성'], 'bệnh viện, cấp cứu, hỗn loạn', '병원, 응급실, 아수라장'),
    ('yerin_chan_benh_nhan_bang_khay_doc', ['P07'], 'Trung cảnh dọc', ['Yerin', 'Dân Thường'],
     f'Yerin ({YR}) giơ chiếc khay kim loại chắn giữa mình và KẺ LANG THANG biến thể Dân Thường vừa bật dậy khỏi cáng, ông ta đập mạnh vào khay; một y tá lùi ra phía sau. {BG2["cap_cuu"]}',
     ['쾅!'], 'yerin, khay kim loại, bệnh nhân', '한예린, 금속 쟁반, 환자'),
    ('taeho_quat_nga_benh_nhan_doc', ['P07'], 'Cảnh dọc hành động', ['Taeho', 'Yerin', 'Dân Thường'],
     f'Taeho lao tới đánh vào vai KẺ LANG THANG biến thể Dân Thường khiến hắn mất thăng bằng rồi đẩy ngã xuống nền; Yerin ({YR}) đứng cạnh sẵn sàng kéo cánh cửa đóng lại. {BG2["cap_cuu"]}',
     ['퍽!'], 'taeho, yerin, đẩy ngã, cấp cứu', '강태호, 한예린, 쓰러뜨리다, 응급실'),
    ('ba_nguoi_qua_ham_xe_doc', ['P08'], 'Cảnh dọc', ['Taeho', 'Yerin', 'Jiwoo'],
     f'Taeho đi đầu, Yerin ở giữa ({YR}), Jiwoo đi sau cùng ({JW}), ba người lặng lẽ đi giữa những chiếc xe bỏ lại. {BG2["ham_xe"]}', None,
     'hầm xe, ba người, taeho, yerin, jiwoo', '지하 주차장, 세 사람, 강태호, 한예린, 서지우'),
    ('den_trung_tam_ban_cung_cuoi_duong_doc', ['P09'], 'Cảnh dọc', None,
     f'Cuối con phố vắng, ánh đèn từ tòa nhà vòm của trung tâm bắn cung hiện ra trong đêm gần nửa đêm, đèn đường vàng, ánh trăng. {BG2["cung"]}', None,
     'trung tâm bắn cung, cuối đường, nửa đêm', '양궁 훈련센터, 길 끝, 자정'),
    ('areum_nang_cung_tren_mai_doc', ['P10'], 'Cảnh dọc góc thấp', ['Areum'],
     f'Nhìn từ dưới lên: Areum, tóc bện dài buông qua vai, đứng trên mái nhà vòm và từ từ nâng cây cung thể thao lên, đặt một mũi tên vào dây, ánh mắt không rời mục tiêu phía dưới. {BG2["cung"]}', None,
     'areum, cung, mái nhà', '서아름, 활, 지붕'),
    ('mui_ten_roi_day_doc', ['P11'], 'Cận cảnh dọc', ['Areum'],
     f'Cận cảnh ngón tay Areum buông dây cung, mũi tên lao xuống phía người xem, đầu mũi tên sáng lên dưới ánh đèn đường. {BG2["cung"]}',
     ['슝!'], 'mũi tên, buông dây, areum', '화살, 시위, 서아름'),
    ('ket_taeho_ngan_truoc_nhom_doc', ['OUTRO'], 'Cận mặt dọc', ['Taeho'],
     'Cận mặt Taeho ngước nhìn lên mái nhà, ánh đèn đường hắt viền sáng quanh khuôn mặt, nền tối gần như đen, ánh mắt căng thẳng, khoảng trống phía dưới để chèn lời kêu gọi xem tiếp.', None,
     'kết, taeho, cliffhanger', '엔딩, 강태호, 클리프행어'),
]

# --- lời đọc Hàn -> markdown ---
body = OrderedDict()
book = {'INTRO': [], 'OUTRO': []}
ko_first = {}
for line in open(D / 'scripts' / 'ko_ep2_short_check.txt', encoding='utf-8'):
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

md = ['## 종말의 날 | 제2화 숏츠 (9:16, 실측 예정) — 본문 여성 내레이션 / 소개·결말 남성 목소리', '## GIỚI THIỆU',
      ' '.join(book['INTRO']), '', '## TRUYỆN']
for sents in body.values():
    md += [' '.join(sents), '']
md += ['## KẾT', ' '.join(book['OUTRO'])]
text_md = '\n'.join(md) + '\n'
(D / 'scripts' / 'ep2_short_ko.md').write_text(text_md, encoding='utf-8', newline='\n')

# --- CSV + shot list ---
rows = []
for i, (slug, pids, shot, names, text, sfx, tvi, tko) in enumerate(SHOTS, 1):
    tags = f'ngay_tan, tap2, short, 9x16, vi, ko, rieng_short_tap2, {tvi}, {tko}'
    rows.append((f'S{i:02d}_{slug}.png', tags, make_prompt(shot, names, text, sfx)))
with open(D / 'ngay_tan_ep2_short_scenes.csv', 'w', encoding='utf-8-sig', newline='') as f:
    w = csv.writer(f, lineterminator='\r\n')
    w.writerow(HDR)
    for i, (fn, tags, prompt) in enumerate(rows, 1):
        w.writerow([i, fn, tags, prompt])

sl = ['# Ngày Tàn — Tập 2: video SHORT (9:16) — danh sách ảnh', '',
      f'{len(SHOTS)} ảnh dọc cho khoảng 60–70 giây giọng Hàn (≈ 4–5 giây/ảnh, chưa đo thật). Lời đọc: `scripts/ep2_short_vi.txt` (VI), `scripts/ep2_short_ko.md` (KO).', '',
      '| STT | File | Đoạn | Câu KO | Chữ hiệu ứng |', '|---|---|---|---|---|']
for i, (slug, pids, shot, names, text, sfx, tvi, tko) in enumerate(SHOTS, 1):
    sl.append(f'| {i} | S{i:02d}_{slug}.png | {", ".join(pids)} | {ko_first.get(pids[0], "")} | {"có" if sfx else ""} |')
(D / 'ngay_tan_ep2_short_shotlist.md').write_text('\n'.join(sl) + '\n', encoding='utf-8', newline='\n')

bad = set()
for fn, tags, prompt in rows:
    for ch in tags + prompt + text_md:
        o = ord(ch)
        if 0xAC00 <= o <= 0xD7A3 or o < 0x250 or 0x1E00 <= o <= 0x1EFF or ch in '“”‘’—…·–~':
            continue
        bad.add((ch, hex(o)))
print(len(rows), 'ảnh short; ký tự lạ:', bad, '; từ Hàn:', len(re.findall(r'[가-힣]+', text_md)))
