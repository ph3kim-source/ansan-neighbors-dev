"""v0.3 (2026-11-18) 실데이터 대조 반영분 시험 — 가상 데이터 판 + (있으면) 실데이터 판 화면 렌더.

    cd 2안
    python -m pytest tests -q

실데이터 판 시험은 data/real 이 있을 때만 돈다(공개 저장소 · 공유판에는 없다). 원자료 행은 출력하지 않는다.
"""
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

BASE = Path(__file__).resolve().parents[1]
SRC = BASE / "src"
sys.path.insert(0, str(SRC))
sys.path.insert(0, str(BASE / "pipeline"))

import config  # noqa: E402
import metrics as mt  # noqa: E402


# ------------------------------------------------------------------ 사는 곳 = DS-017 장기 · 평일 새벽 (D10)
def test_residence_is_weekday_night_long_term():
    prof = mt.ds017_profile()
    sub = prof[(prof["month"] == config.LATEST_MONTH) & (prof["daytype"] == "평일") & (prof["IN_FORN_DIV_NM"] == 1)
               & prof["TIMEZN_CD"].isin(config.RESIDENT_HOURS) & (prof["CNTRY_NM"] == "베트남")]
    expect = sub.groupby("ADM_CD")["POP"].sum() / len(config.RESIDENT_HOURS)
    got = mt.residence().query("CNTRY_NM == '베트남'").set_index("ADM_CD")["RAW"]   # 보정 전 통신 원값
    assert np.allclose(got.sort_index(), expect.sort_index())


def test_residence_calibrated_to_public_dong_totals():
    """v0.4 사는 곳 보정: 동 총량 = 공표 동별 외국인주민, 동 안 국적 구성은 통신 그대로."""
    res = mt.residence()
    pub = mt._public_dong_total(config.LATEST_MONTH)
    tot = res.groupby("ADM_CD")["POP"].sum()
    assert np.allclose(tot, pub.reindex(tot.index))
    one = res[res["ADM_CD"] == config.DONG_CODE["원곡동"]]
    assert np.allclose(one["POP"] / one["POP"].sum(), one["RAW"] / one["RAW"].sum())
    raw = mt.residence(calibrate=False)
    assert np.allclose(raw["POP"], raw["RAW"])


def test_nationality_mix_is_share_within_month():
    mix = mt.nationality_mix(config.NAT_NAMES)
    assert np.allclose(mix.groupby("ETL_YM")["share"].sum(), 1.0)


# ------------------------------------------------------------------ 21개국 · 전입 PUBLIC · 공표 증감
def test_nation_list_matches_delivered_categories():
    names = set(config.NAT_NAMES)
    assert len(names) == 21 and {"캐나다", "프랑스", "기타"} <= names
    assert not ({"우크라이나", "키르기스스탄"} & names)
    assert set(mt.ds017_profile()["CNTRY_NM"].unique()) <= names


def test_ds076_reads_public_only_and_masks():
    files = mt._files("GYEONGGI_IN_STAT_*.csv")
    assert files and all("_PUBLIC_" in f.name for f in files)       # 원본 · PUBLIC 이중 집계 방지
    na = mt.new_arrivals()
    assert len(na) == 25 and (na.loc[na["value"] < config.K_ANON_MIN, "masked"]).all()
    assert "abroad" not in na.columns                                  # 실물에 해외(99999) 전입 없음


def test_foreign_change_is_month_over_month():
    fc = mt.foreign_change()
    assert fc.attrs["prev_month"] < config.LATEST_MONTH
    assert (fc["diff"] == fc["value"] - fc["prev"]).all()


# ------------------------------------------------------------------ 산출 구간 경계 · 연휴 · 행사 효과
def test_breaks_detect_level_jump_and_baseline_stays_in_regime():
    days = pd.date_range("2026-03-01", "2026-04-30").strftime("%Y%m%d")
    s = pd.Series([100.0 if d < "20260401" else 520.0 for d in days], index=days)
    br = mt._breaks(s)
    assert br == ["20260401"]
    assert mt._baseline_days(["20260407"], br) == []                   # 1 · 2주 전이 3월 → 다른 구간이라 뺌
    assert mt._baseline_days(["20260616"], br) == ["20260609", "20260602"]
    assert mt._baseline_days(["20260421"], br) == ["20260407"]          # 4/14 는 명절(동남·남아시아 새해)이라 뺌


