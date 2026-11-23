// 생활 지도 — 실제 바탕지도(OpenStreetMap) 위에 ① 외국인 주민이 찾는 가게(공공 상가정보)
// ② '고향 사람 많은 곳'(시간대 슬라이더 → 동네 색, 통신 자료) ③ 이웃 제보. 표 · 순위는 두지 않는다(2026-11-20 사용자 요청).
import { api } from './api.js';
import { t, natName, hourLabel, dongName, dateLabel } from './i18n.js';
import { S, loadShops, loadPlaces, myCuisines, cuisineLabel, shopTypeLabel, dong, dongLabel, KIND_COLOR, KIND_ICON, KINDS, isSample } from './store.js';
import { $, esc, icon, openSheet, closeSheet, toast } from './ui.js';

const L = window.L;
// 단계별 색 — 1단계('적음')와 가린 동네는 칠하지 않고, 2~4단계만 dataviz 순차 파랑 300 · 450 · 700.
// 회색 바탕지도(#e9ece9) 기준 순서형 검사 통과(밝은 끝 2.10:1). 많은 곳만 눈에 띄게 하려는 것(2026-11-20).
const LEVEL_COLOR = [null, null, '#6da7ec', '#2a78d6', '#0d366b'];
const ANSAN = { center: [37.3195, 126.8125], zoom: 13 };

const M = {
  map: null, cluster: null, dongLayer: null, geo: null, pickPin: null, labels: null,
  kind: 'all', mine: false, query: '',
  people: false, presence: null, presenceEmpty: false, daytype: null, hour: null, timer: null,
  cells: null, holidays: [], hexLayer: null, hexPolys: null,
  highlight: null, userId: null,
};

function nowSlot() {
  const d = new Date();
  return { daytype: d.getDay() === 0 || d.getDay() === 6 ? '주말' : '평일', hour: d.getHours() };
}

// ------------------------------------------------------------------ 틀
function frame(root) {
  root.innerHTML = `
  <div id="leaflet" class="leaflet-host" role="application" aria-label="${esc(t('tab.map'))}"></div>
  <div class="map-top">
    <label class="search map-search">${icon('search')}<input type="search" data-q placeholder="${esc(t('map.search'))}" aria-label="${esc(t('map.search'))}" autocomplete="off"></label>
    <div class="search-results" hidden></div>
    <div class="chip-row" role="toolbar"></div>
  </div>
  <div class="map-fabs">
    <button type="button" class="fab-mini" data-act="locate" aria-label="안산">${icon('target')}</button>
  </div>
  <button type="button" class="fab" data-act="add">${icon('plus')}<span>${esc(t('map.add'))}</span></button>
  <div class="people-panel" hidden></div>
  <div class="pick-overlay" hidden>
    <div class="pick-cross">${icon('pin')}</div>
    <div class="pick-bar"><p>${esc(t('map.addPick'))}</p>
      <div class="row"><button type="button" class="btn ghost" data-act="pick-cancel">${esc(t('cancel'))}</button>
      <button type="button" class="btn primary" data-act="pick-ok">${esc(t('map.addHere'))}</button></div></div>
  </div>`;
}

// 언어를 바꾸거나 계정을 바꿔도 틀의 글이 남지 않게 매번 다시 쓴다
function frameTexts(root) {
  const q = $('[data-q]', root);
  q.placeholder = t('map.search');
  q.setAttribute('aria-label', t('map.search'));
  $('#leaflet', root).setAttribute('aria-label', t('tab.map'));
  $('.fab span', root).textContent = t('map.add');
  $('.pick-bar p', root).textContent = t('map.addPick');
  $('[data-act="pick-cancel"]', root).textContent = t('cancel');
  $('[data-act="pick-ok"]', root).textContent = t('map.addHere');
}

function chipRow(root) {
  const cu = myCuisines();
  // 핀이 하나도 없는 종류는 단추를 두지 않는다(생활 서비스는 확인 목록이 생기기 전까지 비어 있다 — 2026-11-20)
  const have = new Set((S.shops ? S.shops.shops : []).map((s) => s.kind));
  const kinds = ['all', ...KINDS.filter((k) => k === 'community' || have.has(k))];
  const chips = kinds.map((k) => `<button type="button" class="chip-btn${M.kind === k ? ' on' : ''}" data-kind="${k}"
      ${k !== 'all' ? `style="--k:${KIND_COLOR[k]}"` : ''}>${k !== 'all' ? `<i class="dot ${k}"></i>` : ''}${esc(k === 'all' ? t('map.all') : t('kind.' + k))}</button>`);
  if (cu.length) chips.splice(1, 0, `<button type="button" class="chip-btn star${M.mine ? ' on' : ''}" data-mine aria-pressed="${M.mine}">${icon('star')}${esc(t('map.mine'))}</button>`);
  if (!S.user.isKorean) chips.splice(1, 0, `<button type="button" class="chip-btn people${M.people ? ' on' : ''}" data-people aria-pressed="${M.people}">${icon('users')}${esc(t('map.people'))}</button>`);
  $('.chip-row', root).innerHTML = chips.join('');
}

