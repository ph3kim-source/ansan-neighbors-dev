"""2안 공유 시연판(../2안_공유)을 만든다 — GitHub 저장소 → Streamlit Community Cloud(운영 콘솔) + GitHub Pages(시민 앱 링크).

    python pipeline\\build_html.py     # 먼저 — 시민 앱 HTML 판 · 제안 요약(늘 가상)
    python pipeline\\build_share.py

담는 것      운영 콘솔 코드(src), 앱이 읽는 가상 데이터, 보정 기준 공표 통계 2개, 동 경계, requirements, 테마,
             GitHub Pages 사이트(2026-11-23 사용자: "링크 주면 사람들이 볼 수 있게 플랫폼처럼") —
               index.html   첫 화면(pipeline/html/site.html — 서비스 소개 · 앱 열기 · QR · 넓은 화면에선 폰 틀 미리보기)
               app/         시민 앱 HTML 판(html/안산이웃_플랫폼.html 그대로 — 파일 안 가짜 서버, 가상)
               summary/     제안 요약(html/안산이웃_제안요약.html — 앱 링크만 ../app/ 로)
               .nojekyll    Pages 가 파일을 그대로 내보내게
             DS-017 · DS-014 원본은 빼고 집계 캐시(_cache/ds017_profile · ds017_daily · ds014_month)만 담는다.
담지 않는 것  기획 문서(docs/), 인벤토리 원본, 공표 원자료(xlsx·pdf·법무부 csv), 커뮤니티 DB, 보관본, 테스트,
             **민간 실데이터(data/real) — 이 저장소는 공개다.**
공유판 표시   루트의 SHARE_MODE 파일 → 방문자 세션마다 임시 커뮤니티 DB (config.SHARE_MODE · 실데이터 판은 켤 수 없음).
.git 폴더는 지우지 않으므로 다시 만든 뒤 commit · push 하면 된다.
"""
import os
import shutil
import stat
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
OUT = BASE.parent / "2안_공유"

COPY_FILES = [
    "src/app.py", "src/config.py", "src/geo.py", "src/metrics.py", "src/community.py", "src/gen_synthetic.py",
    "data/dong_master.csv", "data/geo/dong.geojson",
    "data/processed/dong_month.csv", "data/processed/gu_nat_month.csv",
    "data/synthetic/MANIFEST.txt", "data/synthetic/_cache/ds017_profile.csv",
    "data/synthetic/_cache/ds017_daily.csv", "data/synthetic/_cache/ds014_month.csv",
    "data/synthetic/_cache/ds032_grid.csv",
    "requirements.txt", ".streamlit/config.toml",
]
REPO_URL = "https://github.com/ph3kim-source/ansan-foreign-community-demo"
PAGES_URL = "https://ph3kim-source.github.io/ansan-foreign-community-demo/"   # 저장소 설정 → Pages: main / (root)
CONSOLE_URL = ""   # Streamlit Community Cloud 의 운영 콘솔 주소 — 알면 적는다(비어 있으면 첫 화면은 GitHub 실행 안내로 잇는다)
APP_HTML = BASE / "html" / "안산이웃_플랫폼.html"
SUMMARY_HTML = BASE / "html" / "안산이웃_제안요약.html"
SITE_TEMPLATE = BASE / "pipeline" / "html" / "site.html"
SYNTHETIC_GLOBS = ["GGC_SALES_YM_AMD_*.csv", "GYEONGGI_IN_STAT_PUBLIC_*.csv", "GYEONGGI_OUT_STAT_PUBLIC_*.csv"]
FORBIDDEN = ("docs/", "_archive", ".db", ".xlsx", ".pdf", "T38_", "T22_", "T1_", "tests/", "data/real", "STAGED.json",
             "zone_multicultural", "road_names")

README = f"""# 안산 이웃 (Ansan Neighbors) — 공유 시연판

외국인 주민 커뮤니티(언어방 익명 게시판) × 국적별 생활권 지도 × 시 공지·공식 Q&A 아이디어의 프로토타입입니다.

⚠️ 고향 사람 지도 · 글 · 행사는 가상 데이터입니다. 민간데이터(통신·카드·신용) 원본이 아니라 데이터 규격(컬럼명·코드값)을 따라
임의로 만든 값이며 실제 분포가 아닙니다. 지도의 가게와 공공 기관은 실제 공공 자료입니다. 안산시 공식 서비스가 아닙니다.

## 👉 [시연판 열기]({PAGES_URL})

링크 하나로 열립니다 — 휴대폰은 첫 화면의 QR 로, PC 는 첫 화면 오른쪽 휴대폰 틀에서 바로 눌러 볼 수 있습니다.

| 화면 | 누가 | 여는 법 |
|---|---|---|
| **시민 앱** (휴대폰 웹앱) | 외국인 주민 · 내국인 이웃 | [바로 열기]({PAGES_URL}app/) — 서버 · 설치 없이 브라우저에서 |
| **운영 콘솔** (Streamlit) | 안산시 담당자 | 이 저장소로 배포한 Streamlit 앱, 또는 아래 '로컬 실행' |
| **제안 요약** | 심사 · 담당자 | [바로 열기]({PAGES_URL}summary/) |

- 시민 앱: 첫 화면에서 언어 → 국적 → 동을 고르거나 시연 계정을 누릅니다. 홈 · 지도(고향 가게 · 공공 기관 · 고향 사람 많은 곳) · 커뮤니티(언어방) · 소식(행사 · 공지 · 시에 묻기) · 나, 5탭입니다.
- 지도의 가게는 공공 상가(상권)정보에서 고르고 식품 인허가 대장으로 영업 중인지 확인한 곳, 공공 기관은 법무부 · 고용노동부 · 한국건강가정진흥원 · 건강보험심사평가원 공개 목록입니다.
- 운영 콘솔: 생활권 동향(격자 지도 · KPI) · 행사 기획·효과 · 외국인 변화 · 공지·소통(공지 · Q&A 답변 · 신고 글 · 가게 정보 제보), 4탭입니다.
- 공유판의 두 화면은 서로 이어져 있지 않습니다. 콘솔에서 올린 공지가 앱에 뜨는 흐름은 원본 프로젝트의 서버 판에서 보여 줍니다.
- 글 · 댓글 · 신고는 방문자마다 따로 저장되고(시민 앱은 그 브라우저 안에만), 새로고침하면 처음 상태로 돌아갑니다.
- 사이트 파일: `index.html`(첫 화면) · `app/`(시민 앱) · `summary/`(제안 요약) — GitHub Pages(main 브랜치 / 루트)로 나갑니다.

## 로컬 실행 (운영 콘솔)

    pip install -r requirements.txt
    streamlit run src/app.py

가상 데이터를 다시 만들려면 `python src/gen_synthetic.py` (시간대 원본 약 100MB가 추가로 생깁니다).
"""
GITIGNORE = ("__pycache__/\n*.db\n.streamlit/secrets.toml\ndata/synthetic/T38_*.csv\ndata/synthetic/T22_*.csv\n"
             "data/real/\n")


