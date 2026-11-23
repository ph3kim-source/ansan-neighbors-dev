// 화면 글 — 한국어 · English · 中文 · Русский · Tiếng Việt (결정 D4: 공식 언어 5개). 기타 언어방 주민은 영어 화면.
// 가게 이름 · 주소는 간판처럼 한국어 그대로 둔다.
export const LANGS = ['ko', 'en', 'zh', 'ru', 'vi'];
export const LANG_NAME = { ko: '한국어', en: 'English', zh: '中文', ru: 'Русский', vi: 'Tiếng Việt' };
const LOCALE = { ko: 'ko-KR', en: 'en-US', zh: 'zh-CN', ru: 'ru-RU', vi: 'vi-VN' };
const IDX = { ko: 0, en: 1, zh: 2, ru: 3, vi: 4 };

const T = {
  'app': ['안산 이웃', 'Ansan Neighbors', '安山邻居', 'Соседи Ансана', 'Hàng xóm Ansan'],
  'tab.home': ['홈', 'Home', '首页', 'Главная', 'Trang chủ'],
  'tab.map': ['지도', 'Map', '地图', 'Карта', 'Bản đồ'],
  'tab.community': ['커뮤니티', 'Community', '社区', 'Общение', 'Cộng đồng'],
  'tab.news': ['소식', 'News', '资讯', 'Новости', 'Tin tức'],
  'tab.me': ['나', 'Me', '我的', 'Профиль', 'Tôi'],
  'back': ['뒤로', 'Back', '返回', 'Назад', 'Quay lại'],
  'close': ['닫기', 'Close', '关闭', 'Закрыть', 'Đóng'],
  'cancel': ['취소', 'Cancel', '取消', 'Отмена', 'Hủy'],
  'save': ['저장', 'Save', '保存', 'Сохранить', 'Lưu'],
  'next': ['다음', 'Next', '下一步', 'Далее', 'Tiếp'],
  'loading': ['불러오는 중…', 'Loading…', '加载中…', 'Загрузка…', 'Đang tải…'],
  'err.network': ['연결이 안 돼요. 잠시 뒤 다시 해 주세요', 'Connection problem — please try again', '网络连接失败，请稍后再试', 'Нет связи — попробуйте ещё раз', 'Lỗi kết nối — vui lòng thử lại'],
  'err.generic': ['잠시 문제가 생겼어요', 'Something went wrong', '出了点问题', 'Что-то пошло не так', 'Đã xảy ra lỗi'],
  'demo.ribbon': ['시연판 · 가게는 실제 공공자료, 글 · 행사 · 고향 사람 지도는 예시예요', 'Demo · shops are real public data; posts, events and the people map are samples', '演示版 · 店铺为真实公共数据，帖子、活动和老乡地图为示例', 'Демо · магазины — реальные открытые данные, посты, события и карта земляков — примеры', 'Bản demo · cửa hàng là dữ liệu công thật, bài viết, sự kiện và bản đồ đồng hương là mẫu'],
  'real.ribbon': ['시연판 · 가게와 고향 사람 지도는 실제 자료, 글 · 행사는 예시예요', 'Demo · shops and the people map use real data; posts and events are samples', '演示版 · 店铺和老乡地图为真实数据，帖子和活动为示例', 'Демо · магазины и карта земляков — реальные данные, посты и события — примеры', 'Bản demo · cửa hàng và bản đồ đồng hương là dữ liệu thật, bài viết và sự kiện là mẫu'],

  // 시작
  'w.title': ['안산에 사는 이웃을 위한 앱', 'For neighbors who live in Ansan', '为住在安山的你', 'Для тех, кто живёт в Ансане', 'Dành cho người sống ở Ansan'],
  'w.sub': ['내 나라 가게 · 우리 말 커뮤니티 · 안산시 소식을 한곳에서', 'Shops from home, talk in your language and city news — in one place', '家乡店铺 · 母语社区 · 安山市消息，一个App全搞定', 'Магазины с родины, общение на родном языке и новости города', 'Cửa hàng quê nhà, cộng đồng tiếng mẹ đẻ và tin tức thành phố'],
  'w.lang': ['언어를 고르세요', 'Choose your language', '选择语言', 'Выберите язык', 'Chọn ngôn ngữ'],
  'w.start': ['시작하기', 'Get started', '开始使用', 'Начать', 'Bắt đầu'],
  'w.demo': ['시연 계정으로 둘러보기', 'Look around with a demo account', '用演示账号看看', 'Посмотреть с демо-аккаунтом', 'Xem thử bằng tài khoản mẫu'],
  'w.who': ['어떤 이웃인가요?', 'Who are you?', '你是哪类邻居？', 'Кто вы?', 'Bạn là ai?'],
  'w.foreign': ['안산에 사는 외국인 주민', 'A foreign resident of Ansan', '住在安山的外国居民', 'Иностранный житель Ансана', 'Cư dân nước ngoài ở Ansan'],
  'w.foreignSub': ['동포 · 귀화자도 여기예요', 'Including ethnic Koreans and naturalized citizens', '包括同胞和入籍者', 'Включая соотечественников и натурализованных', 'Gồm cả kiều bào và người nhập tịch'],
  'w.korean': ['한국인 이웃', 'A Korean neighbor', '韩国邻居', 'Местный житель (кореец)', 'Hàng xóm người Hàn'],
  'w.koreanSub': ['교류방에서 함께해요', 'Join the Exchange room', '在交流区一起聊', 'Общение в комнате «Обмен»', 'Tham gia phòng Giao lưu'],
  'w.nat': ['국적을 고르세요', 'Your nationality', '选择国籍', 'Ваше гражданство', 'Quốc tịch của bạn'],
  'w.dong': ['사는 동네를 고르세요', 'Which neighborhood do you live in?', '你住在哪个洞？', 'В каком районе вы живёте?', 'Bạn sống ở phường nào?'],
  'w.search': ['찾기', 'Search', '搜索', 'Поиск', 'Tìm'],
  'w.privacy': ['이름 · 연락처 · 체류자격은 묻지 않아요. 국적 · 언어 · 동네로만 맞춤 소식을 보내요.', 'We never ask for your name, phone or visa status — only nationality, language and neighborhood.', '我们不收集姓名、电话和签证身份，只按国籍、语言和所住洞推送消息。', 'Мы не спрашиваем имя, телефон и визовый статус — только гражданство, язык и район.', 'Chúng tôi không hỏi tên, số điện thoại hay tình trạng visa — chỉ quốc tịch, ngôn ngữ và phường.'],
  'w.done': ['가입했어요', 'You’re in', '注册完成', 'Готово', 'Đã đăng ký'],
  'w.demoNote': ['시연 계정은 예시 사용자예요', 'Demo accounts are sample users', '演示账号是示例用户', 'Демо-аккаунты — примеры', 'Tài khoản mẫu là người dùng ví dụ'],

  // 홈
  'h.morning': ['좋은 아침이에요', 'Good morning', '早上好', 'Доброе утро', 'Chào buổi sáng'],
  'h.afternoon': ['좋은 오후예요', 'Good afternoon', '下午好', 'Добрый день', 'Chào buổi chiều'],
  'h.evening': ['좋은 저녁이에요', 'Good evening', '晚上好', 'Добрый вечер', 'Chào buổi tối'],
  'h.night': ['오늘도 수고 많았어요', 'Have a restful night', '今天也辛苦了', 'Доброй ночи', 'Hôm nay bạn vất vả rồi'],
  'h.who': ['{dong}에 사는 {nat} 이웃', 'From {nat} · living in {dong}', '住在{dong}的{nat}邻居', '{nat} · район {dong}', 'Người {nat} sống ở {dong}'],
  'h.lives': ['{dong}에 사는 이웃', 'Living in {dong}', '住在{dong}', 'Живу в районе {dong}', 'Sống ở {dong}'],
  'h.qShops': ['가게 찾기', 'Find shops', '找店铺', 'Магазины', 'Tìm cửa hàng'],
  'h.qPeople': ['고향 사람', 'People from home', '老乡在哪儿', 'Земляки', 'Đồng hương'],
  'h.qWrite': ['글쓰기', 'Write', '发帖', 'Написать', 'Viết bài'],
  'h.qAsk': ['시에 묻기', 'Ask the city', '问市政府', 'Спросить город', 'Hỏi thành phố'],
  'h.events': ['곧 열리는 행사', 'Coming up', '即将举行的活动', 'Скоро', 'Sắp diễn ra'],
  'h.shops': ['가까운 고향의 맛', 'A taste of home nearby', '附近的家乡味道', 'Вкус родины рядом', 'Hương vị quê nhà gần bạn'],
  'h.shopsWorld': ['가까운 세계 음식', 'World food nearby', '附近的异国美食', 'Мировая кухня рядом', 'Món ăn quốc tế gần bạn'],
  'h.seeMap': ['지도에서 보기', 'On the map', '在地图上看', 'На карте', 'Xem bản đồ'],
  'h.shopsBusyNote': ['고향 사람이 많이 다니는 쪽 가게부터 보여요', 'Places where people from home go come first', '老乡常去一带的店排在前面', 'Сначала места, где бывают земляки', 'Ưu tiên quán ở khu đồng hương hay qua lại'],
  'h.room': ['우리 언어방 이야기', 'From my language room', '我的语言区', 'Из моей комнаты', 'Từ phòng của tôi'],
  'h.exchange': ['교류방 이야기', 'From the Exchange room', '交流区', 'Из «Обмена»', 'Từ phòng Giao lưu'],
  'h.city': ['안산시가 알려 드려요', 'From Ansan City', '安山市通知', 'Новости города Ансан', 'Tin từ thành phố Ansan'],
  'h.more': ['더 보기', 'More', '更多', 'Ещё', 'Xem thêm'],
  'n.sample': ['예시', 'Sample', '示例', 'Пример', 'Mẫu'],
  'km': ['{n}km', '{n} km', '{n}公里', '{n} км', '{n} km'],
  'm': ['{n}m', '{n} m', '{n}米', '{n} м', '{n} m'],

  // 지도
  'map.search': ['가게 이름 찾기', 'Search a shop', '搜索店名', 'Найти магазин', 'Tìm cửa hàng'],
  'map.all': ['전체', 'All', '全部', 'Все', 'Tất cả'],
  'map.mine': ['내 나라', 'From home', '家乡', 'С родины', 'Quê nhà'],
  'map.people': ['고향 사람 많은 곳', 'People from home', '老乡在哪儿', 'Где земляки', 'Đồng hương ở đâu'],
  'map.weekday': ['평일', 'Weekday', '工作日', 'Будни', 'Ngày thường'],
  'map.weekend': ['주말', 'Weekend', '周末', 'Выходные', 'Cuối tuần'],
  'map.play': ['하루 흐름 보기', 'Play the day', '播放一天', 'Показать день', 'Xem cả ngày'],
  'map.stop': ['멈추기', 'Stop', '停止', 'Стоп', 'Dừng'],
  'map.now': ['지금', 'Now', '现在', 'Сейчас', 'Bây giờ'],
  'map.holiday': ['연휴', 'Holidays', '节假日', 'Праздники', 'Ngày lễ'],
  'map.tipHoliday': ['한국 연휴 낮엔 고향 사람들이 모이는 곳이 진해요', 'Korean holidays: gathering spots get darker', '韩国节假日白天：老乡聚会的地方颜色更深', 'Корейские праздники днём: темнее места встреч', 'Ngày lễ Hàn Quốc: nơi đồng hương tụ tập đậm hơn'],
  'map.cellsHint': ['지도를 키우면 골목 칸(약 330m)으로 보여요', 'Zoom in to see blocks (about 330 m)', '放大地图可按街区（约330米）查看', 'Приблизьте карту — покажем кварталы (~330 м)', 'Phóng to để xem theo khu (~330 m)'],
  'map.cellsOn': ['골목 칸(약 330m)으로 보고 있어요 · 사람이 적은 칸은 칠하지 않아요', 'Showing blocks (about 330 m) · blocks with few people stay blank', '正在按街区（约330米）显示 · 人少的格子不上色', 'Показаны кварталы (~330 м) · где мало людей — без цвета', 'Đang xem theo khu (~330 m) · khu ít người không tô màu'],
  'map.cellsNone': ['이 나라는 골목 단위 자료가 부족해 동네 단위로만 보여요', 'Not enough block-level data for this country — neighborhoods only', '该国街区级数据不足，只按洞显示', 'Для этой страны мало данных по кварталам — только районы', 'Không đủ dữ liệu theo khu cho nước này — chỉ theo phường'],
  'map.cellsHoliday': ['연휴는 동네 단위로만 보여요', 'Holidays are shown by neighborhood only', '节假日只按洞显示', 'Праздники — только по районам', 'Ngày lễ chỉ hiện theo phường'],
  'map.ppInfoHoliday': ['연휴는 한국 공휴일({days})을 모아 본 거예요.', 'Holidays combine Korean public holidays ({days}).', '节假日汇总了韩国公休日（{days}）。', 'Праздники — это корейские выходные дни ({days}).', 'Ngày lễ là tổng hợp các ngày nghỉ lễ của Hàn Quốc ({days}).'],
  'map.ppInfoCells': ['지도를 키우면 동네보다 작은 골목 칸(약 330m 육각형)으로 보여요. 칸이 작아도 단계만 보이고, 사람이 아주 적은 칸은 칠하지 않아요.', 'Zoom in to see hexagon blocks (about 330 m), smaller than neighborhoods. Only levels are shown, and blocks with very few people stay blank.', '放大地图可看到比洞更小的街区格（约330米六边形）。只显示等级，人很少的格子不上色。', 'При приближении видны шестиугольные кварталы (~330 м). Показаны только уровни; где людей очень мало — без цвета.', 'Khi phóng to sẽ thấy các ô lục giác (~330 m) nhỏ hơn phường. Chỉ hiện mức độ, ô có rất ít người không tô màu.'],
  'map.ppWhat': ['{nat} 사람이 많은 곳', 'Where people from {nat} are', '{nat}老乡多的地方', 'Где больше земляков ({nat})', 'Nơi có nhiều người {nat}'],
  'map.ppNone': ['이 시간엔 눈에 띄게 많은 곳이 없어요', 'No place stands out at this time', '这个时间没有特别集中的地方', 'В это время заметных мест нет', 'Giờ này không có nơi nào đông nổi bật'],
  'map.tipWork': ['평일 낮엔 주로 일터 · 학교 쪽이 진해요', 'Weekday daytime: mostly workplaces and schools', '工作日白天：多在上班、上学的地方', 'Будни днём: в основном работа и учёба', 'Ban ngày trong tuần: chủ yếu nơi làm việc, học tập'],
  'map.tipHome': ['밤엔 주로 사는 동네가 진해요', 'At night: mostly where people live', '夜里：多在住的地方', 'Ночью: в основном там, где живут', 'Ban đêm: chủ yếu là nơi ở'],
  'map.tipMeet': ['주말 낮엔 장 보고 모이는 곳이 진해요', 'Weekend daytime: shopping and meeting spots', '周末白天：购物、聚会的地方', 'Выходные днём: магазины и места встреч', 'Ban ngày cuối tuần: nơi mua sắm, gặp gỡ'],
  'map.tipAny': ['진할수록 그 시간에 많이 있어요', 'Darker means more people at this time', '颜色越深，这个时间人越多', 'Темнее — больше людей в это время', 'Càng đậm càng đông vào giờ này'],
  'map.few': ['적음', 'Fewer', '少', 'Меньше', 'Ít'],
  'map.many': ['많음', 'More', '多', 'Больше', 'Nhiều'],
  'map.ppHelp': ['이 지도는 무엇인가요?', 'What does this map show?', '这张地图是什么？', 'Что показывает карта?', 'Bản đồ này là gì?'],
  'map.ppInfo1': ['고른 시간에 안산의 동네마다 {nat} 사람이 얼마나 있는지 색으로 보여 줘요. 진할수록 많아요.', 'For the time you choose, each Ansan neighborhood is colored by how many people from {nat} are there. Darker means more.', '按你选的时间，用颜色显示安山各洞有多少{nat}老乡。颜色越深人越多。', 'Для выбранного времени районы Ансана окрашены по тому, сколько там людей из страны {nat}. Темнее — больше.', 'Theo giờ bạn chọn, mỗi phường ở Ansan được tô màu theo số người {nat} ở đó. Càng đậm càng đông.'],
  'map.ppInfo2': ['고향 사람들이 모이는 곳이나 많이 사는 동네를 찾을 때 써요. 주말 낮엔 모이는 곳, 밤엔 사는 동네가 잘 보여요.', 'Use it to find where people from home meet or live: weekend daytime shows meeting spots, night shows where they live.', '可以用来找老乡聚会或居住的地方：周末白天看聚会处，夜里看住的地方。', 'Помогает найти, где земляки встречаются и живут: выходные днём — места встреч, ночь — где живут.', 'Dùng để tìm nơi đồng hương gặp gỡ hoặc sinh sống: trưa cuối tuần thấy nơi gặp gỡ, ban đêm thấy nơi ở.'],
  'map.ppInfo3': ['휴대폰 신호로 추정한 정도라서 사람 수가 아니고, 누가 어디 있는지는 알 수 없어요. 사람이 아주 적은 동네는 색을 칠하지 않아요.', 'It is an estimate from mobile network data — not a headcount, and no one can be identified. Places with very few people stay uncolored.', '这是根据手机信号估算的程度，不是人数，也无法知道谁在哪里。人很少的洞不上色。', 'Это оценка по данным мобильной сети — не число людей, и никого нельзя узнать. Районы, где людей очень мало, не окрашены.', 'Đây là ước tính từ tín hiệu di động — không phải số người, không biết được ai ở đâu. Phường có rất ít người sẽ không tô màu.'],
  'map.sample': ['예시 데이터(실제 아님)', 'Sample data (not real)', '示例数据(非真实)', 'Пример (не реальные данные)', 'Dữ liệu mẫu (không thật)'],
  'map.internal': ['실제 통신 자료({month})', 'Real mobile data ({month})', '真实通信数据（{month}）', 'Реальные данные связи ({month})', 'Dữ liệu di động thật ({month})'],
  'map.peopleEmpty': ['고향 사람 수가 적어 지도에 표시하지 않아요 — 한 사람 한 사람을 알아볼 수 없게', 'Too few people from home to show — to protect privacy', '人数太少，为保护隐私不显示', 'Слишком мало людей — скрыто ради приватности', 'Quá ít người — ẩn để bảo vệ quyền riêng tư'],
  'lv.1': ['적음', 'Few', '较少', 'Мало', 'Ít'],
  'lv.2': ['보통', 'Some', '一般', 'Средне', 'Vừa'],
  'lv.3': ['많음', 'Many', '较多', 'Много', 'Nhiều'],
  'lv.4': ['아주 많음', 'Lots', '非常多', 'Очень много', 'Rất nhiều'],
  'lv.none': ['적음', 'Few', '较少', 'Мало', 'Ít'],
  'map.add': ['가게 알려주기', 'Add a place', '推荐店铺', 'Добавить место', 'Thêm địa điểm'],
  'map.addPick': ['지도를 움직여 가운데 핀을 가게 위치에 맞추세요', 'Move the map so the pin is on the place', '移动地图，让中间的图钉对准店铺位置', 'Сдвиньте карту, чтобы метка была на месте', 'Di chuyển bản đồ để ghim nằm đúng vị trí'],
  'map.addHere': ['이 위치로', 'Use this spot', '就是这里', 'Здесь', 'Chọn vị trí này'],
  'map.addName': ['가게 · 장소 이름', 'Name of the place', '店名/地点名称', 'Название', 'Tên địa điểm'],
  'map.addKind': ['종류', 'Type', '类型', 'Тип', 'Loại'],
  'map.addCuisine': ['어느 나라 음식 · 상품인가요? (선택)', 'Which country’s food or goods? (optional)', '哪国的食品/商品？(可选)', 'Кухня или товары какой страны? (необязательно)', 'Đồ ăn/hàng của nước nào? (không bắt buộc)'],
  'map.addSend': ['알려주기', 'Send', '提交', 'Отправить', 'Gửi'],
  'map.addDone': ['고마워요! 이웃 추천 {n}개가 모이면 ‘확인됨’이 붙어요', 'Thank you! It gets “verified” after {n} neighbor likes', '谢谢！获得{n}个邻居推荐后会标记“已确认”', 'Спасибо! После {n} отметок соседей место будет «проверено»', 'Cảm ơn! Sau {n} lượt giới thiệu sẽ được “xác minh”'],
  'map.outside': ['안산 안의 위치를 골라 주세요', 'Please pick a spot inside Ansan', '请选择安山市内的位置', 'Выберите место в Ансане', 'Hãy chọn vị trí trong Ansan'],
  'map.noResult': ['찾는 가게가 없어요', 'No matching shops', '没有找到', 'Ничего не найдено', 'Không tìm thấy'],
  'map.dongShops': ['이 동네 가게 {n}곳', '{n} shops here', '这里有{n}家店', 'Здесь магазинов: {n}', '{n} cửa hàng ở đây'],
  'map.dongPosts': ['이 동네 이야기', 'Posts about here', '这里的帖子', 'Посты об этом районе', 'Bài viết về nơi này'],
  'map.nowLevel': ['{time} · {nat} 사람 {lv}', '{time} · people from {nat}: {lv}', '{time} · {nat}老乡：{lv}', '{time} · земляки ({nat}): {lv}', '{time} · người {nat}: {lv}'],
  'map.osm': ['지도 © OpenStreetMap 기여자', 'Map © OpenStreetMap contributors', '地图 © OpenStreetMap 贡献者', 'Карта © участники OpenStreetMap', 'Bản đồ © cộng tác viên OpenStreetMap'],

  'kind.food': ['음식점', 'Restaurants', '餐厅', 'Еда', 'Quán ăn'],
  'kind.grocery': ['식료품 · 마트', 'Groceries', '食品超市', 'Продукты', 'Thực phẩm'],
  'kind.service': ['생활 서비스', 'Services', '生活服务', 'Услуги', 'Dịch vụ'],
  'kind.official': ['공공 · 상담', 'Public help', '公共服务', 'Помощь', 'Hỗ trợ công'],
  'kind.community': ['이웃 제보', 'Neighbor tips', '邻居推荐', 'От соседей', 'Hàng xóm giới thiệu'],
  'kind.other': ['기타', 'Other', '其他', 'Другое', 'Khác'],
  'sub.phone': ['휴대폰', 'Phone shop', '手机店', 'Связь', 'Điện thoại'],
  'sub.travel': ['여행사', 'Travel agency', '旅行社', 'Турагентство', 'Đại lý du lịch'],
  'sub.translate': ['번역 · 통역', 'Translation', '翻译', 'Перевод', 'Dịch thuật'],
  'sub.support': ['지원 기관', 'Support center', '支援中心', 'Центр поддержки', 'Trung tâm hỗ trợ'],
  'sub.immigration': ['출입국 · 체류 민원', 'Immigration office', '出入境 · 居留', 'Миграционная служба', 'Xuất nhập cảnh · cư trú'],
  'sub.job': ['고용센터 · 일자리', 'Employment center', '就业中心', 'Центр занятости', 'Trung tâm việc làm'],
  'sub.family': ['가족센터 · 다문화가족', 'Family center', '家庭中心 · 多文化家庭', 'Семейный центр', 'Trung tâm gia đình'],
  'sub.health': ['보건소', 'Public health center', '保健所', 'Центр здоровья', 'Trung tâm y tế công'],
  'cu.cn': ['중국 · 연변', 'Chinese', '中国 · 延边', 'Китайская', 'Trung Quốc'],
  'cu.vn': ['베트남', 'Vietnamese', '越南', 'Вьетнамская', 'Việt Nam'],
  'cu.th': ['태국', 'Thai', '泰国', 'Тайская', 'Thái Lan'],
  'cu.id': ['인도네시아', 'Indonesian', '印尼', 'Индонезийская', 'Indonesia'],
  'cu.ph': ['필리핀', 'Filipino', '菲律宾', 'Филиппинская', 'Philippines'],
  'cu.kh': ['캄보디아', 'Cambodian', '柬埔寨', 'Камбоджийская', 'Campuchia'],
  'cu.mm': ['미얀마', 'Myanmar', '缅甸', 'Мьянманская', 'Myanmar'],
  'cu.np': ['네팔 · 인도', 'Nepali & Indian', '尼泊尔 · 印度', 'Непальская и индийская', 'Nepal & Ấn Độ'],
  'cu.lk': ['스리랑카', 'Sri Lankan', '斯里兰卡', 'Шри-ланкийская', 'Sri Lanka'],
  'cu.ca': ['중앙아시아 · 러시아', 'Central Asian & Russian', '中亚 · 俄罗斯', 'Центральная Азия и Россия', 'Trung Á & Nga'],
  'cu.mn': ['몽골', 'Mongolian', '蒙古', 'Монгольская', 'Mông Cổ'],
  'cu.halal': ['할랄 · 케밥', 'Halal & kebab', '清真 · 烤肉', 'Халяль и кебаб', 'Halal & kebab'],
  'cu.world': ['세계 식품', 'World foods', '世界食品', 'Продукты разных стран', 'Thực phẩm quốc tế'],
  'cu.sea': ['동남아', 'Southeast Asian', '东南亚', 'Юго-Восточная Азия', 'Đông Nam Á'],
  'cu.intl': ['외국 음식', 'International', '外国料理', 'Иностранная кухня', 'Món nước ngoài'],

  'shop.like': ['추천해요', 'Recommend', '推荐', 'Рекомендую', 'Giới thiệu'],
  'shop.likes': ['이웃 추천 {n}', '{n} neighbor likes', '{n}个邻居推荐', 'Рекомендаций: {n}', '{n} lượt giới thiệu'],
  'shop.verified': ['확인됨', 'Verified', '已确认', 'Проверено', 'Đã xác minh'],
  'shop.wrong': ['정보가 달라요', 'Report a problem', '信息有误', 'Ошибка в данных', 'Báo sai thông tin'],
  'shop.r.closed': ['문을 닫았어요', 'It has closed', '已关门', 'Закрылось', 'Đã đóng cửa'],
  'shop.r.wrong_type': ['이런 가게가 아니에요', 'Not this kind of shop', '不是这类店', 'Это другой тип', 'Không phải loại này'],
  'shop.r.wrong_place': ['위치가 달라요', 'Wrong location', '位置不对', 'Не то место', 'Sai vị trí'],
  'shop.r.other': ['다른 문제', 'Something else', '其他问题', 'Другое', 'Vấn đề khác'],
  'shop.thanks': ['고마워요. 시에서 확인할게요', 'Thanks — the city will check it', '谢谢，市政府会核实', 'Спасибо, город проверит', 'Cảm ơn, thành phố sẽ kiểm tra'],
  'shop.route': ['길찾기', 'Directions', '路线', 'Маршрут', 'Chỉ đường'],
  'shop.floor': ['{f}층', 'Floor {f}', '{f}楼', '{f} этаж', 'Tầng {f}'],
  'shop.b.category': ['공공 상가정보의 업종 분류', 'Category from the public business registry', '公共商家信息的行业分类', 'Категория из открытого реестра', 'Phân loại từ dữ liệu công'],
  'shop.b.name': ['가게 이름으로 분류했어요 — 틀리면 알려 주세요', 'Sorted by its name — tell us if it’s wrong', '按店名分类 —— 如有误请告诉我们', 'Определено по названию — сообщите, если неверно', 'Phân loại theo tên — hãy báo nếu sai'],
  'shop.b.review': ['가게 이름을 보고 골랐어요(현장 확인 전) — 틀리면 알려 주세요', 'Picked by its name (not checked on site) — tell us if it’s wrong', '根据店名挑选(未经实地核实) —— 如有误请告诉我们', 'Выбрано по названию (на месте не проверено) — сообщите, если неверно', 'Chọn theo tên (chưa kiểm tra thực tế) — hãy báo nếu sai'],
  'shop.b.OpenStreetMap': ['위치: OpenStreetMap', 'Location: OpenStreetMap', '位置：OpenStreetMap', 'Место: OpenStreetMap', 'Vị trí: OpenStreetMap'],
  'shop.source': ['공공 상가정보 {date} 기준이에요. 그사이 문을 닫았을 수 있어요', 'Public business data as of {date} — it may have closed since', '公共商家数据({date})，之后可能已关门', 'Открытые данные на {date} — место могло закрыться', 'Dữ liệu công tính đến {date} — có thể đã đóng cửa'],
  'shop.nearBadge': ['고향 사람 많은 곳', 'People from home', '老乡多', 'Много земляков', 'Đông đồng hương'],
  'shop.nearLine': ['주말 낮에 고향 사람이 많이 다니는 골목에 있어요', 'On a street busy with people from home on weekend afternoons', '位于周末白天老乡常去的街区', 'На улице, где по выходным днём много земляков', 'Nằm ở khu đồng hương hay qua lại vào trưa cuối tuần'],
  'shop.nearLineDong': ['주말 낮에 고향 사람이 많은 동네에 있어요', 'In a neighborhood with many people from home on weekend afternoons', '位于周末白天老乡多的洞', 'В районе, где по выходным днём много земляков', 'Nằm ở phường có nhiều đồng hương vào trưa cuối tuần'],
  'shop.checkedField': ['현장에서 영업 중인 것을 확인했어요({date})', 'Confirmed open on site ({date})', '已现场确认营业中（{date}）', 'Проверено на месте: работает ({date})', 'Đã kiểm tra tại chỗ: đang mở cửa ({date})'],
  'shop.checked': ['안산시 영업 신고 대장에서 영업 중으로 확인했어요({date} 기준)', 'Confirmed open in Ansan’s business license register (as of {date})', '已在安山市营业申报台账中确认营业中（截至{date}）', 'По реестру лицензий Ансана работает (на {date})', 'Đã xác nhận đang kinh doanh trong sổ đăng ký của Ansan (đến {date})'],
  'shop.officialSrc': ['공개 자료: {src}', 'Public data: {src}', '公开数据：{src}', 'Открытые данные: {src}', 'Dữ liệu công khai: {src}'],
  'shop.cuisineNote': ['음식 · 상품 종류예요. 주인의 국적이 아니에요', 'This is the type of food or goods, not the owner’s nationality', '仅表示食品/商品种类，不代表店主国籍', 'Это тип кухни или товаров, а не гражданство владельца', 'Đây là loại món ăn/hàng hóa, không phải quốc tịch chủ quán'],
  'shop.community': ['이웃이 알려준 곳이에요', 'Shared by a neighbor', '邻居推荐的地方', 'Место от соседа', 'Do hàng xóm giới thiệu'],

  // 커뮤니티
  'room.ko': ['한국어', 'Korean', '韩语', 'Корейский', 'Tiếng Hàn'],
  'room.zh': ['中文', '中文', '中文', '中文', '中文'],
  'room.ru': ['Русский', 'Русский', 'Русский', 'Русский', 'Русский'],
  'room.vi': ['Tiếng Việt', 'Tiếng Việt', 'Tiếng Việt', 'Tiếng Việt', 'Tiếng Việt'],
  'room.en': ['English', 'English', 'English', 'English', 'English'],
  'room.etc': ['기타 언어', 'Other languages', '其他语言', 'Другие языки', 'Ngôn ngữ khác'],
  'room.exchange': ['교류방', 'Exchange', '交流区', 'Обмен', 'Giao lưu'],
  'tag.자유': ['자유', 'Free talk', '闲聊', 'Разное', 'Tự do'],
  'tag.고민': ['고민', 'Advice', '求助', 'Совет', 'Tâm sự'],
  'tag.구인구직': ['구인구직', 'Jobs', '招聘求职', 'Работа', 'Việc làm'],
  'tag.모임': ['모임', 'Meetups', '聚会', 'Встречи', 'Gặp mặt'],
  'tag.집·생활': ['집 · 생활', 'Home & life', '住房 · 生活', 'Жильё и быт', 'Nhà & đời sống'],
  'tag.병원': ['병원', 'Clinics', '医院', 'Больницы', 'Bệnh viện'],
  'tag.비자·행정': ['비자 · 행정', 'Visa & papers', '签证 · 行政', 'Визы и документы', 'Visa & giấy tờ'],
  'c.hot': ['지금 인기 글', 'Popular now', '热门', 'Популярное', 'Đang nổi bật'],
  'c.write': ['글쓰기', 'Write', '发帖', 'Написать', 'Viết bài'],
  'c.topic': ['주제', 'Topic', '话题', 'Тема', 'Chủ đề'],
  'c.title': ['제목', 'Title', '标题', 'Заголовок', 'Tiêu đề'],
  'c.body': ['내용', 'What’s on your mind?', '内容', 'Текст', 'Nội dung'],
  'c.dong': ['동네', 'Neighborhood', '所在洞', 'Район', 'Phường'],
  'c.room': ['올릴 방', 'Room', '发布到', 'Комната', 'Phòng'],
  'c.when': ['언제 만나요?', 'When?', '什么时候？', 'Когда?', 'Khi nào?'],
  'c.whenPh': ['예: 토요일 오후 3시', 'e.g. Saturday 3 pm', '例：周六下午3点', 'например: суббота, 15:00', 'vd: thứ Bảy 3 giờ chiều'],
  'c.post': ['올리기', 'Post', '发布', 'Опубликовать', 'Đăng'],
  'c.anonPost': ['익명으로 올라가요', 'Posted anonymously', '匿名发布', 'Публикуется анонимно', 'Đăng ẩn danh'],
  'c.anon': ['익명', 'Anonymous', '匿名', 'Аноним', 'Ẩn danh'],
  'c.op': ['익명(글쓴이)', 'Anonymous (author)', '匿名(楼主)', 'Аноним (автор)', 'Ẩn danh (tác giả)'],
  'c.anonN': ['익명{n}', 'Anonymous {n}', '匿名{n}', 'Аноним {n}', 'Ẩn danh {n}'],
  'c.me': ['나', 'me', '我', 'я', 'tôi'],
  'c.like': ['좋아요', 'Like', '赞', 'Нравится', 'Thích'],
  'c.comments': ['댓글', 'Comments', '评论', 'Комментарии', 'Bình luận'],
  'c.addComment': ['댓글을 남겨 보세요', 'Write a comment', '写评论', 'Комментарий', 'Viết bình luận'],
  'c.send': ['보내기', 'Send', '发送', 'Отправить', 'Gửi'],
  'c.report': ['신고', 'Report', '举报', 'Пожаловаться', 'Báo cáo'],
  'c.reportWhy': ['신고 이유를 골라 주세요', 'Why are you reporting this?', '请选择举报原因', 'Причина жалобы', 'Lý do báo cáo'],
  'c.reported': ['신고했어요', 'Reported', '已举报', 'Жалоба отправлена', 'Đã báo cáo'],
  'c.hiddenNow': ['신고가 쌓여 글이 숨겨졌어요', 'Hidden after several reports', '举报累计，帖子已隐藏', 'Скрыто после нескольких жалоб', 'Đã ẩn sau nhiều báo cáo'],
  'c.translate': ['한국어 번역 보기', 'Show Korean translation', '查看韩语翻译', 'Показать перевод на корейский', 'Xem bản dịch tiếng Hàn'],
  'c.original': ['원문만 보기', 'Original only', '只看原文', 'Только оригинал', 'Chỉ bản gốc'],
  'c.noTr': ['새 글은 번역 기능을 연결한 뒤 볼 수 있어요', 'Translation for new posts is coming', '新帖翻译功能即将上线', 'Перевод новых постов появится позже', 'Bản dịch bài mới sẽ có sau'],
  'c.rules': ['익명 게시판 · 혐오 표현 금지 · 신고가 3건 쌓이면 자동으로 숨겨져요', 'Anonymous board · no hate speech · hidden automatically after 3 reports', '匿名版块 · 禁止仇恨言论 · 举报满3次自动隐藏', 'Анонимно · без языка вражды · скрывается после 3 жалоб', 'Ẩn danh · không ngôn từ thù ghét · tự ẩn sau 3 báo cáo'],
  'c.koreanRule': ['한국인 이웃은 교류방에서만 글 · 댓글을 쓸 수 있어요. 언어방은 읽기 · 좋아요 · 신고만 돼요', 'Korean neighbors can post and comment only in Exchange; language rooms are read-only for them', '韩国邻居只能在交流区发帖和评论，语言区只能浏览、点赞、举报', 'Местные жители пишут только в «Обмене»; языковые комнаты — только чтение', 'Người Hàn chỉ viết trong phòng Giao lưu; các phòng ngôn ngữ chỉ đọc'],
  'c.empty': ['아직 글이 없어요. 첫 글을 남겨 보세요', 'No posts yet — be the first', '还没有帖子，来发第一帖吧', 'Пока нет постов — напишите первым', 'Chưa có bài — hãy viết bài đầu tiên'],
  'c.meetHint': ['주말 오후에 고향 사람이 많은 동네: {dongs}', 'People from home gather on weekend afternoons in: {dongs}', '周末下午老乡多的洞：{dongs}', 'По выходным днём земляки чаще в: {dongs}', 'Chiều cuối tuần đồng hương hay ở: {dongs}'],
  'c.posted': ['글을 올렸어요', 'Posted', '已发布', 'Опубликовано', 'Đã đăng'],
  'c.need': ['제목과 내용을 적어 주세요', 'Please add a title and text', '请填写标题和内容', 'Добавьте заголовок и текст', 'Hãy nhập tiêu đề và nội dung'],
  'c.mine': ['내 글', 'My post', '我的帖子', 'Мой пост', 'Bài của tôi'],
  'c.sameNat': ['{nat} 사람 글만', 'Only people from {nat}', '只看{nat}老乡', 'Только земляки ({nat})', 'Chỉ người {nat}'],
  'rr.사기·브로커': ['사기 · 브로커', 'Scam or broker', '诈骗 · 中介', 'Мошенничество', 'Lừa đảo, môi giới'],
  'rr.혐오 표현': ['혐오 표현', 'Hate speech', '仇恨言论', 'Язык вражды', 'Ngôn từ thù ghét'],
  'rr.광고·스팸': ['광고 · 스팸', 'Ads or spam', '广告 · 垃圾信息', 'Реклама, спам', 'Quảng cáo, spam'],
  'rr.개인정보': ['개인정보 노출', 'Personal information', '泄露个人信息', 'Личные данные', 'Lộ thông tin cá nhân'],
  'rr.기타': ['기타', 'Other', '其他', 'Другое', 'Khác'],

  // 소식
  'n.events': ['행사', 'Events', '活动', 'События', 'Sự kiện'],
  'n.infos': ['안내', 'Notices', '通知', 'Объявления', 'Thông báo'],
  'n.ask': ['시에 묻기', 'Ask the city', '问市政府', 'Спросить город', 'Hỏi thành phố'],
  'n.forMe': ['나에게 맞춤', 'For you', '为你推荐', 'Для вас', 'Dành cho bạn'],
  'n.past': ['지난 행사', 'Past events', '往期活动', 'Прошедшие события', 'Sự kiện đã qua'],
  'n.today': ['오늘', 'Today', '今天', 'Сегодня', 'Hôm nay'],
  'n.where': ['장소', 'Where', '地点', 'Где', 'Ở đâu'],
  'n.onMap': ['지도에서 보기', 'See on the map', '在地图上看', 'На карте', 'Xem trên bản đồ'],
  'n.remind': ['알림 받기', 'Remind me', '提醒我', 'Напомнить', 'Nhắc tôi'],
  'n.reminded': ['알림 켜짐', 'Reminder on', '已开启提醒', 'Напоминание включено', 'Đã bật nhắc'],
  'n.remindNote': ['시연판이라 실제 알림은 가지 않아요', 'This demo doesn’t send real notifications', '演示版不会真的发送通知', 'Демо не отправляет уведомления', 'Bản demo không gửi thông báo thật'],
  'n.source': ['원문 보기', 'Official source', '查看原文', 'Источник', 'Nguồn chính thức'],
  'n.empty': ['지금은 소식이 없어요', 'Nothing right now', '暂时没有消息', 'Пока ничего нет', 'Hiện chưa có tin'],
  'n.kind.event': ['행사', 'Event', '活动', 'Событие', 'Sự kiện'],
  'n.kind.policy': ['정책', 'Policy', '政策', 'Программа', 'Chính sách'],
  'n.kind.notice': ['공지', 'Notice', '公告', 'Объявление', 'Thông báo'],
  'n.cityOnly': ['안산시 · 경기도 안내만 올라와요. 정부 정책은 원문 링크로 이어져요', 'Ansan and Gyeonggi notices; national policies link to the official source', '仅发布安山市和京畿道的通知，中央政策附原文链接', 'Объявления Ансана и провинции Кёнгидо; госпрограммы — по ссылке', 'Thông báo của Ansan và Gyeonggi; chính sách quốc gia có liên kết gốc'],
  'topic.의료': ['건강', 'Health', '医疗', 'Здоровье', 'Y tế'],
  'topic.노동': ['일 · 노동', 'Work', '劳动', 'Работа', 'Lao động'],
  'topic.교육': ['교육', 'Education', '教育', 'Образование', 'Giáo dục'],
  'topic.행정': ['행정', 'Paperwork', '行政', 'Документы', 'Hành chính'],
  'topic.비자': ['비자', 'Visa', '签证', 'Виза', 'Visa'],
  'topic.규칙': ['규칙', 'Rules', '规则', 'Правила', 'Quy định'],
  'q.hint': ['안산시 담당자가 직접 답해요. 같은 궁금증이 있는 이웃도 함께 봐요', 'City staff answer directly; neighbors with the same question can read it too', '由安山市工作人员直接回答，有同样疑问的邻居也能看到', 'Отвечают сотрудники города; ответ видят все', 'Cán bộ thành phố trả lời; mọi người đều xem được'],
  'q.anyLang': ['어떤 언어로 써도 괜찮아요', 'Write in any language', '用任何语言都可以', 'Можно на любом языке', 'Viết bằng ngôn ngữ nào cũng được'],
  'q.title': ['무엇이 궁금하세요?', 'What would you like to ask?', '你想问什么？', 'Ваш вопрос', 'Bạn muốn hỏi gì?'],
  'q.body': ['자세한 내용 (선택)', 'Details (optional)', '详细内容(可选)', 'Подробности (необязательно)', 'Chi tiết (không bắt buộc)'],
  'q.send': ['질문 보내기', 'Send question', '提交问题', 'Отправить вопрос', 'Gửi câu hỏi'],
  'q.sent': ['질문을 보냈어요', 'Question sent', '问题已提交', 'Вопрос отправлен', 'Đã gửi câu hỏi'],
  'q.answered': ['답변 완료', 'Answered', '已回答', 'Есть ответ', 'Đã trả lời'],
  'q.pending': ['답변을 기다리는 중', 'Waiting for an answer', '等待回答', 'Ждёт ответа', 'Đang chờ trả lời'],
  'q.city': ['안산시 답변', 'Answer from Ansan City', '安山市的回答', 'Ответ города', 'Thành phố trả lời'],
  'q.mine': ['내 질문', 'My question', '我的问题', 'Мой вопрос', 'Câu hỏi của tôi'],
  'q.trKo': ['한국어 번역', 'Korean translation', '韩语翻译', 'Перевод на корейский', 'Bản dịch tiếng Hàn'],

  // 나
  'me.title': ['내 정보', 'My info', '我的信息', 'Мои данные', 'Thông tin của tôi'],
  'me.lang': ['화면 언어', 'App language', '界面语言', 'Язык приложения', 'Ngôn ngữ ứng dụng'],
  'me.nat': ['국적', 'Nationality', '国籍', 'Гражданство', 'Quốc tịch'],
  'me.korean': ['한국인 이웃', 'Korean neighbor', '韩国邻居', 'Местный житель', 'Người Hàn'],
  'me.dong': ['사는 동네', 'Neighborhood', '居住洞', 'Район', 'Phường'],
  'me.joined': ['가입한 날', 'Joined', '注册日期', 'С нами с', 'Ngày tham gia'],
  'me.notif': ['알림', 'Notifications', '通知', 'Уведомления', 'Thông báo'],
  'me.nCity': ['나에게 맞는 안산시 소식', 'City news for me', '适合我的市政消息', 'Новости города для меня', 'Tin thành phố dành cho tôi'],
  'me.nEvent': ['행사 하루 전 알림', 'Day-before event reminders', '活动前一天提醒', 'Напоминание за день до события', 'Nhắc trước sự kiện 1 ngày'],
  'me.nComment': ['내 글에 댓글', 'Comments on my posts', '我的帖子有新评论', 'Комментарии к моим постам', 'Bình luận bài của tôi'],
  'me.install': ['휴대폰 홈 화면에 앱 추가', 'Add to your home screen', '添加到手机主屏幕', 'Добавить на главный экран', 'Thêm vào màn hình chính'],
  'me.installHow': ['브라우저 메뉴(⋮ 또는 공유)에서 ‘홈 화면에 추가’를 누르세요', 'Open the browser menu (⋮ or Share) and tap “Add to Home screen”', '在浏览器菜单(⋮或分享)中点“添加到主屏幕”', 'В меню браузера (⋮ или «Поделиться») выберите «На экран “Домой”»', 'Mở menu trình duyệt (⋮ hoặc Chia sẻ) và chọn “Thêm vào màn hình chính”'],
  'me.installBtn': ['설치하기', 'Install', '安装', 'Установить', 'Cài đặt'],
  'me.data': ['이 앱의 정보는 어디서 왔나요?', 'Where does this information come from?', '这些信息来自哪里？', 'Откуда эти данные?', 'Thông tin này từ đâu?'],
  'me.dShops': ['가게: 소상공인시장진흥공단 상가(상권)정보 {date} — 누구나 쓸 수 있는 공공데이터예요', 'Shops: Korea small-business registry ({date}) — open public data', '店铺：小商工人市场振兴公团商家信息({date}) —— 公开数据', 'Магазины: открытый реестр малого бизнеса ({date})', 'Cửa hàng: dữ liệu công về hộ kinh doanh ({date})'],
  'me.dPeople': ['고향 사람 많은 곳: 휴대폰 통신 자료로 추정한 동네별 정도예요. 동네 단위로만, 적은 곳은 숨겨요', 'People from home: estimated by neighborhood from mobile network data; small numbers are hidden', '老乡在哪儿：由手机通信数据按洞估算，人少的地方不显示', 'Где земляки: оценка по районам по мобильным данным; малые числа скрыты', 'Đồng hương ở đâu: ước tính theo phường từ dữ liệu di động; số nhỏ được ẩn'],
  'me.dSample': ['지금 이 부분은 예시 데이터예요', 'This part is sample data for now', '这部分目前是示例数据', 'Сейчас это примерные данные', 'Phần này hiện là dữ liệu mẫu'],
  'me.dReal': ['지금 이 부분은 실제 통신 자료({month})예요', 'This part uses real mobile data ({month})', '这部分使用真实通信数据（{month}）', 'Здесь реальные данные связи ({month})', 'Phần này dùng dữ liệu di động thật ({month})'],
  'me.dPosts': ['글 · 행사 · 질문은 시연용 예시예요', 'Posts, events and questions are demo samples', '帖子、活动和问答是演示示例', 'Посты, события и вопросы — демо-примеры', 'Bài viết, sự kiện và câu hỏi là mẫu demo'],
  'me.privacy': ['이름 · 연락처 · 체류자격은 모으지 않아요', 'We don’t collect names, phone numbers or visa status', '我们不收集姓名、电话和签证身份', 'Мы не собираем имена, телефоны и визовый статус', 'Chúng tôi không thu thập tên, số điện thoại hay visa'],
  'me.switch': ['다른 시연 계정으로 보기', 'Switch demo account', '切换演示账号', 'Сменить демо-аккаунт', 'Đổi tài khoản mẫu'],
  'me.logout': ['로그아웃', 'Log out', '退出登录', 'Выйти', 'Đăng xuất'],
  'me.saved': ['바꿨어요', 'Updated', '已更改', 'Сохранено', 'Đã cập nhật'],
  'me.official': ['공무원 미리보기', 'Official preview', '公务员预览', 'Просмотр сотрудника', 'Xem trước (cán bộ)'],

  'ago.now': ['방금', 'just now', '刚刚', 'только что', 'vừa xong'],
};