// ------------------------------------------------------------------ 가게 핀
function pinIcon(kind, extra = '') {
  return L.divIcon({
    className: 'pin-wrap',
    html: `<span class="pin ${kind}${extra}" style="--k:${KIND_COLOR[kind] || '#555'}">${icon(KIND_ICON[kind] || 'pin')}</span>`,
    iconSize: [30, 30], iconAnchor: [15, 15],
  });
}

function visibleShops() {
  const cu = myCuisines();
  const q = M.query.trim().toLowerCase();
  const shops = (S.shops ? S.shops.shops : []).filter((s) => {
    if (M.kind !== 'all' && M.kind !== 'community' && s.kind !== M.kind) return false;
    if (M.kind === 'community') return false;
    if (M.mine && !(cu.includes(s.cuisine) || s.cuisine === 'world' || s.kind === 'official')) return false;
    return !q || s.name.toLowerCase().includes(q);
  });
  const places = (M.kind === 'all' || M.kind === 'community') && !M.mine
    ? (S.places || []).filter((p) => !q || p.name.toLowerCase().includes(q)).map((p) => ({ ...p, id: 'p' + p.id, pid: p.id, kind: 'community', placeKind: p.kind }))
    : [];
  return shops.concat(places);
}

function drawPins() {
  if (!M.map) return;
  if (M.cluster) M.map.removeLayer(M.cluster);
  // '고향 사람 많은 곳'을 볼 때는 동네 색만 — 핀이 색을 가린다. 골목 칸까지 키우면 내 나라 가게 핀만 칸 위에 올린다
  // (고향 사람이 많이 다니는 골목의 가게가 한눈에 — 2026-11-20 사용자: "고향 사람 다니는 쪽으로")
  if (M.people && !M.pinsCells) { M.cluster = null; return; }
  const onlyMine = M.people && M.pinsCells;
  const cu = myCuisines();
  M.cluster = L.markerClusterGroup({
    showCoverageOnHover: false, maxClusterRadius: 46, spiderfyOnMaxZoom: true, disableClusteringAtZoom: 18,
    iconCreateFunction: (c) => L.divIcon({ className: 'cluster-wrap', html: `<span class="cluster">${c.getChildCount()}</span>`, iconSize: [36, 36] }),
  });
  for (const s of visibleShops()) {
    if (onlyMine && !cu.includes(s.cuisine)) continue;
    const m = L.marker([s.lat, s.lon], { icon: pinIcon(s.kind, s.verified ? ' verified' : ''), title: s.name, keyboard: true });
    m.on('click', () => openShop(s));
    M.cluster.addLayer(m);
  }
  M.map.addLayer(M.cluster);
}

// ------------------------------------------------------------------ 가게 시트
function routeLinks(s) {
  const name = encodeURIComponent(s.name);
  return `<a class="btn ghost sm" target="_blank" rel="noopener" href="https://map.kakao.com/link/to/${name},${s.lat},${s.lon}">${icon('route')}${esc(t('shop.route'))} · Kakao</a>
          <a class="btn ghost sm" target="_blank" rel="noopener" href="https://www.google.com/maps/dir/?api=1&destination=${s.lat},${s.lon}">Google</a>`;
}

