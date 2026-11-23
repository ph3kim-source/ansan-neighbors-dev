"""안산 이웃 — 시민 앱(PWA) 서버. 화면은 app/ 의 정적 파일, 데이터는 /api (결정 13, 2026-11-20).

    python src\\server.py                 # 가상 판 · http://127.0.0.1:8600
    python src\\server.py --lan           # 같은 와이파이의 휴대폰으로 보기
    set ANSAN_DATA=real & python src\\server.py   # 실데이터 판 · 127.0.0.1:8602 (앱_실행.bat 은 data\\real 이 있으면 실데이터 판을 8600 으로 연다)

- 커뮤니티 · 공지 · Q&A 는 Streamlit 운영 콘솔(src/app.py)과 **같은 SQLite**(data/community.db)를 쓴다.
  공무원이 콘솔에서 올린 공지가 앱 소식에 바로 보이고, 주민이 앱에서 한 질문 · 신고가 콘솔에 쌓인다.
- 통신 자료는 동마다 1~4 단계만 내보낸다(metrics.presence_levels). 비중 · 인원은 API 로 나가지 않는다.
- 가게는 공공 상가정보(pipeline/stage_shops.py → data/public/shops_ansan.csv)다.
- 실데이터 판은 이 PC(127.0.0.1)에서만 연다. 공유판 · 드라이브 앱에는 실데이터가 들어가지 않는다(정적 파일에 데이터가 없다).
"""
import argparse
import csv
import datetime as dt
import os
import sys
from functools import lru_cache
from pathlib import Path

from starlette.applications import Starlette
from starlette.concurrency import run_in_threadpool
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles

sys.path.insert(0, str(Path(__file__).resolve().parent))
import community as cm  # noqa: E402
import config as C  # noqa: E402
import metrics as mt  # noqa: E402
from geo import dong_at, dong_centroids, dong_geojson_light  # noqa: E402

APP_DIR = C.BASE_DIR / "app"
SHOPS_CSV = C.DATA_DIR / "public" / "shops_ansan.csv"
FACILITIES_CSV = C.DATA_DIR / "public" / "facilities.csv"
UI_LANGS = ("ko", "en", "zh", "ru", "vi")
# 국적 → 그 나라 사람이 찾을 음식 · 상품 종류 (stage_shops.CUISINE_WORDS 코드). 'world'(세계 식품)는 모두에게
NAT_CUISINES = {
    "중국": ["cn"], "우즈베키스탄": ["ca"], "러시아": ["ca"], "카자흐스탄": ["ca"], "베트남": ["vn"],
    "인도네시아": ["id", "halal"], "네팔": ["np"], "필리핀": ["ph"], "미얀마": ["mm"], "몽골": ["mn"],
    "캄보디아": ["kh"], "방글라데시": ["halal", "np"], "태국": ["th"], "파키스탄": ["halal", "np"],
    "스리랑카": ["lk", "np"], "인도": ["np"], "기타": ["ca"],
}
POST_REPORT_REASONS = ["사기·브로커", "혐오 표현", "광고·스팸", "개인정보", "기타"]
PORT_SYNTHETIC, PORT_REAL = 8600, 8602


# ------------------------------------------------------------------ 공통
def ok(data, status: int = 200) -> JSONResponse:
    return JSONResponse(data, status_code=status, headers={"Cache-Control": "no-store"})


async def body_of(request: Request) -> dict:
    try:
        data = await request.json()
    except Exception:
        raise HTTPException(400, "bad_json")
    if not isinstance(data, dict):
        raise HTTPException(400, "bad_json")
    return data


def current_user(request: Request, required: bool = True) -> dict:
    auth = request.headers.get("authorization", "")
    token = auth[7:] if auth.lower().startswith("bearer ") else request.headers.get("x-session", "")
    user = cm.user_by_token(token.strip())
    if required and not user:
        raise HTTPException(401, "login_required")
    return user


def ui_lang(user: dict) -> str:
    lang = (user or {}).get("language") or "ko"
    return lang if lang in UI_LANGS else "en"     # 기타 언어방(etc) 주민은 영어 화면


