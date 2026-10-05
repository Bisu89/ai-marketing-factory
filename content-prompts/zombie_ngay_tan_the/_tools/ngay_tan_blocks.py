"""Khối prompt cố định của series Ngày Tàn (phong cách, phủ định, khoá nhân vật/zombie, phông nền). Nguồn: IMAGE_SYSTEM.md."""
import csv, os, re


# ---------- khối cố định (copy nguyên văn từ IMAGE_SYSTEM.md) ----------
STYLE = ('Phong cách webtoon/manhwa Hàn Quốc, nét mực đen đậm sạch sẽ, tô màu phẳng 2D kiểu cel-shading, '
         'bóng đổ cứng cạnh, màu sắc rực rỡ bão hoà, bố cục điện ảnh. Tuyệt đối KHÔNG phong cách vẽ sơn dầu, '
         'KHÔNG anime bán thực, KHÔNG ảnh chụp thực tế, KHÔNG 3D render. Máu luôn là chất lỏng đen sẫm loãng '
         '(ichor), không bao giờ màu đỏ.')
RATIO = 'Tỷ lệ khung hình 16:9 ngang.'
NEG = ('PHỦ ĐỊNH: giải phẫu sai, thừa/thiếu ngón tay, mặt biến dạng, khoả thân, lộ ngực hoặc vùng nhạy cảm, '
       'tư thế gợi dục, phong cách sơn dầu, ảnh thực, anime bán thực, 3D, máu đỏ tươi, chữ, logo, watermark, '
       'ký hiệu lạ. PHỦ ĐỊNH BỔ SUNG: trẻ em, thiếu niên, nhân vật trông trẻ con.')
NEG_SHEET = NEG + ' Cắt mất đầu, cắt mất chân, thiếu bàn tay, góc nhìn méo mó.'

TAEHO = ('Kang Taeho, nam 32 tuổi, cao 1m87, vai rộng, thân hình săn chắc gọn gàng. Tóc đen ngắn kiểu undercut hơi rối. '
         'Mắt nâu đen, ánh nhìn sắc lạnh. Một vết sẹo ngắn cắt qua lông mày trái, râu lún phún quanh cằm. '
         'Dây thẻ quân nhân đeo ở cổ.')
TAEHO_DO1 = ('Áo thun đen bó sát, áo khoác dã chiến xanh ô-liu, quần túi hộp tối màu, ủng chiến đấu đen, găng hở ngón '
             'màu đen, balo quân dụng nhỏ trên lưng. Cầm dao găm chiến đấu.')
TAEHO_QP = ('Quân phục dã chiến thẳng thớm kèm quân hàm thượng sĩ trên vai, mũ nồi đen, tư thế đứng nghiêm.')
JIWOO = ('Seo Jiwoo, nữ 29 tuổi, cao 1m68, thân hình đồng hồ cát đầy đặn. Tóc nâu đậm gợn sóng dài, buộc đuôi ngựa thấp '
         'lỏng lẻo, vài sợi tóc rơi bên má. Gọng kính mảnh đẩy lên đầu. Mắt tròn hiền. Một nốt ruồi nhỏ dưới mắt trái.')
JIWOO_DO1 = ('Áo sơ mi trắng kem không tay, cổ áo hơi mở, váy bút chì màu nâu ngắn có đường xẻ cao bên đùi, tất lưới mỏng, '
             'giày bệt, túi xách vải đeo vai.')
YERIN = ('Han Yerin, nữ 30 tuổi, cao 1m72, dáng thon cao với đôi chân dài. Tóc đen cắt bob ngang cằm, mái lệch. '
         'Mắt mèo sắc sảo, biểu cảm lạnh lùng. Một nốt ruồi nhỏ dưới khoé môi bên phải. Ống nghe đeo quanh cổ.')
YERIN_DO1 = ('Áo scrub y tế xanh navy cổ V không tay, đã bị cắt ngắn và buộc nút vạt phía trước, áo blouse trắng khoác ngoài '
             'bị xé mất cả hai tay áo, quần lửng túi hộp màu xám, túi y tế đeo bên đùi.')
AREUM = ('Seo Areum, nữ 26 tuổi, cao 1m75, thể hình vận động viên cân đối, đôi chân dài săn chắc. Tóc nâu tro rất dài bện '
         'thành một bím dài buông sau lưng. Mắt hổ phách quyết đoán, biểu cảm tự tin hơi bướng.')
