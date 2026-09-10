# Avatar Caching — Design

## Problem

Avatars are served as an inline base64 `data:` URI (`avatar_data_url`) embedded
in three response schemas in `accounts/src/normly_accounts/schemas.py`:
`AccountResponse`, `SessionValidationResponse`, and `ExportAccountFields`. The
encoding happens on every call via `avatar_data_url()` in
`accounts/src/normly_accounts/routers/login.py`.

`frontend/src/lib/use-account-session.ts`'s `useAccountSession()` hook calls
`GET /api/auth/session` (proxying `GET /v1/accounts/session`) on every mount of
`AppShell`/`AppHeader` and the account page. That route was deliberately set to
`cache: "no-store"` in an earlier sub-project to fix a false-401 race — so the
full avatar payload (base64-encoded, ~30-60% larger than the raw bytes) is
re-downloaded and re-embedded into the JSON response on every page navigation,
with no HTTP caching possible for an inline data URI.

## Goals

- Serve avatar images as a normal, browser-cacheable HTTP resource instead of
  inline base64.
- Keep the existing two-hop auth architecture consistent with every other
  account-scoped resource in this project: the browser never holds the Bearer
  token, only an httpOnly session cookie; the frontend proxies with the Bearer
  token server-side.
- Change only what needs to change: `POST /avatar` and `DELETE /avatar` (and
  their frontend proxies) already exist and are unaffected by this design.

## Design

### Backend: `GET /v1/accounts/avatar`

New endpoint in `accounts/src/normly_accounts/routers/profile.py`, Bearer-auth
via the existing `get_current_account` dependency (same as `POST`/`DELETE
/avatar`).

- Returns the raw image bytes (`account.avatar_image`) as a `Response` with
  `media_type=account.avatar_content_type` (currently always `image/jpeg`,
  since `upload_avatar` normalizes every upload to a 256x256 JPEG — but the
  endpoint reads the stored content type rather than hardcoding it, so it
  keeps working if that normalization ever changes).
- 404 (`HTTPException(status_code=404, detail="no avatar set")`) if
  `account.avatar_image is None`.
- `ETag` header: a hex digest (`hashlib.sha256(account.avatar_image).hexdigest()`)
  wrapped in quotes per the HTTP spec (`f'"{digest}"'`). Content-derived, not
  timestamp-derived, so re-uploading the *same* image (rare, but possible)
  correctly keeps the same ETag instead of forcing an unnecessary re-fetch.
- Supports conditional requests: if the incoming `If-None-Match` header
  matches the computed ETag, return `304 Not Modified` with no body.
- `Cache-Control: private, max-age=0, must-revalidate` — `private` because
  this is Bearer-authenticated per-account content that must never be cached
  by a shared/intermediate cache; `max-age=0, must-revalidate` because the
  browser cannot know a stored avatar changed without asking, but the
  `ETag`/`If-None-Match` round trip makes that ask cheap (a 304 with no body)
  rather than a full re-download.

### Frontend: `GET /api/account/avatar`

New handler added to the *existing* file
`frontend/src/app/api/account/avatar/route.ts` (which already has `POST` and
`DELETE`), following the same pattern as those two handlers and as
`frontend/src/app/api/auth/session/route.ts`'s cookie read:

- Reads the session cookie via `readSessionCookies(request)`; 401 if absent
  (matching `POST`/`DELETE`'s existing behavior).
- Forwards the incoming `If-None-Match` header to the backend call, so the
  conditional-request chain (browser → frontend → backend) works end to end
  instead of the frontend always re-fetching from the backend even when the
  browser already has a fresh copy.
- On a backend `304`, returns `304` with no body.
- On a backend `404`, returns `404` (the `<img>` component's `onError`
  handles this — see below).
- On a backend `200`, streams the image bytes through with the same
  `Content-Type`, `ETag`, and `Cache-Control` headers (do not let Next.js's
  own data cache intercept this — use the same `cache: "no-store"` fetch
  option already established for other account-scoped proxies in this
  project, since the *browser's* HTTP cache is what does the caching here,
  not Next.js's server-side fetch cache).

The browser references this endpoint directly as `<img src="/api/account/avatar">`
— no client-side JS is needed to manage caching; the browser's own HTTP cache
does it via the ETag/304 mechanism above.

### Response schema changes

- Remove `avatar_data_url` from `AccountResponse` and
  `SessionValidationResponse`. Both responses fire on every session check /
  profile load; neither needs to embed the image anymore now that
  `<img src="/api/account/avatar">` fetches and caches it independently.
- **Keep** `avatar_data_url` in `ExportAccountFields`. The GDPR data export
  is a single self-contained JSON document handed to the user — it must not
  depend on a second authenticated request succeeding later to be complete.
- This is a breaking response-shape change, coordinated within the same
  sub-project (not staged/versioned) — `accounts/` and `frontend/` are
  deployed together in this project, so no transition period is needed.

### Frontend: avatar rendering

Every place that currently reads `avatarDataUrl` from the session/account
response switches to rendering `<img src="/api/account/avatar">` with an
`onError` fallback to the existing initials-based `Avatar` display (the
current fallback already used when no avatar is set at all — a 404 becomes
just another case of "no avatar"). Known usage sites to update:
`frontend/src/components/app-shell.tsx`'s `NavUser`, and
`frontend/src/components/account/name-avatar-section.tsx`. `avatarDataUrl`
is removed from `mapAccountSummary` (`frontend/src/lib/account-response.ts`)
and the account-session TypeScript types, except where the export flow needs
it.

After a successful avatar upload or delete (`POST`/`DELETE /api/account/avatar`,
unchanged), the `<img>` tag's `src` needs a cache-busting suffix (e.g. a
client-side timestamp or upload-count query param) so the browser doesn't
keep showing the old cached image under the same URL — the ETag alone
doesn't help here since the *browser* decides whether to even ask the server
again within its heuristic freshness window; forcing a new URL sidesteps
that instead of fighting it.

## Out of scope

- No change to `POST /avatar` / `DELETE /avatar` (upload/delete flows) beyond
  their existing frontend proxy file gaining a new sibling handler in the
  same file.
- No avatar resizing/format changes — still always a 256x256 JPEG.
- No CDN/object-storage move — avatar bytes stay in Postgres exactly as
  today; this design only changes how they're *served*, not stored.

## Testing

- Backend: new tests for `GET /v1/accounts/avatar` — 404 when unset, 200 with
  correct `Content-Type`/`ETag`/`Cache-Control` when set, 304 when
  `If-None-Match` matches, 200 (fresh body) when it doesn't.
- Frontend: new tests for the route handler — 401 without a session cookie,
  conditional-request pass-through (mock backend 304 → route returns 304),
  404 pass-through, and the `<img>` `onError`-to-initials fallback in the
  `NavUser`/account-overlay components.
