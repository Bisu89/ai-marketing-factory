"""Dựng ngay_tan_ep1_scenes_v3.csv + ngay_tan_ep1_shotlist.md từ danh sách S(...) bên dưới.
Tập mới: copy file này thành build_ep2_csv.py, thay danh sách S(...), tên file ra và kịch bản Hàn (ko_epN_check.txt).
Chạy: python build_ep1_csv.py (đóng file CSV nếu đang mở bằng Excel, nếu không sẽ bị PermissionError)."""
import csv, os, re

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import ngay_tan_blocks as _blocks

g = vars(_blocks)
STYLE, RATIO, NEG, BG = g['STYLE'], g['RATIO'], g['NEG'], g['BG']
D = str(HERE.parent)
HDR = ['STT', 'Ten file (filename.png)', 'Tags (dan khi import)', 'Prompt day du (copy nguyen vao ChatGPT)']

REF = {
    'Taeho': 'bang_nhan_vat_taeho.png', 'Minseo': 'bang_nhan_vat_minseo.png', 'Choi': 'bang_nhan_vat_choi.png',
    'Dahee': 'bang_nhan_vat_dahee.png', 'Kẻ Lang Thang': 'bang_zombie_lang_thang.png',
    'Kẻ Săn Mồi số 1': 'bang_zombie_ke_san_moi_so1.png',
}
NEG_SFX = NEG.replace('chữ, logo, watermark', 'phụ đề, bóng thoại, mọi chữ khác ngoài chữ hiệu ứng đã chỉ định, logo, watermark')
UNI = 'mặc quân phục dã chiến thượng sĩ và đội mũ nồi đen'
WET = 'áo khoác ướt mưa'
CAS = 'đồ thường ngày (áo len sáng màu và quần jeans)'
SUBJ = 'Subject-03 (Kẻ Săn Mồi số 1 khi còn là người, mặc đồ thử nghiệm xám nhạt)'


def sfx_text(items):
    return ('Chữ hiệu ứng tiếng động kiểu truyện tranh Hàn Quốc, viết bằng Hangul, nét dày cách điệu, đặt đúng chỗ phát ra âm thanh: '
            + ', '.join(f'"{t}"' for t in items) + '. Chỉ có đúng các chữ hiệu ứng này, không có chữ nào khác.')


ROSTER_FILE = 'bang_nhan_vat_tong_hop.png'
ROSTER = {
    'Taeho': 'KANG TAEHO (강태호)', 'Minseo': 'LEE MINSEO (이민서)', 'Choi': 'CHOI GANGSIK (최강식)',
    'Dahee': 'BAEK DAHEE (백다희)', 'Jiwoo': 'SEO JIWOO (서지우)', 'Yerin': 'HAN YERIN (한예린)', 'Areum': 'SEO AREUM (서아름)',
}


def make_prompt(shot, names, text, sfx):
    parts = []
    if names:
        humans = [n for n in names if n in ROSTER]
        monsters = [n for n in names if n not in ROSTER]
        # Ảnh mẫu đã được tạo sẵn trong cuộc trò chuyện GPT này: gọi lại theo tên, không đính kèm/up lại ảnh.
        head = ''
        if humans:
            mapping = '; '.join(f'{n} = {ROSTER[n]}' for n in humans)
            head += (f'Dùng lại bảng nhân vật tổng hợp đã tạo ở đầu cuộc trò chuyện này (không cần đính kèm lại ảnh). '
                     f'Nhân vật được gọi theo tên ghi trong bảng: {mapping}. Giữ đúng khuôn mặt, kiểu tóc, trang phục và dáng người '
                     'của nhân vật có đúng tên đó trong bảng (trừ chỗ được nêu thay đổi bên dưới).')
        if monsters:
            head += (f' Quái vật {", ".join(monsters)} giữ đúng hình dáng như bảng zombie tương ứng đã tạo trước đó trong cuộc trò chuyện này.')
        parts.append(head.strip())
    parts.append(f'[{shot}] {text}')
    parts.append('Tất cả nhân vật trong ảnh đều là người trưởng thành.')
    if sfx:
        parts.append(sfx_text(sfx))
    parts += [STYLE, RATIO, NEG_SFX if sfx else NEG]
    return ' '.join(parts)


SHOTS = []


def S(slug, pids, pri, reuse, shot, names, text, sfx, tvi, tko):
    SHOTS.append(dict(slug=slug, pids=pids, pri=pri, reuse=reuse, shot=shot, names=names, text=text, sfx=sfx, tvi=tvi, tko=tko))


# pri: A = bắt buộc, B = nên có, C = tuỳ chọn.  reuse: True = dùng lại được cho tập khác.
S('cong_chinh_taeho_gac', ['P01'], 'A', False, 'Cảnh rộng', ['Taeho'],
  f'Taeho {UNI}, đứng nghiêm gác ở chốt cổng phía bắc viện nghiên cứu Cheonma, ba ngày trước đại dịch. {BG["chinh"]}', None,
  'taeho, quân phục, gác cổng, cheonma, viện nghiên cứu', '태호, 군복, 정문, 경비, 천마, 연구소')
S('vien_cheonma_toan_canh_dem', ['P02'], 'B', True, 'Toàn cảnh', None,
  'Toàn cảnh viện nghiên cứu Cheonma nửa chìm vào sườn núi vào ban đêm lạnh, ánh đèn trắng lạnh hắt ra từ các cửa sổ, sương mỏng, không có người.', None,
  'viện nghiên cứu, cheonma, đêm, núi, toàn cảnh', '연구소, 천마, 밤, 산, 전경')
S('taeho_hanh_lang_nhin_kinh', ['P02'], 'A', False, 'Trung cảnh', ['Taeho'],
  f'Taeho {UNI}, đứng ở hành lang bên ngoài khu thử nghiệm, nhìn qua lớp kính dày, ánh đèn lạnh, không khí căng thẳng. {BG["lab"]}', None,
  'taeho, hành lang, kính dày, khu thử nghiệm, nhìn', '태호, 복도, 유리, 시험동')
S('ba_linh_bi_cach_ly', ['P02'], 'B', True, 'Góc nhìn qua kính', None,
  f'Nhìn qua lớp kính dày: ba người lính trưởng thành mặc đồ thử nghiệm xám nhạt ngồi và nằm trong phòng cách ly, trông mệt mỏi nhưng còn tỉnh táo, ánh đèn lạnh. {BG["lab"]}', None,
  'ba người lính, cách ly, thử nghiệm, phòng kính', '병사 세 명, 격리, 시험, 유리방')
S('ong_thuoc_aegis7_phat_sang', ['P02'], 'B', True, 'Cận cảnh', None,
  'Cận cảnh một giá đựng các ống thuốc nhỏ phát ra ánh xanh lạnh trong phòng thí nghiệm, vài ống có nhãn trống (không chữ), đèn trần phản chiếu trên mặt kính, không khí bí mật.', None,
  'aegis-7, ống thuốc, phòng thí nghiệm, ánh xanh', '이지스-7, 약병, 연구실, 푸른 빛')
