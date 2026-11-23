"""인벤토리 스키마(실제 컬럼명·코드값·파일명 패턴)를 따르는 가상 데이터 생성기.

    python src\\gen_synthetic.py

- 총량: 안산시 공표 통계(2안/data/processed)의 동별 외국인주민·구×국적 인원에 맞춘다.
- 동×국적 분배: 공표 통계에 없으므로 시나리오(AFFINITY)를 시드로 IPF 보정 → '가정'.
- 출력: data/synthetic/ — 앱은 같은 파일 이름 틀을 data/real(실데이터 판)에서도 읽는다.
- 인코딩: CP949 (실물 2026 파일은 UTF-8 — 앱이 판별해서 읽는다).

v0.3 (2026-11-18) — 실물 규격에 맞춤: 실제 21개국 범주, DS-076 · 077 은 PUBLIC 판 이름 · 해외(99999) 출발 없음,
DS-014(T22) 추가. 앱이 더 쓰지 않는 DS-028 · DS-042 · DS-061 은 만들지 않는다.
가상 시나리오(가정): 한국 공휴일에 근로자가 많은 국적이 원곡동 · 중앙동에 낮 동안 더 모이고, 시연 행사일에는 대상 국적이
행사 동에 더 모인다 — 배수는 임의값이며 실데이터에서 잰 값이 아니다.
"""
import calendar
import datetime as dt
import math

import numpy as np
import pandas as pd
import shapely

from config import (ANCHOR_DONG_CSV, ANCHOR_GU_NAT_CSV, ANCHOR_NAT_MAP, CARD_INDUSTRIES, CSV_ENCODING,
                    DONG_MASTER_CSV, DONGS, EVENTS, GRID_HOURS, IS_REAL, KOREAN_NT_CODE, KR_HOLIDAYS, LATEST_MONTH,
                    MONTHS, NAT_CODE, NAT_NAMES, SEED, SGG_NAMES, SYNTHETIC_CACHE_DIR, SYNTHETIC_DIR,
                    TELECOM_SAMPLE_RATE)
from geo import load_dong_features, utmk_to_wgs84, wgs84_to_utmk

RNG = np.random.default_rng(SEED)
DONG_CODES = np.array([d[0] for d in DONGS])
DONG_NAMES = [d[2] for d in DONGS]
SGG_CODES = np.array([c[:5] for c in DONG_CODES])
NAT_ARR = np.array(NAT_NAMES)
N_D, N_N = len(DONGS), len(NAT_NAMES)
D_IDX = {name: i for i, name in enumerate(DONG_NAMES)}
N_IDX = {name: i for i, name in enumerate(NAT_NAMES)}
RU_NATS = ["우즈베키스탄", "러시아", "카자흐스탄"]
# 고용허가제 송출국 중심(공개 정보) — 가상 '연휴 결집' 시나리오에 쓴다
WORKER_NATS = ["인도네시아", "네팔", "방글라데시", "스리랑카", "캄보디아", "미얀마", "파키스탄", "태국", "필리핀", "베트남"]

# 동×국적 분배 시나리오 (가정) — 값이 클수록 그 동에 더 몰려 산다
AFFINITY = {
    "원곡동": {"중국": 2.2, "베트남": 2.5, "인도네시아": 3.0, "네팔": 3.0, "방글라데시": 3.0,
             "파키스탄": 3.0, "스리랑카": 3.0, "캄보디아": 2.5, "미얀마": 2.5, "필리핀": 2.0,
             "태국": 2.0, "기타": 2.0},
    "선부2동": {n: 4.0 for n in RU_NATS},
    "선부1동": {n: 2.5 for n in RU_NATS},
    "선부3동": {n: 2.0 for n in RU_NATS},
    "백운동": {"중국": 1.6, "베트남": 1.5},
    "신길동": {"중국": 1.4, "네팔": 1.8, "캄보디아": 1.8, "베트남": 1.4},
    "초지동": {"네팔": 2.0, "캄보디아": 2.0, "인도네시아": 1.8, "방글라데시": 1.8, "베트남": 1.5},
    "사동": {"중국": 1.5, "몽골": 2.5, "베트남": 1.3, "미국": 1.6, "인도": 1.8, "일본": 1.4},
    "이동": {"중국": 1.3, "몽골": 2.0, "우즈베키스탄": 1.4},
    "고잔동": {"미국": 1.8, "일본": 1.8, "베트남": 1.6, "필리핀": 1.5},
    "중앙동": {"미국": 1.6, "일본": 1.6},
    "호수동": {"미국": 1.5, "일본": 1.5, "베트남": 1.3},
    "대부동": {"캄보디아": 2.5, "태국": 2.0, "베트남": 1.5},
    "본오1동": {"우즈베키스탄": 1.4, "카자흐스탄": 1.3},
    "반월동": {"네팔": 1.5, "캄보디아": 1.5, "미얀마": 1.5},
}