export function openShop(s) {
  const community = s.kind === 'community';
  const typeLine = community ? `${t('kind.community')}${s.placeKind && s.placeKind !== 'other' ? ' · ' + t('kind.' + s.placeKind) : ''}` : shopTypeLabel(s);
  const cuisine = cuisineLabel(s.cuisine);
  const basis = community ? t('shop.community') : (t('shop.b.' + s.basis) !== 'shop.b.' + s.basis ? t('shop.b.' + s.basis) : '');
  const floor = s.floor ? ' · ' + t('shop.floor', { f: s.floor }) : '';
  openSheet(`
    <div class="shop-head">
      <span class="shop-dot big" style="--k:${KIND_COLOR[s.kind]}">${icon(KIND_ICON[s.kind] || 'pin')}</span>
      <div><h2>${esc(s.name)}</h2>
      <p class="meta">${esc(typeLine)}${cuisine ? ' · ' + esc(cuisine) : ''}</p></div>
    </div>
    ${s.addr ? `<p class="addr">${icon('pin', 'sm')}${esc(s.addr)}${esc(floor)}</p>` : `<p class="addr">${icon('pin', 'sm')}${esc(dongLabel(s.dong))}</p>`}
    <div class="row wrap">${routeLinks(s)}</div>
    <div class="row">
      <button type="button" class="btn like${s.voted ? ' on' : ''}" data-act="like">${icon('thumb')}<span>${esc(t('shop.like'))}</span><b data-votes>${s.votes || 0}</b></button>
      ${!community && s.kind !== 'official' ? `<button type="button" class="btn ghost" data-act="wrong">${icon('flag')}${esc(t('shop.wrong'))}</button>` : ''}
    </div>
    ${s.verified ? `<p class="chip ok">${icon('check')}${esc(t('shop.verified'))}</p>` : ''}
    ${s.near ? `<p class="near-line">👥 ${esc(t(s.near === 'cell' ? 'shop.nearLine' : 'shop.nearLineDong'))}${isSample() ? ' · ' + esc(t('n.sample')) : ''}</p>` : ''}
    ${s.checked ? `<p class="checked-line">${icon('check', 'sm')}${esc(t(s.checkSrc === 'field' ? 'shop.checkedField' : 'shop.checked', { date: s.checked }))}</p>` : ''}
    <div class="fine">
      ${cuisine ? `<p>${esc(t('shop.cuisineNote'))}</p>` : ''}
      ${basis ? `<p>${esc(basis)}</p>` : ''}
      ${!community && s.kind !== 'official' && !s.checked ? `<p>${esc(t('shop.source', { date: S.shops.date }))}</p>` : ''}
    </div>
    <div class="wrong-box" hidden>
      <p class="label">${esc(t('shop.wrong'))}</p>
      <div class="row wrap">${S.boot.shopFeedback.map((r) => `<button type="button" class="chip-btn" data-reason="${r}">${esc(t('shop.r.' + r))}</button>`).join('')}</div>
    </div>`, {
    label: s.name,
    onMount: (body) => {
      body.addEventListener('click', async (e) => {
        const b = e.target.closest('button');
        if (!b) return;
        try {
          if (b.dataset.act === 'like') {
            if (community) {
              const res = await api(`/api/places/${s.pid}/vote`, { method: 'POST' });
              s.votes = res.votes; s.voted = true; b.classList.add('on');
              $('[data-votes]', b).textContent = res.votes;
              loadPlaces(true);
            } else {
              const res = await api(`/api/shops/${encodeURIComponent(s.id)}/vote`, { method: 'POST' });
              s.votes = res.votes; s.voted = res.voted; b.classList.toggle('on', res.voted);
              $('[data-votes]', b).textContent = res.votes;
            }
          } else if (b.dataset.act === 'wrong') {
            $('.wrong-box', body).hidden = false;
          } else if (b.dataset.reason) {
            await api(`/api/shops/${encodeURIComponent(s.id)}/feedback`, { method: 'POST', body: { reason: b.dataset.reason } });
            toast(t('shop.thanks'));
            closeSheet();
          }
        } catch (err) { toast(err.code === 'network' ? t('err.network') : t('err.generic')); }
      });
    },
  });
}

// ------------------------------------------------------------------ 고향 사람 많은 곳
// 2026-11-20 사용자 질문 "3번째는 뭘 표현한 거지?" → 화면만 봐도 읽히게 바꿨다:
// 제목 문장(언제 · 누가 많은 곳), 많은 동네 이름 단추, 지도 위 동네 이름표, 시간대 풀이 한 줄, '적음 → 많음' 범례, ? 설명.
const slotNow = () => (M.presence && M.presence[M.daytype] ? M.presence[M.daytype][M.hour] : {});
const dayWord = (d) => t(d === '주말' ? 'map.weekend' : d === '연휴' ? 'map.holiday' : 'map.weekday');
const timeText = () => `${dayWord(M.daytype)} ${hourLabel(M.hour)}`;

// 골목 칸(육각, ≈H3 res9 · 약 330m) — 동네를 키워 볼 때만. 실데이터 판 · 50m 표에 있는 국적만(2026-11-20).
// 연휴는 50m 표에 날짜 구분이 없어 동 단위로만 본다.
const CELL_ZOOM = 14;
const zoomedIn = () => !!(M.map && M.map.getZoom() >= CELL_ZOOM);
const cellsShown = () => !!(M.people && M.cells && M.cells.usable && M.cells.hex.length && M.daytype !== '연휴' && zoomedIn());

