"""스모크 테스트 — 가상 데이터 지표 규칙 + 커뮤니티 규칙 + 운영 콘솔 화면 예외 여부 + 공지 대상 지정.

시민 화면(휴대폰 앱)의 화면 · API 시험은 tests/test_app.py 에 있다.

    cd 2안
    python -m pytest tests -q

화면·커뮤니티 시험은 임시 DB(temp_db)를 쓴다 — 시연용 data/community.db 를 건드리지 않는다.
"""
import sqlite3
import sys
from contextlib import closing
from pathlib import Path

import numpy as np
import pytest

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

import community as cm  # noqa: E402
import config  # noqa: E402
import metrics as mt  # noqa: E402
from config import MASK_MIN_POP  # noqa: E402
from geo import utmk_to_wgs84, wgs84_to_utmk  # noqa: E402


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    """기본 DB 경로를 임시 파일로 바꾸고 시드한다 (앱도 같은 모듈을 쓰므로 함께 바뀐다)."""
    db = tmp_path / "community.db"
    monkeypatch.setattr(cm, "DB_PATH", db)
    cm.use_db(None)
    cm.init_db()
    yield db
    cm.use_db(None)


def test_utmk_roundtrip():
    x, y = wgs84_to_utmk(126.83, 37.32)
    lon, lat = utmk_to_wgs84(x, y)
    assert abs(lon - 126.83) < 1e-7 and abs(lat - 37.32) < 1e-7
    # 인벤토리 샘플: 성포동 중심 (942311, 1924967) → 안산 상록구 부근
    lon, lat = utmk_to_wgs84(942311, 1924967)
    assert 126.80 < lon < 126.90 and 37.28 < lat < 37.36


def test_residence_share_and_mask():
    df = mt.residence_by_dong("우즈베키스탄")
    assert len(df) == 25
    assert np.isclose(df["share"].sum(), 1.0)
    assert (df.loc[df["value"] < MASK_MIN_POP, "masked"]).all()
    assert mt.living_area_top("우즈베키스탄", 1)["ADM_NM"].iloc[0] == "선부2동"  # 시나리오 가정


def test_residence_coverage_skips_masked():
    df = mt.residence_by_dong("우즈베키스탄")
    top = mt.living_area_top("우즈베키스탄", 3)
    assert mt.residence_coverage("우즈베키스탄", list(top["ADM_CD"])) == pytest.approx(top["share"].sum())
    masked = list(df.loc[df["masked"], "ADM_CD"])
    if masked:  # 소수(마스킹) 동만 고르면 포함률은 0 — 마스킹된 값이 비율로 새지 않게
        assert mt.residence_coverage("우즈베키스탄", masked) == 0


def test_card_rank_has_no_amount():
    """v0.3: 국적별 결제 → 외국인 전체(gb=03 · nt≠000) 업종 대분류만 — 금액 칸은 화면 표에 없다."""
    rank = mt.foreign_spending_rank()
    assert "amt" not in rank.columns and rank["결제건수 비중"].sum() == pytest.approx(100, abs=1)
    assert (mt.ds056_foreign()["nt"] != config.KOREAN_NT_CODE).all() and (mt.ds056_foreign()["gb"] == "03").all()


def test_business_name_blocked(temp_db):
    user = cm.user_by_persona("rustam")
    with pytest.raises(ValueError):
        cm.add_post(user, "ru", "사업장후기", "㈜테스트 후기", "본문", user["dong"], {})


def test_korean_neighbor_only_exchange():
    assert cm.can_write({"is_korean": 1}, "exchange")
    assert not cm.can_write({"is_korean": 1}, "ru")


def test_korean_neighbor_comments_only_in_exchange(temp_db):
    neighbor = cm.user_by_persona("neighbor")
    assert neighbor["is_korean"] == 1 and neighbor["nationality"] is None
    ru_post = cm.list_posts(room="ru", limit=1)[0]
    with pytest.raises(PermissionError):
        cm.add_comment(neighbor, ru_post["id"], "안녕하세요")
    ex_post = cm.list_posts(room="exchange", limit=1)[0]
    assert cm.add_comment(neighbor, ex_post["id"], "반가워요")


