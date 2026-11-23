"""시민 앱 '생활 지도'의 가게 목록 — 공공 상가(상권)정보에서 외국인 주민이 찾는 가게만 고른다 (결정 13).

    python pipeline\\stage_shops.py                 # 4안 폴더의 상가정보(경기, 2026-06)를 찾아 쓴다
    python pipeline\\stage_shops.py --src <경기 csv> # 다른 판(분기 갱신본)으로
    python pipeline\\stage_shops.py --check         # 분류 결과 개수만 보이고 파일은 쓰지 않는다

입력: 소상공인시장진흥공단 상가(상권)정보 — 공공데이터포털 파일 데이터(이용 제한 없음). 안산(41271 · 41273)만 쓴다.
출력: data/public/shops_ansan.csv (공공 자료라 공개 저장소 · 공유판에 담아도 된다)

고르는 방법 (위에서부터):
1. **업종 분류**: 중분류 '동남아시아' 전부, 소분류 '마라탕/훠궈' — 공공 분류가 이미 외국 음식이라고 적은 가게.
2. **상호 낱말**: 음식 · 식료품 · 생활 서비스(휴대폰 · 여행사) 업종 안에서 나라 · 음식 이름이 상호에 든 가게.
   업종을 먼저 거르므로 '타이어' · '인도어 골프' 같은 오탐은 들어오지 않는다. 상호로 고르는 것은 원래 결정 R4-16과
   충돌하므로(2026-11-20 사용자 요청으로 결정 13에서 바꿈) 화면에 "상호로 분류 — 틀리면 알려 주세요"를 붙이고,
   주민의 '정보가 달라요' 신고를 관리자가 검수한다.
3. **검수 목록** (`data/public/shops_overrides.csv`): 낱말로 안 잡히는 가게를 넣고(예: 러시아어 'лепёшка' 레표시카),
   잘못 잡힌 가게를 뺀다. 엑셀로 고칠 수 있게 CSV로 둔다. 원곡동은 상호 전체를 작업자(Claude)가 이름만 보고 한 번 훑었다
   (2026-11-20) — 현장 · 담당자 확인이 아니다. 주인의 국적은 상가정보에 없어 알 수 없다. 정확도는 아직 재지 않았다.
4. 번역 · 통역 서비스업은 상호에 '번역 · 통역'이 든 곳을 넣는다(이 업종에 편의점 · 주차장 같은 오분류가 섞여 있어서).
5. 생활 서비스(번역 · 여행 · 휴대폰)는 **지금은 지도에 싣지 않는다**(`SERVICES_ON_MAP = False`). 상가정보는 '사업자 등록한
   곳'의 목록이라 간판 없는 사무실 · 집 주소 · 문 닫은 곳이 섞인다. 2026-11-20 사용자가 네이버 지도로 대충 찾아본 것만 해도
   케이트랜스(선부동, 건물명 없는 4층) · 부카리트래블(손 목록으로 넣은 곳) · 우정외국어번역이 없었다. 찾아갈 수 없는 곳을 싣지
   않고 집을 지도에 찍지 않으려는 것이다. 시나 지원센터가 확인한 목록이 생기면 켠다 — 켜더라도 원곡동 밖은 손 목록에 있는 곳만.
6. **영업 확인**(2026-11-20 사용자: "너가 직접 확인해야지"): 고른 가게를 안산 식품 인허가 대장(영업 신고 — 행안부
   LOCALDATA, `stage_licenses.py` 로 받음)과 하나하나 맞춰 '영업/정상'으로 확인된 곳만 지도에 싣는다(`verify_shops.py`).
   폐업 · 대장에 없음은 `data/public/shops_unverified.csv`(확인 대기)로 보낸다. 인허가 파일이 없으면 멈춘다 — 확인 없이 싣지 않는다.
   식료품은 포장 식품만 팔면 신고가 필요 없어 대부분 확인되지 않는다('없는 가게'가 아니라 '공공 자료로 확인 못 함').
   → `make_field_list.py` 가 현장 확인 목록(엑셀)을 만들고, 채운 목록을 `import_field_check.py` 로 들이면 8번에서 반영된다.
7. **음식 종류 확인**(같은 날 "잘 검증한 거지?"): 상가정보 소분류 '베트남식 · 기타 동남아식'만으로 잡힌 가게에 라이브카페 · 호프 ·
   치킨집 · 한식당이 섞여 있었다. 이름 낱말이나 인허가 업태 '외국음식전문점'이 뒷받침해야 싣고, 업태만 있으면 나라를 모르므로
   intl(외국 음식)로 둔다(`confirm_cuisine`). 같은 신고에 핀이 둘이면 하나만 남긴다.

'음식 종류(cuisine)'는 **음식 · 상품의 종류**다. 가게 주인의 국적을 뜻하지 않는다(화면에도 그렇게 적는다).
"""
import argparse
import re
import sys
from pathlib import Path

