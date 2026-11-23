// 화면 부품 — 글자 이스케이프, 아이콘, 아래에서 올라오는 시트, 알림 토스트.
import { t } from './i18n.js';

export const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
export const icon = (name, cls = '') => `<svg class="ic ${cls}" aria-hidden="true"><use href="#i-${name}"/></svg>`;
export const $ = (sel, root = document) => root.querySelector(sel);
export const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

// ------------------------------------------------------------------ 시트
let sheetClose = null;
export function openSheet(html, { onMount, label = '' } = {}) {
  const root = $('#sheet');
  const panel = $('#sheet .sheet-panel');
  panel.innerHTML = `<div class="sheet-grip" aria-hidden="true"></div>
    <button class="sheet-x" type="button" aria-label="${esc(t('close'))}">${icon('close')}</button>
    <div class="sheet-body">${html}</div>`;
  panel.setAttribute('aria-label', label);
  root.hidden = false;
  requestAnimationFrame(() => root.classList.add('open'));
  const done = () => closeSheet();
  $('.sheet-x', panel).addEventListener('click', done);
  $('.sheet-back', root).onclick = done;
  sheetClose = null;
  if (onMount) sheetClose = onMount($('.sheet-body', panel)) || null;
  setTimeout(() => { const f = $('[autofocus]', panel); if (f) f.focus(); }, 180);
  return $('.sheet-body', panel);
}
export function closeSheet() {
  const root = $('#sheet');
  if (root.hidden) return;
  root.classList.remove('open');
  if (typeof sheetClose === 'function') sheetClose();
  sheetClose = null;
  setTimeout(() => { root.hidden = true; $('#sheet .sheet-panel').innerHTML = ''; }, 200);
}
export const sheetOpen = () => !$('#sheet').hidden;

// ------------------------------------------------------------------ 토스트
let toastTimer = null;
export function toast(msg) {
  const el = $('#toast');
  el.textContent = msg;
  el.hidden = false;
  el.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { el.classList.remove('show'); setTimeout(() => { el.hidden = true; }, 220); }, 2600);
}

// ------------------------------------------------------------------ 거리
export function haversine(a, b) {
  const R = 6371000, rad = Math.PI / 180;
  const dLat = (b.lat - a.lat) * rad, dLon = (b.lon - a.lon) * rad;
  const s = Math.sin(dLat / 2) ** 2 + Math.cos(a.lat * rad) * Math.cos(b.lat * rad) * Math.sin(dLon / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(s));
}

export function emptyState(text, ic = 'info') {
  return `<div class="empty">${icon(ic)}<p>${esc(text)}</p></div>`;
}
