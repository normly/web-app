// frontend/public/service-worker.js
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

// App-shell caching only -- no push-event handler. Real Web Push delivery
// depends on Google FCM / Apple APNs (see the design spec's "Entschieden
// mit dem Auftraggeber" Punkt 5), deliberately out of scope. A future
// push handler would live in this same file without needing a rewrite.
//
// Plain JavaScript, not TypeScript: this file is served as-is from
// public/ (Next.js does not run it through its own build/bundle step),
// so a compiled .ts source would just be a second copy to keep in sync --
// simpler and less drift-prone to write it directly as the file that ships.

const CACHE_NAME = "normly-shell-v1";
const SHELL_ASSETS = ["/", "/manifest.webmanifest"];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE_NAME).then((cache) => cache.addAll(SHELL_ASSETS)));
});

self.addEventListener("fetch", (event) => {
  event.respondWith(
    caches.match(event.request).then((cached) => cached ?? fetch(event.request)),
  );
});
