"""Editorial scripts read and written inside Codex; no model API calls."""
import json
from pathlib import Path
from render_crmn_101_150 import save_script, read, SERIES

DATA = {}
DATA[121] = '''
1|Thẩm Lãng nhờ Kiếm Vương chờ thêm để thu xếp hậu quả vụ ám sát. Lý Thiên Thu nhận xét câu chuyện đổ cho các phe giang hồ chẳng thể đánh lừa người khác.
2|Thẩm Lãng vốn chỉ cần một lời giải thích để những người có quyền dễ bề che đậy. Hắn không trông mong tất cả sẽ tin vào câu chuyện đó.
5|Trên đường đi, nghe Kiếm Vương nhắc chuyện mất con, Thẩm Lãng lập tức xin lỗi vì vô tình chạm vào nỗi đau của ông.
13|Trong khi ấy, Tiết Lệ tới Huyền Vũ Bá tước phủ. Dù Kim gia từng giúp gia đình thoát nạn hải tặc, nàng lại xem thường mối hôn ước giữa hai nhà.
16|Nàng muốn hủy hôn với Kim Mộc Thông, còn yêu cầu chính Huyền Vũ Bá phải đứng ra mở lời để nhà mình giữ được thể diện.
32|Ở phía bên kia, người dân bàn tán trái ngược về Cừu Yêu Nhi. Có thương nhân bênh vực nàng vì những kẻ bị nàng tiêu diệt vốn là hải tặc đe dọa việc buôn bán.
49|Từ Thiên Thiên dùng thân phận Trương Xuân Hoa để tìm đường tiếp cận Cừu Yêu Nhi. Bức thư giới thiệu trở thành tấm vé bước vào cuộc gặp.
54|Thiên Thiên đề nghị giúp Cừu Yêu Nhi đối phó Cừu Kiêu. Nàng muốn dùng sự thông minh để đổi lấy một chỗ đứng bên cạnh nữ tướng.
61|Sau đó nàng nói thật mình là con gái Từ Quang Doãn, kể chuyện gia đình tan nát và những người thân bị Trương Tấn sát hại để cầu xin che chở.
63|Nhưng cách lấy lòng của Thiên Thiên không có tác dụng. Cừu Yêu Nhi thẳng thừng nói mình không thích phụ nữ rồi cho người đưa nàng ra ngoài.
'''
DATA[122] = '''
1|Từ Thiên Thiên chưa chịu bỏ cuộc. Nàng thoát khỏi những người đưa mình đi rồi quay lại cầu xin Cừu Yêu Nhi cho nương nhờ.
3|Cừu Yêu Nhi đã nghe chuyện nhà nàng, cũng bất ngờ vì nàng còn sống. Nữ tướng có thể thu nhận người gặp nạn, nhưng không cần thêm một kẻ bày mưu bên cạnh.
5|Được hỏi biết làm việc gì, Thiên Thiên lúng túng trước những công việc hầu hạ thông thường. Muốn ở lại, nàng phải tìm đúng thứ chủ nhân thật sự cần.
25|Ở một nơi khác, Cừu Thiên Nguy tính chuyện giành chỗ đứng trên đất liền. Muốn thế lực hải tặc tồn tại lâu dài, hắn cần một cơ nghiệp vượt ra ngoài biển.
27|Đường Luân cho biết trên đảo Kim Sơn có năm nghìn quân. Ông ta cũng không muốn tiếp tục để Kim gia kiếm lợi trong khi bản thân chỉ ngồi chờ thất thế.
29|Cừu Thiên Nguy lại đòi bảy phần lợi ích. Đường Luân phải lo cả thợ mỏ lẫn việc luyện kim nhưng vẫn bị ép nhận phần chia ít hơn.
30|Lời đe dọa rất rõ: nếu không đồng ý, hải tặc cứ đợi đảo trở về tay Kim gia rồi chiếm trọn. Đường Luân chẳng có nhiều quyền lựa chọn.
43|Tại quán trọ, Tiết Lệ muốn giành phòng tốt nhất. Biết người đang ở là Thẩm Lãng, nàng càng khinh thường vì hắn chỉ là một chàng rể ở nhờ.
46|Thẩm Lãng nhận ra đây chính là người từng đính hôn với Mộc Thông. Tiết Lệ vẫn tiếp tục xúc phạm, thậm chí còn bắt hắn phải cúi mắt khi nói chuyện.
58|Hắn âm thầm chuẩn bị một trò trả đũa bằng thứ gây kích ứng ngoài da. Trong đầu Thẩm Lãng, vị tiểu thư kiêu ngạo sắp phải nếm một bài học khó chịu.
'''
DATA[123] = '''
1|Thẩm Lãng cho làm lại y phục của Tiết Lệ để thực hiện trò trả đũa. Hắn còn chuẩn bị mùi hương nhằm che giấu những dấu vết đáng ngờ.
3|Việc đánh tráo giữa vòng hộ vệ đòi hỏi một cao thủ. Vì thế hắn đem cả ân tình Kiếm Vương còn nợ mình ra để nhờ Lý Thiên Thu giúp sức.
5|Lý Thiên Thu không ngờ một lần mang ơn cứu mạng lại được dùng vào chuyện như thế. Nhưng Thẩm Lãng biết không phải ai cũng vượt qua được hộ vệ của Tiết Lệ.
43|Sau đó Tiết Lệ phải chịu cảm giác ngứa ngáy đau rát suốt chuyến đi. Nàng chưa hiểu nguyên nhân, trong khi trò trả đũa đã đạt được mục đích.
45|Trở về gần Huyền Vũ thành, Thẩm Lãng chia tay Lý Thiên Thu. Hắn còn ngờ rằng vị Kiếm Vương vẫn đang giận vì chuyện mình vừa nhờ vả.
47|Tin Cừu Thiên Nguy đã điều quân tới khiến Thẩm Lãng chú ý ngay. Một bước then chốt trong kế hoạch của hắn cuối cùng đã chuyển động.
48|Hắn đề nghị nhạc phụ dẫn hai nghìn quân ra Kim Sơn. Điều quan trọng là phải diễn như đang giành đảo, còn thực tế tránh giao chiến với hải tặc.
55|Trong phủ, Kim Mộc Thông lại đang cặm cụi học hành. Sau chuyện hôn ước, chàng muốn thi đỗ tiến sĩ để tự tìm một người vợ tốt.
58|Thẩm Lãng nhắc em vợ rằng thân phận người nối nghiệp quý tộc vốn không bắt buộc phải theo con đường khoa cử. Nhưng Mộc Thông vẫn muốn có thành tích của riêng mình.
59|Đến lúc nghe em vợ xin hàng trăm bài văn và cả nghìn bài thơ để học, Thẩm Lãng chỉ còn biết hỏi vì sao cậu không tự viết lấy.
'''
DATA[124] = '''
1|Đường Luân tới thăm Huyền Vũ Bá tước phủ, làm ra vẻ giữ chữ tín khi tuyên bố giao trả đảo Kim Sơn. Phía sau lễ nghi ấy vẫn là cuộc tính toán giữa các thế lực.
4|Hai ngày sau, Kim gia đưa hai nghìn quân, hai trăm thợ luyện kim và tám trăm thợ mỏ xuống thuyền. Đường Duẫn cũng đi cùng đoàn ra đảo.
6|Trên đường, hai bên nói chuyện hòa giải và đoàn kết quý tộc cũ. Những lời đẹp đẽ không khiến Thẩm Lãng quên mục đích thật của chuyến đi.
32|Hải tặc đã chiếm Kim Sơn, khiến Kim Trác nổi giận. Đúng như kế hoạch đã bàn, ông không lao vào một trận đánh mà ra lệnh cho quân quay về.
34|Thẩm Lãng lấy lý do thuyền quá nặng để bỏ lại những thứ không cần thiết. Lương thực cùng vật tư trở thành món quà mà đối phương vui vẻ nhận lấy.
36|Cừu Hào cười đắc ý vì vừa có đảo, vừa được người và đồ tiếp tế. Hắn không biết việc rút quân vốn nằm trong dự tính của Thẩm Lãng.
61|Nhưng món nợ cũ vẫn đang treo trên đầu Kim gia. Họ đã trả một trăm vạn trong nhiều năm, giờ tiền mặt còn chưa đầy hai vạn mà vẫn thiếu bảy mươi vạn.
62|Kim gia xin Thư Đình Ngọc của Ẩn Nguyên Hội gia hạn một năm. Đối phương lập tức từ chối, không cho họ thêm thời gian xoay xở.
64|Hạn cuối chỉ còn một tháng. Nếu không trả đủ bảy mươi vạn kim tệ, đảo Vọng Nhai đem thế chấp sẽ bị lấy đi theo giấy nợ.
65|Thẩm Lãng nổi giận ngay trước mặt chủ nợ. Khi người của Ẩn Nguyên Hội rời phủ, áp lực tài chính đã trở thành mặt trận mới của cuộc tranh đoạt.
'''
DATA[125] = '''
13|Thẩm Lãng hiểu Từ Thiên Thiên là một mắt xích quan trọng. Nếu nàng không thể đứng vững bên cạnh Cừu Yêu Nhi, kế hoạch phía sau cũng sẽ gặp nguy hiểm.
16|Lại có người tới đòi tiền. Lâm Mặc của Cẩm Tú Các đưa khoản một nghìn kim tệ ra tính lãi thành một nghìn ba trăm, ép Thẩm Lãng phải hoàn trả.
18|Hắn còn nói công thức nhuộm đã bị lấy cắp để biện minh cho yêu cầu của mình. Từng người một đang tranh thủ thời điểm Kim gia khó khăn để dồn ép.
25|Không chỉ chủ nợ, người của Đại Lý Tự cũng xuất hiện. Họ điều tra cái chết Chúc Lan Đình và nhắm vào việc Thẩm Lãng từng có mặt gần Nam Hoa.
26|Thẩm Lãng nhận ra một quan viên bình thường không tự nhiên dám làm chuyện này. Đằng sau cuộc điều tra hẳn còn có một chỗ dựa đủ lớn.
28|Trước khoản đòi tiền, hắn lại nhận rất nhanh. Chính sự bình thản ấy khiến cuộc gây sức ép diễn ra khác với điều những người kia mong đợi.
29|Hắn ra lệnh mang đủ một nghìn ba trăm kim tệ ra trả. Bề ngoài đó là cách thanh toán món nợ, nhưng trong lòng hắn đã ghi nhớ người đang ép mình.
43|Sau khi những kẻ đòi nợ hả hê, Thẩm Lãng cho rằng Lâm Mặc đã đi quá giới hạn. Việc chèn ép lần này sẽ có một cái giá khác.
44|Hắn giao cho Thập Tam chuẩn bị một cái bẫy nguy hiểm ở nhà xí. Trò trả đũa được ngụy trang thành tai nạn để nhắm vào đám người đang ăn mừng.
'''
DATA[126] = '''
19|Lâm Mặc thúc người của Đại Lý Tự bắt Thẩm Lãng về giam. Mộc Lan lập tức rút kiếm chắn trước chồng, không chịu để họ tùy tiện dẫn người đi.
23|Thẩm Lãng lại trấn an vợ rồi chủ động giơ tay. Những vết nổi trên cánh tay khiến đám quan sai đang hung hăng bỗng chùn bước.
26|Họ nghi hắn mắc đậu mùa. Thẩm Lãng còn nhắc chuyện đi khám ở Phong Hoa Cốc, khiến ai nấy càng sợ hãi, tránh xa hắn ngay lập tức.
29|Cảnh bắt người biến thành cảnh tháo chạy. Hắn còn gọi với theo, giục họ cứ đưa mình về nha môn như vừa tuyên bố ban đầu.
44|Ở phía bên kia, Lâm Mặc cùng những người đứng về phe mình mở tiệc. Họ tưởng Kim gia đã tới đường cùng nên chẳng còn kiêng dè.
45|Bữa tiệc chưa kết thúc, một người đột nhiên đau bụng. Rồi những người khác cũng lần lượt ôm bụng, cuống cuồng tìm chỗ giải quyết.
48|Cả nhóm chạy vào nhà xí, còn Thập Tam đã chờ bên ngoài. Cái bẫy Thẩm Lãng chuẩn bị từ trước bắt đầu khép lại.
49|Kết cấu trong nhà xí sập xuống khiến những người ở bên trong không thoát kịp. Sự hoảng loạn lập tức thay thế tiếng cười đắc ý ban nãy.
52|Lửa bùng lên, biến cuộc trả đũa thành một vụ chết người. Ba người con của Lâm Mặc cùng một vị quan khách bị chôn vùi trong biển lửa.
'''
DATA[127] = '''
2|Giữa lúc những người khác tránh xa Kim gia, Ngũ vương tử Ninh Chính lại tới thăm. Thân phận hoàng tử không khiến cuộc đời chàng được thuận lợi.
3|Mẹ của chàng từng là người hầu bên cạnh Tô Bội Bội. Khi chàng ra đời, ngoại hình khác thường cùng một tai họa trùng lúc đã khiến người ta gán cho chàng điềm xấu.
4|Chính Tô Bội Bội đã cầu xin quốc quân giữ mạng đứa trẻ. Ân tình năm ấy là lý do Ninh Chính vẫn nhớ tới nhà họ Kim trong lúc khó khăn.
6|Chàng mang gần hai vạn kim tệ tới giúp. Số tiền ấy gần như toàn bộ tài sản của chàng, dù vẫn còn cách rất xa khoản nợ bảy mươi vạn.
25|Trương Tấn thì đếm từng ngày chờ hạn trả nợ. Hắn tin chỉ còn mười ba ngày nữa là có thể nhìn Kim gia sụp đổ.
27|Mộc Lan tìm đến chín nhà quý tộc nhưng chỉ vay được tổng cộng một nghìn kim tệ. Những quan hệ cũ bộc lộ sự lạnh nhạt khi gia đình cần giúp đỡ nhất.
28|Thẩm Lãng vẫn trấn an rằng mình có kế hoạch. Hắn không đặt hy vọng cứu cả gia tộc vào những khoản vay nhỏ mà mọi người miễn cưỡng đưa ra.
29|Hồng Tuyến, vợ Kim Hối, muốn gặp Mộc Lan. Mộc Lan phải tạm rời cuộc bàn bạc trong lúc Thẩm Lãng tiếp tục lo những mắt xích khác.
61|Thư của Từ Thiên Thiên báo tin Cừu Yêu Nhi thích nghe chuyện anh hùng. Nàng cần một câu chuyện thật dài để giữ được vị trí bên cạnh nữ tướng.
64|Thẩm Lãng nhanh chóng nghĩ tới những truyện mình biết. Một câu chuyện đủ hấp dẫn có thể giúp Thiên Thiên ở lại lâu hơn bất kỳ lời lấy lòng nào.
'''
DATA[128] = '''
19|Người của Thiên Đạo Hội đề nghị mua ruộng và cả tòa thành với tổng giá hai mươi chín vạn. Đổi tài sản lấy tiền sẽ giúp Kim gia tạm thời thoát hiểm.
20|Thẩm Lãng từ chối bán thành. Đó là gốc rễ quân sự của gia tộc, và một khi mất đi thì dù có tiền cũng rất khó dựng lại cơ nghiệp.
24|Thứ hắn đem ra thương lượng là một chiếc gương trong veo. Những vị khách lập tức sững sờ trước hình ảnh phản chiếu rõ ràng chưa từng thấy.
32|Thẩm Lãng nói chi phí làm ra thấp hơn một lượng bạc, sản xuất nhiều còn có thể rẻ hơn. Trong khi ấy, giá bán một chiếc có thể tới một trăm kim tệ.
35|Thiên Đạo Hội muốn mua vào với giá mười kim tệ mỗi chiếc. Nhưng Thẩm Lãng cho biết hiện chỉ có một nghìn chiếc sẵn hàng.
43|Giá trị không nằm riêng ở số hàng có sẵn mà còn ở khả năng tạo ra chúng. Phần nguyên liệu chỉ chiếm một phần rất nhỏ so với giá gương bán ra.
44|Hai bên tranh luận gay gắt về số tiền hợp tác. Phía Thiên Đạo Hội cho rằng một trăm vạn quá cao và chỉ muốn trả bốn mươi vạn.
45|Họ biết hạn trả nợ đã cận kề nên dùng thời gian để ép giá. Thẩm Lãng vẫn giữ thái độ cứng rắn, không chịu đổi cơ hội lớn lấy một khoản cứu nguy nhỏ.
47|Hắn đưa ra viễn cảnh Thiên Đạo Hội vượt qua Ẩn Nguyên Hội. Đây là cơ hội đổi tương quan giữa hai thế lực thương mại, đủ lớn để họ phải tính lại.
48|Thẩm Lãng nhấn mạnh mình cần một trăm vạn kim tệ. Cuộc mặc cả đã chuyển từ chuyện mua vài chiếc gương sang một vụ hợp tác quyết định tương lai.
'''
DATA[129] = '''
1|Hoàng Đồng đích thân tới và nhìn ra ý nghĩa của cơ hội này. Ông không muốn để một vụ mặc cả làm Thiên Đạo Hội bỏ lỡ món lợi về sau.
2|Dù vậy, ông vẫn cần tận mắt xác nhận một nghìn chiếc gương. Chỉ khi hàng hóa thật sự tồn tại thì mọi lời hứa mới có trọng lượng.
3|Kim Hối mở cửa dẫn người vào kiểm tra. Thẩm Lãng đã chuẩn bị thứ khiến cuộc thương lượng không còn dừng ở những lời mô tả.
6|Cảnh trước mắt làm khách tới xem kinh ngạc. Sản phẩm mà họ tưởng hiếm có đã xuất hiện đủ nhiều để chứng minh khả năng cung ứng của Kim gia.
61|Trong lúc chuyện gương tiến triển, Từ Thiên Thiên bắt đầu kể Tây Du Ký cho Cừu Yêu Nhi. Những lời mở đầu đưa người nghe vào một thế giới hoàn toàn khác.
62|Thiên Thiên vẫn lo không biết nữ tướng có hiểu và thích câu chuyện hay không. Nàng đang đánh cược chỗ dung thân của mình vào những trang truyện ấy.
'''
DATA[130] = '''
1|Từ Thiên Thiên cố tình kể thật chậm, hai canh giờ chỉ đi được một phần câu chuyện. Nếu kể hết quá nhanh, nàng sẽ mất thứ giúp mình ở lại.
2|Đến đoạn con khỉ tìm học đạo với Bồ Đề Tổ Sư, Cừu Yêu Nhi đã chăm chú lắng nghe. Thế giới thần tiên khiến nàng không muốn câu chuyện dừng lại.
3|Những điều kỳ lạ trong Tây Du Ký vượt xa cuộc sống hiện tại. Với Cừu Yêu Nhi, chuyện kể mở ra một khoảng tự do mà nàng khó tìm được ngoài đời.
4|Khi Thiên Thiên ngừng kể, nàng nơm nớp chờ phản ứng. Kế hoạch này chỉ thành công nếu người nghe thật sự muốn nghe tiếp.
5|Lời khen của Cừu Yêu Nhi cuối cùng cũng tới. Thiên Thiên vui mừng vì đã tìm được cách giữ mình bên cạnh nữ tướng mà không cần dùng những lời hứa suông.
55|Trở lại phía Thẩm Lãng, hắn nghe chuyện Tiết Lệ mắc một chứng bệnh kỳ lạ. Nguồn cơn của lời đồn ấy vốn nằm trong trò trả đũa mà hắn đã sắp đặt.
57|Tại Huyền Vũ Bá tước phủ, Tô Bội Bội nhận được thư của Châu Thần. Lá thư kéo những quan hệ cũ trở lại giữa lúc gia đình còn nhiều biến động.
58|Bà không giữ thư lại mà đưa thẳng vào lửa. Những lời trong thư không thể khiến vị phu nhân chấp nhận khuất phục.
59|Tô Bội Bội lạnh lùng nói Tô gia rồi sẽ hối hận. Sóng gió trước mắt chưa kết thúc, một cuộc đối đầu khác đã bắt đầu hiện hình.
'''

