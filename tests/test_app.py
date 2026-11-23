"""v0.5 시민 앱(결정 13, 2026-11-20) 시험 — 가게 고르기 · 우리 이웃 많은 곳 단계 · 간편가입 · API.

    cd 2안
    python -m pytest tests -q

API 시험은 임시 DB 로 서버를 띄운다(uvicorn, 이 PC 안 포트) — 시연용 data/community.db 를 건드리지 않는다.
"""
import datetime as dt
import json
import socket
import sys
import threading
import time
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import requests

BASE = Path(__file__).resolve().parents[1]
SRC = BASE / "src"
sys.path.insert(0, str(SRC))
sys.path.insert(0, str(BASE / "pipeline"))

import community as cm  # noqa: E402
import config  # noqa: E402
import metrics as mt  # noqa: E402
import stage_shops  # noqa: E402
from geo import dong_at  # noqa: E402

WONGOK, GOJAN, SEONBU2 = config.DONG_CODE["원곡동"], config.DONG_CODE["고잔동"], config.DONG_CODE["선부2동"]


# ------------------------------------------------------------------ 가게 고르기 (pipeline/stage_shops.py)
def _store(no, name, big, mid, sub, dong="원곡동", branch=""):
    return {"상가업소번호": no, "상호명": name, "지점명": branch, "상권업종대분류명": big, "상권업종중분류명": mid,
            "상권업종소분류명": sub, "행정동코드": WONGOK + "00", "행정동명": dong, "도로명주소": "경기도 안산시 단원구 예시로 1",
            "층정보": "1", "lon": 126.79, "lat": 37.33}


def test_shops_pick_by_category_then_name_inside_business_type():
    df = pd.DataFrame([
        _store("a", "포하노이", "음식", "동남아시아", "베트남식 전문"),          # 업종으로
        _store("b", "아무개마라탕", "음식", "중식", "마라탕/훠궈"),             # 업종으로
        _store("c", "연길양꼬치", "음식", "중식", "중국집"),                  # 상호로(중국)
        _store("d", "사마르칸트", "소매", "종합 소매", "슈퍼마켓"),            # 상호로(중앙아시아 식품)
        _store("e", "금호타이어", "소매", "자동차 부품 소매", "타이어 소매업"),  # 업종 밖 — '타이'에 걸리면 안 됨
        _store("f", "행복베이커리", "음식", "기타 간이", "빵/도넛"),            # '커리' 아님
        _store("g", "중화반점", "음식", "중식", "중국집"),                    # 한국식 중국집 — 넣지 않음
        _store("h", "단골단란주점", "음식", "주점", "요리 주점"),              # '란주' 아님
        _store("i", "우리번역센터", "과학·기술", "기타 전문 과학", "번역/통역 서비스업"),
        _store("j", "씨유편의점", "과학·기술", "기타 전문 과학", "번역/통역 서비스업"),  # 업종 오분류 — 넣지 않음
        _store("k", "몽골리안바베큐", "음식", "주점", "요리 주점"),             # 검수 목록에서 뺌
        _store("l", "레표시카", "음식", "기타 간이", "빵/도넛"),               # 검수 목록에서 넣음
    ])
    ov = pd.DataFrame([
        {"상호명": "몽골리안*", "행정동명": "", "action": "exclude", "kind": "", "sub": "", "cuisine": "", "note": ""},
        {"상호명": "레표시카", "행정동명": "원곡동", "action": "include", "kind": "food", "sub": "", "cuisine": "ca", "note": ""},
    ])
    out = stage_shops.classify(df, ov, services=True).set_index("shop_id")   # 생활 서비스 고르기 규칙까지 본다
    assert set(out.index) == {"a", "b", "c", "d", "i", "l"}
    assert out.loc["a", "cuisine"] == "vn" and out.loc["a", "basis"] == "category"
    assert out.loc["b", "cuisine"] == "cn"
    assert out.loc["c", "cuisine"] == "cn" and out.loc["c", "basis"] == "name"
    assert out.loc["d", "kind"] == "grocery" and out.loc["d", "cuisine"] == "ca"
    assert out.loc["i", "kind"] == "service" and out.loc["i", "sub"] == "translate"
    assert out.loc["l", "basis"] == "review" and out.loc["l", "cuisine"] == "ca"