def _writable(func, path, exc):
    """Windows '읽기 전용' 표시가 붙은 폴더(2안_공유의 data · data/synthetic 등)는 지우지 못한다 → 표시를 풀고 다시
    (3안 #23 과 같은 함정 — 중간에 멈추면 공유판 폴더가 반쯤 지워진 채로 남는다)."""
    os.chmod(path, stat.S_IWRITE)
    func(path)


def build_site() -> None:
    """GitHub Pages 사이트 — 첫 화면 · 시민 앱 · 제안 요약(모두 가상). build_html.py 결과를 쓴다."""
    import csv
    import datetime
    import re
    app = APP_HTML.read_text(encoding="utf-8")
    if '"mode":"synthetic"' not in app:
        sys.exit(f"{APP_HTML.name} 가 가상 판이 아님 — 공개 사이트에는 가상 판만. python pipeline\\build_html.py 로 다시 만든다")
    summary = SUMMARY_HTML.read_text(encoding="utf-8")
    link = f'href="{APP_HTML.name}"'
    if link not in summary:
        sys.exit("제안 요약에서 앱 링크를 못 찾음 — 사이트에서는 ../app/ 로 바꿔야 한다")
    summary = summary.replace(link, 'href="../app/"')
    with open(BASE / "data" / "public" / "shops_ansan.csv", encoding="utf-8-sig", newline="") as fh:
        shops = list(csv.DictReader(fh))
    with open(BASE / "data" / "public" / "facilities.csv", encoding="utf-8-sig", newline="") as fh:
        facilities = list(csv.DictReader(fh))
    console = (f'<a class="go" href="{CONSOLE_URL}">운영 콘솔 열기 →</a>' if CONSOLE_URL else
               f'<a class="go" href="{REPO_URL}#로컬-실행-운영-콘솔">운영 콘솔 실행 방법 (GitHub) →</a>')
    site = SITE_TEMPLATE.read_text(encoding="utf-8")
    for key, val in {"__SHOPS_N__": str(len(shops)), "__SHOPS_YM__": shops[0]["std_ym"], "__CHECKED__": shops[0]["checked"],
                     "__FAC_N__": str(len(facilities)), "__CONSOLE_LINK__": console, "__REPO_URL__": REPO_URL,
                     "__BUILT__": datetime.date.today().isoformat()}.items():
        site = site.replace(key, val)
    left = sorted(set(re.findall(r"__[A-Z_]+__", site)))
    if left:
        sys.exit(f"첫 화면에 채우지 못한 자리: {left}")
    (OUT / "index.html").write_text(site, encoding="utf-8")
    for rel, text in (("app/index.html", app), ("summary/index.html", summary)):
        (OUT / rel).parent.mkdir(parents=True, exist_ok=True)
        (OUT / rel).write_text(text, encoding="utf-8")
    for name in ("icon-192.png", "apple-touch-icon.png"):
        shutil.copy2(BASE / "app" / "icons" / name, OUT / name)
    (OUT / ".nojekyll").write_text("", encoding="utf-8")


def main() -> None:
    manifest = (BASE / "data" / "synthetic" / "MANIFEST.txt").read_text(encoding="utf-8-sig")
    if "가상 데이터" not in manifest:
        sys.exit("data/synthetic/MANIFEST.txt 가 가상 데이터 표시가 아님 — 공유판에는 가상 데이터만 담는다")
    OUT.mkdir(exist_ok=True)
    for item in OUT.iterdir():
        if item.name == ".git":
            continue
        if item.is_dir():
            shutil.rmtree(item, onexc=_writable)
        else:
            os.chmod(item, stat.S_IWRITE)
            item.unlink()
    files = [BASE / f for f in COPY_FILES]
    for pattern in SYNTHETIC_GLOBS:
        files += sorted((BASE / "data" / "synthetic").glob(pattern))
    for src in files:
        if not src.exists():
            sys.exit(f"없음: {src} — 먼저 python src\\gen_synthetic.py 를 실행하세요")
        dst = OUT / src.relative_to(BASE)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
    build_site()
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