S('linh_co_giat_sau_kinh', ['P03', 'P04'], 'A', True, 'Cảnh rộng', ['Kẻ Săn Mồi số 1'],
  f'Nhìn từ ngoài kính: {SUBJ}, nằm co giật dữ dội trên giường bệnh, đôi mắt bắt đầu phủ trắng đục; một bác sĩ chạy tới giữ vai; không máu me. {BG["lab"]}',
  ['쾅!', '쾅!'], 'subject-03, co giật, giường bệnh, thử nghiệm, aegis-7', '3호 피험자, 경련, 병상, 시험, 이지스-7')
S('ban_tay_bau_chat_thanh_giuong', ['P04'], 'B', True, 'Cận cảnh', None,
  'Cận cảnh hai bàn tay người lính bấu chặt thành giường bệnh, các đường gân nổi lên trên mu bàn tay và cẳng tay, ánh đèn lạnh.', None,
  'bàn tay, giường bệnh, co giật, gân', '손, 병상, 경련, 힘줄')
S('mat_phu_trang_duc', ['P04'], 'B', True, 'Cực cận mắt', None,
  'Cực cận đôi mắt của một người lính đang bị phủ dần một lớp trắng đục, đồng tử mờ đi, các mạch máu mỏng màu xám tối quanh mắt (không máu đỏ).', None,
  'mắt trắng đục, cận cảnh, biến đổi', '흰 눈, 클로즈업, 변이')
S('bac_si_giu_vai_tiem_an_than', ['P04'], 'A', True, 'Trung cảnh', None,
  f'Một bác sĩ giữ vai người lính đang co giật, bác sĩ thứ hai chuẩn bị ống tiêm thuốc an thần, hỗn loạn nhưng tiết chế, không máu me. {BG["lab"]}',
  ['쿵!'], 'bác sĩ, tiêm, an thần, co giật, phòng cách ly', '의사, 주사, 진정제, 경련, 격리실')
S('taeho_quay_dau_nhin_cua_kinh', ['P05'], 'C', False, 'Cận mặt', ['Taeho'],
  f'Cận mặt Taeho {UNI} khẽ quay đầu nhìn sang ô kính bên cạnh, ánh đèn lạnh hắt nghiêng, vẻ ngờ vực.', None,
  'taeho, quay đầu, nhìn, kính', '태호, 고개를 돌리다, 유리')
S('minseo_dung_sau_kinh', ['P06'], 'A', True, 'Trung cảnh', ['Minseo'],
  f'Minseo đứng sau một ô kính, mặt tái đi, không ghi chép cũng không nhìn màn hình, chỉ nhìn chằm chằm người đang co giật như thể điều cô sợ nhất cuối cùng đã xảy ra. {BG["lab"]}', None,
  'minseo, nghiên cứu viên, sợ hãi, sau kính', '민서, 연구원, 두려움, 유리')
S('minseo_can_mat_anh_mat_so_hai', ['P06'], 'B', True, 'Cận mặt', ['Minseo'],
  'Cận mặt Minseo, đôi mắt sau cặp kính nứt mở to, đồng tử run nhẹ, quầng thâm đậm, ánh đèn phòng thí nghiệm phản chiếu trên tròng kính.', None,
  'minseo, cận mặt, sợ hãi, kính nứt', '민서, 클로즈업, 두려움, 금 간 안경')
S('minseo_luot_qua_taeho', ['P07', 'P08'], 'B', False, 'Cảnh rộng', ['Taeho', 'Minseo'],
  f'Hành lang vắng của khu nghiên cứu: Minseo bước lướt ngang qua Taeho ({UNI}), không nhìn vào mặt anh, hai bóng người đi ngược chiều, ánh đèn hành lang lạnh. {BG["lab"]}', None,
  'minseo, taeho, hành lang, lướt qua', '민서, 태호, 복도, 스치다')
S('minseo_nhet_the_nho_vao_tay', ['P08'], 'A', False, 'Cận cảnh hai bàn tay', ['Taeho', 'Minseo'],
  f'Cận cảnh hai bàn tay: bàn tay Minseo nhét một chiếc thẻ nhớ nhỏ vào lòng bàn tay Taeho (đang {UNI}) rồi khép các ngón tay anh lại, phía sau mờ hai thân người lướt qua nhau. {BG["lab"]}', None,
  'minseo, taeho, thẻ nhớ, bàn tay, bí mật', '민서, 태호, 메모리카드, 손, 비밀')
S('taeho_nhin_theo_bong_minseo', ['P09', 'P10'], 'C', False, 'Trung cảnh sau lưng', ['Taeho', 'Minseo'],
  f'Taeho ({UNI}) đứng yên nắm chặt bàn tay có thẻ nhớ, nhìn theo bóng lưng Minseo đi xa dần cuối hành lang dài, ánh đèn phía cuối nhạt dần.', None,
  'taeho, minseo, nhìn theo, hành lang, bí ẩn', '태호, 민서, 뒷모습, 복도, 미스터리')
S('taeho_xem_the_nho_dem', ['P11'], 'A', True, 'Trung cảnh', ['Taeho'],
  'Taeho ngồi một mình trong phòng tối ban đêm, ánh sáng xanh từ màn hình máy tính xách tay hắt lên gương mặt căng thẳng khi xem dữ liệu (màn hình không có chữ).', None,
  'taeho, máy tính, thẻ nhớ, ban đêm, xem dữ liệu', '태호, 컴퓨터, 메모리카드, 밤, 자료 확인')
S('man_hinh_video_thu_nghiem', ['P11'], 'B', True, 'Cận màn hình', None,
  'Cận cảnh màn hình máy tính chia ô nhiều khung hình video thử nghiệm: bóng người lính trong phòng kính, một người đang co giật mờ, các đường biểu đồ xanh (không có chữ, không có số).', None,
  'màn hình, video thử nghiệm, dữ liệu', '화면, 시험 영상, 데이터')
S('tap_bao_cao_noi_bo_mat', ['P11'], 'C', True, 'Cận cảnh', None,
  'Cận cảnh một xấp báo cáo nội bộ có dấu mật đỏ tròn (không chữ) trên mặt bàn, một bàn tay đang lật trang, ánh đèn bàn ấm.', None,
  'báo cáo nội bộ, tài liệu mật, bàn tay', '내부 보고서, 기밀, 손')
S('nguoi_thu_thuoc_mat_kiem_soat', ['P11'], 'B', True, 'Cảnh tưởng tượng tối', None,
  'Hình dung trong đầu Taeho, tông tối nhiều bóng: một người lính trưởng thành bị trói vào ghế, hung hãn vùng vẫy, đôi mắt trắng đục, da xám dần, các nhân viên áo trắng đứng xa quan sát; tiết chế, không máu me.', None,
  'người thử thuốc, mất kiểm soát, hung hãn, hồi tưởng', '시험 대상자, 통제 불능, 난폭, 회상')
S('taeho_giau_ban_sao_the_quan_nhan', ['P12'], 'A', False, 'Cận cảnh', ['Taeho'],
  'Cận cảnh bàn tay Taeho mở vỏ chiếc thẻ quân nhân đeo ở cổ và giấu một thẻ nhớ siêu nhỏ vào mặt trong, ánh đèn bàn ấm trong phòng ở ban đêm, khuôn mặt anh mờ phía sau.', ['철컥'],
  'taeho, thẻ quân nhân, bản sao, giấu', '태호, 인식표, 사본, 숨기다')