def _write(df: pd.DataFrame, name: str) -> int:
    df.to_csv(SYNTHETIC_DIR / name, index=False, encoding=CSV_ENCODING)
    return len(df)


def _month_days(month: str) -> int:
    return calendar.monthrange(int(month[:4]), int(month[4:]))[1]


def _shift_month(month: str, delta: int) -> str:
    y, m = int(month[:4]), int(month[4:]) + delta
    while m <= 0:
        y, m = y - 1, m + 12
    while m > 12:
        y, m = y + 1, m - 12
    return f"{y}{m:02d}"


# ------------------------------------------------------------------ 기준표
def build_dong_master() -> pd.DataFrame:
    info = {code: (geom, feat["properties"]) for code, _, geom, feat in load_dong_features()}
    rows = []
    for mois, sgis, name in DONGS:
        geom, props = info[mois]
        point = geom.representative_point()
        rows.append({"ADM_CD": mois, "SGIS_CD": sgis, "ADM_NM": name, "SGG_CD": mois[:5],
                     "GU": SGG_NAMES[mois[:5]].split()[-1], "LON": round(point.x, 6),
                     "LAT": round(point.y, 6), "MANUF_WORKERS": int(props.get("제조업종사자", 0))})
    master = pd.DataFrame(rows)
    master.to_csv(DONG_MASTER_CSV, index=False, encoding="utf-8-sig")
    return master


def calibrated_people() -> dict:
    """{월: [동25 × 국적21] 인원} — 공표 총량에 맞춘 IPF 결과 (분배는 가정)."""
    dong = pd.read_csv(ANCHOR_DONG_CSV)
    gunat = pd.read_csv(ANCHOR_GU_NAT_CSV)
    gunat["nat21"] = gunat["nat"].map(ANCHOR_NAT_MAP).fillna("기타")
    seed = np.ones((N_D, N_N))
    for dname, boosts in AFFINITY.items():
        for nat, k in boosts.items():
            seed[D_IDX[dname], N_IDX[nat]] *= k
    out = {}
    for month in MONTHS:
        ym = f"{month[:4]}-{month[4:]}"
        dong_tot = dong[dong["ym"] == ym].set_index("dong")["foreign_resident"]
        gu_nat = gunat[gunat["ym"] == ym].groupby(["gu", "nat21"])["total_all"].sum()
        matrix = np.zeros((N_D, N_N))
        for gu in ("상록구", "단원구"):
            rows = [i for i, c in enumerate(DONG_CODES) if SGG_NAMES[c[:5]].endswith(gu)]
            row_t = np.array([float(dong_tot.get(DONG_NAMES[i], 0.0)) for i in rows])
            col_t = np.array([float(gu_nat.get((gu, n), 0.0)) for n in NAT_NAMES])
            col_t *= row_t.sum() / max(col_t.sum(), 1.0)
            x = seed[rows] * (row_t / seed[rows].sum(axis=1))[:, None]
            for _ in range(80):
                cs = x.sum(axis=0)
                x *= np.divide(col_t, cs, out=np.ones_like(cs), where=cs > 0)[None, :]
                rs = x.sum(axis=1)
                x *= np.divide(row_t, rs, out=np.ones_like(rs), where=rs > 0)[:, None]
            matrix[rows] = x
        out[month] = matrix
    return out


