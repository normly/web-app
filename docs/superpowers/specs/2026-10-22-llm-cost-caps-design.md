# LLM cost caps — design

Issue: [#40](https://github.com/normly/web-app/issues/40) · Branch:
`feature/40-llm-cost-caps` · Status: approved in brainstorming 2026-10-22

## Problem

Synthesis answers call an open-weight model on STACKIT AI Model Serving,
which bills per token. STACKIT offers rate limits only (requests and tokens
per minute, pooled per project); there is no spending cap — confirmed in the
STACKIT portal. Rate limits bound the speed of spending, not the total, and
let one abuser starve every other user. Today the chat service has neither a
rate limit nor a quota, and `LlmClient.chat` discards the token usage the API
returns.

## Goal

Predictable inference costs from day one, enforced by normly itself. The
worst-case monthly cost must be computable from configuration.

## Decisions

| # | Question | Decision |
|---|---|---|
| 1 | How is the token budget counted? | Actual usage from the API's `usage` field, added after each call. Overshoot bounded by `max_tokens` per call. |
| 2 | How are budgets split? | Two separate pools, `anonymous` and `registered`, each with a daily and a monthly token budget. |
| 3 | Answer cut off (`finish_reason = length`)? | Fallback text, same as the existing verbatim and faithfulness checks. |
| 4 | Unit of the per-user quota? | AI answers (synthesis questions) per day. |
| 5 | Configuration? | Environment variables with small defaults; no UI, no database. |
| 6 | Usage view content? | Personal quota only, plus a notice when the user's pool is exhausted. No global percentages. |
| 7 | Wording? | "KI-Antworten" / "AI answers". |
| 8 | Alerts? | Mail to the Lead Maintainers at 50/80/100 % of each monthly pool budget, plus once when a daily pool budget is exhausted. |

Dropped from the issue: "bounded chat history in the context" (the history
is never sent to the model) and "budgets configurable" as a separate item
(covered by decision 5).

## Scope

Only synthesis questions call the model. Structural questions (validity,
successors, references) are answered from the graph (ADR-008) and are never
counted, limited or blocked — they keep working when every budget is spent.
Search is unaffected.

## Architecture

Approach: counters in the chat service, following the pattern of the existing
`api/` rate limiter. Rejected: a separate LLM gateway service (more to operate
than needed now) and checks in the frontend BFF (bypassable, not server-side).

### Units

- **`LlmClient` (chat/)** — `chat()` returns an `LlmResult(text,
  input_tokens, output_tokens, finish_reason)` instead of a bare string.
  Both clients send the output cap (`max_tokens` for OpenAI-compatible,
  `options.num_predict` for Ollama) and map the provider's fields
  (`usage.prompt_tokens`/`completion_tokens`, `finish_reason`; Ollama
  `prompt_eval_count`/`eval_count`, `done_reason`). If usage is missing, the
  client reports the output cap as output tokens and `ceil(chars / 3)` of the
  prompt as input tokens — conservative.
- **`LlmUsageRepository` (core/, Postgres implementation)** — the only place
  that touches the new tables (ADR-006):
  - `add_tokens(pool, day, input_tokens, output_tokens)` — atomic UPSERT into
    a per-pool, per-UTC-day row; returns the new day and month totals.
  - `pool_totals(pool, day)` — day total and month total (sum of the month's
    day rows).
  - `record_question(key, day, limit) -> (count, allowed)` — atomic UPSERT
    like `PostgresRateLimitRepository.record_and_check`.
  - `question_count(key, day)` — for the usage view.
  - `claim_alert(pool, period, threshold) -> bool` — insert with a unique
    constraint; true only for the caller that created the row.
  - `delete_before(...)` — retention, run opportunistically.
- **`BudgetGuard` (chat/)** — admission and booking, no SQL. Admission checks
  the pool's day and month totals against the budget, then records the
  question against the user's quota. Booking adds tokens after each call and
  triggers alerts.
- **`BudgetSettings` (chat/)** — reads the environment variables once at
  startup; invalid values fail startup.
- **`BudgetAlerter` (chat/)** — sends alert mail through
  `normly_core.notifications.email`. Mail errors are logged and never reach
  the user's request.

### Tables (new Alembic migration in core/)

- `llm_token_usage(pool, day, input_tokens, output_tokens)`, primary key
  `(pool, day)`. No personal data. Retention: 40 days.
- `llm_question_count(key, day, count)`, primary key `(key, day)`. The key
  embeds an account ID or an anon ID plus address. Retention: 2 days.
- `llm_budget_alert(pool, period, threshold, sent_at)`, unique
  `(pool, period, threshold)`; `period` is `YYYY-MM` or `YYYY-MM-DD`.
  Retention: 40 days.

All tables live in the encrypted PostgreSQL instance like every other table.

### Request flow (`POST /v1/chat`)

1. Validate the request. Messages longer than the input limit are rejected
   with 400 and a clear message — never truncated silently.
2. Classify the question as today. Structural → answer as today, no guard.
3. Synthesis → pick the pool: `registered` with a valid account identity,
   otherwise `anonymous`.
4. Admission, in this order:
   1. Pool day total ≥ daily budget → 429 `pool_daily_exhausted`.
   2. Pool month total ≥ monthly budget → 429 `pool_monthly_exhausted`.
   3. Record the question for the user key; over the daily quota →
      429 `quota_exhausted`.
5. Answer call, then booking. `finish_reason = length` → fallback text (the
   faithfulness call is skipped).
6. Faithfulness call, then booking.

A question counts against the quota once admitted, even if a STACKIT call
fails afterwards — no refunds, which keeps the counter simple.

If the database is unreachable during admission or booking, the request fails
(fail-closed): no model call without counting.

User keys: account ID for registered users; for anonymous users
`<anon id>:<origin address>`, derived exactly as in
`api/src/normly_api/rate_limit.py`. The frontend chat route
(`frontend/src/app/api/chat/route.ts`) does not forward
`X-Normly-Anon-Id` and `X-Forwarded-For` to the chat service today; it must,
using `frontend/src/lib/rate-limit-headers.ts`.

All windows are UTC: days reset at 00:00 UTC, months on the 1st at 00:00
UTC. The frontend shows reset times in the user's local time.

### 429 response

```json
{
  "detail": {
    "reason": "quota_exhausted",
    "resets_at": "2026-10-23T00:00:00Z",
    "anonymous": true
  }
}
```

`reason` is one of `quota_exhausted`, `pool_daily_exhausted`,
`pool_monthly_exhausted`. A `Retry-After` header carries the same reset in
seconds.

### Overshoot and worst case

Costs are known only after a call, so concurrent in-flight requests can push
a pool past its budget. Per pool and period the worst case is

    budget + concurrent_requests × 2 calls × (input_cap + output_cap)

The worst-case monthly cost is the sum of both monthly pool budgets plus that
margin, priced at the model's output-token rate as an upper bound.

## Configuration

| Variable | Meaning | Starting default |
|---|---|---|
| `NORMLY_LLM_MAX_OUTPUT_TOKENS` | Output cap per call | 1024 |
| `NORMLY_CHAT_MAX_MESSAGE_CHARS` | Input limit for the user message | 2000 |
| `NORMLY_CHAT_QUOTA_ANONYMOUS_DAILY` | AI answers per anonymous user per day | 10 |
| `NORMLY_CHAT_QUOTA_REGISTERED_DAILY` | AI answers per registered user per day | 30 |
| `NORMLY_LLM_BUDGET_ANONYMOUS_DAILY_TOKENS` | Anonymous pool, per day | 500000 |
| `NORMLY_LLM_BUDGET_ANONYMOUS_MONTHLY_TOKENS` | Anonymous pool, per month | 10000000 |
| `NORMLY_LLM_BUDGET_REGISTERED_DAILY_TOKENS` | Registered pool, per day | 2000000 |
| `NORMLY_LLM_BUDGET_REGISTERED_MONTHLY_TOKENS` | Registered pool, per month | 40000000 |
| `NORMLY_LLM_BUDGET_ALERT_RECIPIENTS` | Comma-separated alert addresses | empty (alerts logged only) |

The defaults are starting points, not measured values. The first
implementation task measures the real STACKIT model with representative
questions: input and output tokens per call and per synthesis answer. The
output cap is set to twice the longest measured answer, and the token
budgets are derived from the measured tokens per answer times the quotas.
The measured values and the derivation are recorded in this spec before the
defaults are finalized.

Recipient addresses are set on the VM, never in the repository.
`MAINTAINERS.md` lists the Lead Maintainers by name only and stays that way.

## Alerts

After each booking the guard compares the pool's month total with 50, 80 and
100 % of the monthly budget, and the day total with 100 % of the daily
budget. For each crossed threshold it calls `claim_alert`; only a successful
claim sends mail. One mail per pool, period and threshold, even under
concurrency — at most two daily-exhaustion mails per day.

The mail (English) names the pool, the threshold, the current total, the
budget and the reset time.

## Usage view

**Endpoint:** `GET /v1/chat/usage` in the chat service, account token
required (401 otherwise). Response:

```json
{
  "used": 7,
  "limit": 30,
  "resets_at": "2026-10-23T00:00:00Z",
  "pool_exhausted": false,
  "pool_resets_at": null
}
```

The frontend reaches it through a new BFF route `/api/account/usage`, like
the other `/api/account/*` routes.

**Profile section "Nutzung" / "Usage":** a new entry in the sidebar of
`frontend/src/components/account/profile-overlay.tsx`, built from shadcn
components in the style of the existing sections:

- section heading and description like the other sections
- shadcn `Progress` (added via the shadcn CLI) labelled
  "KI-Antworten heute: 7 von 30" / "AI answers today: 7 of 30"
- reset line: "Wird zurückgesetzt um 02:00 (in 5 Std.)" in local time
- when the pool is exhausted, a notice: "KI-Antworten sind heute
  ausgelastet, wieder ab 02:00. Suche und Normauskünfte (Gültigkeit,
  Nachfolger, Verweise) funktionieren weiterhin."
- `Skeleton` while loading

Anonymous users have no profile; they see the reset time only in the chat
notice.

**Chat notice on 429:** a localized message chosen by `reason`, with the
reset time. Anonymous users additionally get the hint to sign in
(REQ-ACC-003). Wording follows the usage view ("KI-Antworten", "Suche und
Normauskünfte … funktionieren weiterhin"). English: "AI answers".

## Testing

- Unit: guard pool selection, admission order, all three 429 reasons,
  day and month rollover, `finish_reason = length` → fallback without a
  faithfulness call, structural questions never counted, settings parsing,
  usage-field mapping and the conservative fallback for both clients.
- Repository against real Postgres: atomic counters under concurrent
  requests, month totals, `claim_alert` deduplication under concurrency,
  retention.
- Router: 400 for oversized messages, 429 body and `Retry-After`, usage
  endpoint with and without an account.
- Frontend: usage section (values, reset time, exhausted notice, loading),
  chat notice per reason, anonymous sign-in hint, BFF header forwarding.
- E2E: limit reached → notice shown; a structural question still answered.

## Documentation

- New ADR-029: cost caps enforced by normly because STACKIT offers rate
  limits only; pools, per-user quota, fail-closed. (If another open PR
  claims 029 first, take the next free number.)
- SRS: extend REQ-ACC-003 (quota also for registered users, unit "AI
  answers per day", user notice) and add the pool budgets and alerts next to
  REQ-SEC-004.
- `docs/guide/operations.md`: the new environment variables, alert
  recipients, how to read the counters.
- `docs/reference/chat.md`: the 429 body and the usage endpoint.
- Issue #40: remove the chat-history item and item 6.

## Out of scope

- Response caching for identical questions.
- Spending caps inside STACKIT (none exist).
- A usage view for anonymous users.
