# Chat Input Auto-Resize and Width Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Double the chat column's width, halve the chat input's resting height, and make the input grow automatically as the user types (capped, then internal scroll).

**Architecture:** Two independent, single-file changes on top of the existing chat UI: a Tailwind class swap for column width, and a ref + `useLayoutEffect` auto-resize behavior added to the existing controlled `Textarea` in the chat input.

**Tech Stack:** Next.js 16 App Router, React 19, Tailwind CSS 3, TypeScript.

## Global Constraints

- Chat column width: `max-w-3xl` (768px) → `max-w-[96rem]` (1536px, exactly double). Spec: `docs/superpowers/specs/2026-09-15-chat-input-auto-resize-and-width-design.md`.
- Textarea resting height: `min-h-[88px]` → `min-h-[44px]` (half).
- Auto-grow cap: `260px` (~3x today's 88px resting height, user-approved rounded figure) — beyond this, internal scroll (`overflow-y: auto`) instead of further growth.
- Must behave identically in Firefox and Chromium — no CSS-only (`field-sizing: content`) shortcut, since that's Chromium-only today.
- No automated test for the auto-resize behavior — jsdom doesn't compute real layout, so `scrollHeight` is always 0 there (per spec's Testing section). Manual verification only.

---

### Task 1: Widen the chat column

**Files:**
- Modify: `frontend/src/app/home-page-content.tsx:65`

**Interfaces:**
- Consumes: none (no dependency on Task 2).
- Produces: none (leaf change, nothing downstream depends on the exact class name).

- [ ] **Step 1: Change the wrapping div's max-width class**

In `frontend/src/app/home-page-content.tsx`, line 65 currently reads:

```tsx
      <div className="mx-auto flex max-w-3xl flex-1 flex-col gap-4 p-4">
```

Change `max-w-3xl` to `max-w-[96rem]`:

```tsx
      <div className="mx-auto flex max-w-[96rem] flex-1 flex-col gap-4 p-4">
```

- [ ] **Step 2: Verify in the browser**

With the frontend dev server running (`npm run dev` in `frontend/`), open `http://localhost:3000/` in a private/incognito window (bypasses any stale service worker cache — see prior session notes if unsure why this matters). Confirm the chat column visibly spans roughly twice its previous width, up to a 1536px viewport width, and stays centered.

- [ ] **Step 3: Commit**

```bash
cd /home/snake/Dokumente/Projekte/01_normly/normly-app
git add frontend/src/app/home-page-content.tsx
git commit -m "feat(frontend): double chat column width

Signed-off-by: normly <anonymous-jw@pm.me>
Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 2: Auto-resizing chat input with a height cap

**Files:**
- Modify: `frontend/src/components/chat/chat-input.tsx`

**Interfaces:**
- Consumes: `Textarea` from `@/components/ui/textarea` (already forwards `ref` to the underlying `<textarea>` element — see `frontend/src/components/ui/textarea.tsx:8-22`, no changes needed there).
- Produces: none (leaf change; `ChatInput`'s exported props signature `{ onSend, disabled }` is unchanged).

- [ ] **Step 1: Add the resize constant, a ref, and the resting-height class**

In `frontend/src/components/chat/chat-input.tsx`, add a module-level constant right after the imports, add a `textareaRef`, and change the `Textarea`'s className from `min-h-[88px]` to `min-h-[44px]`:

```tsx
"use client";

import * as React from "react";
import { ArrowUp } from "lucide-react";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import { useTranslation } from "@/lib/i18n/provider";

const MAX_HEIGHT_PX = 260; // ~3x the 88px resting height this replaces (user-approved, rounded)

export function ChatInput({
  onSend,
  disabled,
}: {
  onSend: (message: string) => void;
  disabled: boolean;
}) {
  const { t } = useTranslation();
  const [value, setValue] = React.useState("");
  const textareaRef = React.useRef<HTMLTextAreaElement>(null);

  const submit = () => {
    const trimmed = value.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed);
    setValue("");
  };

  return (
    <div className="flex items-center gap-2 rounded-lg border bg-background p-2">
      <Textarea
        ref={textareaRef}
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
        className="min-h-[44px] resize-none border-0 shadow-none focus-visible:ring-0"
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

(This step alone leaves the box at a fixed 44px with no auto-grow yet — Step 2 adds that.)

- [ ] **Step 2: Add the auto-resize effect**

In the same file, add a `React.useLayoutEffect` right after the `textareaRef` declaration (before `submit`):

```tsx
  const textareaRef = React.useRef<HTMLTextAreaElement>(null);

  React.useLayoutEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    if (value === "") {
      el.style.height = "";
      el.style.overflowY = "hidden";
      return;
    }
    el.style.height = "auto";
    const nextHeight = Math.min(el.scrollHeight, MAX_HEIGHT_PX);
    el.style.height = `${nextHeight}px`;
    el.style.overflowY = el.scrollHeight > MAX_HEIGHT_PX ? "auto" : "hidden";
  }, [value]);
```

- [ ] **Step 3: Manual verification (no automated test — see Global Constraints)**

With the dev server running, open the chat page in a private/incognito window in both Firefox and Chromium if both are available:

1. Type a short message (a few words). Expected: box stays at its 44px resting height.
2. Paste or type a long multi-paragraph message (enough to exceed ~260px of text). Expected: box grows as you type, stops growing at 260px, and an internal scrollbar appears — the outer page does not scroll, only the textarea's own content.
3. Send the message (click the arrow button or press Enter). Expected: input clears and the box's height resets back to the 44px resting height, not stuck at whatever height it last grew to.
4. Resize the browser window narrower (e.g. to a phone-width ~400px). Expected: box still behaves the same way; nothing overflows the viewport horizontally.

- [ ] **Step 4: Commit**

```bash
cd /home/snake/Dokumente/Projekte/01_normly/normly-app
git add frontend/src/components/chat/chat-input.tsx
git commit -m "feat(frontend): auto-resize chat input up to a height cap

Signed-off-by: normly <anonymous-jw@pm.me>
Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```