def test_services_off_the_map_until_verified():
    """생활 서비스는 지금 지도에 싣지 않는다 — 상가정보는 사업자 등록 목록이라 간판 없는 사무실 · 집 주소가 섞이고,
    사용자가 네이버 지도로 찾아본 3곳이 없었다(2026-11-20). 켜더라도 원곡동 밖은 손 목록에 있는 곳만."""
    far = {"행정동코드": SEONBU2 + "00", "행정동명": "선부2동"}
    df = pd.DataFrame([
        {**_store("m", "케이번역", "과학·기술", "기타 전문 과학", "번역/통역 서비스업"), **far},   # 원곡동 밖 번역 — 뺌
        {**_store("n", "하노이여행", "시설관리·임대", "여행 서비스", "여행사"), **far},           # 원곡동 밖 여행사 — 뺌
        _store("o", "하노이여행", "시설관리·임대", "여행 서비스", "여행사"),                     # 원곡동 여행사 — 둠
        {**_store("p", "확인된번역", "과학·기술", "기타 전문 과학", "번역/통역 서비스업"), **far},  # 원곡동 밖이어도 손 목록에 있으면 둠
        {**_store("q", "포하노이", "음식", "동남아시아", "베트남식 전문"), **far},               # 음식점은 이 규칙과 관계없음
    ])
    ov = pd.DataFrame([{"상호명": "확인된번역", "행정동명": "선부2동", "action": "include", "kind": "service",
                        "sub": "translate", "cuisine": "", "note": ""}])
    assert set(stage_shops.classify(df, ov).set_index("shop_id").index) == {"q"}   # 기본값: 생활 서비스 없음
    out = stage_shops.classify(df, ov, services=True).set_index("shop_id")
    assert set(out.index) == {"o", "p", "q"}
    assert out.loc["p", "basis"] == "review"


def test_licence_name_match_rules():
    """가게 이름 ↔ 인허가 신고 이름 — 괄호 · 지점 · 영문 병기는 같게, 흔한 낱말 · 동네 이름 · 지점만 같은 것은 다르게."""
    import verify_shops as vs
    same = [("천상마라탕", "천상(川湘)마라탕"), ("이면가우육면", "이면가란주우육면"), ("미스터케밥", "미스터케밥(Mr.Kebab)"),
            ("퐁닭 이동점", "퐁닭(이동점)"), ("칸티뿌르레스토랑 안산지점", "칸티푸르레스토랑"), ("리치", "리치(RICH)2")]
    diff = [("다복양꼬치", "대박양꼬치"), ("품육안산 상록수점", "훌랄라바베큐치킨&종로냄비김치찌개(상록수점)"),
            ("라홍방마라탕원곡점", "원곡"), ("행복한마라탕", "천상마라탕"), ("취향마라 안산고잔점", "브레댄코(안산고잔점)")]
    for a, b in same:
        assert vs.name_score(a, b) >= vs.MATCH_MIN, (a, b)
    for a, b in diff:
        assert vs.name_score(a, b) < vs.MATCH_MIN, (a, b)


def test_licence_check_keeps_only_open_shops():
    """같은 건물의 같은 가게 신고가 영업 중이면 open, 폐업뿐이면 closed, 없으면 not_found — 업종이 맞는 신고만 본다."""
    import verify_shops as vs
    addr = "경기도 안산시 단원구 다문화길 13"
    shops = pd.DataFrame([
        {"shop_id": "a", "name": "하노이쌀국수", "kind": "food", "road_addr": addr},
        {"shop_id": "b", "name": "술탄케밥", "kind": "food", "road_addr": addr},
        {"shop_id": "c", "name": "없는식당", "kind": "food", "road_addr": addr},
        {"shop_id": "d", "name": "대박중국식품", "kind": "grocery", "road_addr": addr},
    ])
    raw = pd.DataFrame({"상가업소번호": list("abcd"), "상호명": ["하노이쌀국수", "술탄케밥", "없는식당", "대박중국식품"],
                        "지점명": [""] * 4, "지번주소": ["경기도 안산시 단원구 원곡동 789-3"] * 4})

    def lic_row(no, name, state, kind, closed=""):
        return {"관리번호": no, "사업장명": name, "영업상태명": state, "폐업일자": closed, "도로명주소": addr + ", 1층 (원곡동)",
                "지번주소": "", "업태구분명": "", "최종수정시점": "2026-11-18 10:00:00", "type": kind}
    lic = pd.DataFrame([lic_row("1", "하노이쌀국수(HANOI)", "영업/정상", "일반음식점"),
                        lic_row("2", "술탄케밥", "폐업", "일반음식점", "2026-10-07"),
                        lic_row("3", "대박양꼬치", "영업/정상", "일반음식점")])     # 같은 건물 음식점 신고로 식료품을 확인하지 않는다
    lic["rk"], lic["jk"], lic["rm"] = lic["도로명주소"].map(vs.road_key), lic["지번주소"].map(vs.jibun_key), lic["도로명주소"].map(vs.road_main)
    res = vs.match(shops, raw, lic)["res"].to_dict()
    assert res == {"a": "open", "b": "closed", "c": "not_found", "d": "not_found"}


