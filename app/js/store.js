// 앱 상태와 데이터 불러오기 — 화면 모듈들이 같이 쓴다.
import { api } from './api.js';
import { t, natName, dongName } from './i18n.js';

export const S = {
  boot: null,      // /api/bootstrap
  user: null,      // /api/me
  shops: null,     // {date, shops: [...]}
  places: null,    // 이웃 제보 [...]
  news: null,
};

// 가게 종류 색 — dataviz 범주 순서 2 · 3 · 7(주황 · 청록 · 보라, 모든 쌍 색각 검사 통과). 파랑은 '이웃 많은 곳'(순서형) 몫
export const KIND_COLOR = { food: '#eb6834', grocery: '#1baf7a', service: '#6250d6', official: '#1f2a27', community: '#ffffff' };
export const KIND_ICON = { food: 'bowl', grocery: 'basket', service: 'phone', official: 'building', community: 'pin', other: 'pin' };
export const KINDS = ['food', 'grocery', 'service', 'official', 'community'];

export const go = (hash) => { if (location.hash !== hash) location.hash = hash; };
export const dong = (code) => (S.boot ? S.boot.dongs.find((d) => d.code === code) : null);
export const dongLabel = (code, short = false) => { const d = dong(code); return d ? dongName(d.name, short) : ''; };
export const nation = (name) => (S.boot ? S.boot.nations.find((n) => n.name === name) : null);
export const flag = (name) => { const n = nation(name); return n ? n.flag : '🌐'; };
export const natLabel = (name) => (name ? `${flag(name)} ${natName(name)}` : `🇰🇷 ${t('me.korean')}`);
export const isSample = () => S.boot && S.boot.mode !== 'real';

export function myCuisines() {
  return (S.user && S.user.cuisines) || [];
}

// 카드 그림 — 음식 종류 · 가게 종류를 그림 글자로(홈이 딱딱해 보인다는 의견, 2026-11-20). 주인 국적이 아니라 음식 종류다.
const CUISINE_EMOJI = { cn: '🥟', vn: '🍜', th: '🍤', id: '🍚', ph: '🍗', kh: '🍲', mm: '🍜', np: '🍛', lk: '🍛', ca: '🍖', mn: '🍖', halal: '🥙', world: '🌏', sea: '🍲' };
const SUB_EMOJI = { phone: '📱', travel: '✈️', translate: '💬', support: '🏛️' };
export function shopEmoji(s) {
  if (s.kind === 'grocery') return '🛒';
  if (s.kind === 'service') return SUB_EMOJI[s.sub] || '🧾';
  if (s.kind === 'official') return '🏛️';
  if (s.kind === 'community') return '📍';
  return CUISINE_EMOJI[s.cuisine] || '🍽️';
}

// 시드 글 제목 끝의 '(가상)' 꼬리표 → 작은 '예시' 딱지로. 예시라는 표시는 남기고 제목은 깔끔하게.
const SAMPLE_TAIL = /\s*[(（](?:가상(?: 공지)?|sample|示例|пример|mẫu)[)）]\s*$/i;
export function splitSample(title) {
  const s = String(title || '');
  return SAMPLE_TAIL.test(s) ? { title: s.replace(SAMPLE_TAIL, ''), sample: true } : { title: s, sample: false };
}
export function cuisineLabel(c) { return c ? t('cu.' + c) : ''; }
export function shopTypeLabel(s) {
  if (s.kind === 'service' || s.kind === 'official') return t('sub.' + (s.sub || 'support'));
  if (s.kind === 'community') return t('kind.community');
  return t('kind.' + s.kind);
}

export async function loadShops(force = false) {
  if (!S.shops || force) S.shops = await api('/api/shops');
  return S.shops;
}
export async function loadPlaces(force = false) {
  if (!S.places || force) S.places = (await api('/api/places')).places;
  return S.places;
}
export async function loadNews(force = false) {
  if (!S.news || force) S.news = await api('/api/news');
  return S.news;
}
export function resetData() { S.shops = null; S.places = null; S.news = null; }