def test_holiday_effect_has_both_kinds():
    he = mt.holiday_effect()
    assert {"한국 연휴", "모국 명절"} <= set(he["구분"])
    assert (he["배수"].dropna() > 0).all()


def test_event_effect_targets_rise_in_synthetic_preset():
    if config.IS_REAL:
        pytest.skip("가상 판 시나리오 시험")
    ev = mt.preset_event(config.EVENTS[-1]["area_cd"])
    eff = mt.event_effect(ev["dong"], ev["days"], ev["target"])
    assert eff["대상 국적"].any()
    assert mt.event_total_uplift(ev["dong"], ev["days"], ev["target"]) > 0


def test_sales_effect_needs_daily_cards():
    if mt.card_is_daily():
        pytest.skip("일별 카드(실데이터 판)")
    assert mt.event_sales_effect(config.DONG_CODE["원곡동"], ["20260501"]).empty


# ------------------------------------------------------------------ DS-014 외국인 유동 (결정 7)
def test_ds014_trend_and_sex_age():
    tr = mt.foreign_flow_trend()
    assert np.allclose(tr.groupby("month")["share"].sum(), 1.0)
    assert tr["ratio"].dropna().between(0, 1).all()
    sa = mt.foreign_sex_age(config.DONG_CODE["원곡동"])
    assert len(sa) == 26 and sa["비중"].dropna().sum() <= 1.0 + 1e-9


# ------------------------------------------------------------------ v0.4 — 50m 격자 집계본 · 2단계 스위치 · 다문화특구
def test_grid_cache_uses_names_and_mask():
    g = mt.ds032_grid()
    assert mt.grid_nations()[0] == mt.GRID_ALL
    assert set(g["TIME_CD"].unique()) <= set(config.GRID_HOURS) and set(g["daytype"]) <= {"평일", "주말"}
    assert set(g["NAT"]) - {mt.GRID_ALL} <= set(config.NAT_NAMES)       # 실물처럼 국적 이름
    hour = config.GRID_HOURS[1]
    sums = []
    for res in config.GRID_RES_OPTIONS:                                    # 가림은 칸을 묶은 뒤에
        cells = mt.grid_cells(mt.GRID_ALL, "평일", hour, res)
        assert len(cells) and {"lon", "lat", "POP"} <= set(cells.columns)
        assert (cells["POP"] >= config.GRID_MIN_POP).all()
        sums.append(cells["POP"].sum())
    assert sums == sorted(sums)                                            # 크게 묶을수록 가려지는 몫이 줄어든다


def test_grid_aggregate_daily_mean_and_drops_korean():
    rows = []
    for ymd in ("20260601", "20260602"):          # 월 · 화 → 평일 이틀
        rows.append({"ADMI_NM": "원곡동", "UTMK_X": 100, "UTMK_Y": 200, "TIME_CD": "03", "FORN_GB": "중국",
                     "M_10_CNT": 6.0, "F_10_CNT": 4.0, "ETL_YMD": ymd})
        rows.append({"ADMI_NM": "원곡동", "UTMK_X": 100, "UTMK_Y": 200, "TIME_CD": "03", "FORN_GB": "N",
                     "M_10_CNT": 99.0, "F_10_CNT": 99.0, "ETL_YMD": ymd})
    out = mt.grid_aggregate([pd.DataFrame(rows)], [3], 5.0)
    china = out[(out["NAT"] == "중국") & (out["daytype"] == "평일")]
    assert china["POP"].tolist() == [10.0]                                # 이틀 평균 (6+4)
    assert "N" not in set(out["NAT"])                                     # 내국인 행은 뺀다


def test_phase2_tags_hidden(tmp_path, monkeypatch):
    import community as cm
    assert not config.ENABLE_PHASE2 and not (set(config.PHASE2_TAGS) & set(config.ACTIVE_TAGS))
    monkeypatch.setattr(cm, "DB_PATH", tmp_path / "c.db")
    cm.use_db(None)
    cm.init_db()
    try:
        assert not [p for p in cm.list_posts(limit=500) if p["tag"] in config.PHASE2_TAGS]
    finally:
        cm.use_db(None)


