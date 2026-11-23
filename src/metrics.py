"""인벤토리 데이터셋(가상 또는 실데이터)을 화면용 지표로 집계한다.

원칙 (매뉴얼 · README):
- 통신·카드는 표본 추정치 → 비중·순위·증감률로만 보여준다. 절대값은 마스킹 판정에만 쓴다.
- 대민개방 X 데이터(DS-056·032·014 원값)는 시민 화면에 금액·원값을 노출하지 않는다.
Streamlit에 의존하지 않으므로 테스트에서 그대로 불러 쓸 수 있다.

데이터 판 (config.DATA_MODE)
- synthetic: data/synthetic (gen_synthetic.py) · real: data/real (pipeline/stage_real.py, 내부 검토용).
- 캐시(_cache)는 판마다 따로 둔다. 원본이 없고 캐시만 있으면(공유판) 캐시를 그대로 쓴다.

v0.3 (2026-11-18, 실데이터 대조 반영 — 프로젝트 루트 data/2안_실데이터_대조.md, 비공개)
- 사는 곳: DS-028 '20박 이상' → DS-017 장기 외국인의 평일 새벽 평균 위치 (기본값 D10)
- 카드(DS-056): 국적별 → 외국인 전체(gb=03 · nt≠000)만, 관리자 화면 (기본값 D11)
- 행사 효과: DS-042 · 061(미납품) → DS-017 동 단위 일별 (기본값 D13)
- 새로 온 이웃(시민): DS-076 → 공표 외국인주민 통계 전월 대비 (기본값 D14). DS-076 · 077 은 PUBLIC 판 · 관리자 화면만
- DS-014 외국인 유동 추이 · 성·연령 구조 (사용자 결정 7)
"""
import json
from functools import lru_cache

import numpy as np
import pandas as pd

from config import (ANCHOR_DONG_CSV, CACHE_DIR, CSV_ENCODING, DONG_CODE, DONG_NAME, DONGS, EVENTS,
                    HOLIDAY_BASE_MIN, HOME_FESTIVALS, IS_REAL, K_ANON_MIN, KOREAN_NT_CODE, KR_HOLIDAYS,
                    LATEST_MONTH, MASK_MIN_POP, RESIDENT_CALIBRATE, RESIDENT_DAYTYPE, RESIDENT_HOURS,
                    SOURCE_DIR)
from geo import utmk_to_wgs84

ALL_DONGS = [code for code, _, _ in DONGS]
ANSAN_SGG = {"41271", "41273"}
SEX_AGE = [(s, a) for s in ("M", "F") for a in (10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70)]
SEX_AGE_COLS = [f"{s}_{a}_CNT" for s, a in SEX_AGE]


def _hint() -> str:
    return "python pipeline\\stage_real.py" if IS_REAL else "python src\\gen_synthetic.py"


def _read_csv(path, dtype=None) -> pd.DataFrame:
    """실물 2026 파일은 UTF-8, 가상은 CP949 → 판별. 헤더 공백(실물 함정)은 지운다."""
    for enc in ("utf-8-sig", CSV_ENCODING):
        try:
            df = pd.read_csv(path, encoding=enc, dtype=dtype, low_memory=False)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise ValueError(f"인코딩 판별 실패: {path}")
    df.columns = [str(c).strip() for c in df.columns]
    return df


def _files(pattern: str) -> list:
    return sorted(SOURCE_DIR.glob(pattern))


def _read(pattern: str, dtype: dict) -> pd.DataFrame:
    files = _files(pattern)
    if not files:
        raise FileNotFoundError(f"{SOURCE_DIR / pattern} — 먼저 {_hint()} 실행")
    return pd.concat([_read_csv(f, dtype) for f in files], ignore_index=True)


def _cache_fresh(cache, raw_files) -> bool:
    """공유판에는 원본 대신 집계 캐시만 담는다 → 원본이 없으면 캐시를 그대로 쓴다."""
    return cache.exists() and (not raw_files or cache.stat().st_mtime > max(f.stat().st_mtime for f in raw_files))


def _with_all_dongs(series: pd.Series) -> pd.DataFrame:
    df = series.reindex(ALL_DONGS, fill_value=0.0).rename("value").reset_index()
    df.columns = ["ADM_CD", "value"]
    df["ADM_NM"] = df["ADM_CD"].map(DONG_NAME)
    return df


def _share(df: pd.DataFrame, mask_min: float) -> pd.DataFrame:
    total = df["value"].sum()
    df["share"] = df["value"] / total if total > 0 else 0.0
    df["masked"] = df["value"] < mask_min
    return df


def _ymd(series: pd.Series) -> pd.Series:
    return pd.to_datetime(pd.to_numeric(series, errors="coerce").astype("Int64").astype(str), format="%Y%m%d",
                          errors="coerce")


# ------------------------------------------------------------------ DS-017 (모이는 곳 · 사는 곳 · 연휴 · 행사)
T38 = "T38_AMD_INFLOW_TIME_F_POP_*_4127.csv"


def _build_ds017_caches():
    """원본 한 번 읽어 두 캐시를 만든다: 월 × 평일/주말 × 동 × 시간대 일평균(profile), 날짜 × 동 하루 합(daily)."""
    raw = _read(T38, {"ETL_YMD": str, "SGG_CD": str, "ADM_CD": str})
    raw["date"] = _ymd(raw["ETL_YMD"])
    raw = raw[raw["date"].notna()]
    raw["month"] = raw["date"].dt.strftime("%Y%m")
    raw["daytype"] = np.where(raw["date"].dt.weekday >= 5, "주말", "평일")
    ndays = raw.groupby(["month", "daytype"])["date"].nunique().rename("ndays").reset_index()
    prof = raw.groupby(["month", "daytype", "ADM_CD", "TIMEZN_CD", "IN_FORN_DIV_NM", "CNTRY_NM"],
                       as_index=False)["POP"].sum().merge(ndays, on=["month", "daytype"])
    prof["POP"] = (prof["POP"] / prof["ndays"]).round(3)
    prof = prof.drop(columns="ndays")
    daily = raw.groupby(["date", "ADM_CD", "IN_FORN_DIV_NM", "CNTRY_NM"], as_index=False)["POP"].sum()
    daily["date"] = daily["date"].dt.strftime("%Y%m%d")
    daily["POP"] = daily["POP"].round(2)
    # 한국 연휴(KR_HOLIDAYS) 날의 시간대별 값 — 시민 앱 '연휴' 보기(2026-11-20)
    raw["ymd"] = raw["date"].dt.strftime("%Y%m%d")
    hol = raw[raw["ymd"].isin(list(KR_HOLIDAYS))]
    hol = (hol.groupby(["ymd", "ADM_CD", "TIMEZN_CD", "IN_FORN_DIV_NM", "CNTRY_NM"], as_index=False)["POP"].sum()
           .rename(columns={"ymd": "date"}))
    hol["POP"] = hol["POP"].round(3)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    prof.to_csv(CACHE_DIR / "ds017_profile.csv", index=False, encoding="utf-8-sig")
    daily.to_csv(CACHE_DIR / "ds017_daily.csv", index=False, encoding="utf-8-sig")
    hol.to_csv(CACHE_DIR / "ds017_holiday.csv", index=False, encoding="utf-8-sig")


def _ds017_cache(name: str) -> pd.DataFrame:
    cache = CACHE_DIR / name
    if not _cache_fresh(cache, _files(T38)):
        _build_ds017_caches()
    return pd.read_csv(cache, dtype={"month": str, "ADM_CD": str, "date": str})


@lru_cache(maxsize=1)
def ds017_profile() -> pd.DataFrame:
    """월 × 평일/주말 × 동 × 시간대 × 장단기 × 국적 일평균 POP."""
    return _ds017_cache("ds017_profile.csv")


