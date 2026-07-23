/* 书房阅读器 Service Worker
 *
 * 缓存策略：
 *   - 应用外壳（index.html / manifest / 图标）：stale-while-revalidate，
 *     离线时也能打开阅读器界面。
 *   - /api/*：只走网络，绝不缓存（数据是动态的，且前端在离线时会自动
 *     降级到 localStorage）。
 *   - 书籍正文 *.txt：network-first，成功后写入独立的 books 缓存并做数量
 *     上限裁剪，让最近读过的书可离线重读，同时避免缓存无限膨胀。
 */
const VERSION = 'v1';
const SHELL_CACHE = 'shufang-shell-' + VERSION;
const BOOK_CACHE = 'shufang-books-' + VERSION;
const BOOK_LIMIT = 20; // 最多离线保留多少本书的正文

const SHELL_ASSETS = [
  '/',
  '/index.html',
  '/manifest.webmanifest',
  '/icons/icon-192.png',
  '/icons/icon-512.png',
  '/icons/icon-maskable-192.png',
  '/icons/icon-maskable-512.png',
  '/icons/apple-touch-icon.png',
  '/icons/favicon-64.png',
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(SHELL_CACHE)
      .then((cache) => cache.addAll(SHELL_ASSETS))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(
        keys.filter((k) => k !== SHELL_CACHE && k !== BOOK_CACHE)
            .map((k) => caches.delete(k))
      ))
      .then(() => self.clients.claim())
  );
});

// 裁剪 books 缓存，保留最近写入的 BOOK_LIMIT 条。
async function trimBookCache() {
  const cache = await caches.open(BOOK_CACHE);
  const keys = await cache.keys();
  if (keys.length <= BOOK_LIMIT) return;
  // keys() 大致按插入顺序返回，删掉最旧的若干条。
  for (const req of keys.slice(0, keys.length - BOOK_LIMIT)) {
    await cache.delete(req);
  }
}

async function networkFirstBook(request) {
  const cache = await caches.open(BOOK_CACHE);
  try {
    const resp = await fetch(request);
    if (resp && resp.ok) {
      cache.put(request, resp.clone());
      trimBookCache();
    }
    return resp;
  } catch (err) {
    const cached = await cache.match(request);
    if (cached) return cached;
    throw err;
  }
}

async function staleWhileRevalidate(request) {
  const cache = await caches.open(SHELL_CACHE);
  const cached = await cache.match(request);
  const network = fetch(request)
    .then((resp) => {
      if (resp && resp.ok) cache.put(request, resp.clone());
      return resp;
    })
    .catch(() => null);
  return cached || network || fetch(request);
}

self.addEventListener('fetch', (event) => {
  const { request } = event;
  if (request.method !== 'GET') return; // 只处理 GET

  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return; // 只处理同源

  // API：永远走网络，不拦截缓存。
  if (url.pathname.startsWith('/api/')) return;

  // 书籍正文：network-first + 离线缓存。
  if (url.pathname.endsWith('.txt')) {
    event.respondWith(networkFirstBook(request));
    return;
  }

  // 导航请求（打开应用）：回退到缓存的 index.html。
  if (request.mode === 'navigate') {
    event.respondWith(
      staleWhileRevalidate(request).catch(() => caches.match('/index.html'))
    );
    return;
  }

  // 其余同源静态资源：stale-while-revalidate。
  event.respondWith(staleWhileRevalidate(request));
});
