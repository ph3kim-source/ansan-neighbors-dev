# -*- coding: utf-8 -*-
"""문서 생성 — params.py 를 근거로 docs/ 를 만든다.

코드와 문서가 어긋나지 않게 하기 위해 문서를 손으로 쓰지 않는다.
등급이 바뀌면 이 스크립트를 다시 돌린다.

실행  python src/gen_docs.py
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import params  # noqa: E402

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS = os.path.join(BASE, "docs")
PROC = os.path.join(BASE, "data", "processed")


def ledger():
    g = params.summary()
    L = ["# 2안 근거 대장",
         "",
         "> `src/params.py` 에서 자동 생성됩니다. 직접 고치지 마십시오.",
         "> 등급 · **A** 보유 데이터로 직접 산출 · **B** 타당성 확인 + 판단 혼입 ·",
         "> **C** 근거 없음 · **X** 근거 불필요(시민이 정하는 값)",
         "",
         "**분포 — A %d · B %d · C %d · X %d**" % (g["A"], g["B"], g["C"], g["X"]),
         ""]

    for grade in ("C", "B", "A", "X"):
        ps = [p for p in params.P if p.grade == grade]
        if not ps:
            continue
        L += ["---", "", "## %s등급 (%d건)" % (grade, len(ps)), ""]
        for p in ps:
            L.append("### `%s` = %s" % (p.name, p.value))
            L.append("")
            L.append(p.basis)
            L.append("")
            if p.source:
                L.append("- 출처 · %s" % p.source)
            if p.replace:
                L.append("- 등급을 올리려면 · %s" % p.replace)
            if p.need:
                L.append("- 요청할 자료 · %s" % p.need)
            if p.note:
                L.append("- 참고 · %s" % p.note)
            L.append("")
    return "\n".join(L)


def criteria():
    ok, tot = params.criteria_summary()
    L = ["# 2안 5대 기준 자체 판정",
         "",
         "> `src/params.py` 에서 자동 생성됩니다.",
         "> 매뉴얼 — \"기준에 미달하는 아이디어는 스스로 탈락시키고 그 이유를 기록하십시오\"",
         "",
         "**충족 %d / %d**" % (ok, tot),
         "",
         "| # | 기준 | 판정 | 해소 조건 |",
         "|---|---|---|---|"]
    for c in params.CRITERIA:
        mark = "충족" if c["verdict"] == "충족" else "**미달**"
        L.append("| %d | %s | %s | %s |" % (c["no"], c["name"], mark, c["fix"] or "—"))
    L += ["", "---", ""]
    for c in params.CRITERIA:
        L += ["## %d. %s — %s" % (c["no"], c["name"], c["verdict"]), "", c["why"], ""]
        if c["fix"]:
            L += ["**해소 조건** · %s" % c["fix"], ""]
    L += ["---", "",
          "## 결론", "",
          "5대 기준 %d개 미달로, 현재 산출물은 **서비스 아이디어가 아니라 "
          "주 데이터 수급 전의 현황판(baseline)** 입니다." % (tot - ok),
          "미달 3건은 전부 `DS-056`(국적×업종×소비)을 비롯한 민간데이터 미수급에서 "
          "비롯되며, 수급되면 ①④는 즉시 해소됩니다.",
          "③시민 중심성은 데이터가 와도 자동으로 해소되지 않습니다 — "
          "정착 장애요인 1·2위(문화적 차이 39.5% · 사회적 편견 33.6%, 합계 73.1%)는 "
          "상권 데이터로 풀리는 문제가 아니기 때문입니다.", ""]
    return "\n".join(L)


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    os.makedirs(DOCS, exist_ok=True)
    for name, text in (("근거대장.md", ledger()), ("5대기준_판정.md", criteria())):
        path = os.path.join(DOCS, name)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        print("docs/%-18s %5d자" % (name, len(text)))

    g = params.summary()
    ok, tot = params.criteria_summary()
    with open(os.path.join(PROC, "grades.json"), "w", encoding="utf-8") as f:
        json.dump({"grades": g, "criteria_ok": ok, "criteria_total": tot},
                  f, ensure_ascii=False, indent=2)
    print("등급 A %d · B %d · C %d · X %d / 5대 기준 충족 %d-%d"
          % (g["A"], g["B"], g["C"], g["X"], ok, tot))


if __name__ == "__main__":
    main()
