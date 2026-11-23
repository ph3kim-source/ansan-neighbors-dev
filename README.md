# 2안 v2 — 안산 이웃 (Ansan Neighbors)

> 안산시청 AI빅데이터팀 2027년도 수탁연구과제 · **프로토타입 v0.5** — 2026-11-20 시민 화면을 휴대폰 웹앱으로(실제 지도 위 외국인 주민 가게 · 시간대별 우리 이웃 많은 곳 · 언어방 · 소식), Streamlit 은 운영 콘솔 (`docs/기획_결정사항.md` §2 결정 13 · `docs/진행상황.md` §2)
> 외국인 주민 커뮤니티(에브리타임식 언어방) × 국적별 생활권 지도 × 안산시 공지·공식 Q&A

⚠️ **이 저장소의 수치는 모두 가상이다.** 인벤토리 실물과 같은 컬럼명·코드값·파일명 규칙을 따르는 임의 데이터(`data/synthetic/`)로 동작한다.
민간 실데이터(`data/real/`, 2026-11-20 사용 승인)는 이 PC에 옮겨 둔 것이 있으면 앱 · 콘솔이 자동으로 쓰지만, **이 저장소 · 공유판 · 드라이브 앱에는 들어가지 않는다**(.gitignore · 빌더가 막음 — 사용과 공개는 다른 일).

## 실행

| 누가 | 실행 | 주소 |
|---|---|---|
| **누구나** — 링크로 보는 시연판(가상 판 · 설치 없음) | — | https://ph3kim-source.github.io/ansan-foreign-community-demo/ (첫 화면 · `app/` 시민 앱 · `summary/` 제안 요약) · 공무원 화면 https://ansan-foreign-community-demo-gb9dqrtsvvb85qo2de8q8w.streamlit.app/ (잠들어 있으면 깨우기 단추) |
| **시민(외국인 주민 · 내국인 이웃)** — 휴대폰 웹앱 | `앱_실행.bat` (휴대폰으로 보려면 `앱_휴대폰으로_보기.bat`) | http://127.0.0.1:8600 |
| **안산시 담당자** — 운영 콘솔(Streamlit) | `실행.bat` | http://localhost:8501 |

두 화면은 같은 커뮤니티 DB(`data/community.db`)를 쓴다 — 콘솔에서 올린 공지가 앱 소식에 보이고, 앱에서 한 질문 · 신고가 콘솔에 쌓인다.
PC 브라우저에서 휴대폰 크기로 보려면 F12 → 기기 툴바(Ctrl+Shift+M). 앱은 홈 화면에 설치할 수 있다(PWA).

```powershell
python src\gen_synthetic.py      # 가상 데이터 (최초 1회)
python pipeline\stage_licenses.py   # 안산 식품 인허가(공공 · 키 없음) → data/public/raw/localdata (git 제외)
python pipeline\stage_shops.py   # 시민 앱 가게 목록 — 공공 상가정보에서 고르고 인허가 대장으로 영업 확인 → data/public/shops_ansan.csv (저장소에 있음)
python src\server.py             # 시민 앱 (Starlette + uvicorn — Streamlit 에 딸려 있어 따로 설치하지 않는다)
python -m streamlit run src\app.py   # 운영 콘솔
python -m pytest tests -q        # 67개 — 실데이터가 적재돼 있으면 실데이터 판 화면 렌더 시험도 돈다(없으면 건너뜀)
```

### 실데이터 판 (2026-11-20 사용 승인 — `앱_실행.bat` · `실행.bat` 은 data\real 이 있으면 자동으로 실데이터)

```powershell
python pipeline\stage_real.py    # 구글 드라이브(G:)에서 2안이 쓰는 것만 data\real 로 (DS-017 · 014 · 056 외국인 행 · 076/077 PUBLIC · 다문화특구 경계)
python pipeline\stage_grid.py    # 50m 격자(DS-032) 원본 3~4GB → 평일/주말 × 3개 시각 × 국적 하루 평균 집계본만 (수 분)
python pipeline\stage_roads.py   # 격자 칸 거리 이름 — 도로명주소 도로구간(공공)에서 안산 도로만 50m 칸 × 도로명 길이로 (API · 키 불필요)
```

