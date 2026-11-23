// 커뮤니티 — 언어방 익명 게시판(에브리타임식, 결정 R2-6 · 7). 글 목록 → 글 보기(댓글 · 좋아요 · 신고) → 글쓰기.
import { api } from './api.js';
import { t, ago, dongName, natName } from './i18n.js';
import { S, dongLabel, flag, go } from './store.js';
import { setTop } from './chrome.js';
import { $, esc, icon, openSheet, closeSheet, toast, emptyState } from './ui.js';

const ROOM_ORDER = ['ko', 'zh', 'ru', 'vi', 'en', 'etc', 'exchange'];
const C = { room: null, tag: '', same: false, userId: null };

const myRoom = () => (S.user.isKorean ? 'exchange' : S.user.language);
const canWrite = (room) => room === 'exchange' || !S.user.isKorean;

function author(p) {
  return p.isKorean ? '🇰🇷' : flag(p.nat);
}

export function postItem(p) {
  const hot = p.likes >= S.boot.hotMin;
  return `<a class="post-item" href="#/post/${p.id}">
    <div class="chips">${hot ? '<span class="chip hot">HOT</span>' : ''}<span class="chip">${esc(t('tag.' + p.tag))}</span>
      ${p.mine ? `<span class="chip brand">${esc(t('c.mine'))}</span>` : ''}</div>
    <h3>${esc(p.title)}</h3>
    <p class="excerpt">${esc(p.body)}</p>
    <p class="meta"><span>${author(p)} ${esc(t('c.anon'))}</span><span>${esc(dongLabel(p.dong, true))}</span><span>${esc(ago(p.created))}</span>
      <span class="stat">${icon('heart', 'sm')}${p.likes}</span><span class="stat">${icon('comment', 'sm')}${p.comments}</span></p>
  </a>`;
}

function roomChips() {
  const mine = myRoom();
  const rooms = [mine, ...ROOM_ORDER.filter((r) => r !== mine)];
  return rooms.map((r) => `<button type="button" class="chip-btn${C.room === r ? ' on' : ''}" data-room="${r}">${esc(t('room.' + r))}</button>`).join('');
}

// ------------------------------------------------------------------ 목록
export async function renderList(view, r) {
  if (C.userId !== S.user.id) { C.userId = S.user.id; C.room = myRoom(); C.tag = ''; C.same = false; }
  const dongFilter = r.q.get('dong') || '';
  setTop(t('tab.community'));
  const qs = new URLSearchParams({ room: C.room, limit: '40' });
  if (C.tag) qs.set('tag', C.tag);
  if (dongFilter) qs.set('dong', dongFilter);
  // 언어방은 그대로 두고 '같은 나라 글만' 걸러 보기(2026-11-20 사용자 결정) — 국적 ≠ 언어(R2-7)라 방을 쪼개지 않는다
  const sameChip = !S.user.isKorean && S.user.nationality;
  if (sameChip && C.same) qs.set('nat', S.user.nationality);
  const [list, hot] = await Promise.all([api('/api/posts?' + qs), api('/api/posts/hot')]);
  const writable = canWrite(C.room);
  view.innerHTML = `
    <div class="chip-row sticky" role="tablist" aria-label="room">${roomChips()}</div>
    ${S.user.isKorean && C.room !== 'exchange' ? `<p class="notice">${icon('info')}${esc(t('c.koreanRule'))}</p>` : ''}
    ${dongFilter ? `<p class="filter-note">${icon('pin', 'sm')}${esc(dongLabel(dongFilter))} <a href="#/community">${icon('close', 'sm')}</a></p>` : ''}
    ${hot.posts.length && !dongFilter ? `<section class="block"><div class="block-head"><h2>${icon('fire', 'sm')} ${esc(t('c.hot'))}</h2></div>
      <div class="h-scroll">${hot.posts.map((p) => `<a class="hot-card" href="#/post/${p.id}"><span class="chip">${esc(t('room.' + p.room))}</span>
        <b>${esc(p.title)}</b><small>${icon('heart', 'sm')}${p.likes} · ${icon('comment', 'sm')}${p.comments}</small></a>`).join('')}</div></section>` : ''}
    <div class="chip-row" role="toolbar">
      ${sameChip ? `<button type="button" class="chip-btn same${C.same ? ' on' : ''}" data-same aria-pressed="${C.same}">${flag(S.user.nationality)} ${esc(t('c.sameNat', { nat: natName(S.user.nationality) }))}</button>` : ''}
      <button type="button" class="chip-btn${!C.tag ? ' on' : ''}" data-tag="">${esc(t('map.all'))}</button>
      ${S.boot.tags.map((g) => `<button type="button" class="chip-btn${C.tag === g ? ' on' : ''}" data-tag="${esc(g)}">${esc(t('tag.' + g))}</button>`).join('')}
    </div>
    <div class="list">${list.posts.length ? list.posts.map(postItem).join('') : emptyState(t('c.empty'), 'chat')}</div>
    <p class="rules">${esc(t('c.rules'))}</p>
    ${writable ? `<a class="fab" href="#/write?room=${C.room}">${icon('pen')}<span>${esc(t('c.write'))}</span></a>` : ''}`;
  view.onclick = (e) => {
    const b = e.target.closest('button');
    if (!b) return;
    if (b.dataset.room) { C.room = b.dataset.room; renderList(view, r); }
    else if ('same' in b.dataset) { C.same = !C.same; renderList(view, r); }
    else if ('tag' in b.dataset) { C.tag = b.dataset.tag; renderList(view, r); }
  };
}

