# Frontend Shell and Chat UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first normly frontend: an installable, DE/EN-bilingual, WCAG 2.1 AA chat
web app (Next.js) that works fully anonymously and optionally links sessions to a real
account, backed by the already-shipped `api/`/`accounts/`/`chat/` services.

**Architecture:** A new top-level `frontend/` (Next.js App Router, TypeScript). No direct
client-side calls to `accounts/`/`chat/` — Next.js Route Handlers act as a thin
backend-for-frontend, translating backend session tokens into httpOnly cookies the browser
never reads directly. One small, closely-related backend addition (list a account's chat
sessions) lands first since `/chats` cannot be built without it.

**Tech Stack:** Next.js 14 (App Router) + TypeScript + React 18, Tailwind CSS 3 + shadcn/ui,
Vitest + React Testing Library (component tests), Playwright + `@axe-core/playwright`
(end-to-end + accessibility).

## Global Constraints

- License header on every new Python file (`# SPDX-License-Identifier: AGPL-3.0-or-later` +
  `# Copyright (C) 2026 normly contributors`) — Task 1 only, the rest of this plan is
  TypeScript/frontend code, licensed AGPL-3.0-or-later too but conventionally without a
  per-file SPDX header block in this ecosystem; a single `LICENSE` reference at the package
  root is enough, matching common Next.js project conventions. Do not skip DCO sign-off on any
  commit regardless of language.
- Every commit needs a DCO `Signed-off-by` trailer — use `git commit -s`.
- No direct client-side (browser) calls to `accounts/` or `chat/` — always through a Next.js
  Route Handler, source files under `src/app/api/*` (the `app/` segment is the App Router's
  source root, not part of the served URL — a handler at `src/app/api/chat/route.ts` is served
  at `/api/chat`, never `/app/api/chat`). `api/` reads MAY be called directly from Server
  Components where convenient (read-only, no session state involved), but citation resolution
  in this plan goes through a Route Handler too, for one consistent pattern.
- Session tokens live only in httpOnly cookies, set by Route Handlers — never in
  `localStorage`, never readable by client-side JavaScript.
- No hardcoded backend URLs — always from environment variables
  (`NORMLY_API_BASE_URL`/`NORMLY_ACCOUNTS_BASE_URL`/`NORMLY_CHAT_BASE_URL`), matching the
  convention already established in `chat/`'s own service-to-service calls.
- `output: "standalone"` in `next.config.ts` — one image for any number of instances, no
  instance-specific rebuild (ADR-010).
- Theming (colors/typography/logo) and locale default are runtime configuration, never baked
  into the build.
- No `next-intl` or other locale-routing middleware — locale is a cookie
  (`normly_locale`), never a URL prefix.
- No WHAT-comments; only non-obvious WHY, matching the rest of this codebase's style.

---

### Task 1: Backend — list a account's chat sessions

**Files:**
- Modify: `core/src/normly_core/graph/domain.py`
- Modify: `core/src/normly_core/graph/postgres/repositories.py`
- Modify: `core/tests/graph/test_architecture.py`
- Test: `core/tests/graph/test_chat_repository.py`
- Create: `chat/src/normly_chat/routers/sessions.py`
- Modify: `chat/src/normly_chat/schemas.py`
- Modify: `chat/src/normly_chat/main.py`
- Test: `chat/tests/test_sessions_router.py`

**Interfaces:**
- Consumes: `ChatSessionORM`/`ChatSession` (existing), `AccountsClient.validate_session`
  (existing, `chat/src/normly_chat/accounts_client.py`).
- Produces: `ChatRepository.list_sessions_for_account(account_id) -> list[ChatSession]`;
  `GET /v1/chat/sessions` (requires `Authorization: Bearer <account-session-token>`) — consumed
  by Task 11 (`/chats` route handler).

- [ ] **Step 1: Write the failing core test**

```python
# Add to core/tests/graph/test_chat_repository.py

def test_list_sessions_for_account_returns_only_that_accounts_sessions_newest_first(db_session):
    from normly_core.graph.postgres.repositories import PostgresAccountRepository

    account_a = PostgresAccountRepository(db_session).create_account(
        email="sessions-a@example.de", password_hash=None,
    )
    account_b = PostgresAccountRepository(db_session).create_account(
        email="sessions-b@example.de", password_hash=None,
    )
    repo = PostgresChatRepository(db_session)
    older = repo.create_session(
        session_token="tok-a-older", jurisdiction="DE", language="de",
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc), account_id=account_a.id,
    )
    newer = repo.create_session(
        session_token="tok-a-newer", jurisdiction="DE", language="en",
        created_at=datetime(2026, 2, 1, tzinfo=timezone.utc), account_id=account_a.id,
    )
    repo.create_session(
        session_token="tok-b", jurisdiction="DE", language="de",
        created_at=datetime(2026, 1, 15, tzinfo=timezone.utc), account_id=account_b.id,
    )
    repo.create_session(
        session_token="tok-anon", jurisdiction="DE", language="de",
        created_at=datetime(2026, 1, 20, tzinfo=timezone.utc),
    )

    sessions = repo.list_sessions_for_account(account_a.id)

    assert [s.id for s in sessions] == [newer.id, older.id]
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd core && .venv/bin/python -m pytest tests/graph/test_chat_repository.py -v`
Expected: FAIL — `list_sessions_for_account` doesn't exist yet.

- [ ] **Step 3: Add the Protocol method and implementation**

Add to the `ChatRepository` Protocol in `core/src/normly_core/graph/domain.py`, right after
`get_session_by_token`:

```python
    def list_sessions_for_account(self, account_id: uuid.UUID) -> list[ChatSession]: ...
```

Add to `PostgresChatRepository` in `core/src/normly_core/graph/postgres/repositories.py`,
right after `get_session_by_token`:

```python
    def list_sessions_for_account(self, account_id: uuid.UUID) -> list[ChatSession]:
        rows = self._session.execute(
            select(ChatSessionORM)
            .where(ChatSessionORM.account_id == account_id)
            .order_by(ChatSessionORM.created_at.desc())
        ).scalars()
        return [_chat_session_to_domain(row) for row in rows]
```

- [ ] **Step 4: Exempt the new read from the jurisdiction guard**

`list_sessions_for_account` resolves session identity, not rights-gated content — same
category as `get_session_by_token`/`list_messages_for_session`, already exempted. Add to
`JURISDICTION_EXEMPT_READS` in `core/tests/graph/test_architecture.py`, next to the existing
`"ChatRepository.get_session_by_token"` line:

```python
    "ChatRepository.list_sessions_for_account",
```

- [ ] **Step 5: Run the core tests**

Run: `cd core && .venv/bin/python -m pytest tests/graph/test_chat_repository.py tests/graph/test_architecture.py -v`
Expected: PASS.

- [ ] **Step 6: Run the full core suite**

Run: `cd core && .venv/bin/python -m pytest -v -W error`
Expected: all pass, pristine output.

- [ ] **Step 7: Commit the core change**

```bash
git add core/src/normly_core/graph/domain.py core/src/normly_core/graph/postgres/repositories.py \
  core/tests/graph/test_architecture.py core/tests/graph/test_chat_repository.py
git commit -s -m "feat: add ChatRepository.list_sessions_for_account"
```

- [ ] **Step 8: Write the failing chat/ router test**

```python
# chat/tests/test_sessions_router.py
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

import uuid

from normly_chat.accounts_client import ChatAccountIdentity


class _FakeAccountsClient:
    def __init__(self, identity):
        self._identity = identity

    def validate_session(self, token):
        return self._identity


def test_missing_authorization_header_returns_401(client):
    response = client.get("/v1/chat/sessions")
    assert response.status_code == 401


def test_invalid_account_token_returns_401(client):
    from normly_chat.dependencies import get_accounts_client
    from normly_chat.main import create_app

    app = create_app()
    app.dependency_overrides[get_accounts_client] = lambda: _FakeAccountsClient(None)
    from normly_chat.dependencies import get_session
    # Reuse the same db_session override the `client` fixture already set up.
    app.dependency_overrides[get_session] = client.app.dependency_overrides[get_session]

    from fastapi.testclient import TestClient
    with TestClient(app) as raising_client:
        response = raising_client.get(
            "/v1/chat/sessions", headers={"Authorization": "Bearer not-a-real-token"},
        )
    assert response.status_code == 401


def test_returns_only_the_authenticated_accounts_sessions(client, db_session):
    from normly_core.graph.postgres.repositories import (
        PostgresAccountRepository,
        PostgresChatRepository,
    )
    from datetime import datetime, timezone

    account = PostgresAccountRepository(db_session).create_account(
        email="sessions-router@example.de", password_hash=None,
    )
    other_account = PostgresAccountRepository(db_session).create_account(
        email="sessions-router-other@example.de", password_hash=None,
    )
    chat_repo = PostgresChatRepository(db_session)
    mine = chat_repo.create_session(
        session_token="mine-tok", jurisdiction="DE", language="de",
        created_at=datetime.now(timezone.utc), account_id=account.id,
    )
    chat_repo.create_session(
        session_token="theirs-tok", jurisdiction="DE", language="de",
        created_at=datetime.now(timezone.utc), account_id=other_account.id,
    )

    from normly_chat.dependencies import get_accounts_client
    identity = ChatAccountIdentity(account_id=account.id, email=account.email)
    client.app.dependency_overrides[get_accounts_client] = lambda: _FakeAccountsClient(identity)

    response = client.get(
        "/v1/chat/sessions", headers={"Authorization": "Bearer whatever-the-fake-accepts"},
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["session_token"] == mine.session_token
```

- [ ] **Step 9: Run the test to verify it fails**

Run: `cd chat && .venv/bin/python -m pytest tests/test_sessions_router.py -v`
Expected: FAIL — no `/v1/chat/sessions` route exists yet.

- [ ] **Step 10: Add the schema and router**

Add to `chat/src/normly_chat/schemas.py`, after `ChatResponse`:

```python
class ChatSessionSummary(BaseModel):
    id: uuid.UUID
    session_token: str
    jurisdiction: str
    language: str
    created_at: datetime
```

Add `from datetime import datetime` to the top of `schemas.py` if not already imported.

```python
# chat/src/normly_chat/routers/sessions.py
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from normly_core.graph.postgres.repositories import PostgresChatRepository

from normly_chat.accounts_client import AccountsClient
from normly_chat.dependencies import get_accounts_client, get_session
from normly_chat.schemas import ChatSessionSummary

sessions_router = APIRouter(prefix="/v1/chat", tags=["sessions"])

_BEARER_PREFIX = "Bearer "


@sessions_router.get("/sessions", response_model=list[ChatSessionSummary])
def list_sessions(
    authorization: str | None = Header(default=None),
    session: Session = Depends(get_session),
    accounts_client: AccountsClient = Depends(get_accounts_client),
) -> list[ChatSessionSummary]:
    # Unlike the main /v1/chat endpoint, an account token is REQUIRED here,
    # not optional -- listing sessions is inherently an account-only
    # operation (REQ-ACC-004 lists "gespeicherte Verläufe" as account-gated).
    if authorization is None or not (
        authorization[:len(_BEARER_PREFIX)].lower() == _BEARER_PREFIX.lower()
    ):
        raise HTTPException(status_code=401, detail="account session required")
    account_token = authorization[len(_BEARER_PREFIX):]

    identity = accounts_client.validate_session(account_token)
    if identity is None:
        raise HTTPException(status_code=401, detail="account session required")

    chat_repo = PostgresChatRepository(session)
    sessions = chat_repo.list_sessions_for_account(identity.account_id)
    return [
        ChatSessionSummary(
            id=s.id, session_token=s.session_token, jurisdiction=s.jurisdiction,
            language=s.language, created_at=s.created_at,
        )
        for s in sessions
    ]
```

- [ ] **Step 11: Mount the router**

Add to `chat/src/normly_chat/main.py`:

```python
from normly_chat.routers.sessions import sessions_router
```