@lru_cache(maxsize=1)
def ds017_daily() -> pd.DataFrame:
    """날짜 × 동 × 장단기 × 국적 하루 POP 합 (시간대 합 = 연인원 성격 — 비율로만 쓴다)."""
    df = _ds017_cache("ds017_daily.csv")
    df["ts"] = pd.to_datetime(df["date"], format="%Y%m%d")
    return df


@lru_cache(maxsize=1)
def ds017_holiday() -> pd.DataFrame:
    """한국 연휴 날짜 × 동 × 시간대 × 장단기 × 국적 POP (시민 앱 '연휴' 보기)."""
    return _ds017_cache("ds017_holiday.csv")


def presence_holidays() -> list:
    """'연휴' 보기에 모은 날짜(자료에 있는 것만) — [{'date': 'YYYYMMDD', 'name': '설날'}, …]."""
    days = sorted(set(ds017_holiday()["date"].astype(str)) & set(KR_HOLIDAYS))
    return [{"date": d, "name": KR_HOLIDAYS[d]} for d in days]


def months() -> list:
    return sorted(ds017_profile()["month"].unique())


def gathering(nat: str, daytype: str, hours, month: str = LATEST_MONTH, div: int = 1) -> pd.DataFrame:
    """해당 시간대 평균 POP의 동별 비중 (국적 안에서)."""
    prof = ds017_profile()
    sub = prof[(prof["month"] == month) & (prof["daytype"] == daytype) & (prof["CNTRY_NM"] == nat)
               & (prof["TIMEZN_CD"].isin(list(hours))) & (prof["IN_FORN_DIV_NM"] == div)]
    series = sub.groupby("ADM_CD")["POP"].sum() / max(len(list(hours)), 1)
    return _share(_with_all_dongs(series), MASK_MIN_POP)


def gathering_hourly(nats: list, daytype: str = "주말", month: str = LATEST_MONTH) -> pd.DataFrame:
    """대상 국적들의 (동 × 시간대) 점수 — 국적마다 비중으로 바꾼 뒤 평균 (큰 국적 쏠림 방지)."""
    prof = ds017_profile()
    sub = prof[(prof["month"] == month) & (prof["daytype"] == daytype) & prof["CNTRY_NM"].isin(nats)
               & (prof["IN_FORN_DIV_NM"] == 1)].copy()
    sub["share"] = sub["POP"] / sub.groupby(["CNTRY_NM", "TIMEZN_CD"])["POP"].transform("sum")
    score = sub.groupby(["ADM_CD", "TIMEZN_CD"], as_index=False)["share"].sum()
    score["share"] /= max(len(nats), 1)
    score["ADM_NM"] = score["ADM_CD"].map(DONG_NAME)
    return score


def event_recommend(nats: list, top: int = 5, hours=range(10, 22)) -> pd.DataFrame:
    """행사 기획 추천: 주말 10~21시 중 대상 국적이 가장 많이 모이는 동 — 동마다 가장 좋은 시작 시각 하나.

    (동, 시각) 쌍을 그대로 순위 매기면 한 동이 시각만 바꿔 상위를 다 차지한다(브라우저 점검 2026-11-16:
    우즈벡·카자흐·러시아 → 1~5위가 전부 선부2동). 그래서 동 중복을 뺀다. 점수 계산은 그대로.
    """
    score = gathering_hourly(nats)
    score = score[score["TIMEZN_CD"].isin(list(hours))]
    best = score.sort_values("share", ascending=False).drop_duplicates("ADM_CD")
    return best.head(top).reset_index(drop=True)


# ------------------------------------------------------------------ 사는 곳 (DS-017 장기 · 평일 새벽)
def _public_dong_total(month: str):
    """공표 동별 외국인주민(등록외국인 + 거소신고 동포) — 그 달이 없으면 None."""
    pub = anchor_dong()
    sub = pub[pub["month"] == month]
    return sub.set_index("ADM_CD")["foreign_resident"].astype(float) if len(sub) else None


def residence(month: str = LATEST_MONTH, calibrate: bool = None) -> pd.DataFrame:
    """거주 근사: 장기(1) 외국인의 평일 새벽(RESIDENT_HOURS) 시간당 평균 POP — 밤에 머무는 곳 = 사는 곳.

    RAW = 통신 원값(평균), POP = 보정값. 보정(RESIDENT_CALIBRATE, v0.4 사용자 결정): 동마다 국적 구성은 통신 그대로 두고
    동 총량을 공표 동별 외국인주민 수에 맞춘다 → 산단 기숙사 · 야간 근무로 밤 인구가 부푼 동(초지동 등)을 줄인다.
    한계: 공표 통계(주민등록 · 거소신고)와 통신(휴대폰 가입 국적)의 '외국인' 정의가 다르다.
    DS-028(연속숙박 20박 이상)은 실물에서 거주 판정이 성립하지 않아 쓰지 않는다 (기본값 D10).
    """
    prof = ds017_profile()
    sub = prof[(prof["month"] == month) & (prof["daytype"] == RESIDENT_DAYTYPE) & (prof["IN_FORN_DIV_NM"] == 1)
               & prof["TIMEZN_CD"].isin(RESIDENT_HOURS)]
    out = sub.groupby(["ADM_CD", "CNTRY_NM"], as_index=False)["POP"].sum()
    out["RAW"] = out["POP"] / len(RESIDENT_HOURS)
    out["POP"] = out["RAW"]
    pub = _public_dong_total(month) if (RESIDENT_CALIBRATE if calibrate is None else calibrate) else None
    if pub is not None:
        tot = out.groupby("ADM_CD")["RAW"].transform("sum")
        k = out["ADM_CD"].map(pub) / tot.where(tot > 0)
        out["POP"] = np.where(k.notna(), out["RAW"] * k, out["RAW"])
    return out[["ADM_CD", "CNTRY_NM", "POP", "RAW"]]


def residence_by_dong(nat: str, month: str = LATEST_MONTH) -> pd.DataFrame:
    """비중은 보정값(POP)으로, '소수' 가림은 통신 원값(RAW)으로 — 보정이 작은 칸을 키워 드러내지 않게(보수적)."""
    res = residence(month)
    sub = res[res["CNTRY_NM"] == nat].set_index("ADM_CD")
    df = _share(_with_all_dongs(sub["POP"]), MASK_MIN_POP)
    df["masked"] = sub["RAW"].reindex(df["ADM_CD"]).fillna(0).to_numpy() < MASK_MIN_POP
    return df


def living_area_top(nat: str, n: int = 3, month: str = LATEST_MONTH) -> pd.DataFrame:
    df = residence_by_dong(nat, month)
    return df[~df["masked"]].sort_values("share", ascending=False).head(n)


def residence_coverage(nat: str, dongs, month: str = LATEST_MONTH) -> float:
    """고른 동들이 이 국적 거주자의 몇 %를 담는지 — 한 분포의 부분합.

    소수(마스킹)인 동은 빼고 센다 → 마스킹된 값이 비율로 새어 나가지 않는다 (그래서 실제보다 작거나 같다).
    """
    df = residence_by_dong(nat, month)
    vis = df[~df["masked"]]
    return float(vis.loc[vis["ADM_CD"].isin(list(dongs)), "share"].sum())


def residence_trend(nats: list) -> pd.DataFrame:
    """월 × 동 × 국적 거주 근사 (ETL_YM 칸 이름은 화면 코드와 맞춤) — 달끼리 원값 비교 금지(산출 구간 경계)."""
    frames = [residence(m).assign(ETL_YM=m) for m in months()]
    df = pd.concat(frames, ignore_index=True)
    return df[df["CNTRY_NM"].isin(nats)][["ETL_YM", "ADM_CD", "CNTRY_NM", "POP"]]


def nationality_mix(nats: list) -> pd.DataFrame:
    """월마다 '사는 곳'(장기 · 평일 새벽) 외국인 중 국적 비중 — 달 안의 비율이라 산출 구간이 바뀌어도 비교할 수 있다."""
    frames = [residence(m).assign(ETL_YM=m) for m in months()]
    df = pd.concat(frames, ignore_index=True)
    df["share"] = df["POP"] / df.groupby("ETL_YM")["POP"].transform("sum")
    out = df.groupby(["ETL_YM", "CNTRY_NM"], as_index=False)["share"].sum()
    return out[out["CNTRY_NM"].isin(nats)]


