# Email templates and per-account language — design

Date: 2026-10-21
Status: approved by the owner in brainstorming, 2026-10-21
Issue: #45 · Branch: `feature/45-email-templates` (off `develop`)

## Background

Every email normly sends is a single plain-text sentence with a bare link.
Issue #45 asks for professional emails based on the normly corporate design.
The owner supplied an HTML layout (react-email output) that this design
adopts as the base layout.

All seven emails are sent from Python, through
`EmailSender.send(to, subject, body)` in
`core/src/normly_core/notifications/email.py`:

| # | Trigger | Sent from |
|---|---|---|
| 1 | Registration with password | `accounts/.../routers/registration.py` |
| 2 | Resend verification email | `accounts/.../routers/email_verification.py` |
| 3 | Password reset | `accounts/.../routers/password_reset.py` |
| 4 | Magic link (sign-in and first registration) | `accounts/.../routers/magic_link.py` |
| 5 | Email change (to the new address) | `accounts/.../routers/email_change.py` |
| 6 | Normtracker notification, four trigger types | `core/.../notifications/detection.py` |
| 7 | Warning before an abandoned registration is deleted | `core/.../notifications/abandoned_registration.py` |

Problems beyond the missing layout:

- Mail 6 names neither the standard nor links to it; it shows the internal
  enum value (`new_edition`).
- No mail states how long its link is valid or what to do if the recipient
  did not request it.
- Accounts store no language. Mails 1–6 are German only, mail 7 is
  bilingual. The frontend already has a German/English switch.

## Decisions

- **Per-account language** (option C in brainstorming): a new
  `account.locale` column; request-triggered mails use the language of the
  request, job-triggered mails use the stored one.
- **The language switch updates the stored language automatically** when
  the user is signed in. No separate setting.
- **Jinja2 templates in the core** (option A). All senders are Python; the
  frontend sends no mail. Jinja2 is already in `uv.lock` (via torch) and
  becomes a direct dependency of `normly-core`.
- **Link targets come from `NORMLY_PUBLIC_BASE_URL`**, never hard-coded.
  In production it is `https://app.normly.ai`.

## Components

### Renderer: `core/src/normly_core/notifications/mail/`

- `templates/base.html.j2` — the owner's layout: wordmark, card with
  heading, paragraph, button, plain-text fallback link, optional muted
  note, footer with claim and imprint/privacy links. Hidden preheader,
  `<html lang="de|en">`. Table-based, inline styles only (mail clients
  ignore `<style>` blocks inconsistently).
- `templates/base.txt.j2` — the same structure as plain text.
- `texts.py` — all subjects and copy as `{"de": {...}, "en": {...}}`, one
  key per mail kind. Separates content from presentation; a new language
  is one new block.
- `render.py` — `render_email(kind, locale, **params) -> RenderedEmail`
  with fields `subject`, `text`, `html`. Jinja2 with autoescape on. An
  unknown locale falls back to `de`; an unknown kind raises.

Colors are the shadcn "neutral" tokens, named as such in the template
context so the mapping stays visible:

| Token | Value | Used for |
|---|---|---|
| `muted` | `#f5f5f5` | page background |
| `card` | `#ffffff` | card |
| `foreground` | `#0a0a0a` | text, wordmark |
| `border` | `#e5e5e5` | card border |
| `primary` | `#171717` | button |
| `primary-foreground` | `#fafafa` | button text |
| `muted-foreground` | `#737373` | note, fallback link, footer |
| `radius` | `8px` | card, button |

No other colors are introduced. The wordmark stays text, not an image,
because many clients block images.

### Sender

`EmailSender.send(*, to, subject, body, html=None)`. With `html` set,
`SmtpEmailSender` sends `multipart/alternative` (text first, HTML second);
without it, behavior is unchanged. `RecordingEmailSender` records `html`;
`NullEmailSender` accepts and ignores it.

### Call sites

All seven call sites call `render_email(...)` and pass `subject`, `text`
as `body`, and `html`. Rendering happens **before** the `try` around
`send()`: a template error is a programming error and must surface, not be
swallowed as an SMTP failure. The existing fail-soft handling of delivery
errors is unchanged.

