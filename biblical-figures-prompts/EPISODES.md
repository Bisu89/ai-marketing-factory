# Biblical Figures — ghi chú 15 tập

Ghi chú nội dung cho từng tập, để viết spec (`biblical_figures_epN_spec.json`) nhanh hơn và
để loạt không bị trùng chất liệu giữa các tập. Trạng thái tổng quan + quy trình nằm ở
[SERIES.md](SERIES.md); quy tắc kỹ thuật (style ảnh, reuse, giới hạn) nằm ở [RULES.md](RULES.md).

Mỗi tập: **góc nhìn/hook** — **đã ghi chép** (Kinh Thánh + sử gia ngoài đạo như Josephus, Tacitus,
Philo) — **truyền thống/truyền thuyết** (hậu thế, không có trong văn bản gốc) — **nhân vật mới cần
thêm vào `bf_style.py`** — **tận dụng được gì từ kho ảnh**.

---

## 1. Judas Iscariot ✅ ĐÃ LÀM

30 pieces of silver, nụ hôn ở Gethsemane, hai cách kể khác nhau về cái chết (Matthew vs Acts), Phúc
Âm Judas (Gnostic, 2006). Phong cách ảnh: "cinematic" (đợt đầu, đã đổi từ tập 2).
Project 109 (dài, 12:47) / 104 (short). Nhân vật: J, JC (bản che mặt).

## 2. Pontius Pilate ✅ ĐÃ LÀM

Viên đá Caesarea (1961) xác nhận ông có thật, vụ cờ hiệu, cống dẫn nước, phiên xử, rửa tay, bị
triệu về Rome vì vụ Samaria, truyền thuyết hồ trên núi Pilatus. Phong cách đổi sang "painting" rồi
"mini_low" (ảnh do app tự tạo). Project 119 (dài, 12:40) / 120 (short, ảnh cinematic cũ).
Nhân vật: P, C (Caiaphas).

## 3. Mary Magdalene ✅ ĐÃ LÀM

Có mặt ở cả 4 Phúc Âm lúc đóng đinh, người đầu tiên thấy mộ trống, "Apostle to the Apostles". Huyền
thoại "gái mại dâm" do bài giảng Giáo hoàng Gregory năm 591 tạo ra, Vatican rút lại 1969. Phúc Âm
Mary (Gnostic), truyền thuyết Pháp/hang ẩn tu, thuyết "vợ của Chúa Giêsu" (Da Vinci Code, đã bác bỏ).
Project 126 (dài, 9:58) / 127 (short). Nhân vật: MM.

## 4. Simon Peter ✅ ĐÃ LÀM

Đi trên mặt nước, được gọi Messiah rồi bị gọi Satan trong cùng cuộc nói chuyện, 3 lần chối Chúa,
phục hồi bên hồ Galilee, Lễ Ngũ Tuần, rửa tội Cornelius (mở đạo cho dân ngoại), xung đột với Paul ở
Antioch. Truyền thống: Rome, "Quo Vadis", tử đạo lộn ngược dưới Nero, xương cốt Vatican 1968.
Project 143 (dài, 9:45) / 144 (short). Nhân vật: PT, PL (Paul, để dành tập 5).

---

## 5. Paul of Tarsus — "Kẻ bắt đạo trở thành người truyền đạo khắp đế chế" ✅ ĐÃ LÀM

Stephen bị ném đá (Saul giữ áo), cải đạo trên đường Damascus, Ananias, 3 hành trình truyền giáo,
Lystra tưởng là thần, va chạm với Peter ở Antioch (nối mạch tập 4), Areopagus ở Athens, bạo loạn
Ephesus, kháng cáo lên Caesar, đắm tàu ở Malta, giam lỏng ở Rome (Acts dừng ở đây). Truyền thống:
chém đầu dưới Nero, mộ tại San Paolo fuori le Mura; tranh luận học thuật 7 thư thật/6 thư nghi ngờ.
Project 146 (dài, 9:00) / 145 (short). Nhân vật mới (chỉ tập này): Barnabas, Ananias.

## 6. John the Baptist — "Người dọn đường, bị chặt đầu vì một điệu nhảy"