def public_user(u: dict) -> dict:
    return {"id": u["id"], "nationality": u["nationality"], "language": u["language"], "uiLang": ui_lang(u),
            "dong": u["dong"], "dongName": C.DONG_NAME.get(u["dong"], ""), "isKorean": bool(u["is_korean"]),
            "role": u["role"], "joined": (u["joined_at"] or "")[:10], "persona": u.get("persona_key"),
            "cuisines": NAT_CUISINES.get(u["nationality"] or "", [])}


def pick(d: dict, lang: str) -> str:
    return d.get(lang) or d.get("en" if lang != "ko" else "ko") or d.get("ko", "")


def int_or_400(value, name="id") -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        raise HTTPException(400, f"bad_{name}")


# ------------------------------------------------------------------ 기본 정보 · 로그인
async def bootstrap(request: Request):
    cent = dong_centroids()
    personas = [{"key": k, "label": p["label"], "nationality": p["nationality"], "language": p["language"],
                 "dong": p["dong"], "isKorean": bool(p["is_korean"]), "role": p["role"]}
                for k, p in C.PERSONAS.items()]
    return ok({
        "mode": "real" if C.IS_REAL else "synthetic", "dataMonth": f"{C.LATEST_MONTH[:4]}-{C.LATEST_MONTH[4:6]}",
        "langs": list(UI_LANGS),
        "nations": [{"name": n, "flag": f, "room": r} for n, _, f, r in C.NATIONS],
        "dongs": [{"code": c, "name": nm, "gu": "상록구" if c.startswith("41271") else "단원구",
                   "lon": round(cent[c][0], 6), "lat": round(cent[c][1], 6)} for c, _, nm in C.DONGS],
        "rooms": list(C.ROOMS), "tags": C.ACTIVE_TAGS, "personas": personas,
        "natCuisines": NAT_CUISINES, "shopDate": shops_meta()["date"],
        "placeVerify": C.PLACE_VERIFY_UPVOTES, "reportHide": C.REPORT_HIDE_THRESHOLD, "hotMin": C.HOT_MIN_LIKES,
        "reportReasons": POST_REPORT_REASONS, "shopFeedback": list(cm.SHOP_FEEDBACK_REASONS),
    })


async def login_persona(request: Request):
    data = await body_of(request)
    key = data.get("persona")
    if key not in C.PERSONAS:
        raise HTTPException(400, "bad_persona")
    user = cm.user_by_persona(key)
    return ok({"token": cm.create_session(user["id"]), "user": public_user(user)})


async def signup(request: Request):
    data = await body_of(request)
    try:
        user = cm.create_user(data.get("nationality"), data.get("language", ""), data.get("dong", ""),
                              bool(data.get("isKorean")))
    except ValueError as err:
        raise HTTPException(400, str(err))
    return ok({"token": cm.create_session(user["id"]), "user": public_user(user)})


async def me(request: Request):
    user = current_user(request)
    if request.method == "PATCH":
        data = await body_of(request)
        try:
            user = cm.update_user(user["id"], language=data.get("language"), dong=data.get("dong"))
        except ValueError as err:
            raise HTTPException(400, str(err))
    return ok(public_user(user))


# ------------------------------------------------------------------ 지도
@lru_cache(maxsize=1)
def load_shops() -> list:
    if not SHOPS_CSV.exists():
        return []
    with open(SHOPS_CSV, encoding="utf-8-sig", newline="") as fp:
        rows = list(csv.DictReader(fp))
    for r in rows:
        r["lon"], r["lat"] = float(r["lon"]), float(r["lat"])
    return rows


def shops_meta() -> dict:
    rows = load_shops()
    return {"date": rows[0]["std_ym"] if rows else "", "n": len(rows)}


@lru_cache(maxsize=1)
def load_facilities() -> list:
    if not FACILITIES_CSV.exists():
        return []
    with open(FACILITIES_CSV, encoding="utf-8-sig", newline="") as fp:
        rows = list(csv.DictReader(fp))
    for r in rows:
        r["lon"], r["lat"] = float(r["lon"]), float(r["lat"])
    return rows


