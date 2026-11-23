"""식료품 현장 확인 목록(엑셀) 만들기 — 영업 신고 대장으로 확인하지 못한 식료품 가게를 시 · 외국인주민지원센터가 확인하도록.

    python pipeline\\make_field_list.py        → 현장확인/식료품_현장확인_목록.xlsx

채운 뒤:  python pipeline\\import_field_check.py 현장확인\\식료품_현장확인_목록.xlsx  →  python pipeline\\stage_shops.py
         ('영업 중'은 지도에 다시 오르고, 문 닫음 · 다른 가게 · 못 찾음은 확인 대기 목록에서도 빠진다)

왜: 포장 식품만 파는 가게는 영업 신고 의무가 없어 공공 자료로 영업 여부를 확인할 수 없다(2026-11-20, 73곳 중 6곳만 확인).
자료는 공공 상가정보 · 공공 인허가뿐이다(민간 데이터 없음). '확인한 사람'은 엑셀 안에만 두고 앱 파일로 옮기지 않는다.
"""
import datetime
import re
import sys
from pathlib import Path
from urllib.parse import quote

import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.worksheet.datavalidation import DataValidation

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE / "pipeline"))
import stage_shops  # noqa: E402

OUT = BASE / "현장확인" / "식료품_현장확인_목록.xlsx"
LIST_SHEET = "확인 목록"
FONT = "맑은 고딕"            # 한글 표 — Arial 에는 한글 글꼴이 없어 맑은 고딕을 쓴다
CUISINE_KO = {"cn": "중국 · 연변", "vn": "베트남", "th": "태국", "id": "인도네시아", "ph": "필리핀", "kh": "캄보디아",
              "mm": "미얀마", "np": "네팔 · 인도", "lk": "스리랑카", "ca": "중앙아시아 · 러시아", "mn": "몽골",
              "halal": "할랄", "world": "세계 식품", "sea": "동남아", "intl": "외국 식품"}
HEADERS = ["번호", "동", "가게 이름", "파는 것", "도로명 주소", "층", "지도", "확인 결과", "지금 간판 이름(다른 가게면)",
           "메모", "확인 날짜", "확인한 사람", "가게 번호(고치지 마세요)"]
WIDTHS = [7, 10, 24, 18, 36, 6, 11, 13, 22, 30, 13, 12, 26]
INPUT_COLS = range(8, 13)     # H~L — 채우는 칸(노란색)
YELLOW = PatternFill("solid", fgColor="FFF2A8")
GREY = PatternFill("solid", fgColor="EEEEEE")
THIN = Side(style="thin", color="BBBBBB")


def _addr_key(addr: str):
    m = re.search(r"(\S+(?:로|길))\s*(\d+)(?:-(\d+))?", addr or "")
    return (m.group(1), int(m.group(2)), int(m.group(3) or 0)) if m else (addr or "", 0, 0)


def field_rows(unverified: pd.DataFrame, done: set) -> pd.DataFrame:
    """확인할 식료품 — 이미 현장 확인한 가게는 빼고, 동 → 길 이름 → 건물 번호 순(걸어서 돌기 좋게)."""
    g = unverified[(unverified["kind"] == "grocery") & ~unverified["shop_id"].isin(done)].copy()
    g["_k"] = g["road_addr"].map(_addr_key)
    return g.sort_values(["dong_name", "_k", "name"]).drop(columns="_k").reset_index(drop=True)


