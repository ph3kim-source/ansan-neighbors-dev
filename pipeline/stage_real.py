"""2안 실데이터 적재 — 구글 드라이브(G:) 원본에서 2안이 쓰는 것만 data/real 로 옮긴다 (내부 분석 · 내부 시연용).

    python pipeline\\stage_real.py           옮기기 (이미 같은 원본이면 건너뜀)
    python pipeline\\stage_real.py --check   옮기지 않고 원본 위치 · 크기만 확인

옮기는 것 — 근거는 프로젝트 루트 data/2안_실데이터_대조.md (공개 저장소 밖 비공개 문서)
  DS-017 T38_AMD_INFLOW_TIME_F_POP   2026-01~06       원본 그대로
  DS-014 T22_GG_ADMI_FLOWPOP         2025-01~2026-06  헤더 공백 정리(2025-01~03) · 파일 안 날짜가 달 이름과 다르면 건너뜀
                                                      (2026-01 파일은 2월 파일과 바이트까지 같다 — 1월 없음)
  DS-056 GGC_SALES_YM_AMD            2026-01~06       외국인 행만(gb=03 · nt≠000) — 2안은 내국인 결제를 쓰지 않는다(최소 수집)
  DS-076 GYEONGGI_IN_STAT_PUBLIC     2026-01~06       안산에 사는(BS_SIGNGU 41271 · 41273) 행만 · K-10 PUBLIC 판만
  DS-077 GYEONGGI_OUT_STAT_PUBLIC    2026-01~06       안산에서 나간(BS_SIGNGU 41271 · 41273) 행만 · PUBLIC 판만
  다문화특구 경계                    시 내부 산출물(집계구 shp, EPSG:5179)
                                     → 하나로 합친 선을 WGS84 GeoJSON 으로 (zone_multicultural.geojson). 시 내부 산출물이라 실데이터 판에만.
  (50m 격자 DS-032 는 따로: pipeline/stage_grid.py — 원본이 커서 집계본만 남긴다)
  (격자 칸 거리 이름 — 도로명주소 도로구간(공공)은 따로: pipeline/stage_roads.py)

지키는 것
- data/real 은 .gitignore · pipeline/build_share.py · ../build_app_folders.py 가 모두 막는다 (공개 저장소 · 드라이브 앱에 안 들어감).
- 화면 · 로그에 원자료 행을 찍지 않는다 — 파일 이름 · 행 수 · 날짜 범위 · 고친 것만.
- 드라이브 폴더 ID 를 코드에 적지 않는다 — G:\\.shortcut-targets-by-id 아래에서 폴더 이름으로 찾고, 그 목록이 비어 보이면
  (드라이브를 다시 켠 뒤 — 2026-11-20) 내 드라이브의 '<폴더 이름>.lnk' 바로가기 하나만 따라간다.
- 시 드라이브 폴더 · 파일 이름도 코드에 적지 않는다 — 공개 저장소 밖 프로젝트 루트의 data/2안_드라이브_이름.json 에서 읽는다
  (2026-11-23 사용자 결정: 이름은 빼고 올린다). 그 파일이 없으면 적재만 멈추고, 이 모듈을 불러 쓰는 시험은 그대로 돈다.
- STAGED.json 에 원본 경로 · 크기 · sha256 · 날짜 범위 · 고친 것을 남긴다.
"""
import datetime
import hashlib
import io
import json
import subprocess
import sys
from pathlib import Path

import pandas as pd

