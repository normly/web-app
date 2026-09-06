# Frontend Chat-Seite (verschachtelte Sidebar) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the chat page's message list and input with shadcn
components (color-differentiated bubbles, a copy button under AI
replies, a taller input with an icon send button), add a second, nested
sidebar on the chat page only (date-grouped session history plus a "Neuer
Chat" button), and retire the standalone `/chats` history page — its one
job (browsing past sessions) moves entirely into the new nested sidebar.

**Architecture:** Two independent `SidebarProvider` trees, nested: the
outer one is `AppShell` (Plan 2, unchanged — Chat/Suche nav). Inside its
`SidebarInset`, this plan adds a second, page-local `ChatShell` with its
*own* `SidebarProvider`/`Sidebar`/`SidebarInset` for the history panel —
each `SidebarProvider` scopes its own React context and its own
`--sidebar-width` CSS variables to its own subtree, so nesting them is
supported and the outer/inner triggers never fight over which sidebar
they control. The one thing they *do* share is `sidebar.tsx`'s hardcoded
`sidebar_state` cookie name (both write to the same key on toggle) — see
Global Constraints for why this is accepted, not fixed, in this plan.

**Tech Stack:** shadcn `textarea` primitive (new); existing `sidebar`,
`dropdown-menu` (unused here), `button`, `avatar` primitives from Plan 1/2;
`lucide-react`'s `Copy`, `Check`, `ArrowUp`, `Plus`, `PanelLeft` icons;
`navigator.clipboard` (browser API, no new dependency).

## Global Constraints

- Design spec: `docs/superpowers/specs/2026-09-05-frontend-shadcn-redesign-design.md`
  — this plan implements only the "### Chat-Seite (verschachtelte
  Sidebar)" section (lines 93-109). It does NOT touch `AppShell`,
  `PageHeader`, the Profil-Overlay, Auth pages, or Suche/Dokument-Detail —
  those are other plans in this redesign.
