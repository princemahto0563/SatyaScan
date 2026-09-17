// SatyaScan Lightweight Service Worker for Checkpoint Station Reliability
// PRIVACY BY DESIGN: Strictly caches UI application shell assets only.
// NEVER caches sensitive biometrics, document photos, selfies, heatmaps, reports, or API responses.

const CACHE_NAME = "satyascan-v1";
const STATIC_ASSETS = ["/", "/manifest.json", "/icon.svg"];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(STATIC_ASSETS);
    })
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) => {
      return Promise.all(
        keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key))
      );
    })
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const url = event.request.url;

  // STRICT PRIVACY POLICY: Zero biometric or sensitive document caching
  if (
    event.request.method !== "GET" ||
    url.includes("/api/") ||
    url.includes("/data/") ||
    url.includes("/uploads/") ||
    url.includes("/storage/") ||
    url.includes("/reports/") ||
    url.includes("/media/") ||
    url.includes("selfie") ||
    url.includes("passport") ||
    url.includes("heatmap") ||
    url.includes("pdf")
  ) {
    return; // Pass through directly to network/backend; zero offline biometric storage
  }

  // Only serve cached static UI shell assets (HTML, JS, CSS, SVG icons)
  event.respondWith(
    caches.match(event.request).then((cachedResponse) => {
      return cachedResponse || fetch(event.request);
    })
  );
});