S('taeho_khoa_the_goc_vao_tu', ['P12'], 'B', False, 'Cận cảnh', ['Taeho'],
  f'Taeho ({UNI}) đặt thẻ nhớ gốc vào ngăn tủ cá nhân bằng sắt xám rồi khoá lại, cận cảnh bàn tay và ổ khoá, hành lang phòng nghỉ lính tối.', ['철컥'],
  'taeho, tủ cá nhân, thẻ gốc, khoá', '태호, 사물함, 원본, 잠금')
S('taeho_dung_canh_cua_so_dem', ['P13', 'P14'], 'C', False, 'Cận mặt từ bên', ['Taeho'],
  'Taeho đứng bên cửa sổ phòng tối nhìn ra khu căn cứ trong đêm, gương mặt vừa tin vừa lo, ánh đèn ngoài sân hắt nghiêng lên mặt anh.', None,
  'taeho, cửa sổ, đêm, suy nghĩ', '태호, 창문, 밤, 생각')
S('taeho_bao_cao_dai_ta_choi', ['P15'], 'A', False, 'Trung cảnh', ['Taeho', 'Choi'],
  f'Taeho {UNI}, đứng báo cáo trước bàn làm việc của Choi; Choi ngả người ra ghế nghe không cắt ngang, không ngạc nhiên. {BG["vp"]}', None,
  'taeho, choi, đại tá, báo cáo, văn phòng', '태호, 최강식, 대령, 보고, 사무실')
S('choi_can_mat_nghe_im_lang', ['P15'], 'B', True, 'Cận mặt', ['Choi'],
  'Cận mặt Choi ngả người ra sau ghế, hai ngón tay chạm nhẹ vào cằm, ánh mắt tính toán, không chớp, ánh đèn bàn hắt nửa mặt.', None,
  'choi, cận mặt, lạnh lùng, tính toán', '최강식, 클로즈업, 냉정, 계산')
S('taeho_noi_toi_con_co_du_lieu', ['P16', 'P17', 'P18'], 'B', False, 'Cận mặt hai người', ['Taeho', 'Choi'],
  f'Cảnh đối thoại: Taeho ({UNI}) nhìn thẳng vào Choi và nói ngắn gọn, Choi nhìn lại chăm chú; ánh mắt Choi bắt đầu thay đổi rất nhẹ. {BG["vp"]}', None,
  'taeho, choi, đối thoại, dữ liệu', '태호, 최강식, 대화, 자료')
S('choi_anh_mat_doi_khac', ['P19'], 'C', True, 'Cực cận mắt', ['Choi'],
  'Cực cận đôi mắt Choi, đồng tử thu nhỏ rất nhẹ, một tia lạnh chớp qua, nền tối mờ.', None,
  'choi, ánh mắt, cực cận', '최강식, 눈빛, 클로즈업')
S('taeho_bi_ap_giai_hanh_lang', ['P20'], 'B', False, 'Cảnh rộng', ['Taeho'],
  f'Hành lang quân sự dài: hai người lính áp giải Taeho ({UNI}) đi, anh bước đều nhưng ánh mắt cảnh giác, ánh đèn trắng lạnh, bóng đổ dài.', None,
  'taeho, áp giải, hành lang quân sự, lính', '태호, 연행, 군 복도, 병사')
S('phong_tham_van_ho_so_gia', ['P20', 'P21'], 'A', False, 'Cảnh rộng', ['Taeho'],
  f'Phòng thẩm vấn quân sự lạnh lẽo: một người lính cấp dưới mặt bầm tím đứng bên bàn, trên bàn là báo cáo thương tích và vài vật chứng, camera an ninh ở góc trần; Taeho ({UNI}) ngồi đối diện, ánh mắt lạnh.', None,
  'taeho, thẩm vấn, hồ sơ giả, camera, bị hãm hại', '태호, 취조실, 조작, 누명, 카메라')
S('linh_cap_duoi_mat_bam_tim', ['P21'], 'C', True, 'Cận mặt', None,
  'Cận mặt một người lính cấp dưới trưởng thành với mặt bầm tím được dàn dựng, mắt tránh nhìn, mồ hôi trên trán, ánh đèn phòng thẩm vấn gắt.', None,
  'người lính, bầm tím, dàn dựng, thẩm vấn', '병사, 멍, 연출, 취조')
S('anh_camera_va_bao_cao_gia', ['P21'], 'B', True, 'Cận cảnh mặt bàn', None,
  'Cận cảnh mặt bàn phòng thẩm vấn: báo cáo thương tích, vài ảnh chụp từ camera an ninh và các vật chứng xếp ngay ngắn như được sắp đặt sẵn (không chữ).', None,
  'vật chứng, báo cáo, camera, dàn dựng', '증거, 보고서, 카메라, 조작')
S('taeho_biet_la_gia', ['P22'], 'B', False, 'Cận mặt', ['Taeho'],
  f'Cận mặt Taeho ({UNI}) nhìn xuống các vật chứng, ánh mắt lạnh và bình tĩnh khi nhận ra tất cả là dàn dựng.', None,
  'taeho, nhận ra, bình tĩnh, cận mặt', '태호, 깨닫다, 침착, 클로즈업')
S('linh_luc_tu_ca_nhan_cua_taeho', ['P23'], 'B', False, 'Cảnh rộng', None,
  'Trong phòng nghỉ tối, hai người lính lục tung tủ cá nhân bằng sắt xám, quần áo và đồ đạc vương vãi trên sàn, ánh đèn pin quét qua.', None,
  'lục tủ, tủ cá nhân, lính, lục soát', '사물함, 수색, 병사')
S('vo_the_quan_nhan_bi_bo_sot', ['P23'], 'A', False, 'Cận cảnh', ['Taeho'],
  'Cận cảnh chiếc thẻ quân nhân đeo trước ngực Taeho, chiếc vỏ kim loại sáng mờ, phía sau là hình bóng hai người lính đang quay đi, không ai chú ý tới nó.', None,
  'thẻ quân nhân, vỏ thẻ, bị bỏ sót, cận cảnh', '인식표, 케이스, 놓치다, 클로즈업')
S('taeho_bi_tuoc_quan_ham', ['P24', 'P25'], 'A', False, 'Trung cảnh', ['Taeho', 'Choi'],
  f'Taeho {UNI}, đứng thẳng bất động khi quân hàm thượng sĩ bị gỡ khỏi vai; Choi đứng sau bàn nhìn anh rất lâu. {BG["vp"]}', None,
  'taeho, choi, tước quân hàm, loại ngũ', '태호, 최강식, 계급 박탈, 전역')
S('quan_ham_roi_xuong_ban', ['P24'], 'B', False, 'Cận cảnh', None,
  'Cận cảnh một chiếc quân hàm thượng sĩ bị đặt xuống mặt bàn gỗ tối, ánh đèn bàn hắt một vệt sáng lạnh lên nó.', ['탁!'],
  'quân hàm, tước, mặt bàn, cận cảnh', '계급장, 박탈, 책상, 클로즈업')
