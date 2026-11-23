// 소식 — 행사(카드 · 지도 · 알림) / 안내(정책 · 공지, 주제별) / 시에 묻기(공식 Q&A). 내 언어로 보인다(공식글 5개 언어, 결정 R2-8).
import { api } from './api.js';
import { t, ago, dateLabel, timeOf } from './i18n.js';
import { S, loadNews, dongLabel, splitSample } from './store.js';
import { setTop } from './chrome.js';
import { esc, icon, openSheet, toast, emptyState } from './ui.js';
import { eventCard, dday } from './home.js';

const N = { tab: 'events', topic: '' };
const REMIND_KEY = 'ansan-neighbors-remind';

function reminded() {
  try { return JSON.parse(localStorage.getItem(REMIND_KEY) || '[]'); } catch { return []; }
}
function toggleRemind(id) {
  const list = reminded();
  const on = !list.includes(id);
  const next = on ? [...list, id] : list.filter((x) => x !== id);
  try { localStorage.setItem(REMIND_KEY, JSON.stringify(next)); } catch { /* 없음 */ }
  return on;
}

function openItem(item) {
  const isEvent = item.kind === 'event';
  const on = reminded().includes(item.id);
  const { title, sample } = splitSample(item.title);
  openSheet(`
    <div class="chips"><span class="chip ${item.forMe ? 'brand' : ''}">${esc(t('n.kind.' + item.kind))}</span>
      ${item.forMe ? `<span class="chip brand">${esc(t('n.forMe'))}</span>` : ''}
      ${item.topic && !isEvent ? `<span class="chip">${esc(t('topic.' + item.topic) !== 'topic.' + item.topic ? t('topic.' + item.topic) : item.topic)}</span>` : ''}
      ${sample ? `<span class="chip">${esc(t('n.sample'))}</span>` : ''}</div>
    <h2><span class="emo" aria-hidden="true">${esc(item.emoji || '')}</span> ${esc(title)}</h2>
    ${isEvent ? `<p class="meta">${icon('cal', 'sm')}${esc(dateLabel(item.date, { year: 'numeric', month: 'long', day: 'numeric', weekday: 'long' }))}${timeOf(item.date) ? ' ' + esc(timeOf(item.date)) : ''} · ${esc(dday(item.date))}</p>` : ''}
    ${item.dong ? `<p class="meta">${icon('pin', 'sm')}${esc(t('n.where'))}: ${esc(dongLabel(item.dong))}</p>` : ''}
    <div class="post-body">${esc(item.body).replace(/\n/g, '<br>')}</div>
    <div class="row wrap">
      ${item.dong ? `<a class="btn ghost" href="#/map?dong=${item.dong}">${icon('map')}${esc(t('n.onMap'))}</a>` : ''}
      ${isEvent ? `<button type="button" class="btn ${on ? 'primary' : 'ghost'}" data-remind>${icon('bell')}${esc(t(on ? 'n.reminded' : 'n.remind'))}</button>` : ''}
      ${item.link ? `<a class="btn ghost" target="_blank" rel="noopener" href="${esc(item.link)}">${icon('link')}${esc(t('n.source'))}</a>` : ''}
    </div>
    ${isEvent ? `<p class="fine">${esc(t('n.remindNote'))}</p>` : ''}`, {
    label: item.title,
    onMount: (body) => {
      body.addEventListener('click', (e) => {
        const b = e.target.closest('[data-remind]');
        if (!b) return;
        const now = toggleRemind(item.id);
        b.className = 'btn ' + (now ? 'primary' : 'ghost');
        b.innerHTML = `${icon('bell')}${esc(t(now ? 'n.reminded' : 'n.remind'))}`;
        toast(t(now ? 'n.reminded' : 'n.remind'));
      });
      // 닫으면 주소에서 item 을 지운다 — 같은 소식을 다시 눌러도 열리게
      return () => { if (location.hash.includes('item=')) history.replaceState(null, '', '#/news?tab=' + N.tab); };
    },
  });
}

function eventsTab(news) {
  if (!news.events.length && !news.pastEvents.length) return emptyState(t('n.empty'), 'cal');
  return `<div class="list">${news.events.map((e) => eventCard(e)).join('') || emptyState(t('n.empty'), 'cal')}</div>
    ${news.pastEvents.length ? `<details class="past"><summary>${esc(t('n.past'))} (${news.pastEvents.length})</summary>
      <div class="list">${news.pastEvents.map((e) => eventCard(e, true)).join('')}</div></details>` : ''}`;
}

