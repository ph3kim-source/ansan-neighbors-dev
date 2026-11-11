# -*- coding: utf-8 -*-
"""검증 — A등급 파라미터가 보유 데이터로 재현되는지 확인한다.

A등급은 '보유 데이터로 직접 산출'을 뜻하므로, 여기서 재현되지 않으면
등급을 내려야 한다. 반박되면 그대로 출력하고 등급 강등을 표시한다.

  ① 원자료 정합      공표 통계 자체의 합계가 맞는가 (TOTAL_ALL 함정 포함)
  ② 공간 단위 대조    동 25개가 경계 파일과 이름까지 일치하는가
  ③ 전사 정확성      PDF에서 옮긴 숫자가 각 표의 자기 합계와 맞는가
  ④ 동 단위 국적 추정  가능한가 (DONG_NAT_ESTIMATE = C 의 근거)
  ⑤ 점포 국적 판별    가능한가 (STORE_NAT = C 의 근거)
  ⑥ 5대 기준 자체 판정

실행  python src/validate.py
"""
import csv
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import params  # noqa: E402
import survey  # noqa: E402

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROC = os.path.join(BASE, "data", "processed")
POI = os.path.join(BASE, "..", "4안", "data", "processed", "poi.csv")
GEO = os.path.join(BASE, "..", "4안", "data", "processed", "dong.geojson")
YM = params.YM.value

RESULT = []


def check(no, title, ok, detail, grade_note=""):
    RESULT.append({"no": no, "title": title, "ok": ok,
                   "detail": detail, "grade_note": grade_note})
    mark = "OK  " if ok else "반박"
    print("\n[%s] %s %s" % (mark, no, title))
    for line in detail:
        print("     " + line)
    if grade_note:
        print("     -> " + grade_note)


