"""초안 스모크 테스트 — 가상 데이터 지표 규칙 + 페르소나별 화면 예외 여부.

    cd 2안
    python -m pytest tests -q
"""
import sys
from pathlib import Path

import numpy as np
import pytest

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

import community as cm  # noqa: E402
import metrics as mt  # noqa: E402
from config import MASK_MIN_POP, PERSONAS  # noqa: E402
from geo import utmk_to_wgs84, wgs84_to_utmk  # noqa: E402


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


def test_card_rank_has_no_amount():
    rank = mt.spending_rank("베트남")
    assert "amt" not in rank.columns and rank["결제건수 비중"].sum() == pytest.approx(100, abs=1)


def test_business_name_blocked():
    user = cm.user_by_persona("rustam")
    with pytest.raises(ValueError):
        cm.add_post(user, "ru", "사업장후기", "㈜테스트 후기", "본문", user["dong"], {})


def test_korean_neighbor_only_exchange():
    assert cm.can_write({"is_korean": 1}, "exchange")
    assert not cm.can_write({"is_korean": 1}, "ru")


@pytest.mark.parametrize("persona", list(PERSONAS))
def test_app_renders(persona):
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(str(SRC / "app.py"), default_timeout=240)
    at.session_state["persona"] = persona
    at.run()
    assert not at.exception, [e.message for e in at.exception]