const NAT = {   // 국적 이름 [ko, en, zh, ru, vi]
  '중국': ['중국', 'China', '中国', 'Китай', 'Trung Quốc'], '우즈베키스탄': ['우즈베키스탄', 'Uzbekistan', '乌兹别克斯坦', 'Узбекистан', 'Uzbekistan'],
  '러시아': ['러시아', 'Russia', '俄罗斯', 'Россия', 'Nga'], '카자흐스탄': ['카자흐스탄', 'Kazakhstan', '哈萨克斯坦', 'Казахстан', 'Kazakhstan'],
  '베트남': ['베트남', 'Vietnam', '越南', 'Вьетнам', 'Việt Nam'], '인도네시아': ['인도네시아', 'Indonesia', '印度尼西亚', 'Индонезия', 'Indonesia'],
  '네팔': ['네팔', 'Nepal', '尼泊尔', 'Непал', 'Nepal'], '필리핀': ['필리핀', 'Philippines', '菲律宾', 'Филиппины', 'Philippines'],
  '미얀마': ['미얀마', 'Myanmar', '缅甸', 'Мьянма', 'Myanmar'], '몽골': ['몽골', 'Mongolia', '蒙古', 'Монголия', 'Mông Cổ'],
  '캄보디아': ['캄보디아', 'Cambodia', '柬埔寨', 'Камбоджа', 'Campuchia'], '방글라데시': ['방글라데시', 'Bangladesh', '孟加拉国', 'Бангладеш', 'Bangladesh'],
  '태국': ['태국', 'Thailand', '泰国', 'Таиланд', 'Thái Lan'], '파키스탄': ['파키스탄', 'Pakistan', '巴基斯坦', 'Пакистан', 'Pakistan'],
  '스리랑카': ['스리랑카', 'Sri Lanka', '斯里兰卡', 'Шри-Ланка', 'Sri Lanka'], '인도': ['인도', 'India', '印度', 'Индия', 'Ấn Độ'],
  '미국': ['미국', 'USA', '美国', 'США', 'Hoa Kỳ'], '일본': ['일본', 'Japan', '日本', 'Япония', 'Nhật Bản'],
  '캐나다': ['캐나다', 'Canada', '加拿大', 'Канада', 'Canada'], '프랑스': ['프랑스', 'France', '法国', 'Франция', 'Pháp'],
  '기타': ['기타', 'Other', '其他', 'Другая', 'Khác'],
};
// 동 이름 로마자(국어의 로마자 표기법) — 외국어 화면에서 한글 옆에 붙인다(표지판은 한글이라 한글을 지운다 X)
const DONG_ROMAN = {
  '일동': 'Il-dong', '이동': 'I-dong', '사동': 'Sa-dong', '사이동': 'Sai-dong', '해양동': 'Haeyang-dong',
  '본오1동': 'Bono 1-dong', '본오2동': 'Bono 2-dong', '본오3동': 'Bono 3-dong', '부곡동': 'Bugok-dong',
  '월피동': 'Wolpi-dong', '성포동': 'Seongpo-dong', '반월동': 'Banwol-dong', '안산동': 'Ansan-dong', '와동': 'Wa-dong',
  '고잔동': 'Gojan-dong', '중앙동': 'Jungang-dong', '호수동': 'Hosu-dong', '원곡동': 'Wongok-dong', '백운동': 'Baegun-dong',
  '신길동': 'Singil-dong', '초지동': 'Choji-dong', '선부1동': 'Seonbu 1-dong', '선부2동': 'Seonbu 2-dong',
  '선부3동': 'Seonbu 3-dong', '대부동': 'Daebu-dong',
};

