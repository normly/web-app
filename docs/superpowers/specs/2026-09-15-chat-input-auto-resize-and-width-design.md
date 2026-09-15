# Chat Input Auto-Resize and Width — Design

## Problem

`frontend/src/components/chat/chat-input.tsx` renders a fixed-height
`Textarea` (`min-h-[88px]`) inside a chat column capped at `max-w-3xl`
(768px, set in `frontend/src/app/home-page-content.tsx`). User feedback after
visually testing the frontend: the chat column reads as too narrow and the
input box too tall at rest, and typing a long message doesn't grow the box at
all — the text just scrolls inside the fixed 88px, forcing the user to scroll
to review what they typed before sending.

## Goals

- Chat column (message list + input) twice as wide as today.
- Input box half as tall at rest as today.
- Input box grows automatically as the user types, up to 3x today's height,
  before falling back to internal scrolling.
- Works the same in Firefox and Chromium (the project is tested in both).

## Design

### Column width

`frontend/src/app/home-page-content.tsx`: the wrapping `<div>`'s
`max-w-3xl` (768px) becomes `max-w-[96rem]` (1536px, exactly double).
Tailwind's default scale stops at `max-w-7xl` (1280px), so this needs an
arbitrary-value class rather than a named one.

### Resting height

`frontend/src/components/chat/chat-input.tsx`: the `Textarea`'s
`min-h-[88px]` becomes `min-h-[44px]` (half).

### Auto-grow up to a cap

Same file. A `textareaRef` (via the `Textarea`'s already-forwarded `ref`)
plus a `React.useLayoutEffect` keyed on `value`:

```ts
const MAX_HEIGHT_PX = 260; // ~3x today's 88px resting height (user-approved, rounded)
```

On each change: reset `style.height` to `"auto"` (so `scrollHeight` reflects
the *new* content, not the previous fixed height), then set
`style.height = Math.min(scrollHeight, MAX_HEIGHT_PX) + "px"`. Toggle
`overflow-y` to `"auto"` once `scrollHeight > MAX_HEIGHT_PX`, `"hidden"`
otherwise (avoids a permanently visible scrollbar track before the cap is
reached).

Chosen over the CSS-only `field-sizing: content` property because that
property is Chromium-only today — this project needs Firefox parity, and the
JS approach behaves identically everywhere.

Resetting `value` (new chat / after send) also resets the inline height back
to the CSS `min-h-[44px]` — clear the inline `style.height` in the same
effect when `value === ""`, rather than leaving the last-typed height
sticking around empty.

## Out of scope

- No change to send-on-Enter / Shift+Enter behavior.
- No change to the message list's own width beyond following the column's
  new `max-w-[96rem]`.
- No persistence of draft text across reloads — unrelated to this sizing
  change.

## Testing

- Manual verification in the running dev frontend (both Firefox and, if
  convenient, Chromium): type a short message (stays at resting height), a
  long multi-paragraph message (grows up to the cap, then scrolls
  internally), then send (height resets to resting).
- No new automated test: this is layout/behavior on top of an already
  effectively untested component (`chat-input.tsx` has no existing test
  file), and the behavior is awkward to assert meaningfully via jsdom (which
  doesn't compute real layout, so `scrollHeight` is always 0 there).
