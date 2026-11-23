"""안산 식품 인허가 파일 받기 — 시민 앱 가게가 실제로 영업 중인지 맞춰 보는 공공 자료 (2026-11-20).

    python pipeline\\stage_licenses.py            # 8종을 받아 data/public/raw/localdata/ 에 둔다(원본 바이트 그대로)
    python pipeline\\stage_licenses.py --check    # 받은 파일의 행 수 · 영업 상태만 보인다

출처: 행정안전부 지방행정 인허가 데이터(LOCALDATA) — 2026-01부터 공공데이터포털로 통합, 파일은 file.localdata.go.kr 에서
      시군구(개방자치단체코드)별로 내려받는다. 안산시 = 3930000. 로그인 · 인증키 없음.
      공공데이터포털 표기: 행정안전부_식품_일반음식점(15045016) 등 — 이용허락범위 제한 없음.

왜 받나: 상가정보는 '사업자 등록한 곳' 목록이라 간판 없는 사무실 · 문 닫은 곳이 섞인다(2026-11-20 사용자가 네이버 지도로
         찾아본 생활 서비스 3곳이 없었다). 음식점 · 식료품은 영업 신고 대장(인허가)에 영업 상태가 있어 하나하나 맞춰 볼 수 있다.
원본은 커서(안산 일반음식점만 수만 행 — 문 닫은 곳 포함) 저장소에 올리지 않는다(.gitignore).
"""
import argparse
import datetime
import hashlib
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
RAW = BASE / "data" / "public" / "raw" / "localdata"
HOST = "https://file.localdata.go.kr"
ORG = "3930000"                      # 경기 안산시
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"
TYPES = {                            # 파일 이름 = 인허가 업종
    "general_restaurants": "일반음식점",
    "rest_cafes": "휴게음식점",
    "bakeries": "제과점영업",
    "tourist_restaurants": "관광식당",
    "instant_food_processors": "즉석판매제조가공업",
    "food_repackagers": "식품소분업",
    "livestock_retail": "축산판매업",
    "other_food_retailers": "식품판매업(기타)",
}


def _get(path: str, referer: str, timeout: int = 300) -> bytes:
    req = urllib.request.Request(HOST + path, headers={"User-Agent": UA, "Referer": referer, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def download(slug: str) -> bytes:
    referer = f"{HOST}/file/{slug}/info"
    for attempt in range(5):
        try:
            _get("/file/validate/download-count", referer, timeout=60)      # 화면의 '다운로드' 단추가 먼저 부르는 횟수 확인
            return _get(f"/file/download/{slug}/info?orgCode={ORG}", referer)
        except urllib.error.HTTPError as err:
            if err.code != 429:
                raise
            wait = 20 * (attempt + 1)
            print(f"    {slug}: 잠시 뒤 다시(429) — {wait}초")
            time.sleep(wait)
    raise SystemExit(f"[X] {slug}: 다운로드 횟수 제한이 풀리지 않았습니다")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    RAW.mkdir(parents=True, exist_ok=True)
    man_path = RAW / "MANIFEST.json"
    man = json.loads(man_path.read_text(encoding="utf-8")) if man_path.exists() else {}
    if not args.check:
        for slug, name in TYPES.items():
            data = download(slug)
            (RAW / f"{slug}_{ORG}.csv").write_bytes(data)
            man[slug] = {"name": name, "org": ORG, "retrieved": datetime.date.today().isoformat(), "bytes": len(data),
                         "sha256": hashlib.sha256(data).hexdigest(), "url": f"{HOST}/file/download/{slug}/info?orgCode={ORG}",
                         "license": "공공데이터포털 · 이용허락범위 제한 없음"}
            print(f"[v] {name} · {len(data):,} bytes")
            time.sleep(2)
        man_path.write_text(json.dumps(man, ensure_ascii=False, indent=2), encoding="utf-8")
    import pandas as pd
    for slug, name in TYPES.items():
        p = RAW / f"{slug}_{ORG}.csv"
        if not p.exists():
            print(f"[ ] {name}: 없음")
            continue
        df = read_license(p)
        state = df["영업상태명"].value_counts().to_dict() if "영업상태명" in df.columns else {}
        print(f"[i] {name}: {len(df):,}행 · 상태 {state}")


def read_license(path: Path):
    """인허가 CSV 한 개 — 인코딩이 판마다 달라(utf-8 / cp949) 둘 다 시도한다."""
    import pandas as pd
    for enc in ("utf-8-sig", "cp949"):
        try:
            return pd.read_csv(path, dtype=str, encoding=enc, low_memory=False).fillna("")
        except UnicodeDecodeError:
            continue
    raise SystemExit(f"[X] {path.name}: 인코딩을 읽지 못했습니다")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