옮긴 뒤에는 위 표의 `실행.bat` · `앱_실행.bat` 을 그대로 켠다 — 콘솔은 이 PC(127.0.0.1)에서만 열리고, 앱의 고향 사람 지도는 동네마다 1~4 단계로만 나간다.
실데이터 전용 실행 파일 두 개(`시연_실데이터.bat` · `앱_실데이터.bat`)는 위 두 파일과 같은 판을 열어 겹쳐서 2026-11-23 `../_보관/2안_실데이터_실행파일_20261123/` 로 옮겼다.

실물에서 찾은 함정(헤더 공백 · 중복 납품 달 · 산출 수준 변화)은 적재 스크립트와 `src/metrics.py` 가 처리한다. 수치와 근거는 프로젝트 루트의 비공개 문서에 있다.

Python 3.13(`C:\Users\master\AppData\Local\Programs\Python\Python313`) 기준으로 시험했다. 4안 `실행.bat`은 3.12를 쓰니 혼동 주의.

### HTML 판 (서버 없이 파일 두 개)

| 파일 | 누가 보나 | 내용 |
|---|---|---|
| `html\안산이웃_플랫폼.html` | 시민 | 시민 휴대폰 앱(`app/`) 그대로. 더블클릭하면 브라우저에서 열린다. 언어 → 국적 → 동 간편가입, 또는 '시연 계정으로 둘러보기'. 서버 대신 파일 안의 가짜 서버(`pipeline/html/demo_api.js`)가 `server.py` 와 같은 규칙으로 답한다 |
| `html\안산이웃_제안요약.html` | 심사 · 담당자 | 제안 요약 — 핵심 흐름 · 무엇이 어디에 있나 · 5대 기준 자체 판정 · 2단계 · 다음 단계 |

2026-11-23 사용자 결정("시민들은 제안 요약을 안 봐도 된다, 진짜 시민이 쓸 수 있게"): 예전 시연판의 틀(시연 사용자 바꾸기 · 시연 순서 · 「민간데이터 끄기」 · 브라우저와 휴대폰 모형 · 운영 콘솔 · 제안 요약 탭)을 뺐다.
운영 콘솔은 Streamlit(`실행.bat`)에 있다. 예전 시연판은 `../_보관/2안_이전시민화면_20261120/`, 줄이기 전 전체기능판은 `../_보관/2안_html_전체기능판_20261116/`.
글 · 질문 · 추천은 그 브라우저 탭에만 남는다(새로 고치면 처음 상태). 지도 바탕(OpenStreetMap)은 인터넷이 있어야 보인다.

```powershell
python pipeline\build_html.py    # app\ + 가짜 서버 + 가상 시드 → html\안산이웃_플랫폼.html · html\안산이웃_제안요약.html(틀: pipeline\html\proposal.html)
```

HTML 판은 늘 가상 데이터로 만든다(파일로 퍼지는 산출물이라 실데이터 판으로는 만들지 않음 — `ANSAN_DATA=real` 이면 빌드가 멈춘다). 통신 자료는 동네 단계만 담는다. 가게 목록은 실제 공공자료다.

## 사용 데이터셋 (인벤토리 기준, v0.3)