- **No fake session titles or previews, no click-to-resume.** The
  existing `/api/chat/sessions` BFF route (unchanged by this plan)
  returns `{id, session_token, jurisdiction, language, created_at}[]` —
  there is no title or preview field anywhere in the backend, and no
  session-resumption feature exists (confirmed in
  `chats-page-content.tsx`'s own comment: building it is real feature
  work that hasn't happened). shadcnuikit's `ai-chat-v2` reference shows
  real conversation titles ("Best travel experience" etc.) — that is
  *layout* inspiration only, per the spec ("keine Fremd-Registry-
  Abhängigkeit — wird als eigene Komponente gebaut"), not a content
  requirement. Every history item in this plan shows its **creation
  date/time only** (the same data `chats-page-content.tsx` already shows
  today), grouped into date buckets — nothing more. Do not invent a
  title/preview field or a resumption click-handler; a history item is
  plain, non-interactive text, not a button or link.
- **No fake search box in the history sidebar.** The `ai-chat-v2`
  reference shows a "Search chats…" input; the design spec's text for
  this section never asks for one, and there's no backend search
  capability to wire it to. Building a non-functional search input would
  be misleading UI the spec didn't request — leave it out entirely
  (unlike the Header-Muster plan's notification bell, which the spec
  *explicitly* asked for as an intentional placeholder — this is not that
  case).
- **Nested-sidebar cookie collision, accepted as-is.** `sidebar.tsx`
  (Plan 1) hardcodes `SIDEBAR_COOKIE_NAME = "sidebar_state"` and writes it
  on every `SidebarProvider`'s toggle — both the outer `AppShell` and this
  plan's inner `ChatShell` write to the *same* cookie key. This is
  currently harmless: neither `SidebarProvider` in this codebase reads the
  cookie back (Plan 2's final review noted the outer one is already
  write-only), so the collision has no visible effect today. It only
  becomes a real bug if a future plan wires up cookie-based collapse
  persistence — at that point, whoever does that must give each
  `SidebarProvider` a distinct storage key (the primitive doesn't support
  this natively; would need a small fork of that one line). Not this
  plan's job; leave an inline comment where `ChatShell`'s `SidebarProvider`
  is created pointing at this note.
- **Both sidebars must have their trigger reachable outside the
  `<Sidebar>` element they control** — this is the exact mistake Plan 2's
  final review caught and fixed for the outer sidebar (a trigger placed
  inside the `Sidebar` it opens is unreachable once that sidebar is a
  closed mobile Sheet). This plan's inner `ChatShell` trigger lives inside
  the inner `SidebarInset`, never inside the inner `Sidebar` — Task 5's
  code follows this from the start; don't move it later.
- Any task that pastes canonical shadcn component code (this plan installs
  `textarea`) must grep the *built* CSS for the classes it introduces, not
  just trust a green build — a real Critical bug in Plan 2 came from
  Tailwind v3 silently dropping unrecognized/incompatible utility classes.
  (`textarea.tsx`'s own classes were checked in advance and use only
  already-covered tokens — `border-input`, `bg-background`,
  `ring-ring`, `ring-offset-background` — no opacity modifiers, no new
  gap expected; the grep step still runs, to catch a transcription typo,
  not because a gap is anticipated here.)
- Every new/modified hand-written source file keeps the
  `SPDX-License-Identifier: AGPL-3.0-or-later` + copyright header. Files
  generated verbatim by the shadcn CLI (Task 3's `textarea.tsx`) are
  exempt.
- Every commit needs `git commit -s` (DCO `Signed-off-by: normly
  <anonymous-jw@pm.me>`) plus a separate `Co-Authored-By: Claude Sonnet 5
  <noreply@anthropic.com>` trailer for AI-executed work — never a second
  `Signed-off-by` line.
- No direct push to `main` — branch + PR against the `stackit` remote.
  **Ask the user for explicit confirmation before pushing the branch,
  opening the PR, or asking them to merge it** — each triggers a billed
  STACKIT CI run, and the user has asked to be asked every time.
- Tests: Vitest unit tests in `frontend/tests/unit/*.test.tsx`, run with
  `npm test` from `frontend/`. Playwright e2e stays out of scope for this
  plan's automated checks (same exclusion as Plans 1-2); this plan removes
  the `/chats` route, which may affect an existing e2e spec — flagged as a
  manual follow-up in Task 6, not fixed here.
- Branch: create `frontend/chat-page` off latest `main`, once Plan 2's PR
  is merged (this plan needs `AppShell`/`PageHeader` from main).

---

### Task 1: Migrate `citation-chip.tsx` off the old brand token

**Files:**
- Modify: `frontend/src/components/chat/citation-chip.tsx`

**Interfaces:**
- Consumes: nothing new — `CitationChip`'s `{ citation: CitationView }`
  prop shape is unchanged.
- Produces: nothing new for later tasks; this is a values-only visual fix,
  parked explicitly in Plan 1's review for whichever plan next touches the
  chat window (this one).

- [ ] **Step 1: Replace the old `text-brand` class**

In `frontend/src/components/chat/citation-chip.tsx`, change the linked
variant's className from:

```tsx
      className="text-xs text-brand underline"
```

to:

```tsx
      className="text-xs text-primary underline"
```

(The non-linked fallback branch, `text-xs text-muted-foreground`, already
uses a current-theme token and is untouched.)

- [ ] **Step 2: Run the existing test that covers this component**

Run: `cd frontend && npm test -- message-list`
Expected: PASS (`message-list.test.tsx` renders `CitationChip` indirectly
via `MessageList` and asserts on the link's `href`, not its classes, so
this is a safe, behavior-preserving change).

- [ ] **Step 3: Run the build**

Run: `cd frontend && npm run build`
Expected: succeeds.

- [ ] **Step 4: Commit**

```bash
cd frontend
git add src/components/chat/citation-chip.tsx
git commit -s -m "refactor(frontend): migrate citation-chip off the old brand token"
```

---

### Task 2: Rebuild `MessageList` — color-differentiated bubbles + copy button

**Files:**
- Modify: `frontend/src/components/chat/message-list.tsx`
- Modify: `frontend/tests/unit/message-list.test.tsx`
- Modify: `frontend/src/lib/i18n/de.json`, `frontend/src/lib/i18n/en.json`
  (new `chat.copyButtonLabel`, `chat.copiedLabel` keys)

**Interfaces:**
- Consumes: the existing `ChatMessageView`/`CitationView` types and
  `CitationChip` (Task 1) — unchanged.
- Produces: `MessageList`'s own props (`{ messages: ChatMessageView[];
  isLoading: boolean }`) are unchanged — `home-page-content.tsx` (Task 5)
  keeps calling it exactly as it does today; only the rendered markup and
  classes change.

- [ ] **Step 1: Add the copy-button i18n keys**

In `frontend/src/lib/i18n/de.json`, add to the existing `"chat"` object:

```json
    "copyButtonLabel": "Antwort kopieren",
    "copiedLabel": "Kopiert"
```

In `frontend/src/lib/i18n/en.json`:

```json
    "copyButtonLabel": "Copy response",
    "copiedLabel": "Copied"
```

- [ ] **Step 2: Write the failing test for the copy button**

Add to `frontend/tests/unit/message-list.test.tsx` (new `it` block,
inside the existing `describe("MessageList", ...)`, after the existing
tests — keep all three existing tests unchanged):

```tsx
  it("copies the assistant message to the clipboard when the copy button is clicked", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.assign(navigator, { clipboard: { writeText } });
    const messages: ChatMessageView[] = [
      { role: "assistant", content: "DIN EN ISO 9001 ist noch gültig.", citations: [] },
    ];
    render(
      <LocaleProvider initialLocale="de">
        <MessageList messages={messages} isLoading={false} />
      </LocaleProvider>,
    );
    fireEvent.click(screen.getByRole("button", { name: "Antwort kopieren" }));
    expect(writeText).toHaveBeenCalledWith("DIN EN ISO 9001 ist noch gültig.");
  });

  it("does not render a copy button next to a user message", () => {
    const messages: ChatMessageView[] = [{ role: "user", content: "Ist DIN EN ISO 9001 gültig?" }];
    render(
      <LocaleProvider initialLocale="de">
        <MessageList messages={messages} isLoading={false} />
      </LocaleProvider>,
    );
    expect(screen.queryByRole("button", { name: "Antwort kopieren" })).not.toBeInTheDocument();
  });
```

Add `fireEvent` to the existing `import { render, screen } from
"@testing-library/react";` line (making it `import { render, screen,
fireEvent } from "@testing-library/react";`), and add `vi` to the existing
`import { describe, expect, it } from "vitest";` line (making it `import {
describe, expect, it, vi } from "vitest";`).

- [ ] **Step 3: Run it to verify it fails**

Run: `cd frontend && npm test -- message-list`
Expected: FAIL — no button named "Antwort kopieren" exists yet.

- [ ] **Step 4: Replace `MessageList`'s rendering**

Replace `frontend/src/components/chat/message-list.tsx`'s entire content:

```tsx
// frontend/src/components/chat/message-list.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

"use client";

import * as React from "react";
import { Check, Copy } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useTranslation } from "@/lib/i18n/provider";
import { CitationChip, type CitationView } from "@/components/chat/citation-chip";

export interface ChatMessageView {
  role: "user" | "assistant";
  content: string;
  citations?: CitationView[];
}

