// 나 — 화면 언어 · 사는 동네 바꾸기, 알림 설정(시연), 앱 설치, 정보 출처, 계정.
import { api, setToken } from './api.js';
import { t, setLang, lang, LANGS, LANG_NAME, natName, dongName } from './i18n.js';
import { S, go, resetData, flag, isSample } from './store.js';
import { setTop } from './chrome.js';
import { esc, icon, toast } from './ui.js';

const NOTIF_KEY = 'ansan-neighbors-notif';
let installPrompt = null;
window.addEventListener('beforeinstallprompt', (e) => { e.preventDefault(); installPrompt = e; });

function notifPrefs() {
  try { return JSON.parse(localStorage.getItem(NOTIF_KEY) || '{"city":true,"event":true,"comment":true}'); }
  catch { return { city: true, event: true, comment: true }; }
}

export async function render(view) {
  const u = S.user;
  setTop(t('tab.me'));
  const prefs = notifPrefs();
  // 이미 설치했거나, 파일 하나로 연 HTML 판(file:)이면 설치 안내를 숨긴다 — 파일은 홈 화면에 설치할 수 없다
  const standalone = window.matchMedia('(display-mode: standalone)').matches || location.protocol === 'file:';
  view.innerHTML = `
  <section class="profile">
    <span class="avatar">${u.isKorean ? '🇰🇷' : flag(u.nationality)}</span>
    <div><h2>${esc(u.isKorean ? t('me.korean') : natName(u.nationality))}</h2>
      <p class="meta">${esc(dongName(S.boot.dongs.find((d) => d.code === u.dong)?.name || ''))} · ${esc(t('me.joined'))} ${esc(u.joined)}</p></div>
  </section>

  <section class="block card">
    <h2 class="label">${esc(t('me.lang'))}</h2>
    <div class="seg wide lang-seg">${LANGS.map((l) => `<button type="button" class="${l === lang() ? 'on' : ''}" data-lang="${l}" lang="${l}">${esc(LANG_NAME[l])}</button>`).join('')}</div>
    <label class="label" for="me-dong">${esc(t('me.dong'))}</label>
    <select id="me-dong" data-dong>${S.boot.dongs.map((d) => `<option value="${d.code}" ${d.code === u.dong ? 'selected' : ''}>${esc(dongName(d.name))}</option>`).join('')}</select>
  </section>

  <section class="block card">
    <h2 class="label">${esc(t('me.notif'))}</h2>
    ${[['city', 'me.nCity'], ['event', 'me.nEvent'], ['comment', 'me.nComment']].map(([k, key]) => `
      <label class="switch"><span>${esc(t(key))}</span><input type="checkbox" data-notif="${k}" ${prefs[k] ? 'checked' : ''}><i></i></label>`).join('')}
    <p class="fine">${esc(t('n.remindNote'))}</p>
  </section>

  ${standalone ? '' : `<section class="block card">
    <h2 class="label">${icon('phone', 'sm')} ${esc(t('me.install'))}</h2>
    ${installPrompt ? `<button type="button" class="btn primary" data-act="install">${esc(t('me.installBtn'))}</button>` : `<p class="meta">${esc(t('me.installHow'))}</p>`}
  </section>`}

  <section class="block card">
    <h2 class="label">${esc(t('me.data'))}</h2>
    <ul class="sources">
      <li>${icon('bowl', 'sm')}<span>${esc(t('me.dShops', { date: S.boot.shopDate }))}</span></li>
      ${u.isKorean ? '' : `<li>${icon('users', 'sm')}<span>${esc(t('me.dPeople'))}${isSample() ? ` <b class="sample">${esc(t('me.dSample'))}</b>` : ` <b class="internal">${esc(t('me.dReal', { month: S.boot.dataMonth }))}</b>`}</span></li>`}
      <li>${icon('chat', 'sm')}<span>${esc(t('me.dPosts'))}</span></li>
      <li>${icon('map', 'sm')}<span>${esc(t('map.osm'))}</span></li>
      <li>${icon('shield', 'sm')}<span>${esc(t('me.privacy'))}</span></li>
    </ul>
  </section>

  <section class="block row wrap">
    <a class="btn ghost" href="#/welcome?switch=1">${icon('users')}${esc(t('me.switch'))}</a>
    <button type="button" class="btn ghost" data-act="logout">${esc(t('me.logout'))}</button>
  </section>`;

  view.onclick = async (e) => {
    const b = e.target.closest('button');
    if (!b) return;
    try {
      if (b.dataset.lang && b.dataset.lang !== lang()) {
        // 언어방(room)도 함께 바뀐다 — 기타 언어방 주민이 영어를 고르면 영어방으로
        S.user = await api('/api/me', { method: 'PATCH', body: { language: b.dataset.lang } });
        setLang(S.user.uiLang);
        resetData();
        toast(t('me.saved'));
        window.dispatchEvent(new Event('ansan:rerender'));
      } else if (b.dataset.act === 'install' && installPrompt) {
        installPrompt.prompt();
        installPrompt = null;
      } else if (b.dataset.act === 'logout') {
        setToken('');
        S.user = null;
        resetData();
        go('#/welcome');
      }
    } catch { toast(t('err.generic')); }
  };
  view.onchange = async (e) => {
    if (e.target.matches('[data-dong]')) {
      try {
        S.user = await api('/api/me', { method: 'PATCH', body: { dong: e.target.value } });
        resetData();
        toast(t('me.saved'));
        render(view);
      } catch { toast(t('err.generic')); }
    } else if (e.target.matches('[data-notif]')) {
      const p = notifPrefs();
      p[e.target.dataset.notif] = e.target.checked;
      try { localStorage.setItem(NOTIF_KEY, JSON.stringify(p)); } catch { /* 없음 */ }
    }
  };
}