Link validity in the copy comes from the existing lifetime constants
(`_VERIFICATION_TOKEN_LIFETIME`, `_MAGIC_LINK_TOKEN_LIFETIME`,
`_RESET_TOKEN_LIFETIME`, `_EMAIL_CHANGE_TOKEN_LIFETIME`), never duplicated
as literals.

## Language data flow

- **Migration `0039`** adds `account.locale` (`text`, nullable, no default,
  check constraint `locale IN ('de', 'en')`). NULL means the language is
  unknown: existing accounts keep NULL; accounts created from now on always
  get a value (default `de`). Domain model, ORM and repository carry the field; the repository
  gets `update_locale`, following the existing per-field
  `update_notification_preference`. `AccountResponse` exposes `locale`.
- **Frontend `resolveLocale(request)`** in `frontend/src/lib/i18n/`:
  cookie `normly_locale` → `Accept-Language` → `de`. Same logic as
  `layout.tsx` today; `layout.tsx` is switched to use it so there is one
  implementation.
- **BFF routes pass `locale`** in the payload to accounts: register,
  magic-link request, magic-link confirm, password-reset request,
  verify-email resend, email change.
- **Accounts schemas** get `locale: Literal["de", "en"] = "de"` on those
  requests. A missing value means `de` (older clients keep working); an
  invalid value is a `400`, the accounts service's uniform status for
  request-validation errors.
- **Account creation** stores the locale: registration with password,
  magic-link confirm (creates the account for an unknown address), Google
  OAuth callback (reads the `normly_locale` cookie / `Accept-Language` from
  the callback request in the BFF and passes it on).
- **Language switch**: `setLocale` additionally calls a new BFF route
  `PUT /api/account/locale {locale}`. The session cookie is `httpOnly`, so
  the client cannot tell whether someone is signed in; the route can. Without
  a session cookie it answers `204` and calls nothing; with one it forwards
  `PATCH /v1/accounts/profile {locale}`. `UpdateProfileRequest` accepts
  `locale`. A failed call is ignored silently — the cookie switch is what
  the user sees, the stored value catches up on the next switch.
- **Which language a mail uses**: mails 1–5 use the request's `locale`;
  mails 6 and 7 use `account.locale`. NULL behaves as `de`
  everywhere (mail 6, `AccountResponse`) except mail 7: a NULL-locale
  recipient gets one mail with the German and the English copy in a single
  layout (`render_bilingual_email`, subject `German / English`), since the
  deletion warning is the only safeguard before an account is deleted
  (ADR-027). Otherwise mail 7 is monolingual.

## Mail content

The copy uses "du", as today. German shown; English is equivalent in
content. `{base}` is `NORMLY_PUBLIC_BASE_URL`.

| Mail | Subject | Heading | Text | Button → target | Note (muted) |
|---|---|---|---|---|---|
| 1, 2 Verification | Bestätige deine E-Mail-Adresse | Willkommen bei normly | Bitte bestätige deine E-Mail-Adresse, um dein Konto zu aktivieren. | E-Mail bestätigen → `/verify-email?token=` | Der Link ist 48 Stunden gültig. Du hast dich nicht registriert? Dann ignoriere diese Mail. |
| 4 Magic link | Dein Anmeldelink für normly | Bei normly anmelden | Klicke auf den Button, um dich anzumelden. Falls du noch kein Konto hast, wird es dabei angelegt. | Anmelden → `/magic-link?token=` | Der Link ist 15 Minuten gültig und nur einmal verwendbar. Du hast ihn nicht angefordert? Dann ignoriere diese Mail. |
| 3 Password reset | Passwort zurücksetzen | Passwort zurücksetzen | Du hast angefordert, dein Passwort zurückzusetzen. | Neues Passwort festlegen → `/reset-password?token=` | Der Link ist 1 Stunde gültig. Du hast das nicht angefordert? Dann bleibt dein Passwort unverändert. |
| 5 Email change | Bestätige deine neue E-Mail-Adresse | Neue E-Mail-Adresse bestätigen | Bestätige, dass du künftig {new address} für dein normly-Konto verwenden möchtest. | Adresse bestätigen → `/confirm-email-change?…` | Der Link ist 24 Stunden gültig. Du hast das nicht angefordert? Dann ignoriere diese Mail. |
| 6 New edition | Neue Ausgabe: {designation} | Neue Ausgabe von {designation} | Für „{title}" auf deiner Watchlist ist eine neue Ausgabe erschienen: {document}. | Regelwerk ansehen → `/documents/{id}` | Watchlist note (below) |
| 6 National adoption | Neue nationale Fassung: {designation} | Neue nationale Fassung von {designation} | Für „{title}" auf deiner Watchlist ist eine neue nationale Fassung erschienen: {document} ({jurisdiction}). | Regelwerk ansehen → `/documents/{id}` | Watchlist note |
| 6 Rights change | Rechteänderung: {designation} | Rechteänderung bei {designation} | Die Nutzungsrechte für „{title}" haben sich geändert. | Details ansehen → `/documents/{id}` | Watchlist note |
| 6 No longer available | Nicht mehr verfügbar: {designation} | {designation} ist nicht mehr verfügbar | „{title}" ist in normly nicht mehr verfügbar. | Watchlist öffnen → `/` | Watchlist note |
| 7 Deletion warning | Dein normly-Konto wird gelöscht | Dein Konto wird bald gelöscht | Dein Konto wurde nie bestätigt und lange nicht genutzt. Es wird frühestens am {date} gelöscht, wenn du dich bis dahin nicht anmeldest. | Bei normly anmelden → `/` | — |