def test_sea_category_alone_is_not_enough():
    """상가정보 소분류 '베트남식 전문'만으로는 싣지 않는다 — 이름 낱말이나 인허가 업태 '외국음식전문점'이 있어야 한다(2026-11-20).
    업태만 있으면 외국 음식점은 맞지만 나라는 모른다 → intl."""
    raw = pd.DataFrame({"상가업소번호": list("abc"), "상권업종소분류명": ["베트남식 전문"] * 3})
    shops = pd.DataFrame([
        {"shop_id": "a", "name": "아우라7080라이브", "basis": "category", "cuisine": "vn", "res": "open", "lic_upte": "라이브카페"},
        {"shop_id": "b", "name": "락만하우스", "basis": "category", "cuisine": "vn", "res": "open", "lic_upte": "외국음식전문점(인도,태국등)"},
        {"shop_id": "c", "name": "미스사이공", "basis": "category", "cuisine": "vn", "res": "open", "lic_upte": "한식"},
    ])
    out = stage_shops.confirm_cuisine(shops, raw).set_index("shop_id")
    assert out.loc["a", "res"] == "cuisine_unconfirmed"
    assert out.loc["b", "res"] == "open" and out.loc["b", "cuisine"] == "intl"
    assert out.loc["c", "res"] == "open" and out.loc["c", "cuisine"] == "vn"          # 이름에 '사이공'
    assert stage_shops.cuisine_of("향교연운남쌀국수") == "cn"                           # 운남(윈난) 쌀국수는 중국 음식


def test_field_check_roundtrip(tmp_path):
    """현장 확인 목록 — 만들고 채우고 들이면: '영업 중'은 지도에(현장 확인), 나머지 결과는 빠지고, 예시 줄 · 빈 줄은 건너뛴다."""
    import make_field_list as mfl
    import import_field_check as ifc
    from openpyxl import load_workbook
    unverified = pd.DataFrame([
        {"shop_id": "g1", "name": "행복식품", "kind": "grocery", "cuisine": "cn", "dong_name": "원곡동", "road_addr": "경기도 안산시 단원구 다문화길 20", "floor": "1", "lon": "126.79", "lat": "37.33"},
        {"shop_id": "g2", "name": "코진카", "kind": "grocery", "cuisine": "ca", "dong_name": "원곡동", "road_addr": "경기도 안산시 단원구 다문화길 3", "floor": "", "lon": "126.79", "lat": "37.33"},
        {"shop_id": "g3", "name": "빈칸마트", "kind": "grocery", "cuisine": "world", "dong_name": "이동", "road_addr": "경기도 안산시 상록구 예시로 1", "floor": "", "lon": "126.86", "lat": "37.30"},
        {"shop_id": "f1", "name": "어느식당", "kind": "food", "cuisine": "cn", "dong_name": "원곡동", "road_addr": "경기도 안산시 단원구 다문화길 9", "floor": "", "lon": "126.79", "lat": "37.33"},
    ])
    rows = mfl.field_rows(unverified, done={"g3x"})
    assert list(rows["shop_id"]) == ["g2", "g1", "g3"]                     # 식료품만 · 동 → 길 → 건물 번호 순
    path = mfl.build_workbook(rows, tmp_path / "목록.xlsx", {"std_ym": "2026-06", "checked": "2026-11-18", "made": "2026-11-20"})
    wb = load_workbook(path)
    ws = wb[mfl.LIST_SHEET]
    assert ws["A2"].value == "예시" and ws["H2"].value == "영업 중"
    ws["H3"], ws["K3"] = "영업 중", "2026-11-25"                           # g2
    ws["H4"], ws["I4"] = "다른 가게", "새가게"                               # g1, 날짜 없음 → 들인 날
    wb.save(path)
    got = ifc.read_results(path).set_index("shop_id")
    assert set(got.index) == {"g2", "g1"} and got.loc["g2", "checked_on"] == "2026-11-25" and got.loc["g1", "note"] == "새가게"
    shops = pd.DataFrame({"shop_id": ["g1", "g2", "g3"], "res": ["not_found"] * 3, "checked": ["2026-11-18"] * 3,
                          "check_src": ["licence"] * 3})
    out = stage_shops.apply_fieldcheck(shops, got.reset_index()).set_index("shop_id")
    assert out.loc["g2", "res"] == "open" and out.loc["g2", "check_src"] == "field" and out.loc["g2", "checked"] == "2026-11-25"
    assert out.loc["g1", "res"] == "field_other" and out.loc["g3", "res"] == "not_found"
    ws["H5"] = "있음"                                                       # 목록에 없는 값은 멈춘다
    wb.save(path)
    with pytest.raises(SystemExit):
        ifc.read_results(path)