and, in `create_app()`, next to the existing `app.include_router(chat_router, ...)` line:

```python
    app.include_router(sessions_router, responses=COMMON_ERROR_RESPONSES)
```

- [ ] **Step 12: Run the tests**

Run: `cd chat && .venv/bin/python -m pytest tests/test_sessions_router.py -v`
Expected: PASS.

- [ ] **Step 13: Run the full chat suite**

Run: `cd chat && .venv/bin/python -m pytest -v -W error -rs`
Expected: all pass (Ollama-gated tests still skip, as before).

- [ ] **Step 14: Commit**

```bash
git add chat/src/normly_chat/routers/sessions.py chat/src/normly_chat/schemas.py \
  chat/src/normly_chat/main.py chat/tests/test_sessions_router.py
git commit -s -m "feat: add GET /v1/chat/sessions for account-linked history"
```

---

### Task 2: Next.js app scaffold and PWA basics

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/tsconfig.json`
- Create: `frontend/next.config.ts`
- Create: `frontend/tailwind.config.ts`
- Create: `frontend/postcss.config.js`
- Create: `frontend/src/app/globals.css`
- Create: `frontend/src/app/layout.tsx`
- Create: `frontend/src/app/page.tsx`
- Create: `frontend/public/manifest.webmanifest`
- Create: `frontend/public/icon-192.png`, `frontend/public/icon-512.png` (placeholder icons)
- Create: `frontend/public/service-worker.js`
- Create: `frontend/vitest.config.ts`
- Test: `frontend/tests/unit/smoke.test.tsx`

**Interfaces:**
- Consumes: nothing (first frontend task).
- Produces: a booting Next.js app at `frontend/`, the `src/app/`, `src/components/`,
  `src/lib/` directory layout every later task builds into.

- [ ] **Step 1: Create `package.json`**

```json
{
  "name": "normly-frontend",
  "version": "0.1.0",
  "private": true,
  "license": "AGPL-3.0-or-later",
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start",
    "test": "vitest run",
    "test:e2e": "playwright test"
  },
  "dependencies": {
    "next": "^14.2.0",
    "react": "^18.3.0",
    "react-dom": "^18.3.0"
  },
  "devDependencies": {
    "typescript": "^5.4.0",
    "@types/node": "^20.14.0",
    "@types/react": "^18.3.0",
    "@types/react-dom": "^18.3.0",
    "tailwindcss": "^3.4.0",
    "postcss": "^8.4.0",
    "autoprefixer": "^10.4.0",
    "vitest": "^1.6.0",
    "@vitejs/plugin-react": "^4.3.0",
    "jsdom": "^24.1.0",
    "@testing-library/react": "^15.0.0",
    "@testing-library/jest-dom": "^6.4.0",
    "@playwright/test": "^1.45.0",
    "@axe-core/playwright": "^4.9.0"
  }
}
```

- [ ] **Step 2: Create `tsconfig.json`**

```json
{
  "compilerOptions": {
    "target": "ES2020",
    "lib": ["dom", "dom.iterable", "esnext"],
    "allowJs": false,
    "skipLibCheck": true,
    "strict": true,
    "noEmit": true,
    "esModuleInterop": true,
    "module": "esnext",
    "moduleResolution": "bundler",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "jsx": "preserve",
    "incremental": true,
    "plugins": [{ "name": "next" }],
    "paths": { "@/*": ["./src/*"] }
  },
  "include": ["next-env.d.ts", "**/*.ts", "**/*.tsx", ".next/types/**/*.ts"],
  "exclude": ["node_modules"]
}
```

- [ ] **Step 3: Create `next.config.ts`**

```typescript
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
```

- [ ] **Step 4: Create Tailwind and PostCSS config**

```typescript
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
```

```javascript
// frontend/postcss.config.js
module.exports = {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
  },
};
```

- [ ] **Step 5: Create `globals.css`**

```css
/* frontend/src/app/globals.css */
@tailwind base;
@tailwind components;
@tailwind utilities;

:root {
  /* Default brand colors -- overridden at runtime by Task 4's theming
     system, never baked into the build (a single image serves any
     instance's own colors). */
  --brand: 222 89% 55%;
  --brand-foreground: 0 0% 100%;
}
```

- [ ] **Step 6: Create the root layout and home page**

```tsx
// frontend/src/app/layout.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "normly",
  description: "Normen- und Regelwerkswissen im Dialog",
  manifest: "/manifest.webmanifest",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="de">
      <body>{children}</body>
    </html>
  );
}
```

```tsx
// frontend/src/app/page.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

export default function HomePage() {
  return <main>normly</main>;
}
```

(This placeholder home page is deliberately minimal — Task 8 replaces it with the real chat
UI. A step this early only needs the app to boot.)

- [ ] **Step 7: Create the PWA manifest and a minimal service worker**

```json
// frontend/public/manifest.webmanifest
{
  "name": "normly",
  "short_name": "normly",
  "description": "Normen- und Regelwerkswissen im Dialog",
  "start_url": "/",
  "display": "standalone",
  "background_color": "#ffffff",
  "theme_color": "#1d4ed8",
  "icons": [
    { "src": "/icon-192.png", "sizes": "192x192", "type": "image/png" },
    { "src": "/icon-512.png", "sizes": "512x512", "type": "image/png" }
  ]
}
```

Create two placeholder PNG icons (`frontend/public/icon-192.png`, `icon-512.png`) — any valid
192x192 and 512x512 PNG works for now (a solid-color square is fine); Task 4's theming work
replaces these with instance-configurable icons if that becomes a real need, tracked as an
open point, not solved here.

```javascript
// frontend/public/service-worker.js
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

// App-shell caching only -- no push-event handler. Real Web Push delivery
// depends on Google FCM / Apple APNs (see the design spec's "Entschieden
// mit dem Auftraggeber" Punkt 5), deliberately out of scope. A future
// push handler would live in this same file without needing a rewrite.
//
// Plain JavaScript, not TypeScript: this file is served as-is from
// public/ (Next.js does not run it through its own build/bundle step),
// so a compiled .ts source would just be a second copy to keep in sync --
// simpler and less drift-prone to write it directly as the file that ships.

const CACHE_NAME = "normly-shell-v1";
const SHELL_ASSETS = ["/", "/manifest.webmanifest"];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE_NAME).then((cache) => cache.addAll(SHELL_ASSETS)));
});

self.addEventListener("fetch", (event) => {
  event.respondWith(
    caches.match(event.request).then((cached) => cached ?? fetch(event.request)),
  );
});
```

Register it in `layout.tsx` — add a small client component:

```tsx
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
```

Update `layout.tsx`'s `<body>` to render it:

```tsx
      <body>
        <ServiceWorkerRegistration />
        {children}
      </body>
```

(Add `import { ServiceWorkerRegistration } from "@/components/service-worker-registration";`
at the top.)

- [ ] **Step 8: Create the Vitest config and a smoke test**

```typescript
// frontend/vitest.config.ts
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import path from "path";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    setupFiles: ["./tests/unit/setup.ts"],
  },
  resolve: {
    alias: { "@": path.resolve(__dirname, "./src") },
  },
});
```

```typescript
// frontend/tests/unit/setup.ts
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import "@testing-library/jest-dom/vitest";
```

```tsx
// frontend/tests/unit/smoke.test.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import HomePage from "@/app/page";