**Hook:** Ông làm phép rửa cho chính Chúa Giêsu. Vài tháng sau, đầu ông nằm trên một cái mâm.
**Đã ghi chép:** sinh ra muộn màng (cha mẹ già — Luke), sống khổ hạnh trong sa mạc, rao giảng ăn năn,
làm phép rửa cho Jesus ở sông Jordan, công khai chỉ trích Herod Antipas cưới vợ của anh trai mình
(Herodias), bị bỏ tù, bị chặt đầu vì lời hứa của Herod với con gái Herodias sau điệu nhảy (Mark
không nêu tên cô, Josephus và truyền thống sau gọi là Salome).
**Nguồn ngoài Kinh Thánh — điểm nhấn của tập:** Josephus (Antiquities 18.116-119) xác nhận việc John
bị giết, nhưng ghi lý do khác: Herod sợ ảnh hưởng chính trị của ông, không nhắc gì tới điệu nhảy hay
Herodias. Hai nguồn, hai động cơ — trình bày song song, không chọn phe.
**Truyền thống:** đầu John được chôn/thờ ở nhiều nơi khác nhau (Damascus, Amiens...) — ví dụ tốt cho
việc "thánh tích giả" nở rộ thời Trung Cổ.
**Nhân vật mới:** JB (John the Baptist), HA (Herod Antipas đã có từ ep2), Herodias, con gái bà
(Salome — không đặt tên trong lời kể nếu theo sát Mark, chỉ gọi "con gái của Herodias").
**Tận dụng kho:** `herod_antipas_mocking` (ep2, đổi bối cảnh), `galilee_boat_dawn`/sông hồ (ep4).
**Lưu ý:** đầu trên mâm — chỉ vẽ cái mâm phủ khăn hoặc cảnh trước/sau, không vẽ trực tiếp.

## 7. Caiaphas — "Vị thầy tế tại vị lâu nhất, người quyết định số phận Chúa Giêsu"

**Hook:** Mọi vị thầy tế trước và sau ông đều bị La Mã phế truất trong vài năm. Ông tại vị 18 năm.
**Đã ghi chép:** con rể của Annas (thầy tế trước đó, vẫn có quyền lực ngầm), chủ trì phiên tòa tôn
giáo xử Jesus, câu nói "thà một người chết thay cho dân" (John 11:50) — đọc như toan tính chính trị
lạnh lùng hơn là ác ý cá nhân, giữ được ghế suốt 10 năm cai trị của Pilate (ep2 đã nhắc) nhờ biết
"làm việc" với La Mã.
**Khảo cổ — điểm nhấn:** năm 1990, một hộp xương (ossuary) khắc tên "Yehosef bar Qayafa" được tìm
thấy ở Jerusalem, được nhiều học giả coi là của chính Caiaphas — một trong số ít nhân vật Phúc Âm có
bằng chứng khảo cổ gần như chắc chắn.
**Tranh luận:** ông là kẻ ác tâm hay chỉ là một chính trị gia tôn giáo cố giữ hòa bình mong manh với
La Mã để tránh thảm sát? Trình bày cả hai cách đọc.
**Nhân vật mới:** C đã có. Cần thêm: Annas (bố vợ).
**Tận dụng kho:** `caiaphas_portrait`, `caiaphas_pilate_meeting` (ep2), `jesus_before_caiaphas` (ep3).

## 8. Herod Antipas — "Kẻ giết người báo tin, chế giễu người được báo trước"

**Hook:** Ông xử tử người loan báo. Vài năm sau, người được loan báo đứng trước mặt ông, và ông chỉ
cười nhạo.
**Đã ghi chép:** con trai Herod Đại Đế, cai trị Galilee và Perea gần 43 năm (ổn định bất thường so
với anh em mình), chặt đầu John the Baptist, Pilate gửi Jesus sang cho ông xét xử vì Jesus là người
Galilee (Luke), ông và lính của mình chế giễu Jesus rồi trả lại cho Pilate, xây thành Tiberias.
**Josephus bổ sung:** trận thua quân đội trước vua Aretas của Nabatea — Josephus ghi rằng nhiều người
Do Thái thời đó coi đó là "trừng phạt của trời" vì tội giết John.
**Kết cục:** bị vợ Herodias xúi giục xin hoàng đế Caligula phong vương (như cháu mình, Herod
Agrippa I, vừa được phong), nhưng bị tố cáo phản nghịch, mất hết và bị đày sang Gaul (Pháp ngày nay),
chết trong lưu đày.
**Nhân vật mới:** HA đã có (ep2). Cần thêm: Herodias, Aretas (chỉ 1 cảnh).
**Tận dụng kho:** `herod_antipas_mocking` (ep2) dùng lại nguyên, `jerusalem_dusk_panorama`.

## 9. Thomas "Doubting Thomas" — "Người không tin, trở thành vị thánh của cả một tiểu lục địa"