# ------------------------------------------------------------------ 산출 구간 경계 (실물 함정)
def _breaks(daily_total: pd.Series) -> list:
    """월별 하루 합 중앙값이 앞달의 2배 이상 · 절반 이하로 바뀌면 그 달 1일(YYYYMMDD)을 경계로 본다.
    실물 DS-017 은 2026-04 부터 수준이 크게 바뀐다(같은 때 행 수 · 헤더 형식도 바뀜 — 납품 산출 변경 추정)."""
    by_m = daily_total.groupby(daily_total.index.str[:6]).median()
    out = []
    for prev, cur in zip(by_m.index[:-1], by_m.index[1:]):
        if by_m[prev] > 0 and not (0.5 < by_m[cur] / by_m[prev] < 2.0):
            out.append(cur + "01")
    return out


@lru_cache(maxsize=1)
def ds017_breaks() -> list:
    d = ds017_daily()
    return _breaks(d[d["IN_FORN_DIV_NM"] == 1].groupby("date")["POP"].sum())


def _same_regime(a: str, b: str, breaks) -> bool:
    return sum(a >= x for x in breaks) == sum(b >= x for x in breaks)


# ------------------------------------------------------------------ 연휴 · 명절 효과 (관리자 전용)
SPECIAL_DAYS = {**{d: ("한국 연휴", n) for d, n in KR_HOLIDAYS.items()},
                **{d: ("모국 명절", n) for d, n in HOME_FESTIVALS.items()}}


def _baseline_median(table: pd.DataFrame, day: str, breaks=()) -> pd.Series:
    """같은 요일 · 앞뒤 4주 · 연휴/명절이 아닌 날 · 같은 산출 구간의 중앙값 (table 의 index = 'YYYYMMDD')."""
    t = pd.Timestamp(day)
    keep = []
    for s in table.index:
        u = pd.Timestamp(s)
        keep.append(u.weekday() == t.weekday() and s != day and abs((u - t).days) <= 28
                    and s not in SPECIAL_DAYS and _same_regime(s, day, breaks))
    return table[keep].median()


def holiday_effect(div: int = 1) -> pd.DataFrame:
    """날짜(연휴 · 명절) × 국적: 안산 전체 하루 POP ÷ 같은 요일 ±4주 중앙값. 기준이 작으면 NaN(소수)."""
    daily = ds017_daily()
    table = daily[daily["IN_FORN_DIV_NM"] == div].groupby(["date", "CNTRY_NM"])["POP"].sum().unstack(fill_value=0)
    breaks = ds017_breaks()
    rows = []
    for d, (kind, label) in SPECIAL_DAYS.items():
        if d not in table.index:
            continue
        base = _baseline_median(table, d, breaks)
        ratio = table.loc[d] / base.where(base >= HOLIDAY_BASE_MIN)
        for nat, r in ratio.items():
            rows.append({"date": d, "구분": kind, "이름": label, "CNTRY_NM": nat, "배수": r})
    return pd.DataFrame(rows, columns=["date", "구분", "이름", "CNTRY_NM", "배수"])


def holiday_top_dongs(day: str, nats: list, n: int = 3, div: int = 1) -> pd.DataFrame:
    """그날 대상 국적이 평소(같은 요일 ±4주 중앙값)보다 많이 늘어난 동 — 증가분 비중(%)."""
    daily = ds017_daily()
    sub = daily[(daily["IN_FORN_DIV_NM"] == div) & daily["CNTRY_NM"].isin(nats)]
    table = sub.groupby(["date", "ADM_CD"])["POP"].sum().unstack(fill_value=0)
    if day not in table.index:
        return pd.DataFrame(columns=["ADM_CD", "ADM_NM", "증가분 비중"])
    inc = (table.loc[day] - _baseline_median(table, day, ds017_breaks())).clip(lower=0)
    if inc.sum() <= 0:
        return pd.DataFrame(columns=["ADM_CD", "ADM_NM", "증가분 비중"])
    out = (inc / inc.sum()).sort_values(ascending=False).head(n).rename("증가분 비중").reset_index()
    out.columns = ["ADM_CD", "증가분 비중"]
    out["ADM_NM"] = out["ADM_CD"].map(DONG_NAME)
    return out[["ADM_CD", "ADM_NM", "증가분 비중"]]


# ------------------------------------------------------------------ 행사 효과 (동 단위 — DS-017 · DS-056)
def _baseline_days(days: list, breaks=()) -> list:
    """행사일마다 1 · 2주 전 같은 요일 (행사일 · 연휴 · 다른 산출 구간은 뺀다)."""
    special = set(days) | set(SPECIAL_DAYS)
    out = []
    for d in days:
        t = pd.Timestamp(d)
        for k in (7, 14):
            b = (t - pd.Timedelta(days=k)).strftime("%Y%m%d")
            if b not in special and b not in out and _same_regime(b, d, breaks):
                out.append(b)
    return out


def event_effect(dong: str, days: list, targets=(), div: int = None) -> pd.DataFrame:
    """국적별 행사일 평균 ÷ 기준일 평균 − 1 (동 하나). 기준일 평균이 MASK_MIN_POP 미만이면 증가율 비표시."""
    daily = ds017_daily()
    sub = daily[daily["ADM_CD"] == dong]
    if div:
        sub = sub[sub["IN_FORN_DIV_NM"] == div]
    table = sub.groupby(["date", "CNTRY_NM"])["POP"].sum().unstack(fill_value=0)
    base_days = [d for d in _baseline_days(days, ds017_breaks()) if d in table.index]
    on_days = [d for d in days if d in table.index]
    cols = ["국적", "기준일", "행사일", "증가율(%)", "대상 국적"]
    if not base_days or not on_days:
        return pd.DataFrame(columns=cols)
    on, off = table.loc[on_days].mean(), table.loc[base_days].mean()
    out = pd.DataFrame({"국적": on.index, "기준일": off.values, "행사일": on.values})
    out["증가율(%)"] = np.where(out["기준일"] >= MASK_MIN_POP, (out["행사일"] / out["기준일"] - 1) * 100, np.nan)
    out["증가율(%)"] = out["증가율(%)"].round(0)
    out["대상 국적"] = out["국적"].isin(list(targets))
    return out[cols]


def event_total_uplift(dong: str, days: list, targets=()) -> float:
    eff = event_effect(dong, days, targets)
    if eff.empty:
        return float("nan")
    sel = eff[eff["대상 국적"]] if targets and eff["대상 국적"].any() else eff
    base, on = sel["기준일"].sum(), sel["행사일"].sum()
    return float((on / base - 1) * 100) if base > 0 else float("nan")


def event_daily(dong: str, days: list, pad: int = 14) -> pd.DataFrame:
    """행사 앞뒤 하루 외국인 POP 합 (장기 · 단기) — 추이 차트용."""
    daily = ds017_daily()
    t0, t1 = pd.Timestamp(min(days)) - pd.Timedelta(days=pad), pd.Timestamp(max(days)) + pd.Timedelta(days=3)
    sub = daily[(daily["ADM_CD"] == dong) & daily["ts"].between(t0, t1)].copy()
    sub["구분"] = np.where(sub["IN_FORN_DIV_NM"] == 1, "장기 체류", "단기 체류")
    out = sub.groupby(["ts", "구분"], as_index=False)["POP"].sum()
    out["행사일"] = out["ts"].dt.strftime("%Y%m%d").isin(days)
    return out


def preset_event(area_cd: str) -> dict:
    """가상 판 시연 행사 → (동코드, 날짜, 대상) — 실데이터 판에는 시의 실제 행사 기록이 없다."""
    ev = next(e for e in EVENTS if e["area_cd"] == area_cd)
    return {"name": ev["name"], "dong": DONG_CODE[ev["dong"]], "days": ev["days"], "target": ev["target"]}