Watchlist note: „Du erhältst diese Mail, weil das Regelwerk auf deiner
Watchlist steht. Benachrichtigungen änderst du in deinem Konto." The
account link goes to `{base}/` — there is no dedicated account URL; the
profile is an overlay.

Every button is followed by the same URL as plain text ("Falls der Button
nicht funktioniert, öffne diesen Link: …").

Dates are formatted per locale: `21.10.2026` (de), `21 October 2026` (en).

### Normtracker details (mail 6)

`detection.py` resolves, through the existing repositories (no SQL in the
notification logic):

- `designation` and `title` of the watched work, preferring the account's
  language, falling back to any available title;
- the triggering document (`trigger_document_id`) for `{document}` and the
  link; for a rights change without a triggering document, a document of
  the work.

Fallbacks: no designation → `{origin_issuer} {origin_number}:{edition}`
(every document has these, so a designation always exists); no title → the
designation is used in its place; no document to link → the button goes to
`{base}/`; `NORMLY_PUBLIC_BASE_URL` unset (the jobs have no default) → no
button, as the deletion warning does today.

## Configuration (self-hosting)

Imprint and privacy policy belong to whoever operates the instance. Two
new optional variables, read by the renderer:

- `NORMLY_IMPRINT_URL`, `NORMLY_PRIVACY_URL` — when unset, the
  corresponding footer link is left out.

normly's production sets them to `https://normly.ai/imprint` and
`https://normly.ai/privacy`. The wordmark links to
`NORMLY_PUBLIC_BASE_URL`. Documented in `docs/guide/self-hosting.md` and
`docs/guide/operations.md`; the deployment `.env` template gets both
variables.

## Error handling

- Delivery failures: unchanged fail-soft behavior per call site.
- Template errors: raised, not caught (see Call sites).
- Unknown `locale` in a request: `400`. Missing: `de`.
- Unknown locale in the renderer (defensive, e.g. a bad DB value): `de`.
- `account.locale` NULL: `de`, except the deletion warning, which is bilingual.
- Missing work metadata in mail 6: fallbacks above.

## Testing

- **Renderer** (core): every kind × `de`/`en` renders; subject is right;
  the link appears in HTML and text; inserted values are escaped
  (`<script>` in a title); footer links appear only when the variables are
  set; no unrendered `{{` in any output.
- **SmtpEmailSender**: with `html`, a `multipart/alternative` with both
  parts; without, plain text as before.
- **Accounts**: existing tests adapted; new tests that `locale` is stored
  on register, magic-link confirm and Google; that the mail comes in the
  request's language; that `PATCH profile` changes `locale`; that an
  invalid locale is a `400`.
- **Core jobs**: the Normtracker mail contains designation, title and the
  document link; the deletion warning uses `account.locale`.
- **Migration**: upgrade/downgrade, like the existing migration tests.
- **Frontend**: `resolveLocale` unit test; BFF routes forward `locale`;
  `/api/account/locale` forwards only with a session cookie; the
  language switch calls it.

## Out of scope

Dark-mode mail variants, an image logo, bundling several Normtracker
events into one mail, languages beyond German and English, a dedicated
account settings URL.