def build_workbook(rows: pd.DataFrame, out: Path, meta: dict) -> Path:
    wb = Workbook()
    guide = wb.active
    guide.title = "사용법"
    sheet = wb.create_sheet(LIST_SHEET)
    n = len(rows)
    first, last = 3, 2 + n                       # 1행 머리글 · 2행 예시 · 3행부터 가게

    # ---- 확인 목록
    sheet.append(HEADERS)
    for c, w in enumerate(WIDTHS, start=1):
        sheet.column_dimensions[sheet.cell(1, c).column_letter].width = w
        h = sheet.cell(1, c)
        h.font = Font(name=FONT, bold=True, size=10)
        h.fill = YELLOW if c in INPUT_COLS else GREY
        h.alignment = Alignment(vertical="center", wrap_text=True)
        h.border = Border(bottom=THIN)
    example = ["예시", "원곡동", "(예시) 행복식품", "중국 · 연변 식료품", "경기도 안산시 단원구 예시로 1", "1", "카카오맵",
               "영업 중", "", "주인에게 확인 · 중국 식품 팖", datetime.date(2026, 11, 25), "담당자", ""]
    sheet.append(example)
    for c in range(1, len(HEADERS) + 1):
        cell = sheet.cell(2, c)
        cell.font = Font(name=FONT, size=10, italic=True, color="888888")
    sheet.cell(2, 11).number_format = "yyyy-mm-dd"
    for i, r in enumerate(rows.itertuples(), start=1):
        label = CUISINE_KO.get(r.cuisine, "")
        sheet.append([i, r.dong_name, r.name, f"{label} 식료품" if label else "식료품", r.road_addr, r.floor or "", "카카오맵",
                      None, None, None, None, None, r.shop_id])
        row = sheet.max_row
        link = sheet.cell(row, 7)
        link.hyperlink = f"https://map.kakao.com/link/map/{quote(r.name)},{r.lat},{r.lon}"
        link.font = Font(name=FONT, size=10, color="1C5CAB", underline="single")
        for c in range(1, len(HEADERS) + 1):
            cell = sheet.cell(row, c)
            if c != 7:
                cell.font = Font(name=FONT, size=10, color="888888" if c == 13 else "000000")
            cell.alignment = Alignment(vertical="top", wrap_text=c in (3, 5, 9, 10))
            cell.border = Border(bottom=THIN)
            if c in INPUT_COLS:
                cell.fill = YELLOW
        sheet.cell(row, 11).number_format = "yyyy-mm-dd"
    pick = DataValidation(type="list", formula1='"' + ",".join(stage_shops.FIELD_RESULTS) + '"', allow_blank=True,
                          showErrorMessage=True, errorTitle="확인 결과", error="목록에서 고르세요")
    sheet.add_data_validation(pick)
    pick.add(f"H2:H{max(last, 2)}")
    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = f"A1:M{max(last, 2)}"
    sheet.page_setup.orientation = "landscape"
    sheet.page_setup.fitToWidth = 1
    sheet.page_setup.fitToHeight = 0
    sheet.sheet_properties.pageSetUpPr.fitToPage = True
    sheet.print_title_rows = "1:1"

    # ---- 사용법
    guide.column_dimensions["A"].width = 16
    guide.column_dimensions["B"].width = 96
    lines = [
        ("안산 이웃 · 식료품 가게 현장 확인 목록", None, "title"),
        ("", None, None),
        ("왜 확인하나요", f"시민 앱 지도에는 영업 중인 것이 확인된 가게만 올립니다. 음식점은 영업 신고 대장으로 확인했지만, 포장 식품만 "
                     f"파는 가게는 신고 의무가 없어 공공 자료로는 확인할 수 없습니다. '{LIST_SHEET}' 시트의 식료품 가게 {n}곳을 "
                     f"확인해 주시면 '영업 중'인 곳이 지도에 다시 올라갑니다.", None),
        ("채우는 칸", "노란 칸(확인 결과 · 지금 간판 이름 · 메모 · 확인 날짜 · 확인한 사람)만 채웁니다. 회색 '가게 번호'는 고치지 마세요. "
                  "2행은 쓰는 법을 보여 주는 예시이고 반영되지 않습니다.", "yellow"),
        ("확인하는 법", "직접 가 보거나, '지도' 칸의 카카오맵 링크로 위치를 보고 전화 등으로 확인합니다.", None),
        ("확인 결과", "목록에서 고릅니다.", None),
        ("  영업 중", "그 이름의 가게가 지금 열려 있다(간판이 조금 달라도 같은 가게면 영업 중)", None),
        ("  문 닫음", "가게가 없어졌거나 비어 있다", None),
        ("  다른 가게", "그 자리에 다른 가게가 있다 — '지금 간판 이름'에 적어 주세요", None),
        ("  못 찾음", "주소에서 가게를 찾지 못했다", None),
        ("다 채우면", "파일을 앱 담당에게 돌려줍니다. 담당은 python pipeline\\import_field_check.py <이 파일> → "
                  "python pipeline\\stage_shops.py 로 지도에 반영합니다. '확인한 사람'은 이 엑셀 안에만 남고 앱 파일로 옮기지 않습니다.", None),
        ("", None, None),
        ("확인 현황", "(아래 숫자는 엑셀에서 열 때 계산됩니다)", "bold"),
    ]
    for a, b, style in lines:
        guide.append([a, b])
        row = guide.max_row
        guide.cell(row, 1).font = Font(name=FONT, size=14 if style == "title" else 10, bold=style in ("title", "bold") or (b and not a.startswith("  ")))
        guide.cell(row, 2).font = Font(name=FONT, size=10)
        guide.cell(row, 2).alignment = Alignment(wrap_text=True, vertical="top")
        if style == "yellow":
            guide.cell(row, 1).fill = YELLOW
    rng = f"'{LIST_SHEET}'!H{first}:H{max(last, first)}"
    stats = [("전체", f"=COUNTA('{LIST_SHEET}'!A{first}:A{max(last, first)})"),
             ("확인함", f"=COUNTA({rng})")] + [(f"  {k}", f'=COUNTIF({rng},"{k}")') for k in stage_shops.FIELD_RESULTS]
    stats.append(("남음", f"=B{guide.max_row + 1}-B{guide.max_row + 2}"))
    for a, formula in stats:
        guide.append([a, formula])
        guide.cell(guide.max_row, 1).font = Font(name=FONT, size=10)
        guide.cell(guide.max_row, 2).font = Font(name=FONT, size=10)
        guide.cell(guide.max_row, 2).alignment = Alignment(horizontal="left")
    guide.append([])
    guide.append(["자료 기준", f"공공 상가정보 {meta.get('std_ym', '')} · 영업 신고 대장(행정안전부 인허가) {meta.get('checked', '')} · "
                           f"목록 만든 날 {meta.get('made', '')}"])
    guide.cell(guide.max_row, 1).font = Font(name=FONT, size=10, bold=True)
    guide.cell(guide.max_row, 2).font = Font(name=FONT, size=10, color="666666")
    wb.calculation.fullCalcOnLoad = True          # 이 PC 에 LibreOffice 가 없어 미리 계산해 두지 못한다 — 엑셀이 열 때 계산
    wb.active = 1
    out.parent.mkdir(parents=True, exist_ok=True)
    wb.save(out)
    return out


def main() -> None:
    unverified = pd.read_csv(stage_shops.UNVERIFIED_CSV, dtype=str, encoding="utf-8-sig").fillna("")
    done = set(stage_shops.read_fieldcheck()["shop_id"])
    rows = field_rows(unverified, done)
    meta = {"std_ym": unverified["std_ym"].iloc[0] if len(unverified) else "",
            "checked": unverified["checked"].iloc[0] if len(unverified) else "",
            "made": datetime.date.today().isoformat()}
    out = build_workbook(rows, OUT, meta)
    print(f"[v] {out} · 식료품 {len(rows)}곳 (이미 현장 확인한 {len(done)}곳 제외)")
    print("    동별:", rows["dong_name"].value_counts().to_dict())


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