# ------------------------------------------------------------------ 활동 모형
def _profile(weekend: bool) -> np.ndarray:
    """시간대별 (집, 일터, 여가) 비중 [24×3]."""
    prof = np.zeros((24, 3))
    for h in range(24):
        if not weekend:
            prof[h] = ((0.95, 0.03, 0.02) if h <= 5 else (0.70, 0.25, 0.05) if h <= 7 else
                       (0.25, 0.65, 0.10) if h <= 17 else (0.50, 0.20, 0.30) if h <= 19 else
                       (0.70, 0.05, 0.25) if h <= 22 else (0.90, 0.03, 0.07))
        else:
            prof[h] = ((0.93, 0.02, 0.05) if h <= 6 else (0.75, 0.10, 0.15) if h <= 9 else
                       (0.45, 0.15, 0.40) if h <= 12 else (0.35, 0.12, 0.53) if h <= 18 else
                       (0.55, 0.05, 0.40) if h <= 21 else (0.85, 0.02, 0.13))
    return prof


PROFILES = {False: _profile(False), True: _profile(True)}
PRESENCE = {False: 0.93, True: 0.86}


def attraction(sample_people: np.ndarray, master: pd.DataFrame):
    """(집, 일터, 여가) 유인 행렬 [3 × 동 × 국적], 국적별로 동 합이 1."""
    tot = sample_people.sum(axis=0)
    tot[tot == 0] = 1
    home = sample_people / tot
    work_w = master["MANUF_WORKERS"].to_numpy(float) + 300.0
    work = 0.6 * (work_w / work_w.sum())[:, None] + 0.4 * home
    hub = np.ones((N_D, N_N))
    hub[D_IDX["원곡동"]] *= 5.0
    hub[D_IDX["중앙동"]] *= 2.8
    hub[D_IDX["고잔동"]] *= 1.8
    hub[D_IDX["초지동"]] *= 1.3
    for nat in RU_NATS:
        hub[D_IDX["선부2동"], N_IDX[nat]] *= 4.0
        hub[D_IDX["원곡동"], N_IDX[nat]] *= 0.5
    hub[D_IDX["사동"], N_IDX["몽골"]] *= 2.0
    leisure = hub * (0.25 + home * 3)
    leisure /= leisure.sum(axis=0, keepdims=True)
    return np.stack([home, work, leisure])


# ------------------------------------------------------------------ DS-017
def _day_boost(ymd: str) -> np.ndarray:
    """가상 시나리오 배수 [24 × 동 × 국적] — 공휴일 근로자 결집 · 시연 행사일 대상 국적 결집 (임의값)."""
    boost = np.ones((24, N_D, N_N))
    if ymd in KR_HOLIDAYS:
        k = 3.0 if KR_HOLIDAYS[ymd].startswith("설") else 1.6
        for nat in WORKER_NATS:
            boost[10:22, D_IDX["원곡동"], N_IDX[nat]] *= k
            boost[10:22, D_IDX["중앙동"], N_IDX[nat]] *= 1 + (k - 1) / 3
    for ev in EVENTS:
        if ymd in ev["days"]:
            for nat in ev["target"]:
                boost[10:20, D_IDX[ev["dong"]], N_IDX[nat]] *= 2.5
    return boost


def gen_ds017(people: dict, master: pd.DataFrame) -> int:
    total = 0
    for month in MONTHS:
        y, m = int(month[:4]), int(month[4:])
        sample = people[month] * TELECOM_SAMPLE_RATE
        nat_total = sample.sum(axis=0)
        mats = attraction(sample, master)
        frames = []
        for day in range(1, _month_days(month) + 1):
            date = dt.date(y, m, day)
            weekend = date.weekday() >= 5
            prof = PROFILES[weekend]
            expected = np.einsum("hk,kdn->hdn", prof, mats) * nat_total[None, None, :] * PRESENCE[weekend]
            ymd = date.strftime("%Y%m%d")
            long_pop = (expected * _day_boost(ymd) * RNG.lognormal(0, 0.08, (1, N_D, N_N))
                        * RNG.lognormal(0, 0.05, (24, N_D, N_N)))
            short_pop = ((0.2 + prof[:, 2])[:, None, None] * mats[2][None, :, :]
                         * (nat_total * 0.03)[None, None, :] * RNG.lognormal(0, 0.15, (24, N_D, N_N)))
            for div, arr in ((1, long_pop), (2, short_pop)):
                h_idx, d_idx, n_idx = np.nonzero(arr >= 1.0)
                frames.append(pd.DataFrame({
                    "ETL_YMD": ymd, "SGG_CD": SGG_CODES[d_idx], "ADM_CD": DONG_CODES[d_idx],
                    "TIMEZN_CD": h_idx, "IN_FORN_DIV_NM": div, "CNTRY_NM": NAT_ARR[n_idx],
                    "POP": np.round(arr[h_idx, d_idx, n_idx], 2)}))
        total += _write(pd.concat(frames, ignore_index=True), f"T38_AMD_INFLOW_TIME_F_POP_{month}_4127.csv")
    return total


