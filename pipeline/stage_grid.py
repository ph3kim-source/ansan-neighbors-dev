"""2안 50m 격자 실물 적재 — DS-032 원본(한 달 3~4GB)을 드라이브에서 조각으로 읽어 작은 집계본만 남긴다 (내부 검토용).

    python pipeline\\stage_grid.py            2026-06 (기본)
    python pipeline\\stage_grid.py 202605     다른 달

남기는 것   data/real/_cache/ds032_grid.csv — 평일/주말 × 시각(config.GRID_HOURS) × 국적(외국인 전체 + 모든 국적) × 50m 셀
            하루 평균, 가림 전 값(비공개 폴더). 가림(config.GRID_MIN_POP)은 화면에서 칸을 묶은 뒤에 한다 —
            50m 칸 그대로 지우면 실물에서 셀이 거의 남지 않았다(첫 실행 2026-11-18). 원본은 data/real 에 복사하지 않는다.
지키는 것   원자료 행을 찍지 않는다 — 행 수 · 국적별 합계 비중 · 셀 수만. STAGED.json 에 출처 · 크기 · 처리 내용을 남긴다.
"""
import datetime
import json
import sys
import time
from pathlib import Path

import pandas as pd

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE / "src"))
sys.path.insert(0, str(BASE / "pipeline"))

import stage_real  # noqa: E402  (드라이브 찾기 재사용)

REAL = BASE / "data" / "real"


def main() -> None:
    import os
    os.environ["ANSAN_DATA"] = "real"            # metrics 를 실데이터 판으로 불러 집계 함수만 쓴다
    import config
    import metrics
    ym = next((a for a in sys.argv[1:] if a.isdigit() and len(a) == 6), "202606")
    root = stage_real.drive_root()
    name = f"T1_GG_50CELL_FLOWPOP_{ym}_4127.csv"
    src = stage_real.find_source(root, f"구매데이터_안산시_{ym[:4]}", "통신데이터", name, ym)
    if src is None:
        sys.exit(f"[X] 드라이브에 {name} 없음")
    size = src.stat().st_size
    print(f"원본 {name} · {size / 1e9:.2f} GB — 조각으로 읽는 중 (수 분)")
    t0 = time.time()
    cols = metrics.GRID_USECOLS + [f"{s}_{a}_CNT" for s in "MF" for a in range(10, 75, 5)] + ["M_75_UP", "F_75_UP"]
    seen = {"rows": 0}

    def chunks():
        for ch in pd.read_csv(src, encoding="utf-8-sig", usecols=lambda c: c.strip() in cols, chunksize=2_000_000,
                              dtype={"FORN_GB": str, "ETL_YMD": str, "ADMI_NM": str}, low_memory=False):
            seen["rows"] += len(ch)
            print(f"  … {seen['rows'] / 1e6:.0f}백만 행 ({time.time() - t0:.0f}초)", flush=True)
            yield ch

    # 한 번 읽어 두 집계본을 만든다 — 관리자 격자(GRID_HOURS, 예전과 같은 파일)와 시민 앱 골목 칸(CELL_HOURS, 24시간).
    # 하루 평균의 날 수는 시각과 관계없이 같으므로(모든 날에 모든 시각이 있다) 24시간 집계에서 시각만 골라도 예전과 같다.
    hours = sorted(set(config.GRID_HOURS) | set(config.CELL_HOURS))
    grid_all = metrics.grid_aggregate(chunks(), hours)                  # 가림 전 · 모든 국적
    grid = grid_all[grid_all["TIME_CD"].isin(config.GRID_HOURS)].reset_index(drop=True)
    out = REAL / "_cache" / metrics.GRID_CACHE
    out.parent.mkdir(parents=True, exist_ok=True)
    grid.to_csv(out, index=False, encoding="utf-8-sig")
    cells_out = REAL / "_cache" / metrics.CELL_CACHE
    grid_all.to_csv(cells_out, index=False, encoding="utf-8-sig")
    metrics.ds032_grid.cache_clear()
    metrics.ds032_cells24.cache_clear()
    metrics.presence_cells.cache_clear()
    print(f"[v] {cells_out} — 24시간 {len(grid_all):,}행 (시민 앱 골목 칸)")
    for nat in sorted(set(grid_all["NAT"]) - {metrics.GRID_ALL, "기타"}):      # 국적별로 골목 칸을 쓸 수 있는지 — 비율만 찍는다
        c = metrics.cells_from_grid(grid_all, nat, config.CELL_HEX_AREA_M2, config.CELL_MIN_POP, config.CELL_USABLE_SHARE,
                                    with_stats=True)
        if c:
            print(f"    골목 칸 {nat}: {'씀' if c['usable'] else '안 씀'} · 가림 뒤 남는 인원 중앙값 {c['retained'] * 100:.0f}% "
                  f"· 칸 {len(c['hex'])}개")
    nat_share = (grid[grid["NAT"] != metrics.GRID_ALL].groupby("NAT")["POP"].sum()
                 / grid.loc[grid["NAT"] == metrics.GRID_ALL, "POP"].sum() * 100).round(1)
    cells = grid[grid["NAT"] == metrics.GRID_ALL][["UTMK_X", "UTMK_Y"]].drop_duplicates()
    print(f"[v] {out} — {len(grid):,}행 · 50m 셀 {len(cells):,}개 · {time.time() - t0:.0f}초")
    print("    국적 합계 비중 % (상위 12):", nat_share.sort_values(ascending=False).head(12).to_dict())
    for res in config.GRID_RES_OPTIONS:      # 가림(묶은 뒤 GRID_MIN_POP) 후 남는 칸 수 — 평일 오후 2시
        n_all = len(metrics.grid_cells(metrics.GRID_ALL, "평일", 14, res))
        n_nat = {n: len(metrics.grid_cells(n, "평일", 14, res)) for n in nat_share.sort_values(ascending=False).head(6).index}
        print(f"    {res}m 칸: 외국인 전체 {n_all}칸 · 국적별 {n_nat}")
    manifest_path = REAL / "STAGED.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {"files": []}
    manifest["files"] = [r for r in manifest["files"] if r.get("ds") != "DS-032"]
    staged = datetime.datetime.now().isoformat(timespec="seconds")
    source = f"G:\\…\\{stage_real.TOP}\\{src.relative_to(root).as_posix()}"
    manifest["files"].append({
        "ds": "DS-032", "file": metrics.GRID_CACHE, "source": source,
        "bytes_source": size, "rows_source": seen["rows"], "rows": len(grid),
        "fixes": [f"외국인 행만 · 시각 {config.GRID_HOURS} · 평일/주말 하루 평균 · 가림 전 값(화면에서 칸 묶은 뒤 "
                  f"{config.GRID_MIN_POP:g} 미만 가림) · 원본 미복사"],
        "staged": staged})
    manifest["files"].append({
        "ds": "DS-032", "file": metrics.CELL_CACHE, "source": source, "bytes_source": size, "rows": len(grid_all),
        "fixes": ["외국인 행만 · 0~23시 · 평일/주말 하루 평균 · 가림 전 값 — 시민 앱이 육각 칸(≈H3 res9)으로 묶은 뒤 "
                  f"{config.CELL_MIN_POP:g} 미만 가림 · 원본 미복사"],
        "staged": staged})
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
