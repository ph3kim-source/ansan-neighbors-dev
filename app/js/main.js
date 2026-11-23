// 안산 이웃 — 시민 앱. 화면 이동은 주소의 #/… 로 한다(새로고침해도 그 화면).
import { api, getToken, setToken } from './api.js';
import { setLang, t, LANGS } from './i18n.js';
import { S, go } from './store.js';
import { $, closeSheet, sheetOpen, emptyState, esc } from './ui.js';
import { renderTabbar, renderRibbon } from './chrome.js';
import * as Welcome from './welcome.js';
import * as Home from './home.js';
import * as MapView from './map.js';
import * as Community from './community.js';
import * as News from './news.js';
import * as Me from './me.js';

const TAB_OF = { home: 'home', map: 'map', community: 'community', post: 'community', write: 'community', news: 'news', me: 'me' };

function parse() {
  const raw = location.hash.replace(/^#\/?/, '');
  const [path, qs] = raw.split('?');
  const parts = path.split('/').filter(Boolean);
  return { name: parts[0] || 'home', arg: parts[1] || '', q: new URLSearchParams(qs || '') };
}

let routing = 0;
async function route() {
  const my = ++routing;
  if (sheetOpen()) closeSheet();
  const r = parse();
  if (!S.user && r.name !== 'welcome') { go('#/welcome'); return; }
  if (S.user && r.name === 'welcome' && !r.q.has('switch')) { go('#/home'); return; }
  const known = r.name === 'welcome' || r.name in TAB_OF;
  if (!known) { go('#/home'); return; }

  document.body.dataset.route = r.name;
  const onMap = r.name === 'map';
  $('#tabbar').hidden = r.name === 'welcome';
  $('#topbar').hidden = r.name === 'welcome' || onMap;
  $('#view').hidden = onMap;
  $('#mapview').hidden = !onMap;
  renderRibbon();
  if (r.name !== 'welcome') renderTabbar(TAB_OF[r.name]);

  const view = $('#view');
  view.onclick = view.onsubmit = view.onchange = view.oninput = null;   // 앞 화면의 손잡이를 떼어 낸다
  if (!onMap) { view.innerHTML = `<div class="loading">${esc(t('loading'))}</div>`; view.scrollTop = 0; }
  try {
    switch (r.name) {
      case 'welcome': await Welcome.render(view, r); break;
      case 'home': await Home.render(view, r); break;
      case 'map': await MapView.render($('#mapview'), r); break;
      case 'community': await Community.renderList(view, r); break;
      case 'post': await Community.renderPost(view, r); break;
      case 'write': await Community.renderWrite(view, r); break;
      case 'news': await News.render(view, r); break;
      case 'me': await Me.render(view, r); break;
    }
  } catch (err) {
    if (my !== routing) return;
    console.warn(err);
    if (err && err.status === 401) { setToken(''); S.user = null; go('#/welcome'); return; }
    view.hidden = false;
    view.innerHTML = emptyState(err && err.code === 'network' ? t('err.network') : t('err.generic'), 'info');
  }
}

// 다른 화면에서 언어를 바꾸면(나 → 화면 언어) 틀까지 다시 그린다
export function rerender() { route(); }
window.addEventListener('ansan:rerender', rerender);

async function start() {
  try {
    S.boot = await api('/api/bootstrap');
  } catch {
    $('#view').innerHTML = emptyState('연결이 안 돼요 · Connection problem', 'info');
    return;
  }
  if (getToken()) {
    try { S.user = await api('/api/me'); } catch { setToken(''); }
  }
  let saved = '';
  try { saved = localStorage.getItem('ansan-neighbors-lang') || ''; } catch { /* 없음 */ }
  const guess = (navigator.language || 'ko').slice(0, 2);
  setLang(S.user ? S.user.uiLang : (saved || (LANGS.includes(guess) ? guess : 'en')));
  window.addEventListener('hashchange', route);
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && sheetOpen()) closeSheet(); });
  route();
  if ('serviceWorker' in navigator && location.protocol !== 'file:' && window.isSecureContext) {
    navigator.serviceWorker.register('./sw.js').catch(() => { /* 오프라인 캐시 없이도 동작 */ });
  }
}

start();