S('choi_nhin_taeho_biet_qua_nhieu', ['P26'], 'A', True, 'Cận mặt', ['Choi'],
  f'Cận mặt Choi đứng sau bàn, ánh mắt lạnh và chậm rãi, như đang nói một câu chốt hạ, phông tối mờ. {BG["vp"]}', None,
  'choi, cận mặt, đe dọa, văn phòng', '최강식, 클로즈업, 위협, 사무실')
S('taeho_im_lang_khong_tra_loi', ['P27'], 'B', False, 'Cận mặt', ['Taeho'],
  f'Cận mặt Taeho ({UNI}) im lặng, hàm siết lại, ánh mắt nhìn thẳng vào Choi không đáp, nửa mặt chìm trong bóng.', None,
  'taeho, im lặng, cận mặt, nhìn thẳng', '태호, 침묵, 클로즈업, 정면')
S('taeho_buoc_ra_cua_dong_lai', ['P27', 'P28'], 'B', False, 'Cảnh sau lưng', ['Taeho'],
  f'Taeho bước ra khỏi căn phòng, cánh cửa gỗ nặng đóng lại sau lưng anh, hành lang trống, bóng anh đổ dài dưới ánh đèn, anh không còn quân hàm trên vai.', ['탁!'],
  'taeho, cánh cửa, đóng lại, bước ra', '태호, 문, 닫히다, 나가다')
S('taeho_di_san_can_cu_ba_lo', ['P28'], 'B', False, 'Cảnh rộng', ['Taeho'],
  'Chiều tối, Taeho mặc áo thun đen và áo khoác dã chiến, đeo balô cũ, bước một mình qua sân căn cứ trống, ngoái nhìn toà nhà chỉ huy lần cuối, ánh nắng cuối ngày cam nhạt.', None,
  'taeho, sân căn cứ, rời đi, balô', '태호, 기지, 떠나다, 배낭')
S('taeho_lai_xe_hoang_hon', ['P29'], 'A', True, 'Cảnh rộng', ['Taeho'],
  'Taeho một mình lái xe trên con đường ven núi về phía thành phố lúc trời bắt đầu tối, ánh hoàng hôn cam tím hắt lên kính xe, vẻ mặt trống rỗng.', None,
  'taeho, lái xe, hoàng hôn, thành phố, một mình', '태호, 운전, 황혼, 도시, 혼자')
S('coc_xe_do_dac_ca_nhan', ['P29'], 'C', False, 'Cận cảnh', None,
  'Cận cảnh cốp xe mở: vài bộ quần áo gấp vội, một túi đồ cá nhân và một chiếc balô cũ, ánh hoàng hôn cam rọi vào.', None,
  'cốp xe, đồ cá nhân, balô, cận cảnh', '트렁크, 짐, 배낭, 클로즈업')
S('hop_nhan_tren_ghe_xe', ['P30'], 'A', False, 'Cận cảnh', None,
  'Cận cảnh một hộp nhẫn nhỏ mở nắp trên ghế phụ, chiếc nhẫn lấp lánh dưới ánh hoàng hôn, bóng vô-lăng mờ phía trước.', None,
  'hộp nhẫn, nhẫn cầu hôn, ghế xe, hoàng hôn', '반지 상자, 프러포즈, 차 좌석, 황혼')
S('hoi_tuong_taeho_va_dahee', ['P30'], 'A', False, 'Cảnh hồi tưởng ấm áp', ['Taeho', 'Dahee'],
  f'Hồi tưởng tông màu ấm, ánh sáng dịu: Taeho ({CAS}) và Dahee (váy đời thường nhẹ nhàng) cùng đi bên nhau trên phố đêm có đèn lồng, cười nhẹ; Taeho trông thư giãn, khác hẳn ngày thường.', None,
  'taeho, dahee, hồi tưởng, hẹn hò, ấm áp', '태호, 다희, 회상, 데이트, 따뜻함')
S('dien_thoai_do_chuong_khong_ai_nghe', ['P31'], 'C', True, 'Cận cảnh', ['Taeho'],
  'Cận cảnh bàn tay Taeho cầm điện thoại đang đổ chuông trên màn hình (không chữ), không ai nghe máy, nền xe tối.', ['지잉'],
  'điện thoại, đổ chuông, không nghe máy', '휴대전화, 신호음, 받지 않음')
S('xe_quan_doi_den_dau_ben_kia_duong', ['P31'], 'A', False, 'Cảnh rộng', ['Taeho'],
  f'Taeho ({WET}) đứng bên này đường nhìn sang chiếc xe quân đội màu đen đang đỗ bên kia đường trước nhà Dahee. {BG["nha"]}', None,
  'taeho, xe quân đội, nhà dahee, bên kia đường', '태호, 군용 차량, 다희 집, 길 건너')
S('dahee_buoc_xuong_xe', ['P32'], 'A', False, 'Trung cảnh', ['Dahee'],
  f'Dahee bước xuống từ chiếc xe quân đội đen, tay giữ cửa xe, vẻ mặt vừa lo lắng vừa cảnh giác. {BG["nha"]}', None,
  'dahee, xuống xe, xe quân đội, lo lắng', '다희, 하차, 군용 차량, 불안')
S('choi_buoc_ra_tu_ghe_sau', ['P33'], 'A', False, 'Trung cảnh', ['Choi'],
  f'Choi bước ra từ ghế sau của chiếc xe quân đội đen, chỉnh lại găng tay da, ánh mắt quét qua con đường. {BG["nha"]}', None,
  'choi, ghế sau, xe quân đội, bước ra', '최강식, 뒷좌석, 군용 차량, 내리다')
S('dahee_va_choi_di_vao_nha', ['P33'], 'B', False, 'Cảnh rộng', ['Dahee', 'Choi'],
  f'Dahee và Choi cùng bước vào cổng nhà dưới đèn cổng ấm, Choi hơi cúi đầu nói nhỏ với cô, mưa phùn lấm tấm. {BG["nha"]}', None,
  'dahee, choi, vào nhà, mưa', '다희, 최강식, 집, 비')
S('taeho_dung_trong_mua_suy_nghi', ['P34'], 'B', False, 'Cận mặt', ['Taeho'],
  f'Cận mặt Taeho ({WET}) đứng dưới mưa phùn, ánh mắt đảo giữa những khả năng, vẻ chối bỏ điều mình sợ, đèn đường mờ phía sau.', None,
  'taeho, mưa, suy nghĩ, chối bỏ', '태호, 비, 생각, 부정')
S('taeho_tien_lai_gan_cua', ['P35'], 'B', False, 'Cảnh sau lưng', ['Taeho'],
  f'Taeho ({WET}) bước từng bước chậm tới gần cánh cửa nhà Dahee, ánh đèn cổng ấm hắt lên lưng anh, bóng đổ dài ra đường ướt. {BG["nha"]}', ['터벅터벅'],
  'taeho, tiến lại gần cửa, nhà dahee', '태호, 문 앞, 다희 집, 다가가다')
S('ban_tay_cham_tay_nam_cua', ['P35'], 'A', False, 'Cận cảnh', ['Taeho'],
  f'Cận cảnh bàn tay Taeho ({WET}) sắp chạm vào tay nắm cửa, khoảnh khắc ngập ngừng, ánh đèn ấm từ khe cửa hắt ra.', ['두근'],
  'bàn tay, tay nắm cửa, ngập ngừng, cận cảnh', '손, 문고리, 망설임, 클로즈업')