function CopyButton({ content }: { content: string }) {
  const { t } = useTranslation();
  const [copied, setCopied] = React.useState(false);

  const handleCopy = async () => {
    await navigator.clipboard.writeText(content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <Button
      variant="ghost"
      size="icon"
      className="h-7 w-7"
      onClick={handleCopy}
      aria-label={copied ? t("chat.copiedLabel") : t("chat.copyButtonLabel")}
    >
      {copied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
    </Button>
  );
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
    <div className="flex flex-col gap-6" role="log" aria-live="polite">
      {messages.map((message, index) =>
        message.role === "user" ? (
          <div key={index} className="flex justify-end">
            <p className="max-w-[80%] whitespace-pre-wrap rounded-lg bg-primary px-4 py-2 text-sm text-primary-foreground">
              {message.content}
            </p>
          </div>
        ) : (
          <div key={index} className="flex flex-col gap-2">
            <p className="whitespace-pre-wrap text-sm text-foreground">{message.content}</p>
            {message.citations && message.citations.length > 0 && (
              <div className="flex gap-2">
                {message.citations.map((citation) => (
                  <CitationChip key={citation.documentId} citation={citation} />
                ))}
              </div>
            )}
            <CopyButton content={message.content} />
          </div>
        ),
      )}
      {isLoading && (
        <p aria-busy="true" className="text-sm text-muted-foreground">
          {t("chat.loading")}
        </p>
      )}
    </div>
  );
}
```

(User bubbles use `bg-primary`/`text-primary-foreground` — both already
covered by `tailwind.config.ts`'s `withOpacity()` from Plan 1, no new
color-token gap. Assistant replies have no bubble background, matching
the `ai-chat-v2` reference's plain-text assistant style.)

- [ ] **Step 5: Run the test to verify it passes**

Run: `cd frontend && npm test -- message-list`
Expected: PASS, all 5 tests (3 existing + 2 new).

- [ ] **Step 6: Run the full unit suite and the build**

Run: `cd frontend && npm test && npm run build`
Expected: both succeed.

- [ ] **Step 7: Commit**

```bash
cd frontend
git add src/components/chat/message-list.tsx tests/unit/message-list.test.tsx \
  src/lib/i18n/de.json src/lib/i18n/en.json
git commit -s -m "feat(frontend): color-differentiated chat bubbles with a copy button"
```

---

### Task 3: Rebuild `ChatInput` — `Textarea` + icon send button

**Files:**
- Create (via CLI): `frontend/src/components/ui/textarea.tsx`
- Modify: `frontend/src/components/chat/chat-input.tsx`
- Modify: `frontend/tests/unit/chat-input.test.tsx`

**Interfaces:**
- Consumes: `Button`'s `size="icon"` variant (Plan 1).
- Produces: `ChatInput`'s props (`{ onSend: (message: string) => void;
  disabled: boolean }`) are unchanged — Task 5's `home-page-content.tsx`
  keeps calling it exactly as today.

- [ ] **Step 1: Install the `textarea` primitive**

Run: `cd frontend && npx shadcn@latest add textarea -y`

- [ ] **Step 2: Verify no unrelated files were touched**

Run: `cd frontend && git status --porcelain`
Expected: only `src/components/ui/textarea.tsx` (new, untracked) appears —
nothing else. (Plan 2's Task 1 found the shadcn CLI can silently rewrite
unrelated files like `tailwind.config.ts` on an `--overwrite` install;
`textarea` has no registry dependencies of its own, so this should be a
clean, single-file add, but verify rather than assume.) If anything else
shows as modified, run `git diff` on it, and if it's an unwanted rewrite,
`git checkout -- <file>` before continuing.

- [ ] **Step 3: Grep the built CSS for `textarea.tsx`'s classes**

Run: `cd frontend && npm run build && grep -c "focus-visible\\:ring-ring" .next/static/css/*.css`
Expected: a non-zero count (confirms the primitive's focus-ring utility,
which depends on the `ring` color token, compiled to a real rule).

- [ ] **Step 4: Write the failing test for the new input shape**

Replace `frontend/tests/unit/chat-input.test.tsx`'s entire content:

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

  it("calls onSend when Enter is pressed without Shift", () => {
    const onSend = vi.fn();
    renderWithLocale(<ChatInput onSend={onSend} disabled={false} />);
    const textbox = screen.getByPlaceholderText("Frage stellen…");
    fireEvent.change(textbox, { target: { value: "Frage" } });
    fireEvent.keyDown(textbox, { key: "Enter" });
    expect(onSend).toHaveBeenCalledWith("Frage");
  });

  it("does not call onSend when Shift+Enter is pressed (newline instead)", () => {
    const onSend = vi.fn();
    renderWithLocale(<ChatInput onSend={onSend} disabled={false} />);
    const textbox = screen.getByPlaceholderText("Frage stellen…");
    fireEvent.change(textbox, { target: { value: "Frage" } });
    fireEvent.keyDown(textbox, { key: "Enter", shiftKey: true });
    expect(onSend).not.toHaveBeenCalled();
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

(This drops nothing from the existing suite except the plain-`Enter`
test's name, which now explicitly says "without Shift", and adds the one
new Shift+Enter case — the send-button-click, disabled, and empty-message
cases are byte-identical to what exists today.)

- [ ] **Step 5: Run it to verify the new test fails, others still pass**

Run: `cd frontend && npm test -- chat-input`
Expected: the Shift+Enter test FAILS (current `ChatInput` has no `Enter`
key handling that checks `shiftKey`, and no textarea to receive a
multi-line keydown at all yet); the other four PASS unchanged.

- [ ] **Step 6: Replace `ChatInput`'s implementation**

Replace `frontend/src/components/chat/chat-input.tsx`'s entire content:

```tsx
// frontend/src/components/chat/chat-input.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

"use client";

import * as React from "react";
import { ArrowUp } from "lucide-react";
import { Textarea } from "@/components/ui/textarea";
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
    <div className="flex items-end gap-2 rounded-lg border bg-background p-2">
      <Textarea
        value={value}
        onChange={(event) => setValue(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === "Enter" && !event.shiftKey) {
            event.preventDefault();
            submit();
          }
        }}
        placeholder={t("chat.inputPlaceholder")}
        disabled={disabled}
        aria-label={t("chat.inputPlaceholder")}
        className="min-h-[60px] resize-none border-0 shadow-none focus-visible:ring-0"
      />
      <Button
        onClick={submit}
        disabled={disabled}
        size="icon"
        className="shrink-0"
        aria-label={t("chat.sendButton")}
      >
        <ArrowUp className="h-4 w-4" />
      </Button>
    </div>
  );
}
```

(The visible "Senden" text button becomes an icon-only button — the test
still finds it via its `aria-label`, which matches the same
`chat.sendButton` translation, so `getByRole("button", { name: "Senden"
})` keeps working unchanged.)

- [ ] **Step 7: Run the test to verify it passes**

Run: `cd frontend && npm test -- chat-input`
Expected: PASS, all 5 tests.

- [ ] **Step 8: Run the full unit suite and the build**

Run: `cd frontend && npm test && npm run build`
Expected: both succeed. (`home-page-content.test.tsx` calls
`fireEvent.change`/`getByRole("button", { name: "Send" })` against
`ChatInput` too — its placeholder/button-label lookups are unaffected by
this change, but this is the step that would catch it if not.)

- [ ] **Step 9: Commit**

```bash
cd frontend
git add src/components/ui/textarea.tsx src/components/chat/chat-input.tsx \
  tests/unit/chat-input.test.tsx
git commit -s -m "feat(frontend): rebuild ChatInput with Textarea and an icon send button"
```

---

### Task 4: New-chat-session route + `ChatHistorySidebar`

**Files:**
- Create: `frontend/src/app/api/chat/new-session/route.ts`
- Create: `frontend/src/components/chat/chat-history-sidebar.tsx`
- Create: `frontend/tests/unit/chat-history-sidebar.test.tsx`
- Modify: `frontend/src/lib/i18n/de.json`, `frontend/src/lib/i18n/en.json`
  (new `history.newChatButton`, `history.bucketToday`,
  `history.bucketYesterday`, `history.bucketLast7Days`,
  `history.bucketOlder` keys)

**Interfaces:**
- Consumes: the existing, unmodified `/api/chat/sessions` BFF route
  (returns 401 for anonymous visitors, else a `ChatSessionSummary[]`);
  `useTranslation()`.
- Produces: `POST /api/chat/new-session` (no request body, `{ ok: true }`
  response, clears the `normly_session` cookie) — Task 5's `ChatShell`
  and `home-page-content.tsx` call this when the user clicks "Neuer Chat".
  `ChatHistorySidebar` (named export from
  `@/components/chat/chat-history-sidebar`), props `{ onNewChat: () =>
  void }` — calls `onNewChat` after the new-session request succeeds;
  Task 5 wires this to clearing the chat page's in-memory message list.

- [ ] **Step 1: Add the history i18n keys**

In `frontend/src/lib/i18n/de.json`, add to the existing `"history"`
object:

```json
    "newChatButton": "Neuer Chat",
    "bucketToday": "Heute",
    "bucketYesterday": "Gestern",
    "bucketLast7Days": "Vor 7 Tagen",
    "bucketOlder": "Älter"
```

In `frontend/src/lib/i18n/en.json`:

```json
    "newChatButton": "New chat",
    "bucketToday": "Today",
    "bucketYesterday": "Yesterday",
    "bucketLast7Days": "Last 7 days",
    "bucketOlder": "Older"
```

- [ ] **Step 2: Write the failing test for the new-session route**

Create `frontend/tests/unit/chat-new-session-route.test.ts`:

```ts
// frontend/tests/unit/chat-new-session-route.test.ts
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { NextRequest } from "next/server";
import { describe, expect, it } from "vitest";
import { POST } from "@/app/api/chat/new-session/route";

describe("POST /api/chat/new-session", () => {
  it("clears the chat session cookie", async () => {
    const request = new NextRequest("http://localhost/api/chat/new-session", {
      method: "POST",
      headers: { cookie: "normly_session=old-token" },
    });
    const response = await POST(request);
    expect(response.status).toBe(200);
    const setCookie = response.headers.get("set-cookie") ?? "";
    expect(setCookie).toContain("normly_session=;");
  });
});
```

- [ ] **Step 3: Run it to verify it fails**

Run: `cd frontend && npm test -- chat-new-session-route`
Expected: FAIL — `Cannot find module '@/app/api/chat/new-session/route'`.

- [ ] **Step 4: Implement the route**

Create `frontend/src/app/api/chat/new-session/route.ts`:

```ts
// frontend/src/app/api/chat/new-session/route.ts
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { NextResponse } from "next/server";

// "Neuer Chat" needs no backend call: the chat session is purely a
// client-cookie concept (see session-cookies.ts) that the next /api/chat
// POST re-creates from scratch once this cookie is gone -- mirrors the
// same response.cookies.delete(...) pattern already used by
// /api/auth/logout for the account-session cookie.
export async function POST(): Promise<NextResponse> {
  const response = NextResponse.json({ ok: true });
  response.cookies.delete("normly_session");
  return response;
}
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `cd frontend && npm test -- chat-new-session-route`
Expected: PASS

- [ ] **Step 6: Write the failing test for `ChatHistorySidebar`**

Create `frontend/tests/unit/chat-history-sidebar.test.tsx`:

```tsx
// frontend/tests/unit/chat-history-sidebar.test.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { LocaleProvider } from "@/lib/i18n/provider";
import { ChatHistorySidebar } from "@/components/chat/chat-history-sidebar";

const originalFetch = global.fetch;

function renderSidebar(onNewChat = vi.fn()) {
  return render(
    <LocaleProvider initialLocale="de">
      <ChatHistorySidebar onNewChat={onNewChat} />
    </LocaleProvider>,
  );
}

describe("ChatHistorySidebar", () => {
  beforeEach(() => {
    window.matchMedia = vi.fn().mockImplementation((query: string) => ({
      matches: false,
      media: query,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    })) as unknown as typeof window.matchMedia;
  });

  afterEach(() => {
    global.fetch = originalFetch;
  });

  it("shows the login-required message when there is no account session", async () => {
    global.fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify([]), { status: 401 }));
    renderSidebar();
    await waitFor(() =>
      expect(screen.getByText("Melde dich an, um deinen Chat-Verlauf zu sehen.")).toBeInTheDocument(),
    );
  });

  it("shows the empty message when logged in with no sessions", async () => {
    global.fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify([]), { status: 200 }));
    renderSidebar();
    await waitFor(() =>
      expect(screen.getByText("Noch keine Chats vorhanden.")).toBeInTheDocument(),
    );
  });

  it("groups sessions into Heute/Gestern/Vor 7 Tagen/Älter buckets", async () => {
    const now = new Date();
    const today = new Date(now);
    const yesterday = new Date(now);
    yesterday.setDate(yesterday.getDate() - 1);
    const fourDaysAgo = new Date(now);
    fourDaysAgo.setDate(fourDaysAgo.getDate() - 4);
    const twoWeeksAgo = new Date(now);
    twoWeeksAgo.setDate(twoWeeksAgo.getDate() - 14);

    global.fetch = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify([
          { id: "1", session_token: "a", jurisdiction: "DE", language: "de", created_at: today.toISOString() },
          { id: "2", session_token: "b", jurisdiction: "DE", language: "de", created_at: yesterday.toISOString() },
          { id: "3", session_token: "c", jurisdiction: "DE", language: "de", created_at: fourDaysAgo.toISOString() },
          { id: "4", session_token: "d", jurisdiction: "DE", language: "de", created_at: twoWeeksAgo.toISOString() },
        ]),
        { status: 200 },
      ),
    );
    renderSidebar();
    await waitFor(() => expect(screen.getByText("Heute")).toBeInTheDocument());
    expect(screen.getByText("Gestern")).toBeInTheDocument();
    expect(screen.getByText("Vor 7 Tagen")).toBeInTheDocument();
    expect(screen.getByText("Älter")).toBeInTheDocument();
  });

  it("calls onNewChat and the new-session endpoint when the button is clicked", async () => {
    const onNewChat = vi.fn();
    global.fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify([]), { status: 401 }));
    renderSidebar(onNewChat);
    await waitFor(() => expect(global.fetch).toHaveBeenCalledWith("/api/chat/sessions"));
    fireEvent.click(screen.getByRole("button", { name: "Neuer Chat" }));
    await waitFor(() =>
      expect(global.fetch).toHaveBeenCalledWith("/api/chat/new-session", { method: "POST" }),
    );
    expect(onNewChat).toHaveBeenCalled();
  });
});
```

- [ ] **Step 7: Run it to verify it fails**

Run: `cd frontend && npm test -- chat-history-sidebar`
Expected: FAIL — `Cannot find module '@/components/chat/chat-history-sidebar'`.

- [ ] **Step 8: Implement `ChatHistorySidebar`**

Create `frontend/src/components/chat/chat-history-sidebar.tsx`:

```tsx
// frontend/src/components/chat/chat-history-sidebar.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

"use client";

import * as React from "react";
import { Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Sidebar,
  SidebarContent,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuItem,
} from "@/components/ui/sidebar";
import { useTranslation } from "@/lib/i18n/provider";
import type { TranslationKey } from "@/lib/i18n/dictionary-keys";

interface ChatSessionSummary {
  id: string;
  session_token: string;
  jurisdiction: string;
  language: string;
  created_at: string;
}

interface Bucket {
  labelKey: TranslationKey;
  sessions: ChatSessionSummary[];
}

function isSameCalendarDay(a: Date, b: Date): boolean {
  return a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate();
}

function groupSessionsByBucket(sessions: ChatSessionSummary[], now: Date): Bucket[] {
  const yesterday = new Date(now);
  yesterday.setDate(yesterday.getDate() - 1);
  const sevenDaysAgo = new Date(now);
  sevenDaysAgo.setDate(sevenDaysAgo.getDate() - 7);

  const buckets: Bucket[] = [
    { labelKey: "history.bucketToday", sessions: [] },
    { labelKey: "history.bucketYesterday", sessions: [] },
    { labelKey: "history.bucketLast7Days", sessions: [] },
    { labelKey: "history.bucketOlder", sessions: [] },
  ];

  const sorted = [...sessions].sort(
    (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime(),
  );
  for (const session of sorted) {
    const createdAt = new Date(session.created_at);
    if (isSameCalendarDay(createdAt, now)) {
      buckets[0].sessions.push(session);
    } else if (isSameCalendarDay(createdAt, yesterday)) {
      buckets[1].sessions.push(session);
    } else if (createdAt.getTime() >= sevenDaysAgo.getTime()) {
      buckets[2].sessions.push(session);
    } else {
      buckets[3].sessions.push(session);
    }
  }
  return buckets.filter((bucket) => bucket.sessions.length > 0);
}

export function ChatHistorySidebar({ onNewChat }: { onNewChat: () => void }) {
  const { t, locale } = useTranslation();
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

  const handleNewChat = async () => {
    await fetch("/api/chat/new-session", { method: "POST" });
    onNewChat();
  };

  const buckets = sessions ? groupSessionsByBucket(sessions, new Date()) : [];

  return (
    // collapsible="offcanvas" (the default): hidden entirely behind a
    // Sheet on mobile until its own trigger (rendered in ChatShell's
    // SidebarInset, never in here -- see Global Constraints) opens it;
    // visible inline on desktop by default. This SidebarProvider's own
    // sidebar_state cookie write collides with AppShell's outer one --
    // accepted, see Global Constraints, not fixed here.
    <Sidebar>
      <SidebarHeader className="p-2">
        <Button onClick={handleNewChat} variant="outline" className="w-full justify-start gap-2">
          <Plus className="size-4" />
          {t("history.newChatButton")}
        </Button>
      </SidebarHeader>
      <SidebarContent>
        {requiresLogin && (
          <p className="p-2 text-sm text-muted-foreground">{t("history.loginRequired")}</p>
        )}
        {sessions !== null && sessions.length === 0 && (
          <p className="p-2 text-sm text-muted-foreground">{t("history.empty")}</p>
        )}
        {buckets.map((bucket) => (
          <SidebarGroup key={bucket.labelKey}>
            <SidebarGroupLabel>{t(bucket.labelKey)}</SidebarGroupLabel>
            <SidebarGroupContent>
              <SidebarMenu>
                {bucket.sessions.map((session) => (
                  <SidebarMenuItem key={session.id}>
                    {/* Plain text, not a link or button: no session-
                        resumption feature exists (see Global Constraints)
                        -- this must not look clickable. */}
                    <span className="flex h-8 items-center rounded-md px-2 text-sm text-sidebar-foreground/70">
                      {new Date(session.created_at).toLocaleString(locale)}
                    </span>
                  </SidebarMenuItem>
                ))}
              </SidebarMenu>
            </SidebarGroupContent>
          </SidebarGroup>
        ))}
      </SidebarContent>
    </Sidebar>
  );
}
```

- [ ] **Step 9: Run the test to verify it passes**

Run: `cd frontend && npm test -- chat-history-sidebar`
Expected: PASS, all 4 tests.

- [ ] **Step 10: Run the full unit suite and the build**

Run: `cd frontend && npm test && npm run build`
Expected: both succeed.

- [ ] **Step 11: Commit**

```bash
cd frontend
git add src/app/api/chat/new-session/route.ts src/components/chat/chat-history-sidebar.tsx \
  tests/unit/chat-new-session-route.test.ts tests/unit/chat-history-sidebar.test.tsx \
  src/lib/i18n/de.json src/lib/i18n/en.json
