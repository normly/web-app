// frontend/next.config.ts
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // One built image serves any number of instances (ADR-010) -- no
  // instance-specific rebuild for theming/config, which is read at runtime.
  output: "standalone",
};

export default nextConfig;