def test_shop_file_is_public_only_and_inside_ansan():
    path = BASE / "data" / "public" / "shops_ansan.csv"
    if not path.exists():
        pytest.skip("가게 목록 없음 — python pipeline\\stage_shops.py")
    s = pd.read_csv(path, dtype=str)
    assert list(s.columns) == stage_shops.COLUMNS           # 공공 상가정보에서 고른 칸뿐
    assert s["dong"].isin(list(config.DONG_NAME)).all()
    assert s["kind"].isin(["food", "grocery", "service"]).all()
    assert s["cuisine"].isin(stage_shops.CUISINES).all()
    lon, lat = s["lon"].astype(float), s["lat"].astype(float)
    assert lon.between(126.5, 126.95).all() and lat.between(37.15, 37.42).all()
    assert not s["name"].str.contains("단란|노래").any()      # 오탐 막기 (2026-11-20 점검에서 나온 것)
    assert not (s["kind"] == "service").any()                # 생활 서비스는 확인 목록이 생기기 전까지 싣지 않는다
    assert s["checked"].fillna("").str.match(r"\d{4}-\d{2}-\d{2}$").all()   # 지도의 가게는 모두 영업 확인(대장 · 현장)
    assert s["check_src"].isin(["licence", "field"]).all()
    assert not s.duplicated(["name", "dong"]).any() or not s.duplicated(["road_addr", "name"]).any()   # 같은 가게 핀 두 개 없음
    assert len(s) > 250 and (s["dong"] == WONGOK).sum() > 80     # 영업 · 음식 종류 확인 뒤 291곳(2026-11-20) — 파이프라인이 깨져 크게 줄면 걸린다


# ------------------------------------------------------------------ 우리 이웃 많은 곳 (metrics.presence_levels)
def test_presence_levels_only_steps_and_masks_small_counts():
    lv = mt.presence_levels("베트남")
    assert set(lv) == {"평일", "주말", "연휴"} and all(set(lv[d]) == set(range(24)) for d in lv)
    # 연휴(한국 공휴일 날짜들)는 평일 · 주말과 같은 단계 기준 — 가상 자료는 연휴 낮에 원곡동으로 모인다
    assert lv["연휴"] != lv["평일"] and {v for h in lv["연휴"].values() for v in h.values()} <= {None, 1, 2, 3, 4}
    assert {h["date"] for h in mt.presence_holidays()} <= set(config.KR_HOLIDAYS)
    values = {v for d in lv.values() for h in d.values() for v in h.values()}
    assert values <= {None, 1, 2, 3, 4} and {1, 4} <= values
    # 그 시각 인원이 MASK_MIN_POP 미만인 동은 단계 대신 None
    g = mt.gathering("베트남", "평일", [14])
    for r in g.itertuples():
        assert (lv["평일"][14][r.ADM_CD] is None) == bool(r.masked)
    # 단계 기준을 48개 시각에 한 번에 잡으므로 시각에 따라 그림이 달라진다
    assert lv["평일"][3] != lv["평일"][14]


