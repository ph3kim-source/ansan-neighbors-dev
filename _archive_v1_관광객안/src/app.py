# -*- coding: utf-8 -*-
"""2안 — 안산 외국인 인구·업종 현황판

주 데이터(DS-056·026·048) 수급 전의 baseline 이다. 서비스가 아니다.
5대 기준 자체 판정에서 3개 미달이며 그 사유를 「근거 대장」 탭에 그대로 둔다.

화면에 올리는 것은 A등급(보유 데이터로 직접 산출)과 원자료 전사뿐이다.
C등급 구성물 — 생활 목적군 · 점포 국적 판별 · 동 단위 국적 추정 — 은
만들지 않았고, 왜 만들지 않았는지를 「근거 대장」에 적었다.

실행  streamlit run src/app.py
"""
import json
import os
import re
import sys

import pandas as pd
import plotly.express as px
import pydeck as pdk
import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import params  # noqa: E402
import survey  # noqa: E402

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROC = os.path.join(BASE, "data", "processed")
POI = os.path.join(BASE, "..", "4안", "data", "processed", "poi.csv")
GEO = os.path.join(BASE, "..", "4안", "data", "processed", "dong.geojson")

st.set_page_config(page_title="2안 · 안산 외국인 인구·업종 현황판",
                   layout="wide", page_icon="🗺️")


# ══ 데이터 ═══════════════════════════════════════════════════
@st.cache_data
def load_csv(name):
    return pd.read_csv(os.path.join(PROC, name), encoding="utf-8-sig")


@st.cache_data
def load_poi():
    df = pd.read_csv(POI, encoding="utf-8-sig")
    return df.rename(columns={"상권업종소분류명": "업종", "행정동명": "동"})


@st.cache_data
def load_geo():
    with open(GEO, encoding="utf-8") as f:
        gj = json.load(f)
    for ft in gj["features"]:
        ft["properties"] = {"동": re.sub(r"\s+", "", ft["properties"]["ADM_NM"])}
    return gj


@st.cache_data
def load_validate():
    p = os.path.join(PROC, "validate.json")
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else None


DONG = load_csv("dong_month.csv")
GUNAT = load_csv("gu_nat_month.csv")
POIDF = load_poi()
GJ = load_geo()
VAL = load_validate()
MONTHS = sorted(DONG["ym"].unique())

# ══ 사이드바 ═════════════════════════════════════════════════
st.sidebar.header("기준")
ym = st.sidebar.selectbox("기준월", MONTHS, index=len(MONTHS) - 1)
st.sidebar.caption("안산시 「외국인주민 통계」 %d개월 보유 (%s ~ %s)"
                   % (len(MONTHS), MONTHS[0], MONTHS[-1]))
show_daebu = st.sidebar.checkbox("대부동(대부도) 포함", value=False,
                                 help=params.VIEW_DEFAULT.basis)
st.sidebar.divider()
g = params.summary()
st.sidebar.metric("파라미터 등급", "A %d · B %d · C %d · X %d"
                  % (g["A"], g["B"], g["C"], g["X"]))
ok, tot = params.criteria_summary()
st.sidebar.metric("5대 기준 자체 판정", "충족 %d / %d" % (ok, tot))
st.sidebar.caption("미달 사유는 「근거 대장」 탭에 그대로 적혀 있습니다.")

D = DONG[DONG["ym"] == ym].copy()
if not show_daebu:
    D = D[D["dong"] != "대부동"]
D["외국인비중"] = D["foreign_resident"] / D["pop_total"]
G = GUNAT[GUNAT["ym"] == ym].copy()

# ══ 헤더 ═════════════════════════════════════════════════════
st.title("안산 외국인 인구·업종 현황판")
st.caption("2안 · 주 데이터(DS-056·026·048) 수급 전 baseline · 기준월 %s" % ym)

st.warning(
    "**이것은 서비스가 아니라 현황판입니다.** 5대 기준 자체 판정에서 "
    "①데이터 실종 테스트 ③시민 중심성 ④멀티데이터 결합 **3개가 미달**입니다. "
    "86종 민간데이터를 한 건도 쓰지 못했고, 안산시 공표 통계와 공공데이터로만 "
    "구성했습니다. 사유는 「근거 대장」 탭에 있습니다.", icon="⚠️")

