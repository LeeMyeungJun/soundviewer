importScripts("./catalog.js");

// Bump this version whenever application files, catalog, or media change.
const VERSION = "v2";
const PREFIX = `soundviewer:${self.registration.scope}:`;
const CACHE = PREFIX + VERSION;
const SHELL = ["./", "index.html", "styles.css", "app.js", "catalog.js", "credits.html", "credits.js", "assets/icon.svg"];
const FILES = [...SHELL, ...self.SOUND_CATALOG.flatMap((item) => [item.image, item.audio])];
const absolute = (path) => new URL(path, self.registration.scope).href;
const knownFiles = new Set(FILES.map(absolute));
let caching;

self.addEventListener("install", (event) => {
  event.waitUntil((async () => {
    const cache = await caches.open(CACHE);
    await cache.addAll(SHELL.map(absolute));
    await self.skipWaiting();
  })());
});
self.addEventListener("activate", (event) => {
  event.waitUntil(self.clients.claim());
});

async function broadcast(state) {
  const clients = await self.clients.matchAll({ includeUncontrolled: true });
  for (const client of clients) client.postMessage({ type: "CACHE_PROGRESS", ...state });
}

async function cacheAll() {
  const cache = await caches.open(CACHE);
  let done = 0;
  let failed = false;
  for (const file of FILES) {
    const url = absolute(file);
    try {
      if (!(await cache.match(url))) {
        const response = await fetch(url, { cache: "reload" });
        if (!response.ok || response.status === 206) throw new Error("Incomplete asset");
        await cache.put(url, response);
      }
      done++;
    } catch { failed = true; }
    await broadcast({ done, total: FILES.length, complete: false, error: false });
  }
  const complete = done === FILES.length;
  // Keep the previous version until its replacement is completely available.
  if (complete) {
    for (const key of await caches.keys()) {
      if (key.startsWith(PREFIX) && key !== CACHE) await caches.delete(key);
    }
  }
  await broadcast({ done, total: FILES.length, complete, error: failed });
}
self.addEventListener("message", (event) => {
  if (event.data?.type !== "CACHE_ALL") return;
  if (!caching) caching = cacheAll().finally(() => { caching = null; });
  event.waitUntil(caching);
});

async function rangeResponse(request, response) {
  const range = request.headers.get("range");
  if (!range) return response;
  const match = /^bytes=(\d*)-(\d*)$/.exec(range);
  const buffer = await response.arrayBuffer();
  const size = buffer.byteLength;
  let start = match?.[1] ? Number(match[1]) : 0;
  let end = match?.[2] ? Number(match[2]) : size - 1;
  if (match && !match[1] && match[2]) {
    start = Math.max(0, size - Number(match[2]));
    end = size - 1;
  }
  end = Math.min(end, size - 1);
  if (!match || (!match[1] && !match[2]) || start > end || start >= size) {
    return new Response(null, { status: 416, headers: { "Content-Range": `bytes */${size}` } });
  }
  const headers = new Headers(response.headers);
  headers.set("Content-Range", `bytes ${start}-${end}/${size}`);
  headers.set("Content-Length", String(end - start + 1));
  headers.set("Accept-Ranges", "bytes");
  return new Response(buffer.slice(start, end + 1), { status: 206, headers });
}

self.addEventListener("fetch", (event) => {
  if (event.request.method !== "GET") return;
  const url = new URL(event.request.url);
  url.search = "";
  if (!knownFiles.has(url.href)) return;
  event.respondWith((async () => {
    const cache = await caches.open(CACHE);
    const cached = await cache.match(url.href);
    if (cached) return rangeResponse(event.request, cached);
    // Fetch complete audio even for Safari range requests, then serve the requested slice.
    const response = await fetch(url.href);
    if (response.ok && response.status !== 206) {
      await cache.put(url.href, response.clone());
      return rangeResponse(event.request, response);
    }
    return response;
  })());
});