async def geo_dongs(request: Request):
    return JSONResponse(dong_geojson_light(), headers={"Cache-Control": "public, max-age=86400"})


@lru_cache(maxsize=32)
def shop_busy_map(nat: str) -> dict:
    """국적 하나 → {가게: 'cell' | 'dong'} — 고향 사람이 많이 다니는 골목 · 동네에 있는 가게(표시만)."""
    return mt.busy_shops(nat, tuple((r["shop_id"], r["lon"], r["lat"], r["dong"]) for r in load_shops()))


async def shops(request: Request):
    user = current_user(request, required=False)
    counts, mine = cm.shop_vote_counts(user["id"] if user else None)
    # 주민 본인 국적만(공무원 · 내국인 이웃에게는 표시 없음 — '고향 사람 많은 곳'과 같은 범위, D8)
    nat = user["nationality"] if user and user["role"] != "official" and not user["is_korean"] else None
    busy = await run_in_threadpool(shop_busy_map, nat) if nat in C.NAT_NAMES else {}
    out = []
    for r in load_shops():
        out.append({"id": r["shop_id"], "name": r["name"], "kind": r["kind"], "sub": r["sub"], "cuisine": r["cuisine"],
                    "basis": r["basis"], "dong": r["dong"], "addr": r["road_addr"], "floor": r["floor"],
                    "lon": r["lon"], "lat": r["lat"], "votes": counts.get(r["shop_id"], 0),
                    "voted": r["shop_id"] in mine, "checked": r.get("checked", ""), "checkSrc": r.get("check_src", "licence"),
                    "near": busy.get(r["shop_id"], "")})
    facilities = [{"id": f"f{i}", "name": f["name"], "kind": "official", "sub": f.get("sub", ""), "cuisine": "",
                   "basis": f["source"], "dong": dong_at(f["lon"], f["lat"]) or "", "addr": f.get("note", ""),
                   "floor": "", "lon": f["lon"], "lat": f["lat"], "votes": 0, "voted": False}
                  for i, f in enumerate(load_facilities())]
    return ok({"date": shops_meta()["date"], "shops": out + facilities})


def shop_exists(shop_id: str) -> bool:
    return any(r["shop_id"] == shop_id for r in load_shops())


async def shop_vote(request: Request):
    user = current_user(request)
    sid = request.path_params["sid"]
    if not shop_exists(sid):
        raise HTTPException(404, "no_shop")
    voted = cm.toggle_shop_vote(sid, user["id"])
    counts, _ = cm.shop_vote_counts()
    return ok({"voted": voted, "votes": counts.get(sid, 0)})


async def shop_feedback(request: Request):
    user = current_user(request)
    sid = request.path_params["sid"]
    if not shop_exists(sid):
        raise HTTPException(404, "no_shop")
    data = await body_of(request)
    try:
        cm.add_shop_feedback(sid, user["id"], data.get("reason", ""))
    except ValueError as err:
        raise HTTPException(400, str(err))
    return ok({"ok": True})


async def places(request: Request):
    user = current_user(request, required=request.method == "POST")
    if request.method == "POST":
        data = await body_of(request)
        try:
            lon, lat = float(data.get("lon")), float(data.get("lat"))
        except (TypeError, ValueError):
            raise HTTPException(400, "bad_location")
        dong = dong_at(lon, lat)
        if not dong:
            raise HTTPException(400, "outside_ansan")
        kind = data.get("kind") if data.get("kind") in ("food", "grocery", "service", "other") else "other"
        try:
            pid = cm.add_place_at(user, data.get("name", ""), kind, data.get("cuisine", ""), dong, lon, lat)
        except ValueError as err:
            raise HTTPException(400, str(err))
        return ok({"id": pid, "dong": dong}, 201)
    return ok({"places": cm.list_app_places(user["id"] if user else None)})


async def place_vote(request: Request):
    user = current_user(request)
    pid = int_or_400(request.path_params["pid"])
    cm.vote_place(pid, user["id"])
    return ok({"votes": cm.place_votes(pid)})