// ------------------------------------------------------------------ 글 보기
function comment(c, showTr) {
  const who = c.alias === 0 ? t('c.op') : t('c.anonN', { n: c.alias });
  return `<li class="comment${c.alias === 0 ? ' op' : ''}">
    <p class="who">${esc(who)}${c.mine ? ` <span class="chip brand">${esc(t('c.me'))}</span>` : ''}<span class="meta">${esc(ago(c.created))}</span></p>
    <p>${esc(c.body)}</p>
    ${showTr && c.bodyKo ? `<p class="tr">${icon('translate', 'sm')}${esc(c.bodyKo)}</p>` : ''}
  </li>`;
}

export async function renderPost(view, r) {
  const id = parseInt(r.arg, 10);
  const p = await api('/api/posts/' + id);
  let showTr = false;
  setTop(t('room.' + p.room), { back: '#/community' });
  const foreignText = p.room !== 'ko' && p.room !== 'exchange';
  const draw = () => {
    view.innerHTML = `
    <article class="post">
      <div class="chips"><span class="chip">${esc(t('tag.' + p.tag))}</span><span class="chip">${icon('pin', 'sm')}${esc(dongLabel(p.dong, true))}</span>
        ${p.extra && p.extra.when ? `<span class="chip brand">${icon('cal', 'sm')}${esc(p.extra.when)}</span>` : ''}</div>
      <h2>${esc(p.title)}</h2>
      <p class="meta">${author(p)} ${esc(t('c.anon'))} · ${esc(ago(p.created))}</p>
      <div class="post-body">${esc(p.body).replace(/\n/g, '<br>')}</div>
      ${foreignText ? `<button type="button" class="link-btn" data-act="tr">${icon('translate', 'sm')}${esc(t(showTr ? 'c.original' : 'c.translate'))}</button>
        ${showTr ? `<p class="tr">${p.bodyKo ? esc(p.bodyKo) : esc(t('c.noTr'))}</p>` : ''}` : ''}
      <div class="post-actions">
        <button type="button" class="btn like${p.liked ? ' on' : ''}" data-act="like" aria-pressed="${p.liked}">${icon('heart')}<span>${esc(t('c.like'))}</span><b>${p.likes}</b></button>
        <span class="meta">${icon('comment', 'sm')}${p.thread.length}</span>
        <button type="button" class="btn ghost sm" data-act="report">${icon('flag')}${esc(t('c.report'))}</button>
      </div>
    </article>
    <section class="comments">
      <h3>${esc(t('c.comments'))} ${p.thread.length}</h3>
      <ul>${p.thread.map((c) => comment(c, showTr)).join('')}</ul>
    </section>
    ${p.canWrite ? `<form class="composer" data-comment>
        <input name="body" maxlength="1000" placeholder="${esc(t('c.addComment'))}" aria-label="${esc(t('c.addComment'))}" autocomplete="off">
        <button class="icon-btn send" type="submit" aria-label="${esc(t('c.send'))}">${icon('send')}</button>
      </form>` : `<p class="notice">${icon('info')}${esc(t('c.koreanRule'))}</p>`}`;
  };
  draw();
  view.onclick = async (e) => {
    const b = e.target.closest('button');
    if (!b) return;
    try {
      if (b.dataset.act === 'tr') { showTr = !showTr; draw(); }
      else if (b.dataset.act === 'like') {
        const res = await api(`/api/posts/${id}/like`, { method: 'POST' });
        p.liked = res.liked; p.likes = res.likes; draw();
      } else if (b.dataset.act === 'report') reportSheet(id);
    } catch (err) { toast(err.code === 'network' ? t('err.network') : t('err.generic')); }
  };
  view.onsubmit = async (e) => {
    if (!e.target.matches('[data-comment]')) return;
    e.preventDefault();
    const input = e.target.elements.body;
    const text = input.value.trim();
    if (!text) return;
    try {
      await api(`/api/posts/${id}/comments`, { method: 'POST', body: { body: text } });
      const fresh = await api('/api/posts/' + id);
      Object.assign(p, fresh);
      draw();
      view.scrollTop = view.scrollHeight;
    } catch (err) { toast(err.status === 403 ? t('c.koreanRule') : t('err.generic')); }
  };
}