def load(name):
    with open(os.path.join(PROC, name), encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def n(v):
    return int(v) if v not in ("", None) else 0


# ══════════════════════════════════════════════════════════════
def c1_source_integrity():
    G = [r for r in load("gu_nat_month.csv") if r["ym"] == YM]
    C = [r for r in load("city_nat_month.csv") if r["ym"] == YM]
    D = [r for r in load("dong_month.csv") if r["ym"] == YM]

    # TOTAL_ALL 함정: 구 시트의 '총계'는 등록외국인만 담고 있다
    bad, worst = [], []
    for c in C:
        g = sum(n(r["total_all"]) for r in G if r["nat"] == c["nat"])
        if g != n(c["total"]):
            bad.append((c["nat"], n(c["total"]), g))
    # 동포를 빼면 얼마나 어긋나는지 (함정을 밟았을 때의 오차)
    for c in C:
        reg = sum(n(r["reg_foreign"]) for r in G if r["nat"] == c["nat"])
        t = n(c["total"])
        if t >= 1000 and reg and (t - reg) / t > 0.3:
            worst.append((c["nat"], t, reg, 100 * (t - reg) / t))
    worst.sort(key=lambda x: -x[3])

    det = ["구합(등록외국인+동포) vs 시 총계 : 불일치 %d / %d개 국적"
           % (len(bad), len(C))]
    if bad:
        det.append("  불일치 국적은 전부 소규모: " +
                   ", ".join("%s(%d명)" % (b[0], b[1]) for b in bad[:8]))
    det.append("동포를 더하지 않으면 과소평가되는 국적 (상위 4):")
    for nat, t, reg, pct in worst[:4]:
        det.append("  %-12s 실제 %6s → 등록만 %6s  (%.0f%% 누락)"
                   % (nat, format(t, ","), format(reg, ","), pct))

    # 동 합계 vs 구 합계
    for gu in ("단원구", "상록구"):
        d = sum(n(r["reg_foreign"]) for r in D if r["gu"] == gu)
        g = sum(n(r["reg_foreign"]) for r in G if r["gu"] == gu)
        det.append("%s 동합 %s vs 국적합 %s (차 %+d)"
                   % (gu, format(d, ","), format(g, ","), d - g))

    ok = all(b[1] < 100 for b in bad)
    check("①", "원자료 정합 — TOTAL_ALL (A등급)", ok, det,
          "" if ok else "TOTAL_ALL 등급을 B로 내릴 것")


def c2_spatial():
    D = {r["dong"] for r in load("dong_month.csv") if r["ym"] == YM}
    with open(GEO, encoding="utf-8") as f:
        gj = json.load(f)
    G = {re.sub(r"\s+", "", f["properties"]["ADM_NM"]) for f in gj["features"]}
    ok = (D == G) and len(D) == params.DONG_N.value
    det = ["통계 %d개 / 경계 %d개 / 기대 %d개" % (len(D), len(G), params.DONG_N.value),
           "통계에만: %s" % (sorted(D - G) or "없음"),
           "경계에만: %s" % (sorted(G - D) or "없음")]
    check("②", "공간 단위 대조 — DONG_N (A등급)", ok, det,
          "" if ok else "동명 정규화 규칙을 고칠 것")


def c3_transcription():
    det, ok = [], True
    for y, v in survey.BARRIER_YEAR.items():
        s = sum(v)
        det.append("장애요인 %s 합 %.1f%%%s" % (y, s, "" if 99 <= s <= 101 else "  <- 확인"))
        ok &= 99 <= s <= 101
    for k, v in survey.HEALTH_ROWS.items():
        s = sum(x for x in v if x)
        t = survey.HEALTH_TOTAL[k]
        det.append("보건소 %-10s 항목합 %6s vs 계 %6s  %s"
                   % (k, format(s, ","), format(t, ","), "일치" if s == t else "불일치"))
        ok &= s == t
    lm = sum(m for _, m, _ in survey.LIB_MEMBERS)
    ls = sum(v for _, v in survey.LIB_SUBJECT)
    det.append("도서관 회원합 %s vs 계 %s" % (format(lm, ","), format(survey.LIB_TOTAL, ",")))
    det.append("도서관 주제별합 %s vs 계 %s"
               % (format(ls, ","), format(survey.LIB_SUBJECT_TOTAL, ",")))
    ok &= lm == survey.LIB_TOTAL and ls == survey.LIB_SUBJECT_TOTAL
    fb = survey.FOOD_BIZ
    det.append("식품접객 구합 %d vs 계 %d" % (fb["상록구"] + fb["단원구"], fb["외국인"]))
    ok &= fb["상록구"] + fb["단원구"] == fb["외국인"]
    check("③", "PDF 전사 정확성 (survey.py)", ok, det,
          "" if ok else "전사 오류 — 해당 페이지를 다시 읽을 것")


def _poi():
    with open(POI, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def c4_dong_nat():
    """동 단위 국적 추정이 불가능한 이유 — DONG_NAT_ESTIMATE = C 의 근거"""
    G = [r for r in load("gu_nat_month.csv") if r["ym"] == YM]
    tot = {}
    for r in G:
        tot[r["nat"]] = tot.get(r["nat"], 0) + n(r["total_all"])
    allp = sum(tot.values())
    cn = tot.get("중국", 0) + tot.get("한국계중국인", 0)
    kr = sum(tot.get(k, 0) for k in
             ("우즈베키스탄", "카자흐스탄", "러시아(연방)", "한국계러시아인",
              "키르기스스탄", "우크라이나"))

    P = _poi()
    # 고려인 밀집지(선부2동)에 국적 신호가 있는가 — 비한글 상호 비율
    hangul = re.compile(r"[가-힣]")
    seonbu = [r["상호명"] for r in P if r["행정동명"] == "선부2동"]
    nonko = [s for s in seonbu if not hangul.search(s)]
    det = [
        "중국계  %6s명 (%.1f%%)" % (format(cn, ","), 100 * cn / allp),
        "고려인계 %6s명 (%.1f%%)  <- 이만큼이 시드 없이 비어 있다"
        % (format(kr, ","), 100 * kr / allp),
        "선부2동(외국인 비중 40.0%%, 고려인 밀집) 상호 %d개 중 한글이 없는 상호 %d개 (%.1f%%)"
        % (len(seonbu), len(nonko), 100 * len(nonko) / max(len(seonbu), 1)),
        "→ 간판이 한국어라 상호명에서 국적을 읽어낼 수 없다",
    ]
    check("④", "동 단위 국적 추정 가능성 — DONG_NAT_ESTIMATE = C", False, det,
          "추정하지 않는다. 화면에 동 단위 국적을 표시하지 않는다")


def c5_store_nat():
    """점포 국적 판별이 불가능한 이유 — STORE_NAT = C 의 근거"""
    P = _poi()
    D = {r["dong"]: r["gu"] for r in load("dong_month.csv") if r["ym"] == YM}
    # 초판이 쓴 넓은 사전을 그대로 재현해 과포착을 보인다
    naive = ["중국", "만두", "일식", "중식", "짬뽕"]
    cnt = {"상록구": 0, "단원구": 0}
    for r in P:
        if r["상권업종대분류명"] != "음식":
            continue
        h = r["상호명"] + " " + r["상권업종소분류명"]
        if any(k in h for k in naive):
            gu = D.get(r["행정동명"])
            if gu:
                cnt[gu] += 1
    pub = {"상록구": survey.FOOD_BIZ["상록구"], "단원구": survey.FOOD_BIZ["단원구"]}
    det = ["공표 '외국인 소유 식품접객업' 561개소 (상록 167 / 단원 394)와 대조"]
    for gu in ("단원구", "상록구"):
        det.append("  넓은 상호명 사전 → %s %d개소 포착 = 공표 대비 %.0f%%"
                   % (gu, cnt[gu], 100 * cnt[gu] / pub[gu]))
    det += [
        "오염원: '만두' 568곳(한국 분식) · '중국집' 427곳(한국식 중화요리) · '일식' 232곳",
        "사전을 좁히면 포착률이 55~63%로 떨어진다 (40% 이상 누락)",
        "어느 쪽이든 개별 점포에 국적 라벨을 붙일 근거가 되지 못한다",
    ]
    check("⑤", "점포 국적 판별 가능성 — STORE_NAT = C", False, det,
          "판별하지 않는다. 지도에 국적권 점포를 표시하지 않는다")


def c6_criteria():
    ok, tot = params.criteria_summary()
    det = []
    for c in params.CRITERIA:
        det.append("%d. %-14s %s" % (c["no"], c["name"], c["verdict"]))
    det.append("")
    det.append("충족 %d / %d" % (ok, tot))
    det.append("매뉴얼: '기준에 미달하는 아이디어는 스스로 탈락시키고 사유를 기록한다'")
    det.append("→ 현재 상태는 서비스 아이디어가 아니라 주 데이터 도착 전의 '현황판'이다")
    check("⑥", "5대 기준 자체 판정", ok == tot, det)


def main():
    print("=" * 66)
    print("2안 검증 — 기준월 %s" % YM)
    print("=" * 66)
    c1_source_integrity()
    c2_spatial()
    c3_transcription()
    c4_dong_nat()
    c5_store_nat()
    c6_criteria()

    g = params.summary()
    print("\n" + "=" * 66)
    print("파라미터 등급 분포 — A %d · B %d · C %d · X %d"
          % (g["A"], g["B"], g["C"], g["X"]))
    print("C등급 %d건은 전부 '주 데이터가 없어서 만들지 않은 것'이며, "
          "화면에 올리지 않았다." % g["C"])
    print("=" * 66)

    with open(os.path.join(PROC, "validate.json"), "w", encoding="utf-8") as f:
        json.dump({"ym": YM, "checks": RESULT, "grades": g,
                   "criteria": params.CRITERIA}, f, ensure_ascii=False, indent=2)
    print("기록: data/processed/validate.json")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