# ------------------------------------------------------------------ DS-056
NAT_SPEND_BOOST = {
    "우즈베키스탄": {"F01005": 3.0, "D01001": 2.5}, "러시아": {"F01005": 2.0, "D01001": 2.0},
    "카자흐스탄": {"F01005": 2.5, "D01001": 2.2}, "베트남": {"F01005": 2.5, "D01001": 2.0, "E02001": 1.8},
    "중국": {"F01002": 3.0, "D01001": 1.6, "E01001": 1.3},
    "네팔": {"D01001": 2.8, "F01005": 2.0, "E01001": 1.6}, "방글라데시": {"D01001": 2.8, "E01001": 1.6},
    "파키스탄": {"D01001": 2.8}, "인도네시아": {"D01001": 2.5, "F01005": 2.0}, "스리랑카": {"D01001": 2.2},
    "캄보디아": {"F01005": 2.0, "D01001": 2.0}, "미얀마": {"F01005": 1.8, "D01001": 2.0},
    "태국": {"F01005": 2.2}, "필리핀": {"F02001": 1.5, "D01001": 1.5}, "몽골": {"D01001": 1.8, "L01001": 1.5},
    "미국": {"F02001": 2.0, "F01001": 1.3, "D02001": 1.3}, "일본": {"F02001": 1.8, "F01001": 1.5},
    "인도": {"F01005": 2.0, "D01001": 2.0},
}
BASE_IND_W = {"F01001": 1.6, "F01002": 0.6, "F01005": 0.4, "F02001": 0.9, "D01001": 0.5, "D01002": 1.6,
              "D01004": 1.8, "D02001": 0.5, "D01003": 0.15, "E01001": 0.25, "E02001": 0.4,
              "H01001": 0.6, "H01002": 0.5, "L01001": 0.4}
ETHNIC_IND = {"F01005", "D01001", "F01002"}


def gen_ds056(people: dict, master: pd.DataFrame) -> int:
    dong = pd.read_csv(ANCHOR_DONG_CSV)
    codes = [c[0] for c in CARD_INDUSTRIES]
    tickets = np.array([c[4] for c in CARD_INDUSTRIES], dtype=float)
    meta = {c[0]: c[1:4] for c in CARD_INDUSTRIES}
    total = 0
    for month in MONTHS:
        mats = attraction(people[month] * TELECOM_SAMPLE_RATE, master)
        home, work, leisure = mats
        rows = []
        for n, nat in enumerate(NAT_NAMES):
            monthly_cnt = people[month][:, n].sum() * 0.9
            weights = np.array([BASE_IND_W[c] * NAT_SPEND_BOOST.get(nat, {}).get(c, 1.0) for c in codes])
            weights /= weights.sum()
            for i, code in enumerate(codes):
                loc = (0.3 * home[:, n] + 0.7 * leisure[:, n] if code in ETHNIC_IND
                       else 0.5 * home[:, n] + 0.25 * work[:, n] + 0.25 * leisure[:, n])
                cnt = RNG.poisson(monthly_cnt * weights[i] * loc)
                for d in np.nonzero(cnt >= 1)[0]:
                    amt = cnt[d] * tickets[i] * RNG.lognormal(0, 0.2)
                    rows.append((DONG_CODES[d], code, "03", NAT_CODE[nat], int(round(amt, -1)), int(cnt[d])))
        ym = f"{month[:4]}-{month[4:]}"
        kor = dong[dong["ym"] == ym].set_index("dong")["pop_kor"]
        base_w = np.array([BASE_IND_W[c] for c in codes])
        base_w /= base_w.sum()
        for d, dname in enumerate(DONG_NAMES):
            for gb, share in (("01", 0.55), ("02", 0.30), ("03", 0.15)):
                cnt = RNG.poisson(float(kor.get(dname, 0)) * 1.2 * share * base_w)
                for i in np.nonzero(cnt >= 1)[0]:
                    amt = cnt[i] * tickets[i] * RNG.lognormal(0, 0.2)
                    rows.append((DONG_CODES[d], codes[i], gb, KOREAN_NT_CODE, int(round(amt, -1)), int(cnt[i])))
        df = pd.DataFrame(rows, columns=["admi_cty_no", "card_tpbuz_cd", "gb", "nt", "amt", "cnt"])
        df.insert(0, "ta_ymd", f"{month}01")
        df.insert(1, "cty_rgn_no", df["admi_cty_no"].str[:5])
        df.insert(4, "card_tpbuz_nm_1", df["card_tpbuz_cd"].map(lambda c: meta[c][0]))
        df.insert(5, "card_tpbuz_nm_2", df["card_tpbuz_cd"].map(lambda c: meta[c][1]))
        df.insert(6, "card_tpbuz_nm_3", df["card_tpbuz_cd"].map(lambda c: meta[c][2]))
        total += _write(df, f"GGC_SALES_YM_AMD_{month}.csv")
    return total