S('trong_nha_dahee_noi_nho', ['P36', 'P37', 'P38', 'P39'], 'A', False, 'Cảnh cắt vào trong nhà', ['Dahee', 'Choi'],
  'Cảnh cắt vào bên trong nhà (Taeho không nhìn thấy): Dahee đứng cúi đầu nói rất nhỏ, hai tay nắm chặt vào nhau, Choi ngồi trên ghế sofa nghe, ánh đèn phòng khách ấm nhưng không khí lạnh.', None,
  'dahee, choi, phòng khách, nói nhỏ, báo cáo', '다희, 최강식, 거실, 속삭임, 보고')
S('taeho_dung_chet_lang', ['P40'], 'A', False, 'Cận mặt', ['Taeho'],
  f'Cận mặt Taeho ({WET}) đứng chết lặng ngoài cửa, mắt mở rộng nhưng không có biểu cảm, mưa phùn đọng trên hàng mi, ánh đèn cổng ấm hắt nghiêng.', None,
  'taeho, chết lặng, ngoài cửa, cận mặt', '태호, 얼어붙다, 문 밖, 클로즈업')
S('taeho_tim_ly_do_de_tin', ['P41'], 'C', False, 'Cảnh tưởng tượng', ['Taeho'],
  f'Hình dung trong đầu Taeho: nhiều bóng mờ chồng lên nhau, Taeho ({WET}) đứng giữa, xung quanh là các hình ảnh Dahee mỉm cười xen lẫn bóng Choi, tông màu lạnh và lệch, cảm giác choáng váng.', None,
  'taeho, choáng váng, lý do, hoang mang', '태호, 혼란, 이유, 충격')
S('dahee_noi_nho_choi_nhin', ['P42'], 'C', False, 'Cận mặt', ['Dahee'],
  'Cận mặt Dahee cúi đầu, ánh mắt tránh nhìn, môi mím chặt, nước mắt chực trào nhưng cô kìm lại, ánh đèn phòng khách ấm.', None,
  'dahee, cận mặt, kìm nén, báo cáo', '다희, 클로즈업, 억누름, 보고')
S('chiec_nhan_trong_long_ban_tay', ['P43'], 'A', False, 'Cận cảnh', ['Taeho'],
  'Cận cảnh chiếc nhẫn cầu hôn nằm trong lòng bàn tay Taeho dưới ánh đèn đường lạnh, vài giọt mưa đọng trên mặt nhẫn.', None,
  'chiếc nhẫn, lòng bàn tay, cầu hôn, mưa', '반지, 손바닥, 프러포즈, 비')
S('taeho_quyet_khong_buoc_vao', ['P44'], 'B', False, 'Cảnh sau lưng', ['Taeho'],
  f'Taeho ({WET}) đứng trước cánh cửa khép, đầu hơi cúi, bàn tay buông xuống, không bước vào, ánh đèn ấm phía sau cánh cửa đối lập với bóng tối quanh anh.', None,
  'taeho, quyết định, không bước vào, cánh cửa', '태호, 결심, 들어가지 않다, 문')
S('taeho_tha_nhan_xuong_ranh', ['P45'], 'A', False, 'Cận cảnh', ['Taeho'],
  'Cận cảnh bàn tay Taeho thả chiếc nhẫn cầu hôn xuống rãnh nước bên vỉa hè, nước mưa lấp lánh phản chiếu đèn đường, gương mặt anh mờ phía sau quay đi.', ['퐁당'],
  'taeho, nhẫn, rãnh nước, buông bỏ', '태호, 반지, 배수구, 포기')
S('taeho_di_bo_trong_mua_dem', ['P46'], 'B', True, 'Cảnh rộng', ['Taeho'],
  f'Taeho ({WET}) đi bộ một mình dọc con phố vắng trong mưa, bóng anh kéo dài dưới các cột đèn đường, thành phố xa xa mờ sáng.', ['터벅터벅'],
  'taeho, đi bộ, mưa, phố vắng, một mình', '태호, 걷다, 비, 한적한 거리, 혼자')
S('dien_thoai_rung_so_la', ['P46', 'P47'], 'B', True, 'Cận cảnh', ['Taeho'],
  'Cận cảnh điện thoại rung trên bảng điều khiển xe, màn hình sáng lên tin nhắn từ số lạ (không chữ), nền xe tối.', ['지잉'],
  'điện thoại, rung, tin nhắn, số lạ', '휴대전화, 진동, 문자, 모르는 번호')
S('taeho_doc_tin_nhan_la', ['P47', 'P48'], 'A', True, 'Trung cảnh', ['Taeho'],
  'Taeho ngồi trong xe đỗ ven đường ban đêm, ánh sáng xanh từ màn hình điện thoại hắt lên mặt anh khi đọc một tin nhắn từ số lạ (màn hình không có chữ), vẻ cảnh giác.', None,
  'taeho, điện thoại, tin nhắn, số lạ, đêm', '태호, 휴대전화, 문자, 모르는 번호, 밤')
S('taeho_nhin_quanh_ai_gui', ['P49'], 'C', True, 'Cảnh sau kính xe', ['Taeho'],
  'Nhìn qua kính chắn gió dính mưa: Taeho ngồi trong xe quay nhìn quanh con đường vắng, tìm xem ai gửi tin nhắn, đèn đường nhòe.', None,
  'taeho, nhìn quanh, xe, mưa', '태호, 주위를 보다, 차, 비')
S('minseo_o_tang_ngam_gui_du_lieu', ['P50', 'P51'], 'A', True, 'Trung cảnh', ['Minseo'],
  'Minseo ngồi trước màn hình máy tính ở tầng ngầm, ánh sáng xanh lạnh hắt lên mặt cô, bàn tay run khi cố gửi dữ liệu ra ngoài (không có chữ trên màn hình).', None,
  'minseo, máy tính, tầng ngầm, gửi dữ liệu', '민서, 컴퓨터, 지하, 데이터 전송')
S('thanh_tien_trinh_chay_cham', ['P51'], 'B', True, 'Cận màn hình', None,
  'Cận cảnh một thanh tiến trình xanh dài chạy chậm qua từng phần trên màn hình tối, ánh sáng phản chiếu trên mặt bàn (không có chữ, không có số).', None,
  'thanh tiến trình, gửi dữ liệu, màn hình', '진행 막대, 데이터 전송, 화면')
S('dong_ho_tuong_7_gio_42', ['P51'], 'B', True, 'Cận cảnh', None,
  'Cận cảnh chiếc đồng hồ kim treo tường trong phòng thí nghiệm ngầm, kim giờ và kim phút chỉ khoảng bảy giờ bốn mươi hai phút, ánh đèn lạnh, không có chữ khác.', ['똑딱'],
  'đồng hồ, 19 giờ 42, phòng thí nghiệm', '시계, 7시 42분, 연구실')