**Hook:** Cả thế giới nói về Judas. Rất ít người biết Thomas có thể là tông đồ đi xa nhất — tới tận
Ấn Độ.
**Đã ghi chép:** đòi chạm vào vết thương của Chúa phục sinh mới tin (John 20) — nguồn gốc cụm từ
"doubting Thomas" trong tiếng Anh; trước đó, khi Jesus quyết định quay lại Judea nguy hiểm để thăm
Lazarus, chính Thomas là người nói "chúng ta cũng đi chết với Thầy" (John 11:16) — một Thomas dũng
cảm, trái ngược hình ảnh "kẻ hoài nghi" sau này.
**Truyền thống mạnh — trọng tâm tập:** Acts of Thomas (thế kỷ 3) kể ông truyền giáo tới Ấn Độ. Điều
đặc biệt: cộng đồng Kitô hữu Thánh Thomas (Saint Thomas Christians) ở Kerala, Ấn Độ, vẫn tồn tại thật
đến ngày nay, tự nhận gốc gác từ ông — một trong số ít "truyền thuyết" có hậu duệ sống thật kiểm
chứng được phần nào qua dân tộc học/khảo cổ (di tích cảng cổ Muziris giao thương với La Mã).
**Nhân vật mới:** TH (Thomas).
**Tận dụng kho:** hầu hết cảnh Ấn Độ là ảnh mới, nhưng phần đầu (Jerusalem, mộ, các tông đồ) dùng lại
nhiều từ ep3/ep4 (`mm_stone_rolled_tomb`, `gardener_figure_from_behind`...).

## 10. James, Brother of Jesus — "Người anh em không tin, rồi lãnh đạo cả giáo hội Jerusalem"

**Hook:** Phúc Âm nói các anh em của Jesus không tin ông. Vài năm sau, một trong số họ đứng đầu giáo
hội tại chính Jerusalem.
**Tranh luận học thuật cần trung lập:** "anh em" (brothers) của Jesus — con ruột khác của Mary
(quan điểm Tin Lành phổ biến), anh em họ (quan điểm Công giáo truyền thống, dựa trên cách dùng từ
Aramaic/Hebrew rộng hơn), hay con riêng của Joseph từ cuộc hôn nhân trước (quan điểm Chính Thống
giáo) — trình bày cả ba, không chọn phe, đúng tinh thần series.
**Đã ghi chép:** Mark 3:21 gợi ý gia đình Jesus từng nghĩ ông "mất trí"; 1 Corinthians 15:7 nói Jesus
phục sinh hiện ra riêng với James — có thể là bước ngoặt khiến ông tin; trở thành lãnh đạo giáo hội
Jerusalem (Acts 15, Galatians 1-2), được Paul gọi là một trong ba "cột trụ".
**Nguồn ngoài Kinh Thánh — điểm nhấn:** Josephus (Antiquities 20.200) ghi lại cái chết của ông — bị
thầy tế mới lợi dụng khoảng trống quyền lực La Mã để ném đá chết năm 62 — một trong những ghi chép
độc lập hiếm hoi và sớm nhất về một nhân vật Tân Ước ngoài chính sử liệu Kitô giáo.
**Nhân vật mới:** JM (James).
**Tận dụng kho:** `jesus_before_caiaphas`/Jerusalem Temple images từ ep2-4.

## 11. Barabbas — "Người được thả thay vì Chúa Giêsu — rồi biến mất khỏi lịch sử"

**Hook:** Đám đông chọn thả ông thay vì Jesus. Sau khoảnh khắc đó, không một dòng nào khác nhắc đến
ông nữa.
**Góc nhìn đặc biệt của tập này:** đây là tập về **một khoảng trống lịch sử**, không phải một tiểu
sử — phù hợp làm tập "đổi gió" sau 10 tập đầy ắp sự kiện. Nội dung xoay quanh việc cố gắng dựng lại
chân dung một người gần như không để lại dấu vết gì.
**Đã ghi chép:** bị giam vì tham gia một cuộc nổi dậy có đổ máu (Mark 15:7 — Luke gọi là "một cuộc
nổi loạn trong thành"); tên "Barabbas" trong tiếng Aramaic nghĩa đen là "con của người cha" (bar-
abba) — một số bản chép tay cổ của Matthew còn ghi tên đầy đủ là "Jesus Barabbas", khiến sự lựa chọn
của đám đông mang tính biểu tượng kỳ lạ: Jesus Barabbas hay Jesus gọi là Christ.
**Tranh luận học thuật:** phong tục "thả một tù nhân dịp lễ Vượt Qua" không có bất kỳ ghi chép La Mã
nào khác xác nhận — nhiều sử gia nghi ngờ tính lịch sử của chi tiết này (đã nhắc sơ qua ở ep2, tập
này đào sâu).
**Nhân vật mới:** B (Barabbas) đã có từ ep2.
**Tận dụng kho:** `barabbas_in_chains` (ep2) dùng lại, `crowd_courtyard_shouting` (ep2).