describe("HomePage", () => {
  it("renders without crashing", () => {
    render(<HomePage />);
    expect(screen.getByText("normly")).toBeInTheDocument();
  });
});
```

- [ ] **Step 9: Install dependencies**

```bash
cd frontend
npm install
```

- [ ] **Step 10: Run the smoke test**

Run: `cd frontend && npm test`
Expected: PASS.

- [ ] **Step 11: Verify the app builds**

Run: `cd frontend && npm run build`
Expected: build succeeds with no type errors.

- [ ] **Step 12: Commit**

```bash
git add frontend/
git commit -s -m "feat: scaffold the Next.js frontend app"
```

---

### Task 3: shadcn/ui setup and base components

**Files:**
- Create: `frontend/components.json`
- Create: `frontend/src/lib/utils.ts`
- Create: `frontend/src/components/ui/button.tsx`
- Create: `frontend/src/components/ui/input.tsx`
- Create: `frontend/src/components/ui/dialog.tsx`
- Create: `frontend/src/components/ui/tabs.tsx`
- Test: `frontend/tests/unit/button.test.tsx`

**Interfaces:**
- Consumes: Task 2's scaffold (Tailwind config, `@/*` path alias).
- Produces: `Button`, `Input`, `Dialog`/`DialogContent`/`DialogTrigger`, `Tabs`/`TabsList`/
  `TabsTrigger`/`TabsContent` components under `@/components/ui/*` — consumed by Task 8
  (chat UI), Task 10 (auth dialog).

shadcn/ui ships as a CLI that copies component source into the repository (no runtime
dependency on an external service) — these are its officially-generated component files for
the four primitives this plan needs, added directly rather than run interactively, so the
exact content is reproducible.

- [ ] **Step 1: Add Radix UI primitives as dependencies**

Add to `frontend/package.json`'s `dependencies`:

```json
    "@radix-ui/react-dialog": "^1.1.0",
    "@radix-ui/react-tabs": "^1.1.0",
    "@radix-ui/react-slot": "^1.1.0",
    "class-variance-authority": "^0.7.0",
    "clsx": "^2.1.0",
    "tailwind-merge": "^2.4.0",
    "lucide-react": "^0.400.0"
```

Run `cd frontend && npm install` after adding them.

- [ ] **Step 2: Create `components.json` and `lib/utils.ts`**

```json
// frontend/components.json
{
  "$schema": "https://ui.shadcn.com/schema.json",
  "style": "default",
  "rsc": true,
  "tsx": true,
  "tailwind": {
    "config": "tailwind.config.ts",
    "css": "src/app/globals.css",
    "baseColor": "slate",
    "cssVariables": true
  },
  "aliases": {
    "components": "@/components",
    "utils": "@/lib/utils"
  }
}
```

```typescript
// frontend/src/lib/utils.ts
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
```

- [ ] **Step 3: Add the four base components (shadcn/ui's standard generated content)**

```tsx
// frontend/src/components/ui/button.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center whitespace-nowrap rounded-md text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50",
  {
    variants: {
      variant: {
        default: "bg-brand text-brand-foreground hover:opacity-90",
        outline: "border border-input bg-background hover:bg-accent",
        ghost: "hover:bg-accent hover:text-accent-foreground",
      },
      size: {
        default: "h-10 px-4 py-2",
        sm: "h-9 rounded-md px-3",
        lg: "h-11 rounded-md px-8",
      },
    },
    defaultVariants: { variant: "default", size: "default" },
  },
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : "button";
    return (
      <Comp className={cn(buttonVariants({ variant, size, className }))} ref={ref} {...props} />
    );
  },
);
Button.displayName = "Button";

export { Button, buttonVariants };
```

```tsx
// frontend/src/components/ui/input.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import * as React from "react";
import { cn } from "@/lib/utils";

export type InputProps = React.InputHTMLAttributes<HTMLInputElement>;

const Input = React.forwardRef<HTMLInputElement, InputProps>(
  ({ className, type, ...props }, ref) => (
    <input
      type={type}
      className={cn(
        "flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand disabled:cursor-not-allowed disabled:opacity-50",
        className,
      )}
      ref={ref}
      {...props}
    />
  ),
);
Input.displayName = "Input";

export { Input };
```

```tsx
// frontend/src/components/ui/dialog.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

"use client";

import * as React from "react";
import * as DialogPrimitive from "@radix-ui/react-dialog";
import { X } from "lucide-react";
import { cn } from "@/lib/utils";

const Dialog = DialogPrimitive.Root;
const DialogTrigger = DialogPrimitive.Trigger;
const DialogPortal = DialogPrimitive.Portal;

const DialogOverlay = React.forwardRef<
  React.ElementRef<typeof DialogPrimitive.Overlay>,
  React.ComponentPropsWithoutRef<typeof DialogPrimitive.Overlay>
>(({ className, ...props }, ref) => (
  <DialogPrimitive.Overlay
    ref={ref}
    className={cn("fixed inset-0 z-50 bg-black/50", className)}
    {...props}
  />
));
DialogOverlay.displayName = DialogPrimitive.Overlay.displayName;

const DialogContent = React.forwardRef<
  React.ElementRef<typeof DialogPrimitive.Content>,
  React.ComponentPropsWithoutRef<typeof DialogPrimitive.Content>
>(({ className, children, ...props }, ref) => (
  <DialogPortal>
    <DialogOverlay />
    <DialogPrimitive.Content
      ref={ref}
      className={cn(
        "fixed left-1/2 top-1/2 z-50 w-full max-w-md -translate-x-1/2 -translate-y-1/2 rounded-lg border bg-background p-6 shadow-lg",
        className,
      )}
      {...props}
    >
      {children}
      <DialogPrimitive.Close className="absolute right-4 top-4 opacity-70 hover:opacity-100">
        <X className="h-4 w-4" />
        <span className="sr-only">Schließen</span>
      </DialogPrimitive.Close>
    </DialogPrimitive.Content>
  </DialogPortal>
));
DialogContent.displayName = DialogPrimitive.Content.displayName;

const DialogTitle = React.forwardRef<
  React.ElementRef<typeof DialogPrimitive.Title>,
  React.ComponentPropsWithoutRef<typeof DialogPrimitive.Title>
>(({ className, ...props }, ref) => (
  <DialogPrimitive.Title ref={ref} className={cn("text-lg font-semibold", className)} {...props} />
));
DialogTitle.displayName = DialogPrimitive.Title.displayName;

export { Dialog, DialogTrigger, DialogContent, DialogTitle };
```

```tsx
// frontend/src/components/ui/tabs.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

"use client";

import * as React from "react";
import * as TabsPrimitive from "@radix-ui/react-tabs";
import { cn } from "@/lib/utils";

const Tabs = TabsPrimitive.Root;

const TabsList = React.forwardRef<
  React.ElementRef<typeof TabsPrimitive.List>,
  React.ComponentPropsWithoutRef<typeof TabsPrimitive.List>
>(({ className, ...props }, ref) => (
  <TabsPrimitive.List
    ref={ref}
    className={cn("inline-flex h-10 items-center rounded-md bg-muted p-1", className)}
    {...props}
  />
));
TabsList.displayName = TabsPrimitive.List.displayName;

const TabsTrigger = React.forwardRef<
  React.ElementRef<typeof TabsPrimitive.Trigger>,
  React.ComponentPropsWithoutRef<typeof TabsPrimitive.Trigger>
>(({ className, ...props }, ref) => (
  <TabsPrimitive.Trigger
    ref={ref}
    className={cn(
      "inline-flex items-center justify-center rounded-sm px-3 py-1.5 text-sm font-medium data-[state=active]:bg-background data-[state=active]:shadow",
      className,
    )}
    {...props}
  />
));
TabsTrigger.displayName = TabsPrimitive.Trigger.displayName;

const TabsContent = React.forwardRef<
  React.ElementRef<typeof TabsPrimitive.Content>,
  React.ComponentPropsWithoutRef<typeof TabsPrimitive.Content>
>(({ className, ...props }, ref) => (
  <TabsPrimitive.Content ref={ref} className={cn("mt-4", className)} {...props} />
));
TabsContent.displayName = TabsPrimitive.Content.displayName;

export { Tabs, TabsList, TabsTrigger, TabsContent };
```

Add the missing CSS variables these components reference (`--background`, `--input`,
`--accent`, `--accent-foreground`, `--muted`) to `frontend/src/app/globals.css`'s `:root`
block:

```css
  --background: 0 0% 100%;
  --input: 220 13% 91%;
  --accent: 220 14% 96%;
  --accent-foreground: 220 9% 20%;
  --muted: 220 14% 96%;
```

And extend `tailwind.config.ts`'s `theme.extend.colors` to map them:

```typescript
        background: "hsl(var(--background) / <alpha-value>)",
        input: "hsl(var(--input) / <alpha-value>)",
        accent: "hsl(var(--accent) / <alpha-value>)",
        "accent-foreground": "hsl(var(--accent-foreground) / <alpha-value>)",
        muted: "hsl(var(--muted) / <alpha-value>)",
```

- [ ] **Step 4: Write a test proving the Button component renders and responds to clicks**

```tsx
// frontend/tests/unit/button.test.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { Button } from "@/components/ui/button";

describe("Button", () => {
  it("renders its label and calls onClick when clicked", () => {
    const onClick = vi.fn();
    render(<Button onClick={onClick}>Absenden</Button>);
    const button = screen.getByRole("button", { name: "Absenden" });
    fireEvent.click(button);
    expect(onClick).toHaveBeenCalledOnce();
  });

  it("is disabled and unclickable when the disabled prop is set", () => {
    const onClick = vi.fn();
    render(
      <Button onClick={onClick} disabled>
        Absenden
      </Button>,
    );
    fireEvent.click(screen.getByRole("button", { name: "Absenden" }));
    expect(onClick).not.toHaveBeenCalled();
  });
});
```

- [ ] **Step 5: Run the tests**

Run: `cd frontend && npm test`
Expected: PASS.

- [ ] **Step 6: Verify the build still succeeds**

Run: `cd frontend && npm run build`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add frontend/
git commit -s -m "feat: add shadcn/ui base components (button, input, dialog, tabs)"
```

---

### Task 4: Theming/white-label configuration

**Files:**
- Create: `frontend/src/lib/config.ts`
- Modify: `frontend/src/app/layout.tsx`
- Test: `frontend/tests/unit/config.test.ts`

**Interfaces:**
- Consumes: nothing new.
- Produces: `getInstanceConfig() -> InstanceConfig` (brand color, logo path, instance name) —
  consumed by `layout.tsx` (this task) and any later component that needs the logo/name.

`REQ-UI-001` requires colors/typography/logo to be configurable per instance without a
rebuild. Implementation: environment variables read at request time (Next.js Server
Components re-evaluate `process.env` per request in `standalone` mode — no build-time
inlining for anything read inside a Server Component function body, unlike `NEXT_PUBLIC_*`
variables which ARE inlined at build time and must be avoided here for exactly that reason).

- [ ] **Step 1: Write the failing test**

```typescript
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
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd frontend && npm test`
Expected: FAIL — `@/lib/config` doesn't exist yet.

- [ ] **Step 3: Write the implementation**

```typescript
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
```

- [ ] **Step 4: Inject the configuration into the layout**

Update `frontend/src/app/layout.tsx`:

```tsx
// frontend/src/app/layout.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import type { Metadata } from "next";
import { getInstanceConfig } from "@/lib/config";
import { ServiceWorkerRegistration } from "@/components/service-worker-registration";
import "./globals.css";

export function generateMetadata(): Metadata {
  const config = getInstanceConfig();
  return {
    title: config.instanceName,
    description: "Normen- und Regelwerkswissen im Dialog",
    manifest: "/manifest.webmanifest",
  };
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  const config = getInstanceConfig();
  return (
    <html lang="de" style={{ "--brand": config.brandColorHsl } as React.CSSProperties}>
      <body>
        <ServiceWorkerRegistration />
        {children}
      </body>
    </html>
  );
}
```

(Setting `--brand` via inline `style` on `<html>` overrides `globals.css`'s default at
runtime, per-instance, without a rebuild — the CSS custom property cascade does the rest, since
every Tailwind color that reads `var(--brand)` picks up the override automatically.)

- [ ] **Step 5: Run the tests**

Run: `cd frontend && npm test`
Expected: PASS.

- [ ] **Step 6: Verify the build still succeeds**

Run: `cd frontend && npm run build`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/lib/config.ts frontend/src/app/layout.tsx frontend/tests/unit/config.test.ts
git commit -s -m "feat: add runtime instance theming configuration"
```

---

### Task 5: Internationalization (DE/EN)

**Files:**
- Create: `frontend/src/lib/i18n/de.json`
- Create: `frontend/src/lib/i18n/en.json`
- Create: `frontend/src/lib/i18n/provider.tsx`
- Create: `frontend/src/lib/i18n/dictionary-keys.ts`
- Create: `frontend/src/components/locale-switcher.tsx`
- Modify: `frontend/src/app/layout.tsx`
- Test: `frontend/tests/unit/i18n.test.tsx`

**Interfaces:**
- Consumes: nothing new (locale cookie is read server-side in `layout.tsx`).
- Produces: `LocaleProvider`, `useTranslation() -> { t, locale, dictionary }` React hook,
  `LocaleSwitcher` component — consumed by every later UI task (Task 8 chat UI, Task 10 auth
  dialog, Task 11 history page) for all user-facing text.

- [ ] **Step 1: Write the failing test**

```tsx
// frontend/tests/unit/i18n.test.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { LocaleProvider, useTranslation } from "@/lib/i18n/provider";
import de from "@/lib/i18n/de.json";
import en from "@/lib/i18n/en.json";

function Probe() {
  const { t } = useTranslation();
  return <span>{t("chat.sendButton")}</span>;
}

describe("i18n", () => {
  it("renders the German string by default", () => {
    render(
      <LocaleProvider initialLocale="de">
        <Probe />
      </LocaleProvider>,
    );
    expect(screen.getByText(de.chat.sendButton)).toBeInTheDocument();
  });

  it("renders the English string when initialised with locale=en", () => {
    render(
      <LocaleProvider initialLocale="en">
        <Probe />
      </LocaleProvider>,
    );
    expect(screen.getByText(en.chat.sendButton)).toBeInTheDocument();
  });

  it("has an identical key structure in both dictionaries", () => {
    const flatten = (obj: object, prefix = ""): string[] =>
      Object.entries(obj).flatMap(([key, value]) =>
        typeof value === "object" && value !== null
          ? flatten(value, `${prefix}${key}.`)
          : [`${prefix}${key}`],
      );
    expect(flatten(de).sort()).toEqual(flatten(en).sort());
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd frontend && npm test`
Expected: FAIL — `@/lib/i18n/provider` doesn't exist yet.

- [ ] **Step 3: Write the dictionaries**

```json
// frontend/src/lib/i18n/de.json
{
  "chat": {
    "sendButton": "Senden",
    "inputPlaceholder": "Frage stellen…",
    "loading": "Antwort wird geladen…",
    "historyLink": "Verlauf"
  },
  "auth": {
    "loginTab": "Anmelden",
    "registerTab": "Registrieren",
    "magicLinkTab": "Magic-Link",
    "emailLabel": "E-Mail-Adresse",
    "passwordLabel": "Passwort",
    "loginButton": "Anmelden",
    "registerButton": "Konto erstellen",
    "magicLinkButton": "Anmeldelink senden",
    "googleButton": "Mit Google anmelden",
    "genericError": "Das hat leider nicht funktioniert. Bitte versuche es erneut."
  },
  "history": {
    "title": "Chat-Verlauf",
    "empty": "Noch keine Chats vorhanden.",
    "loginRequired": "Melde dich an, um deinen Chat-Verlauf zu sehen."
  }
}
```

```json
// frontend/src/lib/i18n/en.json
{
  "chat": {
    "sendButton": "Send",
    "inputPlaceholder": "Ask a question…",
    "loading": "Loading answer…",
    "historyLink": "History"
  },
  "auth": {
    "loginTab": "Log in",
    "registerTab": "Register",
    "magicLinkTab": "Magic link",
    "emailLabel": "Email address",
    "passwordLabel": "Password",
    "loginButton": "Log in",
    "registerButton": "Create account",
    "magicLinkButton": "Send login link",
    "googleButton": "Sign in with Google",
    "genericError": "That didn't work. Please try again."
  },
  "history": {
    "title": "Chat history",
    "empty": "No chats yet.",
    "loginRequired": "Log in to see your chat history."
  }
}
```

- [ ] **Step 4: Write the key-path type helper**

```typescript
// frontend/src/lib/i18n/dictionary-keys.ts
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import de from "./de.json";

// Derives the set of valid "chat.sendButton"-style dotted paths straight
// from the German dictionary's shape, so t("chat.sendbutton") (a typo) is
// a compile error instead of a silent missing-key bug.
type Join<K extends string, P extends string> = P extends "" ? K : `${K}.${P}`;

type DictionaryPaths<T> = {
  [K in keyof T & string]: T[K] extends object ? Join<K, DictionaryPaths<T[K]>> : K;
}[keyof T & string];

export type TranslationKey = DictionaryPaths<typeof de>;
```

- [ ] **Step 5: Write the provider and hook**

```tsx
// frontend/src/lib/i18n/provider.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

"use client";

import * as React from "react";
import de from "./de.json";
import en from "./en.json";
import type { TranslationKey } from "./dictionary-keys";

const DICTIONARIES = { de, en } as const;
export type Locale = keyof typeof DICTIONARIES;

interface LocaleContextValue {
  locale: Locale;
  setLocale: (locale: Locale) => void;
  t: (key: TranslationKey) => string;
}

const LocaleContext = React.createContext<LocaleContextValue | null>(null);

function lookup(dictionary: object, key: string): string {
  const value = key.split(".").reduce<unknown>((node, part) => {
    if (node && typeof node === "object" && part in node) {
      return (node as Record<string, unknown>)[part];
    }
    return undefined;
  }, dictionary);
  // A key present in the TranslationKey type is always present in both
  // dictionaries (Step 3's test pins this) -- reaching `undefined` here
  // would mean the dictionaries drifted out of sync at runtime, not a
  // normal user-facing condition, so falling back to the raw key (rather
  // than throwing) keeps the UI readable while surfacing the bug visibly.
  return typeof value === "string" ? value : key;
}

export function LocaleProvider({
  children,
  initialLocale,
}: {
  children: React.ReactNode;
  initialLocale: Locale;
}) {
  const [locale, setLocaleState] = React.useState<Locale>(initialLocale);

  const setLocale = React.useCallback((next: Locale) => {
    setLocaleState(next);
    document.cookie = `normly_locale=${next}; path=/; max-age=${60 * 60 * 24 * 365}; samesite=lax`;
  }, []);

  const t = React.useCallback(
    (key: TranslationKey) => lookup(DICTIONARIES[locale], key),
    [locale],
  );

  const value = React.useMemo(() => ({ locale, setLocale, t }), [locale, setLocale, t]);

  return <LocaleContext.Provider value={value}>{children}</LocaleContext.Provider>;
}

export function useTranslation(): LocaleContextValue {
  const context = React.useContext(LocaleContext);
  if (context === null) {
    throw new Error("useTranslation must be used within a LocaleProvider");
  }
  return context;
}
```

- [ ] **Step 6: Write the locale switcher and wire the provider into the layout**

```tsx
// frontend/src/components/locale-switcher.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

"use client";

import { useTranslation } from "@/lib/i18n/provider";
import { Button } from "@/components/ui/button";

export function LocaleSwitcher() {
  const { locale, setLocale } = useTranslation();
  const other = locale === "de" ? "en" : "de";
  return (
    <Button variant="ghost" size="sm" onClick={() => setLocale(other)}>
      {other.toUpperCase()}
    </Button>
  );
}
```

Update `frontend/src/app/layout.tsx` to read the `normly_locale` cookie server-side (default
from `Accept-Language` when absent) and wrap `children` in `LocaleProvider`:

```tsx
// frontend/src/app/layout.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import type { Metadata } from "next";
import { cookies, headers } from "next/headers";
import { getInstanceConfig } from "@/lib/config";
import { ServiceWorkerRegistration } from "@/components/service-worker-registration";
import { LocaleProvider, type Locale } from "@/lib/i18n/provider";
import "./globals.css";

export function generateMetadata(): Metadata {
  const config = getInstanceConfig();
  return {
    title: config.instanceName,
    description: "Normen- und Regelwerkswissen im Dialog",
    manifest: "/manifest.webmanifest",
  };
}

function resolveInitialLocale(): Locale {
  const cookieLocale = cookies().get("normly_locale")?.value;
  if (cookieLocale === "de" || cookieLocale === "en") {
    return cookieLocale;
  }
  const acceptLanguage = headers().get("accept-language") ?? "";
  return acceptLanguage.toLowerCase().startsWith("en") ? "en" : "de";
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  const config = getInstanceConfig();
  const initialLocale = resolveInitialLocale();
  return (
    <html
      lang={initialLocale}
      style={{ "--brand": config.brandColorHsl } as React.CSSProperties}
    >
      <body>
        <LocaleProvider initialLocale={initialLocale}>
          <ServiceWorkerRegistration />
          {children}
        </LocaleProvider>
      </body>
    </html>
  );
}
```

- [ ] **Step 7: Run the tests**

Run: `cd frontend && npm test`
Expected: PASS, including the dictionary-key-parity test.

- [ ] **Step 8: Verify the build still succeeds**

Run: `cd frontend && npm run build`
Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add frontend/src/lib/i18n/ frontend/src/components/locale-switcher.tsx frontend/src/app/layout.tsx \
  frontend/tests/unit/i18n.test.tsx
git commit -s -m "feat: add DE/EN internationalization (cookie-based, no URL prefix)"
```

---

### Task 6: Backend client wrappers and cookie helpers

**Files:**
- Create: `frontend/src/lib/backend-urls.ts`
- Create: `frontend/src/lib/session-cookies.ts`
- Test: `frontend/tests/unit/session-cookies.test.ts`

**Interfaces:**
- Consumes: nothing new.
- Produces: `getBackendUrls()`, `readSessionCookies(request)`, `applySessionCookies(response,
  {chatSessionToken?, accountSessionToken?})` — consumed by every Route Handler task (7, 9,
  11).

- [ ] **Step 1: Write the failing test**

```typescript
// frontend/tests/unit/session-cookies.test.ts
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { describe, expect, it } from "vitest";
import { NextRequest, NextResponse } from "next/server";
import { applySessionCookies, readSessionCookies } from "@/lib/session-cookies";

describe("session cookies", () => {
  it("reads no cookies from a request that has none", () => {
    const request = new NextRequest("http://localhost/api/chat");
    expect(readSessionCookies(request)).toEqual({
      chatSessionToken: null,
      accountSessionToken: null,
    });
  });

  it("reads both cookies when present", () => {
    const request = new NextRequest("http://localhost/api/chat", {
      headers: { cookie: "normly_session=chat-tok; normly_account_session=account-tok" },
    });
    expect(readSessionCookies(request)).toEqual({
      chatSessionToken: "chat-tok",
      accountSessionToken: "account-tok",
    });
  });

  it("sets the chat session cookie as httpOnly on the response", () => {
    const response = NextResponse.json({ ok: true });
    applySessionCookies(response, { chatSessionToken: "new-chat-tok" });
    const cookie = response.cookies.get("normly_session");
    expect(cookie?.value).toBe("new-chat-tok");
    expect(cookie?.httpOnly).toBe(true);
  });

  it("sets the account session cookie as httpOnly on the response", () => {
    const response = NextResponse.json({ ok: true });
    applySessionCookies(response, { accountSessionToken: "new-account-tok" });
    const cookie = response.cookies.get("normly_account_session");
    expect(cookie?.value).toBe("new-account-tok");
    expect(cookie?.httpOnly).toBe(true);
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd frontend && npm test`
Expected: FAIL — `@/lib/session-cookies` doesn't exist yet.

- [ ] **Step 3: Write the backend URL helper**

```typescript
// frontend/src/lib/backend-urls.ts
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

export interface BackendUrls {
  api: string;
  accounts: string;
  chat: string;
}

// Read per-request (not module-scope constants) so tests can stub env vars
// freely without import-order surprises, matching the pattern already used
// by lib/config.ts.
export function getBackendUrls(): BackendUrls {
  return {
    api: requireEnv("NORMLY_API_BASE_URL"),
    accounts: requireEnv("NORMLY_ACCOUNTS_BASE_URL"),
    chat: requireEnv("NORMLY_CHAT_BASE_URL"),
  };
}

function requireEnv(name: string): string {
  const value = process.env[name];
  if (!value) {
    throw new Error(`${name} is not set`);
  }
  return value;
}
```

- [ ] **Step 4: Write the cookie helpers**

```typescript
// frontend/src/lib/session-cookies.ts
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import type { NextRequest, NextResponse } from "next/server";

const CHAT_SESSION_COOKIE = "normly_session";
const ACCOUNT_SESSION_COOKIE = "normly_account_session";

// 30 days matches accounts/'s own sliding-window session lifetime
// (extended server-side on every successful /v1/accounts/session check);
// the cookie's own max-age is a client-side courtesy, not the source of
// truth -- the backend always re-validates the token regardless.
const ACCOUNT_COOKIE_MAX_AGE_SECONDS = 60 * 60 * 24 * 30;
// chat_session has no defined server-side TTL yet (tracked as an open
// point in the chat/ design) -- 90 days is a reasonable client-side
// default, not a claim about backend expiry.
const CHAT_COOKIE_MAX_AGE_SECONDS = 60 * 60 * 24 * 90;

export interface SessionCookies {
  chatSessionToken: string | null;
  accountSessionToken: string | null;
}

export function readSessionCookies(request: NextRequest): SessionCookies {
  return {
    chatSessionToken: request.cookies.get(CHAT_SESSION_COOKIE)?.value ?? null,
    accountSessionToken: request.cookies.get(ACCOUNT_SESSION_COOKIE)?.value ?? null,
  };
}

export function applySessionCookies(
  response: NextResponse,
  tokens: { chatSessionToken?: string; accountSessionToken?: string },
): void {
  const isProduction = process.env.NODE_ENV === "production";
  if (tokens.chatSessionToken) {
    response.cookies.set(CHAT_SESSION_COOKIE, tokens.chatSessionToken, {
      httpOnly: true,
      secure: isProduction,
      sameSite: "lax",
      path: "/",
      maxAge: CHAT_COOKIE_MAX_AGE_SECONDS,
    });
  }
  if (tokens.accountSessionToken) {
    response.cookies.set(ACCOUNT_SESSION_COOKIE, tokens.accountSessionToken, {
      httpOnly: true,
      secure: isProduction,
      sameSite: "lax",
      path: "/",
      maxAge: ACCOUNT_COOKIE_MAX_AGE_SECONDS,
    });
  }
}
```

- [ ] **Step 5: Run the tests**

Run: `cd frontend && npm test`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/lib/backend-urls.ts frontend/src/lib/session-cookies.ts \
  frontend/tests/unit/session-cookies.test.ts
git commit -s -m "feat: add backend URL and session-cookie helpers"
```

---

### Task 7: Chat Route Handler

**Files:**
- Create: `frontend/src/app/api/chat/route.ts`
- Test: `frontend/tests/unit/chat-route.test.ts`

**Interfaces:**
- Consumes: `getBackendUrls`, `readSessionCookies`, `applySessionCookies` (Task 6).
- Produces: `POST /api/chat` — consumed by Task 8 (chat UI).

- [ ] **Step 1: Write the failing test**

```typescript
// frontend/tests/unit/chat-route.test.ts
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { afterEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";
import { POST } from "@/app/api/chat/route";

const originalFetch = global.fetch;

describe("POST /api/chat", () => {
  afterEach(() => {
    global.fetch = originalFetch;
    vi.unstubAllEnvs();
  });

  it("forwards the request to chat/ and sets the returned session cookie", async () => {
    vi.stubEnv("NORMLY_CHAT_BASE_URL", "http://chat.internal");
    global.fetch = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          session_token: "new-session-token",
          answer: "Beispielantwort",
          answer_type: "synthesis",
          citations: [],
        }),
        { status: 200 },
      ),
    );

    const request = new NextRequest("http://localhost/api/chat", {
      method: "POST",
      body: JSON.stringify({ jurisdiction: "DE", language: "de", message: "Testfrage" }),
      headers: { "content-type": "application/json" },
    });

    const response = await POST(request);
    const body = await response.json();

    expect(global.fetch).toHaveBeenCalledWith(
      "http://chat.internal/v1/chat",
      expect.objectContaining({ method: "POST" }),
    );
    expect(body.answer).toBe("Beispielantwort");
    expect(response.cookies.get("normly_session")?.value).toBe("new-session-token");
  });

  it("forwards an existing account session cookie as an Authorization header", async () => {
    vi.stubEnv("NORMLY_CHAT_BASE_URL", "http://chat.internal");
    global.fetch = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          session_token: "tok", answer: "x", answer_type: "fallback", citations: [],
        }),
        { status: 200 },
      ),
    );

    const request = new NextRequest("http://localhost/api/chat", {
      method: "POST",
      body: JSON.stringify({ jurisdiction: "DE", language: "de", message: "Testfrage" }),
      headers: {
        "content-type": "application/json",
        cookie: "normly_account_session=my-account-token",
      },
    });

    await POST(request);

    const [, init] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(init.headers.Authorization).toBe("Bearer my-account-token");
  });

  it("passes through a 503 from chat/ without crashing", async () => {
    vi.stubEnv("NORMLY_CHAT_BASE_URL", "http://chat.internal");
    global.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: "service temporarily unavailable" }), {
        status: 503,
      }),
    );

    const request = new NextRequest("http://localhost/api/chat", {
      method: "POST",
      body: JSON.stringify({ jurisdiction: "DE", language: "de", message: "Testfrage" }),
      headers: { "content-type": "application/json" },
    });

    const response = await POST(request);
    expect(response.status).toBe(503);
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd frontend && npm test`
Expected: FAIL — the route doesn't exist yet.

- [ ] **Step 3: Write the route handler**

```typescript
// frontend/src/app/api/chat/route.ts
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { NextRequest, NextResponse } from "next/server";
import { getBackendUrls } from "@/lib/backend-urls";
import { applySessionCookies, readSessionCookies } from "@/lib/session-cookies";

export async function POST(request: NextRequest): Promise<NextResponse> {
  const payload = await request.json();
  const { chatSessionToken, accountSessionToken } = readSessionCookies(request);

  const headers: Record<string, string> = { "content-type": "application/json" };
  if (accountSessionToken) {
    headers.Authorization = `Bearer ${accountSessionToken}`;
  }

  const backendResponse = await fetch(`${getBackendUrls().chat}/v1/chat`, {
    method: "POST",
    headers,
    body: JSON.stringify({ ...payload, session_token: chatSessionToken }),
  });

  const body = await backendResponse.json();
  const response = NextResponse.json(body, { status: backendResponse.status });

  if (backendResponse.ok && typeof body.session_token === "string") {
    applySessionCookies(response, { chatSessionToken: body.session_token });
  }

  return response;
}
```

- [ ] **Step 4: Run the tests**

Run: `cd frontend && npm test`
Expected: PASS.

- [ ] **Step 5: Verify the build still succeeds**

Run: `cd frontend && npm run build`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/app/api/chat/route.ts frontend/tests/unit/chat-route.test.ts
git commit -s -m "feat: add the chat Route Handler (BFF for POST /v1/chat)"
```

---

### Task 8: Chat UI components and main page

**Files:**
- Create: `frontend/src/components/chat/message-list.tsx`
- Create: `frontend/src/components/chat/chat-input.tsx`
- Create: `frontend/src/components/chat/citation-chip.tsx`
- Modify: `frontend/src/app/page.tsx`
- Test: `frontend/tests/unit/chat-input.test.tsx`
- Test: `frontend/tests/unit/message-list.test.tsx`

**Interfaces:**
- Consumes: `useTranslation` (Task 5), `Button`/`Input` (Task 3), `POST /api/chat`
  (Task 7).
- Produces: the real `/` chat page — `REQ-UI-002` (input/loading), `REQ-UI-003` (citations).

- [ ] **Step 1: Write the failing tests**

```tsx
// frontend/tests/unit/chat-input.test.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { LocaleProvider } from "@/lib/i18n/provider";
import { ChatInput } from "@/components/chat/chat-input";

function renderWithLocale(ui: React.ReactElement) {
  return render(<LocaleProvider initialLocale="de">{ui}</LocaleProvider>);
}

describe("ChatInput", () => {
  it("calls onSend with the typed message when the send button is clicked", () => {
    const onSend = vi.fn();
    renderWithLocale(<ChatInput onSend={onSend} disabled={false} />);
    const textbox = screen.getByPlaceholderText("Frage stellen…");
    fireEvent.change(textbox, { target: { value: "Ist DIN EN ISO 9001 gültig?" } });
    fireEvent.click(screen.getByRole("button", { name: "Senden" }));
    expect(onSend).toHaveBeenCalledWith("Ist DIN EN ISO 9001 gültig?");
  });

  it("calls onSend when Enter is pressed", () => {
    const onSend = vi.fn();
    renderWithLocale(<ChatInput onSend={onSend} disabled={false} />);
    const textbox = screen.getByPlaceholderText("Frage stellen…");
    fireEvent.change(textbox, { target: { value: "Frage" } });
    fireEvent.keyDown(textbox, { key: "Enter" });
    expect(onSend).toHaveBeenCalledWith("Frage");
  });

  it("does not call onSend while disabled (e.g. a request is in flight)", () => {
    const onSend = vi.fn();
    renderWithLocale(<ChatInput onSend={onSend} disabled={true} />);
    fireEvent.click(screen.getByRole("button", { name: "Senden" }));
    expect(onSend).not.toHaveBeenCalled();
  });

  it("does not call onSend for an empty message", () => {
    const onSend = vi.fn();
    renderWithLocale(<ChatInput onSend={onSend} disabled={false} />);
    fireEvent.click(screen.getByRole("button", { name: "Senden" }));
    expect(onSend).not.toHaveBeenCalled();
  });
});
```

```tsx
// frontend/tests/unit/message-list.test.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { LocaleProvider } from "@/lib/i18n/provider";
import { MessageList, type ChatMessageView } from "@/components/chat/message-list";

describe("MessageList", () => {
  it("renders user and assistant messages with a citation link", () => {
    const messages: ChatMessageView[] = [
      { role: "user", content: "Ist DIN EN ISO 9001 gültig?" },
      {
        role: "assistant",
        content: "DIN EN ISO 9001 ist noch gültig.",
        citations: [{ documentId: "11111111-1111-1111-1111-111111111111", href: "https://example.de/norm" }],
      },
    ];
    render(
      <LocaleProvider initialLocale="de">
        <MessageList messages={messages} isLoading={false} />
      </LocaleProvider>,
    );
    expect(screen.getByText("Ist DIN EN ISO 9001 gültig?")).toBeInTheDocument();
    expect(screen.getByText("DIN EN ISO 9001 ist noch gültig.")).toBeInTheDocument();
    expect(screen.getByRole("link")).toHaveAttribute("href", "https://example.de/norm");
  });

  it("shows a loading indicator when isLoading is true", () => {
    render(
      <LocaleProvider initialLocale="de">
        <MessageList messages={[]} isLoading={true} />
      </LocaleProvider>,
    );
    expect(screen.getByText("Antwort wird geladen…")).toBeInTheDocument();
  });

  it("renders an assistant message without a citation link when resolution failed", () => {
    const messages: ChatMessageView[] = [
      { role: "assistant", content: "Fallback-Antwort ohne Quelle.", citations: [] },
    ];
    render(
      <LocaleProvider initialLocale="de">
        <MessageList messages={messages} isLoading={false} />
      </LocaleProvider>,
    );
    expect(screen.getByText("Fallback-Antwort ohne Quelle.")).toBeInTheDocument();
    expect(screen.queryByRole("link")).not.toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd frontend && npm test`
Expected: FAIL — the components don't exist yet.

- [ ] **Step 3: Write the components**

```tsx
// frontend/src/components/chat/chat-input.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

"use client";

import * as React from "react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { useTranslation } from "@/lib/i18n/provider";

export function ChatInput({
  onSend,
  disabled,
}: {
  onSend: (message: string) => void;
  disabled: boolean;
}) {
  const { t } = useTranslation();
  const [value, setValue] = React.useState("");

  const submit = () => {
    const trimmed = value.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed);
    setValue("");
  };

  return (
    <div className="flex gap-2">
      <Input
        value={value}
        onChange={(event) => setValue(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === "Enter") submit();
        }}
        placeholder={t("chat.inputPlaceholder")}
        disabled={disabled}
        aria-label={t("chat.inputPlaceholder")}
      />
      <Button onClick={submit} disabled={disabled}>
        {t("chat.sendButton")}
      </Button>
    </div>
  );
}
```

```tsx
// frontend/src/components/chat/citation-chip.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

export interface CitationView {
  documentId: string;
  // null when resolving the citation to a real link failed -- degrade to
  // plain text rather than hiding the citation entirely (REQ-UI-003 still
  // wants a reference shown; only the clickable link is best-effort).
  href: string | null;
}

export function CitationChip({ citation }: { citation: CitationView }) {
  if (!citation.href) {
    return <span className="text-xs text-muted-foreground">Quelle</span>;
  }
  return (
    <a
      href={citation.href}
      target="_blank"
      rel="noopener noreferrer"
      className="text-xs text-brand underline"
    >
      Quelle
    </a>
  );
}
```

```tsx
// frontend/src/components/chat/message-list.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { useTranslation } from "@/lib/i18n/provider";
import { CitationChip, type CitationView } from "@/components/chat/citation-chip";

export interface ChatMessageView {
  role: "user" | "assistant";
  content: string;
  citations?: CitationView[];
}

export function MessageList({
  messages,
  isLoading,
}: {
  messages: ChatMessageView[];
  isLoading: boolean;
}) {
  const { t } = useTranslation();
  return (
    <div className="flex flex-col gap-4" role="log" aria-live="polite">
      {messages.map((message, index) => (
        <div
          key={index}
          className={message.role === "user" ? "self-end text-right" : "self-start"}
        >
          <p>{message.content}</p>
          {message.citations && message.citations.length > 0 && (
            <div className="mt-1 flex gap-2">
              {message.citations.map((citation) => (
                <CitationChip key={citation.documentId} citation={citation} />
              ))}
            </div>
          )}
        </div>
      ))}
      {isLoading && <p aria-busy="true">{t("chat.loading")}</p>}
    </div>
  );
}
```

- [ ] **Step 4: Wire the main chat page**

```tsx
// frontend/src/app/page.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

"use client";

import * as React from "react";
import { MessageList, type ChatMessageView } from "@/components/chat/message-list";
import { ChatInput } from "@/components/chat/chat-input";

interface ChatApiResponse {
  answer: string;
  answer_type: "structural" | "synthesis" | "fallback";
  citations: { document_id: string; segment_id: string | null }[];
}

export default function HomePage() {
  const [messages, setMessages] = React.useState<ChatMessageView[]>([]);
  const [isLoading, setIsLoading] = React.useState(false);

  const sendMessage = async (message: string) => {
    setMessages((prev) => [...prev, { role: "user", content: message }]);
    setIsLoading(true);
    try {
      const response = await fetch("/api/chat", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ jurisdiction: "DE", language: "de", message }),
      });
      const body: ChatApiResponse = await response.json();
      const citations = await Promise.all(
        body.citations.map(async (citation) => {
          try {
            const documentResponse = await fetch(
              `/api/documents/${citation.document_id}?jurisdiction=DE`,
            );
            const document = await documentResponse.json();
            return { documentId: citation.document_id, href: document.source?.retrieval_path ?? null };
          } catch {
            return { documentId: citation.document_id, href: null };
          }
        }),
      );
      setMessages((prev) => [...prev, { role: "assistant", content: body.answer, citations }]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <main className="mx-auto flex max-w-2xl flex-col gap-4 p-4">
      <MessageList messages={messages} isLoading={isLoading} />
      <ChatInput onSend={sendMessage} disabled={isLoading} />
    </main>
  );
}
```

This references `/api/documents/{id}` — a small citation-resolution Route Handler that
proxies `GET {API_BASE_URL}/v1/documents/{id}?jurisdiction=...` from `api/`. Add it now (source
file at `src/app/api/documents/[id]/route.ts`, served at `/api/documents/{id}`):

```typescript
// frontend/src/app/api/documents/[id]/route.ts
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { NextRequest, NextResponse } from "next/server";
import { getBackendUrls } from "@/lib/backend-urls";

export async function GET(
  request: NextRequest,
  { params }: { params: { id: string } },
): Promise<NextResponse> {
  const jurisdiction = request.nextUrl.searchParams.get("jurisdiction") ?? "DE";
  const backendResponse = await fetch(
    `${getBackendUrls().api}/v1/documents/${params.id}?jurisdiction=${jurisdiction}`,
  );
  const body = await backendResponse.json();
  return NextResponse.json(body, { status: backendResponse.status });
}
```

- [ ] **Step 5: Run the tests**

Run: `cd frontend && npm test`
Expected: PASS.

- [ ] **Step 6: Verify the build still succeeds**

Run: `cd frontend && npm run build`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/chat/ frontend/src/app/page.tsx \
  frontend/src/app/api/documents/ frontend/tests/unit/chat-input.test.tsx \
  frontend/tests/unit/message-list.test.tsx
git commit -s -m "feat: add the chat UI and wire it to the chat Route Handler"
```

---

### Task 9: Auth Route Handlers

**Files:**
- Create: `frontend/src/app/api/auth/login/route.ts`
- Create: `frontend/src/app/api/auth/register/route.ts`
- Create: `frontend/src/app/api/auth/magic-link/request/route.ts`
- Create: `frontend/src/app/api/auth/magic-link/confirm/route.ts`
- Create: `frontend/src/app/api/auth/google/login/route.ts`
- Create: `frontend/src/app/api/auth/google/callback/route.ts`
- Create: `frontend/src/app/api/auth/session/route.ts`
- Test: `frontend/tests/unit/auth-routes.test.ts`

**Interfaces:**
- Consumes: `getBackendUrls`, `applySessionCookies` (Task 6).
- Produces: the six `/api/auth/*` endpoints — consumed by Task 10 (auth dialog).

- [ ] **Step 1: Write the failing tests**

```typescript
// frontend/tests/unit/auth-routes.test.ts
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { afterEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";
import { POST as login } from "@/app/api/auth/login/route";
import { POST as magicLinkRequest } from "@/app/api/auth/magic-link/request/route";
import { GET as session } from "@/app/api/auth/session/route";

const originalFetch = global.fetch;

describe("auth Route Handlers", () => {
  afterEach(() => {
    global.fetch = originalFetch;
    vi.unstubAllEnvs();
  });

  it("login sets the account session cookie on success", async () => {
    vi.stubEnv("NORMLY_ACCOUNTS_BASE_URL", "http://accounts.internal");
    global.fetch = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          session_token: "acct-tok",
          account: { id: "1", email: "a@example.de", email_verified: true },
        }),
        { status: 200 },
      ),
    );

    const request = new NextRequest("http://localhost/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ email: "a@example.de", password: "correct horse battery staple" }),
      headers: { "content-type": "application/json" },
    });
    const response = await login(request);

    expect(response.status).toBe(200);
    expect(response.cookies.get("normly_account_session")?.value).toBe("acct-tok");
  });

  it("login passes through a 401 without setting a cookie", async () => {
    vi.stubEnv("NORMLY_ACCOUNTS_BASE_URL", "http://accounts.internal");
    global.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: "invalid email or password" }), { status: 401 }),
    );

    const request = new NextRequest("http://localhost/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ email: "a@example.de", password: "wrong" }),
      headers: { "content-type": "application/json" },
    });
    const response = await login(request);

    expect(response.status).toBe(401);
    expect(response.cookies.get("normly_account_session")).toBeUndefined();
  });

  it("magic-link request forwards the payload without needing a cookie", async () => {
    vi.stubEnv("NORMLY_ACCOUNTS_BASE_URL", "http://accounts.internal");
    global.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ status: "if_the_account_exists_an_email_was_sent" }), {
        status: 200,
      }),
    );

    const request = new NextRequest("http://localhost/api/auth/magic-link/request", {
      method: "POST",
      body: JSON.stringify({ email: "a@example.de" }),
      headers: { "content-type": "application/json" },
    });
    const response = await magicLinkRequest(request);
    expect(response.status).toBe(200);
  });

  it("session check returns null-account for a missing cookie without calling the backend", async () => {
    global.fetch = vi.fn();
    const request = new NextRequest("http://localhost/api/auth/session");
    const response = await session(request);
    const body = await response.json();
    expect(body).toEqual({ account: null });
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it("session check returns the account for a valid cookie", async () => {
    vi.stubEnv("NORMLY_ACCOUNTS_BASE_URL", "http://accounts.internal");
    global.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ account_id: "1", email: "a@example.de" }), { status: 200 }),
    );

    const request = new NextRequest("http://localhost/api/auth/session", {
      headers: { cookie: "normly_account_session=acct-tok" },
    });
    const response = await session(request);
    const body = await response.json();
    expect(body.account).toEqual({ accountId: "1", email: "a@example.de" });
  });
});
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd frontend && npm test`
Expected: FAIL — the routes don't exist yet.

- [ ] **Step 3: Write the login, register, and magic-link routes**

```typescript
// frontend/src/app/api/auth/login/route.ts
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { NextRequest, NextResponse } from "next/server";
import { getBackendUrls } from "@/lib/backend-urls";
import { applySessionCookies } from "@/lib/session-cookies";

export async function POST(request: NextRequest): Promise<NextResponse> {
  const payload = await request.json();
  const backendResponse = await fetch(`${getBackendUrls().accounts}/v1/accounts/login`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(payload),
  });
  const body = await backendResponse.json();
  const response = NextResponse.json(body, { status: backendResponse.status });
  if (backendResponse.ok && typeof body.session_token === "string") {
    applySessionCookies(response, { accountSessionToken: body.session_token });
  }
  return response;
}
```

```typescript
// frontend/src/app/api/auth/register/route.ts
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { NextRequest, NextResponse } from "next/server";
import { getBackendUrls } from "@/lib/backend-urls";
import { applySessionCookies } from "@/lib/session-cookies";

export async function POST(request: NextRequest): Promise<NextResponse> {
  const payload = await request.json();
  const backendResponse = await fetch(`${getBackendUrls().accounts}/v1/accounts/register`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(payload),
  });
  const body = await backendResponse.json();
  const response = NextResponse.json(body, { status: backendResponse.status });
  if (backendResponse.ok && typeof body.session_token === "string") {
    applySessionCookies(response, { accountSessionToken: body.session_token });
  }
  return response;
}
```

```typescript
// frontend/src/app/api/auth/magic-link/request/route.ts
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { NextRequest, NextResponse } from "next/server";
import { getBackendUrls } from "@/lib/backend-urls";

export async function POST(request: NextRequest): Promise<NextResponse> {
  const payload = await request.json();
  const backendResponse = await fetch(
    `${getBackendUrls().accounts}/v1/accounts/magic-link/request`,
    {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(payload),
    },
  );
  const body = await backendResponse.json();
  return NextResponse.json(body, { status: backendResponse.status });
}
```

```typescript
// frontend/src/app/api/auth/magic-link/confirm/route.ts
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { NextRequest, NextResponse } from "next/server";
import { getBackendUrls } from "@/lib/backend-urls";
import { applySessionCookies } from "@/lib/session-cookies";

export async function POST(request: NextRequest): Promise<NextResponse> {
  const payload = await request.json();
  const backendResponse = await fetch(
    `${getBackendUrls().accounts}/v1/accounts/magic-link/confirm`,
    {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(payload),
    },
  );
  const body = await backendResponse.json();
  const response = NextResponse.json(body, { status: backendResponse.status });
  if (backendResponse.ok && typeof body.session_token === "string") {
    applySessionCookies(response, { accountSessionToken: body.session_token });
  }
  return response;
}
```

- [ ] **Step 4: Write the Google OAuth routes**

```typescript
// frontend/src/app/api/auth/google/login/route.ts
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { NextRequest, NextResponse } from "next/server";
import { getBackendUrls } from "@/lib/backend-urls";

// A plain redirect, not a fetch-and-relay: accounts/'s own /google/login
// itself redirects to Google, and the browser needs to follow that chain
// with a real navigation, not something a Route Handler can proxy through
// fetch().
export async function GET(): Promise<NextResponse> {
  return NextResponse.redirect(`${getBackendUrls().accounts}/v1/accounts/google/login`);
}
```

```typescript
// frontend/src/app/api/auth/google/callback/route.ts
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { NextRequest, NextResponse } from "next/server";
import { getBackendUrls } from "@/lib/backend-urls";
import { applySessionCookies } from "@/lib/session-cookies";

export async function GET(request: NextRequest): Promise<NextResponse> {
  const code = request.nextUrl.searchParams.get("code");
  const state = request.nextUrl.searchParams.get("state");
  const error = request.nextUrl.searchParams.get("error");

  const forwardedParams = new URLSearchParams();
  if (code) forwardedParams.set("code", code);
  if (state) forwardedParams.set("state", state);
  if (error) forwardedParams.set("error", error);

  const backendResponse = await fetch(
    `${getBackendUrls().accounts}/v1/accounts/google/callback?${forwardedParams.toString()}`,
  );
  const body = await backendResponse.json();

  if (!backendResponse.ok) {
    return NextResponse.redirect(new URL("/?auth_error=1", request.url));
  }

  const response = NextResponse.redirect(new URL("/", request.url));
  applySessionCookies(response, { accountSessionToken: body.session_token });
  return response;
}
```

- [ ] **Step 5: Write the session-check route**

```typescript
// frontend/src/app/api/auth/session/route.ts
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { NextRequest, NextResponse } from "next/server";
import { getBackendUrls } from "@/lib/backend-urls";
import { readSessionCookies } from "@/lib/session-cookies";

export async function GET(request: NextRequest): Promise<NextResponse> {
  const { accountSessionToken } = readSessionCookies(request);
  if (!accountSessionToken) {
    return NextResponse.json({ account: null });
  }

  const backendResponse = await fetch(`${getBackendUrls().accounts}/v1/accounts/session`, {
    headers: { Authorization: `Bearer ${accountSessionToken}` },
  });
  if (!backendResponse.ok) {
    return NextResponse.json({ account: null });
  }
  const body = await backendResponse.json();
  return NextResponse.json({ account: { accountId: body.account_id, email: body.email } });
}
```

- [ ] **Step 6: Run the tests**

Run: `cd frontend && npm test`
Expected: PASS.

- [ ] **Step 7: Verify the build still succeeds**

Run: `cd frontend && npm run build`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/app/api/auth/ frontend/tests/unit/auth-routes.test.ts
git commit -s -m "feat: add auth Route Handlers (login, register, magic-link, Google, session)"
```

---

### Task 10: Auth dialog UI

**Files:**
- Create: `frontend/src/components/auth/auth-dialog.tsx`
- Create: `frontend/src/components/auth/login-form.tsx`
- Create: `frontend/src/components/auth/register-form.tsx`
- Create: `frontend/src/components/auth/magic-link-form.tsx`
- Modify: `frontend/src/app/page.tsx`
- Test: `frontend/tests/unit/login-form.test.tsx`

**Interfaces:**
- Consumes: `Dialog`/`Tabs`/`Button`/`Input` (Task 3), `useTranslation` (Task 5), the
  `/api/auth/*` routes (Task 9).
- Produces: `AuthDialog` — mounted in the page header, consumed by no later task (this is the
  UI leaf for login).

- [ ] **Step 1: Write the failing test**

```tsx
// frontend/tests/unit/login-form.test.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { LocaleProvider } from "@/lib/i18n/provider";
import { LoginForm } from "@/components/auth/login-form";

const originalFetch = global.fetch;

describe("LoginForm", () => {
  afterEach(() => {
    global.fetch = originalFetch;
  });

  it("submits email and password to the login route and calls onSuccess", async () => {
    const onSuccess = vi.fn();
    global.fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify({}), { status: 200 }));

    render(
      <LocaleProvider initialLocale="de">
        <LoginForm onSuccess={onSuccess} />
      </LocaleProvider>,
    );

    fireEvent.change(screen.getByLabelText("E-Mail-Adresse"), {
      target: { value: "a@example.de" },
    });
    fireEvent.change(screen.getByLabelText("Passwort"), {
      target: { value: "correct horse battery staple" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Anmelden" }));

    await waitFor(() => expect(onSuccess).toHaveBeenCalled());
    expect(global.fetch).toHaveBeenCalledWith(
      "/api/auth/login",
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("shows a generic error message on a failed login without calling onSuccess", async () => {
    const onSuccess = vi.fn();
    global.fetch = vi
      .fn()
      .mockResolvedValue(new Response(JSON.stringify({ detail: "invalid" }), { status: 401 }));

    render(
      <LocaleProvider initialLocale="de">
        <LoginForm onSuccess={onSuccess} />
      </LocaleProvider>,
    );

    fireEvent.change(screen.getByLabelText("E-Mail-Adresse"), {
      target: { value: "a@example.de" },
    });
    fireEvent.change(screen.getByLabelText("Passwort"), { target: { value: "wrong" } });
    fireEvent.click(screen.getByRole("button", { name: "Anmelden" }));

    await waitFor(() =>
      expect(screen.getByText("Das hat leider nicht funktioniert. Bitte versuche es erneut.")).toBeInTheDocument(),
    );
    expect(onSuccess).not.toHaveBeenCalled();
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd frontend && npm test`
Expected: FAIL — `LoginForm` doesn't exist yet.

- [ ] **Step 3: Write the forms**

```tsx
// frontend/src/components/auth/login-form.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

"use client";

import * as React from "react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { useTranslation } from "@/lib/i18n/provider";

export function LoginForm({ onSuccess }: { onSuccess: () => void }) {
  const { t } = useTranslation();
  const [email, setEmail] = React.useState("");
  const [password, setPassword] = React.useState("");
  const [error, setError] = React.useState(false);
  const [isSubmitting, setIsSubmitting] = React.useState(false);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setError(false);
    setIsSubmitting(true);
    try {
      const response = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ email, password }),
      });
      if (response.ok) {
        onSuccess();
      } else {
        setError(true);
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <form onSubmit={submit} className="flex flex-col gap-3">
      <label className="flex flex-col gap-1 text-sm">
        {t("auth.emailLabel")}
        <Input
          type="email"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          required
        />
      </label>
      <label className="flex flex-col gap-1 text-sm">
        {t("auth.passwordLabel")}
        <Input
          type="password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          required
        />
      </label>
      {error && <p className="text-sm text-red-600">{t("auth.genericError")}</p>}
      <Button type="submit" disabled={isSubmitting}>
        {t("auth.loginButton")}
      </Button>
    </form>
  );
}
```

```tsx
// frontend/src/components/auth/register-form.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

"use client";

import * as React from "react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { useTranslation } from "@/lib/i18n/provider";

export function RegisterForm({ onSuccess }: { onSuccess: () => void }) {
  const { t } = useTranslation();
  const [email, setEmail] = React.useState("");
  const [password, setPassword] = React.useState("");
  const [error, setError] = React.useState(false);
  const [isSubmitting, setIsSubmitting] = React.useState(false);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setError(false);
    setIsSubmitting(true);
    try {
      const response = await fetch("/api/auth/register", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ email, password }),
      });
      if (response.ok) {
        onSuccess();
      } else {
        setError(true);
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <form onSubmit={submit} className="flex flex-col gap-3">
      <label className="flex flex-col gap-1 text-sm">
        {t("auth.emailLabel")}
        <Input
          type="email"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          required
        />
      </label>
      <label className="flex flex-col gap-1 text-sm">
        {t("auth.passwordLabel")}
        <Input
          type="password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          required
        />
      </label>
      {error && <p className="text-sm text-red-600">{t("auth.genericError")}</p>}
      <Button type="submit" disabled={isSubmitting}>
        {t("auth.registerButton")}
      </Button>
    </form>
  );
}
```

```tsx
// frontend/src/components/auth/magic-link-form.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

"use client";

import * as React from "react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { useTranslation } from "@/lib/i18n/provider";

export function MagicLinkForm() {
  const { t } = useTranslation();
  const [email, setEmail] = React.useState("");
  const [sent, setSent] = React.useState(false);
  const [isSubmitting, setIsSubmitting] = React.useState(false);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setIsSubmitting(true);
    try {
      await fetch("/api/auth/magic-link/request", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ email }),
      });
      // Enumeration-safe by design (accounts/'s own endpoint returns the
      // identical response for a known or unknown address) -- always show
      // the same "check your inbox" confirmation, never an error branch.
      setSent(true);
    } finally {
      setIsSubmitting(false);
    }
  };

  if (sent) {
    return <p className="text-sm">{t("auth.magicLinkButton")} ✓</p>;
  }

  return (
    <form onSubmit={submit} className="flex flex-col gap-3">
      <label className="flex flex-col gap-1 text-sm">
        {t("auth.emailLabel")}
        <Input
          type="email"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          required
        />
      </label>
      <Button type="submit" disabled={isSubmitting}>
        {t("auth.magicLinkButton")}
      </Button>
    </form>
  );
}
```

```tsx
// frontend/src/components/auth/auth-dialog.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

"use client";

import * as React from "react";
import { Dialog, DialogContent, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import { useTranslation } from "@/lib/i18n/provider";
import { LoginForm } from "@/components/auth/login-form";
import { RegisterForm } from "@/components/auth/register-form";
import { MagicLinkForm } from "@/components/auth/magic-link-form";

export function AuthDialog({ onAuthenticated }: { onAuthenticated: () => void }) {
  const { t } = useTranslation();
  const [open, setOpen] = React.useState(false);

  const handleSuccess = () => {
    setOpen(false);
    onAuthenticated();
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="outline">{t("auth.loginTab")}</Button>
      </DialogTrigger>
      <DialogContent>
        <DialogTitle>{t("auth.loginTab")}</DialogTitle>
        <Tabs defaultValue="login">
          <TabsList>
            <TabsTrigger value="login">{t("auth.loginTab")}</TabsTrigger>
            <TabsTrigger value="register">{t("auth.registerTab")}</TabsTrigger>
            <TabsTrigger value="magic-link">{t("auth.magicLinkTab")}</TabsTrigger>
          </TabsList>
          <TabsContent value="login">
            <LoginForm onSuccess={handleSuccess} />
          </TabsContent>
          <TabsContent value="register">
            <RegisterForm onSuccess={handleSuccess} />
          </TabsContent>
          <TabsContent value="magic-link">
            <MagicLinkForm />
          </TabsContent>
        </Tabs>
        <a href="/api/auth/google/login" className="text-center text-sm underline">
          {t("auth.googleButton")}
        </a>
      </DialogContent>
    </Dialog>
  );
}
```

- [ ] **Step 4: Mount the dialog in the page header**

Update `frontend/src/app/page.tsx` to add a header with `AuthDialog` and `LocaleSwitcher`
above the existing chat UI:

```tsx
import { AuthDialog } from "@/components/auth/auth-dialog";
import { LocaleSwitcher } from "@/components/locale-switcher";
```

and, inside the returned JSX, wrap the existing content:

```tsx
  return (
    <>
      <header className="flex items-center justify-between border-b p-4">
        <span className="font-semibold">normly</span>
        <div className="flex items-center gap-2">
          <LocaleSwitcher />
          <AuthDialog onAuthenticated={() => {}} />
        </div>
      </header>
      <main className="mx-auto flex max-w-2xl flex-col gap-4 p-4">
        <MessageList messages={messages} isLoading={isLoading} />
        <ChatInput onSend={sendMessage} disabled={isLoading} />
      </main>
    </>
  );
```

(`onAuthenticated`'s empty callback is intentional for this step — the chat page doesn't need
to react to login beyond what the next chat request already handles: the account-session
cookie set by the login route is automatically forwarded on the very next `POST
/api/chat`, per Task 7's route handler, which links the running session server-side. No
client-side re-fetch is needed here.)

- [ ] **Step 5: Run the tests**

Run: `cd frontend && npm test`
Expected: PASS.

- [ ] **Step 6: Verify the build still succeeds**

Run: `cd frontend && npm run build`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/auth/ frontend/src/app/page.tsx frontend/tests/unit/login-form.test.tsx
git commit -s -m "feat: add the login/register/magic-link/Google auth dialog"
```

---

### Task 11: Chat history page

**Files:**
- Create: `frontend/src/app/api/chat/sessions/route.ts`
- Create: `frontend/src/app/chats/page.tsx`
- Test: `frontend/tests/unit/sessions-route.test.ts`
- Test: `frontend/tests/unit/chats-page.test.tsx`

**Interfaces:**
- Consumes: `GET /v1/chat/sessions` (Task 1), `getBackendUrls`/`readSessionCookies` (Task 6),
  `useTranslation` (Task 5).
- Produces: the `/chats` page (`REQ-UI-005`) — the last frontend page this plan builds.

- [ ] **Step 1: Write the failing Route Handler test**

```typescript
// frontend/tests/unit/sessions-route.test.ts
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { afterEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";
import { GET } from "@/app/api/chat/sessions/route";

const originalFetch = global.fetch;

describe("GET /api/chat/sessions", () => {
  afterEach(() => {
    global.fetch = originalFetch;
    vi.unstubAllEnvs();
  });

  it("returns an empty list without calling the backend when there is no account cookie", async () => {
    global.fetch = vi.fn();
    const request = new NextRequest("http://localhost/api/chat/sessions");
    const response = await GET(request);
    const body = await response.json();
    expect(body).toEqual([]);
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it("forwards the account cookie as Authorization and returns the backend's list", async () => {
    vi.stubEnv("NORMLY_CHAT_BASE_URL", "http://chat.internal");
    global.fetch = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify([
          {
            id: "1", session_token: "tok-1", jurisdiction: "DE", language: "de",
            created_at: "2026-01-01T00:00:00Z",
          },
        ]),
        { status: 200 },
      ),
    );

    const request = new NextRequest("http://localhost/api/chat/sessions", {
      headers: { cookie: "normly_account_session=acct-tok" },
    });
    const response = await GET(request);
    const body = await response.json();

    expect(body).toHaveLength(1);
    const [, init] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(init.headers.Authorization).toBe("Bearer acct-tok");
  });
});
```

- [ ] **Step 2: Write the failing page test**

```tsx
// frontend/tests/unit/chats-page.test.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { LocaleProvider } from "@/lib/i18n/provider";
import { ChatsPageContent } from "@/app/chats/page";

const originalFetch = global.fetch;

describe("ChatsPageContent", () => {
  afterEach(() => {
    global.fetch = originalFetch;
  });

  it("shows the login-required message when there is no account session", async () => {
    global.fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify([]), { status: 401 }));
    render(
      <LocaleProvider initialLocale="de">
        <ChatsPageContent />
      </LocaleProvider>,
    );
    await waitFor(() =>
      expect(
        screen.getByText("Melde dich an, um deinen Chat-Verlauf zu sehen."),
      ).toBeInTheDocument(),
    );
  });

  it("shows an empty-state message when the account has no sessions yet", async () => {
    global.fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify([]), { status: 200 }));
    render(
      <LocaleProvider initialLocale="de">
        <ChatsPageContent />
      </LocaleProvider>,
    );
    await waitFor(() => expect(screen.getByText("Noch keine Chats vorhanden.")).toBeInTheDocument());
  });

  it("lists sessions with a link to reopen each one", async () => {
    global.fetch = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify([
          {
            id: "1", session_token: "tok-1", jurisdiction: "DE", language: "de",
            created_at: "2026-01-01T00:00:00Z",
          },
        ]),
        { status: 200 },
      ),
    );
    render(
      <LocaleProvider initialLocale="de">
        <ChatsPageContent />
      </LocaleProvider>,
    );
    await waitFor(() => expect(screen.getByRole("link")).toHaveAttribute("href", "/?session=tok-1"));
  });
});
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `cd frontend && npm test`
Expected: FAIL — the route and page don't exist yet.

- [ ] **Step 4: Write the sessions Route Handler**

```typescript
// frontend/src/app/api/chat/sessions/route.ts
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { NextRequest, NextResponse } from "next/server";
import { getBackendUrls } from "@/lib/backend-urls";
import { readSessionCookies } from "@/lib/session-cookies";

export async function GET(request: NextRequest): Promise<NextResponse> {
  const { accountSessionToken } = readSessionCookies(request);
  if (!accountSessionToken) {
    return NextResponse.json([]);
  }

  const backendResponse = await fetch(`${getBackendUrls().chat}/v1/chat/sessions`, {
    headers: { Authorization: `Bearer ${accountSessionToken}` },
  });
  if (!backendResponse.ok) {
    return NextResponse.json([], { status: backendResponse.status });
  }
  const body = await backendResponse.json();
  return NextResponse.json(body);
}
```

- [ ] **Step 5: Write the history page**

```tsx
// frontend/src/app/chats/page.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

"use client";

import * as React from "react";
import Link from "next/link";
import { useTranslation } from "@/lib/i18n/provider";

interface ChatSessionSummary {
  id: string;
  session_token: string;
  jurisdiction: string;
  language: string;
  created_at: string;
}

export function ChatsPageContent() {
  const { t } = useTranslation();
  const [sessions, setSessions] = React.useState<ChatSessionSummary[] | null>(null);
  const [requiresLogin, setRequiresLogin] = React.useState(false);

  React.useEffect(() => {
    let cancelled = false;
    fetch("/api/chat/sessions").then(async (response) => {
      if (cancelled) return;
      if (response.status === 401) {
        setRequiresLogin(true);
        return;
      }
      setSessions(await response.json());
    });
    return () => {
      cancelled = true;
    };
  }, []);

  if (requiresLogin) {
    return <p>{t("history.loginRequired")}</p>;
  }
  if (sessions === null) {
    return null;
  }
  if (sessions.length === 0) {
    return <p>{t("history.empty")}</p>;
  }

  return (
    <ul className="flex flex-col gap-2">
      {sessions.map((session) => (
        <li key={session.id}>
          <Link href={`/?session=${session.session_token}`} className="underline">
            {new Date(session.created_at).toLocaleDateString()}
          </Link>
        </li>
      ))}
    </ul>
  );
}

export default function ChatsPage() {
  const { t } = useTranslation();
  return (
    <main className="mx-auto max-w-2xl p-4">
      <h1 className="mb-4 text-xl font-semibold">{t("history.title")}</h1>
      <ChatsPageContent />
    </main>
  );
}
```

Note: `GET /api/chat/sessions` currently returns an empty array both for "not logged in"
and for "logged in with zero sessions" (see Step 4 — it returns `[]` on any non-2xx from the
backend, which includes the 401 the backend gives for a missing/invalid account token, but
also returns `[]`, status 200, when there's no cookie at all). Fix `ChatsPageContent` to tell
these apart: since Step 4's handler passes through the backend's actual status code on
failure (`status: backendResponse.status`), a 401 response IS distinguishable from a 200 with
an empty list — update the `fetch` handling above to check `response.status === 401` (already
shown correctly in the code above) rather than only checking the body. This is already
correct as written; call it out explicitly here so the distinction isn't lost during review.

- [ ] **Step 6: Run the tests**

Run: `cd frontend && npm test`
Expected: PASS.

- [ ] **Step 7: Verify the build still succeeds**

Run: `cd frontend && npm run build`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/app/api/chat/sessions/ frontend/src/app/chats/ \
  frontend/tests/unit/sessions-route.test.ts frontend/tests/unit/chats-page.test.tsx
git commit -s -m "feat: add the chat history page (/chats)"
```

---

### Task 12: Capstone — end-to-end tests and WCAG check

**Files:**
- Create: `frontend/playwright.config.ts`
- Create: `frontend/tests/e2e/chat-and-history.spec.ts`
- Create: `frontend/tests/e2e/accessibility.spec.ts`

**Interfaces:**
- Consumes: everything from Tasks 1-11, plus real `accounts/` and `chat/` processes. No new
  production code expected unless this reveals a real integration gap — if so, fix it in the
  task that owns the affected file.

- [ ] **Step 1: Write the Playwright config**

```typescript
// frontend/playwright.config.ts
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./tests/e2e",
  webServer: {
    command: "npm run build && npm run start",
    url: "http://localhost:3000",
    reuseExistingServer: false,
    timeout: 120_000,
  },
  use: { baseURL: "http://localhost:3000" },
});
```

- [ ] **Step 2: Write the end-to-end test**

This test needs real `accounts/` and `chat/` processes (same pattern already established in
`chat/tests/test_end_to_end.py`'s `api_process`/`accounts_process` fixtures) — start them
manually before running this task's tests, matching how earlier Python end-to-end tasks in
this project were verified:

```bash
# From accounts/, in one terminal:
NORMLY_DATABASE_URL=<test-db-url> .venv/bin/uvicorn normly_accounts.main:app --port 8002
# From chat/, in another terminal (needs api/ and accounts/ addresses too):
NORMLY_DATABASE_URL=<test-db-url> NORMLY_API_BASE_URL=http://localhost:8001 \
  NORMLY_ACCOUNTS_BASE_URL=http://localhost:8002 NORMLY_OLLAMA_BASE_URL=http://localhost:11434 \
  .venv/bin/uvicorn normly_chat.main:app --port 8003
```

```typescript
// frontend/tests/e2e/chat-and-history.spec.ts
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { test, expect } from "@playwright/test";

test.describe("registration, login, and chat history", () => {
  test("a new user can register, and their session survives a page reload", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("button", { name: "Anmelden" }).click();
    await page.getByRole("tab", { name: "Registrieren" }).click();

    const email = `e2e-${Date.now()}@example.de`;
    await page.getByLabel("E-Mail-Adresse").fill(email);
    await page.getByLabel("Passwort").fill("correct horse battery staple");
    await page.getByRole("button", { name: "Konto erstellen" }).click();

    // The dialog closes on success (AuthDialog's onSuccess handler).
    await expect(page.getByRole("dialog")).not.toBeVisible();

    await page.reload();
    const sessionResponse = await page.request.get("/api/auth/session");
    const sessionBody = await sessionResponse.json();
    expect(sessionBody.account?.email).toBe(email);
  });

  test("chat history is empty right after registration, then shows a session after chatting", async ({
    page,
  }) => {
    await page.goto("/");
    await page.getByRole("button", { name: "Anmelden" }).click();
    await page.getByRole("tab", { name: "Registrieren" }).click();
    const email = `e2e-history-${Date.now()}@example.de`;
    await page.getByLabel("E-Mail-Adresse").fill(email);
    await page.getByLabel("Passwort").fill("correct horse battery staple");
    await page.getByRole("button", { name: "Konto erstellen" }).click();
    await expect(page.getByRole("dialog")).not.toBeVisible();

    await page.goto("/chats");
    await expect(page.getByText("Noch keine Chats vorhanden.")).toBeVisible();
  });
});
```

(A full "ask a question, get a synthesis answer, see it in history" test needs a real Ollama
server, same as `chat/`'s own capstone — that variant is not written here to avoid a test this
plan cannot verify in this environment; note it as an open point for whoever has GPU access,
matching the precedent already set by `chat/tests/test_end_to_end.py`.)

- [ ] **Step 3: Write the accessibility test**

```typescript
// frontend/tests/e2e/accessibility.spec.ts
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

test("the chat page has no automatically detectable WCAG 2.1 AA violations", async ({ page }) => {
  await page.goto("/");
  const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze();
  expect(results.violations).toEqual([]);
});

test("the login dialog is keyboard-operable", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Anmelden" }).focus();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("dialog")).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).not.toBeVisible();
});
```

- [ ] **Step 4: Run the end-to-end suite**

Run: `cd frontend && npm run test:e2e`
Expected: PASS, given `accounts/` and `chat/` are running as described in Step 2. If Ollama
is unavailable, that's fine — none of the tests written here depend on it.

- [ ] **Step 5: Run the full unit suite one final time**

Run: `cd frontend && npm test`
Expected: all pass, pristine output.

- [ ] **Step 6: Run the full core and chat suites one final time**

Run: `cd core && .venv/bin/python -m pytest -v -W error`
Run: `cd chat && .venv/bin/python -m pytest -v -W error -rs`
Expected: all pass — this plan's Task 1 change must not have broken anything.

- [ ] **Step 7: Commit**

```bash
git add frontend/playwright.config.ts frontend/tests/e2e/
git commit -s -m "test: add end-to-end chat/history flows and a WCAG 2.1 AA check"
```

---

## Self-Review

**Spec coverage:**

| Spec-Abschnitt | Task |
|---|---|
| `REQ-UI-001` (eigenständige Oberfläche, Theming) | Task 4 |
| `REQ-UI-002` (Chat-Interaktion, Ladezustand) | Task 8 |
| `REQ-UI-003` (Quellenverlinkung) | Task 8 |
| `REQ-UI-004` (WCAG 2.1 AA) | Task 3 (Radix-Basis), Task 12 (axe-core-Prüfung) |
| `REQ-UI-005` (Chat-Historie) | Task 1 (Backend-Voraussetzung), Task 11 |
| `REQ-ACC-001`/`004` (anonym nutzbar, Historie kontopflichtig) | Task 9/10 (optionaler Login), Task 11 (Login-Pflicht nur für `/chats`) |
| `REQ-MOB-001`/`003` (PWA, Abstraktionsschicht) | Task 2 |
| Internationalisierung (DE/EN) | Task 5 |
| BFF/httpOnly-Cookie-Architektur | Task 6, 7, 9, 11 |
| Theming/White-Label | Task 4 |

Keine Lücke gefunden — jeder Abschnitt der Spec hat eine Entsprechung in mindestens einem
Task.

**Placeholder-Scan:** Kein „TBD"/„TODO" gefunden. Ein bewusster, benannter Nachtrag statt eines
Platzhalters: Task 12s voller Synthese-Antwort-Test gegen ein echtes LLM ist explizit als
außerhalb dieses Plans liegend benannt (kein Ollama-Zugang in dieser Umgebung verifizierbar),
mit demselben Muster wie `chat/`s eigener Kapstein-Test — kein „TODO", sondern eine begründete,
dokumentierte Abgrenzung.

**Typkonsistenz:** `ChatSessionSummary` (Task 1, Python-Pydantic-Schema) und die
TypeScript-Interface-Form in Task 11 (`ChatSessionSummary`) tragen dieselben Feldnamen
(`id`, `session_token`, `jurisdiction`, `language`, `created_at`) — geprüft gegen die
tatsächliche `chat/`-Antwortform. `useTranslation()`s `t`-Funktion wird in jeder UI-Komponente
ab Task 8 konsistent verwendet, nie ein hartkodierter deutscher String. Die Cookie-Namen
(`normly_session`, `normly_account_session`, `normly_locale`) stimmen zwischen Spec, Task 5
und Task 6 überein.

---

**Plan complete and saved to `docs/superpowers/plans/2026-08-21-frontend-shell-and-chat.md`. Two execution options:**

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