import pandas as pd

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE / "src"))
from config import DONG_NAME  # noqa: E402

PUBLIC_DIR = BASE / "data" / "public"
OUT_CSV = PUBLIC_DIR / "shops_ansan.csv"
UNVERIFIED_CSV = PUBLIC_DIR / "shops_unverified.csv"     # 인허가로 영업을 확인하지 못해 지도에 싣지 않은 곳(확인 대기 목록)
FIELDCHECK_CSV = PUBLIC_DIR / "shops_fieldcheck.csv"     # 현장 확인 결과(가게 번호별) — pipeline/import_field_check.py 가 채운다
OVERRIDES_CSV = PUBLIC_DIR / "shops_overrides.csv"
SRC_GLOB = "소상공인시장진흥공단_상가(상권)정보_*/*_경기_*.csv"
SEARCH_DIRS = [BASE.parent / "4안" / "data"]
ANSAN_SGG = ("41271", "41273")
ANSAN_BOX = (126.50, 37.15, 126.95, 37.42)   # 경도 · 위도 범위 — 좌표가 이 밖이면 버린다(대부도 포함)

# (음식 종류 코드, 상호 낱말) — 위에서부터 먼저 맞는 것. 나라 이름이 겹치는 것(인도/인도네시아)은 구체적인 것을 먼저 둔다
CUISINE_WORDS = [
    ("id", r"인도네시아|자카르타|와룽|누산따라|누산타라|린두알람|가루다|바타비아|아네카|가톳카차|본독발리|캄풍|사하밧"),
    ("ph", r"필리핀|마닐라|이나살|피노이"),
    ("kh", r"캄보디아|앙코르|크메르|프놈펜"),
    ("mm", r"미얀마|양곤|만달레이"),
    ("th", r"태국|치앙마이|방콕|팟타이|똠얌|쏨땀|수쿠타이|타이(?!어|거|칸|오)"),
    ("vn", r"베트남|하노이|사이공|호치민|다낭|(?<!운남)(?<!윈난)쌀국수|분짜|반미|월남|비엣|(?i:\bpho\b|pho)|포나향|포휘엔|젠틀포|"
           r"포메인|포로안|미분당"),
    ("lk", r"스리랑카|랑카|랑까|콜롬보"),
    ("np", r"네팔|에베레스트|히말라야|카트만두|칸티뿌르|룸비니|나마스테|타지마할|탄두리|마살라|인도(?!네)|인디아|인디안|"
           r"(?i:nepal|india)|(?<!베이)커리"),
    ("mn", r"몽골(?!리안)|울란바토르|칭기스"),
    ("ca", r"우즈벡|사마르칸트|타슈켄트|타쉬켄트|부하라|카자흐|키르기|러시아|고려인|샤슬릭|레표시카|레뾰시카|탄드르|탄디르|샴푸르|"
           r"쿨리나리야|바르바리스|코진카|코르진카|브꾸스|(?i:samarkand)"),
    ("halal", r"할랄|하랄|(?i:halal)|케밥|(?i:kebab)|터키|튀르키예|이스탄불|술탄|알마디나|이브라힘|와합|아프리디"),
    ("cn", r"연변|연길|훈춘|용정|룡정|해란강|하얼빈|심양|서탑|계서|동북요리|동북식당|동북특색|양꼬치|훠궈|마라|중국식품|"
           r"중국마트|중국슈퍼|한중마트|란주(?:우육면|라면|짬뽕|면)|란저우|충칭|중경|량피|우육면|교자관|사오빙|조선족|하이디라오|"
           r"운남|윈난"),
    ("world", r"아시아마트|(?i:asia ?mart)|월드푸드|글로벌마트|수입식품|외국식품|세계식품|포리너"),
]
CUISINES = [c for c, _ in CUISINE_WORDS] + ["sea", "intl"]   # sea = 동남아(나라 미상), intl = 외국 음식(나라 미상 — 아래 confirm_cuisine)
SEA_SUBS = {"베트남식 전문", "기타 동남아식 전문"}               # 이 소분류만으로는 음식 종류를 믿지 않는다(2026-11-20 대조에서 라이브카페 · 호프가 섞여 나옴)
FOREIGN_UPTE = "외국음식전문점(인도,태국등)"