def test_zone_only_in_real_mode():
    if config.IS_REAL:
        pytest.skip("실데이터 판")
    assert mt.zone_geojson() is None                                      # 시 내부 산출물 — 가상 · 공유판에는 없음


# ------------------------------------------------------------------ v0.4 — 격자 칸 그리기 · 칸 거리 이름 (결정 12)
def test_grid_squares_are_res_sized_and_centered():
    from geo import wgs84_to_utmk
    hour = config.GRID_HOURS[1]
    for res in config.GRID_RES_OPTIONS:
        cells = mt.grid_cells(mt.GRID_ALL, "평일", hour, res)
        assert ((cells["x0"] % res) == 0).all() and ((cells["y0"] % res) == 0).all()   # 50 · 100 · 250m 칸이 포개진다
        sq = np.array(mt.grid_squares(cells, res))
        assert sq.shape == (len(cells), 4, 2)
        x, y = wgs84_to_utmk(sq[..., 0], sq[..., 1])
        assert np.allclose(x[:, 1] - x[:, 0], res, atol=0.05) and np.allclose(y[:, 2] - y[:, 1], res, atol=0.05)
        cx, cy = wgs84_to_utmk(cells["lon"].to_numpy(), cells["lat"].to_numpy())
        assert np.allclose(cx, x.mean(axis=1), atol=0.05) and np.allclose(cy, y.mean(axis=1), atol=0.05)


def test_cell_streets_name_longest_road_then_neighbors(monkeypatch):
    fake = pd.DataFrame({"x0": [1000, 1000, 1050, 1150], "y0": [2000] * 4,
                         "RN": ["가로", "나길", "가로", "다길"], "len_m": [30.0, 40.0, 50.0, 10.0]})
    monkeypatch.setattr(mt, "road_cells", lambda: fake)
    mt._street_lengths.cache_clear()
    try:
        cells = pd.DataFrame({"x0": [1000, 1050, 1100, 5000], "y0": [2000] * 4, "POP": [10.0, 20.0, 30.0, 40.0],
                              "ADMI_NM": ["원곡동"] * 4})
        assert mt.cell_streets(cells, 50) == ["나길", "가로", "가로", ""]    # 칸 안 최장 · 없으면 둘레 8칸 · 멀면 빈 이름
        big = pd.DataFrame({"x0": [1000], "y0": [2000], "POP": [9.0], "ADMI_NM": ["원곡동"]})
        assert mt.cell_streets(big, 100) == ["가로"]                          # 100m 칸 = 50m 두 칸의 길이 합
        ss = mt.street_share(cells, mt.cell_streets(cells, 50))
        assert ss.iloc[0]["street"] == "가로" and abs(ss.iloc[0]["share"] - 0.5) < 1e-9   # 이름 없는 칸도 분모에
    finally:
        mt._street_lengths.cache_clear()


def test_streets_only_in_real_mode():
    if config.IS_REAL:
        pytest.skip("실데이터 판")
    assert mt.road_cells() is None and not mt.has_streets()             # 가상 칸에 실제 도로명을 붙이지 않는다
    cells = mt.grid_cells(mt.GRID_ALL, "평일", config.GRID_HOURS[1])
    assert mt.cell_streets(cells, config.GRID_RES_DEFAULT) == [""] * len(cells)


def _write_dbf(path, fields, rows, encoding="cp949"):
    """시험용 작은 dBASE III 표 — fields = [(열 이름, 길이)], rows = [(지움 표시, [값, ...])]."""
    import struct
    rlen = 1 + sum(length for _, length in fields)
    hlen = 32 + 32 * len(fields) + 1
    head = struct.pack("<B3BIHH20x", 3, 126, 11, 20, len(rows), hlen, rlen)
    for name, length in fields:
        head += struct.pack("<11sc4xB15x", name.encode("ascii"), b"C", length)
    body = b"".join((b"*" if deleted else b" ")
                    + b"".join(v.encode(encoding).ljust(length, b" ")[:length] for (_, length), v in zip(fields, vals))
                    for deleted, vals in rows)
    path.write_bytes(head + b"\r" + body + b"\x1a")