k = st.columns(5)
k[0].metric("행정동", "%d개" % len(D))
k[1].metric("외국인주민", "%s명" % format(int(D["foreign_resident"].sum()), ","),
            "총인구의 %.1f%%" % (100 * D["foreign_resident"].sum() / D["pop_total"].sum()))
k[2].metric("관측 국적", "%d개" % G["nat"].nunique(), "구 단위")
k[3].metric("상가 점포", "%s곳" % format(len(POIDF), ","), "업종 %d종" % POIDF["업종"].nunique())
top = D.loc[D["외국인비중"].idxmax()]
k[4].metric("최대 밀집 동", top["dong"], "동 인구의 %.1f%%" % (100 * top["외국인비중"]))

t0, t1, t2, t3, t4 = st.tabs(
    ["🗺️ 동별 인구", "🌏 국적 · 체류자격", "🏪 업종 분포",
     "🙋 수요 — 사람들이 답한 것", "📋 근거 대장"])


# ══ 탭 0 · 동별 인구 ═════════════════════════════════════════
with t0:
    st.subheader("동별 외국인주민")
    st.caption("공표 통계 원값입니다. 나눗셈 외의 가공이 없습니다. (%s)"
               % params.FOREIGN_SHARE.grade + " 등급 A")

    dv = D.copy()
    dv["fill"] = (dv["외국인비중"] / dv["외국인비중"].max() * 255).astype(int)
    fill = {r["dong"]: r["fill"] for _, r in dv.iterrows()}
    feats = [f for f in GJ["features"] if f["properties"]["동"] in fill]
    for f in feats:
        v = fill[f["properties"]["동"]]
        f["properties"]["color"] = [40 + v // 2, 130 - v // 4, 110 - v // 5, 190]
        row = dv[dv["dong"] == f["properties"]["동"]].iloc[0]
        f["properties"]["tip"] = "%s · 외국인주민 %s명 (%.1f%%)" % (
            row["dong"], format(int(row["foreign_resident"]), ","),
            100 * row["외국인비중"])

    c1, c2 = st.columns([1.4, 1])
    with c1:
        st.pydeck_chart(pdk.Deck(
            map_style=None,
            initial_view_state=pdk.ViewState(latitude=37.31, longitude=126.83,
                                             zoom=10.4 if show_daebu else 11.4),
            layers=[pdk.Layer("GeoJsonLayer",
                              {"type": "FeatureCollection", "features": feats},
                              stroked=True, filled=True, get_fill_color="properties.color",
                              get_line_color=[255, 255, 255, 160], line_width_min_pixels=1,
                              pickable=True)],
            tooltip={"text": "{tip}"}))
    with c2:
        show = dv[["dong", "gu", "pop_total", "foreign_resident",
                   "reg_foreign", "diaspora", "외국인비중"]].sort_values(
            "외국인비중", ascending=False)
        show.columns = ["동", "구", "총인구", "외국인주민", "등록외국인", "동포", "비중"]
        st.dataframe(show, hide_index=True, height=430,
                     column_config={"비중": st.column_config.ProgressColumn(
                         "비중", format="%.1f%%", min_value=0.0, max_value=1.0)})

    st.divider()
    st.subheader("%d개월 추이" % len(MONTHS))
    H = DONG.copy()
    if not show_daebu:
        H = H[H["dong"] != "대부동"]
    sel = st.multiselect("동 선택", sorted(H["dong"].unique()),
                         default=list(show["동"].head(5)))
    if sel:
        st.plotly_chart(px.line(H[H["dong"].isin(sel)], x="ym", y="foreign_resident",
                                color="dong", markers=True,
                                labels={"ym": "월", "foreign_resident": "외국인주민(명)",
                                        "dong": "동"}),
                        width='stretch')
    st.caption("%d개월은 계절성을 판단하기에 부족합니다. 단기 증감 방향까지만 읽으십시오."
               % len(MONTHS))


# ══ 탭 1 · 국적 · 체류자격 ═══════════════════════════════════
with t1:
    st.info("국적별 수치는 **구(상록/단원) 단위까지만** 존재합니다. "
            "행정동 단위 국적 분포는 어느 공표 자료에도 없고, 추정도 하지 않았습니다. "
            "(`DONG_NAT_ESTIMATE` = C등급 · 「근거 대장」 참조)", icon="ℹ️")

    piv = G.pivot_table(index="nat", columns="gu", values="total_all",
                        aggfunc="sum").fillna(0)
    piv["합계"] = piv.sum(axis=1)
    piv = piv[piv["합계"] >= 30].sort_values("합계", ascending=False)
    piv["단원구 비중"] = piv.get("단원구", 0) / piv["합계"]

    c1, c2 = st.columns([1, 1])
    with c1:
        st.subheader("국적별 외국인주민")
        st.dataframe(piv.reset_index().rename(columns={"nat": "국적"}),
                     hide_index=True, height=420,
                     column_config={"단원구 비중": st.column_config.ProgressColumn(
                         "단원구 비중", format="%.1f%%", min_value=0.0, max_value=1.0)})
        st.caption(params.TOTAL_ALL.basis.split("★ ")[1][:180] + " …")
    with c2:
        st.subheader("체류자격 구조")
        STAY = [("employ_permit", "고용허가"), ("visit_work", "방문취업"),
                ("marriage", "결혼이민"), ("study", "유학·연수"),
                ("professional", "전문인력"), ("refugee", "난민"),
                ("visit_family", "방문동거"), ("permanent", "영주")]
        rows = []
        for gu in ("단원구", "상록구"):
            sub = G[G["gu"] == gu]
            base = sub["reg_foreign"].sum()
            for col, lab in STAY:
                rows.append({"구": gu, "체류자격": lab,
                             "비중": sub[col].sum() / base if base else 0})
        sd = pd.DataFrame(rows)
        st.plotly_chart(px.bar(sd, x="비중", y="체류자격", color="구",
                               barmode="group", orientation="h",
                               labels={"비중": "등록외국인 대비 비중"}),
                        width='stretch')
        w = sd.pivot(index="체류자격", columns="구", values="비중")
        w["배수"] = w["단원구"] / w["상록구"].replace(0, pd.NA)
        st.dataframe(w.reset_index(), hide_index=True,
                     column_config={c: st.column_config.NumberColumn(c, format="%.1f%%")
                                    for c in ("단원구", "상록구")})
        st.caption("같은 시 안에서 두 구가 다른 구조를 가집니다 — "
                   "단원구는 고용허가(노동), 상록구는 유학·연수(학생) 쪽으로 기웁니다.")


# ══ 탭 2 · 업종 분포 ═════════════════════════════════════════
with t2:
    st.subheader("업종별 입지계수 (LQ)")
    st.info("**업종을 묶지 않았습니다.** 「2안 근거.md」 파라미터 #9가 업종 그룹을 "
            "C등급(카드 업종코드 전체 목록 없음)으로 판정해 두었습니다. "
            "생활 목적군을 임의로 정의하면 그 묶음이 결과를 좌우하므로, "
            "업종소분류를 그대로 고르게 했습니다. (`BIZ_GROUP` = X등급)", icon="ℹ️")

    dong_n = POIDF.groupby("동").size()
    biz_all = POIDF.groupby("업종").size().sort_values(ascending=False)
    N = len(POIDF)
    pick = st.selectbox("업종소분류 (%d종 · 점포 많은 순)" % len(biz_all),
                        biz_all.index.tolist(),
                        format_func=lambda b: "%s (%s곳)" % (b, format(int(biz_all[b]), ",")))

    cnt = POIDF[POIDF["업종"] == pick].groupby("동").size()
    lq = pd.DataFrame({"점포수": cnt}).reindex(dong_n.index).fillna(0)
    lq["동전체점포"] = dong_n
    lq["LQ"] = (lq["점포수"] / lq["동전체점포"]) / (biz_all[pick] / N)
    lq = lq.reset_index().rename(columns={"index": "동", "동": "동"})
    lq = lq.merge(D[["dong", "외국인비중"]], left_on="동", right_on="dong", how="inner")

    # min 결합 — 가중치 없음 (params.COMBINE, A등급)
    lq["외국인비중 분위"] = lq["외국인비중"].rank(pct=True)
    lq["LQ 분위"] = lq["LQ"].rank(pct=True)
    lq["동시분위(min)"] = lq[["외국인비중 분위", "LQ 분위"]].min(axis=1)
    lq = lq.sort_values("동시분위(min)", ascending=False)

    c1, c2 = st.columns([1.3, 1])
    with c1:
        st.plotly_chart(px.scatter(
            lq, x="외국인비중", y="LQ", text="동", size="점포수",
            labels={"외국인비중": "동 인구 중 외국인 비중", "LQ": "%s LQ" % pick},
            title="외국인 비중 × %s 입지계수" % pick).update_traces(
                textposition="top center").add_hline(
                y=1, line_dash="dot", line_color="gray"),
            width='stretch')
        st.caption("가로축·세로축 모두 실측에서 산술로만 나온 값입니다. "
                   "LQ=1 점선은 안산 평균입니다. **두 축이 같이 높다고 해서 "
                   "그 점포를 외국인이 이용한다는 뜻은 아닙니다** — 이용자 정보는 "
                   "어느 보유 데이터에도 없습니다.")
    with c2:
        st.dataframe(
            lq[["동", "점포수", "LQ", "외국인비중", "동시분위(min)"]],
            hide_index=True, height=430,
            column_config={
                "LQ": st.column_config.NumberColumn("LQ", format="%.2f"),
                "외국인비중": st.column_config.NumberColumn("외국인비중", format="%.1f%%"),
                "동시분위(min)": st.column_config.ProgressColumn(
                    "동시분위(min)", format="%.2f", min_value=0.0, max_value=1.0)})
        st.caption("**동시분위 = min(외국인비중 분위, LQ 분위)** — 가중합이 아닙니다. "
                   "3안은 가중치 변경으로 경로의 98%가, 4안은 집결지의 50~85%가 "
                   "뒤바뀌어 가중합을 폐기했습니다. min 은 가중치가 없습니다.")


# ══ 탭 3 · 수요 ══════════════════════════════════════════════
with t3:
    st.subheader("정착 시 장애요인")
    st.caption("안산시 「사회조사」 2024 · %s p.%d · 원값 전사"
               % (survey.SOURCE, survey.BARRIER_PAGE))

    b24 = survey.BARRIER_YEAR["2024"]
    bd = pd.DataFrame({"장애요인": survey.BARRIER_LABELS, "비중": b24})
    c1, c2 = st.columns([1, 1])
    with c1:
        st.plotly_chart(px.bar(bd.sort_values("비중"), x="비중", y="장애요인",
                               orientation="h", text="비중",
                               labels={"비중": "%"}), width='stretch')
    with c2:
        reach = pd.DataFrame([
            {"장애요인": l, "비중(%)": b24[i],
             "현황판이 닿는가": survey.BARRIER_REACH[l][0],
             "비고": survey.BARRIER_REACH[l][1]}
            for i, l in enumerate(survey.BARRIER_LABELS)])
        st.dataframe(reach, hide_index=True)
        st.error("**상위 2개 합계 73.1%는 이 화면으로 해소되지 않습니다.** "
                 "사람들이 어렵다고 답한 것은 문화적 차이와 사회적 편견입니다. "
                 "이것이 5대 기준 ③시민 중심성 '미달' 판정의 근거입니다.", icon="🚫")

    st.warning(params.SURVEY_SCOPE.basis, icon="⚠️")

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**구별 · 연령별**")
        st.dataframe(pd.DataFrame(survey.BARRIER_GU, index=survey.BARRIER_LABELS).T
                     .reset_index().rename(columns={"index": "구"}), hide_index=True)
        st.dataframe(pd.DataFrame(survey.BARRIER_AGE, index=survey.BARRIER_LABELS).T
                     .reset_index().rename(columns={"index": "연령"}), hide_index=True)
    with c2:
        st.markdown("**연도별 추이**")
        yr = pd.DataFrame(survey.BARRIER_YEAR, index=survey.BARRIER_LABELS).T
        st.plotly_chart(px.line(yr, markers=True,
                                labels={"index": "연도", "value": "%", "variable": "장애요인"}),
                        width='stretch')

    st.divider()
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("보건소 이용")
        st.caption("2024 · p.%d · 단위 명" % survey.HEALTH_PAGE)
        hd = pd.DataFrame(survey.HEALTH_ROWS, index=survey.HEALTH_FIELDS).T
        hd.insert(0, "계", [survey.HEALTH_TOTAL[k] for k in hd.index])
        st.dataframe(hd.reset_index().rename(columns={"index": "구분"}), hide_index=True)
        st.caption("외국인 이용자 6,878명은 안산시 전체의 5.5%입니다. 분야 구성이 "
                   "다릅니다 — **교육 15.4%**(전체 9.0%) / 검사 5.6%(전체 45.9%). "
                   "그리고 **교육 1,061명이 전원 단원구**이고 상록구는 0입니다.")
    with c2:
        st.subheader("공공도서관")
        st.caption("2024 · p.%d · 등록회원 %s명"
                   % (survey.LIB_PAGE, format(survey.LIB_TOTAL, ",")))
        ld = pd.DataFrame(survey.LIB_MEMBERS, columns=["국적", "등록회원", "1인당 대출"])
        ld["구성비"] = ld["등록회원"] / survey.LIB_TOTAL
        st.dataframe(ld, hide_index=True,
                     column_config={"구성비": st.column_config.NumberColumn(
                         "구성비", format="%.1f%%")})
        st.caption(f"회원은 중국이 73.5%로 압도적이지만 **1인당 대출 1위는 "
                   f"우즈베키스탄 8.2권**입니다(전체 평균 {survey.LIB_AVG:.1f}권).")

    st.info("사람들이 실제로 쓰는 것은 보건소 교육·도서관 같은 **공공시설**인데, "
            "소상공인 상가정보에는 공공시설이 없어 이 화면에 한 칸도 담기지 못했습니다.",
            icon="ℹ️")


# ══ 탭 4 · 근거 대장 ═════════════════════════════════════════
with t4:
    st.subheader("5대 기준 자체 판정")
    st.caption("매뉴얼 — \"기준에 미달하는 아이디어는 스스로 탈락시키고 "
               "그 이유를 기록하십시오\"")
    for c in params.CRITERIA:
        icon = "✅" if c["verdict"] == "충족" else "❌"
        with st.expander("%s %d. %s — **%s**" % (icon, c["no"], c["name"], c["verdict"]),
                         expanded=(c["verdict"] != "충족")):
            st.write(c["why"])
            if c["fix"]:
                st.caption("해소 조건 · %s" % c["fix"])

    st.divider()
    st.subheader("파라미터 등급")
    gg = params.summary()
    st.caption("A 보유 데이터로 직접 산출 · B 타당성 확인 + 판단 혼입 · "
               "C 근거 없음 · X 근거 불필요 — 현재 **A %d · B %d · C %d · X %d**"
               % (gg["A"], gg["B"], gg["C"], gg["X"]))
    pd_rows = [{"파라미터": p.name, "값": str(p.value), "등급": p.grade,
                "근거": p.basis, "출처": p.source,
                "등급을 올리려면": p.replace or p.need or "-"} for p in params.P]
    st.dataframe(pd.DataFrame(pd_rows), hide_index=True, height=360)

    st.error("**C등급 2건은 화면에 올리지 않았습니다.** "
             "`DONG_NAT_ESTIMATE`(동 단위 국적 분포)와 `STORE_NAT`(점포 국적 판별)입니다. "
             "둘 다 초판 프로토타입에는 들어가 있었고, 검증에서 반박되어 제거했습니다.",
             icon="🚫")

    if VAL:
        st.divider()
        st.subheader("검증 기록")
        st.caption("`python src/validate.py` 출력 · 기준월 %s" % VAL["ym"])
        for c in VAL["checks"]:
            icon = "✅" if c["ok"] else "🚫"
            with st.expander("%s %s %s" % (icon, c["no"], c["title"])):
                st.code("\n".join(c["detail"]), language=None)
                if c["grade_note"]:
                    st.caption("→ " + c["grade_note"])
    else:
        st.info("`python src/validate.py` 를 먼저 실행하면 검증 기록이 여기 표시됩니다.")

    st.divider()
    st.subheader("자료")
    st.markdown("""
- 안산시 「외국인주민 통계」 %s ~ %s (%d개월)
- 안산시 「다문화·외국인가구통계」 2025 공표 (233p)
- 소상공인시장진흥공단 상가(상권)정보 2026.06
- 행정동 경계 SGIS (`4안/data/processed/dong.geojson`)

금액·개인정보는 다루지 않습니다. 통신·카드 데이터는 아직 한 건도 수급하지 못했습니다.
""" % (MONTHS[0], MONTHS[-1], len(MONTHS)))
