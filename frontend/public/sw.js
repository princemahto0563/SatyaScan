// SatyaScan Lightweight Service Worker for Checkpoint Station Reliability
// PRIVACY BY DESIGN: Strictly caches UI application shell assets only.
// NEVER caches sensitive biometrics, document photos, selfies, heatmaps, reports, or API responses.

const CACHE_NAME = "satyascan-v2";
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

  // Network-First for HTML navigation to ensure fresh application updates
  if (event.request.mode === "navigate") {
    event.respondWith(
      fetch(event.request)
        .then((response) => {
          const clone = response.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(event.request, clone));
          return response;
        })
        .catch(() => caches.match(event.request))
    );
    return;
  }

  // Cache-First for static hashed assets
  event.respondWith(
    caches.match(event.request).then((cachedResponse) => {
      return cachedResponse || fetch(event.request);
    })
  );
});