S('minseo_nghe_tieng_dap_tu_khu_thi_nghiem', ['P52'], 'B', True, 'Cận mặt', ['Minseo'],
  'Cận mặt Minseo ngẩng đầu lên khỏi màn hình, ánh mắt giật mình hướng về phía cửa kính, âm thanh nặng vọng lại.', ['쿵!'],
  'minseo, nghe tiếng động, giật mình', '민서, 소리, 놀람')
S('subject03_dung_day_nghieng_dau', ['P53'], 'A', True, 'Trung cảnh sau kính', ['Kẻ Săn Mồi số 1'],
  f'Qua lớp kính: Subject-03 đứng dậy từ giường bệnh, đầu nghiêng như đang làm quen với cơ thể mình, da bắt đầu xám nhợt, mắt trắng đục, các bác sĩ phía sau chưa kịp nhận ra. {BG["lab"]}', None,
  'subject-03, đứng dậy, nghiêng đầu, biến đổi', '3호 피험자, 일어서다, 고개를 갸웃, 변이')
S('subject03_dap_vo_kinh', ['P53', 'P54'], 'A', True, 'Cảnh rộng hành động', ['Kẻ Săn Mồi số 1'],
  f'Subject-03 (Kẻ Săn Mồi số 1, vừa biến đổi) lao vào ô kính khiến kính rạn nứt, một bác sĩ ngã xuống phía sau; đèn báo động đỏ nhấp nháy khắp phòng. {BG["lab_do"]} Cảnh tiết chế, không chi tiết máu me.',
  ['쾅!', '쨍그랑!'], 'subject-03, đập kính, bác sĩ ngã, báo động', '3호 피험자, 유리를 깨다, 의사, 경보')
S('bac_si_bi_can_bong_den', ['P54', 'P55'], 'B', True, 'Cảnh bóng đen', None,
  'Cảnh dạng bóng đen (silhouette) trước ánh đèn báo động đỏ: một bác sĩ ngã xuống sàn, một bóng người khác lao vào, người thứ hai cố kéo đồng nghiệp ra; không chi tiết máu me, chỉ hình khối đen và ánh đỏ.',
  ['꺄악!'], 'bác sĩ, bị cắn, bóng đen, hỗn loạn', '의사, 물림, 실루엣, 혼란')
S('hanh_lang_bao_dong_do_hoang_loan', ['P55'], 'B', True, 'Cảnh rộng', None,
  f'Hành lang khu nghiên cứu chìm trong ánh đèn báo động đỏ, nhân viên áo trắng chạy tán loạn, vài người va vào nhau, hộp tài liệu rơi vãi. {BG["lab_do"]}',
  ['삐—삐—', '후다닥!'], 'báo động đỏ, hỗn loạn, nhân viên chạy, hành lang', '붉은 경보, 혼란, 직원, 복도')
S('minseo_nhin_man_hinh_lan_cuoi', ['P56'], 'B', True, 'Cận mặt', ['Minseo'],
  'Cận mặt Minseo nhìn thanh tiến trình trên màn hình đứng ở mức chưa đầy, nhiều ánh đèn đỏ nhấp nháy hắt lên kính mắt, vẻ quyết định đã gần tới.', ['삐—삐—'],
  'minseo, màn hình, lần cuối, tiến trình', '민서, 화면, 마지막, 진행')
S('minseo_lay_ong_mau_tu_tu_lanh', ['P57'], 'A', True, 'Cận cảnh', ['Minseo'],
  'Cận cảnh bàn tay Minseo lấy một ống mẫu nhỏ từ tủ lạnh phòng thí nghiệm, hơi lạnh bốc lên, ánh đèn đỏ báo động nhấp nháy phía sau.', None,
  'minseo, ống mẫu, tủ lạnh, mẫu gốc', '민서, 시료관, 냉장고, 원본 샘플')
S('minseo_chay_ham_so_tan', ['P57'], 'A', True, 'Cảnh rộng hành động', ['Minseo'],
  f'Minseo (blouse lấm bụi, tóc rối hơn) ôm chặt chiếc hộp kim loại đựng mẫu, chạy hết tốc lực xuống đường hầm sơ tán quân sự cũ, đèn báo động đỏ đổ bóng dài phía sau cô. {BG["ham"]}',
  ['후다닥!', '삐—삐—'], 'minseo, chạy, hầm sơ tán, hộp mẫu', '민서, 달리다, 대피 터널, 시료 상자')
S('choi_nhan_bao_cao_trung_tam_chi_huy', ['P58', 'P59'], 'A', True, 'Trung cảnh', ['Choi'],
  'Choi đứng ở trung tâm chỉ huy với những màn hình cảnh báo đỏ phía sau, nhận báo cáo đầu tiên bằng điện đàm, vẻ mặt bình thản đáng sợ.', None,
  'choi, trung tâm chỉ huy, báo cáo, màn hình đỏ', '최강식, 지휘 센터, 보고, 붉은 화면')
S('man_hinh_camera_nhan_vien_ket_ben_trong', ['P60'], 'A', True, 'Cận màn hình', None,
  'Cận cảnh dãy màn hình camera an ninh: vài nhân viên áo trắng đập vào cánh cửa khoá từ bên trong một hành lang, vẻ hoảng loạn, hình ảnh hạt nhiễu, ánh đỏ cảnh báo (không chữ).', ['쾅!'],
  'màn hình camera, nhân viên bị kẹt, cửa khoá', '감시 카메라, 갇힌 직원, 잠긴 문')
S('si_quan_tre_do_du_hoi', ['P60', 'P61', 'P62'], 'B', True, 'Cận mặt', None,
  'Cận mặt một sĩ quan trẻ trưởng thành đứng cạnh Choi, do dự, giọng như nghẹn lại, mắt liếc nhìn các màn hình đỏ phía sau, trang phục sĩ quan chỉnh tề.', None,
  'sĩ quan trẻ, do dự, trung tâm chỉ huy', '젊은 장교, 망설임, 지휘 센터')
S('choi_im_lang_vai_giay', ['P63'], 'A', True, 'Cực cận mắt', ['Choi'],
  'Cực cận đôi mắt Choi nhìn thẳng, không chớp, ánh đỏ từ màn hình phản chiếu trong đồng tử, không khí đông cứng.', None,
  'choi, im lặng, ánh mắt, cực cận', '최강식, 침묵, 눈빛, 클로즈업')
S('choi_ra_lenh_khong_ai_duoc_ra', ['P64'], 'A', True, 'Trung cảnh', ['Choi'],
  'Choi quay lưng một nửa với sĩ quan trẻ, nói câu ra lệnh cuối cùng, ánh đỏ từ màn hình chiếu lên nửa gương mặt lạnh lẽo.', None,
  'choi, ra lệnh, phong tỏa, lạnh lùng', '최강식, 명령, 봉쇄, 냉혹')
S('cong_khu_quan_su_xe_cuu_thuong_roi_di', ['P65'], 'A', False, 'Cảnh rộng', None,
  'Cổng chính khu quân sự Cheonma ban đêm: một xe cứu thương bật đèn đỏ chạy ra khỏi cổng, trạm gác phía sau chưa kịp đóng cổng, hàng rào thép gai, đèn pha quét, núi tối phía sau.',
  ['삐뽀삐뽀', '부릉~'], 'cổng quân sự, xe cứu thương, thoát ra, lây lan', '군사 정문, 구급차, 탈출, 확산')
