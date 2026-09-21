/* 机会监控 · Service Worker：网络优先，断网退回缓存（能看上一次的数据） */
const CACHE = 'om-v2';
const CORE = ['./', './index.html', './now.html', './learn.html', './assets/app.css', './assets/app.js', './assets/echarts.min.js'];
self.addEventListener('install', e => { e.waitUntil(caches.open(CACHE).then(c => Promise.allSettled(CORE.map(u => c.add(u))))); self.skipWaiting(); });
self.addEventListener('activate', e => { e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k !== CACHE).map(k => caches.delete(k))))); self.clients.claim(); });
self.addEventListener('fetch', e => {
  const req = e.request; let u; try { u = new URL(req.url); } catch (_) { return; }
  if (req.method !== 'GET' || u.origin !== location.origin) return;
  e.respondWith(fetch(req).then(r => { if (r && r.ok) { const copy = r.clone(); caches.open(CACHE).then(c => c.put(req, copy)).catch(() => {}); } return r; })
    .catch(() => caches.match(req, { ignoreSearch: true }).then(m => m || (req.mode === 'navigate' ? caches.match('./index.html') : undefined))));
});
