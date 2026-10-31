// frontend/next.config.ts
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import type { NextConfig } from "next";

export const TOKEN_PAGES = ["/invitation", "/magic-link", "/reset-password", "/confirm-email-change"];

const nextConfig: NextConfig = {
  // One built image serves any number of instances (ADR-010) -- no
  // instance-specific rebuild for theming/config, which is read at runtime.
  output: "standalone",
  // These pages carry a one-time token in the URL; it must not leak to other
  // origins through the Referer header.
  async headers() {
    return TOKEN_PAGES.map((source) => ({
      source,
      headers: [{ key: "Referrer-Policy", value: "no-referrer" }],
    }));
  },
};

export default nextConfig;
