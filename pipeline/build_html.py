"""2안 '안산 이웃' HTML 판 — 브라우저로 바로 여는 파일 두 개(서버 · 설치 없음).

    python pipeline\\build_html.py            → html\\안산이웃_플랫폼.html (시민 앱) · html\\안산이웃_제안요약.html (제안 요약)
    python pipeline\\build_html.py --check    → 데이터 크기 · 요약만 출력 (파일 안 씀)

안산이웃_플랫폼.html = 시민 휴대폰 웹앱(app/) 그대로 (2026-11-23 사용자 결정 — "시민들은 제안 요약을 안 봐도 된다,
진짜 시민이 쓸 수 있게"). 예전 시연판의 틀(시연 사용자 바꾸기 · 시연 순서 · 민간데이터 끄기 · 브라우저 · 휴대폰 모형 ·
운영 콘솔 · 제안 요약 탭)은 뺐다. 운영 콘솔은 Streamlit(실행.bat), 제안 요약은 안산이웃_제안요약.html 로 따로 둔다.
- 앱 코드는 고치지 않는다. index.html 의 CSS · Leaflet 은 끼워 넣고, ES 모듈은 import map(data: URL)으로 싣는다.
- 서버(src/server.py) 대신 같은 파일 안의 가짜 서버(pipeline/html/demo_api.js)가 /api 를 받는다 — fetch 를 가로챈다.
  고정 응답(bootstrap · 지도 경계 · 가게 · 고향 사람 많은 곳 단계 · 모임 장소 힌트)은 아래 build_app_api 가 server.py 의
  처리 함수를 그대로 불러 뽑고, 글 · 댓글 · 공지 · 질문은 가상 시드 DB 를 통째로 담아 demo_api.js 가 같은 규칙으로 다룬다.
  주민이 쓴 글 · 질문 · 추천은 그 탭에만 남는다(새로 고치면 처음 상태).
- 지도 바탕은 OpenStreetMap 타일(인터넷 필요) — 앱과 같다. 오프라인이면 바탕 없이 가게 점과 동 경계만 보인다.
- 홈 화면 설치(manifest · 서비스 워커)는 파일로 열면 쓸 수 없어 뺐다(앱 main.js 도 file: 에서는 서비스 워커를 켜지 않는다).

이 HTML 은 늘 가상 데이터로 만든다 — 실데이터 판(ANSAN_DATA=real)으로는 만들지 않는다(파일로 퍼지는 산출물이라서).
- 통신 자료는 동네 단계(1~4)와 가게의 '고향 사람 많은 곳' 있다/없다만 담는다. 비중 · 인원(POP)은 넣지 않는다.
- 가게는 공공 상가정보 + 인허가 대장 확인(data/public/shops_ansan.csv — 공개 자료, 저장소에도 있다).
화면 코드: app/(그대로) + pipeline/html/demo_api.js(가짜 서버) · pipeline/html/proposal.html(제안 요약 틀).
예전 판: 브라우저 + 휴대폰 + 운영 콘솔 + 제안 요약 탭 시연판은 ../_보관/2안_이전시민화면_20261120/,
줄이기 전 전체기능판은 ../_보관/2안_html_전체기능판_20261116/.
"""
import asyncio
import base64
import datetime as dt
import json
import re
import sqlite3
import sys
import tempfile
from pathlib import Path
from urllib.parse import urlencode

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE / "src"))

import config as C  # noqa: E402

if C.IS_REAL:
    sys.exit("HTML 판은 가상 데이터로만 만든다 — ANSAN_DATA 환경변수를 지우고 다시 실행하세요")
import community as cm  # noqa: E402
import metrics as M  # noqa: E402

SRC = BASE / "pipeline" / "html"
APP_DIR = BASE / "app"
OUT = BASE / "html" / "안산이웃_플랫폼.html"
OUT_PROPOSAL = BASE / "html" / "안산이웃_제안요약.html"


# ------------------------------------------------------------------ 가짜 서버 자료 (가상 시드 DB · server.py 처리 함수)
def _request(path: str, token: str = "", query: str = ""):
    from starlette.requests import Request
    headers = [(b"authorization", f"Bearer {token}".encode())] if token else []
    return Request({"type": "http", "method": "GET", "path": path, "query_string": query.encode(),
                    "headers": headers, "path_params": {}})


def _call(handler, path: str, token: str = "", query: str = ""):
    """server.py 의 처리 함수를 서버 없이 그대로 불러 JSON 을 받는다 (앱이 받는 것과 같은 값)."""
    resp = asyncio.run(handler(_request(path, token, query)))
    assert resp.status_code == 200, (path, query, resp.status_code, resp.body[:200])
    return json.loads(resp.body)