S('xe_buyt_doi_ca_tren_duong_dem', ['P65', 'P66'], 'B', False, 'Cảnh rộng', None,
  'Một chiếc xe buýt đổi ca chạy trên đường vắng ban đêm về phía ánh đèn thành phố xa xa, trong xe lờ mờ các nhân viên ngồi mệt mỏi, một người tựa trán vào cửa kính, mồ hôi lấm tấm.', ['부릉~'],
  'xe buýt, đổi ca, đường đêm, nhân viên', '버스, 교대, 밤길, 직원')
S('nguoi_ngoi_xe_buyt_sot_va_tai_nhot', ['P65'], 'B', False, 'Cận mặt', None,
  'Cận mặt một nhân viên trưởng thành ngồi trong xe buýt đêm, da hơi tái, mồ hôi trên trán, mắt lờ đờ nhìn ra cửa kính tối, đường gân đen mờ nhạt bắt đầu hiện dưới cổ áo (rất nhẹ, gợi ý).', None,
  'nhân viên, xe buýt, sốt, tái nhợt, ủ bệnh', '직원, 버스, 열, 창백, 잠복')
S('ban_do_duong_tu_cheonma_den_seoryeong', ['P65'], 'C', True, 'Cảnh minh hoạ', None,
  'Bản đồ ban đêm kiểu minh hoạ tối giản: vùng núi phía trên có một chấm sáng đỏ (viện nghiên cứu), một đường sáng kéo xuống thành phố phía dưới với nhiều chấm sáng nhỏ; không có chữ, không có số.', None,
  'bản đồ, cheonma, seoryeong, lây lan', '지도, 천마, 서령, 확산')
S('taeho_ngoi_trong_xe_duong_vanh_dai', ['P67'], 'A', True, 'Trung cảnh', ['Taeho'],
  f'Taeho dừng xe giữa đường vành đai ban đêm, tay đặt trên vô-lăng, đèn đường vàng cam hắt qua kính. {BG["vanh_dai"]}', None,
  'taeho, xe, đường vành đai, đêm, dừng', '태호, 차, 순환도로, 밤, 정차')
S('dien_thoai_mat_song', ['P67', 'P68'], 'B', True, 'Cận cảnh', None,
  'Cận cảnh màn hình điện thoại trên bảng điều khiển xe: thanh sóng biến mất từng vạch rồi không còn gì (không chữ), ánh sáng mờ lạnh.', None,
  'điện thoại, mất sóng, vạch sóng', '휴대전화, 신호 끊김, 안테나')
S('dong_xe_don_lai_xe_cuu_thuong_vuot', ['P68'], 'A', True, 'Cảnh rộng', None,
  f'Đường vành đai ban đêm: dòng xe phía trước dồn lại, hai xe cứu thương lần lượt vượt qua vai đường với đèn đỏ quay, còi vang vọng, bóng tối sâu phía sau. {BG["vanh_dai"]}',
  ['삐뽀삐뽀', '빵빵!'], 'đường vành đai, xe cứu thương, dồn xe, còi', '순환도로, 구급차, 정체, 경적')
S('taeho_giam_toc_do', ['P69'], 'C', True, 'Cận cảnh bàn chân', ['Taeho'],
  'Cận cảnh bàn chân Taeho từ từ nhả chân ga rồi đặt lên phanh, đèn pha xe phía trước loang trên mặt đường.', None,
  'taeho, giảm tốc, chân phanh', '태호, 감속, 브레이크')
S('nguoi_chay_ra_giua_xe_bo_lai', ['P70'], 'A', True, 'Cảnh rộng', ['Kẻ Lang Thang'],
  f'Một Kẻ Lang Thang (người đàn ông bị nhiễm) bất ngờ chạy ra từ giữa những chiếc xe bỏ lại trên đường vành đai ban đêm, dáng chúi về phía trước. {BG["vanh_dai"]}', None,
  'người nhiễm, chạy ra, xe bỏ lại, đường vành đai', '감염자, 튀어나오다, 버려진 차, 순환도로')
S('nguoi_nhiem_dap_nap_capo', ['P71'], 'A', True, 'Trung cảnh nhìn từ trong xe', ['Kẻ Lang Thang'],
  f'Nhìn từ trong xe: Kẻ Lang Thang đập hai tay lên nắp capo rồi lao thẳng về phía kính chắn gió. {BG["vanh_dai"]}', ['쾅!'],
  'người nhiễm, đập capo, kính chắn gió', '감염자, 보닛, 앞유리')
S('taeho_dap_phanh_phan_xa', ['P71'], 'B', True, 'Cận cảnh', ['Taeho'],
  'Cận cảnh Taeho giật mình đạp phanh, hai tay siết vô-lăng, mắt mở lớn, ánh đèn pha phản chiếu trên kính.', ['끼익!'],
  'taeho, đạp phanh, phản xạ', '태호, 급브레이크, 반사 신경')
S('nguoi_nhiem_dap_kinh_xe', ['P72', 'P73'], 'A', True, 'Cảnh nhìn từ trong xe', ['Taeho', 'Kẻ Lang Thang'],
  f'Nhìn từ trong xe: Kẻ Lang Thang đập hai tay lên kính chắn gió rồi chống tay ngẩng mặt lên, chất lỏng đen sẫm loãng chảy từ cổ xuống áo; ở góc dưới Taeho siết cán dao găm, kính xe bắt đầu rạn nứt. {BG["vanh_dai"]}',
  ['쾅! 쾅!', '우지직'], 'người nhiễm, đập kính xe, taeho, dao', '감염자, 앞유리, 태호, 칼')
S('mat_nguoi_nhiem_ap_kinh_can_mat', ['P73', 'P74'], 'B', True, 'Cận mặt qua kính', ['Kẻ Lang Thang'],
  'Cận mặt qua lớp kính chắn gió rạn: gương mặt người đàn ông bị nhiễm áp sát vào kính, da trắng bệch, mắt đục ngầu, miệng há, hơi thở làm mờ kính.', None,
  'người nhiễm, cận mặt, áp kính, mắt đục', '감염자, 클로즈업, 유리, 흐린 눈')
S('chat_long_den_chay_tu_co', ['P74'], 'B', True, 'Cực cận cổ', ['Kẻ Lang Thang'],
  'Cực cận cổ và cổ áo của người bị nhiễm, một dòng chất lỏng đen sẫm loãng chảy từ vết thương xuống áo, tông màu tối, tiết chế, không máu đỏ.', None,
  'chất lỏng đen, cổ, vết thương, cực cận', '검은 액체, 목, 상처, 클로즈업')
S('bong_nguoi_xuat_hien_phia_sau', ['P75'], 'A', True, 'Cảnh rộng', ['Kẻ Lang Thang'],
  f'Cảnh rộng ban đêm trên đường vành đai: phía sau chiếc xe dừng, vài Kẻ Lang Thang xiêu vẹo bắt đầu xuất hiện trên con đường tối giữa những chiếc xe bỏ lại. {BG["vanh_dai"]}',
  ['터벅터벅'], 'đàn zombie, bóng người, đường tối, xuất hiện', '좀비 떼, 그림자, 어두운 길, 나타나다')