# ------------------------------------------------------------------ DS-056 외국인 결제 (관리자 전용, 비중 · 증가율만)
@lru_cache(maxsize=1)
def ds056_foreign() -> pd.DataFrame:
    """외국인 행만 (gb=03 외지인 · nt≠000). 규격서 v6: gb 01 내지인 / 02 인접지인 / 03 외지인 — 외국인은 모두 03.
    실데이터 판은 적재 때 이미 외국인 행만 옮긴다(최소 수집). 국적(nt)은 쓰지 않는다 — 실물 코드표 없음."""
    df = _read("GGC_SALES_YM_AMD_*.csv", {"ta_ymd": str, "cty_rgn_no": str, "admi_cty_no": str,
                                           "card_tpbuz_cd": str, "gb": str, "nt": str})
    df = df[(df["gb"] == "03") & (df["nt"] != KOREAN_NT_CODE)].copy()
    df["cnt"] = pd.to_numeric(df["cnt"], errors="coerce").fillna(0)
    return df


def foreign_spending_by_dong(month: str = LATEST_MONTH) -> pd.DataFrame:
    df = ds056_foreign()
    series = df[df["ta_ymd"].str[:6] == month].groupby("admi_cty_no")["cnt"].sum().astype(float)
    return _share(_with_all_dongs(series), K_ANON_MIN)


def foreign_spending_rank(month: str = LATEST_MONTH, dong: str = None) -> pd.DataFrame:
    """업종 대분류별 외국인 결제건수 비중 (금액 비표시)."""
    df = ds056_foreign()
    sub = df[df["ta_ymd"].str[:6] == month]
    if dong:
        sub = sub[sub["admi_cty_no"] == dong]
    out = sub.groupby("card_tpbuz_nm_1", as_index=False)["cnt"].sum()
    if out.empty or out["cnt"].sum() <= 0:
        return pd.DataFrame(columns=["순위", "업종", "결제건수 비중"])
    out["share"] = out["cnt"] / out["cnt"].sum()
    out = out.sort_values("share", ascending=False).reset_index(drop=True)
    out["순위"] = np.arange(1, len(out) + 1)
    out["업종"] = out["card_tpbuz_nm_1"]
    out["결제건수 비중"] = (out["share"] * 100).round(1)
    return out[["순위", "업종", "결제건수 비중"]]


def card_is_daily() -> bool:
    """실물 DS-056 은 일별(ta_ymd), 가상은 월별(YYYYMM01)."""
    return ds056_foreign()["ta_ymd"].nunique() > ds056_foreign()["ta_ymd"].str[:6].nunique()


@lru_cache(maxsize=1)
def card_breaks() -> list:
    return _breaks(ds056_foreign().groupby("ta_ymd")["cnt"].sum()) if card_is_daily() else []


def event_sales_effect(dong: str, days: list) -> pd.DataFrame:
    """업종 대분류별 외국인 결제건수 증가율 — 일별 자료(실물)일 때만. 기준일 건수 K-10 미만은 비표시."""
    cols = ["업종", "기준일 건수 평균", "행사일 건수 평균", "결제건수 증가율(%)"]
    if not card_is_daily():
        return pd.DataFrame(columns=cols)
    df = ds056_foreign()
    sub = df[df["admi_cty_no"] == dong]
    table = sub.groupby(["ta_ymd", "card_tpbuz_nm_1"])["cnt"].sum().unstack(fill_value=0)
    base_days = [d for d in _baseline_days(days, card_breaks()) if d in table.index]
    on_days = [d for d in days if d in table.index]
    if not base_days or not on_days:
        return pd.DataFrame(columns=cols)
    on, off = table.loc[on_days].mean(), table.loc[base_days].mean()
    out = pd.DataFrame({"업종": on.index, "기준일 건수 평균": off.values, "행사일 건수 평균": on.values})
    out["결제건수 증가율(%)"] = np.where(out["기준일 건수 평균"] >= K_ANON_MIN,
                                   (out["행사일 건수 평균"] / out["기준일 건수 평균"] - 1) * 100, np.nan).round(0)
    out = out.drop(columns=["기준일 건수 평균", "행사일 건수 평균"])
    return out.sort_values("결제건수 증가율(%)", ascending=False).reset_index(drop=True)


# ------------------------------------------------------------------ DS-076 / 077 전입·전출 (PUBLIC 판, 관리자 전용)
@lru_cache(maxsize=1)
def ds076() -> pd.DataFrame:
    """PUBLIC(K-10) 판만 — 원본 · PUBLIC 을 같이 두면 같은 이동을 두 번 센다."""
    df = _read("GYEONGGI_IN_STAT_PUBLIC_*.csv", {"BF_YR_MON": str, "BF_SIDO": str, "BF_SIGNGU": str,
                                                  "BS_YR_MON": str, "BS_SIGNGU": str, "BS_HCD": str})
    df["FOR_CNT"] = pd.to_numeric(df["FOR_CNT"], errors="coerce").fillna(0)
    return df[df["BS_SIGNGU"].isin(ANSAN_SGG)]


@lru_cache(maxsize=1)
def ds077() -> pd.DataFrame:
    df = _read("GYEONGGI_OUT_STAT_PUBLIC_*.csv", {"BS_YR_MON": str, "BS_SIGNGU": str, "BS_HCD": str,
                                                   "AF_YR_MON": str, "AF_SIDO": str, "AF_SIGNGU": str})
    df["FOR_CNT"] = pd.to_numeric(df["FOR_CNT"], errors="coerce").fillna(0)
    return df[df["BS_SIGNGU"].isin(ANSAN_SGG)]


def new_arrivals(month: str = LATEST_MONTH) -> pd.DataFrame:
    """수도권 다른 시군에서 안산으로 옮겨 온 외국인(FOR_CNT, 신용정보 보유자) — K-10 미만은 비표시.
    실물에는 해외 · 정보없음(99999)에서 온 전입이 없다(서울 · 인천 · 경기 출발만)."""
    df = ds076()
    sub = df[(df["BS_YR_MON"] == month) & ~df["BF_SIGNGU"].isin(ANSAN_SGG)].copy()
    sub["ADM_CD"] = sub["BS_HCD"].str[:8]
    agg = sub.groupby("ADM_CD")["FOR_CNT"].sum().rename("value")
    out = agg.reindex(ALL_DONGS, fill_value=0).reset_index()
    out.columns = ["ADM_CD", "value"]
    out["ADM_NM"] = out["ADM_CD"].map(DONG_NAME)
    out["masked"] = out["value"] < K_ANON_MIN
    return out.sort_values("value", ascending=False).reset_index(drop=True)


def migration_by_month() -> pd.DataFrame:
    """동 × 월 외국인 전입·전출·순유입 (안산 안 동끼리 이동 포함)."""
    din, dout = ds076().copy(), ds077().copy()
    din["ADM_CD"] = din["BS_HCD"].str[:8]
    dout["ADM_CD"] = dout["BS_HCD"].str[:8]
    a = din.groupby(["BS_YR_MON", "ADM_CD"])["FOR_CNT"].sum().rename("전입")
    b = dout.groupby(["AF_YR_MON", "ADM_CD"])["FOR_CNT"].sum().rename("전출")
    b.index = b.index.set_names(["BS_YR_MON", "ADM_CD"])
    out = pd.concat([a, b], axis=1).fillna(0).reset_index().rename(columns={"BS_YR_MON": "month"})
    out["순유입"] = out["전입"] - out["전출"]
    out["ADM_NM"] = out["ADM_CD"].map(DONG_NAME)
    return out


