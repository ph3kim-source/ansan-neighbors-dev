# -*- coding: utf-8 -*-
"""안산시 외국인주민 통계 월별 xlsx -> tidy CSV

입력  2안/data/(게시용)외국인주민_통계(YYYY.M.).xlsx  x 10개월
출력  2안/data/processed/dong_month.csv      동 x 월   (IPF 마진 A)
      2안/data/processed/gu_nat_month.csv    구 x 국적 x 월 (IPF 마진 B)
      2안/data/processed/city_nat_month.csv  시 x 국적 x 월

v2 에서 쓰는 곳  dong_month · gu_nat_month → src/config.py ANCHOR_* → gen_synthetic.py 가상 데이터 총량 보정
                 (city_nat_month 는 v2 가 읽지 않는다)
실행             새 달 통계 xlsx 를 data/ 에 넣고  python pipeline\\prep.py  → 그다음 python src\\gen_synthetic.py
내력             v1(관광객안) src/prep.py 를 2026-11-16 그대로 옮겨 왔다. v1 보관본은 ../_보관/2안_v1_관광객안

함정
  - 동명에 공백이 섞여 있음 ('일    동', '사 이 동', '본오 1동')
  - 5행은 비율 행이므로 데이터로 읽으면 안 됨
  - 연번이 비어 있는 국적 행(한국계중국인/한국계러시아인/고려인/국적불명)은
    동포 분류라 순수 국적과 성격이 다름 -> is_diaspora 플래그로 구분
  - ★ 구(단원구/상록구) 시트의 '총계(ⓐ+ⓑ)' 헤더는 실제와 다름.
    값은 등록외국인(ⓐ)만 담고 있고 외국국적동포(ⓑ)가 빠져 있음.
    시(외국인현황) 시트의 총계와 대조해 확인함:
      우즈베키스탄 구합 total=2871 = reg_foreign / 시 total=9809 = 2871+6938
    -> 진짜 국적 규모는 total_all = reg_foreign + diaspora 로 계산해야 함.
    이 열을 쓰지 않으면 우즈베키스탄(동포 71%)·카자흐스탄(63%)·
    한국계중국인(66%) 규모를 크게 과소평가하게 됨.
"""
import csv
import glob
import os
import re
import sys

import openpyxl

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(BASE, "data")
OUT = os.path.join(DATA, "processed")

# 동별현황 시트 열 배치 (0-indexed). 5행 헤더 기준 계/남/여 3칸씩
DONG_COLS = {
    "pop_total": 1,      # 외국인주민 포함 총인구
    "pop_kor_reg": 4,    # 내국인 + 등록외국인
    "pop_kor": 7,        # 내국인
    "reg_foreign": 10,   # 등록외국인
    "diaspora": 13,      # 외국국적동포 거소신고자
    "foreign_resident": 17,  # 외국인주민 (등록외국인 + 동포)
}

# 단원구/상록구 시트 열 배치 (0-indexed)
GU_COLS = [
    ("total", 2), ("reg_foreign", 3), ("employ_permit", 4), ("visit_work", 5),
    ("marriage", 6), ("study", 7), ("professional", 8), ("refugee", 9),
    ("visit_family", 10), ("permanent", 11), ("etc", 12), ("diaspora", 13),
]

# 외국인현황(시 전체) 시트 열 배치. 3열은 정체 불명이라 읽지 않음
CITY_COLS = [
    ("total", 2), ("reg_foreign", 4), ("employ_permit", 5), ("visit_work", 6),
    ("marriage", 7), ("study", 8), ("professional", 9), ("refugee", 10),
    ("visit_family", 11), ("permanent", 12), ("etc", 13), ("diaspora", 15),
]

DIASPORA_LABELS = {"한국계중국인", "한국계러시아인", "고려인", "국적불명"}


def norm(s):
    """'일    동' -> '일동', '본오 1동' -> '본오1동'"""
    if s is None:
        return ""
    return re.sub(r"\s+", "", str(s))


def num(v):
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return int(round(v))
    s = str(v).strip().replace(",", "")
    if s in ("", "-", "·", "*"):
        return None
    try:
        return int(round(float(s)))
    except ValueError:
        return None


def month_of(path):
    m = re.search(r"\((\d{4})\.\s*(\d{1,2})\.?\)", os.path.basename(path))
    if not m:
        return None
    return "%s-%02d" % (m.group(1), int(m.group(2)))


def parse_dong(ws, ym):
    """동별현황 -> 25개 행정동. 상록구/단원구 마커로 구를 판정"""
    rows, gu = [], None
    for r in ws.iter_rows(min_row=6, values_only=True):
        name = norm(r[0])
        if not name:
            continue
        if name == "계":
            continue
        if name in ("상록구", "단원구"):
            gu = name
            continue
        if num(r[1]) is None:
            continue
        rec = {"ym": ym, "gu": gu, "dong": name}
        for k, c in DONG_COLS.items():
            rec[k] = num(r[c])
        rows.append(rec)
    return rows


def parse_nat(ws, ym, gu, cols, start_row=6):
    """국적별 시트 -> 국적 x 체류자격. 5행(비율)은 min_row로 건너뜀"""
    rows = []
    for r in ws.iter_rows(min_row=start_row, values_only=True):
        nat = norm(r[1])
        if not nat or nat == "계":
            continue
        seq = norm(r[0])
        rec = {
            "ym": ym,
            "gu": gu,
            "nat": nat,
            "seq": seq if seq else "",
            # 연번 없는 행 = 동포 분류 (순수 국적 집계와 성격이 다름)
            "is_diaspora": 1 if (not seq or nat in DIASPORA_LABELS) else 0,
        }
        for k, c in cols:
            rec[k] = num(r[c]) if c < len(r) else None
        if rec["total"] is None:
            continue
        # 구 시트의 total은 등록외국인만 담고 있으므로 동포를 더해 실제 규모를 만든다
        rec["total_all"] = (rec["reg_foreign"] or 0) + (rec["diaspora"] or 0)
        rows.append(rec)
    return rows


def write_csv(path, rows, fields):
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    print("  %-22s %5d행" % (os.path.basename(path), len(rows)))


def main():
    files = {}
    for p in glob.glob(os.path.join(DATA, "*외국인주민_통계*.xlsx")):
        ym = month_of(p)
        if ym is None:
            print("  [skip] 월 추출 실패:", os.path.basename(p))
            continue
        # 같은 달이 중복 수집된 경우 파일명이 짧은 쪽을 채택 ('(1)' 제거)
        if ym not in files or len(p) < len(files[ym]):
            files[ym] = p

    dong, gu_nat, city_nat = [], [], []
    for ym in sorted(files):
        wb = openpyxl.load_workbook(files[ym], data_only=True)
        dong += parse_dong(wb["동별현황"], ym)
        for g in ("단원구", "상록구"):
            gu_nat += parse_nat(wb[g], ym, g, GU_COLS)
        city_nat += parse_nat(wb["외국인현황"], ym, "안산시", CITY_COLS)
        wb.close()

    print("월:", ", ".join(sorted(files)))
    print("출력")
    write_csv(os.path.join(OUT, "dong_month.csv"), dong,
              ["ym", "gu", "dong"] + list(DONG_COLS))
    nat_fields = (["ym", "gu", "nat", "seq", "is_diaspora", "total_all"]
                  + [k for k, _ in GU_COLS])
    write_csv(os.path.join(OUT, "gu_nat_month.csv"), gu_nat, nat_fields)
    write_csv(os.path.join(OUT, "city_nat_month.csv"), city_nat, nat_fields)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