def _write_polyline_shp(path, lines):
    import struct
    recs = b""
    for i, pts in enumerate(lines, start=1):
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        content = struct.pack("<i4dii", 3, min(xs), min(ys), max(xs), max(ys), 1, len(pts)) + struct.pack("<i", 0)
        content += b"".join(struct.pack("<2d", *p) for p in pts)
        recs += struct.pack(">ii", i, len(content) // 2) + content
    header = struct.pack(">i", 9994) + b"\0" * 20 + struct.pack(">i", (100 + len(recs)) // 2)
    header += struct.pack("<ii4d4d", 1000, 3, 0, 0, 0, 0, 0, 0, 0, 0)
    path.write_bytes(header + recs)


def test_stage_roads_reads_dbf_shp_and_splits_length(tmp_path):
    import stage_roads
    _write_dbf(tmp_path / "r.dbf", [("RN", 20), ("SIG_CD", 5)],
               [(False, ["원곡로", "41273"]), (False, ["수원로", "41111"]), (True, ["지운길", "41271"]),
                (False, ["영동고속도로", "41271"])])
    dbf, enc = stage_roads.read_dbf(tmp_path / "r.dbf", ["RN", "SIG_CD"])
    assert enc == "cp949" and dbf["RN"].tolist()[:2] == ["원곡로", "수원로"]
    assert dbf["deleted"].tolist() == [False, False, True, False]
    assert stage_roads.ansan_roads(dbf).index.tolist() == [0]            # 안산만 · 지운 행 · 고속도로 뺌
    _write_polyline_shp(tmp_path / "r.shp", [[(0, 0), (100, 0)], [(0, 0), (1, 1)], [(0, 0), (1, 1)], [(25, 10), (25, 60)]])
    lines = stage_roads.read_shp_lines(tmp_path / "r.shp", keep={0, 3})
    assert sorted(lines) == [0, 3] and lines[0][0].tolist() == [[0.0, 0.0], [100.0, 0.0]]
    cells = stage_roads.cell_lengths([("가로", lines[0]), ("세로", lines[3])])
    got = {(r.x0, r.y0, r.RN): round(r.len_m, 6) for r in cells.itertuples()}
    assert got == {(0, 0, "가로"): 50.0, (50, 0, "가로"): 50.0, (0, 0, "세로"): 40.0, (0, 50, "세로"): 10.0}


def test_is_utmk_accepts_both_spellings():
    import stage_real
    esri = ('PARAMETER["False_Easting",1000000.0],PARAMETER["False_Northing",2000000.0],'
            'PARAMETER["Central_Meridian",127.5],PARAMETER["Scale_Factor",0.9996]')
    epsg = ('PARAMETER["central_meridian",127.5],PARAMETER["scale_factor",0.9996],'
            'PARAMETER["false_easting",1000000],PARAMETER["false_northing",2000000]')
    assert stage_real.is_utmk(esri) and stage_real.is_utmk(epsg)
    assert not stage_real.is_utmk(epsg.replace("127.5", "127"))         # 중부원점 계열은 아님


@pytest.mark.skipif(sys.platform != "win32", reason="윈도 바로가기")
def test_shortcut_dir_follows_lnk_when_listing_is_empty(tmp_path, monkeypatch):
    import stage_real
    target = tmp_path / "targets" / "03_test"
    target.mkdir(parents=True)
    drive = tmp_path / "mydrive"
    drive.mkdir()
    lnk = drive / "03_test.lnk"
    ps = (f"$s = (New-Object -ComObject WScript.Shell).CreateShortcut('{lnk}'); "
          f"$s.TargetPath = '{target}'; $s.Save()")
    subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps], check=True, capture_output=True,
                   timeout=60)
    empty = tmp_path / "shortcut-targets"
    empty.mkdir()
    monkeypatch.setattr(stage_real, "SHORTCUTS", empty)                   # 드라이브를 다시 켠 직후처럼 목록이 빈 상태
    monkeypatch.setattr(stage_real, "MY_DRIVE", drive)
    assert stage_real.shortcut_dir("03_test") == target
    assert stage_real.shortcut_dir("04_none") is None


