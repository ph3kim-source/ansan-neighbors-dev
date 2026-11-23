"""안산 이웃 (Ansan Neighbors) — 2안 운영 콘솔(안산시 담당자 화면 · 기본 = 가상 데이터).

    cd 2안
    python src\\gen_synthetic.py     # 가상 데이터 (최초 1회)
    streamlit run src\\app.py

    실행.bat                          # 위와 같음 — data\\real 이 있으면 민간 실데이터 판(ANSAN_DATA=real · 이 PC 에서만 열림 · 내부 검토용)

시민 화면은 휴대폰 웹앱(app/ + src/server.py · 앱_실행.bat)이다 — 이 파일에 있던 옛 시민 화면(Streamlit 탭 5개)은
2026-11-20 정리에서 뺐다(바꾸기 전 판은 프로젝트 루트 _보관/2안_이전시민화면_20261120).
결정 근거: docs/기획_결정사항.md · 진행 상황/남은 일: docs/진행상황.md
"""
import datetime as dt
import tempfile
import uuid
from pathlib import Path

import altair as alt
import numpy as np
import pandas as pd
import pydeck as pdk
import streamlit as st

import community as cm
import metrics as mt
from config import (DATA_LABEL, DONG_CODE, DONG_NAME, DONGS, EVENTS, GRID_MIN_POP, GRID_RES_DEFAULT, GRID_RES_OPTIONS,
                    IS_REAL, K_ANON_MIN, MASK_MIN_POP, NAT_FLAG, NAT_NAMES, NOTICE_LANG_MIN_SHARE, NOTICE_TOP_DONGS,
                    OFFICIAL_LANGS, PLACE_VERIFY_UPVOTES, REAL_BADGE, RESIDENT_HOURS, ROOM_SHORT, SHARE_MODE,
                    SYNTHETIC_BADGE, TIME_BANDS)
from geo import load_dong_features

st.set_page_config(page_title="안산 이웃 · Ansan Neighbors", page_icon="🏘️", layout="wide")
st.markdown("""<style>
.syn{background:#FFF4D6;border:1px solid #E8B93A;color:#6B4E00;padding:7px 12px;border-radius:8px;font-size:.85rem;margin:0 0 10px}
.real{background:#E8F1FF;border:1px solid #3B6FD8;color:#123A84;padding:7px 12px;border-radius:8px;font-size:.85rem;margin:0 0 10px}
.chip{display:inline-block;border-radius:999px;padding:1px 9px;font-size:.74rem;margin-right:4px;background:#E8EEFF;color:#2B3A8C}
.chip.hot{background:#FFE3E3;color:#9B1C1C}.chip.off{background:#DFF5E3;color:#17642B}.chip.warn{background:#FFF0D9;color:#8A4B00}
.meta{color:#6B7280;font-size:.8rem}
</style>""", unsafe_allow_html=True)

DONG_CODES = [c for c, _, _ in DONGS]
NATS = [n for n in NAT_NAMES if n != "기타"]
KIND_LABEL = {"event": "🎉 행사", "policy": "📜 정책", "notice": "📌 공지"}
SCOPE_LABEL = {"target": "대상 주민에게만 (맞춤 공지)", "all": "모든 주민 (대상 국적은 표시만)"}
POLICY_TOPICS = ["의료", "노동", "교육", "행정", "비자"]
RES_SRC = (f"DS-017 AMD_INFLOW_TIME_F_POP (대민개방 O) — 장기 체류 외국인의 평일 새벽 "
           f"{RESIDENT_HOURS[0]}~{RESIDENT_HOURS[-1]}시 평균 위치(밤에 머무는 곳 = 사는 곳)의 동별 비중 · "
           "동 총량은 공표 동별 외국인주민 수로 보정(국적 구성은 통신 그대로) · '소수'는 보정 전 원값으로 판정")
WORKER_NATS = ["인도네시아", "네팔", "방글라데시", "스리랑카", "캄보디아", "미얀마"]   # 연휴 효과 기본 비교 국적
# 실데이터 판의 행사 효과 예시 — 시의 실제 행사 기록이 아직 없어 '한국 연휴 · 원곡동'을 자연 실험으로 둔다
REAL_PRESETS = [
    {"name": "설 연휴 · 원곡동 (자연 실험)", "dong": DONG_CODE["원곡동"], "days": ["20260216", "20260217", "20260218"],
     "target": []},
    {"name": "노동절 · 원곡동 (자연 실험)", "dong": DONG_CODE["원곡동"], "days": ["20260501"], "target": []},
    {"name": "부처님오신날 대체공휴일 · 원곡동 (자연 실험)", "dong": DONG_CODE["원곡동"], "days": ["20260525"], "target": []},
]


# ------------------------------------------------------------------ 공통
def badge():
    if IS_REAL:
        st.markdown(f"<div class='real'>{REAL_BADGE}</div>", unsafe_allow_html=True)
    else:
        st.markdown(f"<div class='syn'>{SYNTHETIC_BADGE}</div>", unsafe_allow_html=True)


def source(text):
    st.caption(f"📎 출처: {text} · {DATA_LABEL}")


def break_chip():
    """DS-017 산출 구간 경계가 있으면 알린다 — 경계를 넘는 원값 비교는 하지 않는다 (실물 2026-04)."""
    br = mt.ds017_breaks()
    if br:
        st.markdown(chip(f"DS-017 산출 수준이 {', '.join(b[:4] + '-' + b[4:6] for b in br)}부터 크게 바뀜 — "
                         "달끼리는 비중 · 순위로만, 연휴 · 행사 기준일은 같은 구간 안에서만 고름", "warn"),
                    unsafe_allow_html=True)


def chip(text, kind=""):
    return f"<span class='chip {kind}'>{text}</span>"


def pct(x):
    return f"{x * 100:.1f}%"


