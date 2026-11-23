// 시작 화면 — 언어 → 어떤 이웃 → 국적 → 사는 동 (간편가입, 결정 R2-5). 시연 계정으로 바로 둘러볼 수도 있다.
import { api, setToken } from './api.js';
import { t, setLang, lang, LANGS, LANG_NAME, natName, dongName } from './i18n.js';
import { S, go, resetData, flag } from './store.js';
import { $, esc, icon, toast } from './ui.js';

const st = { step: 'lang', isKorean: false, nationality: null, q: '' };

function langStep() {
  return `
  <section class="welcome">
    <div class="brand-mark">${icon('logo')}</div>
    <h1>${esc(t('app'))}</h1>
    <p class="lead">${esc(t('w.title'))}</p>
    <p class="sub">${esc(t('w.sub'))}</p>
    <h2 class="label">${esc(t('w.lang'))}</h2>
    <div class="lang-grid">
      ${LANGS.map((l) => `<button type="button" class="lang-btn${l === lang() ? ' on' : ''}" data-lang="${l}" lang="${l}">${esc(LANG_NAME[l])}</button>`).join('')}
    </div>
    <button type="button" class="btn primary block" data-act="start">${esc(t('w.start'))}</button>
    <button type="button" class="btn ghost block" data-act="demo">${esc(t('w.demo'))}</button>
  </section>`;
}

function whoStep() {
  return `
  <section class="welcome step">
    ${backBtn('lang')}
    <h1 class="h-step">${esc(t('w.who'))}</h1>
    <button type="button" class="choice" data-who="foreign">
      <span class="choice-emoji">🌏</span><span><b>${esc(t('w.foreign'))}</b><small>${esc(t('w.foreignSub'))}</small></span>${icon('chev')}
    </button>
    <button type="button" class="choice" data-who="korean">
      <span class="choice-emoji">🇰🇷</span><span><b>${esc(t('w.korean'))}</b><small>${esc(t('w.koreanSub'))}</small></span>${icon('chev')}
    </button>
    <p class="privacy">${icon('shield')}${esc(t('w.privacy'))}</p>
  </section>`;
}

function natStep() {
  const q = st.q.trim().toLowerCase();
  const list = S.boot.nations.filter((n) => !q || natName(n.name).toLowerCase().includes(q) || n.name.includes(q));
  return `
  <section class="welcome step">
    ${backBtn('who')}
    <h1 class="h-step">${esc(t('w.nat'))}</h1>
    <label class="search">${icon('search')}<input type="search" data-q value="${esc(st.q)}" placeholder="${esc(t('w.search'))}" aria-label="${esc(t('w.search'))}"></label>
    <div class="pick-list">
      ${list.map((n) => `<button type="button" class="pick" data-nat="${esc(n.name)}"><span class="flag">${n.flag}</span>
        <span>${esc(natName(n.name))}${lang() !== 'ko' ? `<small>${esc(n.name)}</small>` : ''}</span>${icon('chev')}</button>`).join('')}
    </div>
  </section>`;
}

function dongStep() {
  const groups = ['단원구', '상록구'].map((gu) => {
    const ds = S.boot.dongs.filter((d) => d.gu === gu);
    return `<h2 class="label">${esc(gu)}</h2><div class="pick-list">${ds.map((d) => `
      <button type="button" class="pick" data-dong="${d.code}"><span>${esc(dongName(d.name))}</span>${icon('chev')}</button>`).join('')}</div>`;
  }).join('');
  return `
  <section class="welcome step">
    ${backBtn(st.isKorean ? 'who' : 'nat')}
    <h1 class="h-step">${esc(t('w.dong'))}</h1>
    ${groups}
    <p class="privacy">${icon('shield')}${esc(t('w.privacy'))}</p>
  </section>`;
}

function demoStep() {
  const people = S.boot.personas.filter((p) => p.role === 'resident');
  return `
  <section class="welcome step">
    ${backBtn('lang')}
    <h1 class="h-step">${esc(t('w.demo'))}</h1>
    <p class="sub">${esc(t('w.demoNote'))}</p>
    <div class="pick-list">
      ${people.map((p) => {
        const d = S.boot.dongs.find((x) => x.code === p.dong);
        return `<button type="button" class="pick persona" data-persona="${p.key}">
          <span class="flag">${p.isKorean ? '🇰🇷' : flag(p.nationality)}</span>
          <span><b>${esc(p.isKorean ? t('w.korean') : natName(p.nationality))} · ${esc(dongName(d ? d.name : '', true))}</b>
          <small>${esc(LANG_NAME[p.language] || p.language)} · ${esc(p.label.replace(/^\S+\s/, ''))}</small></span>${icon('chev')}</button>`;
      }).join('')}
    </div>
  </section>`;
}

const backBtn = (to) => `<button type="button" class="icon-btn back" data-step="${to}" aria-label="${esc(t('back'))}">${icon('back')}</button>`;

function draw(view) {
  view.innerHTML = { lang: langStep, who: whoStep, nat: natStep, dong: dongStep, demo: demoStep }[st.step]();
  view.scrollTop = 0;
}

async function finish(promise) {
  try {
    const res = await promise;
    setToken(res.token);
    S.user = res.user;
    resetData();
    setLang(res.user.uiLang);
    toast(t('w.done'));
    st.step = 'lang'; st.q = '';
    go('#/home');
  } catch (err) {
    toast(err && err.code === 'network' ? t('err.network') : t('err.generic'));
  }
}

function roomFor(nationality) {
  const n = S.boot.nations.find((x) => x.name === nationality);
  const ui = lang();
  if (ui === 'en' && n && n.room === 'etc') return 'etc';
  return ui;
}

export async function render(view, r) {
  if (r.q.has('switch')) st.step = 'demo';
  draw(view);
  view.onclick = (e) => {
    const b = e.target.closest('button');
    if (!b) return;
    if (b.dataset.lang) {
      setLang(b.dataset.lang);
      try { localStorage.setItem('ansan-neighbors-lang', b.dataset.lang); } catch { /* 없음 */ }
      draw(view);
    } else if (b.dataset.act === 'start') { st.step = 'who'; draw(view); }
    else if (b.dataset.act === 'demo') { st.step = 'demo'; draw(view); }
    else if (b.dataset.step) { st.step = b.dataset.step; draw(view); }
    else if (b.dataset.who) {
      st.isKorean = b.dataset.who === 'korean';
      st.step = st.isKorean ? 'dong' : 'nat';
      draw(view);
    } else if (b.dataset.nat) { st.nationality = b.dataset.nat; st.step = 'dong'; draw(view); }
    else if (b.dataset.dong) {
      finish(api('/api/signup', { method: 'POST', body: {
        nationality: st.isKorean ? null : st.nationality, isKorean: st.isKorean,
        language: st.isKorean ? 'ko' : roomFor(st.nationality), dong: b.dataset.dong } }));
    } else if (b.dataset.persona) {
      finish(api('/api/session', { method: 'POST', body: { persona: b.dataset.persona } }));
    }
  };
  view.oninput = (e) => {
    if (e.target.matches('[data-q]')) {
      st.q = e.target.value;
      const pos = e.target.selectionStart;
      draw(view);
      const inp = $('[data-q]', view);
      inp.focus();
      inp.setSelectionRange(pos, pos);
    }
  };
}