def _encode_levels(levels: dict, codes: list) -> dict:
    """{요일: {시: {동: 1~4|None}}} → {요일: [24개 글자열]} — 동 순서 codes, None = '.' (크기 줄이기, 브라우저가 되푼다)."""
    out = {}
    for day, hours in levels.items():
        rows = []
        for h in range(24):
            row = hours[str(h)] if str(h) in hours else hours[h]
            assert list(row) == codes, "동 순서가 시각마다 같아야 한다"
            rows.append("".join("." if v is None else str(int(v)) for v in row.values()))
        assert len(hours) == 24
        out[day] = rows
    return out


def _decode_levels(enc: dict, codes: list) -> dict:
    return {day: {str(h): {c: (None if ch == "." else int(ch)) for c, ch in zip(codes, row)}
                  for h, row in enumerate(rows)} for day, rows in enc.items()}


def build_app_api() -> dict:
    """가짜 서버 자료 — 임시 DB 에 가상 시드를 새로 깔고 읽는다(시연용 data/community.db 는 건드리지 않는다)."""
    import server as SV
    tmp = Path(tempfile.mkdtemp(prefix="ansan_demo_")) / "community.db"
    cm.set_default_db(tmp)
    try:
        cm.init_db()
        built = dt.datetime.now().replace(microsecond=0)
        official = cm.user_by_persona("official")
        tok = cm.create_session(official["id"])
        boot = _call(SV.bootstrap, "/api/bootstrap")
        shops = _call(SV.shops, "/api/shops", tok)          # 공무원 판 = '고향 사람 많은 곳' 표시 없음 · 추천 0
        assert not any(s.get("near") for s in shops["shops"])
        presence, near, meetup, codes = {}, {}, {}, None
        for nat in C.NAT_NAMES:
            p = _call(SV.presence, "/api/presence", tok, urlencode({"nat": nat}))
            codes = codes or list(next(iter(next(iter(p["levels"].values())).values())))
            enc = _encode_levels(p["levels"], codes)
            assert _decode_levels(enc, codes) == json.loads(json.dumps(p["levels"])), nat
            presence[nat] = {**p, "levels": enc}
            busy = SV.shop_busy_map(nat)
            if busy:
                near[nat] = busy
            meetup[nat] = M.meetup_dongs(nat)

        con = sqlite3.connect(tmp)
        con.row_factory = sqlite3.Row
        rows = lambda sql: [dict(r) for r in con.execute(sql).fetchall()]  # noqa: E731
        age = lambda ts: None if not ts else int((built - dt.datetime.fromisoformat(ts)).total_seconds())  # noqa: E731
        posts = rows("SELECT p.*, (SELECT COUNT(*) FROM likes l WHERE l.post_id=p.id) AS likes FROM posts p ORDER BY id")
        comments = rows("SELECT * FROM comments ORDER BY id")
        reports = rows("SELECT * FROM reports ORDER BY id")
        notices = rows("SELECT * FROM notices ORDER BY id")
        questions = rows("SELECT * FROM questions ORDER BY id")
        authors = {r["author_id"] for r in posts + comments + questions}
        users = [u for u in rows("SELECT * FROM users ORDER BY id") if u["persona_key"] or u["id"] in authors]
        assert not rows("SELECT * FROM places WHERE precise=1") and not rows("SELECT * FROM shop_votes")
        con.close()
    finally:
        cm.set_default_db(None)

    today = built.date()
    day_of = lambda s: (dt.date.fromisoformat(s) - today).days if s else None  # noqa: E731
    return {
        "built": built.isoformat(sep=" "),
        "consts": {"hotDays": C.HOT_DAYS, "hotMin": C.HOT_MIN_LIKES, "reportHide": C.REPORT_HIDE_THRESHOLD,
                   "placeVerify": C.PLACE_VERIFY_UPVOTES, "rooms": list(C.ROOMS), "activeTags": C.ACTIVE_TAGS,
                   "phase2Tags": [] if C.ENABLE_PHASE2 else list(C.PHASE2_TAGS), "natNames": C.NAT_NAMES,
                   "dongName": C.DONG_NAME, "natCuisines": SV.NAT_CUISINES, "uiLangs": list(SV.UI_LANGS),
                   "reportReasons": SV.POST_REPORT_REASONS, "shopFeedback": list(cm.SHOP_FEEDBACK_REASONS),
                   "emojiWords": SV.NOTICE_EMOJI_WORDS, "topicEmoji": SV.NOTICE_TOPIC_EMOJI},
        "bootstrap": boot,
        "geo": SV.dong_geojson_light(),
        "shops": shops,
        "near": near,
        "presence": presence, "presenceDongs": codes,
        "meetup": meetup,
        "users": [{k: u[k] for k in ("id", "persona_key", "nationality", "language", "dong", "role", "is_korean",
                                     "joined_at")} for u in users],
        "posts": [{**{k: p[k] for k in ("id", "room", "tag", "title", "body", "body_ko", "author_id", "dong",
                                        "is_hidden", "likes")},
                   "extra": json.loads(p["extra"]) if p["extra"] else {}, "age": age(p["created_at"])} for p in posts],
        "comments": [{**{k: c[k] for k in ("id", "post_id", "author_id", "body", "body_ko")},
                      "age": age(c["created_at"])} for c in comments],
        "reports": [{**{k: r[k] for k in ("post_id", "user_id", "reason", "status")}, "age": age(r["created_at"])}
                    for r in reports],
        "notices": [{"id": n["id"], "kind": n["kind"], "topic": n["topic"], "titles": json.loads(n["titles"]),
                     "bodies": json.loads(n["bodies"]), "target": json.loads(n["target"]) if n["target"] else [],
                     "target_dongs": json.loads(n["target_dongs"]) if n["target_dongs"] else [],
                     "scope": n["scope"] or "all", "dong": n["dong"] or "", "day": day_of(n["start_date"]),
                     "link": n["link"] or "", "age": age(n["created_at"])} for n in notices],
        "questions": [{**{k: q[k] for k in ("id", "author_id", "language", "title", "body", "body_ko", "answer",
                                            "answered_by")},
                       "age": age(q["created_at"]), "answeredAge": age(q["answered_at"])} for q in questions],
    }


