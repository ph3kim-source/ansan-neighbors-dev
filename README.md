# 2안 v2 — 안산 이웃 (Ansan Neighbors)

> 안산시청 AI빅데이터팀 2027년도 수탁연구과제 · **초안 프로토타입 v0.1 (가상 데이터)**
> 외국인 주민 커뮤니티(에브리타임식 언어방) × 국적별 생활권 지도 × 안산시 공지·공식 Q&A

⚠️ **모든 수치는 가상이다.** 민간데이터 원본이 아직 오지 않아, 인벤토리(`data/안산시_민간데이터_데이터셋_인벤토리_v1.0.xlsx`)의
실제 컬럼명·코드값·파일명 규칙을 그대로 따르는 임의 데이터로 동작한다. 실데이터가 오면 `data/synthetic/` 파일만 교체한다.

## 실행

`실행.bat` 더블클릭 → 브라우저에서 http://localhost:8501 (가상 데이터가 없으면 먼저 자동 생성).

```powershell
python src\gen_synthetic.py      # 가상 데이터 (최초 1회)
python -m streamlit run src\app.py
python -m pytest tests -q
```

Python 3.13(`C:\Users\master\AppData\Local\Programs\Python\Python313`) 기준으로 시험했다. 4안 `실행.bat`은 3.12를 쓰니 혼동 주의.

## 사용 데이터셋 (인벤토리 기준)

| 인벤ID | 테이블 | 화면 | 대민개방 |
|---|---|---|---|
| DS-028 | AMD_STAY_F_POP (외국인 행정동 숙박인원) | 사는 곳 · 내 국적 생활권 자동 설정 · 관리자 동향 | O |
| DS-017 | AMD_INFLOW_TIME_F_POP (외국인 행정동 시간대 방문) | 모이는 곳 · 모임 장소 추천 · 행사 기획 추천 | O |
| DS-056 | GGC_SALES_YM_AMD (행정동 내외구분 카드) | 쓰는 곳 (비중·순위만, 금액 비표시) | X |
| DS-076/077 | GYEONGGI_IN/OUT_STAT (전입·전출) | 새로 온 이웃 · 전입·정착 모니터링 · KPI 가입률 | O |
| DS-032 | GG_50CELL_FLOWPOP (50m 셀) | 관리자 격자 히트맵 | X |
| DS-042/061 | EVENT_VISIT/SALES_NATIONALITY (관심지역 행사) | 관리자 행사 효과 | X · 미납품 |

## 구조

```
src/config.py         상수·가정 (21개국, 동 코드 대조, 파라미터, 페르소나)
src/geo.py            UTM-K ↔ WGS84, 동 경계(4안 geojson 재사용)
src/gen_synthetic.py  가상 데이터 생성 (공표 통계 보정 + 시나리오)
src/metrics.py        지표 집계 (Streamlit 비의존)
src/community.py      SQLite 커뮤니티 + 시드
src/app.py            Streamlit 화면 (시민 5탭 / 관리자 6탭)
tests/test_smoke.py   스모크 테스트
pipeline/build_share.py  공유 시연판(../2안_공유) 생성 → github.com/ph3kim-source/ansan-foreign-community-demo
pipeline/prep.py      공표 외국인주민 통계 xlsx → data/processed/dong_month·gu_nat_month (가상 데이터 총량 보정용)
docs/기획_결정사항.md   인터뷰 결정·데이터 매핑·5대 기준·가정·백로그
docs/진행상황.md        완료/남은 일 — 이어서 작업할 때 여기부터
```

v1(관광객 현황판)은 2안 밖 `../_보관/2안_v1_관광객안/` 에 보관한다(2026-11-16 이동).

5대 기준 자체 판정과 리스크는 `docs/기획_결정사항.md` §4·§5 참조.