DATA[131] = '''
1|Thế tử Vũ An Bá tước phủ vừa rời đi, Lục hoàng tử Ninh Cảnh đã tới. Hắn nói muốn thăm Huyền Vũ Bá đang bệnh và giúp người dì của mình vượt khó.
9|Nhưng khi nhìn Mộc Lan và Thẩm Lãng, trong lòng Ninh Cảnh đầy coi thường. Việc hắn đột nhiên mang tiền tới khiến Tô Bội Bội cũng thấy khác thường.
16|Những chiếc rương được mở ra, bên trong chủ yếu là tiền đồng. Tính cả số bạc lẻ, Thẩm Lãng nhận ra giá trị còn chưa tới mấy trăm kim tệ.
21|Ngay sau món quà phô trương, Ninh Cảnh nói muốn xin phụ vương phong tòa thành của Kim gia cho mình. Hắn đã coi cơ nghiệp người khác như một món đồ sắp được nhận.
24|Tô Bội Bội giận đến khó chịu. Thẩm Lãng lấy lý do nhạc mẫu không khỏe để tiễn khách, khép lại cuộc thăm hỏi mang đầy ý sỉ nhục.
32|Trì gia cũng muốn lợi dụng lúc này để mua ruộng dâu của Kim gia. Thẩm Lãng phải tiếp tục diễn cảnh túng quẫn, vừa giữ tài sản vừa che giấu đường lui.
51|Hai ngày sau, chủ nợ tụ tập ngay trong phủ. Ẩn Nguyên Hội nhắc lại khoản vay một trăm vạn kim tệ từ thời Kim Vũ mang quân đánh hải tặc.
53|Cả gốc và lãi là một trăm bảy mươi vạn; Kim gia đã trả một trăm vạn, còn thiếu bảy mươi vạn. Đối phương đưa giấy nợ ra để đòi lấy đảo Vọng Nhai.
63|Họ yêu cầu ký giấy giao đảo trong ba ngày và còn định đưa quân tới hỗ trợ bàn giao. Những lời nói giữ trật tự thực chất là sức ép buộc Kim gia đầu hàng.
66|Huyền Vũ Bá ho ra máu rồi ngất ngay giữa đại sảnh. Tô Bội Bội nổi giận tố Ẩn Nguyên Hội từng tiết lộ quân cơ cho hải tặc, nhưng đối phương đòi bà phải có bằng chứng.
'''
DATA[132] = '''
1|Thẩm Lãng bảo nhạc mẫu đưa nhạc phụ vào nghỉ, còn chuyện ngoài đại sảnh giao cho mình. Hắn ngồi xuống đối diện đám người đang chờ chia tài sản Kim gia.
6|Chủ nợ không muốn bàn bạc thêm, chỉ thúc hắn ký giấy. Thẩm Lãng lại gọi tất cả những người còn đòi tiền đứng ra một lượt.
16|Khoản của Lâm Mặc được người khác tới đòi thay, hắn cũng nhận. Tiếp đó Cừu Kiêu đưa khoản bồi thường hằng năm cho hải tặc ra ép Kim gia phải trả trước.
31|Có kẻ bảo bán ruộng, không đủ thì bán nhà. Lòng tham lộ rõ khi họ còn đem cả nữ quyến của Kim gia ra làm đối tượng mặc cả.
33|Tổng số tiền bị đòi đã lên tám mươi vạn kim tệ. Mọi người đều tin Kim gia không thể kiếm nổi, và đảo Vọng Nhai chắc chắn sẽ đổi chủ.
36|Thẩm Lãng bỗng bật cười rồi xé bỏ lớp áo ngoài. Bộ y phục đắt tiền bên trong khiến sự khinh thường của cả phòng lập tức biến thành ngỡ ngàng.
39|Hắn mắng thẳng những người đang dồn ép, tuyên bố đừng mơ bắt Kim gia bán đất và giao đảo. Sau đó hắn ra hiệu thanh toán toàn bộ số tiền.
44|Kim tệ đổ xuống từ phía trên thành một cơn mưa vàng. Món nợ mà đối phương tưởng là đòn chí mạng giờ nằm ngay trước mắt tất cả.
47|Thẩm Lãng và Mộc Lan đứng dưới chiếc ô giữa tiếng vàng rơi. Đám chủ nợ từ thế hung hăng chỉ còn biết trố mắt nhìn đại sảnh ngập tiền.
54|Ngay cả Thư Đình Ngọc cũng không tin đây thật sự là tám mươi vạn kim tệ. Thẩm Lãng bảo họ tự nhận phần của mình rồi rời khỏi phủ.
62|Trước mặt các quan viên và hoàng thân, hắn yêu cầu xác nhận khoản bảy mươi vạn đã trả sạch. Chủ nợ không còn cớ lấy đảo Vọng Nhai.
64|Việc xóa nợ được công nhận. Ninh Cảnh tức vì bị xem thường, còn những người chứng kiến bắt đầu hiểu mình đã đánh giá quá thấp chàng rể nhà họ Kim.
'''
DATA[133] = '''
1|Thẩm Lãng hỏi lại cho rõ: đã trả nợ thì không ai có quyền ép Kim gia giao đảo. Câu trả lời trước mặt quan viên chặn đứng âm mưu lấy Vọng Nhai bằng giấy thế chấp.
4|Ninh Cảnh vẫn buông lời đe dọa rằng có tiền chưa chắc có mạng tiêu. Thẩm Lãng chẳng tiếp tục nhún nhường mà bảo từng người nhận tiền rồi đi.
6|Những kẻ vừa còn hùa nhau dồn ép bây giờ phải tự chia tiền trong đại sảnh. Màn thanh toán công khai làm họ hết cơ hội chối bỏ kết quả.
31|Tin truyền tới Tấn Hải Bá tước phủ. Cừu Kiêu báo cho Đường Luân rằng Thẩm Lãng đã trả tới tám mươi vạn và trong nhà có thể còn tiền nữa.
33|Đường Luân sững sờ không hiểu bảy mươi vạn từ đâu mà có. Những dấu hiệu bệnh nặng, vay tiền khắp nơi trước đó hóa ra đều có thể chỉ là màn diễn.
36|Ông ta đã trả giá quá lớn, thậm chí còn để Kim Sơn rơi vào tay hải tặc. Giờ Kim gia vẫn đứng vững khiến toàn bộ sự đánh đổi ấy trở thành điều nhục nhã.
49|Trương Xung nhìn ra Thẩm Lãng tính xa hơn từng bước riêng lẻ. Cuộc đối đầu này hấp dẫn ông ta vì đối thủ đang chủ động dệt một tấm lưới lớn.
50|Ông đoán Cừu Kiêu có thể sẽ chết rất thảm. Điều bất thường là sau nhiều lần bị hãm hại, Thẩm Lãng vẫn chưa trả thù trực tiếp hắn.
51|Theo Trương Xung, Thẩm Lãng còn muốn kéo nhiều thế lực vào cùng một cái bẫy. Món nợ vừa được giải quyết mới chỉ là bước mở đầu.
53|Ông bảo Trương Tấn chuẩn bị cho đại chiến. Thay vì ngăn Thẩm Lãng tiêu diệt các gia tộc cản tân chính, ông còn muốn lợi dụng và phối hợp với kế hoạch ấy.
'''
DATA[134] = '''
2|Trương Tấn biết Từ Thiên Thiên còn sống và đã trở thành người thân cận của Cừu Yêu Nhi. Trương Xung nhận định nàng đang phối hợp với Thẩm Lãng.
4|Việc điều tra đống đổ nát tìm thấy một mật thất có nước. Đó là lời giải cho chuyện Thiên Thiên thoát khỏi đám cháy mà mọi người tưởng đã giết nàng.
5|Trương Tấn muốn tìm cách diệt nàng, nhưng cha hắn lại ngăn. Để Thẩm Lãng tiến hành kế hoạch có thể mở đường thay đổi cục diện Nộ Triều thành.
14|Về phía Kim gia, Thẩm Lãng đề nghị chiêu thêm hai nghìn quân. Hắn cần quân trung thành, vì cuộc chiến sắp tới sẽ dựa nhiều vào bẫy và mưu kế.
16|Việc mở rộng phải hoàn tất trong ba ngày để nhạc phụ dẫn bốn nghìn người ra Vọng Nhai. Vũ khí và giáp trụ đã có, điều còn thiếu là binh lính.
17|Thiên Đạo Hội sẽ ứng thêm tiền, còn Kim gia dùng bốn mươi vạn để trang trí đảo. Mỏ sắt cũ được biến thành một mỏ vàng đủ khiến thiên hạ chú ý.
18|Tăng quân và xây thành trên đảo sẽ làm đối thủ tin đây là trung tâm chiến lược mới. Mọi động thái đều hướng họ tới suy nghĩ Vọng Nhai chứa rất nhiều vàng.
34|Tin đồn lan ra đúng như dự tính. Đường Luân cho kiểm tra vàng mới luyện và càng tin dưới đảo có một mỏ lớn mà nhà họ Kim vừa khai thác được.
57|Khi gặp Trương Xung, ông ta được nhắc phải xác minh trước khi hành động. Thẩm Lãng quá gian xảo để chỉ dựa vào lời đồn rồi dốc toàn lực.
61|Cái tên được đưa ra là Cừu Kiêu. Sau lưng hắn có cả thế lực hải tặc nên Đường Luân tin Kim gia không dám giết nếu hắn vào đảo dò xét.
64|Trương Xung âm thầm nghĩ mình đã đặt Cừu Kiêu dưới mũi kiếm của Thẩm Lãng. Một lời gợi ý vừa đẩy kẻ khác tiến gần hơn tới cái bẫy.
'''
DATA[135] = '''
1|Ở Nộ Triều thành, Cừu Yêu Nhi vẫn say mê nghe Tây Du Ký. Câu chuyện Tề Thiên Đại Thánh chống lại quyền uy chạm đúng điều nàng khao khát.
4|Khi nghe Đại Thánh bị trấn áp dưới Ngũ Hành Sơn, nàng nói mình cũng đang bị nhốt như vậy. Tâm hồn muốn đi xa mà thân thể không thể rời nơi này.
19|Thẩm Lãng nhận thư gấp của Thiên Thiên báo Cừu Yêu Nhi gặp nguy hiểm. Hắn phải cân nhắc vì tới thành của hải tặc chẳng khác nào bước vào sào huyệt đối phương.
20|Nhưng nếu nữ tướng chết, kế hoạch dành cho Nộ Triều thành sẽ đổ vỡ. Hắn quyết định đi cứu và nhờ Thiên Đạo Hội giúp bảo đảm an toàn.
22|Lý Thiên Thu ở quá xa, Hoàng Đồng bèn tiến cử hộ vệ khác. Người sẽ đi cùng Thẩm Lãng là Hoàng Phượng, một cao thủ có thực lực vượt cả Mộc Lan.
32|Để che thân phận, Thẩm Lãng hóa trang thành nữ đại phu. Ngay cả Hoàng Phượng cũng kinh ngạc vì diện mạo thay đổi quá kỹ, gần như không tìm ra sơ hở.
35|Trên đường, hắn hỏi nàng về giới cao thủ trẻ. Chuyến đi vừa là cuộc cứu người, vừa giúp hắn hiểu thêm những sức mạnh có thể ảnh hưởng tới ván cờ.
57|Cuối cùng hai người tới Nộ Triều thành. Vẻ phồn hoa ở đây vượt dự tính của Thẩm Lãng, hoàn toàn không giống một chỗ chỉ có đám cướp biển.
58|Nhìn tòa thành chủ kiên cố, hắn hiểu không thể cường công. Các pháo đài còn hỗ trợ lẫn nhau, nên muốn giành nơi này phải đánh bằng mưu trí.
'''
DATA[136] = '''
2|Thẩm Lãng cùng Hoàng Phượng tìm chỗ liên lạc đã hẹn. Hắn càng thấy rõ Nộ Triều thành không phải mục tiêu có thể lấy được chỉ bằng một trận tiến công.
4|Trong thành bảo, Cừu Yêu Nhi đang chịu bệnh nặng. Nàng đuổi những người xung quanh ra ngoài rồi cho gọi Từ Thiên Thiên tới.
6|Thiên Thiên vội vàng tới gặp chủ nhân, trong lòng đầy lo lắng. Vị trí bên cạnh nữ tướng khiến nàng biết tình hình nguy hiểm hơn vẻ ngoài của cuộc sống trong phủ.
26|Khi gặp Thẩm Lãng cải trang, chính nàng cũng sững sờ. Dáng vẻ nữ đại phu khác quá xa người đàn ông mà nàng từng biết.
29|Thẩm Lãng còn tự đắc trêu nàng về tài hóa trang. Một chút đùa cợt không làm thay đổi việc hắn đang mạo hiểm bước vào giữa thế lực của kẻ địch.
49|Sau khi quan sát bệnh tình, hắn nhận ra cơ thể Cừu Yêu Nhi chịu tổn thương rất nặng. Chỉ có thể chất đặc biệt mới giúp nàng cầm cự tới lúc này.
51|Thiên Thiên đưa câu hỏi của nữ tướng: có thể trị được không. Thẩm Lãng viết trả lời thay vì cất tiếng, tiếp tục giữ vỏ bọc của mình.
54|Hắn cho biết có thể chữa, nhưng phải khám kỹ hơn để xác định vấn đề. Cơ hội cứu Cừu Yêu Nhi cuối cùng đã xuất hiện ngay trong căn phòng ấy.
'''
DATA[137] = '''
3|Sau cuộc kiểm tra, Thẩm Lãng bắt đầu ghi lại những triệu chứng của Cừu Yêu Nhi. Hắn tiếp tục dùng giấy để trao đổi, tránh để giọng nói làm lộ thân phận.
4|Nàng không thể mở mắt bình thường, đầu óc quay cuồng và buồn nôn. Những điều các đại phu trước không nhìn ra lại được hắn hỏi đúng từng điểm.
5|Cừu Yêu Nhi thừa nhận từng đau đến ngất, phải dùng chân khí áp chế khí huyết. Với Thẩm Lãng, cách chống đỡ ấy càng chứng tỏ tình trạng đang rất nguy hiểm.
19|Hắn nhận định lượng độc chất tích tụ trong cơ thể bất thường. Sự việc khác hẳn một chút nhiễm độc từ đồ dùng cổ mà trước đây hắn từng gặp.
21|Thẩm Lãng hướng nghi ngờ vào thức ăn. Thiên Thiên phản đối vì mình và Lục Y vẫn nếm đồ ăn hằng ngày mà không thấy có triệu chứng gì.
23|Hắn giải thích đây là loại độc tích lũy theo thời gian. Người nếm một ít không gặp chuyện ngay, trong khi người ăn liên tục có thể bị hại rất nặng.
37|Cô gái làm bếp hiện tại khóc lóc khẳng định không phản chủ. Nàng định lấy cái chết chứng minh nhưng Cừu Yêu Nhi đã kịp ngăn lại.
41|Nữ tướng tin lời cô và chỉ nói gần đây đồ ăn nhạt hơn trước. Câu nói bình thản ấy lại khiến Thẩm Lãng thấy nàng thật đáng thương.
46|Lục Y khai người đầu bếp cũ xin nghỉ ba ngày trước vì con gái sinh con. Thời điểm ấy cũng trùng với lúc bệnh của Cừu Yêu Nhi phát tác dữ dội.
47|Cừu Yêu Nhi ra lệnh đi tìm cả nhà người đầu bếp. Thiên Thiên hiểu kẻ hạ độc có thể đã lo xóa dấu vết trước khi họ bắt đầu điều tra.
'''
DATA[138] = '''
2|Việc điều tra bắt đầu từ lai lịch người đầu bếp cũ. Bà từng được Cừu Yêu Nhi che chở sau khi rơi vào tay hải tặc và đã làm bếp trong phủ.
4|Nhưng nhà của bà lẫn con cái đều không còn người. Một căn nhà còn bị thiêu sạch, khiến con đường truy tìm kẻ hạ độc bị chặn lại.
5|Hộ vệ nghi Cừu Kiêu vì hắn vẫn coi nữ tướng là đối thủ lớn nhất. Họ muốn tìm thành chủ đòi công đạo, nhưng Cừu Yêu Nhi còn việc khác phải lo.
19|Đối thủ nàng sắp giao đấu là Chúc Hồng Tuyết, người đứng đầu thế hệ cao thủ trẻ. Cừu Yêu Nhi khẳng định đây là quyết đấu, có thể phân cả sống chết.
22|Thẩm Lãng thấy việc ra trận lúc này quá nguy hiểm. Hắn nhận ra bệnh tình còn kéo theo vấn đề trong đầu khiến nàng không thể đứng vững bình thường.
24|Dù biết phương pháp rất mạo hiểm, hắn vẫn xác nhận có thể cứu. Một cuộc chữa trị vượt xa hiểu biết của những người trong phủ sắp diễn ra.
38|Giữa lúc đó, chiến thuyền của Cừu Yêu Nhi xuất hiện trên biển khiến hải tặc hoảng loạn. Danh tiếng nữ sát thần vẫn đủ làm đối phương run sợ.
41|Nữ tướng cầm song đao đứng trên thuyền, khí thế chưa hề khuất phục. Người ngoài khó có thể tưởng tượng nàng vừa phải nằm chịu những cơn đau dữ dội.
55|Lục Y lại tìm gặp Cừu Kiêu và tưởng mình có thể nói chuyện như đồng minh. Hắn lập tức đánh nàng, không chấp nhận để một người hầu thăm dò mình.
63|Nghe Lục Y báo người đầu bếp hạ độc đã biến mất và nhà bị đốt, Cừu Kiêu cũng kinh ngạc. Âm mưu quanh bệnh tình nữ tướng chưa thể giải thích đơn giản bằng một lời tố cáo.
'''
DATA[139] = '''
2|Trước mặt Lục Y, Cừu Kiêu làm bộ nổi giận vì chị bị hại. Nhưng điều hắn thật sự quan tâm chỉ là liệu bệnh có làm hỏng diện mạo và cơ thể nàng hay không.
5|Hắn còn hỏi thứ hương mình chuẩn bị bao giờ phát tác. Lục Y báo nữ tướng vẫn đốt mỗi ngày, nhưng thể chất đặc biệt khiến nàng chưa mất kiểm soát.
6|Nghe tin thuốc đã ngấm rất mạnh, Cừu Kiêu tưởng thời cơ sắp tới. Hắn muốn lợi dụng tình trạng của Cừu Yêu Nhi để thực hiện ý đồ đê tiện.
20|Trong phòng chữa bệnh, Thẩm Lãng dựa vào khả năng quan sát khác thường để xác định chỗ tụ máu. Điều hắn thiếu là sức mạnh và dụng cụ phù hợp.
22|Thiên Thiên lo phương pháp này quá liều lĩnh. Với người trong thế giới ấy, những gì Thẩm Lãng đề nghị nghe gần như không thể tin nổi.
23|Cừu Yêu Nhi lại đồng ý ngay. Nàng để vị nữ đại phu lạ mặt ra tay vì hiểu mình không thể tiếp tục chịu tình trạng hiện tại.
39|Hắn còn đang đếm để chuẩn bị thì nữ tướng đã tự thực hiện phần cần sức mạnh. Sự quyết đoán ấy làm cả Thẩm Lãng lẫn Thiên Thiên sững người.
41|Thẩm Lãng tập trung theo dõi để bảo đảm không đi chệch vị trí. Tài quan sát của hắn kết hợp với khả năng khống chế cơ thể của nàng tạo ra lối thoát.
47|Cừu Yêu Nhi tự vận chân khí để hoàn tất việc chữa trị. Những gì Thẩm Lãng không đủ sức thực hiện lại được nàng làm bằng võ công của chính mình.
51|Cuộc chữa trị thành công. Thẩm Lãng kinh ngạc trước cách dùng chân khí, còn nữ tướng công nhận y thuật của vị khách đã cứu mình.
54|Nàng hứa sẽ trả một ân tình, chỉ cần nằm trong khả năng của mình. Trong đầu Thẩm Lãng, mục tiêu Nộ Triều thành vẫn chưa lúc nào biến mất.
'''
DATA[140] = '''
5|Sau khi trị bệnh, Thẩm Lãng phải liên tục nhắc mình giữ bình tĩnh để khỏi lộ thân phận. Lớp cải trang giúp hắn vào được đây nhưng cũng đẩy hắn vào nhiều tình huống khó xử.
26|Hắn bắt đầu cảm thấy nóng bất thường dù thời tiết không nóng. Cảm giác ấy báo hiệu căn phòng vẫn còn một mối nguy mà việc chữa bệnh chưa giải quyết được.
28|Bên phía thành chủ, Đường Luân và Cừu Thiên Nguy tiếp tục bàn chuyện mỏ vàng. Số tiền Kim gia vừa trả nợ đủ lớn để họ không thể bỏ qua lời đồn.
30|Cừu Thiên Nguy vẫn nghi số vàng có thể đến từ vay mượn hoặc một vụ giao dịch. Xuất hiện đúng hạn trả nợ khiến nó vừa hấp dẫn vừa rất đáng ngờ.
43|Nếu dốc quân đánh đảo rồi phát hiện chẳng có mỏ vàng, hắn sẽ phải trả giá lớn. Số thế lực muốn chia phần cũng có thể ngày càng tăng.
44|Hắn yêu cầu phải xác định vàng có thật trước. Đường Luân lại than rằng những người mình cử đi thám thính đều đã bị giết, không thể tiếp cận tùy tiện.
47|Cừu Kiêu chủ động xin tới đảo dò xét. Hắn tin có cha và cả Nộ Triều thành chống lưng, Kim gia dù giận cũng chẳng dám làm mình bị thương.
48|Hắn nhắc lại những lần từng hạ nhục và hãm hại Kim gia mà chưa bị trả đũa. Chính sự tự tin ấy khiến hắn không nhận ra mình đang được dẫn tới đâu.
55|Trước khi ra đảo, hắn còn hướng ý nghĩ về Cừu Yêu Nhi. Âm mưu nhắm vào nàng vẫn đang diễn ra song song với cuộc tranh đoạt vàng.
58|Trong phòng, nữ tướng nhận ra chiếc lò hương có vấn đề. Nàng thoáng nghi nữ đại phu nhưng lập tức gạt đi, bởi mùi hương đã bị người khác pha thêm thuốc.
59|Nàng xác định đúng nguồn gốc cơn bất thường, nhưng thuốc đã phát tác. Bên ngoài căn phòng yên tĩnh, những kẻ chờ cơ hội vẫn chưa chịu dừng tay.
'''

