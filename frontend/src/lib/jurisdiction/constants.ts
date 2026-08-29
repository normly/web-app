// frontend/src/lib/jurisdiction/constants.ts
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

// Deliberately NOT in provider.tsx (which is "use client"): a Server
// Component (layout.tsx's resolveInitialJurisdiction()) needs to call
// .includes() on JURISDICTIONS as real data at request time. Next.js's RSC
// transform turns every export of a "use client" module -- not just its
// component exports -- into an opaque client reference when imported from
// server code, so calling array methods on it there fails at runtime with
// "Attempted to call includes() from the server but includes is on the
// client" (does not surface in `npm test`/`tsc`, only in a real built-and-
// served app, which is exactly what this plan's Task 9 e2e run is the first
// thing in this branch to exercise). Keeping the plain data in its own
// non-"use client" module lets both server and client code import the real
// array; provider.tsx re-exports it for its existing client consumers.
export const JURISDICTIONS = ["DE", "EU"] as const;
export type Jurisdiction = (typeof JURISDICTIONS)[number];