# 업종 거르기 — 상호 낱말은 이 업종 안에서만 본다
FOOD_EXCLUDE_SUB = {"일반 유흥 주점", "무도 유흥 주점", "생맥주 전문", "카페"}
GROCERY_MID = {"식료품 소매", "종합 소매", "기타 상품 소매"}
GROCERY_EXCLUDE_SUB = {"편의점"}
SERVICE_SUB = {"핸드폰 소매업": "phone", "여행사": "travel", "기타 여행 보조/예약 서비스업": "travel",
               "번역/통역 서비스업": "translate"}
# 번역 · 통역은 나라 이름이 없어도 넣는다 — 다만 이 업종에 편의점 · 주차장 같은 오분류가 많아 상호에 이 말이 있을 때만
TRANSLATE_WORDS = r"번역|통역|랭귀지|트랜스|(?i:translat|lingu)"
SERVICE_DONG = "원곡동"     # 생활 서비스를 손 목록 없이 싣는 곳(위 5번)
SERVICES_ON_MAP = False    # 위 5번 — 확인한 목록이 생기기 전까지 생활 서비스는 싣지 않는다

BASE_COLUMNS = ["shop_id", "name", "kind", "sub", "cuisine", "basis", "dong", "dong_name", "road_addr", "floor",
                "lon", "lat"]
COLUMNS = BASE_COLUMNS + ["std_ym", "checked", "check_src"]   # checked = 영업을 확인한 날(대장 기준일 · 현장 확인한 날), check_src = licence | field


def find_source(arg: str = None) -> Path:
    if arg:
        p = Path(arg)
        if not p.exists():
            sys.exit(f"상가정보 파일이 없다: {p}")
        return p
    hits = sorted(p for d in SEARCH_DIRS for p in d.glob(SRC_GLOB))
    if not hits:
        sys.exit("상가정보(경기) 파일을 못 찾았다 — 공공데이터포털 '소상공인시장진흥공단_상가(상권)정보'를 내려받아 "
                 "--src 로 경기 파일을 넘긴다")
    return hits[-1]


def read_ansan(path: Path) -> pd.DataFrame:
    for enc in ("utf-8-sig", "cp949"):
        try:
            df = pd.read_csv(path, dtype=str, encoding=enc)
            break
        except UnicodeDecodeError:
            continue
    df = df[df["시군구코드"].isin(ANSAN_SGG)].copy()
    df["lon"] = pd.to_numeric(df["경도"], errors="coerce")
    df["lat"] = pd.to_numeric(df["위도"], errors="coerce")
    x0, y0, x1, y1 = ANSAN_BOX
    return df[df["lon"].between(x0, x1) & df["lat"].between(y0, y1)].reset_index(drop=True)


def cuisine_of(name: str) -> str:
    for code, pattern in CUISINE_WORDS:
        if re.search(pattern, name or ""):
            return code
    return ""