def arrivals_by_month() -> pd.DataFrame:
    """월별 수도권 다른 시군에서 온 외국인 전입 합계 (KPI 가입률 분모)."""
    df = ds076()
    sub = df[~df["BF_SIGNGU"].isin(ANSAN_SGG)]
    return sub.groupby("BS_YR_MON", as_index=False)["FOR_CNT"].sum().rename(columns={"BS_YR_MON": "month"})


# ------------------------------------------------------------------ 공표 통계 — 시민 '새로 온 이웃' (기본값 D14)
@lru_cache(maxsize=1)
def anchor_dong() -> pd.DataFrame:
    df = pd.read_csv(ANCHOR_DONG_CSV, encoding="utf-8-sig")
    df["month"] = df["ym"].str.replace("-", "")
    df["ADM_CD"] = df["dong"].map(DONG_CODE)
    return df[df["ADM_CD"].notna()]


def foreign_change(month: str = LATEST_MONTH) -> pd.DataFrame:
    """동별 외국인주민(등록외국인 + 거소신고 동포) 전월 대비 증감 — 안산시 공표 통계라 실제 인원 그대로 보인다."""
    df = anchor_dong()
    ms = sorted(df["month"].unique())
    if month not in ms or ms.index(month) == 0:
        return pd.DataFrame(columns=["ADM_CD", "ADM_NM", "value", "prev", "diff"])
    prev = ms[ms.index(month) - 1]
    cur = df[df["month"] == month].set_index("ADM_CD")["foreign_resident"]
    old = df[df["month"] == prev].set_index("ADM_CD")["foreign_resident"]
    out = pd.DataFrame({"value": cur, "prev": old.reindex(cur.index)}).reset_index()
    out["diff"] = out["value"] - out["prev"]
    out["ADM_NM"] = out["ADM_CD"].map(DONG_NAME)
    out = out.sort_values("diff", ascending=False).reset_index(drop=True)
    out.attrs["prev_month"] = prev
    return out


# ------------------------------------------------------------------ DS-014 외국인 유동 — 추이 · 성·연령 (관리자 전용, 결정 7)
T22 = "T22_GG_ADMI_FLOWPOP_*_4127.csv"


@lru_cache(maxsize=1)
def ds014_month() -> pd.DataFrame:
    """월 × 동 × 내외국인(F/N) × 성·연령 하루 평균(시간대 합) — 원본 → _cache/ds014_month.csv."""
    cache = CACHE_DIR / "ds014_month.csv"
    raw_files = _files(T22)
    if _cache_fresh(cache, raw_files):
        return pd.read_csv(cache, dtype={"month": str, "ADM_CD": str})
    if not raw_files:
        raise FileNotFoundError(f"{SOURCE_DIR / T22} — 먼저 {_hint()} 실행")
    frames = []
    for f in raw_files:
        df = _read_csv(f, {"ADMI_CD": str, "FORN_GB": str, "ETL_YMD": str})
        df["date"] = _ymd(df["ETL_YMD"])
        df = df[df["date"].notna()]
        df["month"] = df["date"].dt.strftime("%Y%m")
        df["ADM_CD"] = df["ADMI_CD"].str[:8]
        for c in SEX_AGE_COLS:
            df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)
        nd = df.groupby("month")["date"].nunique()
        agg = df.groupby(["month", "ADM_CD", "FORN_GB"], as_index=False)[SEX_AGE_COLS].sum()
        agg[SEX_AGE_COLS] = agg[SEX_AGE_COLS].div(agg["month"].map(nd), axis=0).round(3)
        frames.append(agg)
    out = pd.concat(frames, ignore_index=True).groupby(["month", "ADM_CD", "FORN_GB"], as_index=False)[SEX_AGE_COLS].sum()
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    out.to_csv(cache, index=False, encoding="utf-8-sig")
    return out


def ds014_months() -> list:
    return sorted(ds014_month()["month"].unique())


def foreign_flow_trend() -> pd.DataFrame:
    """월 × 동: 안산 외국인 유동 중 이 동의 비중(share) · 이 동 유동 중 외국인 비율(ratio). 외국인 값이 작으면 마스킹."""
    df = ds014_month().copy()
    df["tot"] = df[SEX_AGE_COLS].sum(axis=1)
    piv = df.pivot_table(index=["month", "ADM_CD"], columns="FORN_GB", values="tot", aggfunc="sum").fillna(0)
    piv = piv.reindex(columns=["F", "N"], fill_value=0).reset_index()
    piv["share"] = piv["F"] / piv.groupby("month")["F"].transform("sum")
    piv["ratio"] = piv["F"] / (piv["F"] + piv["N"]).replace(0, np.nan)
    piv["masked"] = piv["F"] < MASK_MIN_POP
    piv["ADM_NM"] = piv["ADM_CD"].map(DONG_NAME)
    return piv[["month", "ADM_CD", "ADM_NM", "share", "ratio", "masked"]]


def foreign_sex_age(dong: str = None, month: str = None) -> pd.DataFrame:
    """외국인(F) 성·연령 구성비 — dong 이 없으면 안산 전체. 칸 값이 MASK_MIN_POP 미만이면 비중 비표시."""
    df = ds014_month()
    month = month or ds014_months()[-1]
    sub = df[(df["FORN_GB"] == "F") & (df["month"] == month)]
    if dong:
        sub = sub[sub["ADM_CD"] == dong]
    vals = sub[SEX_AGE_COLS].sum()
    total = vals.sum()
    out = pd.DataFrame({"성별": ["남" if s == "M" else "여" for s, _ in SEX_AGE],
                        "연령": [f"{a}세+" if a == 70 else f"{a}~{a + 4}세" for _, a in SEX_AGE],
                        "value": vals.values})
    out["비중"] = np.where(out["value"] >= MASK_MIN_POP, out["value"] / total if total > 0 else np.nan, np.nan)
    return out.drop(columns="value")


# ------------------------------------------------------------------ DS-032 50m 격자 (관리자 전용)
# 원본은 한 달 3~4GB(실물) — 앱은 원본을 읽지 않고 '평일/주말 × 시각 × 국적 × 셀' 하루 평균 집계본(_cache/ds032_grid.csv)만 읽는다.
# 실물 FORN_GB 는 국적 이름(N = 내국인, '기타' 등 — 규격서의 '국적코드'와 다름). 가상도 이름으로 맞췄다(v0.4).
T1 = "T1_GG_50CELL_FLOWPOP_*_4127.csv"
GRID_CACHE = "ds032_grid.csv"
GRID_ALL = "외국인 전체"
GRID_USECOLS = ["ADMI_NM", "UTMK_X", "UTMK_Y", "TIME_CD", "FORN_GB", "ETL_YMD"]