DATA[141] = '''
8|Cừu Yêu Nhi cố giữ tỉnh táo trước tác dụng của thuốc rồi thúc ngựa ra bờ biển. Nàng biết mình phải kết thúc trận đấu thật nhanh để trở về.
12|Người đợi nàng là Chúc Hồng Tuyết, cao thủ số một thế hệ trẻ. Cuộc gặp dưới ánh trăng sắp biến bãi biển thành đấu trường của hai người.
16|Hắn nhắc chuyện sư phụ muốn biết khi nào nàng có thể rời Nộ Triều thành. Nhưng Cừu Yêu Nhi vẫn đang chờ một cơ hội bước ra thế giới ngoài biển.
17|Nàng còn hỏi tới Ninh Hàn, người đáng lẽ cùng giao đấu. Chúc Hồng Tuyết cho biết công chúa đang theo sư tổ khai quật cổ văn trên một hòn đảo khác.
32|Cuộc giao phong bùng nổ, sức mạnh hai bên làm mặt đất và cây cối quanh bãi biển tan tác. Cả hai dồn lực vào những đòn đánh quyết định.
36|Khi bụi lắng xuống, hai người đứng hai bên một hố lớn. Cừu Yêu Nhi đã có thương tích, nhưng kết quả không đơn giản như vẻ ngoài.
37|Chúc Hồng Tuyết nhận thua. Nàng lại gắt lên rằng chính mình thua và thúc hắn rời đi, vì không còn thời gian giải thích.
39|Hắn nói sau đòn vừa rồi sức lực của mình gần chạm giới hạn, còn nàng vẫn chưa tới mức ấy và lại mang thương sẵn. Nói xong hắn cáo biệt.
51|Trong phủ, Thẩm Lãng cũng bị hương thuốc làm ý thức mơ hồ. Hắn không còn đủ sức đứng dậy dập lò hương rồi ngã xuống sàn.
55|Cừu Kiêu xông tới phòng nhưng bị các nữ võ sĩ chặn lại. Họ giữ đúng lệnh chủ nhân, bất cứ ai cũng không được tự tiện bước vào.
59|Thấy phòng phải tăng hộ vệ, hắn tưởng Cừu Yêu Nhi đã hoàn toàn bị khống chế bởi thuốc. Kẻ mang ý đồ xấu bắt đầu cười đắc thắng quá sớm.
'''
DATA[142] = '''
1|Cừu Kiêu không chấp nhận bị nữ võ sĩ ngăn cản. Hắn vừa mắng vừa rút kiếm, muốn dùng thân phận thiếu chủ để ép tất cả nhường đường.
4|Đội trưởng trả lời chỉ nghe lệnh chủ nhân. Trong mắt Cừu Kiêu, sự trung thành ấy trở thành cái cớ để hắn nổi giận và ra tay với cả đội.
6|Hắn gào rằng thành trì lẫn đất đai đều thuộc nhà mình. Nhưng những lời đe dọa không khiến các nữ võ sĩ từ bỏ nhiệm vụ bảo vệ căn phòng.
31|Cuộc giao chiến làm nhiều người bị thương. Đội trưởng vẫn chắn trước hắn dù yếu thế, quyết không để kẻ đang nổi điên tiến vào trong.
33|Một đòn bất ngờ cắt ngang cuộc tấn công. Cừu Kiêu quay lại và chết lặng khi thấy Cừu Yêu Nhi đã đứng ngay phía sau.
37|Nàng nói mình vừa đi quyết đấu. Hắn hoảng hốt vì kế hoạch dựa trên việc nàng mắc kẹt trong phòng đã hoàn toàn sai lệch.
38|Nữ tướng lập tức yêu cầu đưa các chị em bị thương đi chữa trị bằng mọi giá. Cơn giận của nàng hướng vào kẻ vừa tấn công người của mình.
40|Trước đây nàng nhường vì coi hắn là em, lần này thì không. Một đòn trừng phạt khiến Cừu Kiêu bị đánh văng, chẳng còn vẻ hung hăng ban đầu.
42|Dù phải bỏ đi, hắn vẫn ôm hận và mơ giành trọn Nộ Triều thành. Thất bại chưa khiến kẻ này từ bỏ tham vọng lẫn ý đồ hãm hại.
46|Trở về phòng, Cừu Yêu Nhi cũng gần mất kiểm soát bởi thuốc. Nàng tìm nữ đại phu vì tin người vừa cứu mình có thể giải được chuyện này.
48|Nhưng người nàng bế dậy lại là Thẩm Lãng đang mê man. Lớp cải trang bị đẩy vào một tình huống mà chính hắn cũng không thể lường trước.
59|Bên ngoài, các nữ võ sĩ tiếp tục tập luyện theo lệnh đội trưởng để che tiếng động trong phòng. Biến cố đêm ấy được giữ kín sau những bức tường thành.
'''
DATA[143] = '''
2|Mộc Lan làm việc trong quân nhiều ngày mới về tới phủ. Nàng muốn gặp chồng nhưng chỉ biết Thẩm Lãng đã ra ngoài mà không nói rõ mình đi đâu.
13|Khi nghe hắn tới Nộ Triều thành cứu Cừu Yêu Nhi, nàng cố gạt những ý nghĩ ghen tuông. Điều nàng lo nhất vẫn là chồng gặp nguy hiểm nơi đất địch.
16|Ở thành chủ phủ, Cừu Kiêu đòi cha xử lý Cừu Yêu Nhi. Hắn nhấn mạnh nàng chỉ là con nuôi và đã có cả một vạn người dưới trướng.
18|Cừu Thiên Nguy nói nàng chỉ mê chiến đấu và thám hiểm, không ham quyền lực. Ông ta không xem sức mạnh của con gái nuôi là lý do phải loại bỏ nàng lúc này.
20|Ông biết rõ những ý nghĩ đê tiện của con trai và cảnh cáo nếu không nể tình cha, Cừu Kiêu đã sớm bị nàng giết. Hắn không được tiếp tục chọc giận nàng.
22|Khi ông dẫn quân đánh Vọng Nhai, Nộ Triều thành vẫn cần Cừu Yêu Nhi trấn thủ. Chỉ thực lực của nàng mới bảo đảm hậu phương không xảy ra biến cố.
24|Cừu Kiêu được lệnh ra đảo tận mắt xác nhận mỏ vàng. Cha hắn muốn bằng chứng thật trước khi điều đại quân vào cuộc tranh đoạt.
34|Sáng hôm sau, Thẩm Lãng tỉnh dậy với ký ức đứt quãng về đêm bị bỏ thuốc. Hắn vừa hoảng hốt về những gì xảy ra, vừa nghĩ tới Mộc Lan đang ở nhà.
43|Thiên Thiên gặp lại hắn và nổi giận trước cách trêu chọc vô duyên. Cả hai vẫn phải che giấu chuyện trong phòng, trong khi âm mưu ngoài kia còn chưa dừng lại.
48|Nàng báo Cừu Thiên Nguy đang gặp nữ tướng và đã biết có nữ đại phu tới phủ. Vỏ bọc giúp Thẩm Lãng lẻn vào nay lại khiến thành chủ chú ý.
54|Hải tặc vương muốn đưa người có y thuật cao về thành chủ phủ chữa nội thương cho mình. Cừu Yêu Nhi lập tức hỏi làm sao nghĩa phụ biết tới vị khách ấy.
57|Lục Y nhận đã bẩm báo tất cả, lấy cớ phải điều tra vụ đầu bếp bị diệt khẩu. Nàng ta tiếp tục mượn lòng lo cho chủ nhân để giải thích hành động đáng ngờ.
'''
DATA[144] = '''
2|Lục Y còn nhắc thân phận con dâu Trương Xung của Thiên Thiên để gieo nghi ngờ. Cừu Yêu Nhi vẫn bình thản, không để nàng ta kéo câu chuyện sang hướng khác.
5|Cừu Thiên Nguy nói rõ muốn đưa nữ đại phu về phủ mình. Cừu Yêu Nhi từ chối theo cách thẳng thắn khiến cả nghĩa phụ và Lục Y đều sững sờ.
19|Sau cuộc gặp, nàng gọi Lục Y theo mình về phòng. Thẩm Lãng cùng Thiên Thiên đều hiểu chuyện cần giải quyết cuối cùng cũng tới.
23|Cừu Yêu Nhi nói mê hương đêm qua bị hạ độc và có người cấu kết Cừu Kiêu. Lục Y lập tức làm ra vẻ kinh ngạc trước điều mình vừa nghe.
31|Nàng ta đòi bằng chứng rồi quay sang tố Thiên Thiên. Theo lời nàng, nữ đại phu và người dẫn tới mới là những kẻ đã bày kế hại chủ nhân.
34|Lục Y thậm chí đề nghị giết cả hai để giữ kín chuyện. Cách đổ lỗi ấy khiến lời biện hộ càng trở thành một sự phản bội rõ ràng.
35|Thẩm Lãng chỉ thẳng người cấu kết Cừu Kiêu chính là Lục Y. Hắn không để kẻ đứng bên cạnh nữ tướng tiếp tục mượn danh trung thành để thao túng.
44|Các hộ vệ khống chế Lục Y theo lệnh chủ nhân. Bằng chứng quan hệ giữa nàng và Cừu Kiêu bị phát hiện, khiến nàng không thể tiếp tục chối quanh.
51|Nàng khóc rằng mình bị thiếu chủ ép buộc, vừa kể công hầu hạ vừa xin được tha. Nhưng Cừu Yêu Nhi không còn tin những lời đó.
61|Lục Y vẫn mặc cả: nếu được nhận làm nghĩa muội, nàng sẽ khai mọi âm mưu trước thành chủ. Ngay lúc lộ chuyện, nàng còn muốn đổi lời khai lấy địa vị.
63|Nữ tướng đặt tay lên đầu khiến Lục Y tưởng mình được chấp nhận. Khoảnh khắc hy vọng ngắn ngủi kết thúc bằng một đòn trừng phạt dứt khoát.
67|Kẻ phản chủ gục xuống giữa phòng. Thẩm Lãng chứng kiến và hiểu Cừu Yêu Nhi có thể cưu mang người gặp nạn, nhưng sẽ không dung thứ sự phản bội.
'''
DATA[145] = '''
2|Giải quyết Lục Y xong, Cừu Yêu Nhi không muốn nghe giải thích về thân phận khách tới. Nàng nói mình chẳng có hứng thú truy hỏi họ là ai hay tới đây vì mục đích gì.
3|Nàng chỉ hỏi câu chuyện Thiên Thiên kể có phải do Thẩm Lãng viết. Khi hắn nhận, nàng khen trong đầu hắn dường như có cả một thế giới khác.
6|Nữ tướng đưa một rương vàng rồi bảo hắn rời đi. Chuyến cứu người mang lại ân tình, nhưng chưa giúp hắn đạt điều mình thật sự muốn ở Nộ Triều thành.
13|Thiên Thiên quỳ xin ở lại, thú nhận mình đã phối hợp với Thẩm Lãng để trả thù Trương gia. Nàng kể cả quá khứ tan cửa nát nhà và sự ngưỡng mộ dành cho nữ tướng.
17|Cừu Yêu Nhi đẩy nàng ra nhưng vẫn không giết. Thiên Thiên tiếp tục bám lấy chủ nhân, còn Thẩm Lãng chỉ biết lo nàng nói thêm những điều bất lợi.
24|Hắn bị yêu cầu hóa trang lại và đưa khỏi Lôi Châu đảo. Nữ tướng còn cấm hắn quay lại, dù vẫn công nhận món nợ cứu mạng.
28|Cừu Yêu Nhi nói rương vàng là bồi thường thương tích. Ân tình chữa bệnh nàng vẫn ghi nhớ và sẽ trả nếu hắn cần trong tương lai.
29|Nhưng nàng không thể phản bội nghĩa phụ, người từng cứu mạng khi nàng trôi dạt trên biển. Đó là giới hạn Thẩm Lãng chưa thể vượt qua bằng vài lời thuyết phục.
33|Sau cuộc gặp, hắn cho rằng chuyến đi vẫn đạt nhiều kết quả vì Thiên Thiên được ở lại. Hắn cũng đã chuẩn bị thêm quân bài cho thời khắc quyết định.
36|Điều làm hắn bối rối nhất lúc này lại là Mộc Lan. Cuộc đối đầu với hải tặc còn có thể tính toán, còn chuyện phải nói với vợ thì chẳng dễ chút nào.
39|Ở Kim gia, Kim Trác bận điều quân, dân phu và vật tư ra Vọng Nhai. Có Hoàng Đồng phối hợp, những hạng mục Thẩm Lãng yêu cầu dần hoàn tất.
43|Ông tin chỉ cần kẻ địch tới là sẽ rơi vào lưới đã giăng. Sau khi trấn an phu nhân, ông dẫn một nghìn tinh nhuệ cùng ba nghìn dân phu lên thuyền ra đảo.
'''

