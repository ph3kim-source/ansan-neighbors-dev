"""가게가 지금 영업 중인지 — 상가정보 가게를 안산 식품 인허가 대장(영업 신고)과 하나하나 맞춰 본다 (2026-11-20).

stage_shops.py 가 부른다. 인허가 파일은 stage_licenses.py 로 받는다(data/public/raw/localdata, 공공 · 키 없음).

맞추는 법
- 같은 건물: 도로명(구 · 길 · 건물번호), 지번(구 · 동 · 번지), 부번을 뗀 도로명 — 셋 중 하나가 같은 신고만 후보로 본다.
- 같은 가게: 이름을 몇 가지로 펴서(통째 · 괄호 뺀 것 · 괄호 안 · 지점 '○○점' 뺀 것) 비교한다.
  · 한쪽이 다른 쪽을 품으면 같다(1.0).
  · 흔한 음식 낱말(마라탕 · 양꼬치 · 쌀국수 · 식품 · 중국 …)을 빼고 남은 고유한 부분이 서로 품으면 0.9.
  · 고유한 부분이 두 글자 이상 같을 때만 글자 순서 겹침(LCS 비율)을 본다 — '다복양꼬치'와 '대박양꼬치'를 같다고 보지 않게.
  · 지점 이름('상록수점')만 남은 것은 이름으로 치지 않는다 — 같은 건물 다른 가게의 '(상록수점)'과 붙지 않게.
  · 0.7 이상이면 같은 가게.
- 업종도 맞아야 한다: 음식점 ↔ 일반 · 휴게음식점 · 제과점 · 관광식당 · 즉석판매제조가공, 식료품 ↔ 식품소분 · 축산판매 ·
  식품판매(기타) · 즉석판매제조가공. 같은 건물의 '대박양꼬치'(음식점 신고)로 '대박중국식품'(가게)을 확인하지 않는다.

결과(res)
- open: 같은 가게의 신고가 '영업/정상' → 지도에 싣는다(checked = 대장 기준일).
- closed: 같은 가게의 신고가 있는데 모두 폐업 · 취소 → 싣지 않는다.
- not_found: 같은 건물에 같은 가게 신고가 없다 → 싣지 않는다(이름이 바뀌었거나 옮겼거나, 신고가 필요 없는 가게).
  식료품은 포장 식품만 팔면 신고가 필요 없어 대부분 여기로 온다 — '없는 가게'라는 뜻이 아니라 '공공 자료로 확인 못 함'이다.
"""
import re

import pandas as pd

import stage_licenses as sl

FOOD_TYPES = {"일반음식점", "휴게음식점", "제과점영업", "관광식당", "즉석판매제조가공업"}
GROCERY_TYPES = {"식품소분업", "축산판매업", "식품판매업(기타)", "즉석판매제조가공업"}
KIND_TYPES = {"food": FOOD_TYPES, "grocery": GROCERY_TYPES}
MATCH_MIN = 0.7
OPEN = "영업/정상"

ROAD = re.compile(r"(상록구|단원구)\s+(\S+?(?:로|길))\s*(\d+(?:-\d+)?)")
JIBUN = re.compile(r"(상록구|단원구)\s+(\S+?동\d?가?)\s+(?:산\s*)?(\d+(?:-\d+)?)")
GENERIC = re.compile(r"마라탕|마라샹궈|훠궈|양꼬치|꼬치|쌀국수|반미|케밥|커리|카레|식품|마트|슈퍼|식당|음식|요리|전문점|본점|"
                     r"중국|베트남|태국|네팔|인도|몽골|우즈벡|러시아|할랄|하랄|연변|동북|월드|푸드|아시아|"
                     r"안산|원곡|고잔|중앙|상록수?|단원|본오|부곡|월피|성포|반월|선부|초지|신길|백운|호수|와동|사동|이동|일동|"
                     r"한양대|에리카|별관|[a-z]+")          # 흔한 음식 낱말 · 안산 동네 이름 — 이것만 같아서는 같은 가게가 아니다
MIN_SHARED = 3                                     # 한쪽이 다른 쪽을 품을 때 품긴 쪽의 최소 글자 수('원곡' · '별관' 같은 두 글자로 붙지 않게)
BRANCH = re.compile(r"\s*\S{1,8}점$")
PUNCT = re.compile(r"[\s()\[\]·.,&'\-_/]")


def road_key(addr: str) -> str:
    m = ROAD.search(addr or "")
    return f"{m.group(1)}|{m.group(2)}|{m.group(3)}" if m else ""


def road_main(addr: str) -> str:
    k = road_key(addr)
    return k.split("-")[0] if k else ""


def jibun_key(addr: str) -> str:
    m = JIBUN.search(addr or "")
    return f"{m.group(1)}|{m.group(2)}|{m.group(3)}" if m else ""