# ------------------------------------------------------------------ 적재 스크립트 · 공개 차단
def test_stage_real_fixes_headers():
    import stage_real
    spaced = "ADMI_CD , FORN_GB , M_10_CNT , ETL_YMD\n41271510,F,1.5,20250101\n".encode("utf-8-sig")
    df = stage_real.read_csv_bytes(spaced)
    assert list(df.columns) == ["ADMI_CD", "FORN_GB", "M_10_CNT", "ETL_YMD"]
    glued = "ETL_YMD SGG_CD,ADM_CD,POP\n20260114,41273,41273545,1.0\n".encode("utf-8")
    df = stage_real.read_csv_bytes(glued)
    assert list(df.columns) == ["ETL_YMD", "SGG_CD", "ADM_CD", "POP"]
    assert stage_real.date_range(df) == ("20260114", "20260114")


def test_stage_real_reads_polygon_shapefile(tmp_path):
    """다문화특구 경계 변환용 shp 파서 — 사각형 하나짜리 폴리곤 shp 를 직접 써서 읽어 본다."""
    import struct
    import stage_real
    ring = [(0.0, 0.0), (0.0, 10.0), (10.0, 10.0), (10.0, 0.0), (0.0, 0.0)]
    content = struct.pack("<i4dii", 5, 0, 0, 10, 10, 1, len(ring)) + struct.pack("<i", 0)
    content += b"".join(struct.pack("<2d", *p) for p in ring)
    rec = struct.pack(">ii", 1, len(content) // 2) + content
    header = struct.pack(">i", 9994) + b"\0" * 20 + struct.pack(">i", (100 + len(rec)) // 2)
    header += struct.pack("<ii4d4d", 1000, 5, 0, 0, 10, 10, 0, 0, 0, 0)
    shp = tmp_path / "a.shp"
    shp.write_bytes(header + rec)
    assert stage_real.read_shp_rings(shp) == [ring]


def test_real_data_never_shipped():
    import build_share
    assert "data/real" in build_share.FORBIDDEN and not any("real" in f for f in build_share.COPY_FILES)
    assert "zone_multicultural" in build_share.FORBIDDEN                  # 시 내부 산출물
    assert "road_names" in build_share.FORBIDDEN                          # 칸 거리 이름은 실데이터 판에만(결정 12)
    assert "data/real/" in (BASE / ".gitignore").read_text(encoding="utf-8-sig")
    out = subprocess.run([sys.executable, "-c", "import config"], cwd=SRC, capture_output=True, text=True,
                         encoding="utf-8", errors="replace",
                         env={**os.environ, "ANSAN_DATA": "bogus", "PYTHONIOENCODING": "utf-8"})
    assert out.returncode != 0                                           # 판 이름이 틀리면 켜지지 않는다


# ------------------------------------------------------------------ 실데이터 판 화면 (있을 때만)
REAL_SCRIPT = r"""
import sys, tempfile, pathlib
sys.path.insert(0, r"{src}")
import community as cm
db = pathlib.Path(tempfile.mkdtemp()) / "community.db"
cm.DB_PATH = db
cm.use_db(None)
cm.init_db()
from streamlit.testing.v1 import AppTest
at = AppTest.from_file(r"{app}", default_timeout=600)
at.run()
assert not at.exception, [e.message for e in at.exception]
print("console ok")
"""


@pytest.mark.skipif(not (config.REAL_DIR / "STAGED.json").exists(), reason="실데이터 미적재 (pipeline/stage_real.py)")
def test_real_mode_renders():
    script = REAL_SCRIPT.format(src=SRC, app=SRC / "app.py")
    out = subprocess.run([sys.executable, "-c", script], cwd=BASE, capture_output=True, text=True, timeout=1200,
                         encoding="utf-8", errors="replace",
                         env={**os.environ, "ANSAN_DATA": "real", "PYTHONIOENCODING": "utf-8"})
    assert out.returncode == 0, out.stderr[-2000:]
    assert out.stdout.count(" ok") == 1