def ago(ts):
    hours = int((dt.datetime.now() - dt.datetime.fromisoformat(ts)).total_seconds() // 3600)
    return "방금" if hours < 1 else f"{hours}시간 전" if hours < 24 else f"{hours // 24}일 전"


def act(fn, *args):
    """버튼 콜백 — 콜백은 새 스레드에서 돌므로 세션 DB를 다시 지정한 뒤 실행 (공유 시연판)."""
    cm.use_db(st.session_state.get("db_path"))
    fn(*args)


def tr(d, lang):
    return d.get(lang) or d.get("ko", "")


def top_visible(df, n=3):
    return df[~df["masked"]].sort_values("share", ascending=False).head(n)


def zone_layer(zone):
    """원곡동 다문화특구 일원 경계(보라색 선) — 실데이터 판에만 있다 (mt.zone_geojson)."""
    return pdk.Layer("GeoJsonLayer", zone, stroked=True, filled=False, get_line_color=[124, 58, 237, 235],
                     line_width_min_pixels=3, pickable=False)


# ------------------------------------------------------------------ 관리자
def page_admin_trends():
    ms = mt.months()
    st.markdown(f"#### 📊 국적별 생활권 동향 — 사는 곳 (DS-017 장기 · 평일 새벽, {ms[0]}~{ms[-1]})")
    break_chip()
    nats = st.multiselect("국적", NATS, default=["중국", "우즈베키스탄", "러시아", "베트남", "카자흐스탄"], key="adm_nats")
    if nats:
        trend = mt.residence_trend(nats)
        # 달끼리 원값(지수)을 비교하지 않는다 — 실물은 산출 구간이 바뀌어 수준이 뛴다. 달 안의 구성비로 본다.
        mix = mt.nationality_mix(nats)
        st.markdown("**사는 곳(밤 기준) 외국인 중 국적 비중**")
        st.altair_chart(alt.Chart(mix).mark_line(point=True).encode(
            x=alt.X("ETL_YM:N", title="월"), y=alt.Y("share:Q", title=None, axis=alt.Axis(format="%")),
            color=alt.Color("CNTRY_NM:N", title="국적")), height=260)
        nat1 = st.selectbox("동별로 볼 국적", nats, key="adm_nat1")
        sub = trend[trend["CNTRY_NM"] == nat1].copy()
        sub["비중"] = sub["POP"] / sub.groupby("ETL_YM")["POP"].transform("sum")
        sub["동"] = sub["ADM_CD"].map(DONG_NAME)
        top6 = sub[sub["ETL_YM"] == ms[-1]].nlargest(6, "비중")["동"]
        st.altair_chart(alt.Chart(sub[sub["동"].isin(top6)]).mark_line(point=True).encode(
            x=alt.X("ETL_YM:N", title="월"), y=alt.Y("비중:Q", axis=alt.Axis(format="%")), color="동:N"), height=260)
        source(RES_SRC + " (표본이라 지수 · 비중으로만 표시)")
    st.divider()
    st.markdown("#### 💳 외국인 결제 — 어느 동 · 어느 업종에서 쓰나 (DS-056 · 관리자 전용)")
    st.markdown(chip("대민개방 X · 금액 없이 건수 비중만", "warn")
                + chip("국적 구분 없음 — 카드사 국적코드표 미수령") + chip("시민 지도에는 내지 않음 (기본값 D11)"),
                unsafe_allow_html=True)
    month = st.select_slider("기준월", ms, value=ms[-1], key="card_month")
    c1, c2 = st.columns([1.3, 1])
    by_dong = mt.foreign_spending_by_dong(month)
    with c1:
        vis = by_dong[~by_dong["masked"]].nlargest(10, "share")
        st.altair_chart(alt.Chart(vis).mark_bar(color="#7C3AED").encode(
            x=alt.X("share:Q", title="외국인 결제건수 비중", axis=alt.Axis(format="%")),
            y=alt.Y("ADM_NM:N", sort="-x", title=None)), height=280)
    with c2:
        dong = st.selectbox("업종을 볼 동", [""] + DONG_CODES, format_func=lambda d: DONG_NAME.get(d, "안산 전체"),
                            key="card_dong")
        st.dataframe(mt.foreign_spending_rank(month, dong or None), hide_index=True)
    st.caption("외국인 결제는 표본 카드사 · 소수 집단 · 대형 점포에 쏠리기 쉽다 — 한 동 · 한 업종이 비중을 좌우하면 "
               "생활권이 아니라 특정 시설 효과일 수 있다. 동 결제건수 10건 미만은 순위에서 뺀다.")
    source("DS-056 GGC_SALES_YM_AMD — gb=03(외지인 · 외국인 모두 여기) · nt≠000 결제건수(cnt) 비중")


HOUR_LABEL = {3: "새벽 3시 (사는 곳)", 14: "오후 2시", 21: "밤 9시"}
# 격자 칸 색 — 파랑 한 색 진하기 5단계(dataviz 순서형 250→650 · 동 지도와 같은 '많을수록 진하게'). 반투명이라 칸 아래 길이 비친다.
GRID_RAMP = [[134, 182, 239], [85, 152, 231], [42, 120, 214], [28, 92, 171], [16, 66, 129]]
GRID_ALPHA = 150
GRID_TOOLTIP = {"html": "<b>{ADMI_NM}</b> {street_txt}<br/>하루 평균 약 {pop_txt}명", "style": {"fontSize": "12px"}}


def grid_tiers(pop):
    """칸 값 → 이 화면 안 5분위 등급(칸이 적으면 등급 수도 줄인다). → (등급 번호 배열, 경계값 배열)"""
    pop = np.asarray(pop, dtype=float)
    if not len(pop):
        return np.zeros(0, dtype=int), np.array([])
    edges = np.unique(np.quantile(pop, np.linspace(0, 1, len(GRID_RAMP) + 1)))
    if len(edges) < 2:
        return np.zeros(len(pop), dtype=int), np.array([pop.min(), pop.max()])
    return np.searchsorted(edges[1:-1], pop, side="right"), edges


def grid_palette(n):
    """등급 n개에 쓸 색 — 5단계에서 고르게 고른다(1개면 가장 진한 색)."""
    if n <= 1:
        return [GRID_RAMP[-1]]
    return [GRID_RAMP[i] for i in np.round(np.linspace(0, len(GRID_RAMP) - 1, n)).astype(int)]


def grid_legend(edges, colors) -> str:
    """색 등급 범례 — 색만으로 읽지 않게 칸 값 범위(하루 평균 명)를 같이 적는다."""
    items = []
    for c, lo, hi in zip(colors, edges[:-1], edges[1:]):
        rng = f"{lo:,.0f}" if round(lo) == round(hi) else f"{lo:,.0f}~{hi:,.0f}"
        items.append('<span style="display:inline-flex;align-items:center;gap:4px;margin-right:12px">'
                     f'<span style="width:14px;height:14px;border-radius:3px;'
                     f'background:rgba({c[0]},{c[1]},{c[2]},{GRID_ALPHA / 255:.2f});border:1px solid rgb({c[0]},{c[1]},{c[2]})">'
                     f'</span>{rng}</span>')
    return ('<div style="font-size:0.85rem;opacity:.85;margin:-4px 0 6px">하루 평균 명 (이 화면 안 등급) &nbsp; '
            + "".join(items) + "</div>")


def grid_view(cells) -> pdk.ViewState:
    """첫 화면을 칸이 모인 곳에 맞춘다 — 칸이 10개 이상이면 바깥 10%는 무시, 확대는 11~15.5 사이."""
    if cells.empty:
        return pdk.ViewState(latitude=37.318, longitude=126.83, zoom=11.6)
    v = pdk.data_utils.compute_view(cells[["lon", "lat"]], view_proportion=0.9 if len(cells) >= 10 else 1)
    return pdk.ViewState(latitude=float(v.latitude), longitude=float(v.longitude), zoom=float(min(max(v.zoom, 11), 15.5)))


def page_admin_grid():
    st.markdown("#### 🔥 50m 격자 지도 — 관리자 전용")
    st.markdown(chip("DS-032 GG_50CELL_FLOWPOP · 대민개방 X · 시민 화면은 행정동 단위만", "warn"), unsafe_allow_html=True)
    if not mt.has_grid():
        st.info("50m 격자 집계본이 없어요 — 실데이터 판은 `python pipeline\\stage_grid.py` 로 원본(한 달 3~4GB)을 "
                "평일/주말 × 시각 × 국적 하루 평균으로 줄여 둡니다.")
        return
    if IS_REAL:
        comp = mt.grid_composition()
        st.markdown(chip("50m 표의 국적 구성이 동 단위 표(DS-017)와 크게 다름 — " + " · ".join(
            f"{n} {v:.0f}%" for n, v in comp.head(4).items()) + " … 국적별 격자는 참고만, '외국인 전체'로 보세요", "warn")
                    + chip("단기 외국인(S99)은 국적 없이 '기타' 행에만 있어 세지 않음 — 장기 체류 외국인(성·연령 칸)만"),
                    unsafe_allow_html=True)
    c = st.columns([1.3, 1, 1.6, 1.3])
    nat = c[0].selectbox("국적 (가림 뒤 칸이 남는 국적만)", mt.grid_nations(),
                         format_func=lambda n: f"{NAT_FLAG.get(n, '🌐')} {n}", key="grid_nat")
    day = c[1].radio("요일", ["평일", "주말"], horizontal=True, key="grid_day")
    hours = mt.grid_hours()
    hour = c[2].radio("시각", hours, index=min(1, len(hours) - 1), horizontal=True,
                      format_func=lambda h: HOUR_LABEL.get(h, f"{h}시"), key="grid_hour")
    res = c[3].radio("칸 크기", GRID_RES_OPTIONS, index=GRID_RES_OPTIONS.index(GRID_RES_DEFAULT), horizontal=True,
                     format_func=lambda r: f"{r}m", key="grid_res",
                     help="50m 칸은 대부분 인원이 적어 가려진다 — 칸을 묶은 뒤에 가림 기준을 적용한다")
    cells = mt.grid_cells(nat, day, hour, res)
    if cells.empty:
        st.info(f"이 조건에서는 하루 평균 {GRID_MIN_POP:g} 이상인 {res}m 칸이 없어요 — 칸 크기를 키우거나 '외국인 전체'를 보세요.")
    streets = mt.cell_streets(cells, res)
    tier, edges = grid_tiers(cells["POP"])
    colors = grid_palette(max(len(edges) - 1, 1))
    data = pd.DataFrame({"poly": mt.grid_squares(cells, res), "color": [colors[t] + [GRID_ALPHA] for t in tier],
                         "ADMI_NM": cells["ADMI_NM"], "street_txt": [f"· {s} 일대" if s else "" for s in streets],
                         "pop_txt": cells["POP"].round().astype(int).astype(str)})
    outline = {"type": "FeatureCollection", "features": [f for *_, f in load_dong_features()]}
    layers = [pdk.Layer("GeoJsonLayer", outline, stroked=True, filled=False,
                        get_line_color=[90, 90, 90, 160], line_width_min_pixels=1),
              # 칸 사이 흰 틈은 미터 단위(3m) — 확대하면 칸이 갈라져 보이고, 도시 전체 배율에서는 틈이 사라져 색이 흐려지지 않는다
              pdk.Layer("PolygonLayer", data, get_polygon="poly", get_fill_color="color", filled=True, stroked=True,
                        get_line_color=[255, 255, 255, 230], get_line_width=3, line_width_min_pixels=0,
                        pickable=True, auto_highlight=True)]
    zone = mt.zone_geojson()
    if zone:
        layers.append(zone_layer(zone))
    st.pydeck_chart(pdk.Deck(map_style=None, initial_view_state=grid_view(cells), layers=layers, tooltip=GRID_TOOLTIP),
                    height=520)
    if len(cells):
        st.markdown(grid_legend(edges, colors), unsafe_allow_html=True)
    total = cells["POP"].sum()
    top = cells.groupby("ADMI_NM")["POP"].sum().sort_values(ascending=False).head(6)
    st.markdown("밀집 상위 동: " + (" · ".join(f"**{k}** {v / total * 100:.0f}%" for k, v in top.items())
                               or "표시할 칸 없음") + ("  · 보라색 선 = 원곡동 다문화특구 일원" if zone else ""))
    if mt.has_streets() and len(cells):
        ss = mt.street_share(cells, streets)
        st.markdown("밀집 거리: " + " · ".join(f"**{r.ADMI_NM} {r.street} 일대** {r.share * 100:.0f}%" for r in ss.itertuples()))
        st.caption("칸 이름 = 칸 안을 가장 길게 지나는 도로명(도로명주소 도로구간) — 그 길 위의 인원이라는 뜻은 아니에요. "
                   "자료의 가장 작은 단위가 50m 칸이라 길마다 값을 매기지 않아요.")
    source(f"DS-032 — 한 달 {day} 하루 평균 · 외국인(N 제외) 50m 셀의 성·연령 합을 {res}m 칸으로 묶음 · 칸 {len(cells):,}개 · "
           f"묶은 칸 값 {GRID_MIN_POP:g} 미만은 지움 · 색 = 이 화면 안 5분위 · FORN_GB 는 국적 이름(실물 확인)"
           + ("" if mt.has_streets() else " · 거리 이름은 실데이터 판에서만(가상 칸에 실제 도로명을 붙이면 사실처럼 읽혀서)"))


def page_admin_events():
    st.markdown("#### 🎪 행사 기획 추천 — DS-017 주말 시간대")
    targets = st.multiselect("대상 국적", NATS, default=["우즈베키스탄", "카자흐스탄", "러시아"], key="ev_targets")
    if targets:
        rec = mt.event_recommend(targets)
        st.dataframe(pd.DataFrame({"순위": range(1, len(rec) + 1), "동": rec["ADM_NM"],
                                   "시작 시각": rec["TIMEZN_CD"].astype(str) + "시",
                                   "대상 국적 평균 비중": (rec["share"] * 100).round(1)}), hide_index=True)
        heat = mt.gathering_hourly(targets)
        heat = heat[heat["TIMEZN_CD"].between(8, 23)]
        order = heat.groupby("ADM_NM")["share"].sum().sort_values(ascending=False).head(12).index.tolist()
        st.altair_chart(alt.Chart(heat[heat["ADM_NM"].isin(order)]).mark_rect().encode(
            x=alt.X("TIMEZN_CD:O", title="시각"), y=alt.Y("ADM_NM:N", sort=order, title=None),
            color=alt.Color("share:Q", title="비중", scale=alt.Scale(scheme="oranges"))), height=320)
        source("DS-017 AMD_INFLOW_TIME_F_POP — 2026-06 주말 일평균, 국적별 비중의 평균")
    st.divider()
    holiday_card()
    st.divider()
    event_effect_section()


def holiday_card():
    """한국 연휴 vs 모국 명절 — 날짜를 고르는 근거 (기본값 D12: 추천 기본값이 아니라 참고 카드, 관리자 전용)."""
    st.markdown("#### 🗓️ 한국 연휴 vs 모국 명절 — 외국인 방문이 평소보다 몇 배? (참고)")
    st.markdown(chip("관리자 전용 — 국적별 결집 배수는 시민 화면에 내지 않음 (혐오 · 단속 오용 방지)", "warn")
                + chip("연휴 인파에는 다른 시에 사는 같은 국적 주민도 섞임"), unsafe_allow_html=True)
    break_chip()
    he = mt.holiday_effect()
    if he.empty:
        st.caption("자료 기간 안에 연휴 · 명절이 없어요.")
        return
    nats = st.multiselect("비교할 국적", NATS, default=[n for n in WORKER_NATS + ["베트남", "중국", "우즈베키스탄"]
                                                     if n in NATS], key="hol_nats", format_func=lambda n: f"{NAT_FLAG[n]} {n}")
    if not nats:
        return
    sub = he[he["CNTRY_NM"].isin(nats)].copy()
    sub["날"] = sub["date"].str[4:6] + "/" + sub["date"].str[6:] + " " + sub["이름"]
    sub["표시"] = np.where(sub["배수"].notna(), sub["배수"].map(lambda v: f"×{v:.1f}" if pd.notna(v) else ""), "소수")
    order = sub.sort_values("date")["날"].unique().tolist()
    # 줄마다 날짜 이름이 다 보이게 (겹침 숨김 · 글자 자름 끔)
    base = alt.Chart(sub).encode(x=alt.X("CNTRY_NM:N", title=None, sort=nats, axis=alt.Axis(labelAngle=0)),
                                 y=alt.Y("날:N", sort=order, title=None,
                                         axis=alt.Axis(labelOverlap=False, labelLimit=260)))
    heat = base.mark_rect().encode(color=alt.Color("배수:Q", title="평소 대비 배수",
                                                   scale=alt.Scale(type="log", scheme="oranges")))
    st.altair_chart(heat + base.mark_text(fontSize=11).encode(text="표시:N"), height=max(260, 26 * len(order)))
    kinds = sub.groupby("구분")["배수"].median()
    st.markdown("**한국 연휴 중앙값** " + (f"×{kinds['한국 연휴']:.1f}" if "한국 연휴" in kinds else "—")
                + " · **모국 명절 중앙값** " + (f"×{kinds['모국 명절']:.1f}" if "모국 명절" in kinds else "—")
                + " — 근로자는 쉬는 날에 모인다. 모국 명절이 평일이면 출근해야 한다.")
    day = st.selectbox("그날 어느 동으로 모였나", order, key="hol_day")
    d = sub.loc[sub["날"] == day, "date"].iloc[0]
    top = mt.holiday_top_dongs(d, nats)
    st.markdown("평소보다 늘어난 인원이 간 동: " + (" · ".join(f"**{r['ADM_NM']}** {pct(r['증가분 비중'])}"
                                                    for _, r in top.iterrows()) or "늘어난 동 없음"))
    source("DS-017 — 장기 체류 외국인 하루 합 ÷ 같은 요일 ±4주(연휴 · 명절 제외) 중앙값 · "
           f"기준이 작으면(하루 합 < 30) '소수' · 이슬람 명절 날짜는 추정")


def event_effect_section():
    """행사 효과 — DS-042 · 061(관심지역, 미납품) 대신 행사가 열린 동 전체로 잰다 (기본값 D13)."""
    st.markdown("#### 📈 행사 효과 — 행사가 열린 동 단위 (DS-017 방문 · DS-056 외국인 결제)")
    st.markdown(chip("DS-042 · 061(관심지역 단위)은 미납품 → 동 전체로 잰다 · 동 안의 다른 인파도 섞임", "warn"),
                unsafe_allow_html=True)
    presets = REAL_PRESETS if IS_REAL else [mt.preset_event(e["area_cd"]) for e in EVENTS]
    labels = [p["name"] for p in presets] + ["직접 입력"]
    pick = st.selectbox("행사", labels, key="ev_sel")
    if pick == "직접 입력":
        c = st.columns([1, 1.4, 1.6])
        dong = c[0].selectbox("동", DONG_CODES, index=DONG_CODES.index(DONG_CODE["원곡동"]), format_func=DONG_NAME.get,
                              key="ev_dong")
        span = c[1].date_input("행사 기간", value=(dt.date(2026, 5, 1), dt.date(2026, 5, 1)),
                               min_value=dt.date(2026, 1, 15), max_value=dt.date(2026, 6, 30), key="ev_span")
        span = span if isinstance(span, (list, tuple)) else (span, span)
        start, end = span[0], span[-1]
        days = [(start + dt.timedelta(days=i)).strftime("%Y%m%d") for i in range((end - start).days + 1)][:7]
        target = c[2].multiselect("대상 국적 (선택)", NATS, key="ev_target")
        ev = {"name": "직접 입력", "dong": dong, "days": days, "target": target}
    else:
        ev = presets[labels.index(pick)]
    eff = mt.event_effect(ev["dong"], ev["days"], ev["target"])
    if eff.empty:
        st.info("그 날짜(또는 1 · 2주 전 기준일)의 자료가 없어요 — 자료 기간 안의 날짜를 고르세요.")
        return
    up = mt.event_total_uplift(ev["dong"], ev["days"], ev["target"])
    who = "대상 국적" if ev["target"] else "외국인 전체"
    m = st.columns(3)
    m[0].metric(f"{who} 방문 증가율", f"{up:+.0f}%" if pd.notna(up) else "—",
                help="행사일 평균 ÷ 1 · 2주 전 같은 요일 평균 − 1 (연휴는 기준일에서 뺌)")
    m[1].metric("장소", DONG_NAME[ev["dong"]])
    m[2].metric("날짜", ", ".join(f"{d[4:6]}/{d[6:]}" for d in ev["days"]))
    vis = eff[eff["증가율(%)"].notna()].copy()
    vis["구분"] = np.where(vis["대상 국적"], "대상 국적", "그 밖")
    # 막대마다 이름이 보이게 높이를 늘리고 범례를 글자로 (브라우저 점검 — 국적 이름 절반이 겹침으로 빠지고 범례가 true/false)
    st.altair_chart(alt.Chart(vis).mark_bar().encode(
        x=alt.X("증가율(%):Q"), y=alt.Y("국적:N", sort="-x", title=None, axis=alt.Axis(labelOverlap=False)),
        color=alt.Color("구분:N", title=None, scale=alt.Scale(domain=["대상 국적", "그 밖"],
                                                             range=["#9333EA", "#CBD5E1"]))),
        height=max(300, 22 * len(vis)))
    daily = mt.event_daily(ev["dong"], ev["days"])
    st.altair_chart(alt.Chart(daily).mark_line(point=True).encode(
        x=alt.X("ts:T", title=None), y=alt.Y("POP:Q", title="하루 외국인 (표본 · 상대값)"),
        color=alt.Color("구분:N", title=None)), height=200)
    if mt.card_is_daily():
        st.markdown("**외국인 결제건수 증가율 — 업종 대분류**")
        st.dataframe(mt.event_sales_effect(ev["dong"], ev["days"]), hide_index=True)
    else:
        st.caption("카드 결제 효과는 일별 자료(실데이터 판)에서만 — 가상 카드 자료는 월 단위입니다.")
    source(f"DS-017 장기 · 단기 외국인 하루 합 · DS-056 gb=03 · nt≠000 결제건수 — 기준일 값이 작으면 "
           f"(방문 < {MASK_MIN_POP:g}, 결제 < {K_ANON_MIN}) 증가율 비표시 · 금액은 쓰지 않음")


def page_admin_migration():
    flow_section()
    st.divider()
    st.markdown("#### 🚚 수도권 다른 시군에서 온 · 간 외국인 — DS-076 · DS-077 (PUBLIC)")
    st.markdown(chip("신용정보 보유 외국인만 집계 → 실제보다 적게 잡힘", "warn")
                + chip("해외에서 바로 온 전입은 없음 — 출발 · 도착이 서울 · 인천 · 경기뿐", "warn"), unsafe_allow_html=True)
    mig = mt.migration_by_month()
    mig_months = sorted(mig["month"].unique())
    month = st.select_slider("기준월", mig_months, value=mig_months[-1], key="mig_month")
    cur = mig[mig["month"] == month].sort_values("순유입", ascending=False)
    st.altair_chart(alt.Chart(cur).mark_bar().encode(
        x=alt.X("순유입:Q"), y=alt.Y("ADM_NM:N", sort="-x", title=None, axis=alt.Axis(labelOverlap=False)),
        color=alt.condition("datum.순유입 > 0", alt.value("#2563EB"), alt.value("#DC2626"))), height=460)
    na = mt.new_arrivals(month)
    vis = na[~na["masked"]].head(5)
    st.markdown("**다른 시군에서 온 외국인 전입 상위 동** (K-10 미만 비표시): "
                + (" · ".join(f"{r.ADM_NM} {int(r.value)}" for r in vis.itertuples()) or "모두 10명 미만"))
    source("DS-076 GYEONGGI_IN_STAT_PUBLIC · DS-077 GYEONGGI_OUT_STAT_PUBLIC — 안산 거주 · FOR_CNT")


def flow_section():
    """DS-014 동 유동인구 — 외국인 유동의 동별 비중 추이 · 성·연령 구조 (사용자 결정 7, 2026-11-18)."""
    ms = mt.ds014_months()
    st.markdown(f"#### 🧭 외국인 유동 추이 — DS-014 동 유동인구 ({ms[0][:4]}-{ms[0][4:]} ~ {ms[-1][:4]}-{ms[-1][4:]})")
    gap = [m for m in pd.period_range(ms[0][:4] + "-" + ms[0][4:], ms[-1][:4] + "-" + ms[-1][4:], freq="M")
           .strftime("%Y%m") if m not in ms]
    notes = [f"빠진 달 {', '.join(gap)} (납품 오류 — 다른 달 파일이 중복 납품)"] if gap else []
    if IS_REAL:
        notes.append("2024년 이전은 산출 기준이 바뀐 것으로 보여(외국인 비중 단절) 확인 전까지 싣지 않음")
    if notes:
        st.markdown(" ".join(chip(n, "warn") for n in notes), unsafe_allow_html=True)
    trend = mt.foreign_flow_trend()
    last = trend[(trend["month"] == ms[-1]) & ~trend["masked"]].nlargest(6, "share")
    sel = st.selectbox("동", DONG_CODES, index=DONG_CODES.index(last["ADM_CD"].iloc[0]) if len(last) else 0,
                       format_func=DONG_NAME.get, key="flow_dong")
    c1, c2 = st.columns([1.4, 1])
    with c1:
        show = trend[trend["ADM_CD"].isin(set(last["ADM_CD"]) | {sel}) & ~trend["masked"]]
        st.markdown("**안산 외국인 유동 중 각 동의 비중**")
        st.altair_chart(alt.Chart(show).mark_line(point=True).encode(
            x=alt.X("month:N", title="월"), y=alt.Y("share:Q", title=None, axis=alt.Axis(format="%")),
            color=alt.Color("ADM_NM:N", title="동")), height=260)
    with c2:
        r = trend[trend["ADM_CD"] == sel].set_index("month")
        a, b = r["ratio"].get(ms[0]), r["ratio"].get(ms[-1])
        st.metric(f"{DONG_NAME[sel]} 유동인구 중 외국인", pct(b) if pd.notna(b) else "—",
                  f"{(b - a) * 100:+.1f}%p ({ms[0][:4]}-{ms[0][4:]} 대비)" if pd.notna(a) and pd.notna(b) else None,
                  delta_color="off")   # 늘고 줆에 좋고 나쁨이 없다 — 빨강 · 초록을 쓰지 않는다
        first, latest = mt.foreign_sex_age(sel, ms[0]), mt.foreign_sex_age(sel, ms[-1])
        def share_of(df, mask):
            v = df.loc[mask(df), "비중"]
            return v.sum() if v.notna().all() and len(v) else np.nan
        fem = [share_of(x, lambda d: d["성별"] == "여") for x in (first, latest)]
        old = [share_of(x, lambda d: d["연령"].str[:2].astype(int) >= 40) for x in (first, latest)]
        st.markdown(f"외국인 중 **여성** {pct(fem[0]) if pd.notna(fem[0]) else '—'} → {pct(fem[1]) if pd.notna(fem[1]) else '—'}  \n"
                    f"외국인 중 **40세 이상** {pct(old[0]) if pd.notna(old[0]) else '—'} → "
                    f"{pct(old[1]) if pd.notna(old[1]) else '—'}")
    latest["비중표시"] = latest["비중"].fillna(0)
    st.markdown(f"**{DONG_NAME[sel]} 외국인 성 · 연령 구성 ({ms[-1][:4]}-{ms[-1][4:]})** — 공지 언어 · 행사 대상 정하기에 참고")
    st.altair_chart(alt.Chart(latest).mark_bar().encode(
        x=alt.X("연령:N", sort=None, title=None), y=alt.Y("비중표시:Q", title=None, axis=alt.Axis(format="%")),
        color=alt.Color("성별:N", scale=alt.Scale(domain=["남", "여"], range=["#2563EB", "#DB2777"])),
        xOffset="성별:N"), height=220)
    source(f"DS-014 GG_ADMI_FLOWPOP (대민개방 O · 2안은 관리자 화면만) — 외국인(F) 하루 평균(시간대 합)의 동별 비중 · "
           f"성 · 연령 칸 값 {MASK_MIN_POP:g} 미만은 0 으로 그림(비표시)")


def next_saturday(today=None):
    today = today or dt.date.today()
    return today + dt.timedelta(days=(5 - today.weekday()) % 7 or 7)


def notice_targeting(nats):
    """대상 국적 → 근거 표를 그리고 제안값(대상 동 · 장소 · 시각 · 번역 언어)을 돌려준다.

    전부 기존 지표 그대로: 거주 상위 동 mt.living_area_top(마스킹 반영) · 시간대별 모이는 동 mt.gathering ·
    행사 장소·시각 mt.event_recommend · 회원 언어방 분포 cm.member_languages. 새 가중합은 없다.
    """
    dongs = []
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**① 사는 곳 — 국적별 거주 비중 상위 동**")
        rows = []
        for n in nats:
            top = mt.living_area_top(n, NOTICE_TOP_DONGS)
            dongs += [c for c in top["ADM_CD"] if c not in dongs]
            rows.append({"국적": f"{NAT_FLAG[n]} {n}",
                         "거주 상위 동": " · ".join(f"{r.ADM_NM} {pct(r.share)}" for r in top.itertuples())
                         or "모두 소수(마스킹)"})
        st.dataframe(pd.DataFrame(rows), hide_index=True)
        source(f"{RES_SRC} · 값 {MASK_MIN_POP:g} 미만 동은 소수(마스킹)라 제안에서 뺌")
    with c2:
        daytype = st.radio("모이는 때", ["주말", "평일"], horizontal=True, key="nf_daytype")
        st.markdown(f"**② 모이는 때·곳 — {daytype} 시간대별 1위 동**")
        rows = []
        for n in nats:
            row = {"국적": f"{NAT_FLAG[n]} {n}"}
            for band, hours in TIME_BANDS.items():
                g = top_visible(mt.gathering(n, daytype, hours), 1)
                row[band.split()[0]] = f"{g['ADM_NM'].iloc[0]} {pct(g['share'].iloc[0])}" if len(g) else "소수"
            rows.append(row)
        st.dataframe(pd.DataFrame(rows), hide_index=True)
        source("DS-017 AMD_INFLOW_TIME_F_POP — 2026-06 시간대별 일평균 POP의 동별 비중 (국적 안에서)")
    rec = mt.event_recommend(nats, top=3)
    st.markdown("**③ 행사 장소·시각 — 주말에 대상 국적이 많이 모이는 동** · "
                + " / ".join(f"{i}. {r.ADM_NM} {int(r.TIMEZN_CD)}시" for i, r in enumerate(rec.itertuples(), 1)))
    source("DS-017 — 국적마다 비중으로 바꾼 뒤 평균 ('행사 기획·효과' 탭과 같은 계산)")
    langs = cm.member_languages(nats)
    total = sum(langs.values())
    share = {k: v / total for k, v in sorted(langs.items(), key=lambda kv: -kv[1])} if total else {}
    sugg_langs = [k for k in OFFICIAL_LANGS if k != "ko" and share.get(k, 0) >= NOTICE_LANG_MIN_SHARE]
    st.markdown("**④ 번역 언어 — 대상 국적 회원이 고른 언어방** · "
                + (" · ".join(f"{ROOM_SHORT.get(k, k)} {pct(v)}" for k, v in share.items()) or "회원 없음"))
    outside = sum(v for k, v in share.items() if k not in OFFICIAL_LANGS)
    note = (f" · ⚠️ {pct(outside)}는 공식 5개 언어 밖(기타 언어방) — 언어방 리더 번역 요청" if outside else "")
    st.caption(f"국적 ≠ 언어(결정 R2-7) — 회원 DB 언어방 비중 {NOTICE_LANG_MIN_SHARE:.0%} 이상을 번역 추천"
               f"{note} · 회원 DB는 시드(가상)")
    covered = " · ".join(f"{NAT_FLAG[n]} {n} {pct(mt.residence_coverage(n, dongs))}" for n in nats)
    st.markdown(f"<span class='meta'>받는 회원(가상 회원 DB) — 국적만: {cm.count_audience(nats)}명 · 거주 상위 동으로 "
                f"좁히면: {cm.count_audience(nats, dongs)}명 ({', '.join(DONG_NAME[d] for d in dongs)} — 대상 국적 거주자 중 "
                f"이 동들에 사는 비중: {covered})</span>", unsafe_allow_html=True)
    return {"dongs": dongs, "langs": sugg_langs,
            "place": rec["ADM_CD"].iloc[0] if len(rec) else "", "hour": int(rec["TIMEZN_CD"].iloc[0]) if len(rec) else 14}


def page_admin_notice(user):
    st.markdown("#### 📣 공지·정책·행사 작성")
    st.caption("대상 국적을 고르면 그 국적이 사는 동(DS-017 평일 새벽) · 모이는 때와 곳(DS-017) · 회원 언어(회원 DB)를 보여 주고, 장소 · 시각을 "
               "미리 채우고 번역 언어를 추천합니다. 대상 동은 '거주 상위 동으로 좁히기'를 켜면 채웁니다. 모두 바꿀 수 있습니다. "
               "맞춤 기준은 국적 · 거주 동뿐 (체류자격 미수집, 결정 R6-21).")
    c = st.columns([1, 2])
    kind = c[0].radio("종류", list(KIND_LABEL), format_func=KIND_LABEL.get, horizontal=True, key="nf_kind")
    nats = c[1].multiselect("대상 국적 (비우면 모든 주민)", NATS, key="nf_nats", format_func=lambda n: f"{NAT_FLAG[n]} {n}")
    sugg = notice_targeting(nats) if nats else {"dongs": [], "langs": [], "place": "", "hour": 14}
    # 대상 동은 기본 비움(국적만) — 거주 상위 동을 미리 고르면 그 밖에 사는 대상 국적 주민이 조용히 빠진다
    # (베트남 상위 3동 = 원곡·사·이동 → 고잔동 결혼이민자 시연 사용자가 못 받음). 좁히기는 켜야 적용 (기본값 D6)
    narrow = bool(nats) and st.toggle("거주 상위 동으로 좁히기", key="nf_narrow",
                                      help="켜면 대상 동 칸에 국적별 거주 상위 동을 채웁니다 — 그 동에 사는 대상 국적 주민에게만 보입니다")
    fk = f"{kind}_{'_'.join(sorted(nats)) or 'all'}" + ("_좁힘" if narrow else "")  # 조건이 바뀌면 새 양식 → 제안값 다시 채움
    trans = {}
    with st.form(f"nf_form_{fk}", clear_on_submit=True):
        scope = st.radio("공개 범위", list(SCOPE_LABEL), index=0 if nats else 1, format_func=SCOPE_LABEL.get,
                         horizontal=True, key=f"nf_scope_{fk}")
        dongs = st.multiselect("대상 동 — 맞춤 공지일 때만 씀 · 비우면 국적만으로", DONG_CODES,
                               default=sugg["dongs"] if narrow else [], format_func=DONG_NAME.get, key=f"nf_dongs_{fk}")
        title = st.text_input("제목 (한국어 원문)", key=f"nf_title_ko_{fk}")
        body = st.text_area("내용 (한국어 원문)", height=90, key=f"nf_body_ko_{fk}")
        with st.expander("번역 — 비우면 한국어 원문이 보입니다" + (" · 추천: " + ", ".join(OFFICIAL_LANGS[k] for k in sugg["langs"])
                                                         if sugg["langs"] else ""), expanded=bool(sugg["langs"])):
            for k in sorted((k for k in OFFICIAL_LANGS if k != "ko"), key=lambda k: k not in sugg["langs"]):
                mark = " · 추천" if k in sugg["langs"] else ""
                trans[k] = (st.text_input(f"{OFFICIAL_LANGS[k]} 제목{mark}", key=f"nf_title_{k}_{fk}"),
                            st.text_area(f"{OFFICIAL_LANGS[k]} 내용{mark}", height=68, key=f"nf_body_{k}_{fk}"))
        cc = st.columns(3)
        places = [""] + DONG_CODES
        place = cc[0].selectbox("장소 동", places,
                                index=places.index(sugg["place"]) if kind == "event" and sugg["place"] in places else 0,
                                format_func=lambda d: DONG_NAME.get(d, "장소 없음"), key=f"nf_place_{fk}")
        day = cc[1].date_input("행사일" if kind == "event" else "게시일",
                               value=next_saturday() if kind == "event" else dt.date.today(), key=f"nf_date_{fk}")
        hour, topic, link = None, ("행사" if kind == "event" else "안내"), ""
        if kind == "event":
            hours = list(range(8, 23))
            hour = cc[2].selectbox("시작 시각", hours, index=hours.index(sugg["hour"]) if sugg["hour"] in hours else 6,
                                   format_func=lambda h: f"{h}시", key=f"nf_hour_{fk}")
        elif kind == "policy":
            topic = cc[2].selectbox("주제", POLICY_TOPICS, key=f"nf_topic_{fk}")
            link = st.text_input("원문 링크 (중앙정부 정책은 링크만, 결정 R5-20)", key=f"nf_link_{fk}")
        submitted = st.form_submit_button("게시하기", type="primary", key=f"nf_submit_{fk}")
    if submitted:
        if not title.strip():
            st.error("제목(한국어 원문)을 입력하세요.")
        else:
            titles, bodies = {"ko": title.strip()}, {"ko": body.strip()}
            for k, (t, b) in trans.items():
                if t.strip():
                    titles[k], bodies[k] = t.strip(), (b.strip() or body.strip())
            target_dongs = dongs if scope == "target" else []
            start = day.isoformat() + (f" {hour:02d}:00" if hour is not None else "")
            try:
                cm.add_notice(kind, topic, titles, bodies, nats, place, start, link.strip(),
                              target_dongs=target_dongs, scope=scope)
            except ValueError as err:
                st.error(str(err))
            else:
                if scope == "target":
                    who = f"맞춤 — 받는 회원 {cm.count_audience(nats, target_dongs)}명(가상 회원 DB)"
                else:
                    who = "모든 주민"
                missing = [OFFICIAL_LANGS[k] for k in sugg["langs"] if k not in titles]
                st.success(f"게시했어요 ({KIND_LABEL[kind]} · {who})"
                           + (f" · 추천 언어 번역 없음: {', '.join(missing)} → 한국어 원문이 보입니다" if missing else ""))
    st.markdown("##### 최근 게시 5건")
    for e in sorted(cm.list_notices(), key=lambda r: -r["id"])[:5]:
        if e["scope"] == "target":
            aud = "맞춤: " + (", ".join(e["target"]) or "국적 무관") + (
                " · " + ", ".join(DONG_NAME.get(d, d) for d in e["target_dongs"]) if e["target_dongs"] else "")
        else:
            aud = "모든 주민"
        st.markdown(f"{chip(KIND_LABEL.get(e['kind'], e['kind']))}{chip(aud, 'off' if e['scope'] == 'target' else '')}"
                    f" **{tr(e['titles'], 'ko')}** <span class='meta'>{e['start_date']} · "
                    f"{'·'.join(OFFICIAL_LANGS.get(k, k) for k in e['titles'])}</span>", unsafe_allow_html=True)


def page_admin_ops(user):
    st.markdown("#### ❓ 공식 Q&A 답변 대기")
    pending = cm.list_questions(pending_only=True)
    if not pending:
        st.caption("대기 중인 질문이 없어요.")
    for q in pending:
        with st.container(border=True):
            st.markdown(f"**{q['title']}** <span class='meta'>{ROOM_SHORT.get(q['language'], '')} · {ago(q['created_at'])}</span>"
                        f"  \n{q['body']}", unsafe_allow_html=True)
            if q["body_ko"]:
                st.caption(f"🌐 {q['body_ko']}")
            with st.form(f"ans_{q['id']}", clear_on_submit=True):
                answer = st.text_area("답변", height=70)
                if st.form_submit_button("답변 등록") and answer.strip():
                    cm.answer_question(q["id"], user["id"], answer.strip())
                    st.rerun()
    st.markdown("#### 🚨 신고 처리 (언어방 리더 1차 검토 → 시 최종 판단)")
    for p in cm.reported_posts():
        with st.container(border=True):
            state = chip("숨김", "hot") if p["is_hidden"] else chip("노출 중")
            st.markdown(f"{state}{chip(ROOM_SHORT[p['room']])} **{p['title']}** · 신고 {p['n_reports']}건 "
                        f"({', '.join(sorted(set(p['reasons'])))})  \n{p['body']}", unsafe_allow_html=True)
            if p["body_ko"]:
                st.caption(f"🌐 {p['body_ko']}")
            b = st.columns(3)
            b[0].button("숨김 유지", key=f"h_{p['id']}", on_click=act, args=(cm.resolve_reports, p["id"], "hide"))
            b[1].button("복구", key=f"r_{p['id']}", on_click=act, args=(cm.resolve_reports, p["id"], "restore"))
            b[2].button("삭제", key=f"d_{p['id']}", on_click=act, args=(cm.resolve_reports, p["id"], "delete"))


SHOP_REASON = {"closed": "문을 닫았어요", "wrong_type": "이런 가게가 아니에요", "wrong_place": "위치가 달라요",
               "other": "다른 문제"}
KIND_KO = {"food": "음식점", "grocery": "식료품·마트", "service": "생활 서비스", "other": "기타"}


@st.cache_data
def app_shops() -> pd.DataFrame:
    path = Path(__file__).resolve().parents[1] / "data" / "public" / "shops_ansan.csv"
    return pd.read_csv(path, dtype=str).set_index("shop_id") if path.exists() else pd.DataFrame()


def page_admin_shops():
    """시민 앱 가게 정보 검수 (결정 13) — 상호로 분류한 가게라 주민 신고를 모아 사람이 고친다."""
    st.markdown("#### 🏪 시민 앱 가게 정보 신고 · 이웃 제보")
    st.caption("가게 목록 = 공공 상가정보에서 업종 · 상호로 고른 것(pipeline/stage_shops.py). 잘못 잡힌 가게는 "
               "data/public/shops_overrides.csv 에 exclude 로 넣고 stage_shops.py 를 다시 돌린다.")
    shops, fb = app_shops(), cm.open_shop_feedback()
    if not fb:
        st.caption("들어온 가게 정보 신고가 없어요.")
    for r in fb:
        name = shops.loc[r["shop_id"], "name"] if r["shop_id"] in shops.index else r["shop_id"]
        dong = shops.loc[r["shop_id"], "dong_name"] if r["shop_id"] in shops.index else ""
        c = st.columns([4, 1])
        c[0].markdown(f"{chip(SHOP_REASON.get(r['reason'], r['reason']), 'warn')} **{name}** "
                      f"<span class='meta'>{dong} · {r['n']}명 · 최근 {r['last'][:10]}</span>", unsafe_allow_html=True)
        c[1].button("확인 완료", key=f"shopfb_{r['shop_id']}_{r['reason']}", on_click=act,
                    args=(cm.close_shop_feedback, r["shop_id"]))
    places = cm.list_app_places()
    if places:
        st.markdown(f"**이웃 제보 장소 {len(places)}곳** (추천 {PLACE_VERIFY_UPVOTES}개면 앱에서 '확인됨')")
        st.dataframe(pd.DataFrame({"이름": [p["name"] for p in places], "종류": [KIND_KO.get(p["kind"], p["kind"]) for p in places],
                                   "동": [DONG_NAME.get(p["dong"], "") for p in places], "추천": [p["votes"] for p in places],
                                   "올린 때": [p["created_at"][:16] for p in places]}), hide_index=True)


def page_admin_kpi():
    st.markdown("#### 📈 성과지표 (KPI)")
    k = cm.kpi_snapshot()
    arrivals = mt.arrivals_by_month()
    members = pd.DataFrame(k["members_by_month"])
    members["month"] = members["ym"].str.replace("-", "")
    rate = arrivals.merge(members, on="month", how="left").fillna(0)
    rate["가입률(%)"] = (rate["n"] / rate["FOR_CNT"].replace(0, np.nan) * 100).round(1)
    c = st.columns(4)
    c[0].metric(f"전입 외국인 대비 가입률 ({rate['month'].iloc[-1]})",
                f"{rate['가입률(%)'].iloc[-1]:.1f}%" if pd.notna(rate["가입률(%)"].iloc[-1]) else "—",
                help="분모 DS-076 은 수도권 다른 시군에서 온 신용정보 보유 외국인뿐 — 지표로 약하다")
    c[1].metric("최근 30일 활동 사용자", f"{k['active_30d']}명", help="글·댓글·추천 활동자 (시드 가상값)")
    if IS_REAL:
        c[2].metric("행사 방문 증가율", "기록 없음", help="시의 실제 행사 기록(날짜 · 동)을 '행사 기획·효과' 탭에 넣으면 잰다")
    else:
        ev = mt.preset_event(EVENTS[-1]["area_cd"])
        up = mt.event_total_uplift(ev["dong"], ev["days"], ev["target"])
        c[2].metric(f"행사 방문 증가율 ({ev['name'][:8]}…)", f"{up:+.0f}%" if pd.notna(up) else "—")
    answered = f"{k['n_answered']}/{k['n_questions']}"
    hours = f" · 평균 {k['avg_answer_hours']:.0f}시간" if k["avg_answer_hours"] else ""
    c[3].metric("공식 Q&A 응답", answered + hours)
    st.altair_chart(alt.Chart(rate).mark_bar().encode(x=alt.X("month:N", title="월"), y="가입률(%):Q"), height=220)
    if IS_REAL:
        st.warning("실데이터 판에서도 가입자 수 · 활동 사용자 · Q&A 는 시연용 시드(가상)입니다 — 운영 전이라 가입률은 "
                   "'실제 전입 대비 가상 가입자'라 값 자체는 의미가 없고, 계산식이 도는지만 확인하는 칸입니다.")
    source("가입률 = 회원 DB 월 신규가입(시드) ÷ DS-076 PUBLIC 외국인 전입 FOR_CNT · 행사 = DS-017 동 단위")


# ------------------------------------------------------------------ main
if SHARE_MODE and "db_path" not in st.session_state:
    st.session_state["db_path"] = str(Path(tempfile.gettempdir()) / f"ansan_neighbors_{uuid.uuid4().hex}.db")
cm.use_db(st.session_state.get("db_path"))
cm.init_db()
# 담당자 한 사람으로 연다 — 시민 시연 사용자(옛 시민 화면 비교용)는 2026-11-20 정리에서 뺐다. 시민 화면 = 휴대폰 앱
user = cm.user_by_persona("official")
with st.sidebar:
    st.markdown("## 🏘️ 안산 이웃 · 운영 콘솔")
    st.caption("안산시 담당자 화면 — 2안 v0.5" + (" · 🔒 실데이터 판" if IS_REAL else ""))
    if SHARE_MODE:  # 공유판 · 드라이브 앱 — 서버 판 앱은 없고, 같은 앱을 파일 하나에 담은 HTML 판(가상)이 함께 간다
        st.info("📱 시민 화면은 **휴대폰 앱**입니다 — 함께 있는 `html/안산이웃_플랫폼.html` 을 내려받아 더블클릭하면 설치 없이 "
                "열립니다([GitHub 저장소의 html 폴더](https://github.com/ph3kim-source/ansan-foreign-community-demo/tree/main/html)). "
                "이 콘솔과는 이어져 있지 않습니다.")
    else:
        st.info("📱 시민 화면은 **휴대폰 앱**입니다 — `앱_실행.bat` 을 실행하면 http://127.0.0.1:8600 에서 열립니다.")
    st.divider()
    if IS_REAL:
        st.markdown("**사용 데이터셋 (민간 실데이터 · 내부 검토용)**  \nDS-017 · DS-014 · DS-056(외국인 전체) · "
                    "DS-076/077(PUBLIC) + 공표 외국인주민 통계")
    else:
        st.markdown("**사용 데이터셋 (모두 가상)**  \nDS-017 · DS-014 · DS-056 · DS-076/077 · DS-032 "
                    "+ 공표 외국인주민 통계(실제 값)")
    if not SHARE_MODE:  # 공유판 · 드라이브 앱에는 docs/ 를 담지 않는다
        st.caption("근거: docs/기획_결정사항.md · 남은 일: docs/진행상황.md")
    if st.button("커뮤니티 DB 초기화"):
        cm.init_db(reset=True)
        st.rerun()

badge()
if SHARE_MODE:
    st.caption("공유 시연판 · 안산시 공식 서비스가 아닙니다 · 글·댓글·신고는 이 브라우저 세션에만 저장되고 "
               "새로고침하면 처음 상태로 돌아갑니다.")
# v0.4 '기능 줄이기'(사용자 결정 2026-11-18): 관리자 탭 7 → 4. 격자 · KPI 는 동향 탭 안 접힌 칸으로,
# 공지 작성 · Q&A · 신고 · 가게 신고는 '공지·소통' 한 탭으로 합쳤다.
tabs = st.tabs(["📊 생활권 동향", "🎪 행사 기획·효과", "🧭 외국인 변화", "📣 공지·소통"])
with tabs[0]:
    page_admin_trends()
    st.divider()
    with st.expander("🔥 50m 격자 지도 (관리자 전용)"):
        page_admin_grid()
    with st.expander("📈 운영 지표 (KPI)"):
        page_admin_kpi()
with tabs[1]:
    page_admin_events()
with tabs[2]:
    page_admin_migration()
with tabs[3]:
    page_admin_notice(user)
    st.divider()
    page_admin_ops(user)
    st.divider()
    page_admin_shops()