def chapter_beats(n):
    beats=[]
    for line in DATA[n].strip().splitlines():
        p,t=line.split('|',1)
        beats.append({'panel':f'crmn_ep{n}/p{int(p):03d}.jpg','type':'BUILD','kind':'recap','narration':t})
    beats[0]['section']=f'Tập {n}'
    return beats

def make_long(start, comments=None):
    beats=[]
    for n in range(start,start+10):
        if n in DATA: chunk=chapter_beats(n)
        else:
            src=read(SERIES/f'ep{n}/script.json')['beats']
            ids=sorted({round(i*(len(src)-1)/15) for i in range(16)})
            chunk=[dict(src[i],panel=f'crmn_ep{n}/'+src[i]['panel'],kind='recap') for i in ids]
            chunk[0]['section']=f'Tập {n}'
        beats.extend(chunk)
        if comments and n in comments:
            beats.append(dict(panel=chunk[-1]['panel'],type='BUILD',kind='commentary',narration=comments[n]))
    save_script(f'long_{start}_{start+9}', {'template':'manhua_recap_long_vi','title':f'Chàng Rể Mạnh Nhất Lịch Sử | Tập {start}–{start+9}','source_dir':f'manhua-recap/crmn_ep{start}','chapters':f'{start-1}-{start+8}','description':f'Thẩm Lãng và những bước ngoặt trong cuộc đối đầu bảo vệ Kim gia, tập {start}–{start+9}.','beats':beats})

