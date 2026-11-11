"""2안 공유 시연판(../2안_공유)을 만든다 — GitHub 저장소 → Streamlit Community Cloud 배포용.

    python pipeline\\build_share.py

담는 것      앱 코드(src), 앱이 읽는 가상 데이터, 보정 기준 공표 통계 2개, 동 경계, requirements, 테마.
             DS-017 원본(약 100MB)은 빼고 집계 캐시(_cache/ds017_profile.csv)만 담는다.
담지 않는 것  기획 문서(docs/), 인벤토리 원본, 공표 원자료(xlsx·pdf·법무부 csv), 커뮤니티 DB, 보관본, 테스트.
공유판 표시   루트의 SHARE_MODE 파일 → 방문자 세션마다 임시 커뮤니티 DB (config.SHARE_MODE).
.git 폴더는 지우지 않으므로 다시 만든 뒤 commit · push 하면 된다.
"""
import shutil
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
OUT = BASE.parent / "2안_공유"

COPY_FILES = [
    "src/app.py", "src/config.py", "src/geo.py", "src/metrics.py", "src/community.py", "src/gen_synthetic.py",
    "data/dong_master.csv", "data/geo/dong.geojson",
    "data/processed/dong_month.csv", "data/processed/gu_nat_month.csv",
    "data/synthetic/MANIFEST.txt", "data/synthetic/_cache/ds017_profile.csv",
    "requirements.txt", ".streamlit/config.toml",
]
SYNTHETIC_GLOBS = ["T37_AMD_STAY_F_POP_*.csv", "GGC_SALES_YM_AMD_*.csv", "T1_GG_50CELL_FLOWPOP_*.csv",
                   "GYEONGGI_IN_STAT_*.csv", "GYEONGGI_OUT_STAT_*.csv", "EVENT_*.csv"]
FORBIDDEN = ("docs/", "_archive", ".db", ".xlsx", ".pdf", "T38_", "tests/")

README = """# 안산 이웃 (Ansan Neighbors) — 공유 시연판

외국인 주민 커뮤니티(언어방 익명 게시판) × 국적별 생활권 지도 × 시 공지·공식 Q&A 아이디어의 프로토타입입니다.

⚠️ 모든 수치는 가상 데이터입니다. 민간데이터(통신·카드·신용) 원본이 아니라 데이터 규격(컬럼명·코드값)을 따라
임의로 만든 값이며 실제 분포가 아닙니다. 안산시 공식 서비스가 아닙니다.

## 둘러보기

- 왼쪽 사이드바에서 시연 사용자(우즈벡 고려인 노동자 · 베트남 결혼이민자 · 중국 동포 · 공무원)를 바꿔 보세요.
- 시민 화면: 내 생활권 · 생활권 지도 · 커뮤니티 · 행사·정책 · 공식 Q&A
- 공무원 화면: 생활권 동향 · 격자 히트맵 · 행사 기획·효과 · 전입·정착 · Q&A·신고 · KPI
- 글·댓글·신고는 방문자 세션마다 따로 저장되고, 새로고침하면 처음 상태로 돌아갑니다.

## 로컬 실행

    pip install -r requirements.txt
    streamlit run src/app.py

가상 데이터를 다시 만들려면 `python src/gen_synthetic.py` (시간대 원본 약 100MB가 추가로 생깁니다).
"""
GITIGNORE = "__pycache__/\n*.db\n.streamlit/secrets.toml\ndata/synthetic/T38_*.csv\n"


def main() -> None:
    OUT.mkdir(exist_ok=True)
    for item in OUT.iterdir():
        if item.name == ".git":
            continue
        shutil.rmtree(item) if item.is_dir() else item.unlink()
    files = [BASE / f for f in COPY_FILES]
    for pattern in SYNTHETIC_GLOBS:
        files += sorted((BASE / "data" / "synthetic").glob(pattern))
    for src in files:
        if not src.exists():
            sys.exit(f"없음: {src} — 먼저 python src\\gen_synthetic.py 를 실행하세요")
        dst = OUT / src.relative_to(BASE)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
    (OUT / "SHARE_MODE").write_text("공유 시연판 표시 파일 — 지우면 세션별 임시 DB가 꺼집니다.\n", encoding="utf-8")
    (OUT / "README.md").write_text(README, encoding="utf-8")
    (OUT / ".gitignore").write_text(GITIGNORE, encoding="utf-8")
    shipped = [p.relative_to(OUT).as_posix() for p in OUT.rglob("*") if p.is_file() and ".git" not in p.parts]
    bad = [p for p in shipped if any(f in p for f in FORBIDDEN)]
    if bad:
        sys.exit(f"담으면 안 되는 파일: {bad}")
    size_mb = sum((OUT / p).stat().st_size for p in shipped) / 1e6
    print(f"{OUT} — 파일 {len(shipped)}개, {size_mb:.1f} MB")


if __name__ == "__main__":
    main()