async def presence(request: Request):
    """우리 이웃이 많은 곳 — 내 국적만(공무원은 아무 국적). 내국인 이웃에게는 국적별 밀집 화면을 주지 않는다(D8)."""
    user = current_user(request)
    if user["role"] == "official":
        nat = request.query_params.get("nat") or "중국"
    elif user["is_korean"]:
        raise HTTPException(403, "not_for_korean_neighbors")
    else:
        nat = user["nationality"]
    if nat not in C.NAT_NAMES:
        raise HTTPException(400, "bad_nat")
    levels = await run_in_threadpool(mt.presence_levels, nat)
    empty = all(v is None for day in levels.values() for hour in day.values() for v in hour.values())
    holidays = await run_in_threadpool(mt.presence_holidays) if "연휴" in levels else []
    cells = await run_in_threadpool(mt.presence_cells, nat)      # 골목 칸(육각) — 실데이터 판 · 50m 표에 있는 국적만, 단계만
    return ok({"nat": nat, "levels": levels, "empty": empty, "month": C.LATEST_MONTH,
               "holidays": [h["date"] for h in holidays], "cells": cells})


# ------------------------------------------------------------------ 커뮤니티
def post_view(p: dict, user: dict, full: bool = False) -> dict:
    view = {"id": p["id"], "room": p["room"], "tag": p["tag"], "title": p["title"],
            "body": p["body"] if full else (p["body"] or "")[:140], "bodyKo": p.get("body_ko") or "",
            "dong": p["dong"], "dongName": C.DONG_NAME.get(p["dong"], ""), "created": p["created_at"],
            "nat": p["nationality"], "lang": p["language"], "isKorean": bool(p["is_korean"]),
            "likes": p["likes"], "comments": p["n_comments"], "mine": bool(user and p["author_id"] == user["id"]),
            "extra": p.get("extra") or {}}
    return view


async def posts(request: Request):
    user = current_user(request)
    if request.method == "POST":
        data = await body_of(request)
        room, tag = data.get("room", ""), data.get("tag", "")
        title, body = (data.get("title") or "").strip(), (data.get("body") or "").strip()
        dong = data.get("dong") or user["dong"]
        if room not in C.ROOMS or tag not in C.ACTIVE_TAGS or dong not in C.DONG_NAME:
            raise HTTPException(400, "bad_post")
        if not title or not body:
            raise HTTPException(400, "need_title_body")
        extra = {}
        if tag == "모임":
            extra = {"when": str(data.get("when") or "")[:40]}
        try:
            pid = cm.add_post(user, room, tag, title[:80], body[:2000], dong, extra)
        except PermissionError:
            raise HTTPException(403, "korean_exchange_only")
        except ValueError as err:
            raise HTTPException(400, str(err))
        return ok({"id": pid}, 201)
    q = request.query_params
    room = q.get("room") or None
    tags = [q["tag"]] if q.get("tag") else None
    dongs = [q["dong"]] if q.get("dong") else None
    nats = [q["nat"]] if q.get("nat") in C.NAT_NAMES else None          # 언어방 안 '같은 나라 글만'
    rows = cm.list_posts(room=room, tags=tags, dongs=dongs, nats=nats, limit=min(int(q.get("limit", 40) or 40), 100))
    return ok({"posts": [post_view(p, user) for p in rows]})


async def hot(request: Request):
    user = current_user(request)
    return ok({"posts": [post_view(p, user) for p in cm.hot_posts(limit=5)]})


async def post_detail(request: Request):
    user = current_user(request)
    p = cm.get_post(int_or_400(request.path_params["pid"]))
    if not p:
        raise HTTPException(404, "no_post")
    view = post_view(p, user, full=True)
    view["liked"] = cm.has_liked(p["id"], user["id"])
    view["canWrite"] = cm.can_write(user, p["room"])
    view["thread"] = [{"id": c["id"], "alias": c["alias_n"], "body": c["body"], "bodyKo": c["body_ko"] or "",
                       "created": c["created_at"], "mine": c["author_id"] == user["id"]}
                      for c in cm.comment_thread(p["id"], p["author_id"])]
    return ok(view)