def test_hex_cells_levels_only_and_mask_small_cells():
    """골목 칸(육각, ≈H3 res9) — 같은 칸 안 점은 같은 칸으로, 적은 칸은 칠하지 않고, 인원은 보내지 않는다."""
    area = config.CELL_HEX_AREA_M2
    R = mt.hex_radius(area)
    assert abs(3 * np.sqrt(3) / 2 * R * R - area) < 1                      # 넓이 그대로
    q, r = mt.hex_axial([950_000.0, 951_234.0], [1_940_000.0, 1_939_100.0], R)
    cx, cy = mt.hex_center(q, r, R)
    assert (mt.hex_axial(cx, cy, R)[0] == q).all() and (mt.hex_axial(cx + 0.4 * R, cy, R)[0] == q).all()
    rows = []
    for day in ("평일", "주말"):
        for h in range(24):
            rows.append({"daytype": day, "TIME_CD": h, "NAT": "중국", "UTMK_X": cx[0], "UTMK_Y": cy[0], "POP": 50.0})
            rows.append({"daytype": day, "TIME_CD": h, "NAT": "중국", "UTMK_X": cx[1], "UTMK_Y": cy[1], "POP": 4.0})
    out = mt.cells_from_grid(pd.DataFrame(rows), "중국", area, 10.0, 0.5)
    assert out["usable"] and len(out["hex"]) == 1                          # 4명 칸은 한 번도 칠해지지 않아 보내지 않는다
    assert {v for d in out["levels"].values() for h in d for v in h} <= {0, 1, 2, 3, 4}
    assert "POP" not in json.dumps(out) and len(out["hex"][0][1]) == 6
    assert mt.cells_from_grid(pd.DataFrame(rows), "베트남", area, 10.0, 0.5) is None
    assert mt.presence_cells("중국") is None                                 # 가상 판에는 골목 칸 집계본이 없다


def test_busy_shops_marks_only_busy_places():
    """고향 사람 많이 다니는 쪽 가게 — 주말 낮 여섯 시각 중 절반 이상 '많음' 이상인 곳만 표시(골목 칸이 없으면 동네로)."""
    week = mt.presence_levels("베트남")["주말"]
    n_busy = {code: sum(1 for h in mt.BUSY_HOURS if (week[h].get(code) or 0) >= mt.BUSY_LEVEL) for code in config.DONG_NAME}
    busy = [c for c, n in n_busy.items() if n >= 3]
    quiet = [c for c, n in n_busy.items() if n == 0]
    assert busy and quiet
    out = mt.busy_shops("베트남", (("s1", 126.8, 37.3, busy[0]), ("s2", 126.8, 37.3, quiet[0])))
    assert out == {"s1": "dong"}                                          # 가상 판에는 골목 칸이 없어 동네로 본다


def test_meetup_dongs_are_names_of_unmasked_dongs():
    dongs = mt.meetup_dongs("우즈베키스탄")
    g = mt.gathering("우즈베키스탄", "주말", range(12, 18)).set_index("ADM_CD")
    assert 0 < len(dongs) <= 3 and not g.loc[dongs, "masked"].any()


def test_dong_at_point():
    assert dong_at(126.7886, 37.3271) == WONGOK               # 안산역
    assert dong_at(127.5, 37.0) is None


# ------------------------------------------------------------------ 간편가입 · 세션 · 제보 (community)
@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    db = tmp_path / "community.db"
    monkeypatch.setattr(cm, "DB_PATH", db)
    cm.use_db(None)
    cm.init_db()
    yield db
    cm.use_db(None)


