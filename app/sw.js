// 안산 이웃 — 서비스 워커. 앱 틀(화면 코드 · 아이콘 · 지도 라이브러리)만 저장해 두고 빨리 연다.
// /api 응답과 지도 타일은 저장하지 않는다(늘 새로 받음 · 실데이터 판의 응답이 기기에 남지 않게).
const CACHE = 'ansan-neighbors-v3';
const SHELL = [
  './', './index.html', './css/app.css', './manifest.webmanifest',
  './js/main.js', './js/api.js', './js/i18n.js', './js/ui.js', './js/store.js', './js/chrome.js',
  './js/welcome.js', './js/home.js', './js/map.js', './js/community.js', './js/news.js', './js/me.js',
  './vendor/leaflet.js', './vendor/leaflet.css', './vendor/leaflet.markercluster.js', './vendor/MarkerCluster.css',
  './icons/icon-192.png', './icons/icon-512.png',
];

self.addEventListener('install', (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting()));
});
self.addEventListener('activate', (e) => {
  e.waitUntil(caches.keys().then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
    .then(() => self.clients.claim()));
});
self.addEventListener('fetch', (e) => {
  const url = new URL(e.request.url);
  if (e.request.method !== 'GET' || url.origin !== location.origin || url.pathname.startsWith('/api/')) return;
  // 화면 코드는 새것을 먼저 받고(고친 내용이 바로 보이게), 연결이 없으면 저장본
  e.respondWith(fetch(e.request).then((res) => {
    const copy = res.clone();
    caches.open(CACHE).then((c) => c.put(e.request, copy));
    return res;
  }).catch(() => caches.match(e.request)));
});
