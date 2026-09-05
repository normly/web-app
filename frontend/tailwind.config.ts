// frontend/tailwind.config.ts
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import type { Config } from "tailwindcss";

// Tailwind v3's `/NN` opacity-modifier syntax (e.g. bg-primary/90) needs a
// color value it can combine with an opacity number -- a bare `var(--x)`
// string can't do that, so Tailwind silently drops the whole utility with
// no build error. These CSS variables hold complete oklch(...) functions
// (see globals.css), so color-mix() is what makes modifiers work; without
// an opacity modifier, the callback's `opacityValue` is a plain "1" or the
// `var(--tw-*-opacity)` fallback, and color-mix() at 100% just returns the
// original color, so the callback works either way.
// Cast to `string`: Tailwind's `Config` type declares `theme.colors` values as
// plain strings (`RecursiveKeyValuePair<string, string>`), but its runtime
// (lib/util/withAlphaVariable.js) explicitly supports and invokes a function
// value, calling it with `{ opacityValue }` -- the ambient types just haven't
// caught up. This is a type-only lie; the function itself is unchanged.
const withOpacity = (variable: string): string =>
  (({ opacityValue }: { opacityValue?: string }) =>
    opacityValue === undefined
      ? `var(${variable})`
      : `color-mix(in oklab, var(${variable}) calc(${opacityValue} * 100%), transparent)`) as unknown as string;

const config: Config = {
  darkMode: ["class"],
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Dormant multi-tenant branding override (REQ-DIST-003) -- see
        // globals.css. Not used by any component added after 2026-09-05.
        brand: "hsl(var(--brand) / <alpha-value>)",
        "brand-foreground": "hsl(var(--brand-foreground) / <alpha-value>)",

        // shadcn default theme. These variables hold complete oklch()
        // color functions (not raw component triples), so they're
        // referenced directly -- no hsl()/oklch() wrapper, and no
        // <alpha-value> opacity trick (needs raw numbers). Nothing here
        // needs bg-primary/50-style opacity modifiers.
        background: withOpacity("--background"),
        foreground: withOpacity("--foreground"),
        card: withOpacity("--card"),
        "card-foreground": withOpacity("--card-foreground"),
        popover: withOpacity("--popover"),
        "popover-foreground": withOpacity("--popover-foreground"),
        primary: withOpacity("--primary"),
        "primary-foreground": withOpacity("--primary-foreground"),
        secondary: withOpacity("--secondary"),
        "secondary-foreground": withOpacity("--secondary-foreground"),
        muted: withOpacity("--muted"),
        "muted-foreground": withOpacity("--muted-foreground"),
        accent: withOpacity("--accent"),
        "accent-foreground": withOpacity("--accent-foreground"),
        destructive: withOpacity("--destructive"),
        "destructive-foreground": withOpacity("--destructive-foreground"),
        border: withOpacity("--border"),
        input: withOpacity("--input"),
        ring: withOpacity("--ring"),
        "chart-1": withOpacity("--chart-1"),
        "chart-2": withOpacity("--chart-2"),
        "chart-3": withOpacity("--chart-3"),
        "chart-4": withOpacity("--chart-4"),
        "chart-5": withOpacity("--chart-5"),
        sidebar: withOpacity("--sidebar"),
        "sidebar-foreground": withOpacity("--sidebar-foreground"),
        "sidebar-primary": withOpacity("--sidebar-primary"),
        "sidebar-primary-foreground": withOpacity("--sidebar-primary-foreground"),
        "sidebar-accent": withOpacity("--sidebar-accent"),
        "sidebar-accent-foreground": withOpacity("--sidebar-accent-foreground"),
        "sidebar-border": withOpacity("--sidebar-border"),
        "sidebar-ring": withOpacity("--sidebar-ring"),
      },
      borderColor: {
        DEFAULT: "var(--border)",
      },
      borderRadius: {
        lg: "var(--radius)",
        md: "calc(var(--radius) - 2px)",
        sm: "calc(var(--radius) - 4px)",
      },
    },
  },
  plugins: [],
};

export default config;
