// frontend/tailwind.config.ts
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Populated by Task 4's theming system via CSS variables --
        // these map Tailwind utility classes (bg-brand, text-brand) to
        // whatever the runtime configuration sets, not a hardcoded value.
        brand: "hsl(var(--brand) / <alpha-value>)",
        "brand-foreground": "hsl(var(--brand-foreground) / <alpha-value>)",
      },
    },
  },
  plugins: [],
};

export default config;