def grid_aggregate(chunks, hours, min_pop: float = 0.0, top_nats: int = None) -> pd.DataFrame:
    """원본 조각들 → (평일/주말, 시각, 국적, 50m 셀) 하루 평균. 외국인 행만 · 고른 시각만.
    min_pop · top_nats 를 주면 그 자리에서 지우고 자른다(시험용). 집계본은 가림 전 값으로 두고(실데이터는 비공개 폴더),
    가림은 화면에서 칸을 묶은 뒤 한다(grid_cells) — 50m 칸 그대로 5 미만을 지우면 실물에서 셀이 거의 남지 않았다(v0.4).
    가상(gen_synthetic) · 실물(pipeline/stage_grid.py)이 같은 함수를 쓴다."""
    parts, days = [], {"평일": set(), "주말": set()}
    for ch in chunks:
        ch.columns = [str(c).strip() for c in ch.columns]
        ch["TIME_CD"] = pd.to_numeric(ch["TIME_CD"], errors="coerce")
        ch = ch[(ch["FORN_GB"].astype(str).str.strip() != "N") & ch["TIME_CD"].isin(hours)].copy()
        if ch.empty:
            continue
        ch["TIME_CD"] = ch["TIME_CD"].astype(int)
        vals = [c for c in ch.columns if c.startswith(("M_", "F_"))]
        ch["POP"] = ch[vals].apply(pd.to_numeric, errors="coerce").fillna(0).sum(axis=1)
        ymd = ch["ETL_YMD"].astype(str).str[:8]
        dts = pd.to_datetime(ymd, format="%Y%m%d", errors="coerce")
        ch["daytype"] = np.where(dts.dt.weekday >= 5, "주말", "평일")
        for t, d in ymd.groupby(ch["daytype"]):
            days[t].update(d.unique())
        parts.append(ch.groupby(["daytype", "TIME_CD", "FORN_GB", "UTMK_X", "UTMK_Y", "ADMI_NM"], as_index=False)["POP"].sum())
    if not parts:
        return pd.DataFrame(columns=["daytype", "TIME_CD", "NAT", "UTMK_X", "UTMK_Y", "ADMI_NM", "POP"])
    agg = pd.concat(parts).groupby(["daytype", "TIME_CD", "FORN_GB", "UTMK_X", "UTMK_Y", "ADMI_NM"], as_index=False)["POP"].sum()
    agg["POP"] = agg["POP"] / agg["daytype"].map({k: max(len(v), 1) for k, v in days.items()})
    total = agg.groupby(["daytype", "TIME_CD", "UTMK_X", "UTMK_Y", "ADMI_NM"], as_index=False)["POP"].sum()
    total["FORN_GB"] = GRID_ALL
    keep = agg.groupby("FORN_GB")["POP"].sum().sort_values(ascending=False)
    keep = keep.head(top_nats).index if top_nats else keep.index
    out = pd.concat([total, agg[agg["FORN_GB"].isin(keep)]], ignore_index=True).rename(columns={"FORN_GB": "NAT"})
    out = out[out["POP"] >= min_pop] if min_pop else out[out["POP"] > 0]
    out["POP"] = out["POP"].round(3)
    return out[["daytype", "TIME_CD", "NAT", "UTMK_X", "UTMK_Y", "ADMI_NM", "POP"]]


def has_grid() -> bool:
    return (CACHE_DIR / GRID_CACHE).exists() or bool(_files(T1))


@lru_cache(maxsize=1)
def ds032_grid() -> pd.DataFrame:
    cache = CACHE_DIR / GRID_CACHE
    raw = _files(T1)
    if not _cache_fresh(cache, raw):
        if not raw:
            raise FileNotFoundError(f"{SOURCE_DIR / T1} — 먼저 {_hint()} 실행")
        from config import GRID_HOURS
        chunks = (c for f in raw for c in pd.read_csv(f, encoding=_encoding_of(f), chunksize=500_000,
                                                      dtype={"FORN_GB": str, "ETL_YMD": str}, low_memory=False))
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        grid_aggregate(chunks, GRID_HOURS).to_csv(cache, index=False, encoding="utf-8-sig")
    return pd.read_csv(cache, dtype={"NAT": str, "daytype": str})


def _encoding_of(path) -> str:
    with open(path, "rb") as fh:
        head = fh.read(4096)
    try:
        head.decode("utf-8")
        return "utf-8-sig"
    except UnicodeDecodeError:
        return CSV_ENCODING