## 12. Nicodemus & Joseph of Arimathea — "Hai môn đệ bí mật"

**Hook:** Cả hai đều là thành viên hội đồng tối cao từng kết án Chúa Giêsu. Cả hai đều âm thầm là
môn đệ của ông.
**Lý do gộp chung một tập:** cả hai xuất hiện cùng nhau ở đúng một cảnh (an táng Jesus, John 19:39-
42), vai trò tương tự nhau (thành viên Sanhedrin, tin bí mật), và riêng lẻ mỗi người không đủ chất
liệu Kinh Thánh cho một tập 10-15 phút.
**Nicodemus — đã ghi chép:** đến gặp Jesus ban đêm (John 3 — "phải được sinh ra lần nữa"), sau đó
công khai bênh vực quyền được xét xử công bằng cho Jesus trước chính hội đồng của mình (John 7:50-
51).
**Joseph of Arimathea — đã ghi chép:** thành viên giàu có của Sanhedrin, xin Pilate thi thể Jesus,
hiến ngôi mộ mới của chính mình.
**Truyền thuyết (trọng tâm phần sau của tập):** truyền thuyết Anh thời Trung Cổ nói Joseph mang Chén
Thánh (Holy Grail) tới Glastonbury, trồng cây táo gai nở hoa vào Giáng Sinh — không có nguồn nào sớm
hơn thế kỷ 12-13, một ví dụ rõ về "truyền thuyết sinh ra để phục vụ một địa phương/tu viện cụ thể".
**Nhân vật mới:** NC (Nicodemus), JA (Joseph of Arimathea).
**Tận dụng kho:** cảnh an táng có thể dựng mới dựa trên `mm_watching_burial` (ep3) đổi góc nhìn.

## 13. Mary, Mother of Jesus — "Người phụ nữ cả ba nhánh Kitô giáo đều tôn kính, nhưng không đồng ý về bà"

**Hook:** Hàng trăm triệu người cầu nguyện với tên bà mỗi ngày. Nhưng Công giáo, Chính Thống giáo và
Tin Lành không đồng ý về gần như mọi điều ngoài những dòng ít ỏi trong Kinh Thánh.
**Cẩn trọng đặc biệt:** đây là tập nhạy cảm nhất của series — cần giữ đúng tinh thần "lịch sử/văn
hóa, trung lập giáo phái" nghiêm ngặt hơn bất kỳ tập nào khác. Mọi tín điều (Vô Nhiễm Nguyên Tội,
Đồng Trinh Trọn Đời, Mông Triệu) trình bày như **tín điều của một số nhánh**, không phải sự thật lịch
sử đã xác lập.
**Đã ghi chép (ít ỏi):** truyền tin (Luke 1), sinh Jesus ở Bethlehem, trốn sang Ai Cập (Matthew 2),
tìm thấy Jesus 12 tuổi giảng đạo trong Đền Thờ, có mặt ở tiệc cưới Cana, có mặt dưới chân thập giá
(chỉ John ghi lại chi tiết này), có mặt cùng các môn đệ sau khi Jesus lên trời (Acts 1:14) — rồi
biến mất khỏi văn bản.
**Khác biệt giáo phái (trình bày song song, không chọn phe):** Công giáo/Chính Thống tin bà đồng
trinh trọn đời bất chấp các "anh em của Jesus" được nhắc tới (xem tập 10); phần lớn Tin Lành đọc theo
nghĩa đen là bà có thêm con sau Jesus. Công giáo tin tín điều Mông Triệu (1950) và Vô Nhiễm Nguyên
Tội (1854) — cả hai đều được công bố rất muộn, nhiều thế kỷ sau thời bà sống.
**Nhân vật mới:** MO (Mary, mẹ Jesus) — khác MM (Mary Magdalene), cần thiết kế rõ ràng tránh nhầm.
**Tận dụng kho:** `pt_at_crucifixion_distance`-kiểu cảnh (ep3/ep4) cho đoạn dưới chân thập giá.

## 14. Herod the Great — "Vị vua xây dựng vĩ đại nhất, và nghi vấn gây tranh cãi nhất"