# ------------------------------------------------------------------ 시민 앱 → 파일 하나
IMPORT_RE = re.compile(r"""((?:import|export)\s[^'";]*?\sfrom\s+|import\s+)(['"])\./([\w-]+\.js)\2""")
FETCH_SHIM = """
// HTML 판: /api 요청을 이 파일 안의 가짜 서버(ANSAN_DEMO — pipeline/html/demo_api.js)로 돌린다. 앱 코드는 그대로 둔다
(function () {
  if (typeof ANSAN_DEMO === 'undefined') return;
  var D = ANSAN_DEMO;
  window.ANSAN_SINGLE_FILE = true;   // 파일 하나 판 — 서비스 워커(sw.js)가 없다. 웹 주소(GitHub Pages)로 열어도 등록하지 않게(main.js)
  var realFetch = window.fetch ? window.fetch.bind(window) : null;
  window.fetch = function (input, init) {
    init = init || {};
    var url = typeof input === 'string' ? input : input.url;
    if (url.indexOf('/api/') !== 0) return realFetch ? realFetch(input, init) : Promise.reject(new TypeError('offline'));
    var h = init.headers || {};
    var auth = String(h.Authorization || h.authorization || '').replace(/^Bearer\\s+/i, '');
    var body;
    try { body = init.body ? JSON.parse(init.body) : undefined; } catch (e) { body = null; }
    return new Promise(function (resolve) {
      setTimeout(function () {
        var r = D.handle(init.method || 'GET', url, body, auth);
        resolve(new Response(JSON.stringify(r.data), { status: r.status, headers: { 'Content-Type': 'application/json' } }));
      }, 0);
    });
  };
})();
"""