git commit -s -m "feat(frontend): add new-chat-session route and date-grouped history sidebar"
```

---

### Task 5: `ChatShell` wrapper — wire the nested sidebar into the chat page

**Files:**
- Create: `frontend/src/components/chat/chat-shell.tsx`
- Modify: `frontend/src/app/home-page-content.tsx`
- Modify: `frontend/tests/unit/home-page-content.test.tsx`
- Modify: `frontend/src/lib/i18n/de.json`, `frontend/src/lib/i18n/en.json`
  (new `nav.toggleChatHistory` key)

**Interfaces:**
- Consumes: `ChatHistorySidebar` (Task 4), `MessageList`/`ChatInput`
  (Tasks 2-3) — all unchanged signatures from this task's point of view.
- Produces: `ChatShell` (named export from `@/components/chat/chat-shell`),
  props `{ onNewChat: () => void; children: React.ReactNode }` — this
  plan's only consumer is `home-page-content.tsx`; no other page uses it.

- [ ] **Step 1: Add the toggle-chat-history i18n key**

In `frontend/src/lib/i18n/de.json`, add to the existing `"nav"` object:

```json
    "toggleChatHistory": "Chatverlauf umschalten"
```

In `frontend/src/lib/i18n/en.json`:

```json
    "toggleChatHistory": "Toggle chat history"