**Hook:** Ông xây nên Đền Thờ mà cả series này liên tục quay lại. Phúc Âm nói ông ra lệnh thảm sát
trẻ sơ sinh để giết một đứa bé.
**Đã ghi chép (Josephus — nguồn sử liệu chính, phong phú nhất cho bất kỳ nhân vật nào trong series):**
được La Mã phong vương dù không phải dòng dõi Do Thái thuần (gốc Idumea), xây lại Đền Thờ Jerusalem ở
quy mô khổng lồ, xây Caesarea Maritima (đã nhắc ở ep2) và pháo đài Masada, cực kỳ đa nghi cuối đời —
xử tử vợ yêu Mariamne và ba người con trai của chính mình vì nghi phản nghịch (hoàng đế Augustus được
cho là từng nói đùa cay đắng: "thà làm con lợn của Herod còn hơn làm con trai ông ta").
**"Thảm sát trẻ sơ sinh Bethlehem" (Matthew 2) — trọng tâm tranh luận của tập:** không được bất kỳ
nguồn nào khác, kể cả Josephus (vốn ghi chép rất chi tiết và không ngại bêu xấu Herod), xác nhận. Nhiều
sử gia đọc đây là một chi tiết mang tính biểu tượng/văn học (gợi lại Pharaoh và Moses) hơn là sự kiện
lịch sử riêng biệt; số khác lưu ý Bethlehem khi đó là một làng rất nhỏ, có thể chỉ liên quan vài chục
trẻ — việc Josephus không nhắc không hẳn là bằng chứng phủ định. Trình bày cả hai hướng.
**Ngôi sao Bethlehem:** các giả thuyết thiên văn (hợp tinh Jupiter-Saturn) trình bày như giả thuyết.
**Nhân vật mới:** HG (Herod Đại Đế) — khác HA (Herod Antipas, con trai ông).
**Tận dụng kho:** `temple_courts_wide`, `caesarea_harbor_wide` (ep2) — chính ông là người xây hai nơi
đó, một sự kết nối tự nhiên hay cho tập này.

## 15. Stephen, the First Martyr — "Người tử đạo đầu tiên, dưới ánh mắt của Paul tương lai"

**Hook:** Một chàng trai trẻ đứng giữ áo cho đám đông, gật đầu tán thành. Vài năm sau, chính anh ta
viết nên phần lớn Tân Ước.
**Đã ghi chép (Acts 6-7, nguồn gần như duy nhất):** một trong bảy người đầu tiên được giao nhiệm vụ
"chấp sự" (phục vụ bàn ăn cho các góa phụ) trong cộng đồng Kitô hữu sơ khai; bị tố cáo báng bổ, bài
diễn thuyết dài nhất trong sách Acts trước hội đồng Sanhedrin tóm tắt lại toàn bộ lịch sử Do Thái; bị
kéo ra ngoài thành ném đá chết — cái chết đầu tiên của một Kitô hữu vì đức tin; Acts 7:58 ghi rõ một
thanh niên tên Saul đứng canh áo cho những người ném đá, "đồng tình với việc giết ông" (Acts 8:1) —
chính là Paul của tập 5.
**Vai trò trong series:** tập khép lại vòng — nối thẳng về tập 5 (Paul), hoàn thiện mạch "đàn áp sinh
ra truyền giáo". Có thể cân nhắc làm tập cuối mùa 1 hoặc đặt sớm hơn, ngay sau tập Paul, để khán giả
thấy rõ liên kết nhân quả.
**Nhân vật mới:** ST (Stephen). Paul (PL) xuất hiện lại, trẻ hơn — cân nhắc giữ cùng gương mặt cho
nhất quán dù câu chuyện này xảy ra trước tập 5.
**Tận dụng kho:** `pt_before_sanhedrin` (ep4, cùng bối cảnh hội đồng) đổi nhân vật, `jerusalem_dusk_panorama`.

---

## Ghi chú chung khi viết spec

- Nhân vật xuất hiện lại từ tập trước (Caiaphas, Herod Antipas, Barabbas, Paul...) đã có sẵn "character
  bible" trong `_tools/bf_style.py` — không viết lại, chỉ cần chọn đúng khóa ký tự.
- Mỗi tập mới nên rà `_pool/pool.csv` lọc `style=mini_low` và `reuse=any` hoặc đúng nhân vật, trước khi
  viết beat "new" — càng về sau kho càng lớn, chi phí ảnh mới càng giảm.
- Thứ tự trên **không bắt buộc phải làm tuần tự** — tập 15 (Stephen) hợp lý nhất nếu làm ngay sau tập 5
  (Paul) để giữ mạch nhân quả; tập 11 (Barabbas) hợp làm tập "nhẹ" xen giữa hai tập nặng.