def _js_const(name: str, value) -> str:
    return f"const {name} = " + json.dumps(value, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/") + ";"


def _data_url(src: str) -> str:
    return "data:text/javascript;base64," + base64.b64encode(src.encode("utf-8")).decode("ascii")


def _png_data_url(path: Path) -> str:
    return "data:image/png;base64," + base64.b64encode(path.read_bytes()).decode("ascii")


def _inline_script(src: str) -> str:
    return "<script>" + re.sub(r"</(script)", r"<\\/\1", src, flags=re.IGNORECASE) + "</script>"


def build_app_html(api_data: dict) -> str:
    """app/index.html → 파일 하나. 바꾸는 것은 파일 연결 방식뿐이다(아래 치환이 하나라도 빗나가면 멈춘다 — 앱 구조가 바뀐 것)."""
    doc = (APP_DIR / "index.html").read_text(encoding="utf-8")

    def sub_once(pattern, repl, text):
        out, n = re.subn(pattern, repl, text)
        assert n >= 1, f"app/index.html 에서 못 찾음: {pattern}"
        return out

    # 홈 화면 설치는 파일로 열면 쓸 수 없다 — manifest 는 빼고, 탭 아이콘만 그림을 끼워 넣는다
    doc = sub_once(r'\s*<link rel="manifest"[^>]*>', "", doc)
    doc = sub_once(r'\s*<link rel="apple-touch-icon"[^>]*>', "", doc)
    doc = sub_once(r'(<link rel="icon"[^>]*href=")(icons/[^"]+)(")',
                   lambda m: m.group(1) + _png_data_url(APP_DIR / m.group(2)) + m.group(3), doc)
    doc = sub_once(r'<link rel="stylesheet" href="([^"]+)">',
                   lambda m: "<style>" + (APP_DIR / m.group(1)).read_text(encoding="utf-8") + "</style>", doc)
    doc = sub_once(r'<script src="(vendor/[^"]+)"></script>',
                   lambda m: _inline_script((APP_DIR / m.group(1)).read_text(encoding="utf-8")), doc)

    imports = {}
    for js in sorted((APP_DIR / "js").glob("*.js")):
        src = IMPORT_RE.sub(lambda m: f"{m.group(1)}{m.group(2)}app/{m.group(3)}{m.group(2)}", js.read_text(encoding="utf-8"))
        left = re.findall(r"""(?:from|import)\s*\(?\s*['"]\.\.?/""", src)
        assert not left, f"{js.name}: 상대 경로 import 를 못 바꿈 {left}"
        imports[f"app/{js.name}"] = _data_url(src)
    # 가짜 서버(자료 · 처리 · fetch 가로채기)는 보통 스크립트라 모듈(main.js)보다 먼저 돈다
    boot = "\n".join([
        _inline_script(_js_const("DATA", {"app": api_data})),
        _inline_script((SRC / "demo_api.js").read_text(encoding="utf-8")),
        _inline_script(FETCH_SHIM),
        '<script type="importmap">' + json.dumps({"imports": imports}) + "</script>",
        "<script type=\"module\">import 'app/main.js';</script>",
    ])
    doc = sub_once(r'<script type="module" src="js/main.js"></script>', lambda m: boot, doc)
    for left in ('src="js/', 'href="vendor/', 'href="css/', 'href="icons/', 'manifest.webmanifest'):
        assert left not in doc, f"파일 밖을 가리키는 연결이 남음: {left}"
    return doc


# ------------------------------------------------------------------ 제안 요약 (심사 · 담당자용 — 시민 앱에서 뺀 것)
def build_proposal(api_data: dict) -> str:
    """틀은 pipeline/html/proposal.html. 자료에서 오는 숫자 몇 개만 채운다(틀의 __이름__)."""
    shops = [s for s in api_data["shops"]["shops"] if "near" in s]      # 'near' 칸이 없는 줄은 공공시설
    fill = {
        "__SHOPS__": f"{len(shops):,}",
        "__NATS__": str(len(C.NAT_NAMES)),
        "__MONTH__": f"{C.LATEST_MONTH[:4]}년 {int(C.LATEST_MONTH[4:6])}월",
        "__BUILT__": api_data["built"][:10],
        "__APP_FILE__": OUT.name,
        "__ICON__": _png_data_url(APP_DIR / "icons" / "icon-192.png"),   # 탭 아이콘을 파일 안에 — 웹 주소로 열 때 /favicon.ico 404 가 안 나게
    }
    html = (SRC / "proposal.html").read_text(encoding="utf-8")
    for key, val in fill.items():
        assert key in html, f"proposal.html 에 {key} 가 없음"
        html = html.replace(key, val)
    left = re.findall(r"__[A-Z_]+__", html)
    assert not left, f"proposal.html 에 채우지 않은 칸: {left}"
    return html


def main():
    api_data = build_app_api()
    app_html = build_app_html(api_data)
    if "--check" in sys.argv:
        sizes = {k: len(json.dumps(v, ensure_ascii=False, separators=(",", ":"))) for k, v in api_data.items()}
        sizes["(시민 앱 파일 전체)"] = len(app_html.encode("utf-8"))
        for k, v in sorted(sizes.items(), key=lambda kv: -kv[1]):
            print(f"{k:20s} {v / 1024:8.1f} KB")
        shops = [s for s in api_data["shops"]["shops"] if "near" in s]
        kinds = {}
        for s in shops:
            kinds[s["kind"]] = kinds.get(s["kind"], 0) + 1
        print(f"가게 {len(shops)} {kinds} · 공공시설 {len(api_data['shops']['shops']) - len(shops)} · "
              f"글 {len(api_data['posts'])} · 공지 {len(api_data['notices'])} · 질문 {len(api_data['questions'])}")
        return
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(app_html, encoding="utf-8")
    OUT_PROPOSAL.write_text(build_proposal(api_data), encoding="utf-8")
    for path in (OUT, OUT_PROPOSAL):
        print(f"[v] {path} · {path.stat().st_size / 1024:.0f} KB")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
