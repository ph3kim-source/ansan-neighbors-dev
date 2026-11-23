"""채운 현장 확인 목록(엑셀) → data/public/shops_fieldcheck.csv — 그다음 stage_shops.py 를 돌리면 지도에 반영된다.

    python pipeline\\import_field_check.py 현장확인\\식료품_현장확인_목록.xlsx
    python pipeline\\stage_shops.py

- '확인 결과'가 비어 있는 줄과 2행 예시는 건너뛴다. 같은 가게를 다시 확인하면 새 결과로 바꾼다.
- '확인한 사람'은 옮기지 않는다(앱 파일은 공개 저장소에 들어간다 — 이름은 시 내부 엑셀에만).
- 날짜가 비어 있으면 들인 날로 적는다.
"""
import datetime
import sys
from pathlib import Path

import pandas as pd
from openpyxl import load_workbook

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE / "pipeline"))
import make_field_list as mfl  # noqa: E402
import stage_shops  # noqa: E402


def read_results(path: Path) -> pd.DataFrame:
    """엑셀 '확인 목록' → (shop_id, name, result, checked_on, note). 모르는 결과 값은 멈춘다(오타를 조용히 넘기지 않게)."""
    ws = load_workbook(path, data_only=True)[mfl.LIST_SHEET]
    head = [c.value for c in ws[1]]
    col = {h: i for i, h in enumerate(head)}
    rows, bad = [], []
    for r in ws.iter_rows(min_row=2, values_only=True):
        no, result, shop_id = r[col["번호"]], r[col["확인 결과"]], r[col["가게 번호(고치지 마세요)"]]
        if no == "예시" or not result or not shop_id:
            continue
        result = str(result).strip()
        if result not in stage_shops.FIELD_RESULTS:
            bad.append(f"{no}번 '{result}'")
            continue
        day = r[col["확인 날짜"]]
        if isinstance(day, datetime.datetime):
            day = day.date()
        day = day.isoformat() if isinstance(day, datetime.date) else (str(day).strip()[:10] if day else datetime.date.today().isoformat())
        note = " · ".join(str(v).strip() for v in (r[col["지금 간판 이름(다른 가게면)"]], r[col["메모"]]) if v)
        rows.append({"shop_id": str(shop_id).strip(), "name": r[col["가게 이름"]], "result": result, "checked_on": day, "note": note})
    if bad:
        sys.exit(f"[X] '확인 결과'는 {list(stage_shops.FIELD_RESULTS)} 중 하나여야 합니다: {', '.join(bad[:10])}")
    return pd.DataFrame(rows, columns=["shop_id", "name", "result", "checked_on", "note"])


def merge(old: pd.DataFrame, new: pd.DataFrame) -> pd.DataFrame:
    """같은 가게는 새 결과로 — 가게 번호로 맞춘다."""
    keep = old[~old["shop_id"].isin(new["shop_id"])]
    return pd.concat([keep, new], ignore_index=True).sort_values(["checked_on", "shop_id"]).reset_index(drop=True)


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    path = Path(sys.argv[1])
    new = read_results(path)
    out = merge(stage_shops.read_fieldcheck(), new)
    out.to_csv(stage_shops.FIELDCHECK_CSV, index=False, encoding="utf-8-sig")
    print(f"[v] {stage_shops.FIELDCHECK_CSV} · 이번에 {len(new)}곳 · 모두 {len(out)}곳")
    print("    결과:", new["result"].value_counts().to_dict())
    print("    → python pipeline\\stage_shops.py 를 돌려 지도에 반영하세요")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