| 인벤ID | 테이블 | 화면 | 대민개방 |
|---|---|---|---|
| DS-017 | AMD_INFLOW_TIME_F_POP (외국인 행정동 시간대 방문) | **사는 곳(장기 · 평일 새벽)** · 모이는 곳 · 모임 장소 추천 · 행사 기획 추천 · 공지 대상 동 · 장소·시각 제안 · 연휴 효과(관리자) · 행사 효과(관리자) | O |
| DS-014 | GG_ADMI_FLOWPOP (행정동 유동인구, 내외국인 · 성 · 연령) | 관리자 외국인 유동 추이 · 성·연령 구성 (전입·정착 탭) | O |
| DS-056 | GGC_SALES_YM_AMD (행정동 내외구분 카드) | 관리자 외국인 결제(외국인 전체, 비중만) · 행사 결제 효과 | X |
| DS-076/077 | GYEONGGI_IN/OUT_STAT_PUBLIC (전입·전출, K-10) | 관리자 전입·정착 · KPI 가입률 | O |
| DS-032 | GG_50CELL_FLOWPOP (50m 셀) | 관리자 격자 지도 — 평일/주말 × 3개 시각 × 국적 하루 평균 집계본만. 화면에서 칸 크기(50 · 100 · 250m)로 묶은 뒤 가리고 반투명 네모 칸으로 그린다 (실데이터 판은 `stage_grid.py`) | X |
| 시 내부 | 원곡동 다문화특구 일원 경계 | 지도 · 격자 위 보라색 선 — 실데이터 판만(시 내부 산출물) | 내부 |
| 공공 | 도로명주소 도로구간 (행정안전부) | 격자 칸 이름 '○○로 일대'(툴팁 · 밀집 거리) — 실데이터 판만. 길마다 값을 매기지는 않는다(가장 작은 단위가 50m 칸, 결정 12) | 공공 |
| 공공 | 소상공인시장진흥공단 상가(상권)정보 2026-09 (2026-11-23 갱신 — 그 전은 2026-06) | 시민 앱 생활 지도의 가게 후보 452곳(음식점 · 식료품) — 업종(동남아시아 · 마라탕/훠궈) + 업종 안 상호 낱말 + 검수 목록(`data/public/shops_overrides.csv`). 생활 서비스(번역 · 여행 · 휴대폰)는 간판 없는 사무실 · 집 주소 등록이 섞여 확인 목록이 생길 때까지 싣지 않는다. 음식 종류는 주인의 국적이 아니다(화면에 적음, 결정 13-②) | 공공 |
| 공공 | 행정안전부 지방행정 인허가(LOCALDATA) — 안산 식품 8종(일반 · 휴게음식점, 제과점, 즉석판매제조가공, 식품소분, 축산판매, 식품판매(기타), 관광식당), 2026-11-18 기준 | 가게 후보를 영업 신고 대장과 하나하나 맞춰 **영업 중으로 확인되고 음식 종류가 뒷받침되는 299곳만 지도에**(음식점 294 · 식료품 5, 2026-09 판 기준). 폐업 7 · 대장에 없음 103 · 음식 종류 근거 없음 39 · 중복 4 는 `data/public/shops_unverified.csv`(확인 대기) | 공공 |
| 공공 | 법무부 출입국 관리사무소 현황 · 고용노동부 고용복지플러스센터 현황 · 한국건강가정진흥원 다문화가족지원센터 현황 · 건강보험심사평가원 병의원 현황 | 시민 앱 지도 '공공 · 상담' 6곳(외국인주민지원본부 · 출입국 종합민원센터 · 고용복지플러스센터 · 가족센터 · 보건소 2) — `data/public/facilities.csv`. 위치는 공개 좌표 두 곳 이상이 맞는지 확인(`located_by` 칸) | 공공 |
| 공공 | OpenStreetMap | 시민 앱 바탕지도 · 공공 기관 위치 확인(고용복지플러스센터 · 가족센터) | 공개 |
| 공표 | 안산시 외국인주민 통계 (동별) | 시민 '외국인 주민이 늘어난 동' · 가상 데이터 총량 보정 | 공표 |

v0.3에서 뺀 것: DS-028(실물에서 거주 판정 불가 → 사는 곳은 DS-017로), DS-042/061(미납품 → 행사 효과는 동 단위로), 시민 지도의 '쓰는 곳' 레이어(카드 국적코드표 없음 · 결제 쏠림). 이유는 `docs/기획_결정사항.md` §2 D10~D16.