# ------------------------------------------------------------------ DS-032 (관리자 격자)
AGE_BUCKETS = ["10", "15", "20", "25", "30", "35", "40", "45", "50", "55", "60", "65", "70"]
AGE_W = np.array([0.02, 0.03, 0.12, 0.16, 0.15, 0.13, 0.11, 0.09, 0.07, 0.05, 0.03, 0.02, 0.01, 0.01])
DS032_COLS = (["ADMI_CD", "CTY_NM", "ADMI_NM", "UTMK_X", "UTMK_Y", "TIME_CD", "FORN_GB", "S99"]
              + [f"M_{a}_CNT" for a in AGE_BUCKETS] + ["M_75_UP"]
              + [f"F_{a}_CNT" for a in AGE_BUCKETS] + ["F_75_UP"] + ["ETL_YMD"])


def _kernel(cell_x, cell_y, cell_dong, hotspots_per_dong, sigma):
    weight = np.full(len(cell_x), 0.02)
    for d in range(N_D):
        idx = np.nonzero(cell_dong == d)[0]
        if len(idx) == 0:
            continue
        picks = RNG.choice(idx, size=min(hotspots_per_dong, len(idx)), replace=False)
        local = np.zeros(len(idx))
        for p in picks:
            dist2 = (cell_x[idx] - cell_x[p]) ** 2 + (cell_y[idx] - cell_y[p]) ** 2
            local += RNG.uniform(0.5, 1.5) * np.exp(-dist2 / (2 * sigma ** 2))
        weight[idx] += local
        weight[idx] /= weight[idx].sum()
    return weight