BASE = Path(__file__).resolve().parents[1]
OUT = BASE / "data" / "real"
SHORTCUTS = Path(r"G:\.shortcut-targets-by-id")
MY_DRIVE = Path(r"G:\내 드라이브")           # 바로가기(.lnk) 자리 — '<폴더 이름>.lnk' 하나만 연다(다른 파일은 열지 않는다)
CATALOG = BASE.parent / "data" / "드라이브_파일목록.csv"
NAMES_FILE = BASE.parent / "data" / "2안_드라이브_이름.json"   # 시 드라이브 폴더 · 파일 이름 — 공개 저장소 밖에 둔다
_NAMES = json.loads(NAMES_FILE.read_text(encoding="utf-8")) if NAMES_FILE.exists() else {}
TOP = _NAMES.get("telecom_top", "")                         # 통신 · 카드 · 신용 원본이 든 바로가기 폴더
ANSAN_SGG = {"41271", "41273"}
M2026 = [f"2026{m:02d}" for m in range(1, 7)]
M2025 = [f"2025{m:02d}" for m in range(1, 13)]

# (DS, 연도 폴더, 하위 폴더, 파일 이름 틀, 달 목록, 방식)
PLAN = [
    ("DS-017", "구매데이터_안산시_2026", "통신데이터", "T38_AMD_INFLOW_TIME_F_POP_{ym}_4127.csv", M2026, "daily"),
    ("DS-014", "구매데이터_안산시_2025", "통신데이터", "T22_GG_ADMI_FLOWPOP_{ym}_4127.csv", M2025, "daily"),
    ("DS-014", "구매데이터_안산시_2026", "통신데이터", "T22_GG_ADMI_FLOWPOP_{ym}_4127.csv", M2026, "daily"),
    ("DS-056", "구매데이터_안산시_2026", "카드데이터", "GGC_SALES_YM_AMD_{ym}.csv", M2026, "card_foreign"),
    ("DS-076", "구매데이터_안산시_2026", "신용데이터", "GYEONGGI_IN_STAT_PUBLIC_{ym}.csv", M2026, "ansan_bs"),
    ("DS-077", "구매데이터_안산시_2026", "신용데이터", "GYEONGGI_OUT_STAT_PUBLIC_{ym}.csv", M2026, "ansan_bs"),
]


def _lnk_target(lnk: Path):
    """윈도 바로가기(.lnk)가 가리키는 경로 — WScript.Shell 로 읽는다. 못 읽으면 None."""
    path = str(lnk).replace("'", "''")
    cmd = ("[Console]::OutputEncoding = [Text.Encoding]::UTF8; "
           f"(New-Object -ComObject WScript.Shell).CreateShortcut('{path}').TargetPath")
    try:
        out = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", cmd],
                             capture_output=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        return None
    text = out.stdout.decode("utf-8", errors="replace").strip()
    return Path(text) if out.returncode == 0 and text else None


def shortcut_dir(top: str):
    """드라이브 바로가기 폴더(G:\\.shortcut-targets-by-id\\<ID>\\<top>). 드라이브를 다시 켠 뒤에는 이 목록이 비어 보이다가
    바로가기를 한 번 따라가면 채워진다(2026-11-20) — 그래서 못 찾으면 내 드라이브의 '<top>.lnk' 를 따라간다."""
    if SHORTCUTS.exists():
        for sid in SHORTCUTS.iterdir():
            if (sid / top).is_dir():
                return sid / top
    lnk = MY_DRIVE / f"{top}.lnk"
    if lnk.exists():
        target = _lnk_target(lnk)
        if target is not None and target.is_dir():
            return target
    return None


def drive_root() -> Path:
    if not TOP:
        sys.exit(f"[X] 드라이브 폴더 이름 파일이 없습니다 — {NAMES_FILE} (../data/드라이브_실데이터_안내.md §1)")
    if not Path("G:/").exists():
        sys.exit("[X] G: 가 없습니다 — 구글 드라이브 데스크톱이 켜져 있는지 확인")
    root = shortcut_dir(TOP)
    if root is None:
        sys.exit(f"[X] {TOP} 바로가기를 G: 에서 찾지 못했습니다 — ../data/드라이브_실데이터_안내.md §1")
    return root


def catalog_rows(match):
    """드라이브 파일목록(프로젝트 루트 data/ — py -3.12 ..\\data\\drive_catalog.py)에서 이름이 맞는 행.
    'Old Version' 폴더는 뺀다. 목록 파일이 없으면 None."""
    import csv
    if not CATALOG.exists():
        return None
    with open(CATALOG, encoding="utf-8-sig") as fh:
        return [r for r in csv.DictReader(fh) if match(r["name"]) and "Old Version" not in r["folder"]]