S('nguoi_di_xieu_vao_dap_than_xe', ['P75'], 'B', True, 'Trung cảnh', ['Kẻ Lang Thang'],
  f'Một Kẻ Lang Thang đi xiêu vẹo đập tay vào thân xe bỏ hoang bên đường, tiếng kim loại vang lên, vài bóng khác phía sau cùng đi về một hướng. {BG["vanh_dai"]}', ['쾅!', '크르르'],
  'zombie, đập thân xe, đi xiêu vẹo', '좀비, 차체, 비틀거림')
S('ban_tay_taeho_truot_xuong_dao', ['P76'], 'A', True, 'Cận cảnh', ['Taeho'],
  'Cận cảnh bàn tay Taeho trượt xuống bên ghế, nắm chặt cán con dao găm, các khớp ngón tay trắng bệch, ánh đèn pha hắt qua kính.', ['철컥'],
  'taeho, bàn tay, con dao, bản năng', '태호, 손, 칼, 본능')
S('taeho_co_the_nhan_ra_nguy_hiem', ['P76'], 'B', True, 'Cận mặt', ['Taeho'],
  'Cận mặt Taeho, ánh mắt chuyển sang chế độ chiến đấu: tập trung, cơ hàm siết, mồ hôi nhỏ trên thái dương, đèn pha phản chiếu trong con ngươi.', None,
  'taeho, cận mặt, chiến đấu, bản năng', '태호, 클로즈업, 전투 태세, 본능')
S('nguoi_nhiem_cham_rai_ngang_dau', ['P77'], 'A', True, 'Cận cảnh qua kính', ['Kẻ Lang Thang'],
  'Qua kính xe nứt, người đàn ông bị nhiễm từ từ ngẩng đầu lên lần nữa, ánh mắt trắng đục nhìn thẳng vào Taeho, một bên kính đã vỡ thành nhiều vết rạn.', None,
  'người nhiễm, ngẩng đầu, kính nứt', '감염자, 고개를 들다, 금 간 유리')
S('bong_thu_hai_hien_ra', ['P78'], 'B', True, 'Cảnh rộng', ['Kẻ Lang Thang'],
  f'Phía sau người đàn ông nhiễm, một bóng người thứ hai bước ra từ bóng tối, rồi bóng thứ ba, xếp thành hàng không đều trên con đường vành đai tối. {BG["vanh_dai"]}', ['터벅터벅'],
  'bóng thứ hai, zombie, đàn, đường tối', '두 번째 그림자, 좀비, 떼, 어두운 길')
S('taeho_nhan_ra_su_that', ['P79'], 'A', True, 'Cận mặt', ['Taeho'],
  'Cận mặt Taeho, ánh mắt chuyển từ nghi ngờ sang nhận thức lạnh buốt, đồng tử co lại, ánh đèn pha xe phía sau hắt viền sáng quanh khuôn mặt.', None,
  'taeho, nhận ra, cận mặt, sững sờ', '태호, 깨닫다, 클로즈업, 충격')
S('dan_quai_tien_lai_toan_canh_ket_tap', ['P80'], 'A', True, 'Toàn cảnh kết tập', ['Kẻ Lang Thang'],
  f'Toàn cảnh kết tập: chiếc xe nhỏ của Taeho dừng giữa đường vành đai tối, phía trước và phía sau là hàng chục bóng Kẻ Lang Thang tiến lại từ mọi hướng, phía xa là ánh sáng thành phố mờ trong khói; không khí bị bao vây. {BG["vanh_dai"]}',
  ['터벅터벅', '크르르'], 'đàn zombie, bao vây, kết tập, toàn cảnh', '좀비 떼, 포위, 엔딩, 전경')

rows = []
for i, sh in enumerate(SHOTS, 1):
    fn = f'{i:03d}_{sh["slug"]}.png'
    tko_full = re.sub(r'(?<!이)민서','이민서',re.sub(r'(?<!백)다희','백다희',re.sub(r'(?<!강)태호','강태호',sh['tko'])))
    tags = ('ngay_tan, tap1, vi, ko, ' + ('tai_su_dung, ' if sh['reuse'] else 'rieng_tap1, ') + f'uutien_{sh["pri"]}, '
            + sh['tvi'] + ', ' + tko_full)
    rows.append((fn, tags, make_prompt(sh['shot'], sh['names'], sh['text'], sh['sfx'])))

OUT = os.path.join(D, 'ngay_tan_ep1_scenes_v3.csv')
with open(OUT, 'w', encoding='utf-8-sig', newline='') as f:
    w = csv.writer(f, lineterminator='\r\n')
    w.writerow(HDR)
    for i, (fn, tags, prompt) in enumerate(rows, 1):
        w.writerow([i, fn, tags, prompt])

# shot list md (đối chiếu với kịch bản Hàn)
ko = {}
for line in open(os.path.join(D, 'scripts', 'ko_ep1_check.txt'), encoding='utf-8'):
    k, t = line.rstrip('\n').split('|', 1)
    ko.setdefault(k.split('-')[0], []).append(t)
md = ['# Ngày Tàn — Tập 1: danh sách ảnh (shot list) đối chiếu kịch bản Hàn', '',
      f'{len(SHOTS)} ảnh, khoảng {600 // len(SHOTS)} giây/ảnh cho tập 10 phút. Ưu tiên: **A** bắt buộc, **B** nên có, **C** tuỳ chọn. '
      '"Tái dùng" = có thể dùng lại ở tập khác. Đoạn = mã đoạn trong `scripts/ko_ep1_check.txt` / `ep1_ko.md`.', '',
      '| STT | File | Đoạn | Câu đầu của đoạn (KO) | Ưu tiên | Tái dùng | Có chữ hiệu ứng |', '|---|---|---|---|---|---|---|']
for i, sh in enumerate(SHOTS, 1):
    first = ko[sh['pids'][0]][0]
    md.append(f'| {i} | {i:03d}_{sh["slug"]}.png | {", ".join(sh["pids"])} | {first} | {sh["pri"]} | {"có" if sh["reuse"] else "không"} | {"có" if sh["sfx"] else ""} |')
cnt = {p: sum(1 for s in SHOTS if s['pri'] == p) for p in 'ABC'}
md += ['', f'Tổng: A = {cnt["A"]}, B = {cnt["B"]}, C = {cnt["C"]}; tái dùng được: {sum(1 for s in SHOTS if s["reuse"])}.']
open(os.path.join(D, 'ngay_tan_ep1_shotlist.md'), 'w', encoding='utf-8', newline='\n').write('\n'.join(md) + '\n')

bad = set()
for fn, tags, prompt in rows:
    for ch in tags + prompt:
        o = ord(ch)
        if 0xAC00 <= o <= 0xD7A3 or o < 0x250 or 0x1E00 <= o <= 0x1EFF or ch in '“”‘’—…·–~':
            continue
        bad.add((ch, hex(o)))
cov = sorted({p for s in SHOTS for p in s['pids']})
allp = sorted(ko)
print(len(rows), 'rows; odd chars:', bad, '; A/B/C', cnt, '; uncovered paragraphs:', [p for p in allp if p not in cov])