def grid_cells(nat: str, daytype: str, hour: int, res: int = None) -> pd.DataFrame:
    """칸 크기 res(m)로 50m 셀을 묶은 뒤 GRID_MIN_POP 미만 칸을 지운다 — 가림은 늘 묶은 다음에.
    UTMK_X/Y 는 50m 칸 가운데(실물 · 가상 모두 끝자리 25)라 칸 왼쪽아래 x0 · y0 = (값 // res) * res — 50 · 100 · 250m
    칸이 0 기준으로 포개진다. lon · lat 는 칸 가운데."""
    from config import GRID_MIN_POP, GRID_RES_DEFAULT
    res = res or GRID_RES_DEFAULT
    df = ds032_grid()
    sub = df[(df["NAT"] == nat) & (df["daytype"] == daytype) & (df["TIME_CD"] == hour)].copy()
    sub["x0"] = (sub["UTMK_X"] // res * res).astype("int64")
    sub["y0"] = (sub["UTMK_Y"] // res * res).astype("int64")
    # 칸이 동 경계를 걸치면 값이 큰 동 이름을 붙인다
    sub = sub.sort_values("POP", ascending=False)
    out = sub.groupby(["x0", "y0"], as_index=False).agg(POP=("POP", "sum"), ADMI_NM=("ADMI_NM", "first"))
    out = out[out["POP"] >= GRID_MIN_POP].reset_index(drop=True)
    lon, lat = utmk_to_wgs84(out["x0"].to_numpy(float) + res / 2, out["y0"].to_numpy(float) + res / 2)
    out["lon"], out["lat"] = lon, lat
    return out[["lon", "lat", "POP", "ADMI_NM", "x0", "y0"]]


def grid_squares(cells: pd.DataFrame, res: int) -> list:
    """칸 네 귀퉁이(WGS84 [경도, 위도] × 4) — 지도에 칸을 네모로 그린다. 번지는 히트맵은 확대하면 점으로 흩어지고
    색 기준이 화면마다 바뀌어서, 자료가 가진 정밀도(칸) 그대로 그리고 확대하면 칸 아래 길이 비치게 했다(v0.4)."""
    x0 = cells["x0"].to_numpy(float)
    y0 = cells["y0"].to_numpy(float)
    xs = np.stack([x0, x0 + res, x0 + res, x0], axis=1).ravel()
    ys = np.stack([y0, y0, y0 + res, y0 + res], axis=1).ravel()
    lon, lat = utmk_to_wgs84(xs, ys)
    return np.round(np.stack([lon, lat], axis=1), 7).reshape(-1, 4, 2).tolist()


@lru_cache(maxsize=1)
def grid_nations() -> list:
    """'외국인 전체'를 먼저, 그다음 셀 값 합이 큰 국적 순 — 가장 큰 칸으로 묶어도 가림 기준을 넘는 칸이 하나도 없는
    국적은 뺀다(고르면 빈 지도만 나오므로). 실물 50m 표는 국적 구성이 동 단위 표와 크게 달라 대부분 빠진다."""
    from config import GRID_RES_OPTIONS
    df = ds032_grid()
    order = df[df["NAT"] != GRID_ALL].groupby("NAT")["POP"].sum().sort_values(ascending=False).index.tolist()
    big = max(GRID_RES_OPTIONS)
    combos = df[["daytype", "TIME_CD"]].drop_duplicates().itertuples(index=False)
    combos = list(combos)
    keep = [n for n in order if any(len(grid_cells(n, d, int(h), big)) for d, h in combos)]
    return [GRID_ALL] + keep


def grid_composition() -> pd.Series:
    """격자 집계본의 국적 구성(%) — 동 단위 표(DS-017)와 비교해 경고할 때 쓴다."""
    df = ds032_grid()
    s = df[df["NAT"] != GRID_ALL].groupby("NAT")["POP"].sum()
    return (s / s.sum() * 100).sort_values(ascending=False)


def grid_hours() -> list:
    return sorted(ds032_grid()["TIME_CD"].unique().tolist())


# ------------------------------------------------------------------ 칸 거리 이름 (실데이터 판만)
# 길 단위 인구 자료는 없다(가장 잘게 = DS-032 50m 칸) — 길마다 값을 매기지 않고 칸을 부르는 이름만 붙인다(결정 12).
ROAD_FILE = "road_names_50m.csv"


@lru_cache(maxsize=1)
def road_cells():
    """도로명주소 도로구간(공공) → 50m 칸 × 도로명 × 길이 (pipeline/stage_roads.py). 도로 자료는 공공이지만 이름을 붙일
    밀집 칸이 실데이터라 실데이터 판에만 둔다 — 가상 격자에 실제 도로명을 붙이면 사실처럼 읽힌다. 없으면 None."""
    if not IS_REAL:
        return None
    f = SOURCE_DIR / ROAD_FILE
    return pd.read_csv(f, encoding="utf-8-sig", dtype={"RN": str}) if f.exists() else None


def has_streets() -> bool:
    return road_cells() is not None


@lru_cache(maxsize=4)
def _street_lengths(res: int) -> pd.DataFrame:
    rd = road_cells()
    return (rd.assign(cx=rd["x0"] // res * res, cy=rd["y0"] // res * res)
            .groupby(["cx", "cy", "RN"], as_index=False)["len_m"].sum())


def cell_streets(cells: pd.DataFrame, res: int) -> list:
    """칸마다 '칸 안을 가장 길게 지나는 도로명' — 칸 안에 도로가 없으면 둘레 8칸까지 본다. 그 길 위의 인원이라는 뜻이
    아니라 칸을 부르는 이름(○○로 일대)이다. 도로 자료가 없으면(가상 판) 빈 이름."""
    if cells.empty or not has_streets():
        return [""] * len(cells)
    g = _street_lengths(int(res))
    top = (g.sort_values("len_m", ascending=False, kind="mergesort").drop_duplicates(["cx", "cy"])
           .set_index(["cx", "cy"])["RN"])
    out = []
    for x, y in zip(cells["x0"].astype("int64"), cells["y0"].astype("int64")):
        name = top.get((x, y))
        if name is None:
            near = g[g["cx"].between(x - res, x + res) & g["cy"].between(y - res, y + res)]
            name = near.groupby("RN")["len_m"].sum().idxmax() if len(near) else ""
        out.append(name)
    return out


def street_share(cells: pd.DataFrame, streets: list, n: int = 5) -> pd.DataFrame:
    """(동, 칸 이름) 별 인원 비중 상위 n — 관리자 '밀집 거리' 줄. 이름 없는 칸은 빼되 비중의 분모에는 넣는다."""
    df = cells.assign(street=list(streets))
    total = df["POP"].sum()
    df = df[df["street"] != ""]
    if df.empty or not total:
        return pd.DataFrame(columns=["ADMI_NM", "street", "share"])
    s = df.groupby(["ADMI_NM", "street"], as_index=False)["POP"].sum()
    s["share"] = s["POP"] / total
    return s.sort_values("share", ascending=False).head(n)[["ADMI_NM", "street", "share"]].reset_index(drop=True)


# ------------------------------------------------------------------ 원곡동 다문화특구 일원 경계 (실데이터 판만)
ZONE_FILE = "zone_multicultural.geojson"


@lru_cache(maxsize=1)
def zone_geojson():
    """시 내부 산출물(집계구를 합친 선) — 공개 여부 확인 전까지 실데이터 판에만.
    pipeline/stage_real.py 가 shp → WGS84 GeoJSON 으로 바꿔 data/real 에 둔다. 없으면 None."""
    if not IS_REAL:
        return None
    f = SOURCE_DIR / ZONE_FILE
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else None


# ------------------------------------------------------------------ 시민 앱 (v0.5, 2026-11-20 · 결정 13)
PRESENCE_QUANTILES = (0.5, 0.8, 0.95)   # 국적 하나의 (평일/주말 × 24시간 × 동) 비중을 한데 모아 자른 4단계


@lru_cache(maxsize=64)
def presence_levels(nat: str, month: str = LATEST_MONTH, div: int = 1) -> dict:
    """시간대별 '우리 이웃이 많은 동' — 동마다 1~4 단계만 준다(비중 · 인원은 화면에 보내지 않는다).

    - 평일/주말 × 0~23시마다 국적 안 동별 비중을 구한다(gathering 과 같은 식, 시각 하나).
    - 단계 기준은 그 국적의 48개 시각 비중을 **한데 모아** 자른다 → 슬라이더를 움직이면 색이 실제로 옮겨 간다
      (시각마다 따로 자르면 어느 시각이든 같은 그림이 된다).
    - 그 시각 인원이 MASK_MIN_POP 미만인 동은 None(소수 — 화면에서 색을 칠하지 않음).
    - '연휴'(2026-11-20): 한국 연휴 날짜마다 비중을 구해 평균한다 — 날마다 비중으로 바꾼 뒤 모으므로 산출 구간
      경계(실물 DS-017 2026-04 수준 변화)의 영향을 받지 않는다. 단계 기준은 평일 · 주말과 **같은** 기준을 쓴다
      (연휴에 원곡동이 평소보다 진해지는 것이 그대로 보이게). 가림은 연휴 날들의 평균 인원으로.
    """
    prof = ds017_profile()
    sub = prof[(prof["month"] == month) & (prof["CNTRY_NM"] == nat) & (prof["IN_FORN_DIV_NM"] == div)]
    pop = sub.groupby(["daytype", "TIMEZN_CD", "ADM_CD"])["POP"].sum()
    shares, masked = {}, {}
    for daytype in ("평일", "주말"):
        for hour in range(24):
            try:
                s = pop.loc[(daytype, hour)]
            except KeyError:
                s = pd.Series(dtype=float)
            s = s.reindex(ALL_DONGS, fill_value=0.0)
            total = s.sum()
            shares[(daytype, hour)] = s / total if total > 0 else s * 0.0
            masked[(daytype, hour)] = s < MASK_MIN_POP
    pooled = np.concatenate([shares[k][~masked[k]].to_numpy() for k in shares]) if shares else np.array([])
    edges = np.quantile(pooled, PRESENCE_QUANTILES) if len(pooled) else np.array([])
    out = {"평일": {}, "주말": {}}
    for (daytype, hour), s in shares.items():
        lv = 1 + np.searchsorted(edges, s.to_numpy(), side="right") if len(edges) else np.ones(len(s), int)
        out[daytype][hour] = {code: (None if m else int(v)) for code, v, m in zip(s.index, lv, masked[(daytype, hour)])}
    hol = ds017_holiday()
    hsub = hol[(hol["CNTRY_NM"] == nat) & (hol["IN_FORN_DIV_NM"] == div)]
    if len(hsub) and len(edges):
        hpop = hsub.groupby(["date", "TIMEZN_CD", "ADM_CD"])["POP"].sum()
        days = sorted(hsub["date"].astype(str).unique())
        out["연휴"] = {}
        for hour in range(24):
            share_d, pop_d = [], []
            for d in days:
                try:
                    s = hpop.loc[(d, hour)]                 # date 는 문자열로 읽는다(_ds017_cache)
                except KeyError:
                    continue
                s = s.reindex(ALL_DONGS, fill_value=0.0)
                if s.sum() > 0:
                    share_d.append(s / s.sum())
                    pop_d.append(s)
            if not share_d:
                out["연휴"][hour] = {code: None for code in ALL_DONGS}
                continue
            share = pd.concat(share_d, axis=1).mean(axis=1)
            pop_avg = pd.concat(pop_d, axis=1).mean(axis=1)
            lv = 1 + np.searchsorted(edges, share.to_numpy(), side="right")
            out["연휴"][hour] = {code: (None if p < MASK_MIN_POP else int(v)) for code, v, p in zip(share.index, lv, pop_avg)}
    return out


def meetup_dongs(nat: str, n: int = 3) -> list:
    """모임 글 쓸 때 보이는 '주말 오후에 우리 이웃이 많은 동' — 이름만(가린 동 제외)."""
    df = gathering(nat, "주말", range(12, 18))
    return list(df[~df["masked"]].sort_values("share", ascending=False).head(n)["ADM_CD"])


# ------------------------------------------------------------------ 시민 앱 골목 칸 (육각 · DS-032, 2026-11-20)
# 동(DS-017)보다 자세히 — 50m 셀은 거의 다 가림 기준에 걸리므로 H3 res9 크기(≈0.105 km²)의 육각 칸으로 묶은 뒤 가린다.
# 동 단위 자료를 육각으로 쪼개지는 않는다(동 값을 고르게 나누는 가짜 정밀도). 실데이터 판의 24시간 집계본이 있을 때만.
CELL_CACHE = "ds032_cells24.csv"


def hex_radius(area_m2: float) -> float:
    """정육각형 넓이 → 가운데에서 꼭짓점까지 거리(m)."""
    return float(np.sqrt(2 * area_m2 / (3 * np.sqrt(3))))


def hex_axial(x, y, R: float):
    """평면 좌표(UTM-K, m) → 꼭짓점이 위로 선 육각 칸의 축 좌표(q, r). H3 처럼 이웃 6칸이 모두 같은 거리에 있다."""
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    cx = (np.sqrt(3) / 3 * x - y / 3) / R
    cz = (2 / 3 * y) / R
    cy = -cx - cz
    rx, ry, rz = np.rint(cx), np.rint(cy), np.rint(cz)
    dx, dy, dz = np.abs(rx - cx), np.abs(ry - cy), np.abs(rz - cz)
    c1 = (dx > dy) & (dx > dz)
    c2 = ~c1 & (dy > dz)
    rx = np.where(c1, -ry - rz, rx)
    ry = np.where(c2, -rx - rz, ry)
    rz = np.where(~c1 & ~c2, -rx - ry, rz)
    return rx.astype(int), rz.astype(int)


def hex_center(q, r, R: float):
    q = np.asarray(q, dtype=float)
    r = np.asarray(r, dtype=float)
    return R * np.sqrt(3) * (q + r / 2), R * 1.5 * r


def hex_polygon(q: int, r: int, R: float) -> list:
    """칸 꼭짓점 6개 — WGS84 [위도, 경도] (Leaflet 순서)."""
    cx, cy = hex_center(q, r, R)
    ang = np.deg2rad(60 * np.arange(6) - 30)
    lon, lat = utmk_to_wgs84(cx + R * np.cos(ang), cy + R * np.sin(ang))
    return np.round(np.stack([lat, lon], axis=1), 6).tolist()


def cells_from_grid(df: pd.DataFrame, nat: str, area_m2: float, min_pop: float, usable_share: float,
                    with_stats: bool = False):
    """50m 셀(daytype · TIME_CD · NAT · UTMK_X · UTMK_Y · POP) → 국적 하나의 육각 칸 단계(동 단계와 같은 식).
    - 칸마다 그 시각 국적 안 비중 → 평일 · 주말 48개 시각을 한데 모은 분위(PRESENCE_QUANTILES)로 1~4 단계.
      그 시각 인원이 min_pop 미만인 칸은 0(칠하지 않음). 한 번도 칠해지지 않는 칸은 보내지 않는다. 인원 · 비중은 보내지 않는다.
    - usable = 가림 뒤 남는 인원 비율의 시각 중앙값 ≥ usable_share — 아니면 화면은 동 단위로만 보인다."""
    sub = df[df["NAT"] == nat]
    if sub.empty:
        return None
    R = hex_radius(area_m2)
    q, r = hex_axial(sub["UTMK_X"], sub["UTMK_Y"], R)
    sub = sub.assign(hid=[f"{a}_{b}" for a, b in zip(q, r)])
    pop = sub.groupby(["daytype", "TIME_CD", "hid"])["POP"].sum()
    hids = sorted(sub["hid"].unique())
    slots = [(d, h) for d in ("평일", "주말") for h in range(24)]
    shares, masked, kept = {}, {}, []
    for d, h in slots:
        try:
            s = pop.loc[(d, h)]
        except KeyError:
            s = pd.Series(dtype=float)
        s = s.reindex(hids, fill_value=0.0)
        tot = s.sum()
        shares[(d, h)] = s / tot if tot > 0 else s * 0.0
        masked[(d, h)] = s < min_pop
        if tot > 0:
            kept.append(float(s[~masked[(d, h)]].sum() / tot))
    retained = float(np.median(kept)) if kept else 0.0
    pooled = np.concatenate([shares[k][~masked[k]].to_numpy() for k in slots])
    if not len(pooled):
        out = {"usable": False, "hex": [], "levels": {}}
        return {**out, "retained": retained} if with_stats else out
    edges = np.quantile(pooled, PRESENCE_QUANTILES)
    grid = {}
    for k in slots:
        lv = 1 + np.searchsorted(edges, shares[k].to_numpy(), side="right")
        lv[masked[k].to_numpy()] = 0
        grid[k] = lv
    keep_idx = np.flatnonzero(np.any(np.stack([grid[k] for k in slots]) > 0, axis=0))
    polys = []
    for i in keep_idx:
        a, b = (int(v) for v in hids[i].split("_"))
        polys.append([hids[i], hex_polygon(a, b, R)])
    levels = {d: [grid[(d, h)][keep_idx].astype(int).tolist() for h in range(24)] for d in ("평일", "주말")}
    out = {"usable": bool(kept) and retained >= usable_share, "hex": polys, "levels": levels}
    return {**out, "retained": retained} if with_stats else out


@lru_cache(maxsize=1)
def ds032_cells24():
    """시민 앱 골목 칸용 24시간 집계본 — 실데이터 판에서 pipeline/stage_grid.py 가 만든 것만. 없으면 None(가상 판에는 없다)."""
    f = CACHE_DIR / CELL_CACHE
    if not IS_REAL or not f.exists():
        return None
    return pd.read_csv(f, dtype={"NAT": str, "daytype": str})


@lru_cache(maxsize=32)
def presence_cells(nat: str):
    """국적 하나의 골목 칸(육각) 단계. 집계본이 없으면(가상 판) None — 화면에 골목 칸 기능 자체를 보이지 않는다.
    50m 표에 그 국적 범주가 없으면 usable=False — 화면이 '이 나라는 골목 단위 자료가 부족해요'라고 알린다."""
    from config import CELL_HEX_AREA_M2, CELL_MIN_POP, CELL_USABLE_SHARE
    df = ds032_cells24()
    if df is None:
        return None
    if nat in (GRID_ALL, "기타") or nat not in set(df["NAT"]):
        return {"usable": False, "hex": [], "levels": {}}
    return cells_from_grid(df, nat, CELL_HEX_AREA_M2, CELL_MIN_POP, CELL_USABLE_SHARE)


# ------------------------------------------------------------------ 고향 사람 많이 다니는 쪽 가게 (2026-11-20)
BUSY_HOURS = list(range(12, 18))   # 주말 낮 — 모이고 장 보는 때(시간대 풀이 tipMeet 와 같은 뜻)
BUSY_LEVEL = 3                      # '많음' 이상


def busy_shops(nat: str, shops: tuple) -> dict:
    """shops = ((shop_id, lon, lat, dong), …) → {shop_id: 'cell' | 'dong'}.
    주말 낮 여섯 시각 중 절반 이상이 '많음' 이상인 골목 칸(그 국적에 골목 칸을 쓸 수 있으면) 또는 동네(못 쓰면)에 있는 가게.
    표시(있다/없다)만 내보낸다 — 단계 · 인원은 내보내지 않는다. 가게에 그 나라 사람이 '간다'는 뜻이 아니라, 고향 사람이
    많이 다니는 골목 · 동네에 '있다'는 뜻이다."""
    out = {}
    cells = presence_cells(nat)
    if cells and cells.get("usable") and cells["hex"]:
        from shapely.geometry import Point, Polygon
        lv = np.array(cells["levels"]["주말"])                     # 24 × 칸
        busy = (lv[BUSY_HOURS] >= BUSY_LEVEL).sum(axis=0) >= len(BUSY_HOURS) / 2
        polys = [(Polygon([(lo, la) for la, lo in pts]) if b else None) for (_, pts), b in zip(cells["hex"], busy)]
        for sid, lon, lat, _ in shops:
            p = Point(lon, lat)
            if any(poly is not None and poly.contains(p) for poly in polys):
                out[sid] = "cell"
        return out
    week = presence_levels(nat)["주말"]
    for sid, _, _, dong in shops:
        n = sum(1 for h in BUSY_HOURS if (week[h].get(dong) or 0) >= BUSY_LEVEL)
        if n >= len(BUSY_HOURS) / 2:
            out[sid] = "dong"
    return out
