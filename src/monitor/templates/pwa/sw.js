/* 机会监控 · Service Worker：网络优先，断网/弱网退回缓存（能看上一次的数据） */
const CACHE = 'om-v3';
const CORE = ['./index.html', './now.html', './learn.html', './assets/app.css', './assets/app.js', './assets/echarts.min.js'];
self.addEventListener('install', e => { e.waitUntil(caches.open(CACHE).then(c => Promise.allSettled(CORE.map(u => c.add(u))))); self.skipWaiting(); });
self.addEventListener('activate', e => { e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k !== CACHE).map(k => caches.delete(k))))); self.clients.claim(); });
self.addEventListener('fetch', e => {
  const req = e.request; let u; try { u = new URL(req.url); } catch (_) { return; }
  if (req.method !== 'GET' || u.origin !== location.origin) return;
  // "./" 与 "./index.html" 是同一页：统一缓存 key，离线时两个入口看到同一份数据
  const key = (req.mode === 'navigate' && /\/(index\.html)?$/.test(u.pathname)) ? './index.html' : req;
  // 弱网（有信号但不通）时 fetch 可能挂几十秒：导航请求 8 秒内没响应就用缓存
  const timeout = new Promise((_, rej) => setTimeout(rej, 8000)); timeout.catch(() => {});
  e.respondWith((req.mode === 'navigate' ? Promise.race([fetch(req), timeout]) : fetch(req))
    .then(r => { if (r && r.ok) { const copy = r.clone(); caches.open(CACHE).then(c => c.put(key, copy)).catch(() => {}); } return r; })
    .catch(() => caches.match(key, { ignoreSearch: true }).then(m => m || (req.mode === 'navigate' ? caches.match('./index.html') : undefined))));
});