```

- [ ] **Step 2: Implement `ChatShell`**

Create `frontend/src/components/chat/chat-shell.tsx`:

```tsx
// frontend/src/components/chat/chat-shell.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

"use client";

import * as React from "react";
import { SidebarInset, SidebarProvider, SidebarTrigger } from "@/components/ui/sidebar";
import { ChatHistorySidebar } from "@/components/chat/chat-history-sidebar";
import { useTranslation } from "@/lib/i18n/provider";

export function ChatShell({
  onNewChat,
  children,
}: {
  onNewChat: () => void;
  children: React.ReactNode;
}) {
  const { t } = useTranslation();

  return (
    <SidebarProvider>
      <ChatHistorySidebar onNewChat={onNewChat} />
      <SidebarInset>
        {/* This sidebar starts open by default on desktop (matching the
            ai-chat-v2 reference's always-visible history panel) and
            closed by default on mobile (the primitive's own
            openMobile state always starts false, regardless of
            defaultOpen) -- md:hidden here means desktop users get no
            toggle chrome (matching the reference, which shows none),
            while mobile users get the one reachable way to open it.
            This trigger lives in SidebarInset, never inside
            ChatHistorySidebar's own <Sidebar> -- see Global
            Constraints on why that placement matters. */}
        <div className="flex items-center border-b p-2 md:hidden">
          <SidebarTrigger aria-label={t("nav.toggleChatHistory")} />
        </div>
        {children}
      </SidebarInset>
    </SidebarProvider>
  );
}
```

- [ ] **Step 3: Write the failing test for `HomePageContent`'s new-chat wiring**

Add to `frontend/tests/unit/home-page-content.test.tsx` (new `it` block,
after the existing test, inside the same `describe`):

```tsx
  it("clears the message list and calls the new-session endpoint when Neuer Chat is clicked", async () => {
    global.fetch = vi.fn().mockImplementation((url: string) => {
      if (url === "/api/chat/sessions") {
        return Promise.resolve(new Response(JSON.stringify([]), { status: 401 }));
      }
      if (url === "/api/chat/new-session") {
        return Promise.resolve(new Response(JSON.stringify({ ok: true }), { status: 200 }));
      }
      return Promise.resolve(
        new Response(JSON.stringify({ answer: "Answer", answer_type: "fallback", citations: [] })),
      );
    });
    window.matchMedia = vi.fn().mockImplementation((query: string) => ({
      matches: false,
      media: query,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    })) as unknown as typeof window.matchMedia;

    render(
      <LocaleProvider initialLocale="de">
        <JurisdictionProvider initialJurisdiction="DE">
          <HomePageContent />
        </JurisdictionProvider>
      </LocaleProvider>,
    );

    fireEvent.change(screen.getByPlaceholderText("Frage stellen…"), {
      target: { value: "Ist DIN EN ISO 9001 gültig?" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Senden" }));
    await waitFor(() => expect(screen.getByText("Ist DIN EN ISO 9001 gültig?")).toBeInTheDocument());

    fireEvent.click(screen.getByRole("button", { name: "Neuer Chat" }));
    await waitFor(() =>
      expect(global.fetch).toHaveBeenCalledWith("/api/chat/new-session", { method: "POST" }),
    );
    expect(screen.queryByText("Ist DIN EN ISO 9001 gültig?")).not.toBeInTheDocument();
  });
```

The existing test in this file sends its message in English
(`initialLocale="en"`, placeholder "Ask a question…", button "Send") —
leave it completely unchanged; this new test uses German strings, both
coexist fine since each `render()` call gets its own `LocaleProvider`.

- [ ] **Step 4: Run it to verify it fails**

Run: `cd frontend && npm test -- home-page-content`
Expected: FAIL — `HomePageContent` doesn't render a "Neuer Chat" button
yet (no `ChatShell` wired in).

- [ ] **Step 5: Wire `ChatShell` into `HomePageContent`**

Modify `frontend/src/app/home-page-content.tsx` — add the import:

```tsx
import { ChatShell } from "@/components/chat/chat-shell";
```

then replace the final `return` statement:

```tsx
  return (
    <div className="mx-auto flex max-w-2xl flex-col gap-4 p-4">
      <MessageList messages={messages} isLoading={isLoading} />
      <ChatInput onSend={sendMessage} disabled={isLoading} />
    </div>
  );
```

with:

```tsx
  return (
    <ChatShell onNewChat={() => setMessages([])}>
      <div className="mx-auto flex max-w-2xl flex-1 flex-col gap-4 p-4">
        <MessageList messages={messages} isLoading={isLoading} />
        <ChatInput onSend={sendMessage} disabled={isLoading} />
      </div>
    </ChatShell>
  );
```

- [ ] **Step 6: Run the test to verify it passes**

Run: `cd frontend && npm test -- home-page-content`
Expected: PASS, both tests (the pre-existing English-locale one and the
new German-locale one).

- [ ] **Step 7: Run the full unit suite and the build**

Run: `cd frontend && npm test && npm run build`
Expected: both succeed.

- [ ] **Step 8: Manual visual check**

Using a running local sandbox (Postgres + `accounts`/`api`/`chat`
services + `npm run dev` — rebuild if not already up, see this
redesign's project memory for the exact commands), confirm in a browser
on `/`: the chat page shows two sidebars (outer Chat/Suche nav, inner
chat history with "Neuer Chat"); sending a message shows the new bubble
styling (dark bubble for your question, plain text for the reply, a copy
button under the reply that actually copies); clicking "Neuer Chat"
clears the message list; at a narrow (phone-width) viewport, the inner
sidebar's trigger appears and actually opens/closes the history panel
without interfering with the outer sidebar's own trigger in `PageHeader`;
toggle dark mode (the `ModeToggle` in `PageHeader`) and confirm both
sidebars, the message bubbles, and the copy button all render correctly
in dark mode too, not just the page body.

- [ ] **Step 9: Commit**

```bash
cd frontend
git add src/components/chat/chat-shell.tsx src/app/home-page-content.tsx \
  tests/unit/home-page-content.test.tsx src/lib/i18n/de.json src/lib/i18n/en.json
git commit -s -m "feat(frontend): wire the nested chat-history sidebar into the chat page"
```

---

### Task 6: Retire `/chats` and the now-dead `showHistoryLink` plumbing

**Files:**
- Delete: `frontend/src/app/chats/page.tsx`
- Delete: `frontend/src/app/chats/chats-page-content.tsx`
- Delete: `frontend/tests/unit/chats-page.test.tsx`
- Modify: `frontend/src/components/app-header.tsx`
- Modify: `frontend/tests/unit/app-header.test.tsx`
- Modify: `frontend/src/app/confirm-email-change/page.tsx`
- Modify: `frontend/src/app/reset-password/page.tsx`
- Modify: `frontend/src/lib/i18n/de.json`, `frontend/src/lib/i18n/en.json`
  (remove the now-dead `chat.historyLink` and `history.title` keys)

**Interfaces:**
- Consumes: nothing new.
- Produces: nothing new — `AppHeader`'s remaining props become
  `{ instanceName: string; logoPath: string | null }` (the
  `showHistoryLink` parameter is removed entirely — it existed only to
  suppress a link to the page this task deletes).

Chat history now lives *only* in `ChatHistorySidebar` (Task 4), reachable
from the Chat nav item in `AppShell` (Plan 2). The standalone `/chats`
page duplicated that same data with no date-grouping and is being
retired, per the design spec ("Die bisherige eigenständige
`/chats`-Verlaufsseite entfällt"). One concrete consequence this task must
handle: `frontend/src/app/account/page.tsx` is the *only* remaining
`AppHeader` consumer that does **not** pass `showHistoryLink={false}` —
once `/chats` is deleted, that page's default-visible "Verlauf" link
would point at a route that no longer exists. Removing the link (and the
prop that controls it) from `AppHeader` entirely fixes this for every
caller at once, rather than patching `account/page.tsx` alone.

- [ ] **Step 1: Delete the standalone history page and its test**

```bash
cd frontend
rm src/app/chats/page.tsx src/app/chats/chats-page-content.tsx tests/unit/chats-page.test.tsx
rmdir src/app/chats
```

- [ ] **Step 2: Remove `showHistoryLink` and the "Verlauf" link from `AppHeader`**

In `frontend/src/components/app-header.tsx`, change the function
signature from:

```tsx
export function AppHeader({
  instanceName,
  logoPath,
  showHistoryLink = true,
}: {
  instanceName: string;
  logoPath: string | null;
  showHistoryLink?: boolean;
}) {
```

to:

```tsx
export function AppHeader({
  instanceName,
  logoPath,
}: {
  instanceName: string;
  logoPath: string | null;
}) {
```

and remove this block entirely (it sits right after the "Suche" link,
inside the `<div className="flex items-center gap-2">`):

```tsx
        {showHistoryLink && (
          <Link href="/chats" className="text-sm underline">
            {t("chat.historyLink")}
          </Link>
        )}
```

- [ ] **Step 3: Update the three remaining `AppHeader` call sites**

In `frontend/src/app/confirm-email-change/page.tsx` and
`frontend/src/app/reset-password/page.tsx`, remove the now-invalid
`showHistoryLink={false}` prop from each page's `<AppHeader ... />` call
(keep `instanceName`/`logoPath` as-is). `frontend/src/app/account/page.tsx`
already doesn't pass this prop — no change needed there.

- [ ] **Step 4: Update `app-header.test.tsx`**

In `frontend/tests/unit/app-header.test.tsx`, delete these two test
cases entirely (both test the now-removed `showHistoryLink` behavior):

```tsx
  it("omits the history link when showHistoryLink is false", async () => {
    global.fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify({ account: null })));
    render(
      <LocaleProvider initialLocale="de">
        <JurisdictionProvider initialJurisdiction="DE">
          <AppHeader instanceName="normly" logoPath={null} showHistoryLink={false} />
        </JurisdictionProvider>
      </LocaleProvider>,
    );
    expect(screen.queryByRole("link", { name: "Verlauf" })).not.toBeInTheDocument();
  });
```

and replace the other one:

```tsx
  it("always links to the search page, independent of showHistoryLink", async () => {
    global.fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify({ account: null })));
    render(
      <LocaleProvider initialLocale="de">
        <JurisdictionProvider initialJurisdiction="DE">
          <AppHeader instanceName="normly" logoPath={null} showHistoryLink={false} />
        </JurisdictionProvider>
      </LocaleProvider>,
    );
    expect(screen.getByRole("link", { name: "Suche" })).toHaveAttribute("href", "/search");
  });
```

with:

```tsx
  it("links to the search page", async () => {
    global.fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify({ account: null })));
    render(
      <LocaleProvider initialLocale="de">
        <JurisdictionProvider initialJurisdiction="DE">
          <AppHeader instanceName="normly" logoPath={null} />
        </JurisdictionProvider>
      </LocaleProvider>,
    );
    expect(screen.getByRole("link", { name: "Suche" })).toHaveAttribute("href", "/search");
  });
