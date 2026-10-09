"""Tập 3 (video dài 16:9): dựng ngay_tan_ep3_scenes_v3.csv + ngay_tan_ep3_shotlist.md + thư mục ngay_tan_ep3_images/.
Đoạn (P001..P224) = đoạn của scripts/ko_ep3_check.txt (bản Hàn là bản gốc). Chạy từ thư mục _tools/ (đóng CSV nếu đang mở bằng Excel)."""
import csv
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
    'Areum': 'SEO AREUM (서아름)', 'Minseo': 'LEE MINSEO (이민서)',
}
ZOMBIES = {
    'Kẻ Lang Thang': 'KẺ LANG THANG (số 1 trong bảng)',
    'Thể Cuồng': 'THỂ CUỒNG (số 2 trong bảng)',
    'Kẻ Hú': 'KẺ HÚ (số 3 trong bảng)',
    'Thể Phình': 'THỂ PHÌNH (số 4 trong bảng)',
    'Giao Hàng': 'KẺ LANG THANG biến thể số 16 NHÂN VIÊN GIAO HÀNG (áo đỏ, túi giao hàng)',
}
# trạng thái trang phục thay đổi so với bảng tổng hợp (chỉ mô tả cái thay đổi)
JW = 'áo sơ mi công sở màu sáng hơi rách, tóc rối, một vệt máu khô trên má và trên tay áo'
JWS = JW + ', mắt cá chân được nẹp bằng hai thanh nhôm và quấn băng trắng'
YR = 'có thêm một vệt máu trên tay áo, đeo balô và túi y tế'
OH = 'ông Oh, dược sĩ trung niên khoảng năm mươi tuổi, tóc muối tiêu, đeo kính, mặc áo blouse trắng'
IN = 'cô thực tập sinh hai mươi bốn tuổi, tóc buộc đuôi ngựa, mặc đồng phục y tá nhạt màu, một bên tay bị trầy'
CO = 'người giao hàng nam trưởng thành mặc áo khoác đỏ, đeo túi giao hàng'
BG3 = {
    'cung': 'Trung tâm huấn luyện bắn cung quốc gia ban đêm: tòa nhà vòm lớn, tường kính cao, sân tập, đèn đường vàng, ánh trăng.',
    'pho_dem': 'Phố thành phố ban đêm, đèn đường chập chờn, xe bỏ lại nằm chắn ngang, vài ngọn lửa âm ỉ trong các tòa nhà ven đường.',
    'rao': 'Hàng rào lưới thép cao giữa sân tập và con đường phía sau trung tâm bắn cung, ban đêm, đèn đường vàng, nền bê tông.',
    'bai_xe': 'Bãi xe phía sau trung tâm bắn cung ban đêm, đèn đường vàng, vài chiếc xe đậu rời rạc.',
    'ngatu': 'Ngã tư thành phố ban đêm, xe va chạm nằm chắn các làn, đèn tín hiệu chập chờn, khói mỏng, các con hẻm tối hai bên.',
    'hem': 'Con hẻm hẹp tối phía sau khu y tế, thùng rác đổ, ống thoát nước, đèn đường xa mờ.',
    'yte': 'Khu y tế quận bốn tầng (kiểu cũ) ban đêm, mặt tiền tối, cửa kính đóng, xe cứu thương bỏ trước cửa.',
    'kho': 'Lối vào kho thuốc phía sau khu y tế: cửa sắt hé mở, hành lang tối, ánh đèn khẩn cấp xanh nhạt.',
    'cau_thang': 'Cầu thang bê tông của khu y tế ban đêm, ánh đèn khẩn cấp xanh nhạt, tay vịn sắt, tường loang ẩm.',
    'hanh_lang4': 'Hành lang tầng bốn khu y tế, đèn khẩn cấp đỏ chập chờn, sàn gạch cũ, cửa các phòng đóng.',
    'thuoc': 'Phòng thuốc lớn: các kệ thuốc cao, tủ kính, ánh đèn khẩn cấp ấm, chiếc tủ kim loại dựng sát cửa.',
    'thuong': 'Sân thượng khu y tế ban đêm, gió mạnh, lan can thấp, bãi đáp trực thăng sơn vòng tròn, toàn cảnh thành phố Seoryeong với khói và vài đám cháy nhỏ.',
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


T, J, Y, A = ['Taeho'], ['Jiwoo'], ['Yerin'], ['Areum']
# ---- P001-P007: mũi tên cứu Taeho, Areum xuất hiện
S('mui_ten_xuyen_dau_the_cuong', ['P001', 'P002'], 'A', False, 'Cảnh rộng hành động', ['Taeho', 'Thể Cuồng'],
  f'Một mũi tên xuyên qua đầu THỂ CUỒNG (người trưởng thành mặc đồng phục nhân viên bảo vệ) đang lao tới từ phía sau lưng Taeho, đầu mũi tên chỉ cách gáy Taeho một gang tay. {BG3["pho_dem"]}', ['퍽!'],
  'mũi tên, xuyên đầu, thể cuồng, cứu taeho', '화살, 머리를 꿰뚫다, 광폭체, 태호를 구하다')
S('taeho_quay_nguoi_rut_dao', ['P003'], 'B', False, 'Trung cảnh', ['Taeho'],
  f'Taeho quay phắt người lại, tay rút con dao quân dụng, nhìn xuống nền bê tông dưới ánh đèn đường chập chờn. {BG3["pho_dem"]}', None,
  'taeho, quay người, rút dao', '태호, 몸을 돌리다, 칼을 뽑다')
S('the_cuong_do_xuong_chat_dich_den', ['P003'], 'A', False, 'Cận cảnh', ['Thể Cuồng'],
  'THỂ CUỒNG (người trưởng thành mặc đồng phục nhân viên bảo vệ) nằm trên nền bê tông, tứ chi co giật vài nhịp rồi bất động, đuôi mũi tên còn rung nhẹ, chất dịch đen sẫm loãng loang dưới ánh đèn đường chập chờn.', None,
  'thể cuồng, co giật, chất dịch đen', '광폭체, 경련, 검은 액체')
S('taeho_khong_nghe_thay_tieng', ['P004'], 'C', False, 'Cận mặt', T,
  'Cận mặt Taeho sững lại, ánh mắt chợt nhận ra mình đã không hề nghe thấy tiếng nó tới gần.', None,
  'taeho, không nghe thấy, cận mặt', '태호, 듣지 못하다, 클로즈업')
S('cung_thu_tren_mai_hien_doi_dien', ['P005', 'P006'], 'A', False, 'Cảnh rộng', A,
  f'Một bóng cung thủ (Areum) đứng trên mái hiên đối diện, cây cung thể thao trong tay, bóng đen rõ nét dưới ánh trăng; cô đã phát hiện ra mối nguy từ trước. {BG3["pho_dem"]}', None,
  'areum, mái hiên, cung thủ, bóng', '서아름, 처마, 궁수, 실루엣')
S('areum_nhay_xuong_lap_ten_tiep', ['P006'], 'A', False, 'Cảnh hành động', A,
  'Areum nhảy xuống từ mái hiên, tiếp đất vững vàng rồi lập tức đặt mũi tên tiếp theo lên dây cung, tóc bện dài tung theo.', ['휙!'],
  'areum, nhảy xuống, lắp mũi tên', '서아름, 뛰어내리다, 화살을 걸다')
S('mui_ten_chia_thang_vao_nguc_taeho', ['P006'], 'A', True, 'Góc nhìn từ Taeho', ['Areum'],
  'Góc nhìn từ phía Taeho: Areum kéo cung, đầu mũi tên kim loại chĩa thẳng vào ngực người xem, ánh mắt cô lạnh và cảnh giác.', None,
  'mũi tên chĩa vào ngực, areum, góc nhìn', '화살이 가슴을 겨누다, 서아름, 시점')
S('areum_goi_ten_ban_dau', ['P007'], 'B', False, 'Cận mặt', A,
  'Cận mặt Areum, mắt hổ phách sắc lạnh, mái tóc nâu tro bện một bím dài, gương mặt căng thẳng dưới ánh đèn đường.', None,
  'areum, cận mặt, ánh mắt sắc', '서아름, 클로즈업, 날카로운 눈')
# ---- P008-P017: Jiwoo chắn, Taeho đặt dao
S('jiwoo_chan_giua_taeho_va_areum', ['P008'], 'A', False, 'Trung cảnh', ['Jiwoo', 'Taeho', 'Areum'],
  f'Jiwoo vội bước lên chắn giữa Taeho và Areum, hai tay giơ nhẹ ra hai bên, quay lưng về phía Taeho và đối mặt với mũi tên của em gái; {JW}.', None,
  'jiwoo, chắn giữa, areum, taeho', '서지우, 가로막다, 서아름, 강태호')
S('jiwoo_noi_ha_cung_xuong', ['P009'], 'B', False, 'Cận mặt', J,
  f'Cận mặt Jiwoo cố giữ bình tĩnh, môi mấp máy nói với em gái, ánh mắt van nài; {JW}.', None,
  'jiwoo, cận mặt, ha cung xuống', '서지우, 클로즈업, 활을 내려')
S('areum_nhin_con_dao_roi_len_mat', ['P010'], 'B', False, 'Cận cảnh', ['Areum', 'Taeho'],
  'Ánh mắt Areum dừng ở con dao quân dụng trong tay Taeho rồi chuyển lên khuôn mặt anh; cung vẫn giương.', None,
  'areum, ánh mắt, con dao, nghi ngờ', '서아름, 시선, 칼, 의심')
S('taeho_cam_dao_khong_hoang_loan', ['P011'], 'C', False, 'Trung cảnh', T,
  f'Taeho đứng yên với con dao quân dụng cầm thấp, vẻ mặt bình tĩnh khác thường giữa thành phố hỗn loạn. {BG3["pho_dem"]}', None,
  'taeho, bình tĩnh, cầm dao', '태호, 침착함, 칼')
S('taeho_dat_dao_xuong_dat_gio_tay', ['P012'], 'A', False, 'Cận cảnh', T,
  'Taeho từ từ đặt con dao quân dụng xuống nền bê tông, lùi một bước, hai tay giơ lên mở ra; bàn tay cận cảnh.', None,
  'taeho, đặt dao xuống, giơ tay, lùi lại', '태호, 칼을 내려놓다, 두 손을 들다')
S('day_cung_chung_xuong_tung_chut', ['P012'], 'B', False, 'Cận cảnh', A,
  'Cận cảnh dây cung của Areum chùng xuống từng chút một, mũi tên từ từ hạ thấp.', None,
  'dây cung chùng, areum, hạ mũi tên', '시위가 느슨해지다, 서아름, 화살을 내리다')
S('areum_giu_khoang_cach_goi_anh_linh', ['P013', 'P014', 'P015'], 'B', False, 'Trung cảnh', ['Areum', 'Taeho'],
  f'Areum hạ cung nhưng đứng cách xa Taeho một khoảng, ánh mắt đầy cảnh giác, môi như đang nói "anh lính" bằng giọng mỉa; Taeho đứng yên, dao nằm dưới đất. {BG3["pho_dem"]}', None,
  'areum, giữ khoảng cách, anh lính', '서아름, 거리를 두다, 군인 아저씨')
S('taeho_im_lang_khong_giai_thich', ['P016'], 'C', False, 'Cận mặt', T,
  'Cận mặt Taeho im lặng, ánh mắt nặng trĩu nhìn Areum, không giải thích gì về quá khứ của mình.', None,
  'taeho, im lặng, quá khứ', '태호, 침묵, 과거')
# ---- P017-P019: Yerin nhận ra Areum
S('yerin_kham_xac_the_cuong', ['P017'], 'B', False, 'Trung cảnh', ['Yerin', 'Thể Cuồng'],
  f'Yerin ({YR}) quỳ một gối kiểm tra thân xác THỂ CUỒNG nằm bất động trên nền bê tông, tay đeo găng, ánh đèn đường chập chờn.', None,
  'yerin, kiểm tra xác, thể cuồng', '한예린, 시체를 살피다, 광폭체')
S('yerin_ngang_len_nhan_ra_areum', ['P017'], 'B', False, 'Cận mặt', Y,
  f'Cận mặt Yerin ngẩng lên nhìn Areum, vẻ mặt đổi khác khi nhận ra người quen; Yerin {YR}.', None,
  'yerin, nhận ra, areum', '한예린, 알아보다, 서아름')
S('hoi_tuong_tap_huan_daejeon_yerin_kham_vai', ['P018'], 'A', True, 'Cảnh hồi tưởng', ['Yerin', 'Areum'],
  'Cảnh hồi tưởng sáng màu, nét mềm hơn: trong phòng y tế của trại tập huấn thể thao ở Daejeon, Yerin (áo blouse trắng sạch, ống nghe) đang khám vai cho Areum (áo thể thao đen, ngồi trên giường khám), cả hai còn trẻ trung thoải mái.', None,
  'hồi tưởng, daejeon, yerin khám vai, areum', '회상, 대전, 어깨 진료, 합숙 훈련')
S('areum_ha_hang_cung_khong_tin_hoan_toan', ['P019'], 'B', False, 'Trung cảnh', ['Areum', 'Yerin'],
  f'Areum hạ hẳn cây cung xuống, nhìn Yerin nhưng vẫn chưa hoàn toàn tin; Yerin {YR} đứng cạnh Jiwoo ({JW}). {BG3["pho_dem"]}', None,
  'areum, hạ cung, yerin, không tin hẳn', '서아름, 활을 내리다, 한예린')
# ---- P020-P025: Areum kể chuyện
S('areum_ke_chuyen_tai_trung_tam', ['P020', 'P021'], 'B', False, 'Trung cảnh', ['Areum', 'Taeho', 'Jiwoo', 'Yerin'],
  f'Areum đứng kể với giọng đều đều, bốn người đứng quanh trên sân trước trung tâm bắn cung; Taeho khoanh tay lắng nghe, Yerin {YR}, Jiwoo ({JW}). {BG3["cung"]}', None,
  'areum kể chuyện, bốn người, trung tâm bắn cung', '서아름, 이야기하다, 네 사람, 양궁 센터')
S('phong_thay_do_dong_doi_nga_guc', ['P021'], 'A', True, 'Cảnh hồi tưởng', None,
  'Cảnh hồi tưởng trong phòng thay đồ của trung tâm bắn cung: một thành viên đội (người trưởng thành, áo thể thao) ngã gục giữa các dãy tủ khóa, những người khác đứng khựng lại hoảng hốt; tiết chế, không máu me.', None,
  'phòng thay đồ, đồng đội ngã, trung tâm', '탈의실, 팀원이 쓰러지다, 센터')
S('dong_doi_dung_day_lao_vao_nguoi_con_lai', ['P021'], 'A', True, 'Cảnh bóng đen', ['Thể Cuồng'],
  'Cảnh dạng bóng đen trong phòng thay đồ: một người trong đội đã biến đổi đứng dậy và lao vào những người còn lại, bóng đen lớn trên tường, ánh đèn trần nhấp nháy; tiết chế.', ['꺄악!'],
  'đồng đội biến đổi, lao vào, bóng đen', '팀원 변이, 덮치다, 실루엣')
S('areum_chay_vao_kho_dung_cu_khoa_cua', ['P022'], 'A', False, 'Cảnh hành động', A,
  'Areum lao vào kho dụng cụ và khóa trái cánh cửa sắt từ bên trong, lưng tì vào cửa, ống tên đeo lưng, thở gấp.', ['철컥'],
  'areum, kho dụng cụ, khóa cửa', '서아름, 장비 창고, 문을 잠그다')
S('tieng_dap_cua_ngoai_kho_dan_im_bat', ['P022'], 'B', False, 'Cận cảnh', A,
  'Cận cảnh Areum ngồi sát tường trong kho tối, tai áp vào cánh cửa sắt rung lên bởi tiếng đập bên ngoài, tiếng đập thưa dần rồi im hẳn.', ['쿵…쿵…'],
  'areum, tiếng đập cửa, im bặt', '서아름, 문 두드리는 소리, 멎다')
S('areum_buoc_ra_trung_tam_khong_con_an_toan', ['P023'], 'C', False, 'Cảnh rộng', A,
  f'Areum bước ra khỏi kho, nhìn quanh hành lang trung tâm bắn cung hoang tàn, đồ đạc đổ ngổn ngang, cô đứng lẻ loi. {BG3["cung"]}', None,
  'areum, trung tâm không an toàn, hoang tàn', '서아름, 안전하지 않은 센터, 폐허')
S('ong_ten_16_mui_cua_areum', ['P024'], 'A', False, 'Cận cảnh', A,
  'Cận cảnh ống tên đeo lưng của Areum, bàn tay cô kéo ra để lộ đúng mười sáu mũi tên, tông tối, ánh đèn đường hắt lên đuôi tên.', None,
  'ống tên, mười sáu mũi tên, areum', '화살통, 열여섯 발, 서아름')
S('areum_noi_con_so_binh_than', ['P025'], 'B', False, 'Cận mặt', A,
  'Cận mặt Areum nói con số ấy rất bình thản, nhưng ánh mắt lộ rõ rằng đó là toàn bộ khả năng tự vệ của cô.', None,
  'areum, bình thản, con số', '서아름, 담담함, 숫자')
S('taeho_hieu_y_nghia_con_so', ['P025'], 'C', False, 'Cận mặt', T,
  'Cận mặt Taeho nhìn Areum với ánh mắt thấu hiểu về ý nghĩa của con số mười sáu.', None,
  'taeho, thấu hiểu', '태호, 이해하다')
# ---- P026-P035: rời trung tâm, hàng rào, Jiwoo ngã
S('khong_the_o_lai_bon_nguoi_nhin_quanh', ['P026'], 'B', False, 'Cảnh rộng', ['Taeho', 'Jiwoo', 'Yerin', 'Areum'],
  f'Bốn người đứng trên sân trước trung tâm bắn cung nhìn quanh đầy bất an, nhận ra không thể ở lại; Taeho dẫn đầu, Yerin {YR}, Jiwoo ({JW}), Areum đeo cung. {BG3["cung"]}', None,
  'bốn người, không thể ở lại, trung tâm', '네 사람, 더 머물 수 없다, 센터')
S('taeho_nhin_ve_phia_nam_muc_tieu', ['P027'], 'B', False, 'Cận mặt', T,
  'Cận mặt Taeho nhìn về phía nam thành phố, mục tiêu của anh vẫn là rời khỏi đây, ánh đèn xa phản chiếu trong mắt.', None,
  'taeho, phía nam, mục tiêu', '태호, 남쪽, 목적')
S('cong_sau_bi_chan_khong_mo_duoc', ['P028', 'P029'], 'B', False, 'Trung cảnh', ['Taeho'],
  f'Taeho đẩy cánh cổng sau của trung tâm bắn cung nhưng nó bị vật gì đó chặn từ bên ngoài, không mở được, ánh đèn đường lọt qua khe hở. {BG3["bai_xe"]}', None,
  'cổng sau bị chặn, taeho', '뒷문이 막히다, 태호')
S('hang_rao_luoi_cao_chan_loi_ra', ['P029'], 'A', True, 'Cảnh rộng', None,
  f'{BG3["rao"]} Hàng rào cao hơn đầu người, không có ai.', None,
  'hàng rào lưới, cao, chắn lối', '철망 울타리, 높다, 길을 막다')
S('areum_vuot_rao_truoc_yerin_theo_sau', ['P030'], 'B', False, 'Cảnh hành động', ['Areum', 'Yerin'],
  f'Areum nhẹ nhàng trèo qua hàng rào lưới, Yerin ({YR}) bám theo phía sau, cả hai leo thoăn thoắt. {BG3["rao"]}', None,
  'areum, yerin, trèo rào', '서아름, 한예린, 울타리를 넘다')
S('jiwoo_truot_chan_khoi_thanh_ngang', ['P031'], 'A', False, 'Cảnh hành động', J,
  f'Jiwoo đang leo xuống phía bên kia hàng rào thì chân trượt khỏi thanh ngang, hai tay buông khỏi lưới, cô chới với giữa không trung; {JW}. {BG3["rao"]}', ['아악!'],
  'jiwoo, trượt chân, hàng rào', '서지우, 발이 미끄러지다, 철망')
S('jiwoo_roi_xuong_be_tong', ['P032'], 'A', False, 'Cảnh rộng', J,
  f'Jiwoo rơi xuống nền bê tông bên chân hàng rào, tiếng va không lớn nhưng cả ba người cùng quay lại; {JW}. {BG3["rao"]}', ['쿵!'],
  'jiwoo, ngã, nền bê tông', '서지우, 추락, 콘크리트 바닥')
S('jiwoo_om_mat_ca_chan_khuyu_goi', ['P033'], 'A', False, 'Cận cảnh', J,
  f'Jiwoo nằm nghiêng, hai tay ôm lấy mắt cá chân, mặt nhăn vì đau; cô cố đứng dậy nhưng vừa đặt chân xuống đã khuỵu gối; {JW}.', None,
  'jiwoo, ôm mắt cá, khuỵu gối', '서지우, 발목, 무릎이 꺾이다')
S('yerin_quy_xuong_kham_mat_ca', ['P034'], 'A', False, 'Trung cảnh', ['Yerin', 'Jiwoo'],
  f'Yerin ({YR}) quỳ xuống sờ quanh mắt cá chân Jiwoo, quan sát nét mặt cô, gương mặt Yerin dần cứng lại; Jiwoo ({JW}) nằm ngửa trên nền bê tông.', None,
  'yerin, khám mắt cá, jiwoo, nghi gãy', '한예린, 발목을 살피다, 서지우, 골절')
S('mat_ca_sung_bien_dang_nghi_gay_xuong', ['P035'], 'B', True, 'Cực cận', None,
  'Cực cận mắt cá chân sưng đỏ và biến dạng của một người phụ nữ, bàn tay đeo găng của bác sĩ đặt nhẹ bên cạnh; hình ảnh y khoa tiết chế, không máu.', None,
  'mắt cá sưng, biến dạng, nghi gãy xương', '부은 발목, 변형, 골절 의심')
# ---- P036-P048: Taeho cân nhắc, thỏa thuận
S('taeho_nhin_con_duong_phia_truoc', ['P036'], 'B', False, 'Cảnh sau lưng', T,
  f'Taeho đứng quay lưng nhìn con đường tối phía trước, ba người còn lại ở phía sau anh, ánh đèn đường xa mờ. {BG3["pho_dem"]}', None,
  'taeho, con đường phía trước, quay lưng', '태호, 앞길, 뒷모습')
S('taeho_can_nhac_di_mot_minh_hay_dua_ca_nhom', ['P037'], 'B', False, 'Cận mặt', T,
  'Cận mặt Taeho cân nhắc, ánh mắt chia hai hướng: một bên là con đường trống trước mặt, một bên là ba người phía sau.', None,
  'taeho, cân nhắc, đi một mình', '태호, 고민, 혼자 가다')
S('taeho_noi_khong_co_nghia_vu', ['P038'], 'A', False, 'Trung cảnh', ['Taeho', 'Areum', 'Jiwoo', 'Yerin'],
  f'Taeho nói rõ rằng mình không có nghĩa vụ đưa mọi người đi, mặt lạnh; Areum, Yerin ({YR}) và Jiwoo ({JW}, ngồi dưới đất) nhìn anh. {BG3["rao"]}', None,
  'taeho, không có nghĩa vụ, cả nhóm', '태호, 의무가 없다, 일행')
S('areum_noi_cu_di_di', ['P039', 'P040'], 'A', False, 'Cận mặt', A,
  'Cận mặt Areum nói không chút do dự bảo Taeho cứ đi một mình, ánh mắt lạnh, khoanh tay trước ngực, cung đeo trên vai.', None,
  'areum, cứ đi đi, lạnh lùng', '서아름, 혼자 가요, 냉정')
S('taeho_khong_di_ngay', ['P041'], 'C', False, 'Cận mặt', T,
  'Cận mặt Taeho im lặng, chưa rời đi, ánh mắt nhìn xa xăm.', None,
  'taeho, chưa rời đi', '태호, 바로 떠나지 않다')
S('cay_cau_lon_phia_nam_xa_xa', ['P042'], 'A', True, 'Toàn cảnh', None,
  'Toàn cảnh một cây cầu lớn bắc qua sông ở phía nam thành phố Seoryeong ban đêm, đèn cầu vàng, khói mỏng, vài ngọn lửa xa xa.', None,
  'cầu lớn, phía nam, seoryeong, sông', '큰 다리, 남쪽, 서령, 강')
S('khu_y_te_quan_tren_duong_di', ['P042'], 'B', False, 'Cảnh rộng', None,
  f'{BG3["yte"]} Nhìn từ xa trên con đường dẫn ra cây cầu, nơi có thể tìm thấy thuốc và vật tư.', None,
  'khu y tế quận, thuốc, vật tư', '구립 의료원, 약, 물자')
S('areum_cung_thu_loi_the', ['P043'], 'C', False, 'Cận cảnh', A,
  'Cận cảnh Areum cầm cung, ánh trăng hắt lên dây cung: một cung thủ tầm xa là lợi thế hiếm giữa thành phố sụp đổ.', None,
  'areum, cung thủ, lợi thế', '서아름, 궁수, 전력')
S('taeho_de_nghi_thoa_thuan_gian_don', ['P044', 'P045'], 'A', False, 'Trung cảnh', ['Taeho', 'Areum', 'Yerin', 'Jiwoo'],
  f'Taeho đưa ra một thỏa thuận đơn giản, một tay chỉ về phía trước, tay kia chỉ về Areum; Areum nhíu mày nghe, Yerin ({YR}) và Jiwoo ({JW}) lắng nghe. {BG3["rao"]}', None,
  'taeho, thỏa thuận, chia việc', '태호, 거래, 역할 분담')
S('bon_nguoi_khong_hua_dong_doi', ['P046', 'P047'], 'B', False, 'Cảnh rộng', ['Taeho', 'Areum', 'Yerin', 'Jiwoo'],
  f'Bốn người đứng cách nhau một khoảng, không ai nắm tay hay mỉm cười: một liên minh vì lợi ích chứ không phải tình đồng đội; Taeho, Areum, Yerin ({YR}), Jiwoo ({JW}). {BG3["rao"]}', None,
  'bốn người, liên minh, không hứa hẹn', '네 사람, 동맹, 약속 없음')
S('areum_suy_nghi_roi_gat_dau', ['P048'], 'B', False, 'Cận mặt', A,
  'Cận mặt Areum suy nghĩ một lúc rồi gật đầu đồng ý, ánh mắt vẫn cảnh giác.', None,
  'areum, gật đầu, đồng ý', '서아름, 고개를 끄덕이다')
# ---- P049-P051: nẹp chân
S('yerin_nep_chan_jiwoo_bang_hai_thanh_nhom', ['P049'], 'A', False, 'Trung cảnh', ['Yerin', 'Jiwoo'],
  f'Yerin ({YR}) dùng hai thanh nhôm lấy từ giá treo dụng cụ nẹp cố định chân Jiwoo, quấn băng trắng quanh nẹp; Jiwoo ({JW}) ngồi dựa hàng rào, cắn môi chịu đau. {BG3["rao"]}', None,
  'yerin, nẹp chân, thanh nhôm, băng', '한예린, 부목, 알루미늄 막대, 붕대')
S('yerin_dan_jiwoo_dung_don_trong_luong', ['P049'], 'C', False, 'Cận cảnh', ['Yerin', 'Jiwoo'],
  f'Cận cảnh Yerin ({YR}) kiểm tra độ chắc của nẹp rồi chỉ ngón tay dặn Jiwoo ({JW}) đừng dồn trọng lượng lên chân.', None,
  'yerin, dặn dò, kiểm tra nẹp', '한예린, 당부, 부목 확인')
S('tui_y_te_vat_tu_can_dan', ['P050'], 'A', False, 'Cận cảnh', Y,
  f'Cận cảnh túi y tế của Yerin ({YR}) mở ra: chỉ còn một bộ khâu nhỏ, vài viên kháng sinh và cuộn băng gần hết, bàn tay cô đếm lại.', None,
  'túi y tế, vật tư cạn, bộ khâu, kháng sinh', '구급 가방, 물자 부족, 봉합 세트, 항생제')
S('can_den_khu_y_te_truoc_khi_het', ['P051'], 'C', False, 'Cận mặt', T,
  'Cận mặt Taeho nhìn về phía trước, tính toán: phải tới khu y tế trước khi vật tư cạn sạch.', None,
  'taeho, tính toán, thời gian', '태호, 계산, 시간')
# ---- P052-P058: xe tải
S('xe_tai_nho_cho_dung_cu_o_bai_xe', ['P052'], 'A', True, 'Cảnh rộng', None,
  f'{BG3["bai_xe"]} Một chiếc xe tải nhỏ màu trắng chở dụng cụ tập luyện đậu một mình, chìa khóa còn cắm trên ổ.', None,
  'xe tải nhỏ, bãi xe, dụng cụ tập luyện', '소형 트럭, 주차장, 훈련 장비')
S('chia_khoa_binh_xang_hon_nua', ['P052'], 'B', True, 'Cận cảnh', None,
  'Cận cảnh chìa khóa cắm trên ổ xe tải, đồng hồ xăng trong bảng điều khiển chỉ hơn nửa bình, ánh sáng bảng điều khiển hắt lên.', None,
  'chìa khóa, đồng hồ xăng, hơn nửa bình', '열쇠, 연료 게이지, 절반 이상')
S('taeho_kiem_tra_buong_lai_guong_duong', ['P053'], 'B', False, 'Trung cảnh', T,
  f'Taeho nhìn nhanh buồng lái, gương chiếu hậu và con đường phía trước chiếc xe tải; không thấy chuyển động nào. {BG3["bai_xe"]}', None,
  'taeho, kiểm tra xe, gương chiếu hậu', '태호, 운전석 확인, 사이드미러')
S('jiwoo_len_ghe_phu_yerin_ngoi_canh', ['P054'], 'B', False, 'Trung cảnh', ['Jiwoo', 'Yerin'],
  f'Jiwoo ({JWS}) được đỡ lên ghế phụ của xe tải, Yerin ({YR}) ngồi sát bên cạnh.', None,
  'jiwoo, yerin, ghế phụ', '서지우, 한예린, 조수석')
S('areum_leo_len_thung_sau_cung_ong_ten', ['P054'], 'B', False, 'Cảnh hành động', A,
  f'Areum leo lên thùng sau của chiếc xe tải nhỏ cùng cây cung và ống tên, đứng vững một chân. {BG3["bai_xe"]}', None,
  'areum, thùng sau xe tải, cung', '서아름, 짐칸, 활')
S('taeho_biet_dong_co_se_goi_zombie', ['P055', 'P056'], 'C', False, 'Cận mặt', T,
  'Cận mặt Taeho trong buồng lái, ánh mắt tính toán: biết rõ tiếng động cơ sẽ vang đi xa nhưng không còn lựa chọn nào khác vì chân Jiwoo.', None,
  'taeho, tiếng động cơ, không còn lựa chọn', '태호, 엔진 소리, 다른 선택이 없다')
S('taeho_khoi_dong_xe', ['P057'], 'A', False, 'Cận cảnh', T,
  'Cận cảnh bàn tay Taeho xoay chìa khóa khởi động xe, đèn bảng điều khiển bật sáng, vẻ mặt quyết định.', ['부릉'],
  'taeho, khởi động xe, chìa khóa', '태호, 시동, 열쇠')
S('quyet_dinh_dau_tien_xe_chay_khoi_bai', ['P058'], 'B', False, 'Cảnh rộng', None,
  f'Chiếc xe tải nhỏ rời bãi xe với đèn pha sáng, bóng nó đổ dài, phía sau trung tâm bắn cung chìm trong bóng tối: quyết định khiến tình hình vượt khỏi tầm kiểm soát. {BG3["bai_xe"]}', None,
  'xe tải rời bãi, đèn pha, quyết định', '트럭 출발, 전조등, 결정')
# ---- P059-P066: ngã tư, Kẻ Hú
S('xe_chay_duong_lon_vang_ve', ['P059', 'P060'], 'A', False, 'Cảnh rộng', None,
  f'Chiếc xe tải nhỏ chạy trên đại lộ gần như bỏ hoang, những chiếc xe đâm vào nhau nằm chắn giữa các làn, vài ngọn lửa âm ỉ trong các tòa nhà ven phố. {BG3["pho_dem"]}', None,
  'xe tải, đại lộ vắng, xe đâm nhau, cháy', '트럭, 텅 빈 대로, 충돌한 차, 불길')
S('taeho_giam_toc_khi_toi_nga_tu', ['P061'], 'B', False, 'Trung cảnh qua kính', T,
  f'Nhìn qua kính chắn gió: Taeho giảm tốc khi xe tới một ngã tư tối, đèn pha quét lên mặt đường. {BG3["ngatu"]}', None,
  'taeho, giảm tốc, ngã tư', '태호, 감속, 교차로')
S('hinh_nguoi_gay_dét_o_goc_duong', ['P062'], 'A', False, 'Cảnh rộng', ['Kẻ Hú'],
  f'Ở góc ngã tư tối, một bóng người gầy đét đứng bất động: KẺ HÚ (số 3 trong bảng), đầu cúi thấp, xương vai nhô lên dưới lớp áo rách. {BG3["ngatu"]}', None,
  'kẻ hú, góc đường, gầy đét', '비명체, 길모퉁이, 앙상한')
S('ke_hu_ngang_dau_duoi_den_pha', ['P063'], 'A', False, 'Cận cảnh', ['Kẻ Hú'],
  'KẺ HÚ từ từ ngẩng đầu khi ánh đèn pha quét lên, gương mặt trắng bệch lóa sáng, mắt trống rỗng.', None,
  'kẻ hú, ngẩng đầu, đèn pha', '비명체, 고개를 들다, 전조등')
S('co_hong_phong_bat_thuong_mieng_mo_rong', ['P064'], 'A', False, 'Cận cảnh', ['Kẻ Hú'],
  'Cận cảnh KẺ HÚ: cổ họng phồng lên bất thường như một cái túi, miệng há rộng quá cỡ để lộ khoảng tối sâu bên trong.', None,
  'kẻ hú, cổ họng phồng, miệng há rộng', '비명체, 부푼 목, 크게 벌린 입')
S('taeho_nhan_ra_qua_muon', ['P065', 'P066'], 'B', False, 'Cận mặt qua kính', T,
  'Cận mặt Taeho trong buồng lái, đồng tử co lại khi nhận ra Kẻ Hú quá muộn.', None,
  'taeho, nhận ra muộn, kẻ hú', '태호, 뒤늦게 깨닫다, 비명체')
# ---- P067-P074: tiếng hú, Areum bắn, đàn tới
S('tieng_hu_bung_len_truoc_dau_xe', ['P067'], 'A', False, 'Cảnh rộng hành động', ['Kẻ Hú'],
  f'KẺ HÚ ngửa cổ hú ngay trước đầu xe tải, sóng âm như rung kính chắn gió, đèn pha lóa. {BG3["ngatu"]}', ['끼아아아악!'],
  'tiếng hú, kẻ hú, trước đầu xe', '비명, 비명체, 차 앞')
S('taeho_u_tai_dap_phanh', ['P068'], 'B', False, 'Cận mặt qua kính', T,
  'Cận mặt Taeho bịt một bên tai ù đặc vì tiếng hú, chân đạp mạnh phanh, kính chắn gió rung.', None,
  'taeho, ù tai, đạp phanh', '태호, 귀가 먹먹하다, 브레이크')
S('areum_bat_day_giuong_cung_o_thung_sau', ['P069'], 'A', False, 'Cảnh hành động góc thấp', A,
  f'Areum bật dậy ở thùng sau xe tải, kéo dây cung căng ngay khi xe chậm lại, tóc bện bay trong gió. {BG3["ngatu"]}', None,
  'areum, bật dậy, kéo cung, thùng xe', '서아름, 일어서다, 시위를 당기다')
S('mui_ten_xuyen_co_hong_ke_hu', ['P070'], 'A', False, 'Cận cảnh hành động', ['Kẻ Hú'],
  'Mũi tên xuyên qua cổ họng KẺ HÚ, tiếng hú đứt giữa chừng, miệng nó đóng lại; tiết chế, chất dịch đen sẫm loãng.', ['퍽!'],
  'mũi tên xuyên cổ họng, kẻ hú, tắt tiếng', '화살이 목을 꿰뚫다, 비명체, 비명이 끊기다')
S('tin_hieu_da_phat_di_ngã_tu_im_lang', ['P071'], 'C', False, 'Cảnh rộng', None,
  f'Ngã tư chợt im lặng sau tiếng hú đứt, nhưng trong các con hẻm tối hai bên đã thấy những cái bóng đầu tiên chuyển động. {BG3["ngatu"]}', None,
  'ngã tư, im lặng, đã muộn', '교차로, 정적, 이미 늦었다')
S('bong_nguoi_xuat_hien_tu_hem_hai_ben', ['P072'], 'A', False, 'Cảnh rộng', ['Kẻ Lang Thang'],
  f'Từ những con hẻm hai bên ngã tư, từng bóng KẺ LANG THANG bắt đầu xuất hiện, lúc đầu vài con rồi hàng chục. {BG3["ngatu"]}', None,
  'bóng người, hẻm, đàn kéo đến', '그림자, 골목, 떼로 몰려오다')
S('dan_ke_lang_thang_ke_le_chan_do_ve_nga_tu', ['P073'], 'A', True, 'Toàn cảnh', ['Kẻ Lang Thang'],
  f'Đàn KẺ LANG THANG kéo lê chân, va vào những chiếc xe bỏ lại và chen nhau dồn về ngã tư trong ánh đèn pha; chiếc xe tải nhỏ đứng giữa. {BG3["ngatu"]}', ['터벅터벅'],
  'đàn kẻ lang thang, kéo lê chân, ngã tư', '떠돌이 떼, 발을 끌다, 교차로')
S('taeho_khong_dem_het_so_dang_do_toi', ['P074'], 'C', False, 'Cận mặt', T,
  'Cận mặt Taeho qua kính, không thể đếm hết số bóng người đang đổ tới, ánh đèn pha phản chiếu trong mắt.', None,
  'taeho, không đếm hết, đàn zombie', '태호, 수를 헤아릴 수 없다')
# ---- P075-P085: đâm thoát, xe chết máy
S('taeho_banh_lai_lach_qua_khe_giua_hai_xe', ['P075'], 'B', False, 'Cảnh hành động', None,
  f'Chiếc xe tải nhỏ bẻ lái lách qua khe hẹp giữa hai chiếc xe bỏ lại, sát mép kim loại. {BG3["ngatu"]}', ['끼익!'],
  'bẻ lái, khe hẹp, lách xe', '핸들을 꺾다, 좁은 틈, 차 사이')
S('dam_ke_lang_thang_chan_ngang_duong', ['P075'], 'B', False, 'Cảnh rộng', ['Kẻ Lang Thang'],
  f'Một đám KẺ LANG THANG lao ra chắn ngang đường trước đầu xe tải, không còn chỗ để né hoàn toàn. {BG3["ngatu"]}', None,
  'kẻ lang thang chắn đường, đầu xe', '떠돌이 무리, 길을 막다')
S('taeho_dap_ga_pha_duong', ['P076'], 'A', False, 'Cận cảnh', T,
  'Cận cảnh bàn chân Taeho đạp ga hết cỡ, đồng hồ vòng tua vọt lên, gương mặt anh quả quyết phía sau kính.', ['부웅!'],
  'taeho, đạp ga, tăng tốc', '태호, 액셀, 가속')
S('xe_tong_dam_dong_ke_lang_thang_va_vat_can', ['P077'], 'A', False, 'Cảnh hành động', ['Kẻ Lang Thang'],
  'Chiếc xe tải nhỏ húc văng KẺ LANG THANG và các vật cản trước đầu xe, thân xe chao đảo; tiết chế, chất dịch đen sẫm loãng bắn lên kính, không máu đỏ.', ['쾅!', '쾅!'],
  'xe tải tông, kẻ lang thang, văng ra', '트럭 충돌, 떠돌이, 튕겨 나가다')
S('xe_re_vao_hem_sau_khu_y_te', ['P077'], 'B', False, 'Cảnh rộng', None,
  f'Chiếc xe tải nhỏ rẽ gấp vào con hẻm dẫn ra phía sau khu y tế, phía sau là đàn bóng người bám theo. {BG3["hem"]}', None,
  'xe rẽ vào hẻm, khu y tế, đàn bám theo', '골목으로 꺾다, 의료원, 추격')
S('xe_tai_chao_dao_can_manh_vo', ['P078'], 'C', False, 'Cảnh hành động', None,
  f'Chiếc xe tải chao đảo khi bánh xe cán qua đống mảnh vỡ trong hẻm hẹp. {BG3["hem"]}', ['덜컹'],
  'xe chao đảo, mảnh vỡ, hẻm', '트럭이 휘청, 파편, 골목')
S('kim_nhiet_do_vot_tieng_rit_dong_co', ['P079'], 'A', False, 'Cận cảnh', None,
  'Cận cảnh bảng đồng hồ xe tải: kim nhiệt độ vọt lên vùng đỏ, đèn cảnh báo nhấp nháy.', ['끼이익'],
  'kim nhiệt độ, đèn cảnh báo, động cơ', '온도계, 경고등, 엔진')
S('khoi_bay_tu_khoang_dong_co_xe_tai', ['P079'], 'B', False, 'Cảnh rộng', None,
  f'Khói trắng bốc lên từ khoang động cơ của chiếc xe tải nhỏ đang chậm dần trong hẻm tối. {BG3["hem"]}', None,
  'khói, khoang động cơ, mất công suất', '연기, 엔진룸, 출력 저하')
S('xe_dung_o_cuoi_hem_taeho_khong_khoi_dong_lai', ['P080', 'P081'], 'A', False, 'Cảnh rộng', ['Taeho'],
  f'Chiếc xe tải nhỏ dừng ở cuối hẻm, khói bay, Taeho ngồi sau tay lái không thử khởi động lại, ánh đèn pha tắt dần. {BG3["hem"]}', None,
  'xe dừng cuối hẻm, không khởi động lại', '골목 끝에 정차, 재시동 포기')
S('bong_dan_xac_song_phia_sau_hem', ['P082'], 'A', False, 'Cảnh rộng', ['Kẻ Lang Thang'],
  f'Nhìn từ buồng lái ra sau: đàn KẺ LANG THANG kéo lê chân tiến vào con hẻm, tiếng chân đang đến gần, bóng chúng chồng lên nhau. {BG3["hem"]}', ['터벅터벅'],
  'đàn phía sau, kéo lê chân, đến gần', '뒤에서 오는 떼, 발소리, 가까워지다')
S('taeho_do_jiwoo_xuong_xe', ['P083'], 'B', False, 'Trung cảnh', ['Taeho', 'Jiwoo', 'Yerin'],
  f'Taeho mở cửa đỡ Jiwoo ({JWS}) xuống xe, Yerin ({YR}) cùng dìu cô; ánh đèn khẩn cấp xanh nhạt từ lối đi sau. {BG3["hem"]}', None,
  'taeho, đỡ jiwoo, yerin', '태호, 서지우를 부축, 한예린')
S('bon_nguoi_vao_loi_di_sau_khu_y_te', ['P083'], 'B', False, 'Cảnh sau lưng', ['Taeho', 'Jiwoo', 'Yerin', 'Areum'],
  f'Bốn người vào lối đi sau khu y tế: Taeho và Yerin ({YR}) dìu Jiwoo ({JWS}), Areum đi cuối quan sát con hẻm. {BG3["kho"]}', None,
  'bốn người, lối sau, khu y tế', '네 사람, 뒤쪽 통로, 의료원')
S('khong_ai_noi_ve_chiec_xe', ['P084', 'P085'], 'C', False, 'Cận cảnh', None,
  f'Chiếc xe tải nhỏ bốc khói bị bỏ lại cuối hẻm, ánh đèn khẩn cấp xanh nhạt hắt lên thân xe; không ai nhắc tới nó. {BG3["hem"]}', None,
  'xe bỏ lại, không ai nhắc', '버려진 트럭, 아무도 말하지 않다')
# ---- P086-P093: vào khu y tế
S('khu_y_te_quan_bon_tang_mat_tien', ['P086'], 'A', True, 'Cảnh rộng', None,
  f'{BG3["yte"]}', None,
  'khu y tế quận, bốn tầng, mặt tiền', '구립 의료원, 사 층, 정면')
S('yerin_tung_den_tap_huan_biet_cua_kho', ['P087'], 'B', False, 'Cận mặt', Y,
  f'Cận mặt Yerin nhớ lại những lần tập huấn ở đây, ánh mắt xác định hướng cửa kho thuốc phía sau; Yerin {YR}.', None,
  'yerin, nhớ lại, cửa kho thuốc', '한예린, 연수, 약품 창고 출입구')
S('cua_kho_thuoc_phia_sau_it_bi_lo', ['P088'], 'B', False, 'Trung cảnh', None,
  f'{BG3["kho"]} Cửa sắt hé mở, tách khỏi đường lớn.', None,
  'cửa kho thuốc, phía sau, ít bị lộ', '약품 창고 문, 뒤편, 눈에 덜 띄다')
S('hanh_lang_toi_mui_thuoc_sat_trung_cu', ['P089'], 'A', True, 'Cảnh rộng', None,
  f'Hành lang tối sau cánh cửa kho: mùi thuốc sát trùng cũ lẫn ẩm mốc, ánh đèn khẩn cấp xanh nhạt, hơi nước bốc nhẹ. {BG3["kho"]}', None,
  'hành lang tối, mùi thuốc, ẩm mốc', '어두운 복도, 소독약 냄새, 곰팡내')
S('doi_hinh_len_cau_thang_taeho_di_dau', ['P090', 'P091'], 'B', False, 'Cảnh dọc cầu thang', ['Taeho', 'Jiwoo', 'Yerin', 'Areum'],
  f'Đội hình lên cầu thang: Taeho đi đầu, Jiwoo ({JWS}) tựa vai anh, Yerin ({YR}) đỡ sát bên, Areum cuối cùng cầm mũi tên sẵn trên dây. {BG3["cau_thang"]}', None,
  'lên cầu thang, đội hình, tầng bốn', '계단, 대형, 사 층')
S('yerin_chi_phong_thuoc_cuoi_hanh_lang', ['P092'], 'C', False, 'Cận mặt', Y,
  f'Cận mặt Yerin ({YR}) thì thầm chỉ về cuối hành lang: phòng thuốc lớn nhất nằm ở đó.', None,
  'yerin, phòng thuốc, cuối hành lang', '한예린, 약품실, 복도 끝')
S('san_thuong_co_cho_truc_thang_ha_canh', ['P092', 'P093'], 'B', True, 'Cảnh rộng', None,
  f'{BG3["thuong"]} Không có ai, bãi đáp trực thăng sơn vòng tròn rõ nét.', None,
  'sân thượng, bãi đáp trực thăng, tập kết cứu hộ', '옥상, 헬기장, 구조 집결지')
# ---- P094-P104: tầng bốn, Thể Phình
S('hanh_lang_tang_bon_ke_lang_thang_dung_ngu', ['P094', 'P095'], 'A', False, 'Cảnh rộng', ['Kẻ Lang Thang'],
  f'Cuối hành lang tầng bốn dưới đèn đỏ khẩn cấp: hơn mười KẺ LANG THANG đứng dọc hai bên tường, đầu cúi, bất động như đang ngủ đứng. {BG3["hanh_lang4"]}', None,
  'hành lang tầng bốn, kẻ lang thang, ngủ đứng', '사 층 복도, 떠돌이, 서서 자는 듯')
S('the_phinh_o_giua_hanh_lang', ['P096', 'P097'], 'A', False, 'Cảnh rộng', ['Thể Phình'],
  f'Giữa hành lang tầng bốn là THỂ PHÌNH (số 4 trong bảng) cao gấp mấy lần những con còn lại, bụng căng phồng, ánh đèn đỏ rọi lên da loang vệt đen. {BG3["hanh_lang4"]}', None,
  'thể phình, giữa hành lang, to gấp ba', '팽창체, 복도 한가운데, 거대')
S('bung_the_phinh_phong_cang_chat_long_den_ben_trong', ['P098'], 'B', False, 'Cận cảnh', ['Thể Phình'],
  'Cận cảnh cái bụng căng phồng của THỂ PHÌNH: da mỏng bóng, chất lỏng đen sẫm loãng cuộn lên bên dưới, một mảng đen đậm tụ lại; hình ảnh tiết chế.', None,
  'bụng thể phình, chất lỏng đen, vệt đen đậm', '팽창체 배, 검은 액체, 짙은 얼룩')
S('taeho_gio_tay_ra_hieu_dung_lai', ['P099'], 'B', False, 'Trung cảnh', ['Taeho', 'Jiwoo'],
  f'Taeho giơ nắm tay ra hiệu dừng lại, Jiwoo ({JWS}) đang dựa vào anh, cả hai khựng ở lối vào hành lang. {BG3["hanh_lang4"]}', None,
  'taeho, ra hiệu dừng, jiwoo', '태호, 멈추라는 신호, 서지우')
S('vai_jiwoo_cham_tay_nam_cua_phia_sau', ['P100', 'P101'], 'A', False, 'Cận cảnh', J,
  f'Cận cảnh vai Jiwoo ({JWS}) vô tình va vào tay nắm cửa kim loại phía sau khi nhóm lùi lại, tay nắm rung lên.', ['딸깍'],
  'vai jiwoo, tay nắm cửa, tiếng kim loại', '서지우 어깨, 문손잡이, 금속 소리')
S('mot_cai_dau_quay_ve_phia_ho', ['P102', 'P103'], 'A', False, 'Cận cảnh', ['Kẻ Lang Thang'],
  'Một cái đầu KẺ LANG THANG trong hành lang đỏ chậm rãi quay về phía người xem, rồi thêm một cái nữa phía sau nó.', None,
  'đầu quay lại, kẻ lang thang, hành lang', '고개가 돌아오다, 떠돌이, 복도')
S('ca_hanh_lang_bat_dau_chuyen_dong', ['P104'], 'A', False, 'Cảnh rộng', ['Kẻ Lang Thang', 'Thể Phình'],
  f'Cả hành lang tầng bốn bắt đầu chuyển động: đám KẺ LANG THANG và THỂ PHÌNH cùng quay về phía lối vào. {BG3["hanh_lang4"]}', ['슥…'],
  'cả hành lang chuyển động, thể phình', '복도 전체가 움직이다, 팽창체')
# ---- P105-P114: dụ đàn
S('taeho_nhin_the_phinh_roi_cay_cung', ['P105'], 'B', False, 'Cận mặt', T,
  'Cận mặt Taeho, ánh mắt chuyển qua lại giữa con quái vật khổng lồ ở xa và cây cung trong tay Areum.', None,
  'taeho, thể phình, cây cung', '태호, 팽창체, 활')
S('no_giua_hanh_lang_khong_co_duong_tranh', ['P106'], 'C', False, 'Cảnh rộng', ['Thể Phình'],
  f'Hành lang tầng bốn hẹp: nếu THỂ PHÌNH nổ ở đây thì không có đường tránh, vách tường hai bên sát nhau. {BG3["hanh_lang4"]}', None,
  'hành lang hẹp, không đường tránh', '좁은 복도, 피할 곳 없음')
S('phai_keo_chung_roi_cho_dang_dung', ['P107'], 'C', False, 'Cận mặt', T,
  'Cận mặt Taeho quyết định: phải dụ chúng rời khỏi chỗ đang đứng.', None,
  'taeho, quyết định, dụ đàn', '태호, 결정, 유인')
S('taeho_dap_chai_nuoc_vao_tuong', ['P108'], 'A', False, 'Cảnh hành động', T,
  f'Taeho đập mạnh chai nước vào bức tường cuối hành lang, mảnh nhựa văng ra, rồi ném chai về phía cầu thang. {BG3["hanh_lang4"]}', ['쨍!'],
  'taeho, đập chai nước, dụ', '태호, 물병, 유인')
S('am_thanh_vang_trong_khong_gian_kin', ['P109'], 'B', False, 'Cảnh rộng', None,
  f'Tiếng động dội vang trong không gian kín của hành lang tầng bốn, những làn sóng âm như hiện thành vòng sáng nhạt trên tường. {BG3["hanh_lang4"]}', ['쨍그랑!'],
  'âm thanh vang, không gian kín', '소리 울림, 닫힌 공간')
S('ke_lang_thang_dong_loat_quay_dau', ['P110'], 'A', False, 'Cảnh rộng', ['Kẻ Lang Thang'],
  f'Đám KẺ LANG THANG đồng loạt quay đầu về phía tiếng động ở cuối hành lang. {BG3["hanh_lang4"]}', None,
  'quay đầu đồng loạt, kẻ lang thang', '일제히 고개를 돌리다, 떠돌이')
S('the_phinh_keo_than_nang_ne_dich_chuyen', ['P110', 'P111'], 'A', False, 'Cảnh rộng', ['Thể Phình', 'Kẻ Lang Thang'],
  f'THỂ PHÌNH kéo thân hình nặng nề dịch chuyển về phía tiếng động, đám KẺ LANG THANG chen theo sau tạo thành một khối hỗn loạn. {BG3["hanh_lang4"]}', None,
  'thể phình dịch chuyển, khối hỗn loạn', '팽창체 이동, 뒤엉킨 무리')
S('mot_con_ke_lang_thang_lao_ve_phia_nhom', ['P112'], 'B', False, 'Cảnh hành động', ['Kẻ Lang Thang', 'Taeho'],
  f'Một KẺ LANG THANG bất ngờ quay về phía nhóm và loạng choạng lao tới, Taeho đứng chắn phía trước. {BG3["hanh_lang4"]}', None,
  'kẻ lang thang lao tới, taeho chắn', '떠돌이가 다가오다, 태호')
S('taeho_vung_dao_chan_con_lang_thang', ['P112'], 'A', False, 'Cận cảnh hành động', ['Taeho', 'Kẻ Lang Thang'],
  'Taeho vung con dao quân dụng chặn đứng KẺ LANG THANG đang lao tới, lưỡi dao lóe lên dưới ánh đèn đỏ; tiết chế, chất dịch đen sẫm loãng.', ['푹!'],
  'taeho, vung dao, chặn', '태호, 칼을 휘두르다')
S('the_phinh_van_dang_di_chuyen_trong_luc_do', ['P113'], 'C', False, 'Cảnh rộng', ['Thể Phình'],
  f'Trong cùng lúc đó, THỂ PHÌNH vẫn tiếp tục dịch chuyển về giữa đám đông ở cuối hành lang. {BG3["hanh_lang4"]}', None,
  'thể phình tiếp tục di chuyển', '팽창체는 계속 움직이다')
S('taeho_xac_nhan_vi_tri_ra_hieu_cho_areum', ['P114'], 'B', False, 'Trung cảnh', ['Taeho', 'Areum'],
  f'Taeho xác nhận THỂ PHÌNH đã vào giữa đám đông và ra hiệu cho Areum bằng một cái gật đầu; Areum giương cung sẵn sàng. {BG3["hanh_lang4"]}', None,
  'taeho, ra hiệu, areum sẵn sàng', '태호, 신호, 서아름')
# ---- P115-P122: nổ
S('areum_buong_day_cung_tren_hanh_lang', ['P115'], 'A', False, 'Cận cảnh', A,
  'Cận cảnh ngón tay Areum buông dây cung, mũi tên rời dây, đuôi tên rung và vệt sáng nhỏ theo ánh đèn đỏ khẩn cấp.', ['핑!'],
  'areum, buông dây cung, mũi tên rời dây', '서아름, 시위를 놓다, 화살')
S('mui_ten_xuyen_vung_den_dam_tren_bung', ['P116'], 'A', False, 'Cận cảnh hành động', ['Thể Phình'],
  'Mũi tên xuyên vào vùng đen đậm tụ lại trên cái bụng căng phồng của THỂ PHÌNH, da bắt đầu rạn nứt quanh đầu tên.', ['퍽!'],
  'mũi tên, bụng thể phình, vùng đen', '화살, 팽창체 배, 검은 부위')
S('co_the_phong_mop_nhan_nheo', ['P117'], 'B', False, 'Cận cảnh', ['Thể Phình'],
  'Cái bụng căng phồng của THỂ PHÌNH nhăn lại và méo mó đột ngột trong khoảnh khắc trước khi nổ.', None,
  'cơ thể méo mó, trước khi nổ', '일그러지다, 폭발 직전')
S('vu_no_tram_duc_chat_dich_den_bat_len_tuong_tran', ['P118', 'P119'], 'A', False, 'Cảnh rộng hành động', ['Thể Phình', 'Kẻ Lang Thang'],
  f'THỂ PHÌNH nổ tung giữa hành lang: chất dịch đen sẫm loãng bắn lên tường và trần, các KẺ LANG THANG gần đó bị hất ngã chồng lên nhau trong không gian hẹp; tiết chế, không nội tạng, không máu đỏ. {BG3["hanh_lang4"]}', ['콰앙!'],
  'vụ nổ, thể phình, chất dịch đen, hất ngã', '폭발, 팽창체, 검은 액체')
S('taeho_dung_than_che_cho_jiwoo', ['P120'], 'A', False, 'Cảnh hành động', ['Taeho', 'Jiwoo', 'Yerin'],
  f'Taeho kéo Jiwoo ({JWS}) xuống thấp và dùng cả thân mình che cho cô khỏi mảnh vỡ và chất dịch đen văng tới, Yerin ({YR}) cúi rạp bên cạnh. {BG3["hanh_lang4"]}', None,
  'taeho che chắn jiwoo, yerin cúi thấp', '태호가 막다, 서지우, 한예린')
S('areum_ban_them_mot_mui_vao_con_dang_bo', ['P121'], 'B', False, 'Cảnh hành động', ['Areum', 'Kẻ Lang Thang'],
  f'Areum bắn thêm một mũi tên vào KẺ LANG THANG đang bò qua đống đổ nát của vụ nổ. {BG3["hanh_lang4"]}', ['핑!'],
  'areum, bắn thêm một mũi, đống đổ nát', '서아름, 한 발 더, 잔해')
S('areum_ra_hieu_loi_di_da_thong', ['P122'], 'B', False, 'Trung cảnh', A,
  f'Areum vẫy tay ra hiệu lối đi đã thông, sau lưng cô là hành lang đầy khói và chất dịch đen. {BG3["hanh_lang4"]}', None,
  'areum, ra hiệu, lối thông', '서아름, 길이 열렸다는 신호')
# ---- P123-P132: vào phòng thuốc
S('chay_ve_phia_phong_thuoc', ['P123'], 'A', False, 'Cảnh hành động', ['Taeho', 'Jiwoo', 'Yerin', 'Areum'],
  f'Cả bốn người chạy dọc hành lang về phía phòng thuốc, Taeho đi đầu đẩy cửa, Yerin ({YR}) đỡ Jiwoo ({JWS}), Areum chạy cuối. {BG3["hanh_lang4"]}', ['후다닥!'],
  'chạy về phòng thuốc, hành lang', '약품실로 달리다, 복도')
S('dong_cua_phong_thuoc_areum_vao_cuoi', ['P124'], 'B', False, 'Trung cảnh', ['Areum', 'Taeho'],
  f'Areum là người cuối cùng vào phòng thuốc và đóng sầm cửa, Taeho đỡ phía trong. {BG3["thuoc"]}', ['쾅!'],
  'areum đóng cửa, phòng thuốc', '서아름, 문을 닫다, 약품실')
S('keo_tu_kim_loai_chan_cua', ['P125'], 'A', False, 'Cảnh hành động', ['Taeho', 'Areum'],
  f'Taeho và Areum cùng kéo một chiếc tủ kim loại lớn chặn sát cửa phòng thuốc, bóng đổ nghiêng trên sàn. {BG3["thuoc"]}', ['끼익'],
  'chặn cửa, tủ kim loại', '캐비닛으로 문을 막다')
S('bon_nguoi_tho_dac_im_lang', ['P126'], 'B', False, 'Cảnh rộng', ['Taeho', 'Jiwoo', 'Yerin', 'Areum'],
  f'Bốn người thở dốc trong phòng thuốc, mỗi người một góc, không ai nói gì sau lằn ranh sinh tử vừa qua; Taeho, Jiwoo ({JWS}), Yerin ({YR}), Areum. {BG3["thuoc"]}', None,
  'bốn người thở dốc, im lặng', '네 사람 숨을 고르다, 침묵')
S('taeho_nhin_canh_cua_het_van_may_chi_vua_du', ['P127'], 'C', False, 'Cận mặt', T,
  'Cận mặt Taeho nhìn về phía cánh cửa đã chặn, hiểu rằng họ sống sót không nhờ một kế hoạch hoàn hảo mà chỉ vừa đủ may mắn.', None,
  'taeho, may mắn, vừa đủ', '태호, 운, 간신히')
S('areum_kiem_tra_ong_ten_con_muoi_hai_mui', ['P128', 'P129'], 'A', False, 'Cận cảnh', A,
  'Cận cảnh Areum kiểm tra ống tên đeo lưng, bàn tay đếm: còn đúng mười hai mũi tên.', None,
  'areum, ống tên, mười hai mũi', '서아름, 화살통, 열두 발')
S('areum_dem_so_mui_ten_da_dung', ['P130', 'P131', 'P132'], 'B', False, 'Cận mặt', A,
  'Cận mặt Areum trầm ngâm tính lại: ban đầu mười sáu, nay chỉ còn mười hai; mỗi mũi tên bắn đi là một phần khả năng sống sót của cô vơi dần.', None,
  'areum, số mũi tên, vơi dần', '서아름, 화살 수, 줄어드는 선택지')
# ---- P133-P147: ba người sống sót, vết cắn
S('phong_thuoc_ba_nguoi_song_sot_sau_ke', ['P133', 'P134'], 'A', False, 'Cảnh rộng', None,
  f'Phía sau các kệ thuốc trong phòng thuốc có ba người ẩn nấp: {OH}; {IN}; và {CO}. Họ nhìn ra đầy cảnh giác. {BG3["thuoc"]}', None,
  'phòng thuốc, ba người sống sót', '약품실, 생존자 세 명')
S('ba_nguoi_nhin_nhom_canh_giac_khong_tan_cong', ['P135'], 'B', False, 'Trung cảnh', None,
  f'Ba người sống sót ({OH}; {IN}; {CO}) nhìn nhóm Taeho bằng ánh mắt cảnh giác nhưng không có ý tấn công. {BG3["thuoc"]}', None,
  'ba người, cảnh giác, không tấn công', '세 사람, 경계, 공격 의사 없음')
S('ong_oh_noi_ve_truc_thang_so_tan', ['P136'], 'B', False, 'Cận mặt', None,
  f'Cận mặt {OH}, kể rằng giám đốc khu y tế từng thông báo sẽ có trực thăng sơ tán trên sân thượng; ánh đèn khẩn cấp ấm.', None,
  'ông oh, trực thăng sơ tán, sân thượng', '오 약사, 구조 헬기, 옥상')
S('cua_san_thuong_chan_bang_giuong_benh', ['P136'], 'B', True, 'Cảnh rộng', None,
  'Cánh cửa lên sân thượng của khu y tế được chặn bằng mấy chiếc giường bệnh chồng lên nhau để ngăn người nhiễm từ cầu thang tràn lên, ánh đèn khẩn cấp xanh nhạt.', None,
  'cửa sân thượng, giường bệnh chặn, cầu thang', '옥상 문, 병상으로 막다, 계단')
S('ho_cho_cuu_ho_tu_khi_tham_hoa_bat_dau', ['P137'], 'C', False, 'Cảnh rộng', None,
  f'Ba người sống sót ngồi co ro ở một góc phòng thuốc, mệt mỏi, chờ cứu hộ từ khi thảm họa bắt đầu; {OH}; {IN}; {CO}. {BG3["thuoc"]}', None,
  'chờ cứu hộ, ba người, phòng thuốc', '구조를 기다리다, 세 사람')
S('yerin_kham_jiwoo_truoc_yeu_cau_thuoc', ['P138'], 'B', False, 'Trung cảnh', ['Yerin', 'Jiwoo'],
  f'Yerin ({YR}) kiểm tra tình trạng Jiwoo ({JWS}) trước, ngón tay chỉ về phía tủ thuốc, yêu cầu kháng sinh, thuốc giảm đau và băng gạc. {BG3["thuoc"]}', None,
  'yerin, kiểm tra jiwoo, yêu cầu thuốc', '한예린, 서지우를 살피다, 약')
S('ong_oh_mo_tu_thuoc_voi_dieu_kien', ['P139'], 'B', False, 'Trung cảnh', None,
  f'{OH} mở tủ thuốc bằng chùm chìa khóa với điều kiện Yerin phải khám cho cả ba người. {BG3["thuoc"]}', None,
  'ông oh, mở tủ thuốc, điều kiện', '오 약사, 약장, 조건')
S('yerin_kham_nhanh_ca_ba_nguoi', ['P140'], 'C', False, 'Trung cảnh', ['Yerin'],
  f'Yerin ({YR}) khám nhanh lần lượt từng người: {OH} không có thương tích; {IN} chỉ bị xước một bên tay. {BG3["thuoc"]}', None,
  'yerin khám, thực tập sinh, dược sĩ', '한예린 진찰, 실습생, 약사')
S('nguoi_giao_hang_theo_phan_xa_rut_tay', ['P141', 'P142'], 'A', False, 'Cận cảnh', None,
  f'Cận cảnh {CO} theo phản xạ rụt cánh tay lại khi tới lượt khám, một cử động nhỏ mà bàn tay Yerin (đeo găng) vẫn bắt lấy. {BG3["thuoc"]}', None,
  'người giao hàng, rụt tay, yerin nhận ra', '배달 기사, 팔을 움츠리다, 예린')
S('dau_rang_sau_duoi_tay_ao_do_rach', ['P143'], 'A', True, 'Cực cận', None,
  'Cực cận một ống tay áo khoác đỏ bị rách và bên dưới là dấu răng sâu trên cánh tay; hình ảnh tiết chế, chỉ vết thâm đen, không máu đỏ.', None,
  'tay áo đỏ rách, dấu răng sâu', '찢어진 붉은 소매, 깊은 이빨 자국')
S('phong_im_bat_ca_nhom_nhin_vet_can', ['P144'], 'B', False, 'Cảnh rộng', None,
  f'Cả phòng thuốc im bặt, mọi ánh mắt dồn về cánh tay của {CO}; {OH}; {IN}; Taeho, Yerin, Areum, Jiwoo đứng rải rác. {BG3["thuoc"]}', None,
  'căn phòng im bặt, vết cắn', '방 안이 조용해지다, 물린 자국')
S('yerin_hoi_bi_can_tu_khi_nao', ['P145'], 'B', False, 'Cận mặt', Y,
  f'Cận mặt Yerin ({YR}) hỏi dồn, ánh mắt sắc: anh ta bị cắn từ khi nào?', None,
  'yerin, hỏi, bị cắn từ khi nào', '한예린, 언제 물렸는가')
S('nguoi_giao_hang_bao_nua_tieng_van_binh_thuong', ['P146'], 'B', False, 'Cận mặt', None,
  f'Cận mặt {CO} nói mới bị cắn nửa tiếng trước, chỉ cắn sượt, và khẳng định mình vẫn bình thường, nét mặt lo âu.', None,
  'người giao hàng, nửa tiếng, vẫn bình thường', '배달 기사, 삼십 분 전, 멀쩡하다')
S('da_xam_tro_quanh_vet_can', ['P147'], 'A', False, 'Cực cận', None,
  'Cực cận vùng da quanh dấu răng đã chuyển sang màu xám tro, các tĩnh mạch đen mờ chạy lan ra; tiết chế, không máu đỏ.', None,
  'da xám tro, quanh vết cắn, lây nhiễm', '잿빛 피부, 물린 자국 주변')
S('taeho_da_thay_nguoi_bien_doi_khong_xem_nhe', ['P148'], 'C', False, 'Cận mặt', T,
  'Cận mặt Taeho nhớ lại những người nhiễm bệnh biến đổi mà anh từng thấy; anh biết không thể xem nhẹ vết cắn đó.', None,
  'taeho, đã thấy biến đổi, không xem nhẹ', '태호, 변하는 모습을 보다')
# ---- P149-P158: tranh luận, lên sân thượng
S('taeho_noi_phai_roi_di_truoc_khi_bien_doi', ['P149'], 'A', False, 'Trung cảnh', ['Taeho', 'Yerin'],
  f'Taeho nói với Yerin phải rời đi trước khi anh ta biến đổi, mặt cứng; Yerin ({YR}) đối diện anh, tay còn cầm hộp thuốc. {BG3["thuoc"]}', None,
  'taeho, phải rời đi, yerin phản đối', '태호, 떠나야 한다, 한예린')
S('yerin_khong_chiu_bo_lai_benh_nhan', ['P150'], 'A', False, 'Cận mặt', Y,
  f'Cận mặt Yerin ({YR}) lắc đầu, ánh mắt kiên quyết: cô không thể bỏ bệnh nhân lại.', None,
  'yerin, không bỏ bệnh nhân', '한예린, 환자를 두고 갈 수 없다')
S('yerin_van_chuan_bi_thuoc_nhu_giu_kiem_soat', ['P151'], 'B', False, 'Cận cảnh', Y,
  f'Cận cảnh bàn tay Yerin ({YR}) gói thuốc và băng gạc vào túi y tế đều đặn, như thể làm đúng quy trình thì giữ được mọi thứ trong tầm kiểm soát.', None,
  'yerin, chuẩn bị thuốc, quy trình', '한예린, 약을 챙기다')
S('areum_tien_den_ben_yerin_khong_thach_thuc', ['P152', 'P153'], 'B', False, 'Trung cảnh', ['Areum', 'Yerin'],
  f'Areum bước tới đứng cạnh Yerin ({YR}), lần này không nhìn Taeho bằng ánh mắt thách thức, chỉ nhắc rằng Jiwoo cần người chăm sóc. {BG3["thuoc"]}', None,
  'areum, bên cạnh yerin, jiwoo cần chữa', '서아름, 한예린 곁, 서지우')
S('yerin_nhin_jiwoo_roi_nhin_nguoi_giao_hang', ['P154'], 'A', False, 'Cảnh cắt hai hướng', ['Yerin', 'Jiwoo'],
  f'Ánh mắt Yerin ({YR}) chuyển giữa Jiwoo ({JWS}, ngồi dựa tường mặt tái đi) và {CO} đang cố giấu cánh tay; cảnh chia đôi cân bằng.', None,
  'yerin, giằng xé, jiwoo và người giao hàng', '한예린, 갈등, 서지우, 배달 기사')
S('yerin_quyet_dinh_chua_jiwoo_truoc_chua_hua', ['P155'], 'B', False, 'Trung cảnh', ['Yerin', 'Jiwoo'],
  f'Yerin ({YR}) quyết định chữa và cố định chân cho Jiwoo ({JWS}) trước; cô không hứa sẽ đưa ai đi cùng. {BG3["thuoc"]}', None,
  'yerin, chữa jiwoo trước, không hứa', '한예린, 서지우 먼저 치료')
S('thoi_gian_khong_nhieu_dong_ho_tuong', ['P156'], 'C', False, 'Cận cảnh', None,
  'Cận cảnh chiếc đồng hồ kim treo tường trong phòng thuốc dưới ánh đèn khẩn cấp, kim giây trôi: thời gian không còn nhiều.', ['똑딱'],
  'đồng hồ, thời gian, không còn nhiều', '벽시계, 시간이 없다')
S('nhom_len_cau_thang_san_thuong_oh_dan_duong', ['P157'], 'A', False, 'Cảnh dọc cầu thang', None,
  f'Cả nhóm leo lên cầu thang tới sân thượng, {OH} và {IN} đi trước dẫn đường, Taeho và Yerin dìu Jiwoo ({JWS}), người giao hàng áo đỏ đi cuối một tay ôm chặt cánh tay, Areum đi sau cùng. {BG3["cau_thang"]}', None,
  'lên sân thượng, cầu thang, người giao hàng cuối', '옥상, 계단, 배달 기사 맨 뒤')
S('taeho_di_gan_nguoi_giao_hang_nhat', ['P158'], 'B', False, 'Trung cảnh', ['Taeho'],
  f'Taeho đi gần {CO} nhất trên cầu thang, mắt không rời cánh tay bị thương của anh ta. {BG3["cau_thang"]}', None,
  'taeho, đi gần người giao hàng', '태호, 가장 가까이, 배달 기사')
# ---- P159-P176: biến đổi
S('hoi_tho_khac_la_khoe_khoe_trong_co', ['P159'], 'B', False, 'Cận mặt', None,
  f'Cận mặt {CO} thở gấp, ngắn và nông, trong cổ họng vang tiếng khò khè, mồ hôi chảy trên trán; ánh đèn khẩn cấp xanh nhạt. {BG3["cau_thang"]}', ['쌕쌕'],
  'người giao hàng, thở khò khè', '배달 기사, 쌕쌕거림')
S('nguoi_giao_hang_do_sup_xuong_cau_thang', ['P160', 'P161'], 'A', False, 'Cảnh hành động', None,
  f'{CO} đột ngột đổ sụp xuống bậc cầu thang, Taeho vừa quay lại; cô thực tập sinh ({IN}) bịt miệng hét lên. {BG3["cau_thang"]}', ['쿵!', '꺄악!'],
  'người giao hàng ngã, thực tập sinh hét', '배달 기사가 쓰러지다, 비명')
S('nguoi_giao_hang_chong_tay_dung_day_dau_lech', ['P162', 'P163'], 'A', False, 'Cận cảnh', ['Giao Hàng'],
  f'Sau vài giây bất động, KẺ LANG THANG biến thể NHÂN VIÊN GIAO HÀNG chống tay đứng dậy trên cầu thang, đầu lệch sang một bên, miệng há ra, mắt không còn nhìn thấy gì. {BG3["cau_thang"]}', None,
  'người giao hàng biến đổi, đầu lệch', '배달 기사 변이, 고개가 꺾이다')
S('lao_thang_ve_phia_yerin', ['P164'], 'A', False, 'Cảnh hành động', ['Giao Hàng', 'Yerin'],
  f'KẺ LANG THANG biến thể NHÂN VIÊN GIAO HÀNG lao thẳng về phía Yerin ({YR}) đang đứng sát cầu thang. {BG3["cau_thang"]}', ['크아악!'],
  'lao vào yerin, người giao hàng', '예린에게 달려들다, 배달 기사')
S('khoang_cach_qua_gan_areum_khong_kip_giuong_cung', ['P165'], 'B', False, 'Trung cảnh', A,
  f'Areum đứng sau với cây cung nửa giương, nhưng khoảng cách quá gần, cô không có thì giờ kéo dây; gương mặt hoảng hốt. {BG3["cau_thang"]}', None,
  'areum, quá gần, không kịp giương cung', '서아름, 너무 가깝다')
S('taeho_lao_toi_chan_ngang_ghi_vao_tuong', ['P166'], 'A', False, 'Cảnh hành động', ['Taeho', 'Giao Hàng'],
  f'Taeho lao vào giữa chặn ngang đường tấn công và ghì KẺ LANG THANG biến thể NHÂN VIÊN GIAO HÀNG vào tường, hai tay giữ chặt cánh tay hắn. {BG3["cau_thang"]}', ['쾅!'],
  'taeho, ghì vào tường, chặn tấn công', '태호, 벽으로 밀치다')
S('hai_ban_tay_quo_ve_co_taeho', ['P166'], 'B', False, 'Cận cảnh', ['Taeho', 'Giao Hàng'],
  'Cận cảnh hai bàn tay của KẺ LANG THANG quờ về phía cổ Taeho, Taeho nghiêng người tránh, gương mặt hai bên sát nhau.', None,
  'bàn tay quờ cổ, taeho tránh', '목을 향한 손, 태호')
S('taeho_xoay_nguoi_tranh_cu_can', ['P167'], 'A', False, 'Cận cảnh hành động', ['Taeho', 'Giao Hàng'],
  'Taeho xoay người né cú cắn trong gang tấc, hàm răng của KẺ LANG THANG khép lại vào khoảng không bên vai anh.', ['딱!'],
  'taeho, né cú cắn, gang tấc', '태호, 물기를 피하다')
S('dao_dam_vao_gay_ket_thuc', ['P167', 'P168'], 'A', False, 'Cận cảnh', ['Taeho', 'Giao Hàng'],
  'Taeho dùng dao quân dụng đâm vào gáy KẺ LANG THANG biến thể NHÂN VIÊN GIAO HÀNG; hình ảnh tiết chế, chỉ bóng đen và vệt ánh kim loại, chất dịch đen sẫm loãng, cơ thể mềm xuống.', ['푹!'],
  'đâm vào gáy, kết thúc, cơ thể mềm xuống', '목덜미를 찌르다, 늘어지다')
S('taeho_giu_them_vai_giay_xac_nhan', ['P169'], 'C', False, 'Cận mặt', T,
  'Cận mặt Taeho vẫn giữ chặt xác trong vài giây, chờ chắc chắn không còn cử động rồi mới buông tay.', None,
  'taeho, giữ thêm, xác nhận', '태호, 확인하다, 손을 놓다')
S('khong_ai_len_tieng_tren_cau_thang', ['P170'], 'C', False, 'Cảnh rộng', None,
  f'Không ai lên tiếng trên cầu thang: xác người giao hàng nằm dưới chân bậc thang, mọi người đứng sững nhìn xuống. {BG3["cau_thang"]}', None,
  'im lặng, xác dưới chân cầu thang', '침묵, 계단 아래 시신')
S('yerin_nhin_xac_roi_nhin_con_dao_trong_tay_taeho', ['P171', 'P172'], 'A', False, 'Cảnh cắt hai hướng', ['Yerin', 'Taeho'],
  f'Yerin ({YR}) đứng cách vài bước, hai bàn tay cứng đờ, nhìn xác người giao hàng nằm dưới chân cầu thang rồi nhìn con dao trong tay Taeho; Taeho đứng đối diện. {BG3["cau_thang"]}', None,
  'yerin, nhìn con dao, hiểu nhưng không chấp nhận', '한예린, 칼을 보다')
S('yerin_noi_hay_bao_toi_truoc_khi_ket_thuc_mang_nguoi', ['P173', 'P174', 'P175'], 'A', False, 'Cận mặt', Y,
  f'Cận mặt Yerin ({YR}) nói khẽ, ánh mắt nghiêm khắc nhưng không có giận dữ: lần sau hãy báo cho cô trước khi quyết định kết thúc mạng sống của một bệnh nhân.', None,
  'yerin, hãy báo cho tôi trước', '한예린, 먼저 알려 달라')
S('taeho_khong_phan_bac_cui_dau_chiu', ['P176'], 'B', False, 'Cận mặt', T,
  'Cận mặt Taeho cúi nhìn xuống, không phản bác, chấp nhận lời của Yerin.', None,
  'taeho, không phản bác', '태호, 반박하지 않다')
# ---- P177-P184: sân thượng
S('nhom_buoc_len_san_thuong_gio_dem', ['P177'], 'A', False, 'Cảnh rộng', None,
  f'Cả nhóm bước ra sân thượng khu y tế trong gió đêm mạnh, tóc áo tung bay; Taeho, Yerin, Jiwoo ({JWS}), Areum, {OH}, {IN}. {BG3["thuong"]}', None,
  'sân thượng, gió đêm, cả nhóm', '옥상, 밤바람, 일행')
S('toan_canh_seoryeong_khoi_va_lua_nho', ['P178'], 'A', True, 'Toàn cảnh', None,
  'Toàn cảnh thành phố Seoryeong nhìn từ sân thượng ban đêm dưới bầu trời đầy khói: những đám cháy nhỏ rải rác giữa các tòa nhà, xa hơn là những vùng tối nơi điện đã bị cắt hoàn toàn.', None,
  'toàn cảnh seoryeong, khói, lửa, vùng mất điện', '서령 전경, 연기, 불길, 정전')
S('ong_oh_va_thuc_tap_sinh_dung_canh_cua', ['P179'], 'B', False, 'Trung cảnh', None,
  f'{OH} và {IN} dừng lại bên cạnh cửa sân thượng, quay lại nhìn nhóm Taeho. {BG3["thuong"]}', None,
  'ông oh, thực tập sinh, cửa sân thượng', '오 약사, 실습생, 옥상 문')
S('hai_nguoi_quyet_dinh_o_lai_khoa_cua', ['P180'], 'B', False, 'Trung cảnh', None,
  f'{OH} và {IN} quyết định ở lại, sẽ khóa cửa từ bên trong và tiếp tục chờ trực thăng; họ không muốn trở thành gánh nặng cho nhóm đang phải dìu người gãy chân. {BG3["thuong"]}', None,
  'hai người ở lại, khóa cửa, chờ trực thăng', '두 사람이 남다, 문을 잠그다')
S('yerin_de_lai_bang_gac_va_ong_giam_dau_duy_nhat', ['P181'], 'A', False, 'Cận cảnh', ['Yerin'],
  f'Cận cảnh bàn tay Yerin ({YR}) đưa cho {IN} một nửa số băng gạc và ống thuốc giảm đau duy nhất; gương mặt cô nghiêm nghị.', None,
  'yerin, để lại băng gạc, thuốc giảm đau', '한예린, 붕대 절반, 진통제')
S('loi_hua_quay_lai_nhe_nhu_long', ['P181', 'P182', 'P183'], 'B', False, 'Cận mặt', ['Yerin', 'Taeho'],
  f'Cận mặt Yerin ({YR}) hứa sẽ quay lại nếu có cơ hội, Taeho đứng cạnh im lặng nhìn đi nơi khác; cả hai biết lời hứa nhẹ đến đâu trong thành phố này. {BG3["thuong"]}', None,
  'lời hứa quay lại, yerin, taeho', '돌아오겠다는 약속, 한예린, 태호')
S('ong_oh_dua_khang_sinh_va_den_pin_nho', ['P184'], 'B', False, 'Cận cảnh', Y,
  f'Cận cảnh {OH} đưa cho Yerin ({YR}) hai mươi viên kháng sinh trong túi giấy cùng một chiếc đèn pin nhỏ.', None,
  'ông oh, hai mươi viên kháng sinh, đèn pin', '오 약사, 항생제 스무 알, 손전등')
# ---- P185-P202: tin nhắn Minseo
S('dien_thoai_cua_yerin_rung_len', ['P185'], 'B', False, 'Cận cảnh', Y,
  f'Cận cảnh chiếc điện thoại trong tay Yerin ({YR}) rung lên và màn hình sáng giữa đêm trên sân thượng.', ['징—'],
  'điện thoại rung, yerin, sân thượng', '휴대전화 진동, 한예린')
S('tin_nhan_den_muon_tin_hieu_chap_chon', ['P186', 'P187'], 'A', False, 'Cận cảnh', Y,
  'Cận cảnh màn hình điện thoại sáng lên với một tin nhắn từ người gửi tên Minseo (chữ trên màn hình mờ, không đọc được), thanh sóng chập chờn.', None,
  'tin nhắn minseo, tín hiệu chập chờn', '민서의 문자, 신호 불안정')
S('yerin_doc_tin_roi_dua_dien_thoai_cho_taeho', ['P188'], 'B', False, 'Trung cảnh', ['Yerin', 'Taeho'],
  f'Yerin ({YR}) đọc tin nhắn một lần rồi đưa điện thoại cho Taeho, hai người đứng sát nhau trong gió đêm trên sân thượng. {BG3["thuong"]}', None,
  'yerin đưa điện thoại, taeho, tin nhắn', '한예린, 휴대전화를 건네다, 태호')
S('minseo_trong_ham_tau_dien_ngam_euljiro', ['P189', 'P190'], 'A', True, 'Cảnh minh họa', ['Minseo'],
  'Cảnh minh họa trong tâm tưởng: Minseo (áo blouse phòng thí nghiệm khoác ngoài áo ba lỗ trắng, kính nứt một tròng, hộp kim loại đựng mẫu đeo chéo) đứng trong đường hầm tàu điện ngầm tối ở khu Euljiro, ánh đèn khẩn cấp vàng yếu, đường ray kéo dài vào bóng tối.', None,
  'minseo, hầm tàu điện ngầm, euljiro', '이민서, 지하철 터널, 을지로')
S('canh_bao_dung_tin_quan_doi_dong_chu_cuoi', ['P191', 'P192'], 'A', False, 'Cận cảnh', None,
  'Cận cảnh màn hình điện thoại phát sáng trong đêm, dòng cuối cùng được làm nổi bật (chữ mờ, không đọc được), nhịp căng thẳng dồn nén.', None,
  'cảnh báo, đừng tin quân đội, dòng cuối', '경고, 군대를 믿지 마, 마지막 줄')
S('taeho_doc_lai_dong_cuoi_lau_hon_can_thiet', ['P193'], 'B', False, 'Cận mặt', T,
  'Cận mặt Taeho nhìn chăm chăm vào màn hình điện thoại lâu hơn cần thiết, ánh sáng xanh của màn hình hắt lên gương mặt.', None,
  'taeho, đọc lại dòng cuối', '태호, 마지막 문장을 오래 보다')
S('nui_cheonma_xa_xa_vien_nghien_cuu', ['P194', 'P195'], 'A', True, 'Toàn cảnh', None,
  'Toàn cảnh núi Cheonma ở ngoại ô phía bắc nhìn từ xa trong đêm, sườn núi tối với vài ánh đèn cơ sở nghiên cứu quân sự nhấp nháy đỏ giữa khói mỏng.', None,
  'núi cheonma, viện nghiên cứu, xa xa', '천마산, 연구소, 먼 풍경')
S('taeho_biet_nhieu_hon_nhung_gi_da_noi', ['P195'], 'B', False, 'Cận mặt', T,
  'Cận mặt Taeho với ánh mắt giấu nhiều điều, biết nhiều hơn những gì mình đã nói với nhóm.', None,
  'taeho, biết nhiều hơn, bí mật', '태호, 더 많이 알고 있다')
S('yerin_nhan_ra_phan_ung_cua_taeho_khong_hoi', ['P196'], 'B', False, 'Trung cảnh', ['Yerin', 'Taeho'],
  f'Yerin ({YR}) nhìn Taeho, nhận ra phản ứng của anh nhưng không hỏi và không ép anh phải giải thích. {BG3["thuong"]}', None,
  'yerin, nhận ra phản ứng, không hỏi', '한예린, 반응을 눈치채다')
S('yerin_noi_se_den_ga_euljiro', ['P197', 'P198'], 'B', False, 'Cận mặt', Y,
  f'Cận mặt Yerin ({YR}) nói sẽ đến ga Euljiro, việc tiếp theo cô sẽ tự quyết định khi tới đó.', None,
  'yerin, đến ga euljiro', '한예린, 을지로역으로 가다')
S('taeho_nhin_ve_phia_nam_con_duong_xa', ['P199'], 'B', False, 'Cảnh sau lưng', T,
  f'Taeho đứng ở mép sân thượng nhìn về phía nam thành phố, nơi con đường anh định đi vẫn nằm ngoài tầm mắt. {BG3["thuong"]}', None,
  'taeho, phía nam, mép sân thượng', '태호, 남쪽, 옥상 가장자리')
S('taeho_van_muon_roi_khoi_seoryeong', ['P200'], 'C', False, 'Cận mặt', T,
  'Cận mặt Taeho, ánh mắt vẫn còn thôi thúc rời khỏi Seoryeong ngay từ đầu.', None,
  'taeho, muốn rời thành phố', '태호, 서령을 떠나고 싶다')
S('taeho_dong_y_dua_yerin_den_euljiro', ['P201', 'P202'], 'A', False, 'Trung cảnh', ['Taeho', 'Yerin'],
  f'Taeho quay sang Yerin ({YR}) gật đầu: anh sẽ đưa cô tới Euljiro; hai người đứng trước nhóm và gió đêm thổi tung áo khoác. {BG3["thuong"]}', None,
  'taeho đồng ý, đưa yerin tới euljiro', '태호, 을지로까지 데려다주기로')
# ---- P203-P214: trực thăng
S('tieng_canh_quat_vong_den_tu_xa', ['P203'], 'B', False, 'Cảnh rộng', None,
  f'Tiếng cánh quạt trực thăng vọng đến từ phía xa trên bầu trời đêm, cả nhóm trên sân thượng ngoảnh về phía âm thanh; {OH} và {IN} bước tới lan can. {BG3["thuong"]}', ['두두두두'],
  'tiếng cánh quạt, xa xa, cả nhóm quay lại', '프로펠러 소리, 먼 곳')
S('truc_thang_quan_su_bay_thap_giua_toa_nha', ['P204'], 'A', True, 'Cảnh rộng hành động', None,
  'Một chiếc trực thăng quân sự bay thấp giữa các tòa nhà cao tầng trong đêm, đèn tìm kiếm quét ngang, khói thành phố cuộn dưới cánh quạt.', ['두두두두'],
  'trực thăng quân sự, bay thấp, đèn tìm kiếm', '군용 헬기, 저공비행, 탐조등')
S('den_tim_kiem_quet_qua_mai_nha_san_thuong', ['P204'], 'A', False, 'Cảnh rộng góc cao', None,
  f'Chùm đèn tìm kiếm của trực thăng quét qua các mái nhà rồi chiếu thẳng lên sân thượng nơi nhóm đang đứng, những cái bóng dài đổ trên sàn. {BG3["thuong"]}', None,
  'đèn tìm kiếm, mái nhà, sân thượng', '탐조등, 지붕, 옥상')
S('ong_oh_va_thuc_tap_sinh_chay_ra_lan_can_vay_tay', ['P205'], 'A', False, 'Cảnh hành động', None,
  f'{OH} và {IN} chạy tới lan can sân thượng, giơ cao hai tay vẫy lia lịa dưới ánh đèn tìm kiếm. {BG3["thuong"]}', None,
  'ông oh, thực tập sinh, vẫy tay', '오 약사, 실습생, 손을 흔들다')
S('yerin_ngang_len_cho_truc_thang_ha_do_cao', ['P205'], 'B', False, 'Cận mặt góc thấp', Y,
  f'Cận mặt Yerin ({YR}) ngẩng lên nhìn trực thăng, đôi mắt phản chiếu chùm đèn, chờ nó hạ độ cao.', None,
  'yerin, ngước lên, chờ trực thăng', '한예린, 올려다보다, 헬기')
S('truc_thang_khong_dung_lai_bay_qua', ['P206'], 'A', False, 'Cảnh rộng', None,
  f'Chiếc trực thăng quân sự không giảm độ cao mà bay thẳng qua sân thượng, bóng nó lướt qua đầu mọi người. {BG3["thuong"]}', ['두두두두'],
  'trực thăng bay qua, không dừng', '헬기가 멈추지 않다')
S('gio_canh_quat_quet_ngang_san_thuong', ['P207'], 'B', False, 'Cảnh hành động', None,
  f'Luồng gió từ cánh quạt quét ngang sân thượng làm áo tóc mọi người bay tung, vài mảnh giấy cuốn lên. {BG3["thuong"]}', ['휘이잉'],
  'gió cánh quạt, quét ngang sân thượng', '프로펠러 바람, 옥상')
S('den_tim_kiem_roi_di_huong_trung_tam_chay', ['P207', 'P208'], 'B', False, 'Cảnh rộng', None,
  'Đèn tìm kiếm lướt qua nhóm thêm lần nữa rồi trực thăng tiếp tục bay về phía trung tâm thành phố đang cháy, ánh lửa lan rộng; không có tín hiệu hạ cánh.', None,
  'đèn rời đi, trung tâm cháy, không hạ cánh', '탐조등이 떠나다, 도심 불길')
S('khong_ai_den_don_truc_thang_bien_mat', ['P209', 'P210'], 'A', False, 'Cảnh rộng', None,
  'Chiếc trực thăng nhỏ dần rồi khuất sau những tòa nhà cao tầng, chỉ còn lại ánh lửa và bầu trời đen: không có ai đến đón.', None,
  'trực thăng khuất, không ai đến đón', '헬기가 사라지다, 아무도 오지 않는다')
S('ong_oh_ha_tay_xuong_thuc_tap_sinh_dung_hinh', ['P211'], 'B', False, 'Trung cảnh', None,
  f'{OH} chậm rãi hạ hai tay xuống khỏi lan can, {IN} đứng chết lặng bên cạnh, cả hai quay lưng về phía trực thăng đã khuất. {BG3["thuong"]}', None,
  'ông oh hạ tay, thực tập sinh sững sờ', '오 약사가 손을 내리다')
S('yerin_nhin_theo_noi_noi_khong_co_so_tan', ['P212', 'P213'], 'A', False, 'Cận mặt', Y,
  f'Cận mặt Yerin ({YR}) nhìn theo hướng trực thăng khuất rất lâu rồi mới nói, ánh mắt nặng trĩu: không có cứu hộ nào cả.', None,
  'yerin, không có sơ tán, thất vọng', '한예린, 구조는 없다')
S('taeho_khong_tra_loi_da_thay_du', ['P214'], 'C', False, 'Cận mặt', T,
  'Cận mặt Taeho không đáp, đã thấy đủ để hiểu rằng không thể trông chờ vào việc được cứu.', None,
  'taeho, không trả lời, không trông chờ', '태호, 대답하지 않다')
# ---- P215-P224: kết
S('areum_mo_ong_ten_dem_lai_muoi_hai_mui', ['P215', 'P216'], 'A', False, 'Cận cảnh', A,
  'Cận cảnh Areum mở nắp ống tên và đếm lại các mũi tên còn lại: mười hai mũi; ánh đèn thành phố cháy hắt từ xa.', None,
  'areum, đếm mũi tên, mười hai', '서아름, 화살 수, 열두 발')
S('areum_dong_ong_ten_deo_cung_len_vai', ['P217'], 'B', False, 'Trung cảnh', A,
  f'Areum đóng nắp ống tên, đeo cung lên vai và bước về phía cầu thang, dáng quả quyết. {BG3["thuong"]}', None,
  'areum, đeo cung lên vai, đi về cầu thang', '서아름, 활을 메다, 계단')
S('taeho_do_jiwoo_dung_day_yerin_kiem_tui_thuoc', ['P218'], 'B', False, 'Trung cảnh', ['Taeho', 'Jiwoo', 'Yerin'],
  f'Taeho đỡ Jiwoo ({JWS}) đứng dậy, Yerin ({YR}) kiểm tra lại túi thuốc, chuẩn bị rời sân thượng. {BG3["thuong"]}', None,
  'taeho đỡ jiwoo, yerin kiểm tra túi thuốc', '태호, 서지우를 일으키다, 약 가방')
S('nhom_roi_san_thuong_khong_biet_co_den_duoc', ['P219'], 'B', False, 'Cảnh sau lưng', ['Taeho', 'Jiwoo', 'Yerin', 'Areum'],
  f'Bốn người bước về phía cửa cầu thang rời sân thượng, bóng họ đổ dài theo ánh lửa xa, không biết liệu có đến được Euljiro; Taeho, Jiwoo ({JWS}), Yerin ({YR}), Areum. {BG3["thuong"]}', None,
  'rời sân thượng, bốn bóng lưng', '옥상을 떠나다, 네 사람의 뒷모습')
S('ong_oh_dong_khoa_cua_san_thuong_phia_sau', ['P220'], 'A', False, 'Cận cảnh', None,
  f'Cận cảnh bàn tay {OH} gài chốt cánh cửa sân thượng từ phía trong, bản lề kim loại, ánh đèn khẩn cấp xanh nhạt trên khe cửa.', ['철컥'],
  'ông oh khóa cửa, sân thượng', '오 약사, 문을 잠그다')
S('canh_cua_ngan_cach_voi_hai_nguoi_cuoi_cung', ['P221'], 'B', False, 'Cảnh cắt', None,
  'Cánh cửa sân thượng khép chặt giữa khung hình: bên ngoài là cầu thang tối với bóng nhóm Taeho, bên trong khe cửa là hai bóng người sống sót cuối cùng của khu y tế.', None,
  'cánh cửa ngăn cách, hai người cuối cùng', '문, 마지막 생존자 두 사람')
S('cau_thang_toi_pho_dem_dan_zombie_va_tin_nhan', ['P222'], 'A', False, 'Cảnh rộng', None,
  f'Cầu thang tối dẫn xuống con phố đêm đầy xác sống ở xa, ánh đèn đường yếu, trên không là bầu trời khói nhuốm đỏ. {BG3["pho_dem"]}', None,
  'cầu thang tối, phố đầy zombie', '어두운 계단, 좀비 가득한 거리')
S('dem_dau_tien_van_chua_ket_thuc', ['P223'], 'C', True, 'Toàn cảnh', None,
  'Toàn cảnh thành phố Seoryeong ban đêm dưới bầu trời nhuốm đỏ, khói và lửa rải rác, báo hiệu đêm đầu tiên vẫn chưa kết thúc.', None,
  'đêm đầu tiên, seoryeong, chưa kết thúc', '첫날 밤, 서령, 끝나지 않았다')
S('taeho_nhan_ra_roi_thanh_pho_khong_con_don_gian', ['P224'], 'A', False, 'Cận mặt', T,
  'Cận mặt Taeho đứng trên cầu thang tối, ánh mắt thay đổi: anh bắt đầu nhận ra rời khỏi thành phố này không còn là một lựa chọn đơn giản như anh từng nghĩ; nền tối gần như đen.', None,
  'taeho, nhận ra, không còn đơn giản', '태호, 깨닫다, 단순한 선택이 아니다')

# ---- ghi file
rows = []
for i, sh in enumerate(SHOTS, 1):
    fn = f'{i:03d}_{sh["slug"]}.png'
    tags = ('ngay_tan, tap3, ko, ' + ('tai_su_dung, ' if sh['reuse'] else 'rieng_tap3, ') + f'uutien_{sh["pri"]}, '
            + sh['tvi'] + ', ' + sh['tko'])
    rows.append((fn, tags, make_prompt(sh['shot'], sh['names'], sh['text'], sh['sfx'])))

with open(D / 'ngay_tan_ep3_scenes_v3.csv', 'w', encoding='utf-8-sig', newline='') as f:
    w = csv.writer(f, lineterminator='\r\n')
    w.writerow(HDR)
    for i, (fn, tags, prompt) in enumerate(rows, 1):
        w.writerow([i, fn, tags, prompt])

first = {}
for line in open(D / 'scripts' / 'ko_ep3_check.txt', encoding='utf-8'):
    k, t = line.rstrip('\n').split('|', 1)
    first.setdefault(k.rsplit('-', 1)[0], t)

md = ['# Ngày Tàn — Tập 3: danh sách ảnh (shot list) đối chiếu lời đọc', '',
      f'{len(SHOTS)} ảnh, khoảng {int(1440 / len(SHOTS))} giây/ảnh (bản Hàn ~24 phút). Ưu tiên: **A** bắt buộc, **B** nên có, **C** tuỳ chọn. "Tái dùng" = dùng lại được ở tập khác. '
      'Đoạn = đoạn của `scripts/ko_ep3_check.txt` (P001..P224, bản Hàn là bản gốc). Chỉ tạo bản KO.', '',
      '| STT | File | Đoạn | Câu đầu của đoạn (KO) | Ưu tiên | Tái dùng | Có chữ hiệu ứng |', '|---|---|---|---|---|---|---|']
for i, sh in enumerate(SHOTS, 1):
    md.append(f'| {i} | {i:03d}_{sh["slug"]}.png | {", ".join(sh["pids"])} | {first.get(sh["pids"][0], "")} | {sh["pri"]} | {"có" if sh["reuse"] else "không"} | {"có" if sh["sfx"] else ""} |')
cnt = {p: sum(1 for s in SHOTS if s['pri'] == p) for p in 'ABC'}
md += ['', f'Tổng: A = {cnt["A"]}, B = {cnt["B"]}, C = {cnt["C"]}; tái dùng được: {sum(1 for s in SHOTS if s["reuse"])}; có chữ hiệu ứng: {sum(1 for s in SHOTS if s["sfx"])}.']
(D / 'ngay_tan_ep3_shotlist.md').write_text('\n'.join(md) + '\n', encoding='utf-8', newline='\n')

img_dir = D / 'ngay_tan_ep3_images'
img_dir.mkdir(exist_ok=True)
(img_dir / '.gitkeep').write_text('')
(img_dir / '_DANH_SACH_TEN_FILE.txt').write_text(
    'Ảnh Tập 3 (video dài 16:9) - lưu ảnh vào thư mục này với ĐÚNG tên file dưới đây (theo ngay_tan_ep3_scenes_v3.csv).\n\n'
    + '\n'.join(fn for fn, _, _ in rows) + '\n', encoding='utf-8', newline='\n')

bad = set()
for fn, tags, prompt in rows:
    for ch in tags + prompt:
        o = ord(ch)
        if 0xAC00 <= o <= 0xD7A3 or o < 0x250 or 0x1E00 <= o <= 0x1EFF or ch in '“”‘’—…·–~':
            continue
        bad.add((ch, hex(o)))
cov = sorted({p for s in SHOTS for p in s['pids']})
allp = sorted(first)
miss = [p for p in allp if p not in cov]
dup = [fn for fn in {r[0] for r in rows} if sum(1 for r in rows if r[0] == fn) > 1]
print(len(rows), 'ảnh; ký tự lạ:', bad, '; A/B/C', cnt, '; đoạn chưa có ảnh:', miss, '; trùng tên:', dup, '; max len', max(len(r[2]) for r in rows))