function dongStyle(feature) {
  const code = feature.properties.code;
  const hl = M.highlight === code;
  if (!M.people || !M.presence) {
    return { color: hl ? '#0b7a66' : '#5c6b66', weight: hl ? 3 : 0.8, opacity: hl ? 0.95 : 0.35, fill: true, fillColor: '#0b7a66', fillOpacity: hl ? 0.08 : 0, dashArray: null };
  }
  if (cellsShown()) {     // 골목 칸을 볼 때 동네는 테두리만 — 칸 색이 가려지지 않게
    return { color: hl ? '#13201c' : '#5c6b66', weight: hl ? 3 : 1.2, opacity: hl ? 0.95 : 0.6, fill: true, fillColor: '#ffffff', fillOpacity: 0.01, dashArray: null };
  }
  const lv = slotNow()[code];
  return lv >= 2
    ? { color: hl ? '#13201c' : '#ffffff', weight: hl ? 3 : 1, opacity: 0.95, fill: true, fillColor: LEVEL_COLOR[lv], fillOpacity: 0.72, dashArray: null }
    : { color: hl ? '#13201c' : '#7d8885', weight: hl ? 3 : 0.9, opacity: hl ? 0.95 : 0.55, fill: true, fillColor: '#ffffff', fillOpacity: 0.01, dashArray: null };
}

function levelOf(code) {
  if (!M.people || !M.presence) return null;
  return slotNow()[code];
}

// 시간대 풀이 — 통신 자료의 흔한 모양(밤 = 사는 곳, 평일 낮 = 일터, 주말 낮 = 모이는 곳)을 한 줄로
function tipKey(day, h) {
  if (h >= 22 || h < 6) return 'map.tipHome';
  if (day === '연휴' && h >= 9 && h < 21) return 'map.tipHoliday';
  if (day === '평일' && h >= 9 && h < 18) return 'map.tipWork';
  if (day === '주말' && h >= 10 && h < 20) return 'map.tipMeet';
  return 'map.tipAny';
}

// 지금 고른 시간에 '많음' 이상인 동네(많은 단계 먼저, 같은 단계는 이름순) — 순위표가 아니라 '어디로 가면 되나'의 답
function topDongs(max = 4) {
  return Object.entries(slotNow()).filter(([, lv]) => lv >= 3)
    .sort((a, b) => b[1] - a[1] || dongLabel(a[0], true).localeCompare(dongLabel(b[0], true)))
    .slice(0, max);
}

const legendBar = () => `<span>${esc(t('map.few'))}</span>${[1, 2, 3, 4].map((lv) => `<i class="lv${lv}"${LEVEL_COLOR[lv] ? ` style="background:${LEVEL_COLOR[lv]}"` : ''}></i>`).join('')}<span>${esc(t('map.many'))}</span>`;

function openDong(code) {
  const d = dong(code);
  if (!d) return;
  const shops = (S.shops ? S.shops.shops : []).filter((s) => s.dong === code);
  const lv = levelOf(code);
  const nat = natName(S.user.nationality);
  openSheet(`
    <h2>${esc(dongName(d.name))}</h2>
    ${M.people && M.presence ? `<p class="level-line">${lv >= 2 ? `<i class="swatch" style="background:${LEVEL_COLOR[lv]}"></i>` : '<i class="swatch none"></i>'}
      ${esc(t('map.nowLevel', { time: timeText(), nat, lv: lv ? t('lv.' + lv) : t('lv.none') }))}</p>` : ''}
    <div class="row wrap">
      <button type="button" class="btn ghost" data-act="shops">${icon('bowl')}${esc(t('map.dongShops', { n: shops.length }))}</button>
      <a class="btn ghost" href="#/community?dong=${code}">${icon('chat')}${esc(t('map.dongPosts'))}</a>
    </div>`, {
    label: d.name,
    onMount: (body) => {
      body.addEventListener('click', (e) => {
        if (e.target.closest('[data-act="shops"]')) {
          closeSheet();
          if (M.people) setPeople($('#mapview'), false);
          M.highlight = code;
          paintDongs();
          const b = M.geo && M.dongLayer ? M.dongLayer.getLayers().find((l) => l.feature.properties.code === code) : null;
          if (b) M.map.fitBounds(b.getBounds(), { padding: [30, 30] });
        }
      });
    },
  });
}