```

- [ ] **Step 5: Remove the two now-dead i18n keys**

Remove `"historyLink": "Verlauf"` from the `"chat"` object in both
`frontend/src/lib/i18n/de.json` and `frontend/src/lib/i18n/en.json`.
Remove the entire `"history"` object's `"title"` key (`"Chat-Verlauf"` /
whatever its English equivalent is) from both files — `history.empty` and
`history.loginRequired` stay, they're still used by `ChatHistorySidebar`
(Task 4).

- [ ] **Step 6: Run the full unit suite**

Run: `cd frontend && npm test`
Expected: PASS — the deleted `chats-page.test.tsx` no longer runs (file
gone), the two edited `app-header.test.tsx` cases pass under their new
names/shapes, everything else unaffected.

- [ ] **Step 7: Run the build**

Run: `cd frontend && npm run build`
Expected: succeeds — no route still references `/chats`, no remaining
`showHistoryLink` call site, no orphaned `chat.historyLink`/`history.title`
lookups (a missing `TranslationKey` reference would be a TypeScript error
here, not a silent runtime issue, since `t()` is typed against the
dictionary's own shape).

- [ ] **Step 8: Note the Playwright e2e residual**

`frontend/tests/e2e/chat-and-history.spec.ts` (not run by this plan's
automated checks, same exclusion as Plans 1-2) may still navigate to
`/chats` or assert on the old history page — out of scope to fix here,
but flag it explicitly in the PR description as a known follow-up, since
e2e is real coverage that would otherwise silently start failing against
a route that no longer exists.

- [ ] **Step 9: Commit**

```bash
cd frontend
git add -A src/app/chats tests/unit/chats-page.test.tsx src/components/app-header.tsx \
  tests/unit/app-header.test.tsx src/app/confirm-email-change/page.tsx \
  src/app/reset-password/page.tsx src/lib/i18n/de.json src/lib/i18n/en.json
git commit -s -m "chore(frontend): retire the standalone /chats page and its dead plumbing"
```

---

## After This Plan

Ask the user for explicit confirmation before pushing the branch and
before opening a PR (each triggers a billed STACKIT CI run — see Global
Constraints). Once confirmed: push `frontend/chat-page`, open a PR against
`main` on the `stackit` remote — mention the Playwright e2e residual
(Task 6, Step 8) in the PR description — wait for the CI pipeline's
`test-frontend` job to go green, then ask the user to merge (same
confirm-first rule applies). Plans 4 (Profil-Overlay), 5 (Auth-Seiten),
and 6 (Suche & Dokument-Detail) remain in this redesign; none of them
depend on this plan specifically, only on Plan 2 (already merged/mergeable).