AREUM_DO1 = ('Áo crop thể thao đen ôm sát, bảo hộ cẳng tay trái màu đen có viền đỏ cam, găng ngón bắn cung, quần short '
             'thể thao đen, bó chân dài tới đùi, túi đựng tên đeo chéo sau lưng, cầm một cây cung thể thao.')
MINSEO = ('Lee Minseo, nữ 33 tuổi, cao 1m65, nhỏ nhắn nhưng đường cong rõ. Tóc bob ngắn màu đen nhuốm tím, hơi rối. '
          'Kính tròn gọng đen với một bên tròng bị nứt. Quầng thâm dưới mắt, vẻ mặt mệt mỏi và cảnh giác. '
          'Thẻ nhân viên phòng thí nghiệm đeo ở cổ.')
MINSEO_DO1 = ('Áo blouse phòng thí nghiệm màu trắng mở khoác ngoài áo ba lỗ trắng, quần short denim, giày thể thao, '
              'một hộp kim loại nhỏ đựng mẫu đeo chéo vai.')
CHOI = ('Đại tá Choi Gangsik, nam 50 tuổi, tóc muối tiêu cắt cua, gương mặt vuông nghiêm nghị, ánh mắt tính toán, '
        'quân phục xanh đậm chỉnh tề với huy hiệu đại tá, găng tay da đen.')
DAHEE = ('Baek Dahee, nữ 30 tuổi, tóc đen dài thẳng, trang điểm tinh tế, áo vest công sở màu be và chân váy ôm, '
         'vẻ mặt vừa lo lắng vừa cảnh giác.')
Z_LANGTHANG = ('Một zombie người trưởng thành đi lê bước, da xám nhợt có đường gân đen, mắt trắng đục, miệng hơi há, '
               'quần áo thường ngày rách bẩn, tư thế gù, hai tay buông thõng. Ichor đen sẫm loãng nhỏ giọt từ vết thương.')
Z_THECUONG = ('Một zombie đang lao chạy với tư thế thân người chúi về trước, tứ chi co giật, da xám nhợt gân đen nổi rõ, '
              'mắt trắng đục, miệng há rộng hung dữ, quần áo rách bươm. Ichor đen sẫm loãng bắn ra khi chạy.')
SUBJECT03 = ('Subject-03: một người lính trưởng thành thể hình rắn chắc, mặc đồ thử nghiệm màu xám nhạt, da xám nhợt gân '
             'đen nổi rõ, mắt trắng đục, đầu nghiêng như đang làm quen với cơ thể mình.')
ADULT_ONLY = 'Tất cả nhân vật trong ảnh đều là người trưởng thành.'

BG = {
    'chinh': 'Cổng chính khu quân sự Cheonma ban ngày, hàng rào thép gai, trạm gác, núi xanh phía sau, bầu trời xám.',
    'lab': 'Phòng thí nghiệm ngầm hiện đại, buồng kính chứa, đèn trần lạnh, thiết bị trắng xanh.',
    'lab_do': 'Phòng thí nghiệm ngầm hiện đại với đèn báo động đỏ, buồng kính vỡ, ống nghiệm đổ vỡ, ichor đen trên sàn.',
    'ham': 'Hầm dịch vụ bê tông chật hẹp, đường ống chạy dọc, đèn khẩn cấp vàng, cửa sắt nặng nề hé mở.',
    'vanh_dai': 'Đường cao tốc vành đai ngoại ô ban đêm, vài chiếc xe bỏ hoang, đèn đường vàng cam, sương mỏng.',
    'nha': 'Mặt tiền khu căn hộ cao cấp lúc chạng vạng, đèn cổng ấm, một chiếc xe quân đội màu đen đậu bên đường, mưa phùn.',
    'vp': 'Văn phòng chỉ huy quân đội, bàn gỗ lớn, bản đồ quân sự trên tường, cờ quốc gia, rèm cửa tối.',
}


def build(scene, chars='', extra=''):
    parts = [scene]
    if chars:
        parts.append(chars)
    parts.append(ADULT_ONLY)
    parts += [STYLE, RATIO, NEG] if not extra else [STYLE, RATIO, extra]
    return ' '.join(parts)


def sheet(char, outfit, extra_view='ba góc nhìn (chính diện, nghiêng, sau lưng) xếp cạnh nhau'):
    return (f'{STYLE} Bảng thiết kế nhân vật: {char} {outfit} Đứng thẳng toàn thân nhìn thẳng, phông nền trắng trơn, '
            f'{extra_view}, thấy rõ bàn tay và bàn chân. {RATIO} {NEG_SHEET}')