async def post_like(request: Request):
    user = current_user(request)
    pid = int_or_400(request.path_params["pid"])
    if not cm.get_post(pid):
        raise HTTPException(404, "no_post")
    cm.toggle_like(pid, user["id"])
    p = cm.get_post(pid)
    return ok({"liked": cm.has_liked(pid, user["id"]), "likes": p["likes"]})


async def post_comment(request: Request):
    user = current_user(request)
    pid = int_or_400(request.path_params["pid"])
    if not cm.get_post(pid):
        raise HTTPException(404, "no_post")
    data = await body_of(request)
    text = (data.get("body") or "").strip()
    if not text:
        raise HTTPException(400, "empty")
    try:
        cid = cm.add_comment(user, pid, text[:1000])
    except PermissionError:
        raise HTTPException(403, "korean_exchange_only")
    return ok({"id": cid}, 201)


async def post_report(request: Request):
    user = current_user(request)
    pid = int_or_400(request.path_params["pid"])
    if not cm.get_post(pid, include_hidden=True):
        raise HTTPException(404, "no_post")
    data = await body_of(request)
    reason = data.get("reason") if data.get("reason") in POST_REPORT_REASONS else "기타"
    return ok({"hidden": cm.report_post(pid, user["id"], reason)})


async def meetup_hint(request: Request):
    user = current_user(request)
    if user["is_korean"] or not user["nationality"]:
        return ok({"dongs": []})
    return ok({"dongs": await run_in_threadpool(mt.meetup_dongs, user["nationality"])})


# ------------------------------------------------------------------ 소식 · Q&A
# 소식 카드 그림 — 한국어 제목 낱말이 먼저, 없으면 주제로 고른다(시민 화면이 딱딱해 보인다는 의견, 2026-11-20).
NOTICE_EMOJI_WORDS = (("김장", "🥬"), ("취업", "💼"), ("일자리", "💼"), ("임금", "💼"), ("송년", "🎉"), ("새해", "🎆"),
                      ("설날", "🎆"), ("추석", "🌕"), ("바자", "🛍️"), ("장터", "🛍️"), ("축제", "🎉"), ("검진", "🩺"),
                      ("한국어", "📚"), ("입학", "🎒"), ("체류", "🛂"), ("정착", "🏠"), ("규칙", "📌"))
NOTICE_TOPIC_EMOJI = {"의료": "🩺", "노동": "💼", "교육": "📚", "행정": "📋", "비자": "🛂", "규칙": "📌", "행사": "🎉"}


def notice_emoji(e: dict) -> str:
    ko = (e.get("titles") or {}).get("ko", "")
    for word, mark in NOTICE_EMOJI_WORDS:
        if word in ko:
            return mark
    return NOTICE_TOPIC_EMOJI.get(e.get("topic") or "", "📢")


def notice_view(e: dict, user: dict, lang: str) -> dict:
    nat = user.get("nationality")
    return {"id": e["id"], "kind": e["kind"], "topic": e["topic"], "emoji": notice_emoji(e), "title": pick(e["titles"], lang),
            "body": pick(e["bodies"], lang), "dong": e["dong"] or "", "dongName": C.DONG_NAME.get(e["dong"] or "", ""),
            "date": e["start_date"], "link": e["link"] or "", "targeted": e["scope"] == "target",
            "forMe": e["scope"] == "target" or bool(nat and nat in (e["target"] or []))}


async def news(request: Request):
    user = current_user(request)
    lang = ui_lang(user)
    today = dt.date.today().isoformat()
    visible = [e for e in cm.list_notices() if cm.notice_visible(e, user)]
    events = [notice_view(e, user, lang) for e in visible if e["kind"] == "event"]
    upcoming = sorted([e for e in events if e["date"] >= today], key=lambda e: (not e["forMe"], e["date"]))
    past = sorted([e for e in events if e["date"] < today], key=lambda e: e["date"], reverse=True)
    infos = [notice_view(e, user, lang) for e in visible if e["kind"] in ("policy", "notice")]
    infos.sort(key=lambda e: (not e["forMe"], e["kind"] != "notice", e["date"]), reverse=False)
    return ok({"events": upcoming, "pastEvents": past[:6], "infos": infos})