def test_notice_visibility_rules():
    lan = {"role": "resident", "is_korean": 0, "nationality": "베트남", "dong": "41273525"}        # 고잔동
    rustam = {"role": "resident", "is_korean": 0, "nationality": "우즈베키스탄", "dong": "41273590"}
    korean = {"role": "resident", "is_korean": 1, "nationality": None, "dong": "41273580"}
    official = {"role": "official", "is_korean": 1, "nationality": None, "dong": "41273532"}
    everyone = {"scope": "all", "target": ["베트남"], "target_dongs": []}
    by_nat = {"scope": "target", "target": ["베트남"], "target_dongs": []}
    by_nat_dong = {"scope": "target", "target": ["베트남"], "target_dongs": ["41273545"]}  # 원곡동만
    assert all(cm.notice_visible(everyone, u) for u in (lan, rustam, korean, official))
    assert cm.notice_visible(by_nat, lan) and not cm.notice_visible(by_nat, rustam)
    assert not cm.notice_visible(by_nat, korean) and cm.notice_visible(by_nat, official)
    assert not cm.notice_visible(by_nat_dong, lan)


def test_target_notice_needs_audience(temp_db):
    with pytest.raises(ValueError):
        cm.add_notice("notice", "안내", {"ko": "대상 없음"}, {"ko": ""}, [], "", "2026-11-16", scope="target")


def test_member_languages_follow_member_db(temp_db):
    langs = cm.member_languages(["중국"])
    assert set(langs) <= {"ko", "zh"} and sum(langs.values()) > 0  # 시드: 중국 국적 회원은 한국어방·중국어방


def test_old_db_is_migrated(tmp_path, monkeypatch):
    """예전 DB(공지 칸 옛 구조, 시연 사용자 일부)도 init_db 만으로 이어서 쓴다 — 지울 필요 없음."""
    db = tmp_path / "old.db"
    with closing(sqlite3.connect(db)) as con:
        con.executescript("""
            CREATE TABLE users(id INTEGER PRIMARY KEY, persona_key TEXT UNIQUE, nationality TEXT, language TEXT,
              dong TEXT, role TEXT, is_korean INTEGER DEFAULT 0, joined_at TEXT);
            CREATE TABLE notices(id INTEGER PRIMARY KEY, kind TEXT, topic TEXT, titles TEXT, bodies TEXT,
              target TEXT, dong TEXT, start_date TEXT, link TEXT, created_at TEXT);
            INSERT INTO users(persona_key, nationality, language, dong, role, is_korean, joined_at)
              VALUES('rustam', '우즈베키스탄', 'ru', '41273590', 'resident', 0, '2026-09-15 09:00:00');
            INSERT INTO notices(kind, topic, titles, bodies, target, dong, start_date, link, created_at)
              VALUES('policy', '의료', '{"ko": "옛 공지"}', '{"ko": "본문"}', '[]', '', '2026-10-01', '', '2026-10-01');""")
        con.commit()
    monkeypatch.setattr(cm, "DB_PATH", db)
    cm.use_db(None)
    cm.init_db()
    with closing(sqlite3.connect(db)) as con:
        cols = {r[1] for r in con.execute("PRAGMA table_info(notices)")}
    assert {"target_dongs", "scope"} <= cols
    old = cm.list_notices("policy")[0]
    assert old["scope"] == "all" and old["target_dongs"] == []
    assert cm.user_by_persona("neighbor")["is_korean"] == 1


def test_console_renders(temp_db):
    """운영 콘솔(담당자 한 사람) — 탭 4개가 예외 없이 그려진다. 옛 시민 화면 · 시연 사용자 고르기는 2026-11-20 에 뺐다."""
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(str(SRC / "app.py"), default_timeout=240)
    at.run()
    assert not at.exception, [e.message for e in at.exception]
    assert [t.label for t in at.tabs] == ["📊 생활권 동향", "🎪 행사 기획·효과", "🧭 외국인 변화", "📣 공지·소통"]
    assert not [w for w in at.selectbox if w.key == "persona"]


