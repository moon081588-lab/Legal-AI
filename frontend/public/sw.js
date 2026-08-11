/* Legal-AI service worker.
 *
 * The static half of this app — evidence checklists, procedure navigator,
 * deadlines, templates, the journal — is useful with no network at all
 * (a shelter with bad signal, the subway, or a server outage). Cache it.
 *
 * Strategy:
 *   - App shell + pages: stale-while-revalidate
 *   - Reference GETs (/api/checklists, /api/procedure, /api/deadlines,
 *     /api/templates/*): network-first, fall back to cache when offline
 *   - /api/chat and other POSTs: never cached (live, personal)
 */

const CACHE = "legal-ai-v1";
const SHELL = ["/", "/journal", "/glossary", "/privacy", "/manifest.webmanifest"];

const CACHEABLE_API = [
  "/api/checklists",
  "/api/procedure",
  "/api/deadlines",
  "/api/templates/",
  "/api/centers",
  "/api/glossary",
  "/api/support/questions",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const { request } = event;
  if (request.method !== "GET") return; // chat POSTs stay live

  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;

  const isApi = url.pathname.startsWith("/api/");
  const cacheableApi = CACHEABLE_API.some((p) => url.pathname.startsWith(p));
  if (isApi && !cacheableApi) return; // health, chat, client-error: always live

  event.respondWith(
    isApi ? networkFirst(request) : staleWhileRevalidate(request)
  );
});

async function networkFirst(request) {
  const cache = await caches.open(CACHE);
  try {
    const res = await fetch(request);
    if (res.ok) cache.put(request, res.clone());
    return res;
  } catch (err) {
    const cached = await cache.match(request);
    if (cached) return cached;
    return new Response(
      JSON.stringify({ offline: true, error: "오프라인 상태이며 저장된 자료가 없습니다." }),
      { status: 503, headers: { "Content-Type": "application/json; charset=utf-8" } }
    );
  }
}

async function staleWhileRevalidate(request) {
  const cache = await caches.open(CACHE);
  const cached = await cache.match(request);
  const network = fetch(request)
    .then((res) => {
      if (res.ok) cache.put(request, res.clone());
      return res;
    })
    .catch(() => cached);
  return cached || network;
}
