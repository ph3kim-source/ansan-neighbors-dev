// 홈 — 숫자 · 순위 대신 바로 쓸 것만: 곧 열리는 행사, 가까운 고향 가게, 언어방 이야기, 안산시 안내.
// 2026-11-20 사용자 의견 "딱딱해 보인다" → 시간대 인사 · 동네 그림 · 색 있는 바로가기 · 그림 카드(행사 포스터, 가게 음식 그림).
import { api } from './api.js';
import { t, natName, dateLabel, timeOf, distance } from './i18n.js';
import { S, loadShops, loadNews, myCuisines, cuisineLabel, shopTypeLabel, dong, dongLabel, shopEmoji, splitSample, isSample } from './store.js';
import { setTop } from './chrome.js';
import { esc, icon, haversine } from './ui.js';
import { postItem } from './community.js';

export function dday(iso) {
  const [y, m, d] = String(iso).slice(0, 10).split('-').map(Number);
  const today = new Date(); today.setHours(0, 0, 0, 0);
  const n = Math.round((new Date(y, m - 1, d) - today) / 86400000);
  return n <= 0 ? t('n.today') : `D-${n}`;
}

const sampleChip = (on) => (on ? `<span class="chip">${esc(t('n.sample'))}</span>` : '');

// 소식 탭의 목록형 행사 카드(날짜 칸)
export function eventCard(e, compact = false) {
  const [, , d] = e.date.slice(0, 10).split('-').map(Number);
  const { title, sample } = splitSample(e.title);
  return `<a class="event-card${compact ? ' compact' : ''}" href="#/news?item=${e.id}">
    <div class="date-tile"><span>${esc(dateLabel(e.date, { month: 'short' }))}</span><b>${d}</b><small>${esc(dateLabel(e.date, { weekday: 'short' }))}</small></div>
    <div class="event-main">
      <div class="chips">${e.forMe ? `<span class="chip brand">${esc(t('n.forMe'))}</span>` : ''}<span class="chip">${esc(dday(e.date))}</span>${sampleChip(sample)}</div>
      <h3><span class="emo" aria-hidden="true">${esc(e.emoji || '')}</span> ${esc(title)}</h3>
      ${e.dong ? `<p class="meta">${icon('pin', 'sm')}${esc(dongLabel(e.dong))}</p>` : ''}
    </div></a>`;
}

// 홈의 포스터형 행사 카드 — 옆으로 넘겨 본다
function eventPoster(e, i) {
  const { title, sample } = splitSample(e.title);
  return `<a class="poster tint-${i % 4}" href="#/news?item=${e.id}">
    <span class="poster-top"><span class="poster-emo" aria-hidden="true">${esc(e.emoji || '🎉')}</span><span class="chip dday">${esc(dday(e.date))}</span></span>
    <b>${esc(title)}</b>
    <small>${esc(dateLabel(e.date))}${timeOf(e.date) ? ' ' + esc(timeOf(e.date)) : ''}${e.dong ? ' · ' + esc(dongLabel(e.dong, true)) : ''}</small>
    <span class="chips">${e.forMe ? `<span class="chip brand">${esc(t('n.forMe'))}</span>` : ''}${sampleChip(sample)}</span>
  </a>`;
}

// 고향 사람이 많이 다니는 골목 · 동네에 있는 가게 표시(서버가 주민 본인 국적으로만 붙인다 — 단계 · 인원 없이 있다/없다만)
export function nearBadge(s) {
  if (!s.near) return '';
  // 카드가 좁아 짧게 — 골목인지 동네인지는 가게 시트의 줄(shop.nearLine · nearLineDong)이 말해 준다
  return `<span class="near-badge">👥 ${esc(t('shop.nearBadge'))}${isSample() ? ' · ' + esc(t('n.sample')) : ''}</span>`;
}