def test_signup_asks_only_nationality_language_dong(temp_db):
    u = cm.create_user("네팔", "etc", WONGOK, False)
    assert (u["nationality"], u["language"], u["dong"], u["role"]) == ("네팔", "etc", WONGOK, "resident")
    k = cm.create_user("베트남", "ko", GOJAN, True)
    assert k["is_korean"] == 1 and k["nationality"] is None      # 내국인은 국적을 남기지 않는다
    for bad in (("화성", "vi", GOJAN, False), ("베트남", "xx", GOJAN, False), ("베트남", "vi", "00000000", False)):
        with pytest.raises(ValueError):
            cm.create_user(*bad)
    tok = cm.create_session(u["id"])
    assert cm.user_by_token(tok)["id"] == u["id"] and cm.user_by_token("nope") is None


def test_app_places_only_precise_and_votes(temp_db):
    seeds = len(cm.list_places())
    assert seeds > 0 and cm.list_app_places() == []               # 시드 장소(동 중심 가상 좌표)는 앱 지도에 없다
    u = cm.user_by_persona("lan")
    pid = cm.add_place_at(u, "  Phở 집  ", "food", "vn", WONGOK, 126.7886, 37.3271)
    other = cm.user_by_persona("rustam")
    cm.vote_place(pid, other["id"])
    rows = cm.list_app_places(u["id"])
    assert rows[0]["name"] == "Phở 집" and rows[0]["votes"] == 1 and rows[0]["mine"] and not rows[0]["verified"]
    assert "created_by" not in rows[0]                             # 누가 올렸는지는 내보내지 않는다
    anon = cm.list_app_places()                                    # 로그인 안 한 요청(GET /api/places)도 마찬가지
    assert anon[0]["mine"] is False and "created_by" not in anon[0]


def test_same_second_newest_first(temp_db, monkeypatch):
    """같은 초에 쓴 글 · 질문 · 장소는 나중 것이 위 — HTML 판 가짜 서버(pipeline/html/demo_api.js)와 같은 순서."""
    fixed = cm._now()        # 시드는 '지금'에서 거꾸로 센 시각이라 고정 날짜를 쓰면 시험 시각에 따라 시드 글이 끼어든다
    monkeypatch.setattr(cm, "_now", lambda: fixed)
    lan = cm.user_by_persona("lan")

    def order(rows, *ids):   # 새로 쓴 두 개의 앞뒤만 본다 — 시드 글 시각과 상관없이
        return [r["id"] for r in rows if r["id"] in ids]

    p1, p2 = (cm.add_post(lan, "vi", "자유", t, "b", GOJAN) for t in ("first", "second"))
    assert order(cm.list_posts(room="vi", limit=500), p1, p2) == [p2, p1]
    q1, q2 = (cm.add_question(lan, t, "") for t in ("first", "second"))
    assert order(cm.list_questions(), q1, q2) == [q2, q1]
    a, b = (cm.add_place_at(lan, n, "food", "vn", WONGOK, 126.7886, 37.3271) for n in ("A", "B"))
    assert order(cm.list_app_places(), a, b) == [b, a]


def test_shop_vote_toggles_and_feedback_reasons(temp_db):
    u = cm.user_by_persona("lan")
    assert cm.toggle_shop_vote("S1", u["id"]) is True
    assert cm.shop_vote_counts(u["id"]) == ({"S1": 1}, {"S1"})
    assert cm.toggle_shop_vote("S1", u["id"]) is False
    cm.add_shop_feedback("S1", u["id"], "closed")
    cm.add_shop_feedback("S1", u["id"], "closed")                 # 같은 사람 같은 이유는 한 번
    assert cm.open_shop_feedback()[0]["n"] == 1
    with pytest.raises(ValueError):
        cm.add_shop_feedback("S1", u["id"], "싫어요")
    cm.close_shop_feedback("S1")
    assert cm.open_shop_feedback() == []


def test_comment_aliases_number_people_not_comments(temp_db):
    lan, rustam, dongpo = (cm.user_by_persona(k) for k in ("lan", "rustam", "dongpo"))
    pid = cm.add_post(lan, "vi", "자유", "t", "b", GOJAN)
    for user in (rustam, lan, rustam, dongpo):
        cm.add_comment(user, pid, "c")
    assert [c["alias_n"] for c in cm.comment_thread(pid, lan["id"])] == [1, 0, 1, 2]