def gen_ds032(people: dict, master: pd.DataFrame) -> int:
    feats = [(code, name, geom) for code, name, geom, _ in load_dong_features() if name != "대부동"]
    minx = min(g.bounds[0] for *_, g in feats)
    miny = min(g.bounds[1] for *_, g in feats)
    maxx = max(g.bounds[2] for *_, g in feats)
    maxy = max(g.bounds[3] for *_, g in feats)
    cx, cy = wgs84_to_utmk([minx, maxx, minx, maxx], [miny, miny, maxy, maxy])
    xs = np.arange(math.floor(cx.min() / 50) * 50 + 25, cx.max(), 50)
    ys = np.arange(math.floor(cy.min() / 50) * 50 + 25, cy.max(), 50)
    gx, gy = np.meshgrid(xs, ys)
    gx, gy = gx.ravel(), gy.ravel()
    lon, lat = utmk_to_wgs84(gx, gy)
    cell_dong = np.full(len(gx), -1)
    for code, name, geom in feats:
        inside = shapely.contains_xy(geom, lon, lat) & (cell_dong < 0)
        cell_dong[inside] = D_IDX[name]
    keep = cell_dong >= 0
    gx, gy, cell_dong = gx[keep], gy[keep], cell_dong[keep]
    k_home = _kernel(gx, gy, cell_dong, 4, 160.0)
    k_out = _kernel(gx, gy, cell_dong, 3, 220.0)

    sample = people[LATEST_MONTH] * TELECOM_SAMPLE_RATE
    mats = attraction(sample, master)
    nat_total = sample.sum(axis=0)
    top_nats = [NAT_NAMES[i] for i in np.argsort(-nat_total) if NAT_NAMES[i] != "기타"][:8]
    sex_age = np.concatenate([0.62 * AGE_W, 0.38 * AGE_W])
    frames = []
    # v0.4: 실물처럼 FORN_GB = 국적 이름, 시각 = 앱의 격자 시각(GRID_HOURS) — 앱은 평일/주말 하루 평균 집계본만 읽는다
    for ymd, weekend in (("20260610", False), ("20260613", True)):
        for hour in GRID_HOURS:
            prof = PROFILES[weekend][hour]
            dong_exp = np.einsum("k,kdn->dn", prof, mats) * nat_total[None, :] * PRESENCE[weekend]
            for nat in top_nats:
                n = N_IDX[nat]
                spread = prof[0] * k_home + (1 - prof[0]) * k_out
                value = dong_exp[cell_dong, n] * spread * RNG.lognormal(0, 0.15, len(gx))
                order = np.argsort(-value)[:1500]
                order = order[value[order] >= 0.2]
                split = value[order][:, None] * sex_age[None, :] * RNG.lognormal(0, 0.1, (len(order), 28))
                df = pd.DataFrame(np.round(split, 2), columns=DS032_COLS[8:36])
                d_codes = DONG_CODES[cell_dong[order]]
                df.insert(0, "ADMI_CD", d_codes)
                df.insert(1, "CTY_NM", [SGG_NAMES[c[:5]] for c in d_codes])
                df.insert(2, "ADMI_NM", [DONG_NAMES[i] for i in cell_dong[order]])
                df.insert(3, "UTMK_X", gx[order].astype(int))
                df.insert(4, "UTMK_Y", gy[order].astype(int))
                df.insert(5, "TIME_CD", hour)
                df.insert(6, "FORN_GB", nat)
                df.insert(7, "S99", np.round(value[order] * 0.04, 2))
                df["ETL_YMD"] = ymd
                frames.append(df)
    return _write(pd.concat(frames, ignore_index=True)[DS032_COLS], f"T1_GG_50CELL_FLOWPOP_{LATEST_MONTH}_4127.csv")


# ------------------------------------------------------------------ DS-076 / DS-077
# 실물 DS-076 · 077 출발 · 도착은 서울(11) · 인천(28) · 경기(41)뿐 — 해외 · 정보없음(99999)은 없다
REGIONS = [("11", "11530", 0.08), ("11", "11560", 0.06), ("41", "41390", 0.18), ("41", "41590", 0.11),
           ("41", "41111", 0.05), ("41", "41220", 0.05), ("28", "28200", 0.07), ("41", "41271", 0.20),
           ("41", "41273", 0.20)]
MIG_TAIL = (["AVG_INC_%d" % i for i in range(1, 11)] + ["AVG_CARD", "LOAN_CNT", "AVG_LOAN"]
            + ["CNT_%d" % i for i in range(1, 11)])


def _profile_cols(tot: int, for_cnt: int) -> dict:
    m_cnt = int(round(tot * RNG.uniform(0.5, 0.6)))
    brackets = RNG.multinomial(tot, [0.18, 0.2, 0.17, 0.12, 0.1, 0.08, 0.06, 0.04, 0.03, 0.02])
    cols = {"TOT_CNT": tot, "M_CNT": m_cnt, "FM_CNT": tot - m_cnt,
            "YES_INCOME": int(tot * 0.5), "SELF_ENT": int(tot * 0.1), "ETC_CNT": int(tot * 0.1),
            "FOR_CNT": for_cnt, "AVG_DIST": round(RNG.uniform(5, 14), 1), "HIGH_CNT": int(tot * 0.02),
            "AVG_INC": int(RNG.normal(2800, 300))}
    cols.update({f"AVG_INC_{i}": int(900 + 650 * i + RNG.normal(0, 60)) for i in range(1, 11)})
    cols.update({"AVG_CARD": int(RNG.normal(1200, 150)), "LOAN_CNT": int(tot * 0.4),
                 "AVG_LOAN": int(RNG.normal(52000, 6000))})
    cols.update({f"CNT_{i}": int(v) for i, v in enumerate(brackets, start=1)})
    return cols


