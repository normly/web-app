// frontend/tests/unit/config.test.ts
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { afterEach, describe, expect, it, vi } from "vitest";
import { getInstanceConfig } from "@/lib/config";

describe("getInstanceConfig", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it("returns sensible defaults when no environment variables are set", () => {
    const config = getInstanceConfig();
    expect(config.instanceName).toBe("normly");
    expect(config.brandColorHsl).toBe("222 89% 55%");
    expect(config.logoPath).toBeNull();
  });

  it("reads overrides from environment variables", () => {
    vi.stubEnv("NORMLY_INSTANCE_NAME", "Beispiel-Institut");
    vi.stubEnv("NORMLY_BRAND_COLOR_HSL", "0 84% 60%");
    vi.stubEnv("NORMLY_LOGO_PATH", "/custom-logo.svg");

    const config = getInstanceConfig();
    expect(config.instanceName).toBe("Beispiel-Institut");
    expect(config.brandColorHsl).toBe("0 84% 60%");
    expect(config.logoPath).toBe("/custom-logo.svg");
  });
});