function reportSheet(id) {
  openSheet(`<h2>${esc(t('c.reportWhy'))}</h2>
    <div class="pick-list">${S.boot.reportReasons.map((r) => `<button type="button" class="pick" data-reason="${esc(r)}"><span>${esc(t('rr.' + r))}</span>${icon('chev')}</button>`).join('')}</div>`, {
    label: t('c.report'),
    onMount: (body) => body.addEventListener('click', async (e) => {
      const b = e.target.closest('[data-reason]');
      if (!b) return;
      try {
        const res = await api(`/api/posts/${id}/report`, { method: 'POST', body: { reason: b.dataset.reason } });
        closeSheet();
        toast(res.hidden ? t('c.hiddenNow') : t('c.reported'));
        if (res.hidden) go('#/community');
      } catch { toast(t('err.generic')); }
    }),
  });
}

// ------------------------------------------------------------------ 글쓰기
export async function renderWrite(view, r) {
  setTop(t('c.write'), { back: '#/community' });
  let room = r.q.get('room') || myRoom();
  if (!canWrite(room)) room = 'exchange';
  const rooms = ROOM_ORDER.filter(canWrite);
  let tag = S.boot.tags[0];
  let hint = null;
  const draw = (keep = {}) => {
    view.innerHTML = `
    <form class="form write" data-write>
      <label>${esc(t('c.room'))}<select name="room">${rooms.map((x) => `<option value="${x}" ${x === room ? 'selected' : ''}>${esc(t('room.' + x))}</option>`).join('')}</select></label>
      <fieldset><legend>${esc(t('c.topic'))}</legend><div class="row wrap">
        ${S.boot.tags.map((g) => `<label class="radio-chip"><input type="radio" name="tag" value="${esc(g)}" ${g === tag ? 'checked' : ''}><span>${esc(t('tag.' + g))}</span></label>`).join('')}
      </div></fieldset>
      ${tag === '모임' ? `<label>${esc(t('c.when'))}<input name="when" maxlength="40" placeholder="${esc(t('c.whenPh'))}" value="${esc(keep.when || '')}"></label>
        ${hint && hint.length ? `<p class="hint">${icon('users', 'sm')}${esc(t('c.meetHint', { dongs: hint.map((c) => dongLabel(c, true)).join(', ') }))}</p>` : ''}` : ''}
      <label>${esc(t('c.title'))}<input name="title" maxlength="80" required value="${esc(keep.title || '')}"></label>
      <label>${esc(t('c.body'))}<textarea name="body" rows="6" maxlength="2000" required>${esc(keep.body || '')}</textarea></label>
      <label>${esc(t('c.dong'))}<select name="dong">${S.boot.dongs.map((d) => `<option value="${d.code}" ${d.code === (keep.dong || S.user.dong) ? 'selected' : ''}>${esc(dongName(d.name))}</option>`).join('')}</select></label>
      <p class="meta">${icon('shield', 'sm')}${esc(t('c.anonPost'))} · ${esc(t('c.rules'))}</p>
      <button class="btn primary block" type="submit">${esc(t('c.post'))}</button>
    </form>`;
  };
  draw();
  view.onchange = async (e) => {
    const f = e.target.form;
    if (!f) return;
    if (e.target.name === 'tag' || e.target.name === 'room') {
      const keep = { title: f.title.value, body: f.body.value, dong: f.dong.value, when: f.when ? f.when.value : '' };
      tag = f.tag.value; room = f.room.value;
      if (tag === '모임' && hint === null && !S.user.isKorean) {
        try { hint = (await api('/api/meetup-hint')).dongs; } catch { hint = []; }
      }
      draw(keep);
    }
  };
  view.onsubmit = async (e) => {
    e.preventDefault();
    const f = new FormData(e.target);
    if (!String(f.get('title')).trim() || !String(f.get('body')).trim()) { toast(t('c.need')); return; }
    try {
      const res = await api('/api/posts', { method: 'POST', body: Object.fromEntries(f) });
      toast(t('c.posted'));
      C.room = f.get('room'); C.tag = '';
      go('#/post/' + res.id);
    } catch (err) {
      toast(err.code === 'korean_exchange_only' ? t('c.koreanRule') : err.code === 'need_title_body' ? t('c.need') : t('err.generic'));
    }
  };
}