export function shopCard(s, meters) {
  const kind = s.kind || 'food';
  return `<a class="shop-card" href="#/map?shop=${encodeURIComponent(s.id)}">
    <span class="shop-emo k-${kind}" aria-hidden="true">${shopEmoji(s)}</span>
    <b>${esc(s.name)}</b>
    <small>${esc(cuisineLabel(s.cuisine) || shopTypeLabel(s))} · ${esc(shopTypeLabel(s))}</small>
    <small class="meta">${icon('pin', 'sm')}${esc(dongLabel(s.dong, true))}${meters != null ? ' · ' + esc(distance(meters)) : ''}</small>
    ${nearBadge(s)}
  </a>`;
}

// 고향 사람이 많이 다니는 쪽 가게를 먼저, 그다음 가까운 순(2026-11-20 사용자: "고향 사람 다니는 쪽으로")
function nearestShops(shops, n = 8) {
  const me = dong(S.user.dong);
  const cu = myCuisines();
  let pool = shops.filter((s) => s.kind === 'food' || s.kind === 'grocery');
  if (cu.length) {
    const mine = pool.filter((s) => cu.includes(s.cuisine));
    if (mine.length >= 3) pool = mine;
  }
  return pool.map((s) => ({ s, m: me ? haversine(me, s) : null }))
    .sort((a, b) => (b.s.near ? 1 : 0) - (a.s.near ? 1 : 0) || (a.m ?? 0) - (b.m ?? 0)).slice(0, n);
}

function greetingKey(h = new Date().getHours()) {
  if (h >= 5 && h < 11) return 'morning';
  if (h >= 11 && h < 17) return 'afternoon';
  if (h >= 17 && h < 22) return 'evening';
  return 'night';
}

// 인사 카드 그림 — 우리 동네(아파트 · 집 · 나무 · 이웃 둘). 낮엔 해, 밤엔 달.
function scene(night) {
  const sky = night
    ? `<mask id="hello-moon"><rect width="170" height="100" fill="#fff"/><circle cx="155" cy="15" r="9.5" fill="#000"/></mask>
       <circle cx="150" cy="20" r="11" fill="#ffe7a3" mask="url(#hello-moon)"/>`
    : '<circle cx="150" cy="20" r="11" fill="#ffc94a"/>';
  const win = (x, y, lit) => `<rect x="${x}" y="${y}" width="6" height="6" rx="1.5" class="${lit ? 's-lit' : 's-win'}"/>`;
  return `<svg class="scene" viewBox="0 0 170 100" aria-hidden="true">
    ${sky}
    <path class="s-ground" d="M0 90 C40 82 80 86 110 87 S150 82 170 85 V100 H0Z"/>
    <rect class="s-bld" x="10" y="30" width="28" height="62" rx="5"/>
    ${win(16, 38, true)}${win(26, 38, false)}${win(16, 49, false)}${win(26, 49, true)}${win(16, 60, true)}${win(26, 60, false)}${win(16, 71, false)}${win(26, 71, true)}
    <rect class="s-bld" x="46" y="58" width="34" height="34" rx="3"/>
    <path d="M42 61 L63 43 L84 61" fill="none" stroke="#ff8a65" stroke-width="6" stroke-linecap="round" stroke-linejoin="round"/>
    <rect x="58" y="74" width="10" height="18" rx="2" fill="#ff8a65"/>${win(50, 65, true)}${win(70, 65, night)}
    <rect class="s-bld" x="88" y="46" width="24" height="46" rx="5"/>
    ${win(93, 53, night)}${win(103, 53, true)}${win(93, 64, true)}${win(103, 64, false)}${win(93, 75, false)}${win(103, 75, night)}
    <circle cx="124" cy="72" r="11" fill="#5fcf9f"/><rect x="122.5" y="76" width="3" height="16" rx="1.5" fill="#a07a55"/>
    <circle cx="142" cy="78" r="4.2" fill="#f4c49c"/><rect x="137" y="84" width="10" height="12" rx="5" fill="#ff8a65"/>
    <circle cx="156" cy="79" r="4.2" fill="#c98f62"/><rect x="151" y="85" width="10" height="11" rx="5" fill="#4f8ff0"/>
  </svg>`;
}

