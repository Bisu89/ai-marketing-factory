"""Tập 2 (video dài 16:9): dựng ngay_tan_ep2_scenes_v3.csv + ngay_tan_ep2_shotlist.md + thư mục ngay_tan_ep2_images/.
Đoạn (P01..P57) = đoạn của scripts/ep2_audiobook_v3.txt theo thứ tự; bản dịch Hàn Tập 2 phải giữ đúng 57 đoạn này.
Chạy từ thư mục _tools/ (đóng file CSV nếu đang mở bằng Excel)."""
import csv
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import ngay_tan_blocks as B  # noqa: E402

D = HERE.parent
STYLE, RATIO, NEG = B.STYLE, B.RATIO, B.NEG
NEG_SFX = NEG.replace('chữ, logo, watermark', 'phụ đề, bóng thoại, mọi chữ khác ngoài chữ hiệu ứng đã chỉ định, logo, watermark')
HDR = ['STT', 'Ten file (filename.png)', 'Tags (dan khi import)', 'Prompt day du (copy nguyen vao ChatGPT)']

ROSTER = {
    'Taeho': 'KANG TAEHO (강태호)', 'Jiwoo': 'SEO JIWOO (서지우)', 'Yerin': 'HAN YERIN (한예린)',
    'Areum': 'SEO AREUM (서아름)',
}
ZOMBIES = {
    'Kẻ Lang Thang': 'KẺ LANG THANG (số 1 trong bảng)',
    'Thể Cuồng': 'THỂ CUỒNG (số 2 trong bảng)',
    'Dân Thường': 'KẺ LANG THANG biến thể số 11 DÂN THƯỜNG (người đàn ông mặc áo hoodie xám và quần jeans)',
    'Bác Sĩ': 'KẺ LANG THANG biến thể số 12 BÁC SĨ (áo blouse rách)',
    'Y Tá': 'KẺ LANG THANG biến thể số 13 Y TÁ (đồng phục y tá nhạt màu, người trưởng thành)',
    'Nhân Viên Văn Phòng': 'KẺ LANG THANG biến thể số 14 NHÂN VIÊN VĂN PHÒNG (áo sơ mi, cà vạt đỏ)',
    'Công Nhân': 'KẺ LANG THANG biến thể số 15 CÔNG NHÂN (mũ bảo hộ, áo phản quang)',
    'Nhân Viên Giao Hàng': 'KẺ LANG THANG biến thể số 16 NHÂN VIÊN GIAO HÀNG (áo đỏ, túi giao hàng)',
}
HORDE = ['Kẻ Lang Thang', 'Dân Thường', 'Nhân Viên Văn Phòng', 'Công Nhân', 'Bác Sĩ', 'Y Tá', 'Nhân Viên Giao Hàng']
HORDE_TXT = '(trộn các biến thể Dân Thường, Nhân Viên Văn Phòng, Công Nhân, Bác Sĩ, Y Tá, Nhân Viên Giao Hàng)'
# trang phục thay đổi so với bảng tổng hợp (chỉ mô tả cái thay đổi)
JW = 'áo sơ mi công sở màu sáng hơi rách, tóc rối, một vệt máu khô trên má và trên tay áo'
YR = 'có thêm một vệt máu trên tay áo, đeo balô'
BG2 = {
    'vanh_dai': B.BG['vanh_dai'],
    'duong': 'Phố nhỏ thành phố ban đêm, đèn đường vàng, xe bỏ hoang, khói mỏng, vài bóng người chạy xa xa.',
    'cong_truong': 'Cổng trường trung học ban đêm, cánh cổng sắt mở một nửa, sân trường tối, tòa nhà chính phía sau.',
    'sanh': 'Sảnh tòa nhà trường học ban đêm, cửa chính mở, ánh sáng đường hắt vào, chiếc giày lẻ và chiếc điện thoại vỡ màn hình trên sàn.',
    'hanh_lang': 'Hành lang tầng hai của trường học ban đêm, tối đen, đèn hành lang tắt, cánh cửa các lớp đóng.',
    'van_thu': 'Phòng văn thư nhỏ trong trường, bàn kéo chắn ngang cửa, vài chai nước, một túi xách.',
    'pho_dem': 'Đường phố thành phố ban đêm, một chiếc xe buýt nằm ngang giữa đường, cửa hàng tiện lợi bốc khói, đèn giao thông vẫn chuyển màu.',
    'bv_ngoai': 'Bên ngoài tòa nhà cấp cứu bệnh viện đại học ban đêm, đèn sáng trưng, xe cứu thương đỗ chồng lên nhau, cửa kính tự động mở đóng liên tục.',
    'cap_cuu': 'Khu cấp cứu bệnh viện hỗn loạn: người nằm trên cáng, người ngồi dưới sàn, nhân viên y tế chạy qua lại, đèn huỳnh quang trắng lạnh.',
    'mua_sam': 'Khu mua sắm bỏ hoang, tối om, cửa hàng đóng kín, cầu thang cuốn ngừng hoạt động.',
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
    parts += [STYLE, RATIO, NEG_SFX if sfx else NEG]
    return ' '.join(parts)


SHOTS = []


def S(slug, pids, pri, reuse, shot, names, text, sfx, tvi, tko):
    SHOTS.append(dict(slug=slug, pids=pids, pri=pri, reuse=reuse, shot=shot, names=names, text=text, sfx=sfx, tvi=tvi, tko=tko))


T = ['Taeho']
# ---- P01-P04: đường vành đai
S('taeho_roi_xe_vanh_dai', ['P01'], 'A', False, 'Cảnh rộng', T,
  f'Taeho đeo balô, tay cầm dao quân dụng, rời chiếc xe nứt kính bỏ lại trên đường vành đai ban đêm, bóng vài người đang tiến tới phía sau. {BG2["vanh_dai"]}', None,
  'taeho, bỏ xe, đường vành đai, đêm', '태호, 차를 버리다, 순환도로, 밤')
S('nguoi_nhiem_nam_yen_canh_xe_nut_kinh', ['P02'], 'B', True, 'Trung cảnh', ['Dân Thường'],
  f'Một Kẻ Lang Thang biến thể Dân Thường nằm bất động trên mặt đường cạnh chiếc xe nứt kính, phía sau là vài bóng người đang tiến lại gần. {BG2["vanh_dai"]}', None,
  'người nhiễm, nằm yên, xe nứt kính, bóng người', '감염자, 쓰러지다, 금 간 차, 그림자')
S('taeho_keo_khoa_ao_rut_dao', ['P02'], 'B', False, 'Cận cảnh', T,
  'Cận cảnh bàn tay Taeho kéo khóa áo khoác lên rồi rút con dao quân dụng ở bên hông, ánh đèn đường vàng cam hắt lên lưỡi dao.', ['철컥'],
  'taeho, kéo khóa, rút dao, cận cảnh', '태호, 지퍼, 칼을 뽑다, 클로즈업')
S('dong_xe_dung_yen_sedan_chan_ngang', ['P03'], 'A', True, 'Cảnh rộng', None,
  f'Dòng xe phía trước đứng yên hoàn toàn trên đường vành đai ban đêm, một chiếc sedan nằm chắn ngang hai làn đường, cửa xe mở toang. {BG2["vanh_dai"]}', None,
  'dòng xe, sedan chắn ngang, cửa mở, đường vành đai', '정체, 세단, 열린 문, 순환도로')
S('nguoi_dap_cua_kinh_taxi', ['P03'], 'A', True, 'Trung cảnh', ['Dân Thường'],
  f'Một Kẻ Lang Thang biến thể Dân Thường đập liên tục vào cửa kính một chiếc taxi như thể bên trong có thứ hắn không chịu buông. {BG2["vanh_dai"]}', ['쾅!', '쾅!'],
  'người nhiễm, đập cửa kính, taxi', '감염자, 유리를 두드리다, 택시')
S('tieng_coi_xe_nguoi_chay_nguoc_chieu', ['P03'], 'C', True, 'Cảnh rộng', None,
  f'Tiếng còi xe kéo dài chói tai, vài người chạy ngược chiều trên làn đường khẩn cấp giữa hàng xe đứng yên, đèn pha xe loang trong khói mỏng. {BG2["vanh_dai"]}', ['빵—'],
  'tiếng còi, người chạy, làn khẩn cấp', '경적, 도망치는 사람, 갓길')
S('nguoi_phu_nu_nga_hai_bong_chom_len', ['P03'], 'B', True, 'Cảnh bóng đen', ['Kẻ Lang Thang'],
  'Cảnh dạng bóng đen trên đường vành đai ban đêm: một người phụ nữ ngã xuống mặt đường, hai Kẻ Lang Thang lao tới chồm lên người cô; tiết chế, chỉ hình khối đen và ánh đèn xe, không chi tiết máu me.', ['꺄악!'],
  'người phụ nữ ngã, bóng đen, chồm lên', '쓰러진 여자, 실루엣, 덮치다')
S('taeho_khong_dung_lai', ['P04'], 'B', False, 'Cảnh sau lưng', T,
  f'Taeho chạy qua đoạn đường đầy xe bỏ lại, không ngoảnh nhìn lại, bóng anh đổ dài dưới đèn đường. {BG2["vanh_dai"]}', None,
  'taeho, không dừng lại, chạy', '태호, 멈추지 않다, 달리다')
# ---- P05-P06: vào phố
S('trung_tam_seoryeong_phia_truoc', ['P05'], 'B', True, 'Toàn cảnh', None,
  'Toàn cảnh trung tâm thành phố Seoryeong ban đêm nhìn từ xa: các tòa nhà sáng đèn, khói đen bốc lên ở vài chỗ, nhiều ánh đèn đỏ nhấp nháy.', None,
  'trung tâm seoryeong, toàn cảnh, khói, ban đêm', '서령 도심, 전경, 연기, 밤')
S('taeho_di_men_pho_nho', ['P05'], 'A', True, 'Trung cảnh', T,
  f'Taeho đi men theo con phố nhỏ, tránh giao lộ lớn, dáng thấp và cảnh giác. {BG2["duong"]}', None,
  'taeho, phố nhỏ, tránh giao lộ, cảnh giác', '태호, 골목, 교차로를 피하다, 경계')
S('anh_den_lam_ro_xe_bo_lai', ['P05'], 'C', True, 'Cảnh rộng', None,
  f'Ánh đèn thành phố không làm mọi thứ sáng hơn, chỉ làm hiện rõ những chiếc xe bỏ lại và vài người chạy tán loạn từng cái bóng một. {BG2["duong"]}', None,
  'ánh đèn, xe bỏ lại, người chạy tán loạn', '가로등, 버려진 차, 도망치는 사람들')
S('tieng_kinh_vo_cua_hang', ['P06'], 'B', True, 'Cảnh rộng', None,
  f'Một tiếng kính vỡ vang lên từ cửa hàng bên đường, những mảnh kính văng trên vỉa hè dưới đèn đường. {BG2["duong"]}', ['쨍그랑!'],
  'kính vỡ, cửa hàng, tiếng động', '유리 깨지는 소리, 가게, 소리')
S('taeho_dung_yen_dem_den_muoi', ['P06'], 'B', False, 'Cận mặt', T,
  'Cận mặt Taeho đứng yên giữa phố tối, mắt hướng về phía tiếng động, môi mím lại như đang đếm đến mười trong đầu và lắng nghe.', None,
  'taeho, đứng yên, lắng nghe, cận mặt', '태호, 가만히 서다, 귀를 기울이다, 클로즈업')
# ---- P07-P09: trường học
S('cong_truong_seoryeong_mo_mot_nua', ['P07'], 'A', False, 'Cảnh rộng', None,
  f'{BG2["cong_truong"]}', None,
  'cổng trường, trường trung học seoryeong, mở một nửa', '교문, 서령고등학교, 반쯤 열림')
S('taeho_nghe_tieng_goi_tu_toa_nha', ['P07'], 'B', False, 'Trung cảnh', T,
  f'Taeho định đi vòng qua cổng trường thì dừng lại, nghiêng đầu nghe một tiếng gọi rất khẽ từ tòa nhà. {BG2["cong_truong"]}', None,
  'taeho, nghe tiếng gọi, cổng trường', '태호, 부르는 소리, 교문')
S('toa_nha_chinh_tang_hai_cua_so_toi', ['P07'], 'B', False, 'Toàn cảnh', None,
  'Tòa nhà chính của trường trung học ban đêm nhìn từ sân: tầng hai có một ô cửa sổ khẽ lay động trong bóng tối, từ đó như có tiếng gọi yếu ớt vọng ra.', None,
  'tòa nhà chính, tầng hai, cửa sổ, tiếng gọi', '본관, 2층, 창문, 부르는 소리')
S('taeho_buoc_vao_san_truong', ['P08'], 'B', False, 'Cảnh sau lưng', T,
  f'Taeho bước vào sân trường tối, hướng về cửa chính của tòa nhà, chiếc dao quân dụng cầm thấp bên người. {BG2["cong_truong"]}', ['터벅터벅'],
  'taeho, vào sân trường', '태호, 운동장, 들어가다')
S('sanh_chinh_chiec_giay_le_loi', ['P09'], 'A', False, 'Cảnh rộng', None,
  f'{BG2["sanh"]} Không có người.', None,
  'sảnh, chiếc giày lẻ, điện thoại vỡ', '로비, 신발 한 짝, 깨진 휴대전화')
S('taeho_len_cau_thang_sat_tuong', ['P09'], 'B', False, 'Trung cảnh', T,
  'Taeho đi sát tường lên cầu thang của trường học tối, từng bậc một, đầu hơi nghiêng để lắng nghe, ánh đèn khẩn cấp xanh nhạt hắt lên.', None,
  'taeho, cầu thang, sát tường, lắng nghe', '태호, 계단, 벽에 붙다, 경청')
S('chieu_nghi_tang_hai_bong_nguoi_cuoi_hanh_lang', ['P10'], 'A', False, 'Cảnh rộng', ['Thể Cuồng'],
  f'Từ chiếu nghỉ tầng hai nhìn xuống cuối hành lang: THỂ CUỒNG, một người trưởng thành mặc bộ đồng phục nhân viên bảo vệ của trường, đứng quay lưng bất động giữa bóng tối. {BG2["hanh_lang"]}', None,
  'thể cuồng, cuối hành lang, quay lưng, đồng phục bảo vệ', '러너, 복도 끝, 뒷모습, 경비복')
S('taeho_nin_tho_dau_giat_nhe', ['P10'], 'C', False, 'Cận mặt', T,
  'Cận mặt Taeho nín thở, ánh mắt dán vào bóng người cuối hành lang, mồ hôi nhỏ trên thái dương.', None,
  'taeho, nín thở, cận mặt', '태호, 숨을 죽이다, 클로즈업')
S('taeho_lui_mot_buoc', ['P11'], 'B', False, 'Cận cảnh bàn chân', T,
  'Cận cảnh bàn chân Taeho lùi một bước trên nền gạch hành lang, đế ủng chạm nhẹ một mảnh vụn nhỏ khiến nó khẽ vang lên.', ['사각'],
  'bàn chân, lùi một bước, tiếng động nhỏ', '발, 한 걸음 물러서다, 작은 소리')
S('bong_nguoi_quay_phat_lai', ['P12'], 'A', True, 'Cận cảnh', ['Thể Cuồng'],
  f'THỂ CUỒNG (người trưởng thành mặc đồng phục nhân viên bảo vệ) quay phắt đầu lại, mắt mở to, miệng há ra, đồng tử trắng đục nhìn thẳng về phía người xem. {BG2["hanh_lang"]}', None,
  'thể cuồng, quay phắt lại, mắt mở to', '러너, 휙 돌아보다, 부릅뜬 눈')
S('the_cuong_lao_toi_hanh_lang', ['P12'], 'A', True, 'Cảnh rộng hành động', ['Thể Cuồng'],
  f'THỂ CUỒNG lao tới dọc hành lang tối với thân người chúi về trước, tứ chi co giật, nhanh hơn mọi thứ trước đó. {BG2["hanh_lang"]}', ['후다닥!'],
  'thể cuồng, lao tới, hành lang, tốc độ', '러너, 돌진, 복도, 속도')
S('taeho_ne_phai_hat_lech_vai', ['P13'], 'A', False, 'Cảnh hành động', ['Taeho', 'Thể Cuồng'],
  f'Taeho né sang phải khi THỂ CUỒNG vồ tới và dùng vai hất lệch hướng nó. {BG2["hanh_lang"]}', ['쿵!'],
  'taeho, né phải, hất lệch', '태호, 오른쪽으로 피하다, 어깨로 밀다')
S('quat_xuong_nen_hanh_lang', ['P13'], 'A', False, 'Cảnh hành động', ['Taeho', 'Thể Cuồng'],
  f'Taeho quật THỂ CUỒNG xuống nền gạch hành lang, bụi bay lên dưới ánh đèn khẩn cấp. {BG2["hanh_lang"]}', ['쾅!'],
  'taeho, quật xuống nền, hành lang', '태호, 바닥에 메치다, 복도')
S('canh_tay_quet_ngang_taeho_cui_xuong', ['P13'], 'B', False, 'Cận cảnh hành động', ['Taeho', 'Thể Cuồng'],
  'Cánh tay của THỂ CUỒNG quét ngang qua, Taeho cúi sát xuống và bàn tay nó sượt qua mái tóc anh trong gang tấc.', ['휙!'],
  'cánh tay quét ngang, cúi xuống, sượt qua tóc', '팔이 휩쓸다, 몸을 숙이다, 머리카락을 스치다')
S('taeho_ghim_vai_khoa_tay_dap_khuyu', ['P13'], 'A', False, 'Cận cảnh hành động', ['Taeho', 'Thể Cuồng'],
  'Taeho ghì vai THỂ CUỒNG xuống nền, khóa cánh tay rồi đập mạnh khuỷu tay vào cổ nó; tiết chế, không máu me, nhấn vào lực và sự kiên quyết.', ['퍽!'],
  'taeho, ghì vai, khóa tay, đập khuỷu', '태호, 어깨를 누르다, 팔을 꺾다, 팔꿈치')
S('co_the_ngung_chuyen_dong', ['P13'], 'C', False, 'Cận cảnh', ['Thể Cuồng'],
  'Bàn tay của THỂ CUỒNG buông lỏng trên nền gạch lạnh, cơ thể ngừng chuyển động hoàn toàn.', None,
  'bàn tay buông lỏng, ngừng chuyển động', '축 늘어진 손, 움직임이 멈추다')
S('chat_dich_den_loang_tren_nen_gach', ['P14'], 'B', True, 'Cận cảnh', None,
  'Cận cảnh một vũng chất dịch đen sẫm loãng loang trên nền gạch hành lang, phản chiếu ánh đèn khẩn cấp xanh nhạt; tông màu tối, không máu đỏ.', None,
  'chất dịch đen, nền gạch, cận cảnh', '검은 액체, 바닥, 클로즈업')
S('taeho_lau_tay_nhin_doc_hanh_lang', ['P15'], 'B', False, 'Trung cảnh', T,
  f'Taeho đứng dậy, lau tay vào quần và nhìn dọc hành lang tối yên ắng, vẻ mặt mệt mỏi nhưng cảnh giác. {BG2["hanh_lang"]}', None,
  'taeho, lau tay, nhìn dọc hành lang', '태호, 손을 닦다, 복도를 보다')
S('tieng_tham_sau_canh_cua', ['P16'], 'B', False, 'Cảnh rộng', None,
  f'Một cánh cửa phòng ở cuối hành lang khẽ hé ra, bóng tối bên trong; từ đó như có tiếng thì thầm yếu ớt vọng ra. {BG2["hanh_lang"]}', None,
  'cánh cửa hé, tiếng thì thầm, hành lang', '살짝 열린 문, 속삭임, 복도')
# ---- P17-P22: Jiwoo
S('canh_cua_van_thu_mo_he', ['P17'], 'A', False, 'Trung cảnh', None,
  f'Cánh cửa phòng văn thư mở hé, một khe sáng nhỏ hắt ra từ bên trong. {BG2["van_thu"]}', None,
  'cửa phòng văn thư, mở hé, khe sáng', '문서실 문, 살짝 열림, 빛')
S('jiwoo_cam_keo_chi_ve_phia_taeho', ['P17'], 'A', False, 'Trung cảnh', ['Jiwoo'],
  f'Jiwoo đứng sau cánh cửa hé, hai tay nắm chặt một cây kéo với mũi kéo chĩa ra ngoài, ánh mắt sợ hãi nhưng quyết liệt; {JW}.', None,
  'jiwoo, cây kéo, chĩa ra, sợ hãi', '서지우, 가위, 겨누다, 두려움')
S('jiwoo_nhin_xac_duoi_chan_taeho', ['P17'], 'B', False, 'Góc nhìn qua vai', ['Jiwoo', 'Taeho', 'Thể Cuồng'],
  f'Qua vai Jiwoo: cô nhìn xuống THỂ CUỒNG nằm bất động dưới chân Taeho rồi nhìn lên Taeho; {JW}.', None,
  'jiwoo, nhìn xác, taeho, qua vai', '서지우, 시체를 보다, 태호, 어깨 너머')
S('jiwoo_ha_keo_xuong', ['P17'], 'B', False, 'Cận cảnh', ['Jiwoo'],
  f'Cận cảnh hai tay Jiwoo từ từ hạ cây kéo xuống, đôi vai thả lỏng một chút; {JW}.', None,
  'jiwoo, hạ kéo, thả lỏng', '서지우, 가위를 내리다, 긴장을 풀다')
S('jiwoo_thu_nhan_tuong_taeho_cung_bien_thanh', ['P17'], 'C', False, 'Cận mặt', ['Jiwoo'],
  f'Cận mặt Jiwoo, ánh mắt nhẹ nhõm xen xấu hổ khi thú nhận cô tưởng anh cũng đã biến thành thứ kia; {JW}.', None,
  'jiwoo, nhẹ nhõm, xấu hổ, cận mặt', '서지우, 안도, 부끄러움, 클로즈업')
S('jiwoo_tu_gioi_thieu_mo_cua_rong_hon', ['P18'], 'B', False, 'Trung cảnh', ['Jiwoo', 'Taeho'],
  f'Jiwoo mở cửa rộng thêm và tự giới thiệu mình, Taeho đứng đối diện cất dao xuống thấp; {JW}. {BG2["van_thu"]}', None,
  'jiwoo, taeho, tự giới thiệu, mở cửa', '서지우, 태호, 자기소개, 문을 열다')
S('can_phong_van_thu_ban_chan_cua', ['P19'], 'A', False, 'Cảnh rộng', None,
  f'{BG2["van_thu"]} Ba chiếc điện thoại xếp cạnh nhau trên bàn; không có người trong khung hình.', None,
  'phòng văn thư, bàn chắn cửa, chai nước, balô', '문서실, 책상 바리케이드, 생수, 가방')
S('ba_chiec_dien_thoai_canh_nhau', ['P19'], 'B', False, 'Cận cảnh', None,
  'Cận cảnh ba chiếc điện thoại xếp cạnh nhau trên mặt bàn gỗ, màn hình tối, một chiếc nứt kính, ánh đèn bàn vàng nhạt.', None,
  'ba chiếc điện thoại, mặt bàn, cận cảnh', '휴대전화 세 대, 책상, 클로즈업')
S('jiwoo_khong_noi_da_song_sot_bang_cach_nao', ['P19'], 'C', False, 'Cận mặt', ['Jiwoo'],
  f'Cận mặt Jiwoo ngồi tựa tường trong phòng văn thư, ánh mắt xa xăm, không kể mình đã sống sót ra sao; {JW}.', None,
  'jiwoo, ngồi tựa tường, ánh mắt xa xăm', '서지우, 벽에 기대다, 먼 눈빛')
S('jiwoo_nhat_dien_thoai_bam_goi', ['P20'], 'A', False, 'Trung cảnh', ['Jiwoo'],
  f'Jiwoo cúi nhặt một chiếc điện thoại và bấm gọi, ánh sáng nhạt của màn hình hắt lên mặt cô; {JW}.', None,
  'jiwoo, nhặt điện thoại, bấm gọi', '서지우, 휴대전화, 전화를 걸다')
S('man_hinh_dien_thoai_khong_co_tin_hieu', ['P20'], 'B', True, 'Cận cảnh', None,
  'Cận cảnh màn hình điện thoại hiển thị không có tín hiệu (không chữ, chỉ biểu tượng vạch sóng trống), ánh sáng lạnh.', None,
  'màn hình điện thoại, không tín hiệu, vạch sóng', '휴대전화 화면, 신호 없음, 안테나')
S('jiwoo_khan_giong_nhac_em_gai', ['P20'], 'B', False, 'Cận mặt', ['Jiwoo'],
  f'Cận mặt Jiwoo, giọng như nghẹn lại khi nhắc đến em gái, mắt ánh lên nước nhưng cô kìm lại; {JW}.', None,
  'jiwoo, nhắc em gái, nghẹn lại, cận mặt', '서지우, 동생, 목이 메다, 클로즈업')
S('trung_tam_cung_quoc_gia_ky_uc', ['P20'], 'C', False, 'Cảnh rộng', None,
  f'{BG2["cung"]} Cảnh dạng hồi tưởng nhẹ, tông màu ấm hơn, không có người.', None,
  'trung tâm bắn cung, phía đông, hồi tưởng', '양궁 센터, 동쪽, 회상')
S('taeho_nhin_dong_ho_gan_muoi_gio', ['P21'], 'B', False, 'Cận cảnh', T,
  'Cận cảnh cổ tay Taeho xem đồng hồ, kim chỉ gần mười giờ đêm, ánh sáng nhạt từ ô cửa sổ hắt vào.', None,
  'taeho, đồng hồ, gần mười giờ', '태호, 시계, 열 시 가까이')
S('taeho_quyet_dinh_nhan_jiwoo_di_cung', ['P21'], 'B', False, 'Trung cảnh', ['Taeho', 'Jiwoo'],
  f'Taeho và Jiwoo đứng đối diện nhau trong hành lang tối, Taeho khẽ gật đầu như đã quyết định để cô đi cùng; {JW}. {BG2["hanh_lang"]}', None,
  'taeho, jiwoo, đi cùng, quyết định', '태호, 서지우, 동행, 결정')
S('jiwoo_khoac_balo_nhin_ra_hanh_lang', ['P22'], 'B', False, 'Trung cảnh', ['Jiwoo'],
  f'Jiwoo kéo chiếc balô dưới bàn ra, khoác lên vai và nhìn ra hành lang tối; {JW}.', None,
  'jiwoo, khoác balô, nhìn hành lang', '서지우, 배낭을 메다, 복도')
S('hai_nguoi_roi_phong_van_thu', ['P22'], 'C', False, 'Cảnh rộng', ['Taeho', 'Jiwoo'],
  f'Taeho và Jiwoo cùng bước ra khỏi phòng văn thư, đi sát nhau dọc hành lang tối về phía cầu thang; {JW}. {BG2["hanh_lang"]}', ['터벅터벅'],
  'taeho, jiwoo, rời phòng, hành lang', '태호, 서지우, 방을 나서다, 복도')
S('roi_truong_bang_cua_sau', ['P23'], 'B', False, 'Cảnh rộng', ['Taeho', 'Jiwoo'],
  f'Taeho và Jiwoo rời trường bằng cửa sau, hai bóng người nhỏ trong sân sau tối của trường; {JW}.', None,
  'rời trường, cửa sau, taeho, jiwoo', '학교를 떠나다, 후문, 태호, 서지우')
# ---- P24-P28: phố
S('pho_ben_ngoai_xe_buyt_nam_ngang', ['P24'], 'A', True, 'Cảnh rộng', None,
  f'{BG2["pho_dem"]} Không có người.', None,
  'xe buýt nằm ngang, phố, đèn giao thông', '버스, 가로막다, 거리, 신호등')
S('cua_hang_tien_loi_boc_khoi', ['P24'], 'A', True, 'Cảnh rộng', None,
  'Một cửa hàng tiện lợi đang bốc khói ban đêm, biển hiệu nhấp nháy, vài món hàng vương vãi trên vỉa hè phía trước.', None,
  'cửa hàng tiện lợi, bốc khói, ban đêm', '편의점, 연기, 밤')
S('den_giao_thong_van_chuyen_mau', ['P24'], 'B', True, 'Cận cảnh', None,
  'Cận cảnh đèn giao thông vẫn chuyển màu đều đặn dù hầu như không còn chiếc xe nào chạy qua, nền phố tối mờ phía sau.', None,
  'đèn giao thông, chuyển màu, phố vắng', '신호등, 색이 바뀌다, 텅 빈 거리')
S('jiwoo_di_sat_phia_sau_taeho', ['P24'], 'B', False, 'Trung cảnh', ['Taeho', 'Jiwoo'],
  f'Jiwoo đi sát phía sau Taeho dọc con phố đầy xe bỏ lại, mắt liếc nhìn mỗi khi có tiếng động; {JW}. {BG2["pho_dem"]}', None,
  'jiwoo, đi sát sau taeho, phố vắng', '서지우, 태호 뒤를 따르다, 빈 거리')
S('jiwoo_nhin_ve_huong_co_tieng_dong', ['P24'], 'C', False, 'Cận mặt', ['Jiwoo'],
  f'Cận mặt Jiwoo ngoái nhìn về hướng vừa có tiếng động, ánh mắt cảnh giác; {JW}.', None,
  'jiwoo, ngoái nhìn, tiếng động', '서지우, 뒤돌아보다, 소리')
S('jiwoo_chi_tay_ve_khu_dan_cu', ['P25'], 'B', False, 'Trung cảnh', ['Jiwoo', 'Taeho'],
  f'Jiwoo chỉ tay về phía khu dân cư phía trước, Taeho nhìn theo hướng tay cô; {JW}. {BG2["duong"]}', None,
  'jiwoo, chỉ tay, khu dân cư, bệnh viện', '서지우, 손가락으로 가리키다, 주택가, 병원')
S('con_duong_qua_khu_dan_cu_toi_benh_vien', ['P25'], 'B', True, 'Cảnh rộng', None,
  'Con đường xuyên qua khu dân cư tối dẫn về phía ánh đèn của bệnh viện đại học ở xa, cửa sổ các căn nhà đều tối.', None,
  'khu dân cư, bệnh viện, ánh đèn xa', '주택가, 병원, 먼 불빛')
S('taeho_ghi_nho_tung_cho_co_chi', ['P25'], 'C', False, 'Cận mặt', T,
  'Cận mặt Taeho gật nhẹ và quét mắt ghi nhớ từng điểm Jiwoo vừa chỉ, như đang vẽ bản đồ trong đầu.', None,
  'taeho, ghi nhớ, bản đồ trong đầu', '태호, 기억하다, 머릿속 지도')
S('tieng_coi_xe_bat_ngo_ben_trai', ['P26'], 'B', True, 'Cảnh rộng', None,
  f'Một tiếng còi xe bất ngờ vang lên từ phía bên trái con phố tối, ánh đèn pha xa xa nhấp nháy. {BG2["duong"]}', ['빵!'],
  'tiếng còi bất ngờ, phố tối, đèn pha', '갑작스러운 경적, 어두운 거리, 헤드라이트')
S('jiwoo_giat_minh_taeho_keo_vao_bong_toi', ['P27'], 'A', False, 'Trung cảnh', ['Taeho', 'Jiwoo'],
  f'Jiwoo giật mình, Taeho kéo cô né vào khoảng tối giữa hai tòa nhà; {JW}. {BG2["duong"]}', None,
  'jiwoo, taeho, né vào bóng tối, kéo', '서지우, 태호, 그림자 속으로, 끌어당기다')
S('ba_bong_nguoi_chay_qua_dau_pho', ['P27'], 'A', True, 'Cảnh rộng', ['Kẻ Lang Thang'],
  f'Ba Kẻ Lang Thang chạy qua đầu phố, lê bước và chúi người về phía trước như bị kéo bởi một sợi dây vô hình. {BG2["duong"]}', ['터벅터벅'],
  'ba kẻ lang thang, đầu phố, lê bước', '워커 세 마리, 골목 어귀, 비틀거리다')
S('mot_con_quay_dau_ve_phia_ho', ['P27'], 'A', True, 'Cận cảnh', ['Kẻ Lang Thang'],
  'Một Kẻ Lang Thang ngoái đầu về phía bóng tối nơi Taeho và Jiwoo nấp, mắt trắng đục, mũi như đang ngửi trong không khí.', ['크르르'],
  'kẻ lang thang, quay đầu, ngửi', '워커, 고개를 돌리다, 냄새를 맡다')
S('taeho_giu_jiwoo_dung_yen', ['P27'], 'B', False, 'Cận cảnh', ['Taeho', 'Jiwoo'],
  f'Taeho đặt tay chặn nhẹ trước người Jiwoo giữ cô đứng yên trong bóng tối, hai người nín thở; {JW}.', None,
  'taeho, giữ jiwoo, đứng yên, nín thở', '태호, 서지우를 붙잡다, 숨죽이다')
S('ba_con_di_theo_tieng_coi', ['P27'], 'B', True, 'Cảnh rộng', ['Kẻ Lang Thang'],
  f'Ba Kẻ Lang Thang quay đi, tiếp tục theo tiếng còi đang vang bên kia đường và khuất dần. {BG2["duong"]}', None,
  'kẻ lang thang, đi theo tiếng còi, khuất dần', '워커, 경적을 따라가다, 멀어지다')
S('jiwoo_tho_ra_cham_chung_phan_ung_am_thanh', ['P28'], 'C', False, 'Cận mặt', ['Jiwoo'],
  f'Cận mặt Jiwoo thở ra thật chậm, vai chùng xuống sau khi bầy zombie đi khuất; {JW}.', None,
  'jiwoo, thở ra, sau khi thoát', '서지우, 숨을 내쉬다, 위기를 넘기다')
S('vet_mau_tren_tay_ao_jiwoo', ['P28'], 'A', False, 'Cận cảnh', ['Jiwoo'],
  'Cận cảnh vệt máu khô trên tay áo sơ mi của Jiwoo dưới ánh đèn đường mờ.', None,
  'vết máu, tay áo, jiwoo, cận cảnh', '핏자국, 소매, 서지우, 클로즈업')
S('jiwoo_lay_tay_che_vet_mau', ['P28'], 'B', False, 'Cận cảnh', ['Jiwoo'],
  'Cận cảnh tay Jiwoo vội vàng che vệt máu trên tay áo còn lại, ánh mắt hiểu ra điều Taeho vừa nói.', None,
  'jiwoo, che vết máu, hiểu ra', '서지우, 핏자국을 가리다, 깨닫다')
# ---- P29-P42: bệnh viện
S('den_benh_vien_dai_hoc_seoryeong', ['P29'], 'A', True, 'Cảnh rộng', ['Taeho', 'Jiwoo'],
  f'Taeho và Jiwoo vòng qua khu dân cư và đến trước cổng bệnh viện đại học Seoryeong, tòa nhà lớn sáng đèn giữa đêm; {JW}.', None,
  'bệnh viện đại học seoryeong, cổng bệnh viện', '서령대학교병원, 병원 입구')
S('toa_nha_cap_cuu_sang_truong_khong_nguoi_huong_dan', ['P30'], 'A', True, 'Cảnh rộng', None,
  f'{BG2["bv_ngoai"]} Không có người hướng dẫn.', None,
  'tòa nhà cấp cứu, sáng trưng, không người hướng dẫn', '응급실 건물, 환한 불빛, 안내 없음')
S('xe_cuu_thuong_do_chong_len_nhau', ['P30'], 'B', True, 'Trung cảnh', None,
  'Những chiếc xe cứu thương đỗ chồng lên nhau trước cửa cấp cứu, đèn xoay đỏ nhấp nháy, cửa xe mở, không có người.', ['삐뽀삐뽀'],
  'xe cứu thương, đỗ chồng lên nhau, đèn xoay', '구급차, 겹쳐 주차, 경광등')
S('cua_kinh_tu_dong_mo_dong_lien_tuc', ['P30'], 'B', True, 'Cận cảnh', None,
  'Cánh cửa kính tự động của khu cấp cứu mở ra rồi đóng lại liên tục như không ai biết cách dừng nó, ánh sáng trắng tràn ra.', None,
  'cửa kính tự động, mở đóng liên tục', '자동문, 계속 열렸다 닫히다')
S('ben_trong_cap_cuu_hon_loan', ['P30'], 'A', True, 'Cảnh rộng', None,
  f'{BG2["cap_cuu"]}', None,
  'khu cấp cứu, hỗn loạn, cáng, nhân viên y tế', '응급실, 혼란, 들것, 의료진')
S('tieng_khoc_o_khu_tiep_nhan', ['P30'], 'C', True, 'Cảnh rộng', None,
  'Khu tiếp nhận bệnh viện hỗn loạn: một người trưởng thành ngồi dưới sàn ôm mặt khóc, xung quanh nhân viên y tế chạy qua lại.', None,
  'khu tiếp nhận, tiếng khóc, ngồi dưới sàn', '접수처, 우는 소리, 바닥에 앉다')
S('yerin_day_cang_quat_dung_dung_giua_loi', ['P31'], 'A', False, 'Trung cảnh', ['Yerin'],
  f'Yerin đẩy một chiếc cáng về phía phòng cấp cứu, quát người đứng giữa lối, khuôn mặt căng thẳng nhưng tỉnh táo; {YR}. {BG2["cap_cuu"]}', None,
  'yerin, đẩy cáng, quát, bác sĩ cấp cứu', '한예린, 들것을 밀다, 소리치다, 응급의')
S('yerin_goi_y_ta_dua_benh_nhan_so_bay_xuong_kho_thuoc', ['P31'], 'B', False, 'Trung cảnh', ['Yerin'],
  f'Yerin quay sang một y tá và ra lệnh đưa bệnh nhân số bảy xuống kho thuốc, tránh xa khu chờ, ánh mắt dứt khoát; {YR}.', None,
  'yerin, ra lệnh, bệnh nhân số bảy, kho thuốc', '한예린, 지시하다, 7번 환자, 약품 창고')
S('taeho_va_jiwoo_dung_gan_cua_vao', ['P31'], 'B', False, 'Cảnh rộng', ['Taeho', 'Jiwoo'],
  f'Taeho và Jiwoo vừa bước qua cửa kính vào khu cấp cứu hỗn loạn, đứng khựng giữa dòng người; {JW}.', None,
  'taeho, jiwoo, bước vào cấp cứu', '태호, 서지우, 응급실로 들어가다')
S('yerin_kiem_tra_nguoi_dang_co_giat_tren_cang', ['P32'], 'A', False, 'Trung cảnh', ['Yerin', 'Dân Thường'],
  f'Yerin cúi xuống kiểm tra một người đàn ông (biến thể Dân Thường, còn là người, đang bắt đầu biến đổi) co giật trên cáng, Taeho và Jiwoo đứng dạt sang một bên; {YR}. {BG2["cap_cuu"]}', None,
  'yerin, kiểm tra bệnh nhân, co giật, cáng', '한예린, 환자를 살피다, 경련, 들것')
S('ong_ta_dot_ngot_bat_day', ['P33'], 'A', True, 'Cận cảnh', ['Dân Thường'],
  f'Người đàn ông trên cáng đột ngột bật dậy, đôi mắt trắng đục mở to, miệng há ra. {BG2["cap_cuu"]}', ['쾅!'],
  'bệnh nhân bật dậy, mắt trắng đục', '환자가 벌떡 일어나다, 흰 눈')
S('y_ta_het_len_ong_ta_chom_toi', ['P34'], 'A', True, 'Cảnh hành động', ['Dân Thường'],
  f'Một y tá hét lên, người đàn ông vừa biến đổi chồm tới phía cô; xung quanh bệnh nhân hoảng loạn né ra. {BG2["cap_cuu"]}', ['꺄악!'],
  'y tá hét, chồm tới, hoảng loạn', '간호사 비명, 덮치다, 아수라장')
S('yerin_keo_khay_kim_loai_chan_giua', ['P34'], 'A', False, 'Cảnh hành động', ['Yerin', 'Dân Thường'],
  f'Yerin kéo chiếc khay kim loại chắn giữa người đàn ông biến đổi và y tá, quát mọi người lùi lại; {YR}.', ['쨍그랑!'],
  'yerin, khay kim loại, chắn giữa, lùi lại', '한예린, 금속 쟁반, 막아서다, 물러서')
S('ong_ta_dap_manh_vao_khay', ['P34'], 'B', True, 'Cận cảnh', ['Dân Thường'],
  'Người đàn ông biến đổi đập mạnh hai tay vào chiếc khay kim loại, khay rung lên và móp lại.', ['쾅!'],
  'đập vào khay, kim loại, móp', '쟁반을 내리치다, 금속, 찌그러짐')
S('yerin_day_cang_sang_ngang_cho_y_ta_thoat', ['P34'], 'B', False, 'Trung cảnh', ['Yerin'],
  f'Yerin không bỏ chạy mà đẩy chiếc cáng sang ngang để y tá phía sau thoát ra, rồi kéo một bệnh nhân khác khỏi khu vực nguy hiểm; {YR}.', None,
  'yerin, đẩy cáng sang ngang, cứu y tá', '한예린, 들것을 옆으로 밀다, 간호사를 구하다')
S('taeho_lao_toi_danh_vao_vai_day_nga', ['P35'], 'A', False, 'Cảnh hành động', ['Taeho', 'Dân Thường'],
  f'Taeho lao tới, đánh vào vai người đàn ông biến đổi khiến hắn mất thăng bằng rồi đẩy ngã xuống nền. {BG2["cap_cuu"]}', ['쿵!'],
  'taeho, lao tới, đánh vào vai, đẩy ngã', '태호, 달려들다, 어깨를 치다, 밀어 넘어뜨리다')
S('yerin_keo_cua_phong_cap_cuu_dong_lai', ['P35'], 'B', False, 'Trung cảnh', ['Yerin'],
  f'Yerin lập tức kéo cánh cửa phòng cấp cứu đóng lại và ra lệnh khóa, một y tá xoay chốt; {YR}.', ['탁!'],
  'yerin, đóng cửa phòng cấp cứu, khóa', '한예린, 응급실 문을 닫다, 잠그다')
S('yerin_cui_tho_doc_gioi_thieu', ['P36'], 'B', False, 'Cận mặt', ['Yerin'],
  f'Yerin cúi xuống thở dốc rồi ngẩng lên giới thiệu mình là bác sĩ cấp cứu, bàn tay vẫn kiểm tra cánh tay người y tá vừa được cứu; {YR}.', None,
  'yerin, thở dốc, giới thiệu, bác sĩ cấp cứu', '한예린, 숨을 헐떡이다, 자기소개, 응급의')
S('jiwoo_hoi_nhung_nguoi_con_lai', ['P37'], 'C', False, 'Cận mặt', ['Jiwoo'],
  f'Cận mặt Jiwoo nhìn quanh khu cấp cứu và hỏi về những người còn lại, giọng run nhẹ; {JW}.', None,
  'jiwoo, hỏi, những người còn lại', '서지우, 묻다, 남은 사람들')
S('yerin_mo_ngan_tu_lay_bang_gac', ['P37'], 'B', False, 'Cận cảnh', ['Yerin'],
  'Cận cảnh bàn tay Yerin mở một ngăn tủ y tế, lấy thêm cuộn băng gạc và nhét vào balô.', None,
  'yerin, ngăn tủ, băng gạc, balô', '한예린, 서랍, 붕대, 배낭')
S('khong_du_nguoi_khong_du_thuoc', ['P37'], 'B', True, 'Cảnh rộng', None,
  'Tủ thuốc và giá vật tư y tế gần như trống rỗng trong khu cấp cứu, vài hộp thuốc rơi trên sàn, ánh đèn huỳnh quang nhấp nháy.', None,
  'tủ thuốc trống, thiếu thuốc, thiếu người', '빈 약장, 약 부족, 인력 부족')
S('yerin_lay_dien_thoai_khong_tin_hieu', ['P38'], 'B', False, 'Cận cảnh', ['Yerin'],
  f'Yerin lấy điện thoại ra, màn hình không có tín hiệu, ngón tay cô dừng lại trên màn hình; {YR}.', None,
  'yerin, điện thoại, không tín hiệu', '한예린, 휴대전화, 신호 없음')
S('yerin_ke_ve_nguoi_ban_o_cheonma', ['P38'], 'B', False, 'Cận mặt', ['Yerin'],
  f'Cận mặt Yerin kể về người bạn làm ở viện Cheonma đã gọi cho cô trước khi mạng chập chờn, ánh mắt lo lắng; {YR}.', None,
  'yerin, người bạn cheonma, lo lắng', '한예린, 천마 친구, 걱정')
S('taeho_giu_ve_mat_binh_thuong_khi_nghe_cheonma', ['P38'], 'A', False, 'Cận mặt', T,
  'Cận mặt Taeho nghe thấy cái tên Cheonma, gương mặt vẫn bình thản nhưng cơ hàm khẽ siết lại, ánh mắt tối đi trong thoáng chốc.', None,
  'taeho, cheonma, giữ vẻ bình thường, cận mặt', '태호, 천마, 표정을 숨기다, 클로즈업')
S('yerin_nhin_dong_ho_nhin_ra_cua_kinh', ['P39'], 'B', False, 'Trung cảnh', ['Yerin'],
  f'Yerin nhìn đồng hồ rồi nhìn ra cửa kính, ngoài hành lang tối bắt đầu có bóng người; {YR}.', None,
  'yerin, nhìn đồng hồ, cửa kính', '한예린, 시계를 보다, 유리문')
S('tieng_chan_ngay_cang_nhieu_ngoai_cua_kinh', ['P39'], 'B', True, 'Cảnh rộng', None,
  'Ngoài hành lang bệnh viện, qua tấm kính mờ, nhiều bóng người đang lê bước về phía cửa phòng cấp cứu, tiếng chân vọng lại.', ['터벅터벅'],
  'tiếng chân, hành lang bệnh viện, bóng người', '발소리, 병원 복도, 그림자')
S('yerin_muon_di_ve_phia_dong_tim_nguoi_ban', ['P40'], 'B', False, 'Trung cảnh', ['Yerin', 'Taeho', 'Jiwoo'],
  f'Yerin đóng balô và nói cô muốn đi về phía đông để tìm người bạn, Taeho và Jiwoo nghe cô nói; {YR}. {BG2["cap_cuu"]}', None,
  'yerin, đi về phía đông, tìm người bạn', '한예린, 동쪽으로 가다, 친구를 찾다')
S('tieng_dap_manh_ngoai_cua', ['P41'], 'A', True, 'Cận cảnh', None,
  'Cánh cửa phòng cấp cứu rung lên từng đợt vì những cú đập mạnh từ bên ngoài, ổ khóa kêu lên.', ['쾅!', '쾅!'],
  'tiếng đập cửa, phòng cấp cứu, rung', '문을 두드리다, 응급실, 진동')
S('yerin_tat_den_khu_cap_cuu_boi_canh_toi', ['P41'], 'A', False, 'Trung cảnh', ['Yerin', 'Taeho', 'Jiwoo'],
  f'Yerin tắt đèn khu cấp cứu, căn phòng chìm vào bóng tối, ba người đứng sát nhau nhìn về phía cửa; {YR}.', ['탁'],
  'yerin, tắt đèn, bóng tối, ba người', '한예린, 불을 끄다, 어둠, 세 사람')
S('taeho_nghi_viec_di_mot_minh_va_ba_nguoi_chung_dich_den', ['P42'], 'B', False, 'Cảnh rộng', ['Taeho', 'Jiwoo', 'Yerin'],
  f'Trong bóng tối của khu cấp cứu, Taeho nhìn Jiwoo và Yerin, trầm tư; ba người chuẩn bị rời đi cùng nhau; {JW}; Yerin {YR}.', None,
  'taeho, ba người, cùng đích đến, quyết định', '태호, 세 사람, 같은 목적지, 결정')
# ---- P43-P50: khu mua sắm, hầm xe
S('roi_benh_vien_bang_cua_phu', ['P43'], 'B', False, 'Cảnh rộng', ['Taeho', 'Jiwoo', 'Yerin'],
  f'Taeho, Jiwoo và Yerin rời bệnh viện bằng cửa phụ, ba bóng người lướt dọc bức tường phía sau tòa nhà; {JW}; Yerin {YR}.', None,
  'rời bệnh viện, cửa phụ, ba người', '병원을 떠나다, 쪽문, 세 사람')
S('duong_sau_benh_vien_hai_xe_tai_chan_giao_lo', ['P44'], 'A', True, 'Cảnh rộng', None,
  'Con đường phía sau bệnh viện ban đêm, hai chiếc xe tải nằm chắn ngang giao lộ, phía sau là hàng chục bóng người đang di chuyển trong bóng tối.', None,
  'hai xe tải, chắn giao lộ, hàng chục bóng người', '트럭 두 대, 교차로 막다, 수십 명')
S('hang_chuc_bong_nguoi_phia_sau_xe_tai', ['P44'], 'A', True, 'Cảnh rộng', HORDE,
  f'Hàng chục Kẻ Lang Thang {HORDE_TXT} lê bước phía sau hai chiếc xe tải chắn ngang, bóng chúng đổ dài dưới ánh đèn đường mờ.', ['터벅터벅', '크르르'],
  'đàn kẻ lang thang, xe tải, đường chính bị chặn', '워커 떼, 트럭, 큰길이 막히다')
S('taeho_keo_hai_nguoi_dung_lai', ['P44'], 'B', False, 'Trung cảnh sau lưng', ['Taeho', 'Jiwoo', 'Yerin'],
  f'Taeho kéo Jiwoo và Yerin dừng lại sau góc tường, giơ tay ra hiệu không đi qua lối đó; {JW}; Yerin {YR}.', None,
  'taeho, kéo hai người dừng lại, không đi qua', '태호, 두 사람을 멈추게 하다, 지나가지 마')
S('jiwoo_chi_loi_duoi_cau_thang_cuon', ['P45'], 'A', False, 'Trung cảnh', ['Jiwoo'],
  f'Jiwoo chỉ về phía lối dưới cầu thang cuốn trong tòa nhà bên phải, giải thích đây là lối cô thường đi ra bãi xe phía sau; {JW}.', None,
  'jiwoo, chỉ lối, dưới cầu thang cuốn', '서지우, 길을 가리키다, 에스컬레이터 아래')
S('cua_hang_dong_kin_khu_mua_sam_toi_om', ['P45'], 'B', True, 'Cảnh rộng', None,
  f'{BG2["mua_sam"]} Không có người.', None,
  'khu mua sắm, tối om, cửa hàng đóng kín', '쇼핑몰, 칠흑, 닫힌 가게')
S('cua_ky_thuat_jiwoo_mo_khoa_chia_cu', ['P45'], 'A', False, 'Cận cảnh', ['Jiwoo'],
  'Cận cảnh bàn tay Jiwoo cắm chiếc chìa khóa cũ vào ổ khóa cửa kỹ thuật dưới gầm cầu thang cuốn, ánh đèn pin nhỏ hắt lên.', ['철컥'],
  'jiwoo, chìa khóa cũ, cửa kỹ thuật, ổ khóa', '서지우, 낡은 열쇠, 기술실 문, 자물쇠')
S('cau_thang_xuong_mui_am_mui_xang', ['P46'], 'B', True, 'Trung cảnh', None,
  'Cánh cửa kỹ thuật mở ra một cầu thang bê tông đi xuống bóng tối, hơi ẩm bốc lên, ánh đèn khẩn cấp đỏ mờ ở dưới đáy.', None,
  'cầu thang đi xuống, mùi ẩm, mùi xăng', '아래로 내려가는 계단, 습기, 휘발유 냄새')
S('thu_tu_di_taeho_yerin_jiwoo', ['P46'], 'C', False, 'Cảnh sau lưng', ['Taeho', 'Yerin', 'Jiwoo'],
  f'Ba người đi xuống cầu thang theo thứ tự: Taeho đi đầu, Yerin ở giữa, Jiwoo đi sau cùng; {JW}; Yerin {YR}.', None,
  'taeho đi đầu, yerin ở giữa, jiwoo sau cùng', '태호가 앞장, 한예린 중간, 서지우 마지막')
S('ham_gui_xe_den_khan_cap_nhap_nhay', ['P47'], 'A', True, 'Cảnh rộng', None,
  f'{BG2["ham_xe"]} Không có người.', None,
  'hầm gửi xe, đèn khẩn cấp, xe bỏ lại', '지하주차장, 비상등, 버려진 차')
S('canh_cua_xe_dang_mo_khong_ai_ben_trong', ['P47'], 'B', True, 'Cận cảnh', None,
  'Một cánh cửa xe đang mở trong hầm gửi xe tối, bên trong ghế trống và chiếc áo khoác bỏ lại, ánh đèn khẩn cấp nhấp nháy.', None,
  'cửa xe đang mở, không ai bên trong, hầm xe', '열린 차 문, 아무도 없음, 주차장')
S('taeho_gio_tay_hieu_dung_nghe_tieng_dong_cuoi_ham', ['P47'], 'A', False, 'Trung cảnh', ['Taeho'],
  f'Taeho giơ tay ra hiệu dừng, nghiêng đầu nghe một âm thanh rất khẽ từ phía cuối hầm. {BG2["ham_xe"]}', None,
  'taeho, giơ tay ra hiệu dừng, âm thanh cuối hầm', '태호, 정지 신호, 주차장 끝의 소리')
S('yerin_cui_thap_jiwoo_nam_chat_quai_balo', ['P47'], 'B', False, 'Cảnh sau lưng', ['Yerin', 'Jiwoo'],
  f'Yerin cúi thấp người nấp sau một chiếc xe, Jiwoo nắm chặt quai balô đứng cạnh cô, cả hai im lặng chờ; {JW}; Yerin {YR}.', None,
  'yerin, jiwoo, nấp sau xe, chờ', '한예린, 서지우, 차 뒤에 숨다, 기다리다')
S('tieng_kim_loai_va_nhau_roi_im_lang', ['P47'], 'B', True, 'Cảnh rộng', None,
  f'Một tiếng kim loại va vào nhau vang lên ở cuối hầm gửi xe tối rồi im bặt, một chiếc thùng sắt khẽ lăn trên nền. {BG2["ham_xe"]}', ['쨍!'],
  'tiếng kim loại va nhau, im lặng, cuối hầm', '쇠 부딪히는 소리, 정적, 주차장 끝')
S('taeho_kiem_tra_tung_khoang_giua_cac_xe', ['P48'], 'B', False, 'Trung cảnh', ['Taeho'],
  f'Taeho đi trước vài bước, kiểm tra từng khoảng giữa các xe, dao cầm thấp, ánh mắt quét kỹ từng góc tối. {BG2["ham_xe"]}', None,
  'taeho, kiểm tra giữa các xe, hầm xe', '태호, 차 사이를 살피다, 주차장')
S('xe_tai_nho_con_chia_khoa_tren_o', ['P49'], 'B', False, 'Cận cảnh', None,
  'Cận cảnh một chiếc xe tải nhỏ trong hầm gửi xe với chìa khóa vẫn cắm trên ổ, ánh đèn khẩn cấp hắt lên bảng điều khiển.', None,
  'xe tải nhỏ, chìa khóa trên ổ, bảng điều khiển', '소형 트럭, 꽂힌 열쇠, 계기판')
S('dong_co_khong_no_binh_nhien_lieu_can', ['P49'], 'B', False, 'Cận cảnh', T,
  'Cận cảnh bàn tay Taeho vặn chìa khóa mà động cơ không nổ, kim đồng hồ nhiên liệu nằm im ở vạch cạn, vẻ mặt thất vọng thoáng qua.', ['끼릭끼릭'],
  'taeho, động cơ không nổ, nhiên liệu cạn', '태호, 시동이 안 걸리다, 연료 바닥')
S('roi_ham_len_loi_phia_sau_gan_nua_dem', ['P50'], 'B', False, 'Cảnh rộng', ['Taeho', 'Jiwoo', 'Yerin'],
  f'Ba người rời hầm bằng lối phía sau khu mua sắm, bước ra con phố yên tĩnh hơn gần nửa đêm; {JW}; Yerin {YR}. {BG2["duong"]}', None,
  'rời hầm, lối phía sau, gần nửa đêm', '지하에서 나오다, 뒷길, 자정 무렵')
S('anh_den_trung_tam_cung_o_cuoi_duong', ['P50'], 'A', True, 'Cảnh rộng', None,
  f'Ở cuối con đường vắng, ánh đèn của trung tâm bắn cung hiện ra, tòa nhà vòm lớn nổi lên trong đêm. {BG2["cung"]}', None,
  'ánh đèn trung tâm bắn cung, cuối con đường', '양궁 센터 불빛, 길 끝')
# ---- P51-P57: kết
S('jiwoo_goi_khong_ai_nghe', ['P51'], 'B', False, 'Trung cảnh', ['Jiwoo'],
  f'Jiwoo lấy điện thoại gọi, áp lên tai, ánh mắt chờ đợi nhưng không ai nghe máy; {JW}.', None,
  'jiwoo, gọi điện, không ai nghe', '서지우, 전화를 걸다, 받지 않음')
S('jiwoo_goi_lai_khong_phan_hoi_goi_ten_em', ['P51'], 'C', False, 'Cận mặt', ['Jiwoo'],
  f'Cận mặt Jiwoo gọi lại lần nữa, rồi nhìn tòa nhà phía trước và khẽ gọi tên em gái, không có tiếng đáp; {JW}.', None,
  'jiwoo, gọi lại, gọi tên em, không đáp', '서지우, 다시 걸다, 동생 이름, 대답 없음')
S('yerin_nguoc_nhin_mai_nha', ['P52'], 'B', False, 'Trung cảnh', ['Yerin'],
  f'Yerin ngước nhìn lên mái tòa nhà vòm, nói tòa nhà có người; {YR}. {BG2["cung"]}', None,
  'yerin, ngước nhìn mái nhà, có người', '한예린, 지붕을 올려다보다, 사람이 있다')
S('bong_nguoi_dung_tren_mai_nha_vom', ['P52'], 'A', True, 'Cảnh rộng', None,
  f'Một bóng người nhỏ đứng trên đỉnh mái nhà vòm của trung tâm bắn cung, in lên nền trăng. {BG2["cung"]}', None,
  'bóng người trên mái, nhà vòm, ánh trăng', '지붕 위 그림자, 돔, 달빛')
S('bong_nguoi_buoc_ra_khoi_vung_toi_areum', ['P53'], 'A', False, 'Cảnh rộng', ['Areum'],
  f'Areum bước ra khỏi vùng tối trên mái nhà vòm, tóc bện dài buông qua vai, tay cầm cây cung thể thao, đứng thẳng dưới ánh đèn đường. {BG2["cung"]}', None,
  'areum, bước ra khỏi vùng tối, mái nhà, cây cung', '서아름, 어둠에서 나오다, 지붕, 활')
S('jiwoo_tien_len_goi_ten_em', ['P53'], 'A', False, 'Trung cảnh', ['Jiwoo', 'Taeho', 'Yerin'],
  f'Jiwoo tiến lên nửa bước, ngẩng nhìn lên mái nhà và gọi tên em, Taeho đưa tay ngăn cô tiến thêm, Yerin đứng phía sau; {JW}; Yerin {YR}.', None,
  'jiwoo, gọi tên em, taeho ngăn lại', '서지우, 동생을 부르다, 태호가 막다')
S('areum_nang_cay_cung_dat_mui_ten_vao_day', ['P54'], 'A', False, 'Trung cảnh góc thấp', ['Areum'],
  f'Nhìn từ dưới lên: Areum từ từ nâng cây cung lên và đặt một mũi tên vào dây, ánh mắt không rời mục tiêu phía dưới. {BG2["cung"]}', None,
  'areum, nâng cung, đặt mũi tên vào dây', '서아름, 활을 들다, 화살을 걸다')
S('taeho_buoc_chan_truoc_jiwoo', ['P55'], 'A', False, 'Trung cảnh', ['Taeho', 'Jiwoo', 'Yerin'],
  f'Taeho bước chắn trước Jiwoo, Yerin lùi sang bên, ba người đứng dưới chân tòa nhà vòm chưa đến ba mươi mét; {JW}; Yerin {YR}.', None,
  'taeho, chắn trước jiwoo, yerin lùi sang bên', '태호, 서지우 앞을 막다, 한예린이 물러서다')
S('areum_keo_day_cung_can_canh', ['P55'], 'A', False, 'Cận cảnh', ['Areum'],
  'Cận cảnh Areum kéo dây cung căng hết cỡ, mắt nheo lại ngắm xuống, đôi vai và cánh tay vững như đá.', None,
  'areum, kéo dây cung, ngắm', '서아름, 시위를 당기다, 조준')
S('mui_ten_huong_thang_xuong_cho_ho_dung', ['P55'], 'A', True, 'Cận cảnh góc nhìn từ dưới', None,
  'Dưới ánh đèn đường, đầu mũi tên kim loại chĩa thẳng xuống người xem, dây cung căng hết cỡ ở phía sau.', None,
  'mũi tên chĩa xuống, đầu mũi tên, dây cung căng', '화살이 아래를 겨누다, 화살촉, 팽팽한 시위')
S('ngon_tay_buong_day_cung', ['P56'], 'A', False, 'Cực cận', ['Areum'],
  'Cực cận ngón tay Areum buông dây cung, dây rung lên và đầu ngón tay trượt khỏi dây.', ['핑!'],
  'areum, ngón tay buông dây, cực cận', '서아름, 시위를 놓다, 클로즈업')
S('mui_ten_lao_xuong', ['P57'], 'A', True, 'Cận cảnh hành động', None,
  'Mũi tên lao xuống từ mái nhà vòm trong đêm, đuôi mũi tên rung và vệt sáng nhỏ kéo dài theo ánh đèn đường, hướng thẳng vào khung hình.', ['슈웅!'],
  'mũi tên lao xuống, từ mái nhà, hành động', '화살이 날아오다, 지붕에서, 액션')

# ---- ghi file
rows = []
for i, sh in enumerate(SHOTS, 1):
    fn = f'{i:03d}_{sh["slug"]}.png'
    tags = ('ngay_tan, tap2, vi, ko, ' + ('tai_su_dung, ' if sh['reuse'] else 'rieng_tap2, ') + f'uutien_{sh["pri"]}, '
            + sh['tvi'] + ', ' + sh['tko'])
    rows.append((fn, tags, make_prompt(sh['shot'], sh['names'], sh['text'], sh['sfx'])))

with open(D / 'ngay_tan_ep2_scenes_v3.csv', 'w', encoding='utf-8-sig', newline='') as f:
    w = csv.writer(f, lineterminator='\r\n')
    w.writerow(HDR)
    for i, (fn, tags, prompt) in enumerate(rows, 1):
        w.writerow([i, fn, tags, prompt])

vi_text = (D / 'scripts' / 'ep2_audiobook_v3.txt').read_text(encoding='utf-8')
body = vi_text[vi_text.index('## TRUYỆN') + 9:vi_text.index('## KẾT')]
paras = [p.strip() for p in re.split(r'\n\s*\n', body) if p.strip() and not p.strip().startswith('##')]
first = {f'P{i:02d}': p.split('. ')[0][:70] for i, p in enumerate(paras, 1)}

md = ['# Ngày Tàn — Tập 2: danh sách ảnh (shot list) đối chiếu lời đọc', '',
      f'{len(SHOTS)} ảnh, khoảng {int(660 / len(SHOTS))} giây/ảnh. Ưu tiên: **A** bắt buộc, **B** nên có, **C** tuỳ chọn. "Tái dùng" = dùng lại được ở tập khác. '
      'Đoạn = đoạn của `scripts/ep2_audiobook_v3.txt` (57 đoạn theo thứ tự; bản Hàn phải giữ đúng 57 đoạn này).', '',
      '| STT | File | Đoạn | Câu đầu của đoạn (VI) | Ưu tiên | Tái dùng | Có chữ hiệu ứng |', '|---|---|---|---|---|---|---|']
for i, sh in enumerate(SHOTS, 1):
    md.append(f'| {i} | {i:03d}_{sh["slug"]}.png | {", ".join(sh["pids"])} | {first.get(sh["pids"][0], "")} | {sh["pri"]} | {"có" if sh["reuse"] else "không"} | {"có" if sh["sfx"] else ""} |')
cnt = {p: sum(1 for s in SHOTS if s['pri'] == p) for p in 'ABC'}
md += ['', f'Tổng: A = {cnt["A"]}, B = {cnt["B"]}, C = {cnt["C"]}; tái dùng được: {sum(1 for s in SHOTS if s["reuse"])}; có chữ hiệu ứng: {sum(1 for s in SHOTS if s["sfx"])}.']
(D / 'ngay_tan_ep2_shotlist.md').write_text('\n'.join(md) + '\n', encoding='utf-8', newline='\n')

img_dir = D / 'ngay_tan_ep2_images'
img_dir.mkdir(exist_ok=True)
(img_dir / '.gitkeep').write_text('')
(img_dir / '_DANH_SACH_TEN_FILE.txt').write_text(
    'Ảnh Tập 2 (video dài 16:9) - lưu ảnh vào thư mục này với ĐÚNG tên file dưới đây (theo ngay_tan_ep2_scenes_v3.csv).\n\n'
    + '\n'.join(fn for fn, _, _ in rows) + '\n', encoding='utf-8', newline='\n')

bad = set()
for fn, tags, prompt in rows:
    for ch in tags + prompt:
        o = ord(ch)
        if 0xAC00 <= o <= 0xD7A3 or o < 0x250 or 0x1E00 <= o <= 0x1EFF or ch in '“”‘’—…·–~':
            continue
        bad.add((ch, hex(o)))
cov = sorted({p for s in SHOTS for p in s['pids']})
miss = [p for p in first if p not in cov]
print(len(rows), 'ảnh; ký tự lạ:', bad, '; A/B/C', cnt, '; đoạn chưa có ảnh:', miss, '; max len', max(len(r[2]) for r in rows))