function peopleInfo() {
  const nat = natName(S.user.nationality);
  openSheet(`
    <h2>${esc(t('map.ppHelp'))}</h2>
    <div class="pp-info">
      <p>${esc(t('map.ppInfo1', { nat }))}</p>
      <div class="pp-legend">${legendBar()}</div>
      <p>${esc(t('map.ppInfo2'))}</p>
      ${M.holidays.length ? `<p>${esc(t('map.ppInfoHoliday', { days: M.holidays.map((d) => dateLabel(`${d.slice(0, 4)}-${d.slice(4, 6)}-${d.slice(6, 8)}`, { month: 'short', day: 'numeric' })).join(', ') }))}</p>` : ''}
      ${M.cells && M.cells.usable ? `<p>${esc(t('map.ppInfoCells'))}</p>` : ''}
      <p class="fine-line">${icon('shield', 'sm')}<span>${esc(t('map.ppInfo3'))}</span></p>
      <p class="fine-line"><b class="${isSample() ? 'sample' : 'internal'}">${esc(t(isSample() ? 'me.dSample' : 'map.internal', { month: S.boot.dataMonth }))}</b></p>
    </div>`, { label: t('map.ppHelp') });
}

function peoplePanel(root) {
  const p = $('.people-panel', root);
  if (!M.people) { p.hidden = true; return; }
  p.hidden = false;
  if (!M.presence) { p.innerHTML = `<p class="loading">${esc(t('loading'))}</p>`; return; }
  const nat = natName(S.user.nationality);
  const empty = M.presenceEmpty;
  p.innerHTML = `
    <div class="pp-title">
      <div><p class="pp-when" aria-live="polite"></p><h2 class="pp-what">${esc(t('map.ppWhat', { nat }))}</h2></div>
      <button type="button" class="icon-btn" data-act="people-info" aria-label="${esc(t('map.ppHelp'))}">${icon('help')}</button>
    </div>
    ${empty ? `<p class="note">${esc(t('map.peopleEmpty'))}</p>` : '<div class="pp-top" data-top></div><p class="pp-tip" data-tip></p><p class="pp-cellnote" data-cellnote hidden></p>'}
    <div class="pp-ctrl">
      <div class="seg" role="tablist">
        ${['평일', '주말', ...(M.presence['연휴'] ? ['연휴'] : [])].map((d) => `<button type="button" role="tab" aria-selected="${M.daytype === d}" class="${M.daytype === d ? 'on' : ''}" data-day="${d}">${esc(dayWord(d))}</button>`).join('')}
      </div>
      <button type="button" class="icon-btn play" data-act="play" aria-label="${esc(t(M.timer ? 'map.stop' : 'map.play'))}">${icon(M.timer ? 'pause' : 'play')}</button>
    </div>
    <input type="range" min="0" max="23" step="1" value="${M.hour}" data-hour aria-label="${esc(t('map.people'))}">
    <div class="ticks" aria-hidden="true"><span>${esc(hourLabel(0))}</span><span>${esc(hourLabel(6))}</span><span>${esc(hourLabel(12))}</span><span>${esc(hourLabel(18))}</span><span>${esc(hourLabel(23))}</span></div>
    ${empty ? '' : `<div class="pp-legend">${legendBar()}<b class="${isSample() ? 'sample' : 'internal'}">${esc(t(isSample() ? 'map.sample' : 'map.internal', { month: S.boot.dataMonth }))}</b></div>`}`;
  peopleTexts(p);
}

// 시간을 옮길 때마다 바뀌는 글 — 패널을 다시 그리지 않아 슬라이더를 끄는 손이 끊기지 않는다
function peopleTexts(p = $('.people-panel')) {
  if (!p || p.hidden || !M.presence) return;
  const now = nowSlot();
  const when = $('.pp-when', p);
  if (when) when.innerHTML = `${now.daytype === M.daytype && now.hour === M.hour ? `<span class="now">${esc(t('map.now'))}</span>` : ''}${esc(timeText())}`;
  const top = $('[data-top]', p);
  if (top) {
    const list = topDongs();
    top.innerHTML = list.length
      ? list.map(([code, lv]) => `<button type="button" data-dong="${code}"><i style="background:${LEVEL_COLOR[lv]}"></i>${esc(dongLabel(code, true))}</button>`).join('')
      : `<span class="none">${esc(t('map.ppNone'))}</span>`;
  }
  const tip = $('[data-tip]', p);
  if (tip) tip.textContent = t(tipKey(M.daytype, M.hour));
  const cn = $('[data-cellnote]', p);
  if (cn) {
    let key = '';
    if (M.cells && M.cells.usable) key = M.daytype === '연휴' ? (zoomedIn() ? 'map.cellsHoliday' : '') : (zoomedIn() ? 'map.cellsOn' : 'map.cellsHint');
    else if (M.cells && zoomedIn()) key = 'map.cellsNone';
    cn.hidden = !key;
    cn.textContent = key ? t(key) : '';
  }
  const range = $('[data-hour]', p);
  if (range) {
    if (+range.value !== M.hour) range.value = M.hour;
    range.setAttribute('aria-valuetext', timeText());
  }
}