async def questions(request: Request):
    user = current_user(request)
    if request.method == "POST":
        data = await body_of(request)
        title, body = (data.get("title") or "").strip(), (data.get("body") or "").strip()
        if not title:
            raise HTTPException(400, "need_title")
        return ok({"id": cm.add_question(user, title[:120], body[:2000])}, 201)
    rows = cm.list_questions()
    return ok({"questions": [{"id": q["id"], "title": q["title"], "body": q["body"], "bodyKo": q["body_ko"] or "",
                              "lang": q["language"], "created": q["created_at"], "answer": q["answer"] or "",
                              "answered": q["answered_at"] or "", "mine": q["author_id"] == user["id"]}
                             for q in rows]})


# ------------------------------------------------------------------ 앱
async def http_error(request: Request, exc: HTTPException):
    return ok({"error": exc.detail}, exc.status_code)


def build_app(db_path: str = None) -> Starlette:
    if db_path:
        cm.set_default_db(db_path)
    cm.init_db()
    routes = [
        Route("/api/bootstrap", bootstrap),
        Route("/api/session", login_persona, methods=["POST"]),
        Route("/api/signup", signup, methods=["POST"]),
        Route("/api/me", me, methods=["GET", "PATCH"]),
        Route("/api/geo/dongs", geo_dongs),
        Route("/api/shops", shops),
        Route("/api/shops/{sid}/vote", shop_vote, methods=["POST"]),
        Route("/api/shops/{sid}/feedback", shop_feedback, methods=["POST"]),
        Route("/api/places", places, methods=["GET", "POST"]),
        Route("/api/places/{pid}/vote", place_vote, methods=["POST"]),
        Route("/api/presence", presence),
        Route("/api/posts", posts, methods=["GET", "POST"]),
        Route("/api/posts/hot", hot),
        Route("/api/posts/{pid}", post_detail),
        Route("/api/posts/{pid}/like", post_like, methods=["POST"]),
        Route("/api/posts/{pid}/comments", post_comment, methods=["POST"]),
        Route("/api/posts/{pid}/report", post_report, methods=["POST"]),
        Route("/api/meetup-hint", meetup_hint),
        Route("/api/news", news),
        Route("/api/questions", questions, methods=["GET", "POST"]),
        Mount("/", app=StaticFiles(directory=str(APP_DIR), html=True), name="app"),
    ]
    return Starlette(routes=routes, exception_handlers={HTTPException: http_error})


def bind_host(lan: bool) -> str:
    """같은 와이파이로 열면 0.0.0.0. 실데이터 판도 열 수 있다 — 2026-11-20 인벤토리 데이터 사용 승인(사용자 전달: "다 써도 된다,
    적극 활용하라"). 시민 화면에는 동네 단계(1~4)만 나가고 적은 칸은 가린다. 공개 저장소 · 외부 서비스에 올리는 것과는 다른 일이다."""
    if lan and C.IS_REAL:
        print("[!] 실데이터 판을 같은 와이파이에 엽니다 — 집 · 사무실 와이파이에서만 쓰고, 공용 와이파이에서는 열지 마십시오")
    return "0.0.0.0" if lan else "127.0.0.1"


def main():
    import uvicorn
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=PORT_REAL if C.IS_REAL else PORT_SYNTHETIC)
    ap.add_argument("--lan", action="store_true", help="같은 와이파이의 휴대폰으로 보기")
    args = ap.parse_args()
    host = bind_host(args.lan)
    if not SHOPS_CSV.exists():
        print("[!] 가게 목록이 없다 — python pipeline\\stage_shops.py 를 먼저 실행한다", file=sys.stderr)
    print(f"[i] 안산 이웃 시민 앱 · {'실데이터 판(고향 사람 지도 = 실제 통신 자료 ' + C.LATEST_MONTH + ')' if C.IS_REAL else '가상 판'} · http://127.0.0.1:{args.port}")
    if args.lan:
        print("    휴대폰: 같은 와이파이에서 http://<이 PC의 IP>:%d (ipconfig 의 IPv4 주소)" % args.port)
    uvicorn.run(build_app(os.environ.get("ANSAN_DB")), host=host, port=args.port, log_level="warning")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
