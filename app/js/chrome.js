// 앱 틀 — 위 제목줄, 아래 탭, 시연판 띠.
import { t } from './i18n.js';
import { S } from './store.js';
import { $, esc, icon } from './ui.js';

const TABS = [['home', 'home'], ['map', 'map'], ['community', 'chat'], ['news', 'news'], ['me', 'user']];

export function renderTabbar(active) {
  $('#tabbar').innerHTML = TABS.map(([key, ic]) => `
    <a class="tab${key === active ? ' on' : ''}" href="#/${key}" ${key === active ? 'aria-current="page"' : ''}>
      ${icon(ic)}<span>${esc(t('tab.' + key))}</span></a>`).join('');
}

export function setTop(title, { back = null, actions = '', brand = false } = {}) {
  const bar = $('#topbar');
  bar.innerHTML = `
    ${back ? `<button class="icon-btn" type="button" data-back aria-label="${esc(t('back'))}">${icon('back')}</button>` : ''}
    ${brand ? `<span class="top-logo" aria-hidden="true">${icon('logo')}</span>` : ''}
    <h1>${esc(title)}</h1>
    <div class="top-actions">${actions}</div>`;
  if (back) $('[data-back]', bar).addEventListener('click', () => (history.length > 1 ? history.back() : (location.hash = back)));
}

export function renderRibbon() {
  const el = $('#ribbon');
  if (!S.boot) { el.hidden = true; return; }
  const real = S.boot.mode === 'real';
  el.className = 'ribbon' + (real ? ' real' : '');
  el.innerHTML = `${icon('info')}<span>${esc(t(real ? 'real.ribbon' : 'demo.ribbon'))}</span>`;
  el.hidden = false;
}