def read_overrides(path: Path = OVERRIDES_CSV) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=["상호명", "행정동명", "action", "kind", "sub", "cuisine", "note"])
    ov = pd.read_csv(path, dtype=str, encoding="utf-8-sig").fillna("")
    bad = ov[~ov["action"].isin(["include", "exclude"])]
    if len(bad):
        sys.exit(f"{path.name}: action 은 include/exclude — {bad['상호명'].tolist()[:5]}")
    return ov


def classify(df: pd.DataFrame, overrides: pd.DataFrame, services: bool = SERVICES_ON_MAP) -> pd.DataFrame:
    """상가정보(안산) → 앱 가게 목록. df 는 상가정보 원래 컬럼 + lon/lat."""
    name = (df["상호명"].fillna("") + " " + df["지점명"].fillna("")).str.strip()
    big, mid, sub = df["상권업종대분류명"], df["상권업종중분류명"].str.strip(), df["상권업종소분류명"].str.strip()
    word = name.map(cuisine_of)

    is_food = big.eq("음식") & ~sub.isin(FOOD_EXCLUDE_SUB) & ~mid.eq("비알코올")
    is_groc = mid.isin(GROCERY_MID) & ~sub.isin(GROCERY_EXCLUDE_SUB)
    is_serv = sub.isin(list(SERVICE_SUB))

    by_category = mid.eq("동남아시아") | sub.eq("마라탕/훠궈")
    is_translate = sub.eq("번역/통역 서비스업") & name.str.contains(TRANSLATE_WORDS, regex=True)
    word = word.where(~sub.eq("번역/통역 서비스업") | is_translate, "")      # 오분류 업소에 붙은 우연한 낱말은 버린다
    pick = (is_food & (by_category | word.ne(""))) | (is_groc & word.ne("")) | (is_serv & word.ne("")) | is_translate

    out = pd.DataFrame({
        "shop_id": df["상가업소번호"], "name": name, "dong": df["행정동코드"].str[:8],
        "road_addr": df["도로명주소"].fillna(""), "floor": df["층정보"].fillna(""),
        "lon": df["lon"].round(6), "lat": df["lat"].round(6),
        "kind": "", "sub": "", "cuisine": word, "basis": "",
        "_dong_nm": df["행정동명"], "_raw_name": df["상호명"].fillna(""),
    })
    out.loc[is_food, "kind"] = "food"
    out.loc[is_groc, "kind"] = "grocery"
    out.loc[is_serv, "kind"] = "service"
    out.loc[is_serv, "sub"] = sub[is_serv].map(SERVICE_SUB)
    out["basis"] = "name"
    out.loc[by_category & is_food, "basis"] = "category"
    out.loc[is_translate, "basis"] = "category"
    # 업종으로만 잡힌 음식점의 종류 — 공공 분류 '베트남식 전문'은 베트남, '기타 동남아식'은 동남아, 마라탕은 중국
    need = out["cuisine"].eq("")
    out.loc[need & sub.eq("베트남식 전문"), "cuisine"] = "vn"
    out.loc[need & sub.eq("기타 동남아식 전문"), "cuisine"] = "sea"
    out.loc[need & sub.eq("마라탕/훠궈"), "cuisine"] = "cn"
    out.loc[out["cuisine"].eq("") & out["kind"].eq("service"), "cuisine"] = "world"
    keep = out[pick].copy()

    # 검수 목록 — 상호명(지점명 빼거나 붙인 것 모두) + 행정동명(비우면 모든 동). 끝에 '*'를 붙이면 앞부분만 맞춘다
    for r in overrides.itertuples():
        hit_all = override_hits(out, r.상호명, r.행정동명)
        if r.action == "exclude":
            keep = keep[~keep.index.isin(out[hit_all].index)]
            continue
        rows = out[hit_all].copy()
        if rows.empty:
            continue                      # 다음 분기 판에서 없어진 가게 — 조용히 넘어간다(--check 가 알려 준다)
        rows["kind"] = r.kind or rows["kind"].replace("", "food")
        rows["sub"] = r.sub or rows["sub"]
        rows["cuisine"] = r.cuisine or rows["cuisine"].replace("", "world")
        rows["basis"] = "review"
        keep = pd.concat([keep[~keep.index.isin(rows.index)], rows])

    keep = keep[keep["dong"].isin(list(DONG_NAME))]
    keep["dong_name"] = keep["dong"].map(DONG_NAME)
    walk_in = ~keep["kind"].eq("service") | keep["dong_name"].eq(SERVICE_DONG) | keep["basis"].eq("review")
    keep = keep[walk_in]                                           # 위 5번 — 원곡동 밖 생활 서비스는 확인한 곳만
    if not services:
        keep = keep[~keep["kind"].eq("service")]                   # 위 5번 — 지금은 생활 서비스를 싣지 않는다
    keep = keep.drop_duplicates(subset=["name", "lon", "lat"])     # 같은 가게가 두 번 실린 경우
    return keep.sort_values(["dong", "kind", "name"])[BASE_COLUMNS].reset_index(drop=True)