# ------------------------------------------------------------------ API (src/server.py)
def _free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def api(tmp_path_factory):
    import uvicorn
    import server
    db = tmp_path_factory.mktemp("appdb") / "community.db"
    port = _free_port()
    srv = uvicorn.Server(uvicorn.Config(server.build_app(str(db)), host="127.0.0.1", port=port, log_level="error"))
    th = threading.Thread(target=srv.run, daemon=True)
    th.start()
    for _ in range(100):
        if srv.started:
            break
        time.sleep(0.05)
    base = f"http://127.0.0.1:{port}"

    def call(path, method="GET", body=None, token=None):
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        r = requests.request(method, base + path, json=body, headers=headers, timeout=30)
        return r.status_code, (r.json() if r.headers.get("content-type", "").startswith("application/json") else r.text)

    def login(persona):
        return call("/api/session", "POST", {"persona": persona})[1]["token"]

    call.login = login
    call.base = base
    yield call
    srv.should_exit = True
    th.join(5)
    cm.set_default_db(None)


def test_api_presence_sends_levels_only(api):
    lan = api.login("lan")
    code, body = api("/api/presence?nat=중국", token=lan)      # 주민은 자기 국적만 — nat 는 무시된다
    assert code == 200 and body["nat"] == "베트남"
    text = json.dumps(body, ensure_ascii=False)
    assert "share" not in text and "POP" not in text
    assert {v for d in body["levels"].values() for h in d.values() for v in h.values()} <= {None, 1, 2, 3, 4}
    assert "연휴" in body["levels"] and set(body["holidays"]) <= set(config.KR_HOLIDAYS)
    assert body["cells"] is None                                          # 골목 칸은 실데이터 판 집계본이 있을 때만
    assert api("/api/presence", token=api.login("neighbor"))[0] == 403    # 내국인 이웃에게는 국적별 밀집 화면 없음(D8)
    assert api("/api/presence?nat=중국", token=api.login("official"))[1]["nat"] == "중국"
    assert api("/api/presence")[0] == 401


def test_api_same_country_filter_and_shop_marks(api):
    """언어방 '같은 나라 글만'(nat) · 가게의 '고향 사람 많은 쪽' 표시(주민 본인 국적만, 있다/없다만)."""
    lan = api.login("lan")
    for room, nat in (("vi", "베트남"), ("ko", "중국")):
        posts = api(f"/api/posts?room={room}&nat={nat}", token=lan)[1]["posts"]
        assert all(p["nat"] == nat for p in posts)
    assert api("/api/posts?room=ko&nat=없는나라", token=lan)[0] == 200    # 모르는 국적은 거르지 않는다
    shops = api("/api/shops", token=lan)[1]["shops"]
    assert {s.get("near", "") for s in shops} <= {"", "dong", "cell"} and any(s.get("near") for s in shops)
    assert not any(s.get("near") for s in api("/api/shops", token=api.login("neighbor"))[1]["shops"])


def test_api_signup_and_profile(api):
    code, body = api("/api/signup", "POST", {"nationality": "몽골", "language": "en", "dong": WONGOK})
    assert code == 200 and body["user"]["uiLang"] == "en" and body["user"]["nationality"] == "몽골"
    tok = body["token"]
    assert api("/api/me", "PATCH", {"language": "ru"}, tok)[1]["uiLang"] == "ru"
    assert api("/api/me", "PATCH", {"dong": "123"}, tok)[0] == 400
    assert api("/api/signup", "POST", {"nationality": "몽골", "language": "en", "dong": "x"})[0] == 400


def test_api_community_rules(api):
    lan, neighbor = api.login("lan"), api.login("neighbor")
    code, body = api("/api/posts", "POST", {"room": "vi", "tag": "자유", "title": "Xin chào", "body": "Hello"}, lan)
    assert code == 201
    pid = body["id"]
    assert api("/api/posts", "POST", {"room": "vi", "tag": "자유", "title": "a", "body": "b"}, neighbor)[0] == 403
    assert api(f"/api/posts/{pid}/comments", "POST", {"body": "x"}, neighbor)[0] == 403
    assert api("/api/posts", "POST", {"room": "exchange", "tag": "자유", "title": "a", "body": "b"}, neighbor)[0] == 201
    assert api(f"/api/posts/{pid}/like", "POST", {}, neighbor)[1] == {"liked": True, "likes": 1}
    detail = api(f"/api/posts/{pid}", token=lan)[1]
    assert detail["mine"] and detail["canWrite"] and "author_id" not in json.dumps(detail)
    hidden = [api(f"/api/posts/{pid}/report", "POST", {"reason": "광고·스팸"}, api.login(k))[1]["hidden"]
              for k in ("rustam", "dongpo", "neighbor")]
    assert hidden == [False, False, True] and api(f"/api/posts/{pid}", token=lan)[0] == 404


