// frontend/src/lib/config.ts
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

export interface InstanceConfig {
  instanceName: string;
  // HSL triple without the hsl() wrapper (e.g. "222 89% 55%") -- this is
  // the exact format Tailwind's `hsl(var(--brand) / <alpha-value>)`
  // color definitions expect (see tailwind.config.ts).
  brandColorHsl: string;
  logoPath: string | null;
}

// Deliberately NOT read from NEXT_PUBLIC_* variables: those are inlined at
// build time, which would defeat "one image, many instances" (ADR-010).
// Reading process.env directly inside a function keeps this evaluated per
// request in a Server Component.
export function getInstanceConfig(): InstanceConfig {
  return {
    instanceName: process.env.NORMLY_INSTANCE_NAME ?? "normly",
    brandColorHsl: process.env.NORMLY_BRAND_COLOR_HSL ?? "222 89% 55%",
    logoPath: process.env.NORMLY_LOGO_PATH ?? null,
  };
}
