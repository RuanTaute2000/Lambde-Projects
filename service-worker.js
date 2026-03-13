const CACHE_NAME = 'lambda-tools-v5';
const ASSETS = [
  '/',
  '/manifest.json',
  '/static/style.css',
  '/static/script.js',
  '/static/logo.png',
  '/static/icon-192.png',
  '/static/icon-512.png',
  '/static/offline.html'
];

self.addEventListener('install', event => {
  self.skipWaiting();
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => cache.addAll(ASSETS))
  );
});

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys => Promise.all(
      keys.filter(key => key !== CACHE_NAME).map(key => caches.delete(key))
    )).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', event => {
  const { request } = event;
  if (request.method !== 'GET') return;

  // Always try network first for navigation/HTML to avoid stale pages
  if (request.mode === 'navigate') {
    event.respondWith(
      fetch(request)
        .then(response => {
          const clone = response.clone();
          caches.open(CACHE_NAME).then(cache => cache.put(request, clone));
          return response;
        })
        .catch(() => caches.match('/static/offline.html'))
    );
    return;
  }

  // Cache-first for static assets
  if (request.url.includes('/static/') || request.url.endsWith('manifest.json')) {
    event.respondWith(
      caches.match(request).then(cached => {
        const network = fetch(request).then(res => {
          caches.open(CACHE_NAME).then(cache => cache.put(request, res.clone()));
          return res;
        });
        return cached || network;
      })
    );
    return;
  }

  // Default: network with cache fallback
  event.respondWith(
    fetch(request)
      .then(res => {
        caches.open(CACHE_NAME).then(cache => cache.put(request, res.clone()));
        return res;
      })
      .catch(() => caches.match(request))
  );
});