def short(number,title,rows):
    beats=[]
    for n,p,t in rows:
        beats.append({'panel':f'crmn_ep{n}/p{p:03d}.jpg','type':'BUILD','kind':'recap','narration':t})
    # One explicit host observation, attached to the preceding story frame.
    b=beats.pop(-2)
    b['kind']='commentary'
    beats.insert(-1,b)
    save_script(f'best_of/cr_s{number:02d}', {'title':title,'source_dir':f'manhua-recap/crmn_ep{rows[0][0]}','description':title,'beats':beats})

SHORTS = [
(15,'Chín nhà quý tộc thua một hoàng tử bị ghét!?','''
127|6|Giữa lúc Kim gia mắc nợ bảy mươi vạn, một hoàng tử mang gần hết tài sản tới giúp.
124|64|Không trả đúng hạn, họ sẽ mất đảo Vọng Nhai vào tay Ẩn Nguyên Hội.
127|25|Trương Tấn đếm từng ngày chờ gia tộc sụp đổ, chẳng tin họ còn cách cứu vãn.
127|27|Mộc Lan tìm tới chín nhà quý tộc, nhưng tổng cộng chỉ vay được một nghìn kim tệ.
127|2|Người chủ động xuất hiện lại là Ngũ vương tử Ninh Chính, vốn chẳng được hoàng gia coi trọng.
127|3|Chàng từng bị gán điềm xấu từ khi chào đời, ngay cả mạng sống cũng suýt không giữ được.
127|4|Năm ấy, Tô Bội Bội đã cầu xin quốc quân tha cho đứa trẻ vô tội.
127|6|Bây giờ chàng mang gần hai vạn kim tệ đến đáp lại ân tình ấy.
127|6|Với món nợ của Kim gia, số tiền vẫn còn thiếu rất xa.
127|6|Nhưng đó gần như là toàn bộ những gì Ninh Chính có thể lấy ra.
127|27|Chín nhà quý tộc có tiền lại chẳng sẵn lòng giúp họ vượt nạn.
127|6|Giá trị của lần giúp đỡ này nằm ở phần người cho dám hy sinh, khiến Ninh Chính nổi bật hơn cả những nhà giàu kia.
127|28|Thẩm Lãng vẫn giữ một kế hoạch khác. Hạn trả nợ đang tới, hắn sắp phải lật lá bài thật sự.
'''),
(16,'Một chiếc gương đổi cả vận mệnh Kim gia!?','''
128|24|Thẩm Lãng mang một chiếc gương ra và đòi thương lượng tới một trăm vạn kim tệ.
124|64|Hắn cần trả món nợ bảy mươi vạn để giữ đảo Vọng Nhai cho Kim gia.
128|19|Thiên Đạo Hội ban đầu muốn mua ruộng cùng tòa thành với hai mươi chín vạn.
128|20|Nhưng hắn quyết giữ thành, vì đó là gốc rễ quân sự của cả gia tộc.
128|24|Thứ được đem ra thay thế khiến các vị khách kinh ngạc: gương phản chiếu rõ chưa từng thấy.
128|32|Hắn nói giá thành còn chưa tới một lượng bạc, sản xuất nhiều lại càng rẻ.
128|33|Còn giá bán có thể lên tới một trăm kim tệ một chiếc.
128|35|Thiên Đạo Hội lập tức muốn nhập hàng, nhưng số sẵn có chỉ một nghìn chiếc.
128|44|Khi hắn yêu cầu một trăm vạn, họ ép xuống bốn mươi vạn.
128|45|Họ biết thời hạn trả nợ đã gần, tưởng hắn nhất định phải nhượng bộ.
128|47|Thẩm Lãng nhắc cơ hội dùng gương vượt qua đối thủ Ẩn Nguyên Hội.
128|47|Hắn khiến người mua nhìn thấy lợi ích dài hạn, nhờ vậy bớt bị mắc kẹt trong áp lực trả nợ trước mắt.
129|1|Đúng lúc ấy Hoàng Đồng đích thân tới. Cuộc mặc cả sắp bước sang một hướng hoàn toàn khác.
'''),
(17,'Kiếm Vương bị nhờ làm chuyện không ngờ tới!?','''
123|5|Một lần mang ơn cứu mạng, Kiếm Vương lại bị nhờ giúp chàng rể trả đũa tiểu thư kiêu ngạo.
122|43|Tiết Lệ tới quán trọ đòi phòng tốt nhất, coi thường người đang ở là Thẩm Lãng.
122|46|Hắn nhận ra đây chính là vị hôn thê đã muốn hủy hôn với Mộc Thông.
122|48|Nàng tiếp tục sỉ nhục, còn bắt hắn cúi mắt trước mình.
122|58|Thẩm Lãng ngoài mặt nhẫn nhịn nhưng âm thầm chuẩn bị một trò gây kích ứng ngoài da.
123|1|Hắn cho làm lại y phục giống hệt đồ nàng đang dùng.
123|2|Mùi hương cũng được chuẩn bị để tránh nàng phát hiện bất thường.
123|3|Nhưng muốn đánh tráo giữa vòng hộ vệ thì phải cần một cao thủ.
123|4|Thẩm Lãng liền nhờ Lý Thiên Thu dùng võ công giúp mình lần này.
123|5|Kiếm Vương không ngờ ân tình lớn lại được đổi lấy một chuyện dở khóc dở cười.
123|6|Hắn vẫn khẳng định chỉ người đủ giỏi mới vượt được đám người bảo vệ Tiết Lệ.
123|5|Tình huống hài nằm ở sự chênh lệch: ân tình cứu mạng được Thẩm Lãng đem dùng cho một trò trả đũa cá nhân.
123|43|Sau đó Tiết Lệ đau rát suốt chuyến đi, còn chưa hiểu thứ gì đã khiến mình khổ sở như thế.
'''),
(18,'Thẩm Lãng khiến chủ nợ ngập trong mưa vàng!?','''
132|44|Chủ nợ kéo tới lấy đảo, Thẩm Lãng lại trả lời bằng một cơn mưa kim tệ ngay giữa đại sảnh.
131|53|Kim gia còn thiếu bảy mươi vạn, ai cũng nghĩ gia tộc hết đường xoay xở.
131|63|Ẩn Nguyên Hội bắt ký giấy, yêu cầu giao đảo Vọng Nhai trong ba ngày.
132|14|Thẩm Lãng không ký ngay mà gọi mọi chủ nợ đứng ra một lượt.
132|16|Khoản nào hắn cũng nhận, khiến đối phương tưởng chàng rể đã phát điên.
132|31|Bọn họ còn đề nghị bán ruộng, bán nhà để trả tiền.
132|33|Tổng số bị đòi tăng lên tám mươi vạn kim tệ, lớn hơn cả món nợ ban đầu.
132|36|Hắn bỗng bật cười rồi xé bỏ lớp áo ngoài trước mặt tất cả.
132|39|Bộ y phục xa xỉ bên trong báo hiệu kẻ đang bị khinh thường chẳng hề túng quẫn.
132|44|Ngay sau hiệu lệnh, vàng từ phía trên đổ xuống, phủ kín bàn ghế.
132|47|Hắn cùng Mộc Lan đứng dưới ô, bình thản nhìn đám chủ nợ chết lặng.
132|62|Trả công khai khiến mọi quan viên đều trở thành người chứng kiến, chặn đường đối phương tiếp tục dùng giấy nợ ép giao đảo.
133|4|Nhưng Ninh Cảnh vẫn đe dọa: có tiền chưa chắc có mạng tiêu. Ván cờ chưa dừng ở chuyện trả nợ.
'''),
(19,'Thẩm Lãng giăng mỏ vàng giả dụ hải tặc!?','''
134|17|Để kéo hải tặc vào bẫy, Thẩm Lãng biến một mỏ sắt cũ thành mỏ vàng trong mắt thiên hạ.
133|31|Tin hắn trả tám mươi vạn khiến Đường Luân choáng váng, không hiểu tiền từ đâu tới.
134|14|Trong khi đối thủ còn đoán, hắn đề nghị Kim gia chiêu thêm hai nghìn quân.
134|16|Bốn nghìn người sẽ được đưa ra Vọng Nhai, còn trong phủ chỉ giữ lực lượng nhỏ.
134|17|Thiên Đạo Hội ứng tiền giúp trang trí đảo thành nơi đang khai thác vàng.
134|18|Tăng quân và xây thành làm người ngoài tin đảo này chứa một nguồn lợi khổng lồ.
134|34|Lời đồn về vàng mới luyện lan đi nhanh chóng, đúng như điều hắn chờ.
134|36|Đường Luân nhìn số vàng và càng tin Kim gia vừa phát hiện mỏ lớn.
134|57|Trương Xung lại nhắc ông ta phải tận mắt xác minh trước khi hành động.
134|59|Nhưng ai vào đảo cũng có thể bị giết, người được chọn phải có chỗ dựa thật mạnh.
134|61|Cái tên bật ra là Cừu Kiêu, con của hải tặc vương.
134|64|Mồi nhử hiệu quả vì đối thủ tưởng mình tự khám phá bí mật, rồi chủ động chọn người bước vào cái bẫy.
134|65|Trương Xung âm thầm mỉm cười. Ông vừa đưa Cừu Kiêu tới dưới mũi kiếm của Thẩm Lãng.
'''),
(20,'Nữ sát thần nợ chàng rể một mạng sống!?','''
139|54|Cừu Yêu Nhi hứa trả một ân tình, còn Thẩm Lãng vừa cứu nàng mà vẫn phải giấu thân phận.
135|19|Hắn nhận thư cầu cứu từ Thiên Thiên, biết nữ tướng đang gặp nguy hiểm.
135|20|Nếu nàng chết, kế hoạch của hắn ở Nộ Triều thành cũng sẽ đổ vỡ.
135|32|Hắn hóa trang thành nữ đại phu rồi nhờ Hoàng Phượng bảo vệ trên đường đi.
137|4|Đến nơi mới biết nàng đau đớn, chóng mặt và không thể mở mắt bình thường.
137|5|Nàng dùng chân khí chống đỡ, nhưng cách ấy không giải quyết được nguyên nhân.
137|21|Thẩm Lãng phát hiện dấu hiệu hạ độc trong thức ăn, tích tụ qua nhiều ngày.
138|22|Không chỉ vậy, trong đầu nàng còn có vấn đề nguy hiểm buộc hắn phải chữa ngay.
139|22|Thiên Thiên nghe phương pháp liều lĩnh thì lo sợ, gần như không thể tin được.
139|23|Nữ tướng lại đồng ý dứt khoát, giao sinh mạng vào tay vị khách lạ.
139|47|Chính võ công của nàng giúp hoàn tất phần Thẩm Lãng không đủ sức thực hiện.
139|51|Cảnh này thuyết phục ở sự phối hợp: một người nhìn ra bệnh, một người đủ quyết đoán và sức mạnh để vượt qua hiểm cảnh.
139|54|Chữa trị thành công, nàng hứa giúp điều mình làm được. Trong đầu hắn lập tức hiện lên mục tiêu Nộ Triều thành.
'''),
(21,'Cừu Kiêu tưởng thắng lại gặp nữ sát thần!?','''
142|35|Cừu Kiêu tưởng nữ tướng mắc kẹt vì thuốc, ai ngờ nàng trở về ngay lúc hắn đang hành hung hộ vệ.
140|58|Trước đó Cừu Yêu Nhi phát hiện lò hương bị pha thêm thứ thuốc nguy hiểm.
141|8|Nàng cố giữ tỉnh táo rồi ra bờ biển dự trận quyết đấu đã hẹn.
141|12|Đối thủ là Chúc Hồng Tuyết, cao thủ đứng đầu thế hệ trẻ.
141|32|Hai người dồn lực giao phong, để lại một hố lớn trên bãi biển.
141|39|Chúc Hồng Tuyết nhận thua vì mình gần cạn sức, còn nàng vẫn chưa tới giới hạn.
141|51|Trong phủ, Thẩm Lãng lại bị hương thuốc làm mê man, không thể tự thoát ra.
141|55|Cừu Kiêu tới cửa phòng, bị nữ võ sĩ chặn lại theo đúng mệnh lệnh chủ nhân.
142|6|Hắn gào thành trì thuộc nhà mình rồi rút kiếm tấn công cả đội.
142|31|Các nữ võ sĩ vẫn bảo vệ căn phòng, dù nhiều người đã bị thương.
142|35|Một đòn bất ngờ chặn hắn, Cừu Yêu Nhi đã đứng sau từ lúc nào.
142|38|Lòng trung thành của các hộ vệ giữ được cánh cửa đủ lâu, khiến sự tính toán của Cừu Kiêu đổ vỡ ngay trước đích.
142|40|Nàng tuyên bố lần này không thể tha rồi vung đòn trừng phạt kẻ vừa hại người của mình.
'''),
(22,'Lục Y lộ phản bội vẫn đòi làm nghĩa muội!?','''
144|61|Bị lộ phản bội, Lục Y vẫn xin làm nghĩa muội rồi mới chịu khai âm mưu của thiếu chủ.
143|57|Trước đó nàng lấy cớ điều tra đầu bếp để báo mọi chuyện với Cừu Thiên Nguy.
144|19|Cừu Yêu Nhi đưa nàng về phòng, nơi Thẩm Lãng và Thiên Thiên đang đợi.
144|23|Nữ tướng nói lò hương bị bỏ thuốc, có người cấu kết với Cừu Kiêu.
144|31|Lục Y lập tức đòi bằng chứng rồi quay sang tố ngược Thiên Thiên.
144|33|Nàng nói nữ đại phu được đưa tới chính là người cùng bày kế hại chủ nhân.
144|34|Thậm chí nàng còn đề nghị giết cả hai để không ai biết chuyện.
144|35|Thẩm Lãng chỉ thẳng kẻ phản chủ đang đứng ngay trước mặt.
144|44|Hộ vệ khống chế Lục Y và phát hiện bằng chứng quan hệ của nàng với Cừu Kiêu.
144|51|Nàng lại khóc rằng bị ép, nhắc công hầu hạ để xin tha mạng.
144|61|Rồi nàng đề nghị đổi lời khai lấy danh phận nghĩa muội của nữ tướng.
144|62|Lời mặc cả khiến sự trung thành cuối cùng cũng mất sức nặng: ngay khi bị bắt, nàng vẫn muốn dùng chủ nhân làm bậc thang đổi đời.
144|63|Cừu Yêu Nhi đặt tay lên đầu. Lục Y tưởng được chấp nhận, nhưng quyết định thật sự của nữ tướng lại hoàn toàn khác.
'''),
(23,'Tự mang đồ ăn vẫn mắc bẫy Thẩm Lãng!?','''
149|29|Cừu Kiêu dự tiệc nhưng tự mang đồ ăn, tưởng như thế là tránh được mọi cái bẫy của Thẩm Lãng.
148|60|Hắn đã tận mắt thấy vàng trên đảo Vọng Nhai và gửi tin về cho cha.
149|19|Cừu Thiên Nguy lập tức muốn giành tám phần lợi ích, còn đòi đóng quân giữ mỏ.
149|48|Đến bàn thương lượng, Cừu Kiêu chẳng tin đồ ăn nước uống mà Kim gia chuẩn bị.
149|53|Hắn ép đối phương nhận yêu cầu, dựa vào võ công và cả trăm hộ vệ sát bên.
149|47|Thẩm Lãng vẫn hạ giọng, làm ra vẻ chịu nhục trước những lời xúc phạm.
150|11|Đúng lúc ấy một người hầu tới lau rượu đổ trên bàn, có cơ hội tới gần thiếu chủ.
150|16|Sự cảnh giác của hắn biến mất khi nổi lòng đê tiện với người đang phục vụ.
150|19|Thuốc bắt đầu phát tác, khiến kẻ luôn tự tin vào sức mạnh không còn khống chế nổi bản thân.
150|21|Kim Trác lập tức ra tay, còn Thẩm Lãng xuất hiện để khóa chặt tình thế.
150|27|Thiếu chủ thành con tin, hộ vệ bên ngoài không dám hành động tùy tiện.
150|29|Cừu Kiêu đề phòng bữa ăn nhưng lại để sự kiêu ngạo phá hỏng cảnh giác. Thẩm Lãng chỉ cần đúng khoảnh khắc ấy.
150|48|Phục binh bắt đầu bắn tên. Nhưng dưới vách núi, hải tặc vẫn đang tràn lên và trận đánh thật sự mới mở màn.
''')]