def variants(name: str) -> set:
    """비교할 이름들 — 통째, 괄호 뺀 것, 괄호 안(지점 이름이 아닐 때만), 그리고 각각에서 지점 '○○점'을 뗀 것."""
    n = re.sub(r"\(주\)|주식회사|㈜|\(유\)|유한회사", "", (name or "").lower())
    out = {n, re.sub(r"\([^)]*\)", "", n)}
    out |= {p for p in re.findall(r"\(([^)]*)\)", n) if not p.strip().endswith("점")}
    out |= {BRANCH.sub("", v) for v in list(out)}
    return {PUNCT.sub("", v) for v in out} - {""}


def lcs(a: str, b: str) -> int:
    prev = [0] * (len(b) + 1)
    for ca in a:
        cur = [0]
        for j, cb in enumerate(b):
            cur.append(prev[j] + 1 if ca == cb else max(prev[j + 1], cur[j]))
        prev = cur
    return prev[-1]


def name_score(a: str, b: str) -> float:
    best = 0.0
    for x in variants(a):
        for y in variants(b):
            if x == y or (min(len(x), len(y)) >= MIN_SHARED and (x in y or y in x)):
                return 1.0
            dx, dy = GENERIC.sub("", x), GENERIC.sub("", y)
            if min(len(dx), len(dy)) >= MIN_SHARED and (dx in dy or dy in dx):
                best = max(best, 0.9)
            if lcs(dx, dy) >= 2:
                best = max(best, 2 * lcs(x, y) / (len(x) + len(y)))
    return best


def load_licences() -> tuple:
    """받아 둔 안산 식품 인허가 전부 → (표, 대장 기준일). 파일이 없으면 멈춘다 — 확인 없이 가게를 싣지 않는다."""
    frames = []
    for slug, kind in sl.TYPES.items():
        path = sl.RAW / f"{slug}_{sl.ORG}.csv"
        if not path.exists():
            raise SystemExit(f"[X] 인허가 파일이 없습니다({kind}) — 먼저 python pipeline\\stage_licenses.py")
        d = sl.read_license(path)
        if len(d):
            d = d[["관리번호", "사업장명", "영업상태명", "폐업일자", "도로명주소", "지번주소", "업태구분명", "최종수정시점"]].copy()
            d["type"] = kind
            frames.append(d)
    lic = pd.concat(frames, ignore_index=True)
    lic["rk"] = lic["도로명주소"].map(road_key)
    lic["jk"] = lic["지번주소"].map(jibun_key)
    lic["rm"] = lic["도로명주소"].map(road_main)
    asof = str(lic["최종수정시점"].max())[:10]
    return lic, asof


def match(shops: pd.DataFrame, raw: pd.DataFrame, lic: pd.DataFrame) -> pd.DataFrame:
    """shops(stage_shops.classify 결과) × raw(상가정보 원래 칸) × lic → shop_id 별 res · 맞춘 신고."""
    extra = raw.set_index("상가업소번호")[["상호명", "지점명", "지번주소"]].fillna("")
    extra = extra[~extra.index.duplicated()]
    groups = {k: lic[lic[k] != ""].groupby(k) for k in ("rk", "jk", "rm")}
    keys = {k: set(g.groups) for k, g in groups.items()}
    rows = []
    for s in shops.itertuples():
        e = extra.loc[s.shop_id] if s.shop_id in extra.index else pd.Series({"상호명": "", "지점명": "", "지번주소": ""})
        probe = {"rk": road_key(s.road_addr), "jk": jibun_key(e["지번주소"]), "rm": road_main(s.road_addr)}
        parts = [groups[k].get_group(v) for k, v in probe.items() if v and v in keys[k]]
        cand = pd.concat(parts).drop_duplicates(subset=["관리번호", "type"]) if parts else lic.iloc[0:0]
        cand = cand[cand["type"].isin(KIND_TYPES.get(s.kind, set()))]
        names = [s.name, e["상호명"], f"{e['상호명']} {e['지점명']}".strip()]
        score = [max(name_score(n, x) for n in names) for x in cand["사업장명"]]
        hit = cand.assign(score=score)
        hit = hit[hit["score"] >= MATCH_MIN].sort_values(["score", "영업상태명"], ascending=[False, True])
        live = hit[hit["영업상태명"] == OPEN]
        best = live.iloc[0] if len(live) else (hit.iloc[0] if len(hit) else None)
        rows.append({"shop_id": s.shop_id, "res": "open" if len(live) else ("closed" if len(hit) else "not_found"),
                     "lic_id": "" if best is None else f"{best['type']}:{best['관리번호']}",
                     "lic_name": "" if best is None else best["사업장명"], "lic_type": "" if best is None else best["type"],
                     "closed_on": "" if best is None or len(live) else best["폐업일자"],
                     "lic_upte": "" if best is None else best["업태구분명"]})
    return pd.DataFrame(rows).set_index("shop_id")