def is_utmk(prj_text: str) -> bool:
    """좌표계 이름은 제각각(KGD2002_Unified_Coordinate_System, Korea 2000 / Unified CS …)이고 매개변수 이름의
    대소문자도 다르다 — UTM-K(EPSG:5179) 매개변수 값으로 판정한다."""
    t = prj_text.replace(" ", "").lower()
    return all(k in t for k in ('"central_meridian",127.5', '"false_easting",1000000', '"false_northing",2000000',
                                '"scale_factor",0.9996'))


def find_source(root: Path, year_dir: str, sub: str, name: str, ym: str):
    """월 폴더는 '202508_재소급' 처럼 꼬리가 붙기도 하고, '표준데이터' 단계가 없기도 하다(2026-04 · 06)."""
    for month_dir in sorted((root / year_dir).glob(f"{ym}*")):
        for cand in (month_dir / "표준데이터" / sub / name, month_dir / sub / name):
            if cand.exists():
                return cand
    return None


def read_csv_bytes(raw: bytes) -> pd.DataFrame:
    """인코딩 판별 + 헤더 정리. 실물 함정: 헤더 쉼표 앞뒤 공백(T22 2025-01~03), 쉼표 대신 공백(T36 2026-01~03)."""
    for enc in ("utf-8-sig", "cp949"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise ValueError("인코딩 판별 실패")
    first, _, rest = text.partition("\n")
    header = [h.strip().strip('"') for h in first.strip().split(",")]
    sample = rest.partition("\n")[0].strip()
    n_data = len(sample.split(",")) if sample else len(header)
    if len(header) < n_data:  # 쉼표 대신 공백으로 붙은 헤더 → 공백으로 한 번 더 쪼갠다
        header = [p for h in header for p in h.split()]
    if len(header) != n_data:
        raise ValueError(f"헤더 {len(header)}칸 ≠ 자료 {n_data}칸")
    return pd.read_csv(io.StringIO(rest), header=None, names=header, dtype=str, keep_default_na=False)


def date_range(df: pd.DataFrame):
    col = next((c for c in ("ETL_YMD", "ta_ymd", "ETL_YM", "BS_YR_MON") if c in df.columns), None)
    if col is None:
        return None, None
    vals = pd.to_numeric(df[col], errors="coerce").dropna().astype("int64").astype(str)
    return (vals.min(), vals.max()) if len(vals) else (None, None)


def stage_one(ds, src: Path, root: Path, ym: str, mode: str, seen_hash: dict):
    """seen_hash 에는 실제로 옮긴 파일만 등록한다 — 잘못 납품된 달(예: 2월 내용이 든 '202601')을 먼저 만나도
    진짜 2월 파일이 '중복'으로 빠지지 않게."""
    raw = src.read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    rec = {"ds": ds, "file": src.name, "source": f"G:\\…\\{TOP}\\{src.relative_to(root).as_posix()}",
           "bytes": len(raw), "sha256": sha, "fixes": []}
    if sha in seen_hash:
        rec["skipped"] = f"{seen_hash[sha]} 와 바이트가 같다(중복 납품)"
        return rec, None
    df = read_csv_bytes(raw)
    original_cols = raw[:400].decode("utf-8-sig", errors="replace").partition("\n")[0]
    if ", " in original_cols or " ," in original_cols:
        rec["fixes"].append("헤더 공백 정리")
    lo, hi = date_range(df)
    rec["date_min"], rec["date_max"], rec["rows_source"] = lo, hi, len(df)
    if mode == "daily" and lo and (lo[:6] != ym or hi[:6] != ym):
        rec["skipped"] = f"파일 이름은 {ym} 인데 안의 날짜가 {lo}~{hi} — 잘못 납품된 달"
        return rec, None
    if mode == "card_foreign":
        df = df[(df["gb"] == "03") & (df["nt"] != "000")]
        rec["fixes"].append("외국인 행만(gb=03 · nt≠000)")
    elif mode == "ansan_bs":
        df = df[df["BS_SIGNGU"].isin(ANSAN_SGG)]
        rec["fixes"].append("안산 BS_SIGNGU 행만")
    rec["rows"] = len(df)
    seen_hash[sha] = src.name
    return rec, df


ZONE_TOP = _NAMES.get("gis_top", "")                         # 집계구 · 도로 GIS 바로가기 폴더 (stage_roads 도 쓴다)
ZONE_NAME = _NAMES.get("zone_shp", "")                       # 다문화특구 경계 shp 파일 이름
ZONE_PREFER = _NAMES.get("zone_prefer", "")                  # 같은 이름 shp 가 여러 폴더에 있으면 이 글자가 든 폴더를 먼저
ZONE_SOURCE = _NAMES.get("zone_source", "시 내부 산출물 (공개 여부 확인 전)")


def read_shp_rings(path: Path):
    """폴리곤 shp(형식 5 · 15 · 25)의 고리(ring) 목록 — geopandas 없이 표준 형식을 직접 읽는다."""
    import struct
    b = path.read_bytes()
    rings, pos = [], 100
    while pos + 8 <= len(b):
        clen = struct.unpack(">i", b[pos + 4:pos + 8])[0] * 2
        content, pos = b[pos + 8:pos + 8 + clen], pos + 8 + clen
        if len(content) < 44 or struct.unpack("<i", content[:4])[0] not in (5, 15, 25):
            continue
        nparts, npoints = struct.unpack("<ii", content[36:44])
        parts = list(struct.unpack(f"<{nparts}i", content[44:44 + 4 * nparts])) + [npoints]
        off = 44 + 4 * nparts
        pts = struct.unpack(f"<{2 * npoints}d", content[off:off + 16 * npoints])
        xy = list(zip(pts[0::2], pts[1::2]))
        rings += [xy[parts[i]:parts[i + 1]] for i in range(nparts)]
    return rings


def stage_zone() -> dict:
    """다문화특구 일원 경계 → 합친 선 → WGS84 GeoJSON. 드라이브 파일목록(프로젝트 루트 data/)에서 위치를 찾는다."""
    if not (ZONE_TOP and ZONE_NAME):
        return {"ds": "zone", "file": "zone_multicultural.geojson", "skipped": f"드라이브 폴더 이름 파일 없음 ({NAMES_FILE.name})"}
    from shapely.geometry import Polygon
    from shapely.ops import unary_union
    sys.path.insert(0, str(BASE / "src"))
    from geo import utmk_to_wgs84
    rows = catalog_rows(lambda name: name == ZONE_NAME)
    if rows is None:
        return {"ds": "zone", "file": ZONE_NAME, "skipped": "드라이브 파일목록 없음 (py -3.12 ..\\data\\drive_catalog.py)"}
    rows.sort(key=lambda r: not (ZONE_PREFER and ZONE_PREFER in r["folder"]))
    top_dir = shortcut_dir(ZONE_TOP)
    if not rows or top_dir is None:
        return {"ds": "zone", "file": ZONE_NAME, "skipped": "드라이브에 없음"}
    shp = top_dir / rows[0]["folder"] / ZONE_NAME
    prj = shp.with_suffix(".prj")
    if not is_utmk(prj.read_text(errors="ignore") if prj.exists() else ""):
        return {"ds": "zone", "file": ZONE_NAME, "skipped": "좌표계가 UTM-K(EPSG:5179) 매개변수가 아님 — 변환 규칙 확인 필요"}
    rings = read_shp_rings(shp)
    merged = unary_union([Polygon(r).buffer(0) for r in rings if len(r) >= 4]).simplify(1.0)

    def to_wgs(geom):
        polys = list(geom.geoms) if geom.geom_type == "MultiPolygon" else [geom]
        out = []
        for p in polys:
            xs, ys = zip(*p.exterior.coords)
            lon, lat = utmk_to_wgs84(list(xs), list(ys))
            out.append([[round(float(a), 7), round(float(b), 7)] for a, b in zip(lon, lat)])
        return {"type": "MultiPolygon", "coordinates": [[ring] for ring in out]}

    gj = {"type": "FeatureCollection", "features": [{"type": "Feature", "geometry": to_wgs(merged),
          "properties": {"name": "원곡동 다문화특구 일원", "source": ZONE_SOURCE}}]}
    (OUT / "zone_multicultural.geojson").write_text(json.dumps(gj, ensure_ascii=False), encoding="utf-8")
    return {"ds": "zone", "file": "zone_multicultural.geojson", "source": f"G:\\…\\{ZONE_TOP}\\{rows[0]['folder']}\\{ZONE_NAME}",
            "rows_source": len(rings), "rows": 1, "fixes": [f"집계구 {len(rings)}개 고리 → 하나로 합침 · EPSG:5179 → WGS84"],
            "area_km2": round(merged.area / 1e6, 3)}


def main() -> None:
    check = "--check" in sys.argv
    root = drive_root()
    OUT.mkdir(parents=True, exist_ok=True)
    manifest_path = OUT / "STAGED.json"
    old = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {"files": []}
    done = {r["sha256"]: r for r in old.get("files", []) if "skipped" not in r and "sha256" in r}
    records, seen_hash = [], {}
    for ds, year_dir, sub, pattern, months, mode in PLAN:
        for ym in months:
            name = pattern.format(ym=ym)
            src = find_source(root, year_dir, sub, name, ym)
            if src is None:
                records.append({"ds": ds, "file": name, "skipped": "드라이브에 없음"})
                print(f"  - {ds} {name}: 드라이브에 없음")
                continue
            if check:
                print(f"  · {ds} {name}: {src.stat().st_size / 1e6:.1f} MB")
                continue
            sha_hint = done.get(next((s for s, r in done.items() if r["file"] == name), None))
            if sha_hint and (OUT / name).exists() and sha_hint.get("bytes") == src.stat().st_size:
                records.append(sha_hint)
                seen_hash[sha_hint["sha256"]] = name
                print(f"  = {ds} {name}: 이미 있음")
                continue
            rec, df = stage_one(ds, src, root, ym, mode, seen_hash)
            records.append(rec)
            if df is None:
                print(f"  ! {ds} {name}: 건너뜀 — {rec['skipped']}")
                continue
            df.to_csv(OUT / name, index=False, encoding="utf-8-sig")
            fixes = (" · " + ", ".join(rec["fixes"])) if rec["fixes"] else ""
            print(f"  + {ds} {name}: {rec['rows']:,}행 · {rec.get('date_min')}~{rec.get('date_max')}{fixes}")
    if check:
        return
    zone = stage_zone()
    records.append(zone)
    print(f"  {'!' if 'skipped' in zone else '+'} 다문화특구 경계: {zone.get('skipped') or zone.get('fixes')}"
          + (f" · {zone['area_km2']} km²" if "area_km2" in zone else ""))
    records += [r for r in old.get("files", []) if r.get("ds") in ("DS-032", "roads")]  # stage_grid · stage_roads 기록은 남긴다
    manifest = {"staged": datetime.datetime.now().isoformat(timespec="seconds"),
                "note": "민간 실데이터(내부 분석용) — 공개 저장소 · 공유판 · 드라이브 앱 · 외부 서비스에 넣지 않는다",
                "_meta": {"synthetic": False}, "files": records}
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    kept = [r for r in records if "skipped" not in r]
    size = sum((OUT / r["file"]).stat().st_size for r in kept if (OUT / r["file"]).exists()) / 1e6
    print(f"[v] {OUT} — 파일 {len(kept)}개, {size:.0f} MB · 건너뜀 {len(records) - len(kept)}개 (STAGED.json)")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
