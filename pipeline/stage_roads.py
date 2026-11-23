"""2안 격자 칸 거리 이름 — 도로명주소 도로구간(행정안전부 공공 자료, 드라이브 GIS 폴더 사본)에서 안산 도로만 골라
'50m 칸 × 도로명 × 길이' 표로 줄인다 → data/real/road_names_50m.csv

    python pipeline\\stage_roads.py

왜 이렇게 (docs/기획_결정사항.md 결정 12)
- 길(도로 구간) 단위 인구 자료는 인벤토리에 없다 — 가장 잘게 나뉜 것이 DS-032 50m 칸이다. 그래서 길마다 값을 매기지 않고,
  칸을 부르는 이름만 붙인다(칸 안을 가장 길게 지나는 도로명 → '○○로 일대'). 그 길 위의 인원이라는 뜻이 아니다.
- 도로 자료는 공공이지만 이름을 붙일 '밀집 칸'이 실데이터라 결과를 실데이터 폴더(data/real)에 둔다 —
  가상 격자에 실제 도로명을 붙이면 사실처럼 읽힐 수 있어 공유판(가상)에는 넣지 않는다.
- 고속도로는 뺀다(칸 이름으로 맞지 않음). 좌표계가 DS-032 와 같은 UTM-K(EPSG:5179)인지 확인한 뒤에만 쓴다.
- geopandas 없이 shp · dbf 표준 형식을 직접 읽는다(2안 환경 = python 3.13). 파일 위치는 드라이브 파일목록에서 이름으로 찾는다.
"""
import datetime
import json
import struct
import sys
from fnmatch import fnmatch
from pathlib import Path

import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE / "pipeline"))

import stage_real  # noqa: E402  (드라이브 찾기 · 파일목록 · 좌표계 판정 재사용)

TOP = stage_real.ZONE_TOP                # GIS 바로가기 폴더 이름 — 공개 저장소 밖 ../data/2안_드라이브_이름.json 에서 (stage_real)
PATTERN = "TL_SPRD_MANAGE_41_*.shp"     # 경기 도로구간 — 끝 6자리 = 기준 연월
OUT_FILE = "road_names_50m.csv"
CELL = 50                                # DS-032 칸 크기(m)
STEP = 5.0                               # 선을 5m 간격 점으로 쪼개 칸마다 길이를 나눈다
SKIP_SUFFIX = ("고속도로",)


def read_dbf(path, fields, encoding=None):
    """dBASE 표에서 고른 열만 문자열로 읽는다 → (DataFrame, 인코딩). 지운 표시(*) 행도 남긴다(deleted 열) —
    shp 레코드 순번과 행 번호를 맞추기 위해서. 인코딩을 안 주면 utf-8 로 읽어 보고 안 되면 cp949."""
    b = Path(path).read_bytes()
    n, hlen, rlen = struct.unpack("<IHH", b[4:12])
    specs, pos, off = {}, 32, 1
    while pos < hlen and b[pos] != 0x0D:
        name = b[pos:pos + 11].split(b"\0")[0].decode("ascii", "replace")
        specs[name] = (off, b[pos + 16])
        off += b[pos + 16]
        pos += 32
    missing = [f for f in fields if f not in specs]
    if missing:
        raise ValueError(f"dbf 에 {missing} 열이 없음 — 도로구간 규격 확인")
    recs = [b[hlen + i * rlen: hlen + (i + 1) * rlen] for i in range(n)]
    raw = {f: [r[specs[f][0]: specs[f][0] + specs[f][1]] for r in recs] for f in fields}
    if encoding is None:
        try:
            for vals in raw.values():
                for v in vals:
                    v.decode("utf-8")
            encoding = "utf-8"
        except UnicodeDecodeError:
            encoding = "cp949"
    df = pd.DataFrame({f: [v.decode(encoding, errors="replace").strip() for v in vals] for f, vals in raw.items()})
    df["deleted"] = [r[:1] == b"*" for r in recs]
    return df, encoding


def read_shp_lines(path, keep=None) -> dict:
    """선 shp(형식 3 · 13 · 23) → {레코드 순번(0부터): [점 배열(n×2), ...]}. keep 을 주면 그 순번만 읽는다."""
    b = Path(path).read_bytes()
    out, pos, idx = {}, 100, -1
    while pos + 8 <= len(b):
        clen = struct.unpack(">i", b[pos + 4:pos + 8])[0] * 2
        content, pos = b[pos + 8:pos + 8 + clen], pos + 8 + clen
        idx += 1
        if keep is not None and idx not in keep:
            continue
        if len(content) < 44 or struct.unpack("<i", content[:4])[0] not in (3, 13, 23):
            continue
        nparts, npoints = struct.unpack("<ii", content[36:44])
        parts = list(struct.unpack(f"<{nparts}i", content[44:44 + 4 * nparts])) + [npoints]
        pts = np.frombuffer(content, dtype="<f8", count=2 * npoints, offset=44 + 4 * nparts).reshape(-1, 2)
        out[idx] = [pts[parts[k]:parts[k + 1]] for k in range(nparts)]
    return out


