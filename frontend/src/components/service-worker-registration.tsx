// frontend/src/components/service-worker-registration.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

"use client";

import { useEffect } from "react";

export function ServiceWorkerRegistration() {
  useEffect(() => {
    if ("serviceWorker" in navigator) {
      navigator.serviceWorker.register("/service-worker.js").catch(() => {
        // Installability is a progressive enhancement -- a failed
        // registration must not break the app itself.
      });
    }
  }, []);
  return null;
}