def confirm_cuisine(shops: pd.DataFrame, raw: pd.DataFrame) -> pd.DataFrame:
    """상가정보 소분류 '베트남식 · 기타 동남아식'만으로 잡힌 가게는 뒷받침이 있어야 싣는다(2026-11-20 사용자: "잘 검증한 거지?").
    대조해 보니 이 소분류에 라이브카페 · 호프 · 치킨집 · 한식당이 섞여 있었다(첼로 · 아우라7080라이브 · 훌랄라 · 퀸 …).
    - 이름에 음식 낱말이 있으면 그 낱말의 음식 종류로 둔다.
    - 낱말은 없고 인허가 업태가 '외국음식전문점'이면 외국 음식점은 맞지만 나라는 모른다 → intl(외국 음식).
    - 둘 다 없으면 res = cuisine_unconfirmed 로 바꿔 싣지 않는다(확인 대기)."""
    sub = shops["shop_id"].map(raw.drop_duplicates("상가업소번호").set_index("상가업소번호")["상권업종소분류명"])
    word = shops["name"].map(cuisine_of)
    only_cat = shops["basis"].eq("category") & sub.isin(SEA_SUBS) & word.eq("")
    foreign = shops["lic_upte"].eq(FOREIGN_UPTE)
    out = shops.copy()
    out.loc[only_cat & foreign, "cuisine"] = "intl"
    out.loc[only_cat & ~foreign & out["res"].eq("open"), "res"] = "cuisine_unconfirmed"
    return out


FIELD_OPEN = "영업 중"
FIELD_RESULTS = {FIELD_OPEN: "open", "문 닫음": "field_closed", "다른 가게": "field_other", "못 찾음": "field_missing"}


def read_fieldcheck(path: Path = None) -> pd.DataFrame:
    """현장 확인 결과(shop_id · result · checked_on · note) — import_field_check.py 가 채운다. 없으면 빈 표."""
    path = path or FIELDCHECK_CSV
    if not path.exists():
        return pd.DataFrame(columns=["shop_id", "name", "result", "checked_on", "note"])
    return pd.read_csv(path, dtype=str, encoding="utf-8-sig").fillna("")


def apply_fieldcheck(shops: pd.DataFrame, fc: pd.DataFrame) -> pd.DataFrame:
    """현장에서 '영업 중'이면 지도에 싣고(check_src = field, checked = 확인한 날), 문 닫음 · 다른 가게 · 못 찾음이면 뺀다.
    가게 번호(상가업소번호)로 맞춘다 — 이름으로 맞추는 손 목록(shops_overrides.csv)과 따로 둔다."""
    out = shops.copy()
    for r in fc.itertuples():
        code = FIELD_RESULTS.get(r.result)
        hit = out["shop_id"].eq(r.shop_id)
        if not code or not hit.any():
            continue
        out.loc[hit, "res"] = code
        if code == "open":
            out.loc[hit, "check_src"] = "field"
            out.loc[hit, "checked"] = r.checked_on
    return out