let cur = 'ko';
export const lang = () => cur;
export const locale = () => LOCALE[cur];
export function setLang(l) {
  cur = LANGS.includes(l) ? l : 'en';
  document.documentElement.lang = cur;
}
export function t(key, vars) {
  const row = T[key];
  let s = row ? (row[IDX[cur]] ?? row[0]) : key;
  if (vars) for (const k in vars) s = s.split('{' + k + '}').join(vars[k]);
  return s;
}
export const has = (key) => key in T;
export const natName = (n) => (NAT[n] ? NAT[n][IDX[cur]] : n || '');
export function dongName(name, short = false) {
  if (!name) return '';
  if (cur === 'ko' || !DONG_ROMAN[name]) return name;
  return short ? DONG_ROMAN[name] : `${name} · ${DONG_ROMAN[name]}`;
}
export function hourLabel(h) {
  const d = new Date(2026, 0, 5, h, 0, 0);
  return new Intl.DateTimeFormat(LOCALE[cur], { hour: 'numeric' }).format(d);
}
// 행사 날짜는 'YYYY-MM-DD' 또는 운영 콘솔이 시작 시각을 붙인 'YYYY-MM-DD HH:MM' 으로 온다 — 앞 10자만 날짜로 읽는다
// (시각이 붙은 행사에서 날짜가 NaN 이 되어 홈 · 소식이 멈췄다, 2026-11-20)
export function dateLabel(iso, opts = { month: 'short', day: 'numeric', weekday: 'short' }) {
  const [y, m, d] = String(iso).slice(0, 10).split('-').map(Number);
  return new Intl.DateTimeFormat(LOCALE[cur], opts).format(new Date(y, m - 1, d));
}
export function timeOf(iso) {
  const hm = /[ T](\d{1,2}):(\d{2})/.exec(iso || '');
  if (!hm) return '';
  return new Intl.DateTimeFormat(LOCALE[cur], { hour: 'numeric', minute: '2-digit' }).format(new Date(2026, 0, 5, +hm[1], +hm[2]));
}
export function ago(ts) {
  const then = new Date(ts.replace(' ', 'T'));
  const sec = (Date.now() - then.getTime()) / 1000;
  if (sec < 3600) return t('ago.now');
  const rtf = new Intl.RelativeTimeFormat(LOCALE[cur], { numeric: 'auto' });
  if (sec < 86400) return rtf.format(-Math.round(sec / 3600), 'hour');
  if (sec < 86400 * 30) return rtf.format(-Math.round(sec / 86400), 'day');
  return dateLabel(ts.slice(0, 10), { year: 'numeric', month: 'short', day: 'numeric' });
}
export function distance(m) {
  return m >= 1000 ? t('km', { n: (m / 1000).toFixed(m >= 10000 ? 0 : 1) }) : t('m', { n: Math.max(50, Math.round(m / 50) * 50) });
}
