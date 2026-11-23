// HTML 판 가짜 서버 — src/server.py 의 /api 를 이 탭 안에서 흉내 낸다. 같은 파일에 담긴 시민 앱(app/)이 fetch 로 부르면
// 작은 스크립트(build_html.FETCH_SHIM)가 여기 handle() 로 돌린다. 자료는 build_html.build_app_api 가
// 가상 시드 DB 와 server.py 처리 함수로 뽑은 DATA.app 이다. 글 · 댓글 · 질문 · 추천은 이 탭에만 남는다(새로 고치면 처음).
// 규칙은 server.py · community.py 와 같게 둔다 — 그쪽을 바꾸면 여기도 바꾼다.
const ANSAN_DEMO = (() => {
  const A = DATA.app, K = A.consts;
  const T0 = Date.now();
  const pad = (n) => String(n).padStart(2, '0');
  const fmt = (d) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
  // 시드 시각은 '만든 때로부터 몇 초 전'으로 담았다 → 여는 때 기준으로 다시 맞춘다(며칠 뒤에 열어도 '2시간 전'은 2시간 전)
  const stamp = (age) => (age == null ? null : fmt(new Date(T0 - age * 1000)));
  const nowTs = () => fmt(new Date());
  const dayStr = (off) => { const d = new Date(); d.setHours(12, 0, 0, 0); d.setDate(d.getDate() + off); return fmt(d).slice(0, 10); };
  const clip = (s, n) => Array.from(String(s || '')).slice(0, n).join('');
  const cmp = (a, b) => { for (let i = 0; i < a.length; i++) { if (a[i] < b[i]) return -1; if (a[i] > b[i]) return 1; } return 0; };

  // ---------------------------------------------------------------- 상태
  const users = new Map(A.users.map((u) => [u.id, { ...u }]));
  let nextUser = 1000000, nextId = 1000000;
  const db = {
    posts: A.posts.map((p) => ({ ...p, created_at: stamp(p.age), likedBy: new Set() })),   // likes = 시드 추천(가상 회원) + likedBy
    comments: A.comments.map((c) => ({ ...c, created_at: stamp(c.age) })),
    reports: A.reports.map((r) => ({ ...r, created_at: stamp(r.age) })),
    notices: A.notices.map((n) => ({ ...n, start_date: n.day == null ? '' : dayStr(n.day), created_at: stamp(n.age) })),
    questions: A.questions.map((q) => ({ ...q, created_at: stamp(q.age), answered_at: stamp(q.answeredAge) })),
    places: [], placeVotes: new Map(), shopVotes: new Map(), shopFeedback: [],
  };
  let current = null;        // 토큰이 없을 때(저장소 막힘) 쓸 마지막 로그인 사용자

  const byPersona = (key) => [...users.values()].find((u) => u.persona_key === key);
  const tokenFor = (u) => 'demo-' + u.id;
  const userByToken = (tok) => (/^demo-\d+$/.test(tok || '') ? users.get(+tok.slice(5)) || null : null);

  // ---------------------------------------------------------------- server.py 도우미
  const uiLang = (u) => { const l = (u && u.language) || 'ko'; return K.uiLangs.includes(l) ? l : 'en'; };
  const publicUser = (u) => ({
    id: u.id, nationality: u.nationality, language: u.language, uiLang: uiLang(u), dong: u.dong,
    dongName: K.dongName[u.dong] || '', isKorean: !!u.is_korean, role: u.role, joined: (u.joined_at || '').slice(0, 10),
    persona: u.persona_key || null, cuisines: K.natCuisines[u.nationality || ''] || [],
  });
  const pick = (d, lang) => d[lang] || d[lang !== 'ko' ? 'en' : 'ko'] || d.ko || '';
  const canWrite = (u, room) => room === 'exchange' || !u.is_korean;
  const author = (id) => users.get(id) || { nationality: null, language: 'ko', is_korean: 0 };
  const likes = (p) => p.likes + p.likedBy.size;
  const nComments = (pid) => db.comments.filter((c) => c.post_id === pid).length;
  const openReports = (pid) => db.reports.filter((r) => r.post_id === pid && r.status === 'open');

  const listPosts = (o = {}) => {
    const since = o.sinceDays ? fmt(new Date(Date.now() - o.sinceDays * 86400000)) : null;
    return db.posts.filter((p) => (!o.room || p.room === o.room) && (!o.tags || o.tags.includes(p.tag))
      && (!o.dongs || o.dongs.includes(p.dong)) && (!o.nats || o.nats.includes(author(p.author_id).nationality))
      && (o.includeHidden || !p.is_hidden) && !K.phase2Tags.includes(p.tag) && (!since || p.created_at >= since))
      .sort((a, b) => cmp([b.created_at, b.id], [a.created_at, a.id])).slice(0, o.limit ?? 60);
  };
  const hotPosts = (limit = 5) => listPosts({ sinceDays: K.hotDays, limit: 200 }).filter((p) => likes(p) >= K.hotMin)
    .sort((a, b) => cmp([-likes(a), a.created_at], [-likes(b), b.created_at])).slice(0, limit);
  const getPost = (pid, includeHidden = false) => {
    const p = db.posts.find((x) => x.id === pid);
    if (!p || (p.is_hidden && !includeHidden) || K.phase2Tags.includes(p.tag)) return null;
    return p;
  };
  const postView = (p, u, full = false) => {
    const a = author(p.author_id);
    return { id: p.id, room: p.room, tag: p.tag, title: p.title, body: full ? p.body : clip(p.body, 140), bodyKo: p.body_ko || '',
      dong: p.dong, dongName: K.dongName[p.dong] || '', created: p.created_at, nat: a.nationality, lang: a.language,
      isKorean: !!a.is_korean, likes: likes(p), comments: nComments(p.id), mine: !!(u && p.author_id === u.id), extra: p.extra || {} };
  };
  const thread = (p, u) => {
    const anon = new Map();
    return db.comments.filter((c) => c.post_id === p.id).sort((a, b) => cmp([a.created_at, a.id], [b.created_at, b.id])).map((c) => {
      let alias = 0;
      if (c.author_id !== p.author_id) { if (!anon.has(c.author_id)) anon.set(c.author_id, anon.size + 1); alias = anon.get(c.author_id); }
      return { id: c.id, alias, body: c.body, bodyKo: c.body_ko || '', created: c.created_at, mine: c.author_id === u.id };
    });
  };

  const noticeVisible = (n, u) => {
    if (u.role === 'official' || (n.scope || 'all') !== 'target') return true;
    if (u.is_korean) return false;
    const nats = n.target || [], dongs = n.target_dongs || [];
    return (!nats.length || nats.includes(u.nationality)) && (!dongs.length || dongs.includes(u.dong));
  };
  const noticeEmoji = (e) => {
    const ko = (e.titles || {}).ko || '';
    for (const [w, m] of K.emojiWords) if (ko.includes(w)) return m;
    return K.topicEmoji[e.topic || ''] || '📢';
  };
  const noticeView = (e, u, lang) => ({
    id: e.id, kind: e.kind, topic: e.topic, emoji: noticeEmoji(e), title: pick(e.titles, lang), body: pick(e.bodies, lang),
    dong: e.dong || '', dongName: K.dongName[e.dong || ''] || '', date: e.start_date, link: e.link || '',
    targeted: e.scope === 'target', forMe: e.scope === 'target' || !!(u.nationality && (e.target || []).includes(u.nationality)),
  });
  const listNotices = () => [...db.notices].sort((a, b) => cmp([a.start_date, a.id], [b.start_date, b.id]));

  // 점이 속한 동 — 지도 경계(GeoJSON) 안팎 판정 (server.dong_at 와 같은 경계)
  const inRing = (x, y, ring) => {
    let inside = false;
    for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
      const [xi, yi] = ring[i], [xj, yj] = ring[j];
      if ((yi > y) !== (yj > y) && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) inside = !inside;
    }
    return inside;
  };
  const inPoly = (x, y, poly) => inRing(x, y, poly[0]) && !poly.slice(1).some((h) => inRing(x, y, h));
  const dongAt = (lon, lat) => {
    for (const f of A.geo.features) {
      const g = f.geometry, polys = g.type === 'Polygon' ? [g.coordinates] : g.coordinates;
      if (polys.some((p) => inPoly(lon, lat, p))) return f.properties.code;
    }
    return null;
  };

  const decodeLevels = (enc) => {
    const out = {};
    for (const [day, rows] of Object.entries(enc)) {
      out[day] = {};
      rows.forEach((row, h) => { out[day][String(h)] = Object.fromEntries(A.presenceDongs.map((c, i) => [c, row[i] === '.' ? null : +row[i]])); });
    }
    return out;
  };

  // ---------------------------------------------------------------- 처리
  class Fail extends Error { constructor(status, code) { super(code); this.status = status; this.code = code; } }
  const need = (u) => { if (!u) throw new Fail(401, 'login_required'); return u; };
  const obj = (b) => { if (!b || typeof b !== 'object' || Array.isArray(b)) throw new Fail(400, 'bad_json'); return b; };
  const intId = (s) => { if (!/^-?\d+$/.test(s)) throw new Fail(400, 'bad_id'); return +s; };
  const shopIds = new Set(A.shops.shops.filter((s) => 'near' in s).map((s) => s.id));

  function newUser(nationality, language, dong, isKorean) {
    if (!(dong in K.dongName)) throw new Fail(400, '거주 동을 골라 주세요');
    if (!K.rooms.includes(language) || language === 'exchange') throw new Fail(400, '언어를 골라 주세요');
    if (isKorean) nationality = null;
    else if (!K.natNames.includes(nationality)) throw new Fail(400, '국적을 골라 주세요');
    const u = { id: nextUser++, persona_key: null, nationality, language, dong, role: 'resident', is_korean: isKorean ? 1 : 0, joined_at: nowTs() };
    users.set(u.id, u);
    return u;
  }

  const ROUTES = [
    ['GET', /^\/api\/bootstrap$/, () => [200, A.bootstrap]],
    ['POST', /^\/api\/session$/, (c) => {
      const u = byPersona(obj(c.body).persona);
      if (!u) throw new Fail(400, 'bad_persona');
      current = u;
      return [200, { token: tokenFor(u), user: publicUser(u) }];
    }],
    ['POST', /^\/api\/signup$/, (c) => {
      const b = obj(c.body), u = newUser(b.nationality, b.language || '', b.dong || '', !!b.isKorean);
      current = u;
      return [200, { token: tokenFor(u), user: publicUser(u) }];
    }],
    ['GET', /^\/api\/me$/, (c) => [200, publicUser(need(c.user))]],
    ['PATCH', /^\/api\/me$/, (c) => {
      const u = need(c.user), b = obj(c.body);
      if (b.language != null) { if (!K.rooms.includes(b.language) || b.language === 'exchange') throw new Fail(400, '언어를 골라 주세요'); u.language = b.language; }
      if (b.dong != null) { if (!(b.dong in K.dongName)) throw new Fail(400, '거주 동을 골라 주세요'); u.dong = b.dong; }
      return [200, publicUser(u)];
    }],
    ['GET', /^\/api\/geo\/dongs$/, () => [200, A.geo]],
    ['GET', /^\/api\/shops$/, (c) => {
      const u = c.user;
      const nat = u && u.role !== 'official' && !u.is_korean ? u.nationality : null;
      const busy = (nat && K.natNames.includes(nat) && A.near[nat]) || {};
      const shops = A.shops.shops.map((s) => {
        if (!('near' in s)) return { ...s };                        // 공공시설 줄은 그대로
        const v = db.shopVotes.get(s.id) || new Set();
        return { ...s, votes: v.size, voted: !!(u && v.has(u.id)), near: busy[s.id] || '' };
      });
      return [200, { date: A.shops.date, shops }];
    }],
    ['POST', /^\/api\/shops\/([^/]+)\/vote$/, (c, m) => {
      const u = need(c.user), sid = decodeURIComponent(m[1]);
      if (!shopIds.has(sid)) throw new Fail(404, 'no_shop');
      const v = db.shopVotes.get(sid) || new Set();
      const voted = !v.has(u.id);
      voted ? v.add(u.id) : v.delete(u.id);
      db.shopVotes.set(sid, v);
      return [200, { voted, votes: v.size }];
    }],
    ['POST', /^\/api\/shops\/([^/]+)\/feedback$/, (c, m) => {
      const u = need(c.user), sid = decodeURIComponent(m[1]);
      if (!shopIds.has(sid)) throw new Fail(404, 'no_shop');
      const reason = obj(c.body).reason || '';
      if (!K.shopFeedback.includes(reason)) throw new Fail(400, '이유를 골라 주세요');
      if (!db.shopFeedback.some((f) => f.shop_id === sid && f.user_id === u.id && f.reason === reason)) {
        db.shopFeedback.push({ shop_id: sid, user_id: u.id, reason, created_at: nowTs(), status: 'open' });
      }
      return [200, { ok: true }];
    }],
    ['GET', /^\/api\/places$/, (c) => {
      const uid = c.user ? c.user.id : null;
      const places = [...db.places].sort((a, b) => cmp([b.created_at, b.id], [a.created_at, a.id])).map((p) => {
        const v = db.placeVotes.get(p.id) || new Set();
        return { id: p.id, name: p.name, kind: p.kind, cuisine: p.cuisine, dong: p.dong, lon: p.lon, lat: p.lat,
          created_at: p.created_at, votes: v.size, verified: v.size >= K.placeVerify, voted: uid != null && v.has(uid), mine: uid != null && p.created_by === uid };
      });
      return [200, { places }];
    }],
    ['POST', /^\/api\/places$/, (c) => {
      const u = need(c.user), b = obj(c.body);
      const lon = parseFloat(b.lon), lat = parseFloat(b.lat);
      if (!Number.isFinite(lon) || !Number.isFinite(lat)) throw new Fail(400, 'bad_location');
      const dong = dongAt(lon, lat);
      if (!dong) throw new Fail(400, 'outside_ansan');
      const kind = ['food', 'grocery', 'service', 'other'].includes(b.kind) ? b.kind : 'other';
      if (!String(b.name || '').trim()) throw new Fail(400, '가게 이름을 적어 주세요');
      const p = { id: nextId++, name: clip(String(b.name).trim(), 60), kind, cuisine: b.cuisine || '', dong,
        lon: Math.round(lon * 1e6) / 1e6, lat: Math.round(lat * 1e6) / 1e6, created_at: nowTs(), created_by: u.id };
      db.places.push(p);
      return [201, { id: p.id, dong }];
    }],
    ['POST', /^\/api\/places\/([^/]+)\/vote$/, (c, m) => {
      const u = need(c.user), pid = intId(m[1]);
      const v = db.placeVotes.get(pid) || new Set();
      v.add(u.id);
      db.placeVotes.set(pid, v);
      return [200, { votes: v.size }];
    }],
    ['GET', /^\/api\/presence$/, (c) => {
      const u = need(c.user);
      let nat;
      if (u.role === 'official') nat = c.q.get('nat') || '중국';
      else if (u.is_korean) throw new Fail(403, 'not_for_korean_neighbors');
      else nat = u.nationality;
      if (!K.natNames.includes(nat)) throw new Fail(400, 'bad_nat');
      const p = A.presence[nat];
      return [200, { ...p, levels: decodeLevels(p.levels) }];
    }],
    ['GET', /^\/api\/posts$/, (c) => {
      const u = need(c.user), q = c.q;
      const nat = q.get('nat');
      const rows = listPosts({ room: q.get('room') || null, tags: q.get('tag') ? [q.get('tag')] : null, dongs: q.get('dong') ? [q.get('dong')] : null,
        nats: K.natNames.includes(nat) ? [nat] : null, limit: Math.min(parseInt(q.get('limit') || '40', 10) || 40, 100) });
      return [200, { posts: rows.map((p) => postView(p, u)) }];
    }],
    ['POST', /^\/api\/posts$/, (c) => {
      const u = need(c.user), b = obj(c.body);
      const room = b.room || '', tag = b.tag || '', title = String(b.title || '').trim(), body = String(b.body || '').trim();
      const dong = b.dong || u.dong;
      if (!K.rooms.includes(room) || !K.activeTags.includes(tag) || !(dong in K.dongName)) throw new Fail(400, 'bad_post');
      if (!title || !body) throw new Fail(400, 'need_title_body');
      if (!canWrite(u, room)) throw new Fail(403, 'korean_exchange_only');
      const extra = tag === '모임' ? { when: clip(String(b.when || ''), 40) } : {};
      const p = { id: nextId++, room, tag, title: clip(title, 80), body: clip(body, 2000), body_ko: null, author_id: u.id, dong,
        created_at: nowTs(), extra, is_hidden: 0, likes: 0, likedBy: new Set() };
      db.posts.push(p);
      return [201, { id: p.id }];
    }],
    ['GET', /^\/api\/posts\/hot$/, (c) => { const u = need(c.user); return [200, { posts: hotPosts(5).map((p) => postView(p, u)) }]; }],
    ['GET', /^\/api\/posts\/([^/]+)$/, (c, m) => {
      const u = need(c.user), p = getPost(intId(m[1]));
      if (!p) throw new Fail(404, 'no_post');
      return [200, { ...postView(p, u, true), liked: p.likedBy.has(u.id), canWrite: canWrite(u, p.room), thread: thread(p, u) }];
    }],
    ['POST', /^\/api\/posts\/([^/]+)\/like$/, (c, m) => {
      const u = need(c.user), p = getPost(intId(m[1]));
      if (!p) throw new Fail(404, 'no_post');
      p.likedBy.has(u.id) ? p.likedBy.delete(u.id) : p.likedBy.add(u.id);
      return [200, { liked: p.likedBy.has(u.id), likes: likes(p) }];
    }],
    ['POST', /^\/api\/posts\/([^/]+)\/comments$/, (c, m) => {
      const u = need(c.user), p = getPost(intId(m[1]));
      if (!p) throw new Fail(404, 'no_post');
      const text = String(obj(c.body).body || '').trim();
      if (!text) throw new Fail(400, 'empty');
      if (!canWrite(u, p.room)) throw new Fail(403, 'korean_exchange_only');
      const cm = { id: nextId++, post_id: p.id, author_id: u.id, body: clip(text, 1000), body_ko: null, created_at: nowTs() };
      db.comments.push(cm);
      return [201, { id: cm.id }];
    }],
    ['POST', /^\/api\/posts\/([^/]+)\/report$/, (c, m) => {
      const u = need(c.user), p = getPost(intId(m[1]), true);
      if (!p) throw new Fail(404, 'no_post');
      const b = obj(c.body), reason = K.reportReasons.includes(b.reason) ? b.reason : '기타';
      if (!db.reports.some((r) => r.post_id === p.id && r.user_id === u.id)) {
        db.reports.push({ post_id: p.id, user_id: u.id, reason, created_at: nowTs(), status: 'open' });
      }
      const hidden = openReports(p.id).length >= K.reportHide;
      if (hidden) p.is_hidden = 1;
      return [200, { hidden }];
    }],
    ['GET', /^\/api\/meetup-hint$/, (c) => {
      const u = need(c.user);
      if (u.is_korean || !u.nationality) return [200, { dongs: [] }];
      return [200, { dongs: A.meetup[u.nationality] || [] }];
    }],
    ['GET', /^\/api\/news$/, (c) => {
      const u = need(c.user), lang = uiLang(u), today = dayStr(0);
      const visible = listNotices().filter((e) => noticeVisible(e, u));
      const events = visible.filter((e) => e.kind === 'event').map((e) => noticeView(e, u, lang));
      const upcoming = events.filter((e) => e.date >= today).sort((a, b) => cmp([!a.forMe, a.date], [!b.forMe, b.date]));
      const past = events.filter((e) => e.date < today).sort((a, b) => cmp([b.date], [a.date]));
      const infos = visible.filter((e) => e.kind === 'policy' || e.kind === 'notice').map((e) => noticeView(e, u, lang))
        .sort((a, b) => cmp([!a.forMe, a.kind !== 'notice', a.date], [!b.forMe, b.kind !== 'notice', b.date]));
      return [200, { events: upcoming, pastEvents: past.slice(0, 6), infos }];
    }],
    ['GET', /^\/api\/questions$/, (c) => {
      const u = need(c.user);
      const qs = [...db.questions].sort((a, b) => cmp([b.created_at, b.id], [a.created_at, a.id]));
      return [200, { questions: qs.map((q) => ({ id: q.id, title: q.title, body: q.body, bodyKo: q.body_ko || '', lang: q.language,
        created: q.created_at, answer: q.answer || '', answered: q.answered_at || '', mine: q.author_id === u.id })) }];
    }],
    ['POST', /^\/api\/questions$/, (c) => {
      const u = need(c.user), b = obj(c.body);
      const title = String(b.title || '').trim(), body = String(b.body || '').trim();
      if (!title) throw new Fail(400, 'need_title');
      const q = { id: nextId++, author_id: u.id, language: u.language, title: clip(title, 120), body: clip(body, 2000), body_ko: null,
        created_at: nowTs(), answer: null, answered_by: null, answered_at: null };
      db.questions.push(q);
      return [201, { id: q.id }];
    }],
  ];

  // 앱이 부르는 입구 — 값은 JSON 으로 한 번 굴려 넘긴다(앱이 고쳐도 여기 상태가 바뀌지 않게)
  function handle(method, url, body, token) {
    const u = new URL(url, 'http://demo.invalid');
    const user = userByToken(token) || (token ? null : current);
    let hit = false;
    for (const [m, re, fn] of ROUTES) {
      const mm = re.exec(u.pathname);
      if (!mm) continue;
      hit = true;
      if (m !== method.toUpperCase()) continue;
      try {
        const [status, data] = fn({ user, body, q: u.searchParams }, mm);
        return { status, data: JSON.parse(JSON.stringify(data)) };
      } catch (err) {
        if (err instanceof Fail) return { status: err.status, data: { error: err.code } };
        console.error(err);
        return { status: 500, data: { error: 'server' } };
      }
    }
    return hit ? { status: 405, data: { error: 'method' } } : { status: 404, data: { error: 'not_found' } };
  }

  return { handle };
})();