// 지도 위 동네 이름표 — '많음' 이상인 동네에만. 붙어 있는 작은 동네끼리 이름표가 겹치면 진한 쪽만 단다
// (빠진 이름은 아래 단추에 다 있고, 지도를 키우면 다시 계산해 붙는다).
let measureCtx = null;
function labelWidth(text) {
  if (!measureCtx) {
    measureCtx = document.createElement('canvas').getContext('2d');
    measureCtx.font = '800 12px system-ui, "Segoe UI", "Malgun Gothic", "Apple SD Gothic Neo", sans-serif';
  }
  return measureCtx.measureText(text).width + 16;
}

function drawLabels() {
  if (!M.map) return;
  if (!M.labels) M.labels = L.layerGroup().addTo(M.map);
  M.labels.clearLayers();
  if (!M.people || !M.presence) return;
  const placed = [];
  const hits = (a) => placed.some((b) => a.x1 < b.x2 && a.x2 > b.x1 && a.y1 < b.y2 && a.y2 > b.y1);
  for (const [code, lv] of Object.entries(slotNow()).filter(([, v]) => v >= 3).sort((a, b) => b[1] - a[1])) {
    const d = dong(code);
    if (!d) continue;
    const name = dongName(d.name, true);
    const pt = M.map.latLngToContainerPoint([d.lat, d.lon]);
    const half = labelWidth(name) / 2;
    const box = { x1: pt.x - half - 2, x2: pt.x + half + 2, y1: pt.y - 12, y2: pt.y + 12 };
    if (hits(box)) continue;
    placed.push(box);
    M.labels.addLayer(L.marker([d.lat, d.lon], {
      icon: L.divIcon({ className: 'dong-tag-wrap', html: `<span class="dong-tag lv${lv}">${esc(name)}</span>`, iconSize: [0, 0] }),
      interactive: false, keyboard: false,
    }));
  }
}

// 골목 칸 — 칸 모양은 국적마다 한 번 만들고, 시각을 옮길 때는 색만 바꾼다(재생 중에도 가볍게)
function drawCells() {
  if (!M.map) return;
  if (!M.hexLayer) M.hexLayer = L.layerGroup().addTo(M.map);
  if (!cellsShown()) {
    if (M.hexPolys) { M.hexLayer.clearLayers(); M.hexPolys = null; }
    return;
  }
  if (!M.hexPolys) {
    // 칸 사이 선은 긋지 않는다 — 벌집 격자가 아니라 '많은 쪽'이 부드러운 색 덩어리로 보이게(2026-11-20 "격자가 대놓고 나와?")
    M.hexPolys = M.cells.hex.map(([, pts]) => L.polygon(pts, { interactive: false, stroke: false, fill: true, fillOpacity: 0 }));
    M.hexPolys.forEach((poly) => M.hexLayer.addLayer(poly));
  }
  const lv = M.cells.levels[M.daytype][M.hour];
  M.hexPolys.forEach((poly, i) => {
    const v = lv[i];
    poly.setStyle(v >= 2 ? { fillColor: LEVEL_COLOR[v], fillOpacity: 0.6 } : { fillOpacity: 0 });
  });
}

function paintDongs() {
  if (M.dongLayer) M.dongLayer.setStyle(dongStyle);
  drawCells();
  const want = cellsShown();          // 골목 칸을 볼 때만 내 나라 가게 핀을 올린다 — 바뀔 때만 다시 그린다
  if (want !== !!M.pinsCells) { M.pinsCells = want; drawPins(); }
  drawLabels();
  peopleTexts();
}

function focusDong(root, code) {
  const l = M.dongLayer && M.dongLayer.getLayers().find((x) => x.feature.properties.code === code);
  if (!l) return;
  M.highlight = code;
  paintDongs();
  const panel = $('.people-panel', root);
  const bottom = panel && !panel.hidden ? panel.offsetHeight + 16 : 20;
  if (M.cells && M.cells.usable && M.daytype !== '연휴') {
    // 골목 칸이 보이는 배율까지 바로 키운다 — 동 가운데를 검색창과 아래 패널 사이 빈 곳에 둔다
    const z = Math.min(15, Math.max(CELL_ZOOM, M.map.getBoundsZoom(l.getBounds(), false, L.point(48, 130 + bottom))));
    const p = M.map.project(l.getBounds().getCenter(), z).add([0, (bottom - 130) / 2]);
    M.map.setView(M.map.unproject(p, z), z);
  } else {
    M.map.fitBounds(l.getBounds(), { paddingTopLeft: [24, 130], paddingBottomRight: [24, bottom], maxZoom: 15 });
  }
  openDong(code);
}