def gen_ds076_077() -> tuple:
    """PUBLIC(K-10) 판 이름으로 낸다 — 앱은 PUBLIC 만 읽는다 (원본 · PUBLIC 을 같이 읽으면 이중 집계)."""
    dong = pd.read_csv(ANCHOR_DONG_CSV)
    totals = [0, 0]
    for month in MONTHS:
        ym = f"{month[:4]}-{month[4:]}"
        dm = dong[dong["ym"] == ym].set_index("dong")
        rows_in, rows_out = [], []
        for code, name in zip(DONG_CODES, DONG_NAMES):
            pop = float(dm.loc[name, "pop_total"])
            f_share = float(dm.loc[name, "foreign_resident"]) / pop
            for kind, rows in (("in", rows_in), ("out", rows_out)):
                movers = pop * 0.011 * RNG.lognormal(0, 0.1)
                for sido, sgg, w in REGIONS:
                    if sgg == code[:5] and RNG.random() < 0.5:
                        continue
                    tot = int(round(movers * w * RNG.lognormal(0, 0.2)))
                    for_cnt = int(round(tot * f_share * 0.45 * RNG.lognormal(0, 0.15)))
                    if tot < 1:
                        continue
                    key = {"BF_YR_MON": _shift_month(month, -12), "BF_SIDO": sido, "BF_SIGNGU": sgg,
                           "BS_YR_MON": month, "BS_SIGNGU": code[:5], "BS_HCD": code + "00"} if kind == "in" else \
                          {"BS_YR_MON": _shift_month(month, -12), "BS_SIGNGU": code[:5], "BS_HCD": code + "00",
                           "AF_YR_MON": month, "AF_SIDO": sido, "AF_SIGNGU": sgg}
                    key.update(_profile_cols(tot, min(for_cnt, tot)))
                    rows.append(key)
        totals[0] += _write(pd.DataFrame(rows_in), f"GYEONGGI_IN_STAT_PUBLIC_{month}.csv")
        totals[1] += _write(pd.DataFrame(rows_out), f"GYEONGGI_OUT_STAT_PUBLIC_{month}.csv")
    return tuple(totals)


# ------------------------------------------------------------------ DS-014 (동 유동인구 · 내외국인 · 성·연령)
DS014_AGES = [10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70]
DS014_COLS = (["ADMI_CD", "CTY_NM", "ADMI_NM", "TIME_CD", "FORN_GB"] + [f"M_{a}_CNT" for a in DS014_AGES]
              + [f"F_{a}_CNT" for a in DS014_AGES] + ["ETL_YMD"])
DS014_DAYS = 7      # 달마다 첫 7일만 낸다 (용량) — 앱은 하루 평균으로 쓰므로 결과 모양은 같다
FOREIGN_AGE_W = np.array([0.02, 0.03, 0.12, 0.17, 0.16, 0.13, 0.11, 0.09, 0.07, 0.05, 0.03, 0.01, 0.01])
KOREAN_AGE_W = np.array([0.06, 0.06, 0.07, 0.07, 0.07, 0.08, 0.09, 0.09, 0.09, 0.09, 0.08, 0.07, 0.08])