# ------------------------------------------------------------------ 공지·정책·행사 작성 (관리자)
def _submit_notice(at, title, nats, kind="event", dongs=None):
    at.radio(key="nf_kind").set_value(kind).run()
    at.multiselect(key="nf_nats").set_value(nats).run()
    assert not at.exception, [e.message for e in at.exception]
    fk = f"{kind}_{'_'.join(sorted(nats)) or 'all'}"
    at.text_input(key=f"nf_title_ko_{fk}").set_value(title)
    if dongs is not None:
        at.multiselect(key=f"nf_dongs_{fk}").set_value(dongs)
    at.button(key=f"nf_submit_{fk}").click()
    at.run()
    assert not at.exception, [e.message for e in at.exception]


def test_notice_form_suggests_from_data(temp_db):
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(str(SRC / "app.py"), default_timeout=240)
    at.run()
    at.radio(key="nf_kind").set_value("event").run()
    at.multiselect(key="nf_nats").set_value(["우즈베키스탄"]).run()
    assert not at.exception, [e.message for e in at.exception]
    rec = mt.event_recommend(["우즈베키스탄"], top=1).iloc[0]
    assert at.selectbox(key="nf_place_event_우즈베키스탄").value == rec["ADM_CD"]   # 장소 = DS-017 추천 1위
    assert at.selectbox(key="nf_hour_event_우즈베키스탄").value == int(rec["TIMEZN_CD"])
    assert at.radio(key="nf_scope_event_우즈베키스탄").value == "target"          # 국적을 고르면 맞춤
    assert at.multiselect(key="nf_dongs_event_우즈베키스탄").value == []           # 대상 동은 기본 비움(국적만)
    at.toggle(key="nf_narrow").set_value(True).run()                               # 좁히기 → DS-028 거주 상위 3동
    top = list(mt.living_area_top("우즈베키스탄", 3)["ADM_CD"])
    assert at.multiselect(key="nf_dongs_event_우즈베키스탄_좁힘").value == top


def test_notice_form_reaches_matching_residents_only(temp_db):
    """콘솔에서 쓴 맞춤 공지 → 휴대폰 앱 소식(server.news 와 같은 cm.notice_visible)에서 대상 주민에게만 보인다."""
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(str(SRC / "app.py"), default_timeout=240)
    at.run()
    title = "시험 행사 — 베트남 주민 대상"
    _submit_notice(at, title, ["베트남"])  # 기본값 그대로 (맞춤 · 대상 동 비움)
    saved = [n for n in cm.list_notices("event") if n["titles"]["ko"] == title]
    assert len(saved) == 1 and saved[0]["scope"] == "target" and saved[0]["target"] == ["베트남"]
    sees = {k: cm.notice_visible(saved[0], cm.user_by_persona(k)) for k in ("lan", "rustam", "neighbor")}
    assert sees == {"lan": True, "rustam": False, "neighbor": False}   # 베트남 결혼이민자만 (우즈벡 고려인 · 내국인 이웃 X)


def test_share_mode_notice_stays_in_session_db(temp_db, monkeypatch):
    from streamlit.testing.v1 import AppTest
    monkeypatch.setattr(config, "SHARE_MODE", True)
    at = AppTest.from_file(str(SRC / "app.py"), default_timeout=240)
    at.run()
    session_db = Path(at.session_state["db_path"])
    try:
        assert session_db != temp_db
        title = "시험 공지 — 공유판 세션"
        _submit_notice(at, title, ["중국"], kind="notice")
        cm.use_db(session_db)
        assert any(n["titles"]["ko"] == title for n in cm.list_notices())
        cm.use_db(None)
        assert not any(n["titles"]["ko"] == title for n in cm.list_notices())
    finally:
        cm.use_db(None)
        session_db.unlink(missing_ok=True)