async function ensurePresence(root) {
  if (M.presence || S.user.isKorean) return;
  const res = await api('/api/presence');
  M.presence = res.levels;
  M.presenceEmpty = res.empty;
  M.holidays = res.holidays || [];
  M.cells = res.cells || null;
  if (M.hexLayer) M.hexLayer.clearLayers();
  M.hexPolys = null;
  if (!M.presence[M.daytype]) M.daytype = '평일';
  peoplePanel(root);
  paintDongs();
}

function fitCity(root) {
  if (!M.dongLayer) return;
  // 섬 지역(대부동)을 빼고 시가지에 맞춘다 — 아래 시간 패널에 가리지 않게
  const city = L.featureGroup(M.dongLayer.getLayers().filter((l) => l.feature.properties.code !== '41273610'));
  const panel = $('.people-panel', root);
  const bottom = panel && !panel.hidden ? panel.offsetHeight + 16 : 20;
  M.map.fitBounds(city.getBounds(), { paddingTopLeft: [8, 120], paddingBottomRight: [8, bottom] });
}

function setPeople(root, on) {
  M.people = on;
  M.highlight = null;
  document.body.classList.toggle('people-on', on);
  if (!on && M.timer) { clearInterval(M.timer); M.timer = null; }
  chipRow(root);
  peoplePanel(root);
  paintDongs();
  drawPins();
  if (on) {
    ensurePresence(root).then(() => fitCity(root)).catch(() => toast(t('err.generic')));
  }
}

// ------------------------------------------------------------------ 장소 제보
function startPick(root) {
  closeSheet();
  $('.pick-overlay', root).hidden = false;
  document.body.classList.add('picking');
}
function endPick(root) {
  $('.pick-overlay', root).hidden = true;
  document.body.classList.remove('picking');
}
function addForm(root, center) {
  const cuisines = ['cn', 'vn', 'th', 'id', 'ph', 'kh', 'mm', 'np', 'lk', 'ca', 'mn', 'halal', 'world'];
  openSheet(`
    <h2>${esc(t('map.add'))}</h2>
    <form class="form" data-form>
      <label>${esc(t('map.addName'))}<input name="name" maxlength="60" required autofocus></label>
      <fieldset><legend>${esc(t('map.addKind'))}</legend><div class="row wrap">
        ${['food', 'grocery', 'service', 'other'].map((k, i) => `<label class="radio-chip"><input type="radio" name="kind" value="${k}" ${i === 0 ? 'checked' : ''}><span>${esc(t('kind.' + k))}</span></label>`).join('')}
      </div></fieldset>
      <label>${esc(t('map.addCuisine'))}<select name="cuisine"><option value="">—</option>
        ${cuisines.map((c) => `<option value="${c}" ${myCuisines()[0] === c ? 'selected' : ''}>${esc(t('cu.' + c))}</option>`).join('')}</select></label>
      <button class="btn primary block" type="submit">${esc(t('map.addSend'))}</button>
    </form>`, {
    label: t('map.add'),
    onMount: (body) => {
      $('[data-form]', body).addEventListener('submit', async (e) => {
        e.preventDefault();
        const f = new FormData(e.target);
        try {
          await api('/api/places', { method: 'POST', body: { name: f.get('name'), kind: f.get('kind'), cuisine: f.get('cuisine'), lon: center.lng, lat: center.lat } });
          toast(t('map.addDone', { n: S.boot.placeVerify }));
          closeSheet();
          await loadPlaces(true);
          drawPins();
        } catch (err) {
          toast(err.code === 'outside_ansan' ? t('map.outside') : t('err.generic'));
        }
      });
    },
  });
}

// ------------------------------------------------------------------ 검색
function searchResults(root) {
  const box = $('.search-results', root);
  const q = M.query.trim();
  if (!q) { box.hidden = true; box.innerHTML = ''; return; }
  const hits = visibleShops().slice(0, 8);
  box.hidden = false;
  box.innerHTML = hits.length ? hits.map((s, i) => `<button type="button" data-hit="${i}"><b>${esc(s.name)}</b><small>${esc(cuisineLabel(s.cuisine) || shopTypeLabel(s))} · ${esc(dongLabel(s.dong, true))}</small></button>`).join('')
    : `<p class="meta">${esc(t('map.noResult'))}</p>`;
  box.onclick = (e) => {
    const b = e.target.closest('[data-hit]');
    if (!b) return;
    const s = hits[+b.dataset.hit];
    box.hidden = true;
    focusShop(s);
  };
}

function focusShop(s) {
  M.map.setView([s.lat, s.lon], 18);
  setTimeout(() => openShop(s), 250);
}