def cell_lengths(lines, res: int = CELL, step: float = STEP) -> pd.DataFrame:
    """[(도로명, [점 배열, ...]), ...] → (칸 왼쪽아래 x0, y0, RN) 별 길이(m).
    선분을 step 간격 점으로 쪼개 점이 든 칸에 길이를 나눠 준다 — 칸 길이의 합은 선 길이와 같고(정확),
    칸 경계에서만 step/2 안쪽으로 어긋난다."""
    starts, ends, names = [], [], []
    for name, parts in lines:
        for p in parts:
            p = np.asarray(p, dtype=float)
            if len(p) < 2:
                continue
            starts.append(p[:-1])
            ends.append(p[1:])
            names.append(np.full(len(p) - 1, name, dtype=object))
    if not starts:
        return pd.DataFrame(columns=["x0", "y0", "RN", "len_m"])
    a = np.concatenate(starts)
    d = np.concatenate(ends) - a
    nm = np.concatenate(names)
    length = np.hypot(d[:, 0], d[:, 1])
    k = np.where(length > 0, np.ceil(length / step), 0).astype(np.int64)
    seg = np.repeat(np.arange(len(length)), k)
    j = np.arange(k.sum()) - np.repeat(np.cumsum(k) - k, k)
    t = (j + 0.5) / k[seg]
    px = a[seg, 0] + d[seg, 0] * t
    py = a[seg, 1] + d[seg, 1] * t
    df = pd.DataFrame({"x0": (np.floor(px / res) * res).astype(np.int64),
                       "y0": (np.floor(py / res) * res).astype(np.int64),
                       "RN": nm[seg], "len_m": (length / np.maximum(k, 1))[seg]})
    return df.groupby(["x0", "y0", "RN"], as_index=False)["len_m"].sum()


def ansan_roads(dbf: pd.DataFrame) -> pd.DataFrame:
    """안산(상록구 41271 · 단원구 41273) 도로구간 중 이름 있는 것 · 고속도로 뺀 것 · 지운 표시 없는 것."""
    keep = (dbf["SIG_CD"].isin(stage_real.ANSAN_SGG) & ~dbf["deleted"] & (dbf["RN"] != "")
            & ~dbf["RN"].str.endswith(SKIP_SUFFIX))
    return dbf[keep]


def main() -> None:
    if not TOP:
        sys.exit(f"[X] 드라이브 폴더 이름 파일이 없습니다 — {stage_real.NAMES_FILE} (../data/드라이브_실데이터_안내.md §1)")
    rows = stage_real.catalog_rows(lambda name: fnmatch(name, PATTERN))
    if rows is None:
        sys.exit("[X] 드라이브 파일목록 없음 — py -3.12 ..\\data\\drive_catalog.py")
    if not rows:
        sys.exit(f"[X] 드라이브 파일목록에 {PATTERN} 없음")
    rows.sort(key=lambda r: (r["name"], r["folder"]), reverse=True)        # 최신 기준 연월
    top_dir = stage_real.shortcut_dir(TOP)
    if top_dir is None:
        sys.exit(f"[X] {TOP} 바로가기를 G: 에서 찾지 못했습니다 — ../data/드라이브_실데이터_안내.md §1")
    shp = top_dir / rows[0]["folder"] / rows[0]["name"]
    prj = shp.with_suffix(".prj")
    if not stage_real.is_utmk(prj.read_text(errors="ignore") if prj.exists() else ""):
        sys.exit("[X] 좌표계가 UTM-K(EPSG:5179) 매개변수가 아님 — 변환 규칙 확인 필요")
    print(f"원본 {shp.name} · {(shp.stat().st_size + shp.with_suffix('.dbf').stat().st_size) / 1e6:.0f} MB — 읽는 중")
    dbf, enc = read_dbf(shp.with_suffix(".dbf"), ["RN", "SIG_CD"])
    ansan = ansan_roads(dbf)
    lines = read_shp_lines(shp, keep=set(ansan.index))
    cells = cell_lengths([(ansan.at[i, "RN"], lines[i]) for i in ansan.index if i in lines])
    cells["len_m"] = cells["len_m"].round(1)
    stage_real.OUT.mkdir(parents=True, exist_ok=True)
    out = stage_real.OUT / OUT_FILE
    cells.to_csv(out, index=False, encoding="utf-8-sig")
    in_ansan = dbf["SIG_CD"].isin(stage_real.ANSAN_SGG)
    rec = {"ds": "roads", "file": OUT_FILE, "public_data": True,
           "source": f"G:\\…\\{TOP}\\{rows[0]['folder']}\\{rows[0]['name']}",
           "bytes_source": shp.stat().st_size + shp.with_suffix(".dbf").stat().st_size,
           "rows_source": len(dbf), "rows": len(cells),
           "fixes": [f"안산(41271 · 41273) 도로구간만 · 고속도로 제외 · {STEP:g}m 간격 점으로 {CELL}m 칸 × 도로명 길이 · "
                     f"dbf {enc} · EPSG:5179 확인"],
           "staged": datetime.datetime.now().isoformat(timespec="seconds")}
    manifest_path = stage_real.OUT / "STAGED.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {"files": []}
    manifest["files"] = [r for r in manifest.get("files", []) if r.get("ds") != "roads"] + [rec]
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[v] {out} — 경기 도로구간 {len(dbf):,}개 중 안산 {int(in_ansan.sum()):,}개 → 쓴 것 {len(ansan):,}개 "
          f"(고속도로 · 이름 없음 · 지움 표시 {int(in_ansan.sum()) - len(ansan):,}개 뺌) · 도로명 {ansan['RN'].nunique():,}개 · "
          f"{CELL}m 칸 {cells[['x0', 'y0']].drop_duplicates().shape[0]:,}개 · 길이 합 {cells['len_m'].sum() / 1000:,.0f} km")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
