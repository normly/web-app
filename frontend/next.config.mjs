// frontend/next.config.mjs
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors
//
// Written as .mjs, not .ts as the task brief specifies: Next.js 14.2.x
// (the pinned major version -- see frontend/package.json) hard-rejects a
// next.config.ts file at startup ("Configuring Next.js via 'next.config.ts'
// is not supported"). TypeScript config files were only added in Next.js 15.
// Content and behavior are otherwise identical to the brief's version;
// only the file extension and the loss of inline type-checking differ.

/** @type {import('next').NextConfig} */
const nextConfig = {
  // One built image serves any number of instances (ADR-010) -- no
  // instance-specific rebuild for theming/config, which is read at runtime.
  output: "standalone",
};

export default nextConfig;