// ------------------------------------------------------------------ 그리기
function initMap(root) {
  M.map = L.map($('#leaflet', root), { zoomControl: false, attributionControl: true, minZoom: 10, maxZoom: 19, zoomSnap: 0.25, zoomDelta: 0.5,
    maxBounds: [[37.12, 126.45], [37.45, 127.0]] }).setView(ANSAN.center, ANSAN.zoom);
  L.control.zoom({ position: 'bottomleft' }).addTo(M.map);
  L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19, attribution: '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a>',
  }).addTo(M.map);
  M.map.attributionControl.setPrefix(false);
  M.map.on('zoomend', () => {
    document.body.classList.toggle('zoom-far', M.map.getZoom() < 13);
    if (M.people) paintDongs();      // 확대하면 겹쳐서 빠졌던 이름표가 붙고, 골목 칸(육각)으로 바뀐다
  });
}

async function ensureGeo() {
  if (M.geo) return;
  M.geo = await api('/api/geo/dongs');
  M.dongLayer = L.geoJSON(M.geo, {
    style: dongStyle,
    onEachFeature: (f, layer) => {
      layer.on('click', () => { if (!document.body.classList.contains('picking')) openDong(f.properties.code); });
    },
  }).addTo(M.map);
  M.dongLayer.bringToBack();
}

export async function render(root, r) {
  const first = !M.map;
  if (first) {
    frame(root);
    initMap(root);
    const slot = nowSlot();
    M.daytype = slot.daytype; M.hour = slot.hour;
    bind(root);
  }
  if (M.userId !== S.user.id) {      // 계정을 바꾸면 앞 사람의 국적 · 필터를 지운다
    M.userId = S.user.id; M.presence = null; M.presenceEmpty = false; M.mine = false; M.kind = 'all'; M.query = '';
    $('[data-q]', root).value = '';
    if (M.people) setPeople(root, false);
    M.map.setView(ANSAN.center, ANSAN.zoom);
  }
  frameTexts(root);
  chipRow(root);
  setTimeout(() => M.map.invalidateSize(), 0);
  await Promise.all([loadShops(), loadPlaces(), ensureGeo()]);
  // 다른 화면에서 넘어온 요청: ?shop= · ?dong= · ?people=1 · ?mine=1
  if (r.q.get('mine') === '1') M.mine = true;
  M.highlight = r.q.get('dong') || null;
  drawPins();
  chipRow(root);
  if (r.q.get('people') === '1' && !S.user.isKorean) setPeople(root, true);
  else { peoplePanel(root); paintDongs(); }
  const sid = r.q.get('shop');
  if (sid) {
    const s = (S.shops.shops || []).find((x) => x.id === sid);
    if (s) focusShop(s);
  } else if (M.highlight) {
    const l = M.dongLayer.getLayers().find((x) => x.feature.properties.code === M.highlight);
    if (l) M.map.fitBounds(l.getBounds(), { padding: [40, 40] });
  }
}

function bind(root) {
  root.addEventListener('click', (e) => {
    const b = e.target.closest('button');
    if (!b) return;
    if (b.dataset.kind) { M.kind = b.dataset.kind; chipRow(root); drawPins(); }
    else if ('mine' in b.dataset) { M.mine = !M.mine; chipRow(root); drawPins(); }
    else if ('people' in b.dataset) setPeople(root, !M.people);
    else if (b.dataset.day) { M.daytype = b.dataset.day; peoplePanel(root); paintDongs(); }
    else if (b.dataset.dong) focusDong(root, b.dataset.dong);
    else if (b.dataset.act === 'people-info') peopleInfo();
    else if (b.dataset.act === 'play') {
      if (M.timer) { clearInterval(M.timer); M.timer = null; }
      else {
        M.timer = setInterval(() => {
          M.hour = (M.hour + 1) % 24;
          const range = $('[data-hour]', root);
          if (range) range.value = M.hour;
          paintDongs();
        }, 900);
      }
      peoplePanel(root);
    } else if (b.dataset.act === 'locate') {
      const me = dong(S.user.dong);
      M.map.setView(me ? [me.lat, me.lon] : ANSAN.center, me ? 15 : ANSAN.zoom);
    } else if (b.dataset.act === 'add') startPick(root);
    else if (b.dataset.act === 'pick-cancel') endPick(root);
    else if (b.dataset.act === 'pick-ok') { const c = M.map.getCenter(); endPick(root); addForm(root, c); }
  });
  root.addEventListener('input', (e) => {
    if (e.target.matches('[data-hour]')) { M.hour = +e.target.value; paintDongs(); }
    else if (e.target.matches('[data-q]')) { M.query = e.target.value; searchResults(root); drawPins(); }
  });
  window.addEventListener('hashchange', () => {
    if (!location.hash.startsWith('#/map') && M.timer) { clearInterval(M.timer); M.timer = null; }
  });
}

