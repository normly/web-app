# Frontend Theme Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the frontend's ad-hoc, incomplete color-token setup with
the shadcn default theme (light + dark, via `next-themes`), so every later
redesign plan (app-shell, chat, profile overlay, auth pages,
search/document-detail) builds on a complete, correct, consistent set of
CSS variables.

**Architecture:** Hand-author the shadcn default theme's exact CSS
variables (already fetched from the `@shadcnblocks/theme/shadcnblocks`
registry item, not re-derived) directly into `globals.css` and
`tailwind.config.ts`, rather than trusting the shadcn CLI's
version-autodetection against this Tailwind v3 project. Then migrate the
four existing color-token-dependent primitives (`button`, `badge`,
`input`, `avatar`) off the old `--brand`-based classes and onto the new
tokens, and only then add `next-themes` for the light/dark toggle (its
`ModeToggle` button needs `Button`'s new `icon` size, so the primitives
migration must land first).

**Tech Stack:** Tailwind CSS v3.4 (already installed, NOT v4 — this
matters, see Task 1), `next-themes` (new dependency), existing
`class-variance-authority` / `@radix-ui/react-slot` / `lucide-react`.

## Global Constraints

- Design spec: `docs/superpowers/specs/2026-09-05-frontend-shadcn-redesign-design.md`
  — this plan implements only that spec's section 1 ("Theme-Fundament").
- **No Mandanten-Branding-Farbe.** `NORMLY_BRAND_COLOR_HSL` and
  `frontend/src/lib/config.ts`'s `getInstanceConfig()` stay in the code
  completely unchanged (REQ-DIST-003), but nothing added in this plan
  reads or references `--brand`/`--brand-foreground` — those two variables
  are the only ones this plan does NOT touch in `globals.css`/
  `tailwind.config.ts`.
- **Tailwind v3, not v4.** The registry theme item's CSS variables hold
  complete `oklch(...)` color function strings, not raw component triples.
  Under Tailwind v3 this means: reference variables directly
  (`var(--primary)`), never wrap them in `hsl()`/`oklch()`, and accept that
  the `bg-primary/50`-style opacity-modifier trick does not work (it needs
  raw numbers, not a pre-wrapped color function). Nothing in this plan or
  the design spec needs that trick.
- Every new/modified source file keeps its existing
  `SPDX-License-Identifier: AGPL-3.0-or-later` + copyright header (see any
  file in `frontend/src` for the exact two lines).
- Every commit needs a real DCO trailer: `git commit -s` (produces
  `Signed-off-by: normly <anonymous-jw@pm.me>`); if this session's work is
  attributed to Claude, add `Co-Authored-By: Claude Sonnet 5
  <noreply@anthropic.com>` as a **separate** trailer — never a second
  `Signed-off-by` line (see [[feedback_ai_dco_signoff]] memory: an AI
  cannot certify the DCO).
- No direct push to `main` — branch + PR against the `stackit` remote,
  per `CLAUDE.md`.
- Tests: Vitest unit tests live in `frontend/tests/unit/*.test.tsx`,
  discovered automatically (see `frontend/vitest.config.ts`). Run with
  `npm test` from `frontend/`. Playwright e2e (`npm run test:e2e`) builds
  and starts the app against a real Postgres — out of scope for this
  plan's automated checks (same exclusion the CI pipeline already applies
  to `frontend`'s `npm test` job); manual visual verification steps are
  called out explicitly where they matter.

---

### Task 1: shadcn default theme CSS variables

**Files:**
- Modify: `frontend/src/app/globals.css`
- Modify: `frontend/tailwind.config.ts`

**Interfaces:**
- Produces: the CSS custom properties `--background`, `--foreground`,
  `--card`, `--card-foreground`, `--popover`, `--popover-foreground`,
  `--primary`, `--primary-foreground`, `--secondary`,
  `--secondary-foreground`, `--muted`, `--muted-foreground`, `--accent`,
  `--accent-foreground`, `--destructive`, `--destructive-foreground`,
  `--border`, `--input`, `--ring`, `--chart-1`..`--chart-5`, `--sidebar`,
  `--sidebar-foreground`, `--sidebar-primary`,
  `--sidebar-primary-foreground`, `--sidebar-accent`,
  `--sidebar-accent-foreground`, `--sidebar-border`, `--sidebar-ring`,
  `--radius`, defined in both `:root` (light) and `.dark` (dark) — every
  later task and plan in this redesign uses these names via Tailwind
  utility classes (`bg-primary`, `text-muted-foreground`, `border-input`,
  etc.), never the raw `var(--x)` form directly.