function infosTab(news) {
  const topics = [...new Set(news.infos.map((i) => i.topic).filter(Boolean))];
  const items = news.infos.filter((i) => !N.topic || i.topic === N.topic);
  return `<div class="chip-row" role="toolbar">
      <button type="button" class="chip-btn${!N.topic ? ' on' : ''}" data-topic="">${esc(t('map.all'))}</button>
      ${topics.map((g) => `<button type="button" class="chip-btn${N.topic === g ? ' on' : ''}" data-topic="${esc(g)}">${esc(t('topic.' + g) !== 'topic.' + g ? t('topic.' + g) : g)}</button>`).join('')}
    </div>
    <div class="list">${items.map((i) => {
      const { title, sample } = splitSample(i.title);
      return `<a class="info-card" href="#/news?item=${i.id}">
      <div class="chips"><span class="chip ${i.kind === 'notice' ? 'warn' : ''}">${esc(t('n.kind.' + i.kind))}</span>${i.forMe ? `<span class="chip brand">${esc(t('n.forMe'))}</span>` : ''}${sample ? `<span class="chip">${esc(t('n.sample'))}</span>` : ''}</div>
      <h3><span class="emo" aria-hidden="true">${esc(i.emoji || '')}</span> ${esc(title)}</h3><p class="excerpt">${esc(i.body)}</p></a>`;
    }).join('') || emptyState(t('n.empty'))}</div>
    <p class="rules">${esc(t('n.cityOnly'))}</p>`;
}

function askTab(qs) {
  const mine = qs.filter((q) => q.mine);
  const others = qs.filter((q) => !q.mine);
  const card = (q) => `<li class="qa">
      <div class="bubble q">${q.mine ? `<span class="chip brand">${esc(t('q.mine'))}</span>` : ''}<b>${esc(q.title)}</b>${q.body ? `<p>${esc(q.body)}</p>` : ''}
        ${q.bodyKo && S.user.uiLang === 'ko' ? `<p class="tr">${icon('translate', 'sm')}${esc(q.bodyKo)}</p>` : ''}
        <span class="meta">${esc(ago(q.created))}</span></div>
      ${q.answer ? `<div class="bubble a"><span class="who">${icon('building', 'sm')}${esc(t('q.city'))}</span><p>${esc(q.answer)}</p></div>`
        : `<p class="pending">${icon('clock', 'sm')}${esc(t('q.pending'))}</p>`}
    </li>`;
  return `<form class="form ask" data-ask>
      <p class="meta">${esc(t('q.hint'))}</p>
      <label>${esc(t('q.title'))}<input name="title" maxlength="120" required placeholder="${esc(t('q.anyLang'))}"></label>
      <label>${esc(t('q.body'))}<textarea name="body" rows="3" maxlength="2000"></textarea></label>
      <button class="btn primary block" type="submit">${icon('send')}${esc(t('q.send'))}</button>
    </form>
    <ul class="qa-list">${mine.map(card).join('')}${others.map(card).join('')}</ul>`;
}

export async function render(view, r) {
  if (r.q.get('tab')) N.tab = r.q.get('tab');
  setTop(t('tab.news'));
  const news = await loadNews(true);
  const itemId = parseInt(r.q.get('item') || '', 10);
  const found = itemId ? [...news.events, ...news.pastEvents, ...news.infos].find((x) => x.id === itemId) : null;
  if (found) N.tab = found.kind === 'event' ? 'events' : 'infos';
  let body = '';
  if (N.tab === 'ask') body = askTab((await api('/api/questions')).questions);
  else if (N.tab === 'infos') body = infosTab(news);
  else body = eventsTab(news);
  view.innerHTML = `
    <div class="seg wide" role="tablist">
      ${['events', 'infos', 'ask'].map((k) => `<button type="button" role="tab" aria-selected="${N.tab === k}" class="${N.tab === k ? 'on' : ''}" data-tab="${k}">${esc(t('n.' + k))}</button>`).join('')}
    </div>
    ${body}`;
  view.onclick = (e) => {
    const b = e.target.closest('button');
    if (!b) return;
    if (b.dataset.tab) { N.tab = b.dataset.tab; history.replaceState(null, '', '#/news?tab=' + N.tab); render(view, { q: new URLSearchParams() }); }
    else if ('topic' in b.dataset) { N.topic = b.dataset.topic; render(view, { q: new URLSearchParams() }); }
  };
  view.onsubmit = async (e) => {
    if (!e.target.matches('[data-ask]')) return;
    e.preventDefault();
    const f = new FormData(e.target);
    try {
      await api('/api/questions', { method: 'POST', body: { title: f.get('title'), body: f.get('body') } });
      toast(t('q.sent'));
      render(view, { q: new URLSearchParams() });
    } catch { toast(t('err.generic')); }
  };
  if (found) openItem(found);
}