## 구조

```
src/config.py         상수·가정 (21개국, 동 코드 대조, 파라미터, 페르소나)
src/geo.py            UTM-K ↔ WGS84, 동 경계(4안 geojson 재사용)
src/gen_synthetic.py  가상 데이터 생성 (공표 통계 보정 + 시나리오)
src/metrics.py        지표 집계 (Streamlit 비의존)
src/community.py      SQLite 커뮤니티 + 시드
src/app.py            운영 콘솔(Streamlit) — 관리자 4탭(동향 · 행사 · 외국인 변화 · 공지·소통 + 시민 앱 가게 신고 검수). 옛 시민 탭은 2026-11-20 정리에서 뺐다
src/server.py         시민 앱 API + 정적 파일 (Starlette) — 가입 · 세션 · 지도 · 커뮤니티 · 소식 · Q&A. 통신 자료는 단계만
app/                  시민 휴대폰 웹앱(PWA) — index.html · css · js(홈 · 지도 · 커뮤니티 · 소식 · 나, 5개 언어) · vendor(Leaflet 1.9.4 · markercluster 1.5.3)
tests/test_smoke.py   테스트 15개 — 지표 규칙 · 커뮤니티 규칙 · 콘솔 화면 렌더 · 공지 대상 지정 · 공유판 세션 DB (임시 DB 사용)
tests/test_app.py     테스트 27개 — 가게 고르기 · 이웃 많은 곳 단계 · 간편가입 · 위치 제보 · 같은 초 순서 · API 규칙 · 화면 코드에 데이터 없음 · 5개 언어
tests/test_v03.py     테스트 25개 — 사는 곳 계산 · 보정 · 21개국 · PUBLIC 전입 · 산출 구간 경계 · 연휴/행사 효과 · DS-014 · 50m 격자 집계 · 격자 칸 · 칸 거리 이름 · 2단계 숨김 · 적재(헤더 · shp · dbf · 바로가기) · 공개 차단 · 실데이터 판 렌더
pipeline/stage_real.py   민간 실데이터 적재(G: → data/real, 내부 검토용 · git 제외)
pipeline/stage_grid.py   50m 격자 원본 → 집계본(data/real/_cache, 원본은 복사하지 않음)
pipeline/stage_roads.py  도로명주소 도로구간 → 50m 칸 × 도로명 길이(data/real — 칸 이름은 실데이터 판만)
pipeline/stage_shops.py  공공 상가정보(경기) → 시민 앱 가게 목록(data/public/shops_ansan.csv · 검수 목록 shops_overrides.csv · 확인 대기 shops_unverified.csv)
pipeline/stage_licenses.py · verify_shops.py  안산 식품 인허가 받기 · 가게 영업 확인(같은 건물 + 같은 이름 + 맞는 업종)
pipeline/build_share.py  공유 시연판(../2안_공유) 생성 → github.com/ph3kim-source/ansan-foreign-community-demo (가상만)
pipeline/build_html.py   HTML 판 생성 — html/안산이웃_플랫폼.html(시민 앱 그대로 + 가짜 서버 pipeline/html/demo_api.js) · html/안산이웃_제안요약.html(틀 pipeline/html/proposal.html) (가상만)
pipeline/prep.py      공표 외국인주민 통계 xlsx → data/processed/dong_month·gu_nat_month (가상 데이터 총량 보정용)
docs/기획_결정사항.md   인터뷰 결정·데이터 매핑·5대 기준·가정·백로그
docs/진행상황.md        완료/남은 일 — 이어서 작업할 때 여기부터
```

v1(관광객 현황판)은 2안 밖 `../_보관/2안_v1_관광객안/` 에 보관한다(2026-11-16 이동).

5대 기준 자체 판정과 리스크는 `docs/기획_결정사항.md` §4·§5 참조. 심사 · 담당자용 한 장 요약은 `html/안산이웃_제안요약.html`.