- Leaves `--brand` / `--brand-foreground` and their `brand` /
  `brand-foreground` Tailwind color keys completely untouched (still
  present, still HSL-triple format, still unused by anything new).

- [ ] **Step 1: Replace `globals.css`'s `:root` block and add a `.dark` block**

Replace the entire file with:

```css
/* frontend/src/app/globals.css */
@tailwind base;
@tailwind components;
@tailwind utilities;

:root {
  /* Dormant multi-tenant branding override (REQ-DIST-003) -- not wired
     into any component (2026-09-05 frontend redesign: "keine
     Mandantenfarben mehr"), kept only so NORMLY_BRAND_COLOR_HSL keeps
     working the day this gets reconnected. Do not remove without a
     separate decision on REQ-DIST-003 itself. */
  --brand: 222 89% 55%;
  --brand-foreground: 0 0% 100%;

  --background: oklch(1 0 0);
  --foreground: oklch(0.145 0 0);
  --card: oklch(1 0 0);
  --card-foreground: oklch(0.145 0 0);
  --popover: oklch(1 0 0);
  --popover-foreground: oklch(0.145 0 0);
  --primary: oklch(0.205 0 0);
  --primary-foreground: oklch(0.985 0 0);
  --secondary: oklch(0.97 0 0);
  --secondary-foreground: oklch(0.205 0 0);
  --muted: oklch(0.97 0 0);
  --muted-foreground: oklch(0.556 0 0);
  --accent: oklch(0.97 0 0);
  --accent-foreground: oklch(0.205 0 0);
  --destructive: oklch(0.577 0.245 27.325);
  --destructive-foreground: oklch(0.985 0 0);
  --border: oklch(0.922 0 0);
  --input: oklch(0.922 0 0);
  --ring: oklch(0.708 0 0);
  --chart-1: oklch(0.646 0.222 41.116);
  --chart-2: oklch(0.6 0.118 184.704);
  --chart-3: oklch(0.398 0.07 227.392);
  --chart-4: oklch(0.828 0.189 84.429);
  --chart-5: oklch(0.769 0.188 70.08);
  --sidebar: oklch(0.985 0 0);
  --sidebar-foreground: oklch(0.145 0 0);
  --sidebar-primary: oklch(0.205 0 0);
  --sidebar-primary-foreground: oklch(0.985 0 0);
  --sidebar-accent: oklch(0.97 0 0);
  --sidebar-accent-foreground: oklch(0.205 0 0);
  --sidebar-border: oklch(0.922 0 0);
  --sidebar-ring: oklch(0.708 0 0);
  --radius: 8px;
}

.dark {
  --background: oklch(0.145 0 0);
  --foreground: oklch(0.985 0 0);
  --card: oklch(0.145 0 0);
  --card-foreground: oklch(0.985 0 0);
  --popover: oklch(0.205 0 0);
  --popover-foreground: oklch(0.985 0 0);
  --primary: oklch(0.922 0 0);
  --primary-foreground: oklch(0.205 0 0);
  --secondary: oklch(0.269 0 0);
  --secondary-foreground: oklch(0.985 0 0);
  --muted: oklch(0.269 0 0);
  --muted-foreground: oklch(0.708 0 0);
  --accent: oklch(0.269 0 0);
  --accent-foreground: oklch(0.985 0 0);
  --destructive: oklch(0.704 0.191 22.216);
  --destructive-foreground: oklch(0.985 0 0);
  --border: oklch(1 0 0 / 10%);
  --input: oklch(1 0 0 / 15%);
  --ring: oklch(0.556 0 0);
  --chart-1: oklch(0.488 0.243 264.376);
  --chart-2: oklch(0.696 0.17 162.48);
  --chart-3: oklch(0.769 0.188 70.08);
  --chart-4: oklch(0.627 0.265 303.9);
  --chart-5: oklch(0.645 0.246 16.439);
  --sidebar: oklch(0.205 0 0);
  --sidebar-foreground: oklch(0.985 0 0);
  --sidebar-primary: oklch(0.488 0.243 264.376);
  --sidebar-primary-foreground: oklch(0.985 0 0);
  --sidebar-accent: oklch(0.269 0 0);
  --sidebar-accent-foreground: oklch(0.985 0 0);
  --sidebar-border: oklch(1 0 0 / 10%);
  --sidebar-ring: oklch(0.556 0 0);
}

@layer base {
  * {
    @apply border-border;
  }
  body {
    @apply bg-background text-foreground;
  }
}
```