def test_api_places_and_shops(api):
    lan = api.login("lan")
    assert api("/api/places", "POST", {"name": "x", "kind": "food", "lon": 127.5, "lat": 37.0}, lan) == \
        (400, {"error": "outside_ansan"})
    code, body = api("/api/places", "POST", {"name": "Bánh mì", "kind": "food", "cuisine": "vn",
                                             "lon": 126.7886, "lat": 37.3271}, lan)
    assert code == 201 and body["dong"] == WONGOK
    shops = api("/api/shops")[1]["shops"]
    if shops:
        sid = next(s["id"] for s in shops if s["kind"] != "official")
        assert api(f"/api/shops/{sid}/vote", "POST", {}, lan)[1] == {"voted": True, "votes": 1}
        assert api(f"/api/shops/{sid}/feedback", "POST", {"reason": "closed"}, lan)[0] == 200
        assert api("/api/shops/NOPE/vote", "POST", {}, lan)[0] == 404


def test_api_news_respects_targeted_notices(api):
    nid = cm.add_notice("notice", "행정", {"ko": "베트남 주민 안내", "vi": "Thông báo"}, {"ko": "본문", "vi": "Nội dung"},
                        ["베트남"], "", "2026-12-01", scope="target")
    lan = api("/api/news", token=api.login("lan"))[1]
    assert any(i["id"] == nid and i["title"] == "Thông báo" and i["forMe"] for i in lan["infos"])
    for other in ("rustam", "neighbor"):
        assert all(i["id"] != nid for i in api("/api/news", token=api.login(other))[1]["infos"])


def test_api_serves_app_shell(api):
    r = requests.get(api.base + "/", timeout=10)
    assert r.status_code == 200 and 'src="js/main.js"' in r.text
    assert requests.get(api.base + "/sw.js", timeout=10).headers["content-type"].startswith("text/javascript")


def test_app_shell_holds_no_data():
    """화면 코드(app/)에는 데이터가 없다 — 모든 숫자는 서버 API 에서 받는다(실데이터 판이 파일로 새지 않게)."""
    files = [p for p in (BASE / "app").rglob("*") if p.is_file()]
    assert not [p for p in files if p.suffix.lower() in (".csv", ".json", ".db", ".xlsx")]
    text = "\n".join(p.read_text(encoding="utf-8", errors="ignore") for p in files if p.suffix in (".js", ".html")
                     and "vendor" not in p.parts)
    assert "POP" not in text and "data/real" not in text


def test_lan_binding_warns_in_real_mode(monkeypatch, capsys):
    """같은 와이파이로 열기 — 2026-11-20 인벤토리 데이터 사용 승인 뒤로 실데이터 판도 열 수 있다. 실데이터 판이면 경고를 찍는다."""
    import server
    monkeypatch.setattr(server.C, "IS_REAL", True)
    assert server.bind_host(True) == "0.0.0.0" and "실데이터" in capsys.readouterr().out
    assert server.bind_host(False) == "127.0.0.1"
    monkeypatch.setattr(server.C, "IS_REAL", False)
    assert server.bind_host(True) == "0.0.0.0" and capsys.readouterr().out == ""


def test_ui_strings_cover_five_languages():
    """화면 글은 모두 5개 언어(한 · 영 · 중 · 러 · 베)를 갖는다 — 빠진 칸이 있으면 한국어가 섞여 보인다."""
    import ast
    import re
    js = (BASE / "app" / "js" / "i18n.js").read_text(encoding="utf-8")
    body = js[js.index("const T = {"):js.index("const NAT = {")]
    rows = re.findall(r"^\s*'([^']+)': (\[.*\]),\s*$", body, flags=re.M)
    assert len(rows) > 150
    for key, arr in rows:
        values = ast.literal_eval(arr)
        assert len(values) == 5 and all(isinstance(v, str) and v for v in values), key