export async function render(view) {
  const u = S.user;
  setTop(t('app'), { brand: true, actions: `<a class="icon-btn" href="#/news" aria-label="${esc(t('tab.news'))}">${icon('bell')}</a>` });
  const room = u.isKorean ? 'exchange' : u.language;
  const [shops, news, posts] = await Promise.all([
    loadShops(), loadNews(), api(`/api/posts?room=${encodeURIComponent(room)}&limit=3`),
  ]);
  const near = nearestShops(shops.shops);
  const cu = myCuisines();
  const events = news.events.slice(0, 4);
  const infos = news.infos.filter((i) => i.forMe).concat(news.infos.filter((i) => !i.forMe)).slice(0, 2);
  const greet = greetingKey();
  const where = dongLabel(u.dong, true);
  const quick = [
    ['#/map', '🍜', 'h.qShops', 0],
    u.isKorean ? null : ['#/map?people=1', '🧑‍🤝‍🧑', 'h.qPeople', 1],
    ['#/write', '✏️', 'h.qWrite', 2],
    ['#/news?tab=ask', '🙋', 'h.qAsk', 3],
  ].filter(Boolean);

  view.innerHTML = `
  <section class="hello-card" data-greet="${greet}">
    <p class="hello">${esc(t('h.' + greet))}</p>
    <p class="who">${esc(u.isKorean ? t('h.lives', { dong: where }) : t('h.who', { dong: where, nat: natName(u.nationality) }))}</p>
    ${scene(greet === 'night' || greet === 'evening')}
  </section>

  <nav class="quick" aria-label="${esc(t('app'))}">
    ${quick.map(([href, emo, key, tint]) => `<a href="${href}"><span class="q-emo tint-${tint}" aria-hidden="true">${emo}</span><span>${esc(t(key))}</span></a>`).join('')}
  </nav>

  ${events.length ? `<section class="block">
    <div class="block-head"><h2>${esc(t('h.events'))}</h2><a href="#/news">${esc(t('h.more'))}${icon('chev', 'sm')}</a></div>
    <div class="h-scroll">${events.map(eventPoster).join('')}</div>
  </section>` : ''}

  <section class="block">
    <div class="block-head"><h2>${esc(t(cu.length ? 'h.shops' : 'h.shopsWorld'))}</h2><a href="#/map${cu.length ? '?mine=1' : ''}">${esc(t('h.seeMap'))}${icon('chev', 'sm')}</a></div>
    ${near.some(({ s }) => s.near) ? `<p class="block-sub">👥 ${esc(t('h.shopsBusyNote'))}</p>` : ''}
    <div class="h-scroll">${near.map(({ s, m }) => shopCard(s, m)).join('')}</div>
  </section>

  <section class="block">
    <div class="block-head"><h2>${esc(t(u.isKorean ? 'h.exchange' : 'h.room'))}</h2><a href="#/community">${esc(t('h.more'))}${icon('chev', 'sm')}</a></div>
    <div class="list">${posts.posts.map(postItem).join('')}</div>
  </section>

  ${infos.length ? `<section class="block">
    <div class="block-head"><h2>${esc(t('h.city'))}</h2><a href="#/news?tab=infos">${esc(t('h.more'))}${icon('chev', 'sm')}</a></div>
    <div class="list">${infos.map((i) => {
      const { title, sample } = splitSample(i.title);
      return `<a class="info-item" href="#/news?item=${i.id}">
      <span class="info-emo" aria-hidden="true">${esc(i.emoji || '📢')}</span>
      <span class="info-text"><b>${esc(title)}</b>
        <span class="chips">${i.forMe ? `<span class="chip brand">${esc(t('n.forMe'))}</span>` : `<span class="chip">${esc(t('n.kind.' + i.kind))}</span>`}${sampleChip(sample)}</span></span>
      ${icon('chev')}</a>`;
    }).join('')}</div>
  </section>` : ''}`;
}