def gen_ds014(people: dict, master: pd.DataFrame) -> int:
    dong = pd.read_csv(ANCHOR_DONG_CSV)
    f_sexage = np.concatenate([0.61 * FOREIGN_AGE_W, 0.39 * FOREIGN_AGE_W])
    f_sexage /= f_sexage.sum()
    k_sexage = np.concatenate([0.5 * KOREAN_AGE_W, 0.5 * KOREAN_AGE_W])
    k_sexage /= k_sexage.sum()
    work_w = master["MANUF_WORKERS"].to_numpy(float) + 300.0
    work_w /= work_w.sum()
    total = 0
    for month in MONTHS:
        y, m = int(month[:4]), int(month[4:])
        sample = people[month] * TELECOM_SAMPLE_RATE
        nat_total = sample.sum(axis=0)
        mats = attraction(sample, master)
        ym = f"{month[:4]}-{month[4:]}"
        kor = dong[dong["ym"] == ym].set_index("dong")["pop_kor"].reindex(DONG_NAMES).fillna(0).to_numpy(float)
        kor_home = kor * TELECOM_SAMPLE_RATE
        frames = []
        for day in range(1, DS014_DAYS + 1):
            date = dt.date(y, m, day)
            weekend = date.weekday() >= 5
            prof = PROFILES[weekend]
            ymd = date.strftime("%Y%m%d")
            foreign = (np.einsum("hk,kdn->hdn", prof, mats) * nat_total[None, None, :] * _day_boost(ymd)).sum(axis=2)
            korean = (prof[:, :1] * kor_home[None, :] + prof[:, 1:2] * kor_home.sum() * work_w[None, :]
                      + prof[:, 2:3] * kor_home[None, :])
            for gb, arr, w in (("F", foreign, f_sexage), ("N", korean, k_sexage)):
                vals = arr[:, :, None] * w[None, None, :] * RNG.lognormal(0, 0.08, (24, N_D, 26))
                h_idx, d_idx = np.meshgrid(np.arange(24), np.arange(N_D), indexing="ij")
                df = pd.DataFrame(np.round(vals.reshape(-1, 26), 2), columns=DS014_COLS[5:31])
                codes = DONG_CODES[d_idx.ravel()]
                df.insert(0, "ADMI_CD", codes)
                df.insert(1, "CTY_NM", [SGG_NAMES[c[:5]] for c in codes])
                df.insert(2, "ADMI_NM", [DONG_NAMES[i] for i in d_idx.ravel()])
                df.insert(3, "TIME_CD", [f"{h:02d}" for h in h_idx.ravel()])
                df.insert(4, "FORN_GB", gb)
                df["ETL_YMD"] = ymd
                frames.append(df)
        total += _write(pd.concat(frames, ignore_index=True)[DS014_COLS], f"T22_GG_ADMI_FLOWPOP_{month}_4127.csv")
    return total


# ------------------------------------------------------------------ main
def main() -> None:
    if IS_REAL:
        raise SystemExit("ANSAN_DATA=real 로는 가상 데이터를 만들지 않습니다 — 환경변수를 지우고 실행하세요")
    SYNTHETIC_DIR.mkdir(parents=True, exist_ok=True)
    SYNTHETIC_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    for old in list(SYNTHETIC_DIR.glob("*.csv")) + list(SYNTHETIC_CACHE_DIR.glob("*.csv")):
        old.unlink()
    master = build_dong_master()
    people = calibrated_people()
    manifest = [
        ("DS-017", "AMD_INFLOW_TIME_F_POP", "T38_AMD_INFLOW_TIME_F_POP_YYYYMM_4127.csv", gen_ds017(people, master)),
        ("DS-014", "GG_ADMI_FLOWPOP", "T22_GG_ADMI_FLOWPOP_YYYYMM_4127.csv", gen_ds014(people, master)),
        ("DS-056", "GGC_SALES_YM_AMD", "GGC_SALES_YM_AMD_YYYYMM.csv", gen_ds056(people, master)),
        ("DS-032", "GG_50CELL_FLOWPOP", f"T1_GG_50CELL_FLOWPOP_{LATEST_MONTH}_4127.csv", gen_ds032(people, master)),
    ]
    n_in, n_out = gen_ds076_077()
    manifest += [("DS-076", "GYEONGGI_IN_STAT_PUBLIC", "GYEONGGI_IN_STAT_PUBLIC_YYYYMM.csv", n_in),
                 ("DS-077", "GYEONGGI_OUT_STAT_PUBLIC", "GYEONGGI_OUT_STAT_PUBLIC_YYYYMM.csv", n_out)]
    out = pd.DataFrame(manifest, columns=["인벤ID", "테이블명", "파일 패턴", "행수"])
    out["비고"] = "가상 데이터 (seed=%d)" % SEED
    out.to_csv(SYNTHETIC_DIR / "MANIFEST.txt", index=False, encoding="utf-8-sig", sep="\t")
    print(out.to_string(index=False))
    import metrics  # 공유판 · 드라이브 앱은 원본 대신 집계 캐시만 담는다 → 여기서 미리 만든다
    metrics.ds017_profile(), metrics.ds017_daily(), metrics.ds014_month(), metrics.ds032_grid()
    print("캐시:", ", ".join(p.name for p in sorted(SYNTHETIC_CACHE_DIR.glob("*.csv"))))


if __name__ == "__main__":
    main()