- [ ] **Step 2: Replace `tailwind.config.ts`'s color mapping**

Replace the entire file with:

```ts
// frontend/tailwind.config.ts
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import type { Config } from "tailwindcss";

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
        background: "var(--background)",
        foreground: "var(--foreground)",
        card: "var(--card)",
        "card-foreground": "var(--card-foreground)",
        popover: "var(--popover)",
        "popover-foreground": "var(--popover-foreground)",
        primary: "var(--primary)",
        "primary-foreground": "var(--primary-foreground)",
        secondary: "var(--secondary)",
        "secondary-foreground": "var(--secondary-foreground)",
        muted: "var(--muted)",
        "muted-foreground": "var(--muted-foreground)",
        accent: "var(--accent)",
        "accent-foreground": "var(--accent-foreground)",
        destructive: "var(--destructive)",
        "destructive-foreground": "var(--destructive-foreground)",
        border: "var(--border)",
        input: "var(--input)",
        ring: "var(--ring)",
        "chart-1": "var(--chart-1)",
        "chart-2": "var(--chart-2)",
        "chart-3": "var(--chart-3)",
        "chart-4": "var(--chart-4)",
        "chart-5": "var(--chart-5)",
        sidebar: "var(--sidebar)",
        "sidebar-foreground": "var(--sidebar-foreground)",
        "sidebar-primary": "var(--sidebar-primary)",
        "sidebar-primary-foreground": "var(--sidebar-primary-foreground)",
        "sidebar-accent": "var(--sidebar-accent)",
        "sidebar-accent-foreground": "var(--sidebar-accent-foreground)",
        "sidebar-border": "var(--sidebar-border)",
        "sidebar-ring": "var(--sidebar-ring)",
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
```

- [ ] **Step 3: Verify the build still compiles**

Run: `cd frontend && npm run build`
Expected: build succeeds with no PostCSS/Tailwind/TypeScript errors. (This
is the concrete verification for this task — there is no meaningful way to
unit-test raw CSS custom properties under jsdom, since Vitest never runs
PostCSS/Tailwind; a successful production build is the real signal that
the new config and CSS parse and apply correctly.)

- [ ] **Step 4: Commit**

```bash
cd frontend
git add src/app/globals.css tailwind.config.ts
git commit -s -m "feat(frontend): add shadcn default theme CSS variables"
```

---

### Task 2: Migrate existing primitives onto the new tokens

**Files:**
- Modify: `frontend/src/components/ui/button.tsx`
- Modify: `frontend/src/components/ui/badge.tsx`
- Modify: `frontend/src/components/ui/input.tsx`
- Modify: `frontend/src/components/ui/avatar.tsx`

**Interfaces:**
- Consumes: the `--primary`/`--secondary`/`--destructive`/`--ring`/etc.
  tokens from Task 1.
- Produces: `Button` gains `variant: "destructive" | "secondary" | "link"`
  (in addition to the existing `"default" | "outline" | "ghost"`) and
  `size: "icon"` (in addition to `"default" | "sm" | "lg"`) — a strict
  superset, every existing call site keeps compiling unchanged. Task 3's
  `ModeToggle` depends on this `size: "icon"` existing — this task must
  land first. `Badge` gains `variant: "secondary" | "destructive"`
  alongside the existing `"default" | "outline"`, and keeps `"muted"`
  (not part of canonical shadcn, but one real call site —
  `src/app/documents/[id]/document-detail-content.tsx:141` — depends on
  it; dropping it is out of scope for a theme-foundation task). `Avatar`
  and `Input` keep their exact existing prop shapes; only their internal
  Tailwind classes change.

- [ ] **Step 1: Replace `button.tsx`'s variants**

Replace `frontend/src/components/ui/button.tsx`'s `buttonVariants` call
(keep the file's existing imports, `ButtonProps` interface, and the
`Button` component body unchanged) with the canonical shadcn set:

```tsx
const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md text-sm font-medium ring-offset-background transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 [&_svg]:pointer-events-none [&_svg]:size-4 [&_svg]:shrink-0",
  {
    variants: {
      variant: {
        default: "bg-primary text-primary-foreground hover:bg-primary/90",
        destructive: "bg-destructive text-destructive-foreground hover:bg-destructive/90",
        outline: "border border-input bg-background hover:bg-accent hover:text-accent-foreground",
        secondary: "bg-secondary text-secondary-foreground hover:bg-secondary/80",
        ghost: "hover:bg-accent hover:text-accent-foreground",
        link: "text-primary underline-offset-4 hover:underline",
      },
      size: {
        default: "h-10 px-4 py-2",
        sm: "h-9 rounded-md px-3",
        lg: "h-11 rounded-md px-8",
        icon: "h-10 w-10",
      },
    },
    defaultVariants: { variant: "default", size: "default" },
  },
);
```

(This drops the old `hover:opacity-90`/`bg-brand` default and the
`focus-visible:ring-brand` in favor of `bg-primary`/`hover:bg-primary/90`
and `focus-visible:ring-ring` — every existing usage passes `variant`
values that still exist, so no call site needs to change.)

- [ ] **Step 2: Run the button test**

Run: `cd frontend && npm test -- button`
Expected: PASS (existing tests only check click/disabled behavior, not
classes).

- [ ] **Step 3: Replace `badge.tsx`'s variants**

Replace `frontend/src/components/ui/badge.tsx`'s `badgeVariants` call
(keep everything else in the file unchanged):

```tsx
const badgeVariants = cva(
  "inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2",
  {
    variants: {
      variant: {
        default: "border-transparent bg-primary text-primary-foreground hover:bg-primary/80",
        secondary: "border-transparent bg-secondary text-secondary-foreground hover:bg-secondary/80",
        destructive: "border-transparent bg-destructive text-destructive-foreground hover:bg-destructive/80",
        outline: "text-foreground",
        // Not part of canonical shadcn -- kept because
        // src/app/documents/[id]/document-detail-content.tsx:141 depends
        // on it; equivalent to the old default before this migration.
        muted: "border-transparent bg-muted text-muted-foreground hover:bg-muted/80",
      },
    },
    defaultVariants: { variant: "default" },
  },
);
```

- [ ] **Step 4: Run the badge test**

Run: `cd frontend && npm test -- badge`
Expected: PASS (the existing "applies the outline variant's classes"
test checks for a bare `"border"` class, which is in the shared base
classes now, present for every variant).

- [ ] **Step 5: Replace `input.tsx`'s className**

Replace `frontend/src/components/ui/input.tsx`'s `className` string
(keep the rest of the file unchanged):

```tsx
        "flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-base ring-offset-background file:border-0 file:bg-transparent file:text-sm file:font-medium file:text-foreground placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 md:text-sm",
```

- [ ] **Step 6: Replace `avatar.tsx`'s fallback classes**

In `frontend/src/components/ui/avatar.tsx`, change the fallback
`<span>`'s className (keep everything else — props, `initialsFor`, the
image branch — unchanged):

```tsx
      className="flex items-center justify-center rounded-full bg-primary text-primary-foreground text-xs font-medium"
```

(was `bg-brand text-brand-foreground`). This is a values-only rename —
`Avatar` keeps its current custom
`{ avatarDataUrl, firstName, lastName, email, size }` API. A later plan
(App-Shell) introduces the *separate*, canonical composable
`Avatar`/`AvatarImage`/`AvatarFallback` trio that `application-shell2`
expects, under a different file/name — not this task's job.

- [ ] **Step 7: Run the avatar test**

Run: `cd frontend && npm test -- avatar`
Expected: PASS (existing tests check rendered content, not classes).

- [ ] **Step 8: Run the full unit suite**

Run: `cd frontend && npm test`
Expected: PASS, every suite.

- [ ] **Step 9: Run the build**

Run: `cd frontend && npm run build`
Expected: succeeds.

- [ ] **Step 10: Manual visual check**

Start the app (`npm run dev`, or the sandbox stack from this session's
earlier run — `docker start normly-pg` if the container still exists,
then the three `uvicorn` processes with their env vars, then
`npm run dev`) and confirm in a browser: primary buttons now render in
the new theme's near-black color rather than the old blue `--brand`
color; the "Gültig"/"Ersetzt" badges on a document detail page (needs at
least one ingested document — see the ingestion commands used earlier
this session) still render correctly; the account avatar's fallback
initials show the same near-black color as buttons now, instead of blue.