def override_hits(out: pd.DataFrame, name: str, dong: str) -> pd.Series:
    if name.endswith("*"):
        hit = out["name"].str.startswith(name[:-1])
    else:
        hit = (out["_raw_name"] == name) | (out["name"] == name)
    return hit & (out["_dong_nm"] == dong) if dong else hit


def unmatched_overrides(df: pd.DataFrame, overrides: pd.DataFrame) -> list:
    full = (df["상호명"].fillna("") + " " + df["지점명"].fillna("")).str.strip()
    probe = pd.DataFrame({"name": full, "_raw_name": df["상호명"].fillna(""), "_dong_nm": df["행정동명"].fillna("")})
    return [f"{r.상호명}({r.행정동명 or '모든 동'})" for r in overrides.itertuples()
            if r.action == "include" and not override_hits(probe, r.상호명, r.행정동명).any()]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    src = find_source(args.src)
    ym = re.search(r"_(\d{6})\.csv$", src.name)
    df = read_ansan(src)
    ov = read_overrides()
    shops = classify(df, ov)
    shops["std_ym"] = f"{ym.group(1)[:4]}-{ym.group(1)[4:]}" if ym else ""
    print(f"[i] {src.name} · 안산 {len(df):,}곳 → 앱 가게 {len(shops)}곳")
    print("    종류:", shops["kind"].value_counts().to_dict())
    print("    근거:", shops["basis"].value_counts().to_dict())
    print("    음식 종류:", shops["cuisine"].value_counts().to_dict())
    miss = unmatched_overrides(df, ov)
    if miss:
        print(f"    검수 목록에 있는데 이 판에 없는 가게 {len(miss)}곳(폐업 · 상호 변경?):", ", ".join(miss[:10]))

    # 6. 영업 확인 — 인허가 대장과 하나하나 맞춰, 영업 중으로 확인된 곳만 지도에 싣는다(verify_shops.py)
    import verify_shops
    lic, asof = verify_shops.load_licences()
    shops = shops.join(verify_shops.match(shops, df, lic), on="shop_id")
    shops = confirm_cuisine(shops, df)
    # 같은 신고에 핀이 둘(상가정보에 같은 가게가 두 줄 — 층 · 좌표만 다름) → 하나만. 이름이 신고와 같은 쪽을 남긴다
    shops["_same"] = shops["name"].str.replace(r"\s", "", regex=True) == shops["lic_name"].str.replace(r"\s", "", regex=True)
    live = shops[shops["res"].eq("open")].sort_values("_same", ascending=False)
    shops.loc[live.index[live.duplicated("lic_id")], "res"] = "duplicate"
    shops["checked"] = asof
    shops["check_src"] = "licence"
    # 8. 현장 확인 — 시 · 지원센터가 채운 확인 목록(make_field_list → import_field_check)이 인허가보다 우선한다(더 최근)
    shops = apply_fieldcheck(shops, read_fieldcheck())
    ok = shops["res"].eq("open")
    print(f"[i] 인허가 대장({asof} 기준) · 현장 확인 반영:")
    print(pd.crosstab(shops["res"], shops["kind"], margins=True).to_string())
    if args.check:
        return
    PUBLIC_DIR.mkdir(parents=True, exist_ok=True)
    shops[ok][COLUMNS].to_csv(OUT_CSV, index=False, encoding="utf-8-sig")
    shops[~ok][["shop_id", "name", "kind", "cuisine", "dong_name", "road_addr", "floor", "lon", "lat", "res", "lic_name",
                "lic_type", "closed_on", "std_ym", "checked"]].to_csv(UNVERIFIED_CSV, index=False, encoding="utf-8-sig")
    print(f"[v] {OUT_CSV} · 지도에 {int(ok.sum())}곳 (현장 확인 {int((ok & shops['check_src'].eq('field')).sum())})")
    print(f"[v] {UNVERIFIED_CSV} · 확인 못 한 {int((~ok).sum())}곳(폐업 {int(shops['res'].eq('closed').sum())})")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