def make_shorts():
    for number,title,raw in SHORTS:
        rows=[]
        for line in raw.strip().splitlines():
            n,p,t=line.split('|',2); rows.append((int(n),int(p),t))
        short(number,title,rows)

if __name__=='__main__':
    make_long(121,{124:'Việc bỏ đảo và để lại tiếp tế khiến hải tặc tưởng mình thắng quá dễ. Cách Thẩm Lãng chấp nhận thiệt trước mắt báo hiệu hắn đang nhắm tới một kết quả xa hơn.',127:'Khoản giúp đỡ của Ninh Chính nhỏ hơn món nợ rất nhiều, nhưng gần như là tất cả những gì chàng có. Đặt cạnh chín nhà quý tộc, hành động ấy cho thấy ai thật sự coi trọng tình nghĩa.',128:'Thẩm Lãng giữ lại tòa thành vì hiểu tiền có thể kiếm lại, còn căn cứ quân sự mất đi sẽ kéo theo cả quyền tự chủ. Chính sự cứng rắn đó giúp hắn giữ thế khi đàm phán.'})
    make_long(131,{132:'Mưa vàng vừa trả nợ vừa buộc quan viên chứng kiến công khai. Cách Thẩm Lãng phô trương số tiền khiến đối thủ hết đường dùng tin đồn nghèo túng để tiếp tục ép giao đảo.',134:'Cái bẫy này dựa vào những dấu hiệu người ngoài tự ghép lại: vàng mới, quân mới và công trình mới. Khi tin mình vừa phát hiện một bí mật, đối thủ càng khó nhận ra có người cố ý cho mình thấy nó.',139:'Điểm hay của cảnh cứu người nằm ở sự phối hợp. Thẩm Lãng nhìn ra vấn đề, còn Cừu Yêu Nhi có sức mạnh và quyết đoán để thực hiện điều hắn không thể tự làm.'})
    make_long(141,{144:'Lục Y muốn dùng lời khai để mua địa vị ngay cả khi đã bị lộ. Chi tiết ấy khiến lời hứa trung thành mất hết sức nặng, bởi điều nàng còn tính vẫn là lợi ích của riêng mình.',147:'Mộc Thông lựa chọn rời nhà đúng lúc mọi người lo sợ nhất. Sự trưởng thành của cậu khiến cuộc chia tay có ý nghĩa hơn một mệnh lệnh từ triều đình.',149:'Cừu Kiêu cẩn thận với đồ ăn nhưng vẫn tin thân phận đủ bảo vệ mình. Thẩm Lãng đang chờ sơ hở trong sự kiêu ngạo đó để biến cuộc thương lượng thành một cái bẫy.'})
    make_shorts()