- [ ] **Step 11: Commit**

```bash
cd frontend
git add src/components/ui/button.tsx src/components/ui/badge.tsx \
  src/components/ui/input.tsx src/components/ui/avatar.tsx
git commit -s -m "refactor(frontend): migrate button/badge/input/avatar off brand tokens"
```

---

### Task 3: Light/Dark toggle via next-themes

**Files:**
- Modify: `frontend/package.json` (add `next-themes` dependency)
- Create: `frontend/src/components/theme-provider.tsx`
- Create: `frontend/src/components/mode-toggle.tsx`
- Create: `frontend/tests/unit/mode-toggle.test.tsx`
- Modify: `frontend/src/app/layout.tsx`
- Modify: `frontend/src/components/app-header.tsx`
- Modify: `frontend/tests/unit/app-header.test.tsx`

**Interfaces:**
- Consumes: Tailwind's `dark:` variant now works via `darkMode: ["class"]`
  from Task 1 — a `dark` class anywhere above an element in the DOM makes
  its `dark:*` utilities apply. `next-themes` is what adds/removes that
  class on `<html>`. Consumes `Button`'s `size="icon"` from Task 2.
- Produces: `ThemeProvider` (named export from
  `@/components/theme-provider`, wraps `next-themes`'s own provider) and
  `ModeToggle` (named export from `@/components/mode-toggle`, a
  self-contained icon button, no props) — later plans (App-Shell's
  header, per the design spec) import `ModeToggle` directly; nothing
  about its props changes later.

- [ ] **Step 1: Add the `next-themes` dependency**

Run: `cd frontend && npm install next-themes@0.4.6`

- [ ] **Step 2: Write the failing test for `ModeToggle`**

Create `frontend/tests/unit/mode-toggle.test.tsx`:

```tsx
// frontend/tests/unit/mode-toggle.test.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

const setTheme = vi.fn();
vi.mock("next-themes", () => ({
  useTheme: () => ({ resolvedTheme: "light", setTheme }),
}));

import { ModeToggle } from "@/components/mode-toggle";

describe("ModeToggle", () => {
  it("switches to dark mode when clicked while resolved theme is light", () => {
    render(<ModeToggle />);
    fireEvent.click(screen.getByRole("button", { name: "Farbschema umschalten" }));
    expect(setTheme).toHaveBeenCalledWith("dark");
  });
});
```

- [ ] **Step 3: Run it to verify it fails**

Run: `cd frontend && npm test -- mode-toggle`
Expected: FAIL — `Cannot find module '@/components/mode-toggle'` (the
file does not exist yet).

- [ ] **Step 4: Create `ThemeProvider`**

Create `frontend/src/components/theme-provider.tsx`:

```tsx
// frontend/src/components/theme-provider.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

"use client";

import * as React from "react";
import { ThemeProvider as NextThemesProvider } from "next-themes";

export function ThemeProvider({
  children,
  ...props
}: React.ComponentProps<typeof NextThemesProvider>) {
  return <NextThemesProvider {...props}>{children}</NextThemesProvider>;
}
```

- [ ] **Step 5: Create `ModeToggle`**

Create `frontend/src/components/mode-toggle.tsx`:

```tsx
// frontend/src/components/mode-toggle.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

"use client";

import * as React from "react";
import { Moon, Sun } from "lucide-react";
import { useTheme } from "next-themes";
import { Button } from "@/components/ui/button";

export function ModeToggle() {
  const { resolvedTheme, setTheme } = useTheme();
  const [mounted, setMounted] = React.useState(false);
  React.useEffect(() => setMounted(true), []);

  return (
    <Button
      variant="outline"
      size="icon"
      aria-label="Farbschema umschalten"
      onClick={() => setTheme(resolvedTheme === "dark" ? "light" : "dark")}
    >
      {mounted && resolvedTheme === "dark" ? (
        <Sun className="h-4 w-4" />
      ) : (
        <Moon className="h-4 w-4" />
      )}
    </Button>
  );
}
```

(The `mounted` guard avoids a server/client hydration mismatch: `next-themes`
only knows the real theme after mounting on the client, so the icon shown
during server rendering must be a fixed default — `Moon` — regardless of
the real stored preference.)

- [ ] **Step 6: Run the test to verify it passes**

Run: `cd frontend && npm test -- mode-toggle`
Expected: PASS

- [ ] **Step 7: Wrap the root layout in `ThemeProvider`**

Modify `frontend/src/app/layout.tsx` — add the import and wrap the
existing children:

```tsx
import { ThemeProvider } from "@/components/theme-provider";
```

(add alongside the other imports at the top), then change the `<body>`
block from:

```tsx
      <body>
        <LocaleProvider initialLocale={initialLocale}>
          <JurisdictionProvider initialJurisdiction={initialJurisdiction}>
            <ServiceWorkerRegistration />
            {children}
          </JurisdictionProvider>
        </LocaleProvider>
      </body>
```

to:

```tsx
      <body>
        <ThemeProvider attribute="class" defaultTheme="system" enableSystem>
          <LocaleProvider initialLocale={initialLocale}>
            <JurisdictionProvider initialJurisdiction={initialJurisdiction}>
              <ServiceWorkerRegistration />
              {children}
            </JurisdictionProvider>
          </LocaleProvider>
        </ThemeProvider>
      </body>
```

- [ ] **Step 8: Add `ModeToggle` to the existing header (temporary placement)**

The App-Shell plan (this redesign's next plan) relocates this into a
shared page header component. Until then, it needs a real, visible home
so this task's own deliverable is actually usable and testable — add it
to the existing `AppHeader`.

Modify `frontend/src/components/app-header.tsx`: add the import

```tsx
import { ModeToggle } from "@/components/mode-toggle";
```

then, inside the `<div className="flex items-center gap-2">` block, add
`<ModeToggle />` right after `<JurisdictionSwitcher />`:

```tsx
        <LocaleSwitcher />
        <JurisdictionSwitcher />
        <ModeToggle />
```

- [ ] **Step 9: Update `app-header.test.tsx` for the new button**

`ModeToggle` calls `useTheme()` from `next-themes`; none of these existing
tests wrap `AppHeader` in a `ThemeProvider`, and none of them need to
exercise the toggle's click behavior (that's `mode-toggle.test.tsx`'s
job) — just mock `next-themes` so rendering doesn't rely on an unmocked
context default, and add one assertion that the button is present.

Add near the top of `frontend/tests/unit/app-header.test.tsx`, after the
existing imports:

```tsx
vi.mock("next-themes", () => ({
  useTheme: () => ({ resolvedTheme: "light", setTheme: vi.fn() }),
}));
```

Add a new test case at the end of the `describe("AppHeader", ...)` block:

```tsx
  it("renders the mode toggle button", async () => {
    global.fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify({ account: null })));
    render(
      <LocaleProvider initialLocale="de">
        <JurisdictionProvider initialJurisdiction="DE">
          <AppHeader instanceName="normly" logoPath={null} />
        </JurisdictionProvider>
      </LocaleProvider>,
    );
    expect(screen.getByRole("button", { name: "Farbschema umschalten" })).toBeInTheDocument();
  });
```

- [ ] **Step 10: Run the full unit suite**

Run: `cd frontend && npm test`
Expected: PASS, all suites including the new/modified ones.

- [ ] **Step 11: Manual visual check**

Using the same running app as Task 2's Step 10, confirm in a browser: the
new moon/sun button appears in the header, clicking it flips the whole
page to a dark background with light text and back, and the choice
survives a page reload (`next-themes` persists to `localStorage`).

- [ ] **Step 12: Commit**

```bash
cd frontend
git add package.json package-lock.json src/components/theme-provider.tsx \
  src/components/mode-toggle.tsx src/app/layout.tsx src/components/app-header.tsx \
  tests/unit/mode-toggle.test.tsx tests/unit/app-header.test.tsx
git commit -s -m "feat(frontend): add light/dark mode toggle via next-themes"
```

---

## After This Plan

Push the branch, open a PR against `main` on the `stackit` remote, wait
for the CI pipeline's `test-frontend` job (the only one this plan's
changes affect) to go green, merge. The next plan in this redesign
(App-Shell + header pattern, per
`docs/superpowers/specs/2026-09-05-frontend-shadcn-redesign-design.md`)
depends on this one being merged first.
