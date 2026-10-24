# LLM Cost Caps Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bound STACKIT inference costs with per-pool token budgets, a daily per-user quota of AI answers, cost alerts to the Lead Maintainers and a usage section in the profile.

**Architecture:** The chat service meters every model call through a `MeteredLlmClient` that books token usage into Postgres via a new `PostgresLlmUsageRepository` (core). A `BudgetGuard` admits synthesis questions only while the pool budget and the user's quota allow it, otherwise the router answers 429 with a reason code. The frontend forwards the anonymous caller key, shows localized notices, and adds a "Nutzung"/"Usage" section to the profile overlay.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2, Alembic, PostgreSQL 16, httpx, pytest + testcontainers; Next.js 16, React 19, shadcn/ui, vitest, Playwright.

**Spec:** `docs/superpowers/specs/2026-10-22-llm-cost-caps-design.md` — read it before starting any task.

## Global Constraints

- Every new source file starts with the license header used in its directory: `# SPDX-License-Identifier: AGPL-3.0-or-later` / `# Copyright (C) 2026 normly contributors` (Python), `// SPDX-License-Identifier: AGPL-3.0-or-later` / `// Copyright (C) 2026 normly contributors` (TypeScript).
- Database access only through repositories in `core/src/normly_core/graph/postgres/repositories.py` (ADR-006). No SQL in `chat/`.
- Pools are exactly `"anonymous"` and `"registered"`.
- 429 reasons are exactly `quota_exhausted`, `pool_daily_exhausted`, `pool_monthly_exhausted`. 400 for an oversized message has detail exactly `message_too_long`.
- All windows are UTC: days reset 00:00 UTC, months on the 1st 00:00 UTC.
- Environment variables and starting defaults (verbatim from the spec): `NORMLY_LLM_MAX_OUTPUT_TOKENS=1024`, `NORMLY_CHAT_MAX_MESSAGE_CHARS=2000`, `NORMLY_CHAT_QUOTA_ANONYMOUS_DAILY=10`, `NORMLY_CHAT_QUOTA_REGISTERED_DAILY=30`, `NORMLY_LLM_BUDGET_ANONYMOUS_DAILY_TOKENS=500000`, `NORMLY_LLM_BUDGET_ANONYMOUS_MONTHLY_TOKENS=10000000`, `NORMLY_LLM_BUDGET_REGISTERED_DAILY_TOKENS=2000000`, `NORMLY_LLM_BUDGET_REGISTERED_MONTHLY_TOKENS=40000000`, `NORMLY_LLM_BUDGET_ALERT_RECIPIENTS` (comma-separated, default empty).
- No e-mail address of a real person anywhere in the repository (code, tests, docs). Tests use `@example.org`.
- UI wording: "KI-Antworten" (de) / "AI answers" (en). Never "Strukturfragen" in user-facing text.
- Frontend UI only from shadcn components in `frontend/src/components/ui/`, styled like the existing account sections.
- Commits: Conventional Commits, `git commit -s` (signs off with the configured human identity), and the trailer `Assisted-by: Claude Code` as the last line of the message body. Never add a `Signed-off-by` or `Co-Authored-By` for an AI.
- Never push; never open a PR. The user decides when CI runs.

Test commands (from the repository root):

- core: `cd core && ../.venv/bin/pytest <path> -v`
- chat: `cd chat && ../.venv/bin/pytest <path> -v`
- frontend: `cd frontend && npx vitest run <path>`

---

## File Structure

**core/**
- Modify `core/src/normly_core/graph/domain.py` — `LlmPoolTotals` value object and `LlmUsageRepository` protocol.
- Modify `core/src/normly_core/graph/postgres/orm.py` — three ORM classes.
- Create `core/migrations/versions/0040_llm_usage.py` — the three tables.
- Modify `core/src/normly_core/graph/postgres/repositories.py` — `PostgresLlmUsageRepository`.
- Create `core/tests/graph/test_llm_usage_repository.py`.

**chat/**
- Create `chat/src/normly_chat/llm_result.py` — `LlmResult`, `estimate_input_tokens`.
- Modify `chat/src/normly_chat/llm_client.py`, `chat/src/normly_chat/ollama_client.py` — `complete()`, output cap, usage mapping.
- Create `chat/src/normly_chat/budget_settings.py` — `PoolBudget`, `BudgetSettings.from_env`.
- Create `chat/src/normly_chat/budget_alerts.py` — `BudgetAlert`, `BudgetAlerter`.
- Create `chat/src/normly_chat/budget_guard.py` — pools, `BudgetExhausted`, `QuotaStatus`, `BudgetGuard`.
- Create `chat/src/normly_chat/metered_llm_client.py` — `LlmOutputTruncated`, `MeteredLlmClient`.
- Create `chat/src/normly_chat/caller_key.py` — anonymous caller key.
- Create `chat/src/normly_chat/routers/usage.py` — `GET /v1/chat/usage`.
- Create `chat/src/normly_chat/measure_usage.py` — measurement module.
- Modify `chat/src/normly_chat/{synthesis,titles,dependencies,errors,main,schemas}.py`, `chat/src/normly_chat/routers/{chat,sessions}.py`.
- Tests: `chat/tests/test_llm_client.py`, `test_ollama_client.py`, `test_budget_settings.py`, `test_budget_alerts.py`, `test_budget_guard.py`, `test_metered_llm_client.py`, `test_caller_key.py`, `test_synthesis.py`, `test_titles.py`, `test_chat_router.py`, `test_sessions_router.py`, `test_usage_router.py`.

**frontend/**
- Modify `frontend/src/app/api/chat/route.ts` — forward caller headers.
- Create `frontend/src/app/api/account/usage/route.ts`.
- Create `frontend/src/lib/i18n/interpolate.ts`, `frontend/src/lib/reset-time.ts`, `frontend/src/lib/chat-error-notice.ts`.
- Modify `frontend/src/app/home-page-content.tsx`, `frontend/src/components/chat/chat-input.tsx`.
- Create `frontend/src/components/ui/progress.tsx` (shadcn CLI), `frontend/src/components/account/usage-section.tsx`.
- Modify `frontend/src/components/account/profile-overlay.tsx`, `frontend/src/lib/i18n/de.json`, `frontend/src/lib/i18n/en.json`.
- Tests under `frontend/tests/unit/` and `frontend/tests/e2e/usage-limits.spec.ts`.

**docs and config:** `docs/adr/README.md` (ADR-029), `docs/srs/03-requirements.md`, `docs/guide/operations.md`, `.env.example`, the spec.

---

### Task 1: LLM clients report token usage and truncation

**Files:**
- Create: `chat/src/normly_chat/llm_result.py`
- Modify: `chat/src/normly_chat/llm_client.py`
- Modify: `chat/src/normly_chat/ollama_client.py`
- Test: `chat/tests/test_llm_client.py`, `chat/tests/test_ollama_client.py`

**Interfaces:**
- Produces: `LlmResult(text: str, input_tokens: int, output_tokens: int, truncated: bool)` (frozen dataclass); `estimate_input_tokens(messages: list[dict]) -> int`; `LlmClient` protocol with `complete(messages: list[dict]) -> LlmResult`; `OpenAiCompatibleClient(base_url, model, api_key, *, max_output_tokens: int, timeout=120.0, transport=None)`; `OllamaClient(base_url, model, *, max_output_tokens: int, timeout=120.0, transport=None)`; `build_llm_client_from_env(environ=os.environ, *, max_output_tokens: int) -> LlmClient`.
- Transitional: both providers keep `chat(messages) -> str` returning `self.complete(messages).text` until Task 6 removes it.

- [ ] **Step 1: Write the failing tests**

Replace the first test in `chat/tests/test_llm_client.py` and add new ones. Every `OpenAiCompatibleClient(...)` and `build_llm_client_from_env(...)` call in this file now passes `max_output_tokens=...`.

```python
def test_openai_compatible_client_posts_chat_completions_and_returns_a_result():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["auth"] = request.headers.get("authorization")
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={
            "choices": [{
                "message": {"role": "assistant", "content": "Antwort"},
                "finish_reason": "stop",
            }],
            "usage": {"prompt_tokens": 120, "completion_tokens": 30, "total_tokens": 150},
        })

    client = OpenAiCompatibleClient(
        "https://llm.example/v1/", "google/gemma-4-31B-it", "secret-token",
        max_output_tokens=512, transport=_transport(handler),
    )
    result = client.complete([{"role": "user", "content": "Frage"}])

    assert result == LlmResult(text="Antwort", input_tokens=120, output_tokens=30, truncated=False)
    assert seen["url"] == "https://llm.example/v1/chat/completions"
    assert seen["auth"] == "Bearer secret-token"
    assert seen["body"]["model"] == "google/gemma-4-31B-it"
    assert seen["body"]["messages"] == [{"role": "user", "content": "Frage"}]
    assert seen["body"]["stream"] is False
    assert seen["body"]["max_tokens"] == 512


def test_openai_compatible_client_flags_a_length_cut_answer_as_truncated():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={
            "choices": [{"message": {"content": "Halbe Antw"}, "finish_reason": "length"}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 512},
        })

    client = OpenAiCompatibleClient(
        "https://llm.example/v1", "m", "t", max_output_tokens=512, transport=_transport(handler),
    )
    assert client.complete([{"role": "user", "content": "x"}]).truncated is True


def test_openai_compatible_client_books_conservatively_when_usage_is_missing():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={
            "choices": [{"message": {"content": "Antwort"}, "finish_reason": "stop"}],
        })

    client = OpenAiCompatibleClient(
        "https://llm.example/v1", "m", "t", max_output_tokens=512, transport=_transport(handler),
    )
    result = client.complete([{"role": "user", "content": "x" * 30}])

    assert result.input_tokens == 10
    assert result.output_tokens == 512


def test_estimate_input_tokens_rounds_up_a_third_of_all_characters():
    assert estimate_input_tokens([
        {"role": "system", "content": "abcd"}, {"role": "user", "content": "ef"},
    ]) == 2


def test_build_from_env_passes_the_output_cap_to_the_client():
    client = build_llm_client_from_env({
        "NORMLY_LLM_PROVIDER": "openai-compatible",
        "NORMLY_LLM_BASE_URL": "https://llm.example/v1",
        "NORMLY_LLM_MODEL": "m",
        "NORMLY_LLM_API_KEY": "t",
    }, max_output_tokens=256)
    assert client._max_output_tokens == 256
```

Update the imports at the top of `chat/tests/test_llm_client.py`:

```python
from normly_chat.llm_client import OpenAiCompatibleClient, build_llm_client_from_env
from normly_chat.llm_result import LlmResult, estimate_input_tokens
from normly_chat.ollama_client import OllamaClient
```

Add Ollama mapping tests to `chat/tests/test_llm_client.py` (they use a mock transport and run without a server; the existing `chat/tests/test_ollama_client.py` stays a live-server test):

```python
def test_ollama_client_sends_num_predict_and_maps_its_counters():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={
            "message": {"role": "assistant", "content": "Antwort"},
            "done_reason": "stop", "prompt_eval_count": 80, "eval_count": 20,
        })

    client = OllamaClient(
        "http://ollama:11434", "gemma4:e4b", max_output_tokens=300, transport=_transport(handler),
    )
    result = client.complete([{"role": "user", "content": "Frage"}])

    assert result == LlmResult(text="Antwort", input_tokens=80, output_tokens=20, truncated=False)
    assert seen["body"]["options"] == {"num_predict": 300}


def test_ollama_client_flags_done_reason_length_as_truncated():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={
            "message": {"content": "Halb"}, "done_reason": "length",
            "prompt_eval_count": 5, "eval_count": 300,
        })

    client = OllamaClient("http://ollama:11434", "m", max_output_tokens=300, transport=_transport(handler))
    assert client.complete([{"role": "user", "content": "x"}]).truncated is True
```

In `chat/tests/test_ollama_client.py`, change the fixture to pass `max_output_tokens=256` and the test to:

```python
def test_complete_returns_a_non_empty_answer_with_usage(ollama_client):
    result = ollama_client.complete(
        [{"role": "user", "content": "Antworte nur mit dem Wort: Test"}]
    )
    assert result.text
    assert result.output_tokens > 0
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd chat && ../.venv/bin/pytest tests/test_llm_client.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'normly_chat.llm_result'`.

- [ ] **Step 3: Implement**

Create `chat/src/normly_chat/llm_result.py`:

```python
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

"""What one model call produced and what it cost."""

from __future__ import annotations

import math
from dataclasses import dataclass

# Rough characters-per-token ratio for German and English text. Only used
# when a provider omits its usage figures; a low ratio over-counts, which is
# the safe direction for a budget.
_CHARS_PER_TOKEN = 3


@dataclass(frozen=True)
class LlmResult:
    text: str
    input_tokens: int
    output_tokens: int
    # The provider stopped because the output cap was reached.
    truncated: bool


def estimate_input_tokens(messages: list[dict]) -> int:
    characters = sum(len(message.get("content") or "") for message in messages)
    return math.ceil(characters / _CHARS_PER_TOKEN)
```

In `chat/src/normly_chat/llm_client.py` replace the protocol, the client and the builder:

```python
from normly_chat.llm_result import LlmResult, estimate_input_tokens
from normly_chat.ollama_client import OllamaClient

...


class LlmClient(Protocol):
    def complete(self, messages: list[dict]) -> LlmResult: ...


class OpenAiCompatibleClient:
    """POST {base_url}/chat/completions with a bearer token; returns the first choice."""

    def __init__(
        self, base_url: str, model: str, api_key: str, *, max_output_tokens: int,
        timeout: float = 120.0, transport: httpx.BaseTransport | None = None,
    ):
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._api_key = api_key
        self._max_output_tokens = max_output_tokens
        self._timeout = timeout
        self._transport = transport

    def complete(self, messages: list[dict]) -> LlmResult:
        with httpx.Client(timeout=self._timeout, transport=self._transport) as http:
            response = http.post(
                f"{self._base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self._api_key}"},
                json={
                    "model": self._model, "messages": messages, "stream": False,
                    "max_tokens": self._max_output_tokens,
                },
            )
        response.raise_for_status()
        body = response.json()
        choice = body["choices"][0]
        usage = body.get("usage") or {}
        # Missing usage is booked conservatively: the full output cap plus an
        # estimate of the prompt, so a silent provider can never undercount.
        return LlmResult(
            text=choice["message"]["content"],
            input_tokens=usage.get("prompt_tokens", estimate_input_tokens(messages)),
            output_tokens=usage.get("completion_tokens", self._max_output_tokens),
            truncated=choice.get("finish_reason") == "length",
        )

    # Transitional until every caller goes through MeteredLlmClient (Task 6).
    def chat(self, messages: list[dict]) -> str:
        return self.complete(messages).text


def build_llm_client_from_env(
    environ: Mapping[str, str] = os.environ, *, max_output_tokens: int,
) -> LlmClient:
    provider = environ.get(PROVIDER_ENV_VAR, PROVIDER_OLLAMA)
    base_url = environ[BASE_URL_ENV_VAR]
    model = environ[MODEL_ENV_VAR]
    if provider == PROVIDER_OLLAMA:
        return OllamaClient(base_url=base_url, model=model, max_output_tokens=max_output_tokens)
    if provider == PROVIDER_OPENAI_COMPATIBLE:
        return OpenAiCompatibleClient(
            base_url, model, environ[API_KEY_ENV_VAR], max_output_tokens=max_output_tokens,
        )
    raise ValueError(
        f"{PROVIDER_ENV_VAR} must be {PROVIDER_OLLAMA!r} or {PROVIDER_OPENAI_COMPATIBLE!r}, "
        f"got {provider!r}"
    )
```

Replace the class body in `chat/src/normly_chat/ollama_client.py` (keep the docstring):

```python
from normly_chat.llm_result import LlmResult, estimate_input_tokens


class OllamaClient:
    # (existing docstring)

    def __init__(
        self, base_url: str, model: str, *, max_output_tokens: int, timeout: float = 120.0,
        transport: httpx.BaseTransport | None = None,
    ):
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._max_output_tokens = max_output_tokens
        self._timeout = timeout
        self._transport = transport

    def complete(self, messages: list[dict]) -> LlmResult:
        with httpx.Client(timeout=self._timeout, transport=self._transport) as http:
            response = http.post(
                f"{self._base_url}/api/chat",
                json={
                    "model": self._model, "messages": messages, "stream": False,
                    "options": {"num_predict": self._max_output_tokens},
                },
            )
        response.raise_for_status()
        body = response.json()
        return LlmResult(
            text=body["message"]["content"],
            input_tokens=body.get("prompt_eval_count", estimate_input_tokens(messages)),
            output_tokens=body.get("eval_count", self._max_output_tokens),
            truncated=body.get("done_reason") == "length",
        )

    # Transitional until every caller goes through MeteredLlmClient (Task 6).
    def chat(self, messages: list[dict]) -> str:
        return self.complete(messages).text
```

In `chat/src/normly_chat/main.py`, the lifespan call becomes `build_llm_client_from_env(max_output_tokens=1024)` for now; Task 6 replaces the literal with the setting.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd chat && ../.venv/bin/pytest tests/test_llm_client.py tests/test_synthesis.py tests/test_titles.py -v`
Expected: PASS (test_ollama_client.py is skipped without a live server).

- [ ] **Step 5: Commit**

```bash
git add chat/src/normly_chat/llm_result.py chat/src/normly_chat/llm_client.py \
  chat/src/normly_chat/ollama_client.py chat/src/normly_chat/main.py \
  chat/tests/test_llm_client.py chat/tests/test_ollama_client.py
git commit -s -m "feat(chat): report token usage and truncation from both LLM clients" \
  -m "Refs #40" -m "Assisted-by: Claude Code"
```

---

### Task 2: Budget settings from the environment

**Files:**
- Create: `chat/src/normly_chat/budget_settings.py`
- Test: `chat/tests/test_budget_settings.py`

**Interfaces:**
- Produces: `PoolBudget(daily_tokens: int, monthly_tokens: int)`; `BudgetSettings(max_output_tokens: int, max_message_chars: int, anonymous_daily_quota: int, registered_daily_quota: int, pools: Mapping[str, PoolBudget], alert_recipients: tuple[str, ...])` with `BudgetSettings.from_env(environ=os.environ) -> BudgetSettings`. `pools` keys are `"anonymous"` and `"registered"`.

- [ ] **Step 1: Write the failing tests**

```python
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

import pytest

from normly_chat.budget_settings import BudgetSettings, PoolBudget


def test_defaults_apply_when_nothing_is_set():
    settings = BudgetSettings.from_env({})

    assert settings.max_output_tokens == 1024
    assert settings.max_message_chars == 2000
    assert settings.anonymous_daily_quota == 10
    assert settings.registered_daily_quota == 30
    assert settings.pools["anonymous"] == PoolBudget(daily_tokens=500_000, monthly_tokens=10_000_000)
    assert settings.pools["registered"] == PoolBudget(daily_tokens=2_000_000, monthly_tokens=40_000_000)
    assert settings.alert_recipients == ()


def test_values_are_read_from_the_environment():
    settings = BudgetSettings.from_env({
        "NORMLY_LLM_MAX_OUTPUT_TOKENS": "800",
        "NORMLY_CHAT_MAX_MESSAGE_CHARS": "1500",
        "NORMLY_CHAT_QUOTA_ANONYMOUS_DAILY": "5",
        "NORMLY_CHAT_QUOTA_REGISTERED_DAILY": "50",
        "NORMLY_LLM_BUDGET_ANONYMOUS_DAILY_TOKENS": "1000",
        "NORMLY_LLM_BUDGET_ANONYMOUS_MONTHLY_TOKENS": "20000",
        "NORMLY_LLM_BUDGET_REGISTERED_DAILY_TOKENS": "3000",
        "NORMLY_LLM_BUDGET_REGISTERED_MONTHLY_TOKENS": "60000",
        "NORMLY_LLM_BUDGET_ALERT_RECIPIENTS": " lead-a@example.org, lead-b@example.org ,",
    })

    assert settings.max_output_tokens == 800
    assert settings.max_message_chars == 1500
    assert settings.anonymous_daily_quota == 5
    assert settings.registered_daily_quota == 50
    assert settings.pools["anonymous"] == PoolBudget(daily_tokens=1000, monthly_tokens=20000)
    assert settings.pools["registered"] == PoolBudget(daily_tokens=3000, monthly_tokens=60000)
    assert settings.alert_recipients == ("lead-a@example.org", "lead-b@example.org")


@pytest.mark.parametrize("value", ["0", "-3", "abc", ""])
def test_a_non_positive_or_non_numeric_value_fails_naming_the_variable(value):
    with pytest.raises(ValueError, match="NORMLY_CHAT_QUOTA_ANONYMOUS_DAILY"):
        BudgetSettings.from_env({"NORMLY_CHAT_QUOTA_ANONYMOUS_DAILY": value})


def test_a_daily_budget_above_the_monthly_budget_fails():
    with pytest.raises(ValueError, match="NORMLY_LLM_BUDGET_ANONYMOUS_DAILY_TOKENS"):
        BudgetSettings.from_env({
            "NORMLY_LLM_BUDGET_ANONYMOUS_DAILY_TOKENS": "200",
            "NORMLY_LLM_BUDGET_ANONYMOUS_MONTHLY_TOKENS": "100",
        })
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd chat && ../.venv/bin/pytest tests/test_budget_settings.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'normly_chat.budget_settings'`.

- [ ] **Step 3: Implement**

```python
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

"""
Cost-cap configuration (issue #40). Read once at startup; an invalid value
fails startup instead of silently running without a cap.

The defaults are starting points, not measured values -- see the design spec
(docs/superpowers/specs/2026-10-22-llm-cost-caps-design.md) for how they are
derived from a measurement of the real model.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass

_DEFAULTS = {
    "NORMLY_LLM_MAX_OUTPUT_TOKENS": 1024,
    "NORMLY_CHAT_MAX_MESSAGE_CHARS": 2000,
    "NORMLY_CHAT_QUOTA_ANONYMOUS_DAILY": 10,
    "NORMLY_CHAT_QUOTA_REGISTERED_DAILY": 30,
    "NORMLY_LLM_BUDGET_ANONYMOUS_DAILY_TOKENS": 500_000,
    "NORMLY_LLM_BUDGET_ANONYMOUS_MONTHLY_TOKENS": 10_000_000,
    "NORMLY_LLM_BUDGET_REGISTERED_DAILY_TOKENS": 2_000_000,
    "NORMLY_LLM_BUDGET_REGISTERED_MONTHLY_TOKENS": 40_000_000,
}
_RECIPIENTS_VAR = "NORMLY_LLM_BUDGET_ALERT_RECIPIENTS"


@dataclass(frozen=True)
class PoolBudget:
    daily_tokens: int
    monthly_tokens: int


@dataclass(frozen=True)
class BudgetSettings:
    max_output_tokens: int
    max_message_chars: int
    anonymous_daily_quota: int
    registered_daily_quota: int
    pools: Mapping[str, PoolBudget]
    alert_recipients: tuple[str, ...]

    @classmethod
    def from_env(cls, environ: Mapping[str, str] = os.environ) -> BudgetSettings:
        def positive(name: str) -> int:
            raw = environ.get(name)
            if raw is None:
                return _DEFAULTS[name]
            try:
                value = int(raw)
            except ValueError:
                raise ValueError(f"{name} must be a positive integer, got {raw!r}") from None
            if value <= 0:
                raise ValueError(f"{name} must be a positive integer, got {raw!r}")
            return value

        def pool(prefix: str) -> PoolBudget:
            daily_var = f"NORMLY_LLM_BUDGET_{prefix}_DAILY_TOKENS"
            budget = PoolBudget(
                daily_tokens=positive(daily_var),
                monthly_tokens=positive(f"NORMLY_LLM_BUDGET_{prefix}_MONTHLY_TOKENS"),
            )
            if budget.daily_tokens > budget.monthly_tokens:
                raise ValueError(f"{daily_var} must not exceed the monthly budget")
            return budget

        recipients = tuple(
            address.strip()
            for address in environ.get(_RECIPIENTS_VAR, "").split(",")
            if address.strip()
        )
        return cls(
            max_output_tokens=positive("NORMLY_LLM_MAX_OUTPUT_TOKENS"),
            max_message_chars=positive("NORMLY_CHAT_MAX_MESSAGE_CHARS"),
            anonymous_daily_quota=positive("NORMLY_CHAT_QUOTA_ANONYMOUS_DAILY"),
            registered_daily_quota=positive("NORMLY_CHAT_QUOTA_REGISTERED_DAILY"),
            pools={"anonymous": pool("ANONYMOUS"), "registered": pool("REGISTERED")},
            alert_recipients=recipients,
        )
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd chat && ../.venv/bin/pytest tests/test_budget_settings.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add chat/src/normly_chat/budget_settings.py chat/tests/test_budget_settings.py
git commit -s -m "feat(chat): read cost-cap settings from the environment" \
  -m "Refs #40" -m "Assisted-by: Claude Code"
```

---

### Task 3: Usage tables and repository (core)

**Files:**
- Modify: `core/src/normly_core/graph/domain.py` (append)
- Modify: `core/src/normly_core/graph/postgres/orm.py` (append)
- Create: `core/migrations/versions/0040_llm_usage.py`
- Modify: `core/src/normly_core/graph/postgres/repositories.py` (append; add the ORM imports to the existing `from normly_core.graph.postgres.orm import (...)` block and `LlmPoolTotals` to the domain import block)
- Test: `core/tests/graph/test_llm_usage_repository.py`

**Interfaces:**
- Produces (domain): `LlmPoolTotals(day_tokens: int, month_tokens: int)` frozen dataclass; `LlmUsageRepository` protocol with the methods below.
- Produces (`PostgresLlmUsageRepository(session)`), all keyword-only, flush but never commit:
  - `add_tokens(*, pool: str, day: date, input_tokens: int, output_tokens: int) -> LlmPoolTotals`
  - `pool_totals(*, pool: str, day: date) -> LlmPoolTotals` — day total = that day's input+output; month total = sum over the 1st of `day`'s month up to and including `day`.
  - `record_question(*, key: str, day: date, limit: int) -> tuple[int, bool]` — new count and `count <= limit`.
  - `question_count(*, key: str, day: date) -> int` — 0 when no row.
  - `claim_alert(*, pool: str, period: str, threshold: int, now: datetime) -> bool`
  - `delete_expired(*, question_before: date, usage_before: date) -> None` — deletes question rows with `day < question_before`, usage rows with `day < usage_before`, alert rows with `sent_at < usage_before` (midnight UTC).

- [ ] **Step 1: Write the failing tests**

Create `core/tests/graph/test_llm_usage_repository.py`:

```python
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timezone

import sqlalchemy as sa
from sqlalchemy.orm import Session

from normly_core.graph.domain import LlmPoolTotals
from normly_core.graph.postgres.orm import (
    LlmBudgetAlertORM,
    LlmQuestionCountORM,
    LlmTokenUsageORM,
)
from normly_core.graph.postgres.repositories import PostgresLlmUsageRepository

_NOW = datetime(2026, 10, 22, 9, 0, tzinfo=timezone.utc)


def test_add_tokens_accumulates_and_returns_day_and_month_totals(db_session):
    repo = PostgresLlmUsageRepository(db_session)
    repo.add_tokens(pool="anonymous", day=date(2026, 10, 21), input_tokens=100, output_tokens=50)
    repo.add_tokens(pool="anonymous", day=date(2026, 10, 22), input_tokens=10, output_tokens=5)

    totals = repo.add_tokens(
        pool="anonymous", day=date(2026, 10, 22), input_tokens=20, output_tokens=5,
    )

    assert totals == LlmPoolTotals(day_tokens=40, month_tokens=190)


def test_pool_totals_ignore_other_pools_and_previous_months(db_session):
    repo = PostgresLlmUsageRepository(db_session)
    repo.add_tokens(pool="anonymous", day=date(2026, 9, 30), input_tokens=1000, output_tokens=0)
    repo.add_tokens(pool="registered", day=date(2026, 10, 22), input_tokens=500, output_tokens=0)
    repo.add_tokens(pool="anonymous", day=date(2026, 10, 1), input_tokens=7, output_tokens=0)

    assert repo.pool_totals(pool="anonymous", day=date(2026, 10, 22)) == LlmPoolTotals(
        day_tokens=0, month_tokens=7,
    )


def test_record_question_counts_per_key_and_day_and_reports_the_limit(db_session):
    repo = PostgresLlmUsageRepository(db_session)
    day = date(2026, 10, 22)

    assert repo.record_question(key="account:a", day=day, limit=2) == (1, True)
    assert repo.record_question(key="account:a", day=day, limit=2) == (2, True)
    assert repo.record_question(key="account:a", day=day, limit=2) == (3, False)
    assert repo.record_question(key="account:b", day=day, limit=2) == (1, True)
    assert repo.record_question(key="account:a", day=date(2026, 10, 23), limit=2) == (1, True)
    assert repo.question_count(key="account:a", day=day) == 3
    assert repo.question_count(key="account:unknown", day=day) == 0


def test_claim_alert_succeeds_only_once_per_pool_period_and_threshold(db_session):
    repo = PostgresLlmUsageRepository(db_session)

    assert repo.claim_alert(pool="anonymous", period="2026-10", threshold=50, now=_NOW) is True
    assert repo.claim_alert(pool="anonymous", period="2026-10", threshold=50, now=_NOW) is False
    assert repo.claim_alert(pool="anonymous", period="2026-10", threshold=80, now=_NOW) is True
    assert repo.claim_alert(pool="registered", period="2026-10", threshold=50, now=_NOW) is True


def test_delete_expired_removes_only_old_rows(db_session):
    repo = PostgresLlmUsageRepository(db_session)
    repo.record_question(key="k", day=date(2026, 10, 20), limit=5)
    repo.record_question(key="k", day=date(2026, 10, 21), limit=5)
    repo.add_tokens(pool="anonymous", day=date(2026, 9, 1), input_tokens=1, output_tokens=0)
    repo.add_tokens(pool="anonymous", day=date(2026, 10, 1), input_tokens=1, output_tokens=0)
    repo.claim_alert(
        pool="anonymous", period="2026-08", threshold=50,
        now=datetime(2026, 8, 31, tzinfo=timezone.utc),
    )
    repo.claim_alert(pool="anonymous", period="2026-10", threshold=50, now=_NOW)

    repo.delete_expired(question_before=date(2026, 10, 21), usage_before=date(2026, 9, 12))

    assert db_session.execute(sa.select(LlmQuestionCountORM.day)).scalars().all() == [
        date(2026, 10, 21),
    ]
    assert db_session.execute(sa.select(LlmTokenUsageORM.day)).scalars().all() == [
        date(2026, 10, 1),
    ]
    assert db_session.execute(sa.select(LlmBudgetAlertORM.period)).scalars().all() == ["2026-10"]


def test_concurrent_questions_and_alert_claims_are_counted_exactly(migrated_engine):
    # Real commits from parallel sessions: the atomicity under concurrency is
    # the point, which the rolled-back db_session fixture cannot show.
    key = f"concurrency:{uuid.uuid4()}"
    period = f"test-{uuid.uuid4().hex[:6]}"
    day = date(2026, 10, 22)

    def record(_):
        with Session(migrated_engine) as session:
            PostgresLlmUsageRepository(session).record_question(key=key, day=day, limit=100)
            session.commit()

    def claim(_):
        with Session(migrated_engine) as session:
            claimed = PostgresLlmUsageRepository(session).claim_alert(
                pool="anonymous", period=period, threshold=100, now=_NOW,
            )
            session.commit()
            return claimed

    try:
        with ThreadPoolExecutor(max_workers=10) as pool:
            list(pool.map(record, range(20)))
            claims = list(pool.map(claim, range(10)))

        with Session(migrated_engine) as session:
            assert PostgresLlmUsageRepository(session).question_count(key=key, day=day) == 20
        assert claims.count(True) == 1
    finally:
        with Session(migrated_engine) as session:
            session.execute(sa.delete(LlmQuestionCountORM).where(LlmQuestionCountORM.key == key))
            session.execute(sa.delete(LlmBudgetAlertORM).where(LlmBudgetAlertORM.period == period))
            session.commit()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd core && ../.venv/bin/pytest tests/graph/test_llm_usage_repository.py -v`
Expected: FAIL — `ImportError: cannot import name 'LlmPoolTotals'`.

- [ ] **Step 3: Implement the domain types**

Append to `core/src/normly_core/graph/domain.py` (it already imports `dataclass`, `date`, `datetime` and `Protocol`; add any that are missing):

```python
@dataclass(frozen=True)
class LlmPoolTotals:
    """Tokens (input + output) a cost pool has used today and this month."""

    day_tokens: int
    month_tokens: int


class LlmUsageRepository(Protocol):
    """Counters for the LLM cost caps (issue #40). Never commits."""

    def add_tokens(
        self, *, pool: str, day: date, input_tokens: int, output_tokens: int,
    ) -> LlmPoolTotals: ...

    def pool_totals(self, *, pool: str, day: date) -> LlmPoolTotals: ...

    def record_question(self, *, key: str, day: date, limit: int) -> tuple[int, bool]: ...

    def question_count(self, *, key: str, day: date) -> int: ...

    def claim_alert(self, *, pool: str, period: str, threshold: int, now: datetime) -> bool: ...

    def delete_expired(self, *, question_before: date, usage_before: date) -> None: ...
```

- [ ] **Step 4: Implement the ORM classes**

Append to `core/src/normly_core/graph/postgres/orm.py`:

```python
class LlmTokenUsageORM(Base):
    __tablename__ = "llm_token_usage"

    pool: Mapped[str] = mapped_column(sa.String(16), primary_key=True)
    day: Mapped[date] = mapped_column(sa.Date, primary_key=True)
    input_tokens: Mapped[int] = mapped_column(sa.BigInteger, default=0)
    output_tokens: Mapped[int] = mapped_column(sa.BigInteger, default=0)

    __table_args__ = (
        sa.CheckConstraint("pool IN ('anonymous', 'registered')", name="ck_llm_token_usage_pool"),
    )


class LlmQuestionCountORM(Base):
    __tablename__ = "llm_question_count"

    # Embeds an account ID or an anon ID plus caller address -- kept for two
    # days only (see the retention in BudgetGuard).
    key: Mapped[str] = mapped_column(primary_key=True)
    day: Mapped[date] = mapped_column(sa.Date, primary_key=True)
    question_count: Mapped[int] = mapped_column(default=0)

    __table_args__ = (sa.Index("ix_llm_question_count_day", "day"),)


class LlmBudgetAlertORM(Base):
    __tablename__ = "llm_budget_alert"

    # The composite key is the dedup: one alert per pool, period and threshold.
    pool: Mapped[str] = mapped_column(sa.String(16), primary_key=True)
    period: Mapped[str] = mapped_column(sa.String(10), primary_key=True)
    threshold: Mapped[int] = mapped_column(primary_key=True)
    sent_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True))
```

- [ ] **Step 5: Write the migration**

Create `core/migrations/versions/0040_llm_usage.py`:

```python
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

"""add LLM cost-cap counters

Token usage per cost pool and UTC day, AI answers per caller and day, and the
dedup record of sent budget alerts (issue #40).

Revision ID: 0040
Revises: 0039
Create Date: 2026-10-22
"""

import sqlalchemy as sa
from alembic import op

revision = "0040"
down_revision = "0039"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "llm_token_usage",
        sa.Column("pool", sa.String(16), primary_key=True),
        sa.Column("day", sa.Date, primary_key=True),
        sa.Column("input_tokens", sa.BigInteger, nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.BigInteger, nullable=False, server_default="0"),
        sa.CheckConstraint("pool IN ('anonymous', 'registered')", name="ck_llm_token_usage_pool"),
    )
    op.create_table(
        "llm_question_count",
        sa.Column("key", sa.String, primary_key=True),
        sa.Column("day", sa.Date, primary_key=True),
        sa.Column("question_count", sa.Integer, nullable=False, server_default="0"),
    )
    op.create_index("ix_llm_question_count_day", "llm_question_count", ["day"])
    op.create_table(
        "llm_budget_alert",
        sa.Column("pool", sa.String(16), primary_key=True),
        sa.Column("period", sa.String(10), primary_key=True),
        sa.Column("threshold", sa.Integer, primary_key=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("llm_budget_alert")
    op.drop_index("ix_llm_question_count_day", table_name="llm_question_count")
    op.drop_table("llm_question_count")
    op.drop_table("llm_token_usage")
```

Before writing it, run `git fetch origin && git ls-tree --name-only origin/develop core/migrations/versions/`. If a `0040_*` already exists on `develop`, use the next free number and set `down_revision` to the latest one.

- [ ] **Step 6: Implement the repository**

Append to `core/src/normly_core/graph/postgres/repositories.py` (add `timedelta`/`time` imports only if needed; `pg_insert`, `sa`, `select`, `date`, `datetime`, `timezone` are already imported):

```python
class PostgresLlmUsageRepository:
    """Counters for the LLM cost caps. Flushes, never commits."""

    def __init__(self, session: Session):
        self._session = session

    def add_tokens(
        self, *, pool: str, day: date, input_tokens: int, output_tokens: int,
    ) -> LlmPoolTotals:
        stmt = (
            pg_insert(LlmTokenUsageORM)
            .values(pool=pool, day=day, input_tokens=input_tokens, output_tokens=output_tokens)
            .on_conflict_do_update(
                index_elements=["pool", "day"],
                set_={
                    "input_tokens": LlmTokenUsageORM.input_tokens + input_tokens,
                    "output_tokens": LlmTokenUsageORM.output_tokens + output_tokens,
                },
            )
        )
        self._session.execute(stmt)
        self._session.flush()
        return self.pool_totals(pool=pool, day=day)

    def pool_totals(self, *, pool: str, day: date) -> LlmPoolTotals:
        rows = self._session.execute(
            select(
                LlmTokenUsageORM.day,
                LlmTokenUsageORM.input_tokens + LlmTokenUsageORM.output_tokens,
            ).where(
                LlmTokenUsageORM.pool == pool,
                LlmTokenUsageORM.day >= day.replace(day=1),
                LlmTokenUsageORM.day <= day,
            )
        ).all()
        return LlmPoolTotals(
            day_tokens=sum(total for row_day, total in rows if row_day == day),
            month_tokens=sum(total for _, total in rows),
        )

    def record_question(self, *, key: str, day: date, limit: int) -> tuple[int, bool]:
        # Atomic under concurrent requests, like PostgresRateLimitRepository.
        stmt = (
            pg_insert(LlmQuestionCountORM)
            .values(key=key, day=day, question_count=1)
            .on_conflict_do_update(
                index_elements=["key", "day"],
                set_={"question_count": LlmQuestionCountORM.question_count + 1},
            )
            .returning(LlmQuestionCountORM.question_count)
        )
        count = self._session.execute(stmt).scalar_one()
        self._session.flush()
        return count, count <= limit

    def question_count(self, *, key: str, day: date) -> int:
        count = self._session.execute(
            select(LlmQuestionCountORM.question_count).where(
                LlmQuestionCountORM.key == key, LlmQuestionCountORM.day == day,
            )
        ).scalar_one_or_none()
        return count or 0

    def claim_alert(self, *, pool: str, period: str, threshold: int, now: datetime) -> bool:
        # Exactly one caller gets the inserted row back; everyone else
        # conflicts and sends nothing.
        stmt = (
            pg_insert(LlmBudgetAlertORM)
            .values(pool=pool, period=period, threshold=threshold, sent_at=now)
            .on_conflict_do_nothing()
            .returning(LlmBudgetAlertORM.pool)
        )
        claimed = self._session.execute(stmt).first() is not None
        self._session.flush()
        return claimed

    def delete_expired(self, *, question_before: date, usage_before: date) -> None:
        self._session.execute(
            sa.delete(LlmQuestionCountORM).where(LlmQuestionCountORM.day < question_before)
        )
        self._session.execute(
            sa.delete(LlmTokenUsageORM).where(LlmTokenUsageORM.day < usage_before)
        )
        cutoff = datetime(
            usage_before.year, usage_before.month, usage_before.day, tzinfo=timezone.utc,
        )
        self._session.execute(
            sa.delete(LlmBudgetAlertORM).where(LlmBudgetAlertORM.sent_at < cutoff)
        )
        self._session.flush()
```

- [ ] **Step 7: Run the tests to verify they pass**

Run: `cd core && ../.venv/bin/pytest tests/graph/test_llm_usage_repository.py tests/test_migrate.py -v`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add core/src/normly_core/graph/domain.py core/src/normly_core/graph/postgres/orm.py \
  core/src/normly_core/graph/postgres/repositories.py core/migrations/versions/0040_llm_usage.py \
  core/tests/graph/test_llm_usage_repository.py
git commit -s -m "feat(core): add counters and repository for LLM cost caps" \
  -m "Refs #40" -m "Assisted-by: Claude Code"
```

---

### Task 4: Budget alerts by mail

**Files:**
- Create: `chat/src/normly_chat/budget_alerts.py`
- Test: `chat/tests/test_budget_alerts.py`

**Interfaces:**
- Consumes: `normly_core.notifications.email.EmailSender` (`send(*, to, subject, body, html=None)`).
- Produces: `BudgetAlert(pool: str, period: str, threshold: int, total_tokens: int, budget_tokens: int, resets_at: datetime)` frozen dataclass; `BudgetAlerter(sender: EmailSender, recipients: tuple[str, ...])` with `send(alert: BudgetAlert) -> None` that never raises.

- [ ] **Step 1: Write the failing tests**

```python
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

import logging
from datetime import datetime, timezone

from normly_core.notifications.email import RecordingEmailSender

from normly_chat.budget_alerts import BudgetAlert, BudgetAlerter

_ALERT = BudgetAlert(
    pool="anonymous", period="2026-10", threshold=80, total_tokens=8_100_000,
    budget_tokens=10_000_000, resets_at=datetime(2026, 11, 1, tzinfo=timezone.utc),
)


def test_every_recipient_gets_a_mail_naming_pool_threshold_and_numbers():
    sender = RecordingEmailSender()
    BudgetAlerter(sender, ("lead-a@example.org", "lead-b@example.org")).send(_ALERT)

    assert [mail["to"] for mail in sender.sent] == ["lead-a@example.org", "lead-b@example.org"]
    mail = sender.sent[0]
    assert "anonymous" in mail["subject"] and "80 %" in mail["subject"]
    assert "8100000" in mail["body"]
    assert "10000000" in mail["body"]
    assert "2026-11-01T00:00:00+00:00" in mail["body"]


def test_without_recipients_the_alert_is_only_logged(caplog):
    sender = RecordingEmailSender()
    with caplog.at_level(logging.WARNING):
        BudgetAlerter(sender, ()).send(_ALERT)

    assert sender.sent == []
    assert "anonymous" in caplog.text


class _FailingSender:
    def __init__(self):
        self.attempts = 0

    def send(self, *, to, subject, body, html=None):
        self.attempts += 1
        raise OSError("relay down")


def test_a_failing_relay_is_logged_and_the_next_recipient_is_still_tried(caplog):
    sender = _FailingSender()
    with caplog.at_level(logging.ERROR):
        BudgetAlerter(sender, ("lead-a@example.org", "lead-b@example.org")).send(_ALERT)

    assert sender.attempts == 2
    assert "relay down" in caplog.text
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd chat && ../.venv/bin/pytest tests/test_budget_alerts.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Implement**

```python
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

"""Budget alert mail to the Lead Maintainers (issue #40)."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime

from normly_core.notifications.email import EmailSender

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BudgetAlert:
    pool: str
    # "YYYY-MM" for a monthly threshold, "YYYY-MM-DD" for daily exhaustion.
    period: str
    threshold: int
    total_tokens: int
    budget_tokens: int
    resets_at: datetime


class BudgetAlerter:
    """
    Recipients come from NORMLY_LLM_BUDGET_ALERT_RECIPIENTS on the VM, never
    from the repository. A failing relay must never fail the user's request,
    so every error is logged and swallowed -- the same fail-soft rule as
    notify-watchers.
    """

    def __init__(self, sender: EmailSender, recipients: tuple[str, ...]):
        self._sender = sender
        self._recipients = recipients

    def send(self, alert: BudgetAlert) -> None:
        subject = f"[normly] LLM budget: {alert.pool} pool at {alert.threshold} % ({alert.period})"
        body = (
            f"The {alert.pool} cost pool reached {alert.threshold} % of its budget "
            f"for {alert.period}.\n\n"
            f"Used: {alert.total_tokens} tokens\n"
            f"Budget: {alert.budget_tokens} tokens\n"
            f"Resets at: {alert.resets_at.isoformat()}\n\n"
            "At 100 % the chat answers AI questions of this pool with a limit notice "
            "until the reset. Budgets are set with the NORMLY_LLM_BUDGET_* variables."
        )
        if not self._recipients:
            logger.warning("budget alert without recipients: %s", subject)
            return
        for recipient in self._recipients:
            try:
                self._sender.send(to=recipient, subject=subject, body=body)
            except Exception:
                logger.exception("budget alert to a recipient failed: %s", subject)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd chat && ../.venv/bin/pytest tests/test_budget_alerts.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add chat/src/normly_chat/budget_alerts.py chat/tests/test_budget_alerts.py
git commit -s -m "feat(chat): send LLM budget alerts by mail" \
  -m "Refs #40" -m "Assisted-by: Claude Code"
```

---

### Task 5: Budget guard and metered client

**Files:**
- Create: `chat/src/normly_chat/budget_guard.py`
- Create: `chat/src/normly_chat/metered_llm_client.py`
- Test: `chat/tests/test_budget_guard.py`, `chat/tests/test_metered_llm_client.py`

**Interfaces:**
- Consumes: `BudgetSettings`, `PoolBudget` (Task 2); `LlmPoolTotals`, `LlmUsageRepository` (Task 3); `BudgetAlert`, `BudgetAlerter` (Task 4); `LlmResult` (Task 1).
- Produces:
  - `POOL_ANONYMOUS = "anonymous"`, `POOL_REGISTERED = "registered"`
  - `next_day_start(now: datetime) -> datetime`, `next_month_start(now: datetime) -> datetime` (UTC)
  - `BudgetExhausted(Exception)` with attributes `reason: str`, `resets_at: datetime`, `anonymous: bool`
  - `QuotaStatus(used: int, limit: int, resets_at: datetime, pool_exhausted: bool, pool_resets_at: datetime | None)`
  - `BudgetGuard(repositories: Callable[[], ContextManager[LlmUsageRepository]], settings: BudgetSettings, alerter, now: Callable[[], datetime] = <utc now>)` with `admit(*, pool, user_key) -> None` (raises `BudgetExhausted`), `pool_available(pool) -> bool`, `book(*, pool, result: LlmResult) -> None`, `status(*, pool, user_key) -> QuotaStatus`.
  - `LlmOutputTruncated(Exception)`; `MeteredLlmClient(inner: LlmClient, guard: BudgetGuard, pool: str)` with `chat(messages) -> str`.
- The `repositories` factory returns a context manager that yields a repository and commits on a clean exit (Task 6 provides the production one).

- [ ] **Step 1: Write the failing guard tests**

Create `chat/tests/test_budget_guard.py`:

```python
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from contextlib import contextmanager
from datetime import date, datetime, timezone

import pytest

from normly_core.graph.domain import LlmPoolTotals

from normly_chat.budget_guard import (
    POOL_ANONYMOUS, POOL_REGISTERED, BudgetExhausted, BudgetGuard, QuotaStatus,
    next_day_start, next_month_start,
)
from normly_chat.budget_settings import BudgetSettings, PoolBudget
from normly_chat.llm_result import LlmResult

_NOW = datetime(2026, 10, 22, 9, 30, tzinfo=timezone.utc)


class _InMemoryUsageRepository:
    def __init__(self):
        self.tokens: dict[tuple[str, date], int] = {}
        self.questions: dict[tuple[str, date], int] = {}
        self.alerts: set[tuple[str, str, int]] = set()
        self.expired_calls = []

    def add_tokens(self, *, pool, day, input_tokens, output_tokens):
        self.tokens[(pool, day)] = self.tokens.get((pool, day), 0) + input_tokens + output_tokens
        return self.pool_totals(pool=pool, day=day)

    def pool_totals(self, *, pool, day):
        month = [
            total for (p, d), total in self.tokens.items()
            if p == pool and d.replace(day=1) == day.replace(day=1) and d <= day
        ]
        return LlmPoolTotals(day_tokens=self.tokens.get((pool, day), 0), month_tokens=sum(month))

    def record_question(self, *, key, day, limit):
        count = self.questions.get((key, day), 0) + 1
        self.questions[(key, day)] = count
        return count, count <= limit

    def question_count(self, *, key, day):
        return self.questions.get((key, day), 0)

    def claim_alert(self, *, pool, period, threshold, now):
        if (pool, period, threshold) in self.alerts:
            return False
        self.alerts.add((pool, period, threshold))
        return True

    def delete_expired(self, *, question_before, usage_before):
        self.expired_calls.append((question_before, usage_before))


class _RecordingAlerter:
    def __init__(self):
        self.alerts = []

    def send(self, alert):
        self.alerts.append(alert)


def _settings(**pools):
    return BudgetSettings(
        max_output_tokens=100, max_message_chars=2000,
        anonymous_daily_quota=2, registered_daily_quota=3,
        pools={
            POOL_ANONYMOUS: pools.get("anonymous", PoolBudget(daily_tokens=1000, monthly_tokens=10_000)),
            POOL_REGISTERED: pools.get("registered", PoolBudget(daily_tokens=1000, monthly_tokens=10_000)),
        },
        alert_recipients=(),
    )


def _guard(repo, settings=None, alerter=None, now=_NOW):
    @contextmanager
    def repositories():
        yield repo

    return BudgetGuard(
        repositories, settings or _settings(), alerter or _RecordingAlerter(), now=lambda: now,
    )


def test_reset_times_are_the_next_utc_day_and_month():
    assert next_day_start(_NOW) == datetime(2026, 10, 23, tzinfo=timezone.utc)
    assert next_month_start(_NOW) == datetime(2026, 11, 1, tzinfo=timezone.utc)
    assert next_month_start(datetime(2026, 12, 5, tzinfo=timezone.utc)) == datetime(
        2027, 1, 1, tzinfo=timezone.utc,
    )


def test_admit_counts_questions_up_to_the_pool_quota():
    repo = _InMemoryUsageRepository()
    guard = _guard(repo)

    guard.admit(pool=POOL_ANONYMOUS, user_key="anon:1.2.3.4")
    guard.admit(pool=POOL_ANONYMOUS, user_key="anon:1.2.3.4")
    with pytest.raises(BudgetExhausted) as raised:
        guard.admit(pool=POOL_ANONYMOUS, user_key="anon:1.2.3.4")

    assert raised.value.reason == "quota_exhausted"
    assert raised.value.resets_at == datetime(2026, 10, 23, tzinfo=timezone.utc)
    assert raised.value.anonymous is True
    # The registered quota (3) is separate from the anonymous one (2).
    for _ in range(3):
        guard.admit(pool=POOL_REGISTERED, user_key="account:a")


def test_admit_refuses_when_the_daily_pool_budget_is_spent_without_counting_the_question():
    repo = _InMemoryUsageRepository()
    repo.tokens[(POOL_ANONYMOUS, _NOW.date())] = 1000
    guard = _guard(repo)

    with pytest.raises(BudgetExhausted) as raised:
        guard.admit(pool=POOL_ANONYMOUS, user_key="anon:x")

    assert raised.value.reason == "pool_daily_exhausted"
    assert raised.value.resets_at == datetime(2026, 10, 23, tzinfo=timezone.utc)
    assert repo.questions == {}
    # The other pool is untouched by the anonymous pool's exhaustion.
    guard.admit(pool=POOL_REGISTERED, user_key="account:a")


def test_admit_refuses_when_the_monthly_pool_budget_is_spent():
    repo = _InMemoryUsageRepository()
    repo.tokens[(POOL_REGISTERED, date(2026, 10, 1))] = 10_000
    guard = _guard(repo)

    with pytest.raises(BudgetExhausted) as raised:
        guard.admit(pool=POOL_REGISTERED, user_key="account:a")

    assert raised.value.reason == "pool_monthly_exhausted"
    assert raised.value.resets_at == datetime(2026, 11, 1, tzinfo=timezone.utc)
    assert raised.value.anonymous is False


def test_admit_runs_retention_with_two_days_of_questions_and_forty_days_of_usage():
    repo = _InMemoryUsageRepository()
    _guard(repo).admit(pool=POOL_ANONYMOUS, user_key="anon:x")

    assert repo.expired_calls == [(date(2026, 10, 21), date(2026, 9, 12))]


def test_a_new_day_starts_a_fresh_quota():
    repo = _InMemoryUsageRepository()
    _guard(repo).admit(pool=POOL_ANONYMOUS, user_key="anon:x")
    _guard(repo).admit(pool=POOL_ANONYMOUS, user_key="anon:x")

    _guard(repo, now=datetime(2026, 10, 23, 0, 0, tzinfo=timezone.utc)).admit(
        pool=POOL_ANONYMOUS, user_key="anon:x",
    )


def test_book_adds_input_and_output_tokens_to_the_pool():
    repo = _InMemoryUsageRepository()
    _guard(repo).book(
        pool=POOL_ANONYMOUS,
        result=LlmResult(text="a", input_tokens=30, output_tokens=12, truncated=False),
    )

    assert repo.tokens == {(POOL_ANONYMOUS, _NOW.date()): 42}


def test_book_sends_each_crossed_threshold_once():
    repo = _InMemoryUsageRepository()
    alerter = _RecordingAlerter()
    guard = _guard(repo, alerter=alerter)
    repo.tokens[(POOL_ANONYMOUS, date(2026, 10, 1))] = 4_900

    guard.book(pool=POOL_ANONYMOUS, result=LlmResult("a", 100, 0, False))   # 5000 = 50 %
    guard.book(pool=POOL_ANONYMOUS, result=LlmResult("a", 10, 0, False))    # still 50 %
    guard.book(pool=POOL_ANONYMOUS, result=LlmResult("a", 890, 0, False))   # day 1000 = 100 %, month 5900

    assert [(a.period, a.threshold) for a in alerter.alerts] == [
        ("2026-10", 50), ("2026-10-22", 100),
    ]
    daily = alerter.alerts[1]
    assert daily.total_tokens == 1000
    assert daily.budget_tokens == 1000
    assert daily.resets_at == datetime(2026, 10, 23, tzinfo=timezone.utc)


def test_book_sends_all_monthly_thresholds_crossed_in_one_step():
    repo = _InMemoryUsageRepository()
    alerter = _RecordingAlerter()
    settings = _settings(anonymous=PoolBudget(daily_tokens=10_000, monthly_tokens=10_000))
    _guard(repo, settings=settings, alerter=alerter).book(
        pool=POOL_ANONYMOUS, result=LlmResult("a", 10_000, 0, False),
    )

    assert sorted((a.period, a.threshold) for a in alerter.alerts) == [
        ("2026-10", 50), ("2026-10", 80), ("2026-10", 100), ("2026-10-22", 100),
    ]


def test_pool_available_reflects_both_budgets():
    repo = _InMemoryUsageRepository()
    guard = _guard(repo)
    assert guard.pool_available(POOL_REGISTERED) is True

    repo.tokens[(POOL_REGISTERED, _NOW.date())] = 1000
    assert guard.pool_available(POOL_REGISTERED) is False


def test_status_reports_used_limit_and_resets():
    repo = _InMemoryUsageRepository()
    guard = _guard(repo)
    guard.admit(pool=POOL_REGISTERED, user_key="account:a")

    assert guard.status(pool=POOL_REGISTERED, user_key="account:a") == QuotaStatus(
        used=1, limit=3, resets_at=datetime(2026, 10, 23, tzinfo=timezone.utc),
        pool_exhausted=False, pool_resets_at=None,
    )


def test_status_caps_used_at_the_limit_and_reports_an_exhausted_pool():
    repo = _InMemoryUsageRepository()
    repo.questions[("account:a", _NOW.date())] = 7
    repo.tokens[(POOL_REGISTERED, date(2026, 10, 1))] = 10_000

    status = _guard(repo).status(pool=POOL_REGISTERED, user_key="account:a")

    assert status.used == 3
    assert status.pool_exhausted is True
    assert status.pool_resets_at == datetime(2026, 11, 1, tzinfo=timezone.utc)
```

- [ ] **Step 2: Write the failing metered-client tests**

Create `chat/tests/test_metered_llm_client.py`:

```python
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

import pytest

from normly_chat.llm_result import LlmResult
from normly_chat.metered_llm_client import LlmOutputTruncated, MeteredLlmClient


class _Provider:
    def __init__(self, result):
        self._result = result

    def complete(self, messages):
        return self._result


class _RecordingGuard:
    def __init__(self):
        self.booked = []

    def book(self, *, pool, result):
        self.booked.append((pool, result))


def test_chat_returns_the_text_and_books_the_usage_to_the_pool():
    result = LlmResult(text="Antwort", input_tokens=10, output_tokens=5, truncated=False)
    guard = _RecordingGuard()

    text = MeteredLlmClient(_Provider(result), guard, "anonymous").chat([{"role": "user", "content": "x"}])

    assert text == "Antwort"
    assert guard.booked == [("anonymous", result)]


def test_a_truncated_answer_is_booked_and_then_raised():
    result = LlmResult(text="Halb", input_tokens=10, output_tokens=100, truncated=True)
    guard = _RecordingGuard()

    with pytest.raises(LlmOutputTruncated):
        MeteredLlmClient(_Provider(result), guard, "registered").chat([])

    assert guard.booked == [("registered", result)]
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `cd chat && ../.venv/bin/pytest tests/test_budget_guard.py tests/test_metered_llm_client.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 4: Implement the guard**

Create `chat/src/normly_chat/budget_guard.py`:

```python
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

"""
Admission and booking for the LLM cost caps (issue #40, ADR-029).

STACKIT bounds only the speed of spending, so normly bounds the total:
two cost pools (anonymous, registered) with a daily and a monthly token
budget, and a daily quota of AI answers per caller. Only synthesis
questions reach the guard; graph answers never cost anything (ADR-008).

Every check and every booking runs in its own short transaction that
commits immediately: a count must survive the request even when the
request fails afterwards, the same reasoning as api/'s rate limiter.
"""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from normly_core.graph.domain import LlmPoolTotals, LlmUsageRepository

from normly_chat.budget_alerts import BudgetAlert
from normly_chat.budget_settings import BudgetSettings
from normly_chat.llm_result import LlmResult

POOL_ANONYMOUS = "anonymous"
POOL_REGISTERED = "registered"

_MONTHLY_THRESHOLDS = (50, 80, 100)
# Question counters embed a caller address: today and yesterday only.
_QUESTION_RETENTION = timedelta(days=1)
_USAGE_RETENTION = timedelta(days=40)


def next_day_start(now: datetime) -> datetime:
    today = now.astimezone(timezone.utc).date()
    tomorrow = today + timedelta(days=1)
    return datetime(tomorrow.year, tomorrow.month, tomorrow.day, tzinfo=timezone.utc)


def next_month_start(now: datetime) -> datetime:
    today = now.astimezone(timezone.utc).date()
    if today.month == 12:
        return datetime(today.year + 1, 1, 1, tzinfo=timezone.utc)
    return datetime(today.year, today.month + 1, 1, tzinfo=timezone.utc)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class BudgetExhausted(Exception):
    def __init__(self, reason: str, resets_at: datetime, anonymous: bool):
        super().__init__(reason)
        self.reason = reason
        self.resets_at = resets_at
        self.anonymous = anonymous


@dataclass(frozen=True)
class QuotaStatus:
    used: int
    limit: int
    resets_at: datetime
    pool_exhausted: bool
    pool_resets_at: datetime | None


class BudgetGuard:
    def __init__(
        self,
        repositories: Callable[[], AbstractContextManager[LlmUsageRepository]],
        settings: BudgetSettings,
        alerter,
        now: Callable[[], datetime] = _utc_now,
    ):
        self._repositories = repositories
        self._settings = settings
        self._alerter = alerter
        self._now = now

    def _quota(self, pool: str) -> int:
        if pool == POOL_ANONYMOUS:
            return self._settings.anonymous_daily_quota
        return self._settings.registered_daily_quota

    def _pool_exhaustion(self, pool: str, totals: LlmPoolTotals, now: datetime):
        """(reason, resets_at) when the pool is spent, else None."""
        budget = self._settings.pools[pool]
        if totals.day_tokens >= budget.daily_tokens:
            return "pool_daily_exhausted", next_day_start(now)
        if totals.month_tokens >= budget.monthly_tokens:
            return "pool_monthly_exhausted", next_month_start(now)
        return None

    def admit(self, *, pool: str, user_key: str) -> None:
        now = self._now()
        today = now.date()
        with self._repositories() as repository:
            exhaustion = self._pool_exhaustion(
                pool, repository.pool_totals(pool=pool, day=today), now,
            )
            if exhaustion is None:
                _, allowed = repository.record_question(
                    key=user_key, day=today, limit=self._quota(pool),
                )
                repository.delete_expired(
                    question_before=today - _QUESTION_RETENTION,
                    usage_before=today - _USAGE_RETENTION,
                )
        anonymous = pool == POOL_ANONYMOUS
        if exhaustion is not None:
            reason, resets_at = exhaustion
            raise BudgetExhausted(reason, resets_at, anonymous)
        if not allowed:
            raise BudgetExhausted("quota_exhausted", next_day_start(now), anonymous)

    def pool_available(self, pool: str) -> bool:
        now = self._now()
        with self._repositories() as repository:
            totals = repository.pool_totals(pool=pool, day=now.date())
        return self._pool_exhaustion(pool, totals, now) is None

    def book(self, *, pool: str, result: LlmResult) -> None:
        now = self._now()
        budget = self._settings.pools[pool]
        candidates = []
        with self._repositories() as repository:
            totals = repository.add_tokens(
                pool=pool, day=now.date(),
                input_tokens=result.input_tokens, output_tokens=result.output_tokens,
            )
            for threshold in _MONTHLY_THRESHOLDS:
                if totals.month_tokens * 100 >= budget.monthly_tokens * threshold:
                    candidates.append(BudgetAlert(
                        pool=pool, period=now.strftime("%Y-%m"), threshold=threshold,
                        total_tokens=totals.month_tokens, budget_tokens=budget.monthly_tokens,
                        resets_at=next_month_start(now),
                    ))
            if totals.day_tokens >= budget.daily_tokens:
                candidates.append(BudgetAlert(
                    pool=pool, period=now.strftime("%Y-%m-%d"), threshold=100,
                    total_tokens=totals.day_tokens, budget_tokens=budget.daily_tokens,
                    resets_at=next_day_start(now),
                ))
            claimed = [
                alert for alert in candidates
                if repository.claim_alert(
                    pool=pool, period=alert.period, threshold=alert.threshold, now=now,
                )
            ]
        # Sent after the claim is committed, so a slow relay holds no lock.
        for alert in claimed:
            self._alerter.send(alert)

    def status(self, *, pool: str, user_key: str) -> QuotaStatus:
        now = self._now()
        with self._repositories() as repository:
            used = repository.question_count(key=user_key, day=now.date())
            totals = repository.pool_totals(pool=pool, day=now.date())
        limit = self._quota(pool)
        exhaustion = self._pool_exhaustion(pool, totals, now)
        return QuotaStatus(
            # Rejected questions are counted too; the view shows at most the limit.
            used=min(used, limit), limit=limit, resets_at=next_day_start(now),
            pool_exhausted=exhaustion is not None,
            pool_resets_at=exhaustion[1] if exhaustion is not None else None,
        )
```

- [ ] **Step 5: Implement the metered client**

Create `chat/src/normly_chat/metered_llm_client.py`:

```python
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

"""
The only LLM client synthesis and title code ever receive: every call is
booked to the request's cost pool before its text is used.
"""

from __future__ import annotations

from normly_chat.llm_client import LlmClient


class LlmOutputTruncated(Exception):
    """The provider stopped at the output cap; the text is incomplete."""


class MeteredLlmClient:
    def __init__(self, inner: LlmClient, guard, pool: str):
        self._inner = inner
        self._guard = guard
        self._pool = pool

    def chat(self, messages: list[dict]) -> str:
        result = self._inner.complete(messages)
        # Booked first: a cut-off answer cost its tokens all the same.
        self._guard.book(pool=self._pool, result=result)
        if result.truncated:
            raise LlmOutputTruncated()
        return result.text
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `cd chat && ../.venv/bin/pytest tests/test_budget_guard.py tests/test_metered_llm_client.py -v`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add chat/src/normly_chat/budget_guard.py chat/src/normly_chat/metered_llm_client.py \
  chat/tests/test_budget_guard.py chat/tests/test_metered_llm_client.py
git commit -s -m "feat(chat): admit and book LLM calls against pool budgets and quotas" \
  -m "Refs #40" -m "Assisted-by: Claude Code"
```

---

### Task 6: Enforce the caps in the chat service

**Files:**
- Create: `chat/src/normly_chat/caller_key.py`, `chat/src/normly_chat/routers/usage.py`
- Modify: `chat/src/normly_chat/synthesis.py`, `chat/src/normly_chat/titles.py`, `chat/src/normly_chat/dependencies.py`, `chat/src/normly_chat/errors.py`, `chat/src/normly_chat/main.py`, `chat/src/normly_chat/schemas.py`, `chat/src/normly_chat/routers/chat.py`, `chat/src/normly_chat/routers/sessions.py`, `chat/src/normly_chat/llm_client.py`, `chat/src/normly_chat/ollama_client.py`
- Test: `chat/tests/test_caller_key.py`, `chat/tests/test_synthesis.py`, `chat/tests/test_titles.py`, `chat/tests/test_chat_router.py`, `chat/tests/test_sessions_router.py`, `chat/tests/test_usage_router.py`

**Interfaces:**
- Consumes: everything from Tasks 1–5.
- Produces:
  - `anonymous_caller_key(request: Request) -> str` → `"anon:<anon id>:<origin>"` or `"anon:<origin>"`; registered key is `f"account:{account_id}"` (built in the routers).
  - `usage_repository_scope(engine) -> Iterator[PostgresLlmUsageRepository]` (contextmanager in `dependencies.py`), `get_budget_guard(request) -> BudgetGuard`, `get_budget_settings(request) -> BudgetSettings`.
  - `GET /v1/chat/usage` → `ChatUsageResponse(used: int, limit: int, resets_at: datetime, pool_exhausted: bool, pool_resets_at: datetime | None)`; 401 without a valid account.
  - `POST /v1/chat`: 400 `{"detail": "message_too_long"}`; 429 `{"detail": {"reason", "resets_at", "anonymous"}}` plus `Retry-After`.
  - Providers lose the transitional `chat()`; only `complete()` remains.

- [ ] **Step 1: Write the failing caller-key test**

Create `chat/tests/test_caller_key.py`:

```python
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from starlette.requests import Request

from normly_chat.caller_key import anonymous_caller_key


def _request(headers: dict[str, str], client=("10.0.0.9", 1234)) -> Request:
    return Request({
        "type": "http", "method": "POST", "path": "/v1/chat",
        "headers": [(k.lower().encode(), v.encode()) for k, v in headers.items()],
        "client": client,
    })


def test_the_key_combines_anon_id_and_the_rightmost_forwarded_address():
    request = _request({"X-Normly-Anon-Id": "abc", "X-Forwarded-For": "6.6.6.6, 1.2.3.4"})
    assert anonymous_caller_key(request) == "anon:abc:1.2.3.4"


def test_without_headers_the_connection_address_is_used():
    assert anonymous_caller_key(_request({})) == "anon:10.0.0.9"
```

- [ ] **Step 2: Write the failing synthesis and title tests**

Append to `chat/tests/test_synthesis.py`:

```python
from normly_chat.metered_llm_client import LlmOutputTruncated


def test_a_truncated_answer_falls_back_without_a_faithfulness_call():
    segment = _FakeSegment(uuid.uuid4(), uuid.uuid4(), "Schutzbrillen sind beim Schweißen Pflicht.")

    class _TruncatingLlm:
        def __init__(self):
            self.calls = 0

        def chat(self, messages):
            self.calls += 1
            raise LlmOutputTruncated()

    llm = _TruncatingLlm()
    result = build_synthesis_answer(
        "Welche Schutzausrüstung beim Schweißen?", "DE", "de", _FakeEmbeddingModel(),
        _FakeSegmentRepo([segment]), llm,
    )

    assert result.is_fallback is True
    assert llm.calls == 1


def test_a_truncated_faithfulness_verdict_counts_as_not_faithful():
    segment = _FakeSegment(uuid.uuid4(), uuid.uuid4(), "Schutzbrillen sind beim Schweißen Pflicht.")

    class _SecondCallTruncates:
        def __init__(self):
            self.calls = 0

        def chat(self, messages):
            self.calls += 1
            if self.calls == 1:
                return "Beim Schweißen muss eine Schutzbrille getragen werden."
            raise LlmOutputTruncated()

    result = build_synthesis_answer(
        "Welche Schutzausrüstung beim Schweißen?", "DE", "de", _FakeEmbeddingModel(),
        _FakeSegmentRepo([segment]), _SecondCallTruncates(),
    )

    assert result.is_fallback is True
```

Append to `chat/tests/test_titles.py`:

```python
from normly_chat.metered_llm_client import LlmOutputTruncated


def test_a_truncated_title_falls_back():
    assert generate_title(_Llm(error=LlmOutputTruncated()), "Frage", "de") is None
```

- [ ] **Step 3: Write the failing router tests**

Append to `chat/tests/test_chat_router.py`:

```python
from datetime import datetime, timezone

from normly_chat.budget_guard import BudgetExhausted
from normly_chat.dependencies import get_budget_guard, get_embedding_model

_SYNTHESIS_QUESTION = "Welche Schutzausrüstung ist beim Schweißen vorgeschrieben?"


class _RecordingGuard:
    """Admits everything and records who was admitted."""

    def __init__(self):
        self.admitted = []

    def admit(self, *, pool, user_key):
        self.admitted.append((pool, user_key))

    def book(self, *, pool, result):
        pass


class _RefusingGuard:
    def __init__(self, reason, anonymous=True):
        self._error = BudgetExhausted(
            reason, datetime(2099, 1, 1, tzinfo=timezone.utc), anonymous,
        )

    def admit(self, *, pool, user_key):
        raise self._error


class _NoMatchEmbedding:
    def embed_query(self, text):
        # A zero vector matches no segment in the empty test database, so
        # synthesis falls back without a model call.
        return [0.0] * 1024


def test_an_oversized_message_is_rejected_before_anything_else(client):
    response = client.post("/v1/chat", json={
        "message": "x" * 2001, "jurisdiction": "DE", "language": "de",
    })

    assert response.status_code == 400
    assert response.json() == {"detail": "message_too_long"}


@pytest.mark.parametrize("reason", ["quota_exhausted", "pool_daily_exhausted", "pool_monthly_exhausted"])
def test_an_exhausted_budget_answers_429_with_reason_and_reset(client, reason):
    client.app.dependency_overrides[get_accounts_client] = lambda: _FixedAccountsClient(None)
    client.app.dependency_overrides[get_budget_guard] = lambda: _RefusingGuard(reason)

    response = client.post("/v1/chat", json={
        "message": _SYNTHESIS_QUESTION, "jurisdiction": "DE", "language": "de",
    })

    assert response.status_code == 429
    assert response.json() == {"detail": {
        "reason": reason, "resets_at": "2099-01-01T00:00:00Z", "anonymous": True,
    }}
    assert int(response.headers["retry-after"]) > 0


def test_a_structural_question_never_reaches_the_guard(client):
    client.app.dependency_overrides[get_api_client] = lambda: _NoDocumentApiClient()
    client.app.dependency_overrides[get_accounts_client] = lambda: _FixedAccountsClient(None)
    client.app.dependency_overrides[get_budget_guard] = lambda: _RefusingGuard("pool_daily_exhausted")

    response = client.post("/v1/chat", json={
        "message": "Ist DIN EN ISO 9001 noch gültig?", "jurisdiction": "DE", "language": "de",
    })

    assert response.status_code == 200


def test_an_anonymous_synthesis_question_is_admitted_to_the_anonymous_pool(client):
    guard = _RecordingGuard()
    client.app.dependency_overrides[get_accounts_client] = lambda: _FixedAccountsClient(None)
    client.app.dependency_overrides[get_budget_guard] = lambda: guard
    client.app.dependency_overrides[get_embedding_model] = lambda: _NoMatchEmbedding()

    response = client.post(
        "/v1/chat",
        json={"message": _SYNTHESIS_QUESTION, "jurisdiction": "DE", "language": "de"},
        headers={"X-Normly-Anon-Id": "abc", "X-Forwarded-For": "1.2.3.4"},
    )

    assert response.status_code == 200
    assert guard.admitted == [("anonymous", "anon:abc:1.2.3.4")]
```

`_FixedAccountsClient` already exists in this file; if it is defined below the new tests, move the new tests below it. Also add a registered-pool test using `_FixedAccountsClient(identity)` with the identity construction the file already uses in `test_request_with_a_valid_account_stores_session_messages_and_returns_a_token`, asserting `guard.admitted == [("registered", f"account:{identity.account_id}")]`.

Create `chat/tests/test_usage_router.py`:

```python
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

import uuid
from datetime import datetime, timezone

from normly_chat.accounts_client import ChatAccountIdentity
from normly_chat.budget_guard import QuotaStatus
from normly_chat.dependencies import get_accounts_client, get_budget_guard


class _FixedAccountsClient:
    def __init__(self, identity):
        self._identity = identity

    def validate_session(self, session_token):
        return self._identity


class _StatusGuard:
    def __init__(self):
        self.asked = []

    def status(self, *, pool, user_key):
        self.asked.append((pool, user_key))
        return QuotaStatus(
            used=7, limit=30, resets_at=datetime(2026, 10, 23, tzinfo=timezone.utc),
            pool_exhausted=True, pool_resets_at=datetime(2026, 11, 1, tzinfo=timezone.utc),
        )


def test_usage_requires_an_account(client):
    client.app.dependency_overrides[get_accounts_client] = lambda: _FixedAccountsClient(None)

    assert client.get("/v1/chat/usage").status_code == 401
    assert client.get("/v1/chat/usage", headers={"Authorization": "Bearer t"}).status_code == 401


def test_usage_returns_the_registered_quota_status(client):
    identity = ChatAccountIdentity(account_id=uuid.uuid4(), email="user@example.org")
    guard = _StatusGuard()
    client.app.dependency_overrides[get_accounts_client] = lambda: _FixedAccountsClient(identity)
    client.app.dependency_overrides[get_budget_guard] = lambda: guard

    response = client.get("/v1/chat/usage", headers={"Authorization": "Bearer t"})

    assert response.status_code == 200
    assert response.json() == {
        "used": 7, "limit": 30, "resets_at": "2026-10-23T00:00:00Z",
        "pool_exhausted": True, "pool_resets_at": "2026-11-01T00:00:00Z",
    }
    assert guard.asked == [("registered", f"account:{identity.account_id}")]
```

In `chat/tests/test_sessions_router.py`, change `_TitleLlm` to the provider interface, because the title route now wraps it in `MeteredLlmClient`:

```python
from normly_chat.llm_result import LlmResult


class _TitleLlm:
    def __init__(self, response=None, error=None):
        self._response = response
        self._error = error
        self.calls = 0

    def complete(self, messages):
        self.calls += 1
        if self._error:
            raise self._error
        return LlmResult(text=self._response, input_tokens=5, output_tokens=3, truncated=False)
```

Add a test that an exhausted registered pool skips the model for titles. Follow the file's existing title tests for setup (`_owned_session`, a stored first question, `_app_for(..., llm_client=llm)`), additionally set `app.dependency_overrides[get_budget_guard] = lambda: _ExhaustedGuard()` with:

```python
class _ExhaustedGuard:
    def pool_available(self, pool):
        return False
```

and assert the response is 200 with the fallback title and `llm.calls == 0`.

- [ ] **Step 4: Run the tests to verify they fail**

Run: `cd chat && ../.venv/bin/pytest tests/test_caller_key.py tests/test_synthesis.py tests/test_titles.py tests/test_chat_router.py tests/test_usage_router.py tests/test_sessions_router.py -v`
Expected: FAIL — missing modules (`normly_chat.caller_key`, `get_budget_guard`) and the new behavior.

- [ ] **Step 5: Implement caller key, synthesis and titles**

Create `chat/src/normly_chat/caller_key.py`:

```python
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

"""
The quota key of an anonymous caller. Same derivation as api/'s rate
limiter (api/src/normly_api/rate_limit.py), duplicated because chat/ does
not depend on api/: X-Normly-Anon-Id from the frontend BFF plus the
rightmost X-Forwarded-For entry, the one our own reverse proxy appended.
"""

from __future__ import annotations

from starlette.requests import Request


def _client_origin_address(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[-1].strip()
    return request.client.host if request.client else "unknown"


def anonymous_caller_key(request: Request) -> str:
    anon_id = request.headers.get("x-normly-anon-id")
    origin = _client_origin_address(request)
    return f"anon:{anon_id}:{origin}" if anon_id else f"anon:{origin}"
```

In `chat/src/normly_chat/synthesis.py`, import `from normly_chat.metered_llm_client import LlmOutputTruncated` and:

```python
def _is_faithful(answer_text: str, context: str, llm_client) -> bool:
    try:
        check_response = llm_client.chat([
            {
                "role": "system",
                "content": f"{_FAITHFULNESS_PROMPT['de']}\n\nKontext:\n{context}",
            },
            {"role": "user", "content": answer_text},
        ])
    except LlmOutputTruncated:
        # A verdict cut off at the cap is no verdict: fail closed.
        return False
    first_word = check_response.strip().lower().split()[0] if check_response.strip() else ""
    return first_word.startswith(_AFFIRMATIVE_ANSWERS["de"])
```

and in `build_synthesis_answer` replace `raw_answer = llm_client.chat(messages)` with:

```python
    try:
        raw_answer = llm_client.chat(messages)
    except LlmOutputTruncated:
        # A cut-off answer is never shown as if it were complete.
        return _fallback(language, ollama_calls=1)
```

In `chat/src/normly_chat/titles.py`, import `LlmOutputTruncated` and extend the caught tuple: `except (httpx.HTTPError, KeyError, IndexError, ValueError, LlmOutputTruncated):`.

- [ ] **Step 6: Implement dependencies, errors, schemas**

Add to `chat/src/normly_chat/dependencies.py`:

```python
from contextlib import contextmanager

from normly_core.graph.postgres.repositories import PostgresLlmUsageRepository

from normly_chat.budget_guard import BudgetGuard
from normly_chat.budget_settings import BudgetSettings


@contextmanager
def usage_repository_scope(engine) -> Iterator[PostgresLlmUsageRepository]:
    # Its own session, committed at once, never the request's: see BudgetGuard.
    with Session(engine) as session:
        yield PostgresLlmUsageRepository(session)
        session.commit()


def get_budget_guard(request: Request) -> BudgetGuard:
    return request.app.state.budget_guard


def get_budget_settings(request: Request) -> BudgetSettings:
    return request.app.state.budget_settings
```

In `chat/src/normly_chat/errors.py`, inside `register_exception_handlers`, before the infrastructure loop:

```python
    @app.exception_handler(BudgetExhausted)
    async def _budget_exhausted_as_429(request: Request, exc: BudgetExhausted) -> JSONResponse:
        seconds = math.ceil((exc.resets_at - datetime.now(timezone.utc)).total_seconds())
        return JSONResponse(
            status_code=429,
            content={"detail": {
                "reason": exc.reason,
                "resets_at": exc.resets_at.isoformat().replace("+00:00", "Z"),
                "anonymous": exc.anonymous,
            }},
            headers={"Retry-After": str(max(1, seconds))},
        )
```

with imports `import math`, `from datetime import datetime, timezone`, `from normly_chat.budget_guard import BudgetExhausted`. Add a 429 entry to the OpenAPI responses of `POST /v1/chat` (Step 7) using a new schema.

Add to `chat/src/normly_chat/schemas.py`:

```python
class BudgetExhaustedDetail(BaseModel):
    reason: Literal["quota_exhausted", "pool_daily_exhausted", "pool_monthly_exhausted"]
    resets_at: datetime
    anonymous: bool


class BudgetExhaustedResponse(BaseModel):
    detail: BudgetExhaustedDetail


class ChatUsageResponse(BaseModel):
    used: int
    limit: int
    resets_at: datetime
    pool_exhausted: bool
    pool_resets_at: datetime | None
```

(`datetime` and `Literal` imports as needed.) FastAPI serializes UTC datetimes as `...Z`; if the test shows `+00:00`, add a `field_serializer` that formats with `isoformat().replace("+00:00", "Z")`.

- [ ] **Step 7: Implement the routers**

In `chat/src/normly_chat/routers/chat.py`:
- Add parameters `request: Request`, `guard: BudgetGuard = Depends(get_budget_guard)`, `settings: BudgetSettings = Depends(get_budget_settings)`.
- Declare `responses={429: {"model": BudgetExhaustedResponse, "description": "A cost cap is exhausted."}}` on the route decorator.
- Right after the existing required-field check:

```python
    if len(payload.message) > settings.max_message_chars:
        raise HTTPException(status_code=400, detail="message_too_long")
```

- Replace the synthesis branch:

```python
    if question_type == QuestionType.SYNTHESIS:
        # Only synthesis costs tokens; graph answers bypass the guard (ADR-008).
        if identity is not None:
            pool, user_key = POOL_REGISTERED, f"account:{identity.account_id}"
        else:
            pool, user_key = POOL_ANONYMOUS, anonymous_caller_key(request)
        guard.admit(pool=pool, user_key=user_key)
        result = build_synthesis_answer(
            payload.message, payload.jurisdiction, payload.language, embedding_model,
            PostgresSegmentRepository(session), MeteredLlmClient(llm_client, guard, pool),
        )
```

In `chat/src/normly_chat/routers/sessions.py`, `create_session_title` gains `guard: BudgetGuard = Depends(get_budget_guard)` and, after the 404 check for a missing first question:

```python
    # Titles cost tokens of the registered pool but no quota. A spent pool
    # gets the fallback title without a model call, like any title failure.
    if not guard.pool_available(POOL_REGISTERED):
        return ChatSessionTitleResponse(title=fallback_title(first_question))
    title = generate_title(
        MeteredLlmClient(llm_client, guard, POOL_REGISTERED), first_question, chat_session.language,
    )
```

Create `chat/src/normly_chat/routers/usage.py`:

```python
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException

from normly_chat.accounts_client import AccountsClient
from normly_chat.budget_guard import POOL_REGISTERED, BudgetGuard
from normly_chat.dependencies import get_accounts_client, get_budget_guard
from normly_chat.schemas import ChatUsageResponse

usage_router = APIRouter(prefix="/v1/chat", tags=["chat"])

_BEARER_PREFIX = "Bearer "


@usage_router.get("/usage", response_model=ChatUsageResponse)
def get_usage(
    authorization: str | None = Header(default=None),
    accounts_client: AccountsClient = Depends(get_accounts_client),
    guard: BudgetGuard = Depends(get_budget_guard),
) -> ChatUsageResponse:
    """The signed-in user's AI answers today, for the profile's usage section."""
    identity = None
    if authorization is not None and (
        authorization[:len(_BEARER_PREFIX)].lower() == _BEARER_PREFIX.lower()
    ):
        identity = accounts_client.validate_session(authorization[len(_BEARER_PREFIX):])
    if identity is None:
        raise HTTPException(status_code=401, detail="not authenticated")
    status = guard.status(pool=POOL_REGISTERED, user_key=f"account:{identity.account_id}")
    return ChatUsageResponse(
        used=status.used, limit=status.limit, resets_at=status.resets_at,
        pool_exhausted=status.pool_exhausted, pool_resets_at=status.pool_resets_at,
    )
```

- [ ] **Step 8: Wire the app and drop the transitional `chat()`**

In `chat/src/normly_chat/main.py` lifespan, replace the LLM client line:

```python
    settings = BudgetSettings.from_env()
    app.state.budget_settings = settings
    app.state.llm_client = build_llm_client_from_env(max_output_tokens=settings.max_output_tokens)
    app.state.budget_guard = BudgetGuard(
        lambda: usage_repository_scope(engine), settings,
        BudgetAlerter(_build_email_sender(), settings.alert_recipients),
    )
```

with a module-level helper mirroring `core/src/normly_core/pipeline/cli.py`:

```python
def _build_email_sender() -> EmailSender:
    smtp_host = os.environ.get("NORMLY_SMTP_HOST")
    if not smtp_host:
        # BudgetAlerter logs the failure; alerts are never silently "sent".
        return NullEmailSender()
    return SmtpEmailSender(
        host=smtp_host,
        port=int(os.environ.get("NORMLY_SMTP_PORT", "587")),
        from_address=os.environ.get("NORMLY_SMTP_FROM", "no-reply@normly.example"),
        username=os.environ.get("NORMLY_SMTP_USERNAME"),
        password=os.environ.get("NORMLY_SMTP_PASSWORD"),
    )
```

and `app.include_router(usage_router, responses=COMMON_ERROR_RESPONSES)` in `create_app`. Remove the transitional `chat()` methods from `OpenAiCompatibleClient` and `OllamaClient`.

- [ ] **Step 9: Run the whole chat suite**

Run: `cd chat && ../.venv/bin/pytest --ignore=tests/test_structural_end_to_end.py -v`
Expected: PASS. Any remaining fake with only a `chat()` method that is passed as `llm_client` into a router now fails with `AttributeError: ... has no attribute 'complete'` — convert it like `_TitleLlm` above.

- [ ] **Step 10: Commit**

```bash
git add chat/
git commit -s -m "feat(chat): enforce LLM cost caps and expose the usage endpoint" \
  -m "Refs #40" -m "Assisted-by: Claude Code"
```

---

### Task 7: Measurement module

**Files:**
- Create: `chat/src/normly_chat/measure_usage.py`
- Create: `chat/measurement/questions_de.txt`
- Test: `chat/tests/test_measure_usage.py`

**Interfaces:**
- Consumes: `build_llm_client_from_env`, `build_synthesis_answer`, `LlmResult`.
- Produces: `RecordingLlmClient(inner)` with `chat(messages) -> str` and `results: list[LlmResult]`; `summarize(rows: list[list[LlmResult]]) -> dict[str, int]` with keys `max_output_tokens`, `max_answer_total`, `mean_answer_total`, `truncated`; CLI `python -m normly_chat.measure_usage <questions file> [--jurisdiction DE] [--language de] [--max-output-tokens 4096]`.

- [ ] **Step 1: Write the failing test**

```python
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from normly_chat.llm_result import LlmResult
from normly_chat.measure_usage import RecordingLlmClient, summarize


class _Provider:
    def complete(self, messages):
        return LlmResult(text="ja", input_tokens=100, output_tokens=40, truncated=False)


def test_the_recording_client_keeps_every_result():
    client = RecordingLlmClient(_Provider())
    assert client.chat([]) == "ja"
    assert client.results == [LlmResult("ja", 100, 40, False)]


def test_summarize_reports_maxima_and_the_mean_per_answer():
    rows = [
        [LlmResult("a", 1000, 300, False), LlmResult("ja", 1200, 2, False)],
        [LlmResult("a", 800, 100, True)],
    ]
    assert summarize(rows) == {
        "max_output_tokens": 300, "max_answer_total": 2502,
        "mean_answer_total": 1701, "truncated": 1,
    }
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd chat && ../.venv/bin/pytest tests/test_measure_usage.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Implement**

```python
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

"""
Measures the real model's token usage per synthesis answer, to derive the
cost-cap defaults (issue #40). Runs wherever the chat service's environment
is set -- locally with a STACKIT key or in the chat container:

    python -m normly_chat.measure_usage chat/measurement/questions_de.txt

Uses a generous output cap so the measurement itself is not cut off. Books
nothing: it never goes through the budget guard.
"""

from __future__ import annotations

import argparse
import os
import statistics

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from normly_core.graph.postgres.repositories import PostgresSegmentRepository
from normly_core.pipeline.embeddings import EmbeddingModel

from normly_chat.llm_client import LlmClient, build_llm_client_from_env
from normly_chat.llm_result import LlmResult
from normly_chat.synthesis import build_synthesis_answer


class RecordingLlmClient:
    def __init__(self, inner: LlmClient):
        self._inner = inner
        self.results: list[LlmResult] = []

    def chat(self, messages: list[dict]) -> str:
        result = self._inner.complete(messages)
        self.results.append(result)
        return result.text


def summarize(rows: list[list[LlmResult]]) -> dict[str, int]:
    answers = [sum(r.input_tokens + r.output_tokens for r in row) for row in rows if row]
    calls = [result for row in rows for result in row]
    return {
        "max_output_tokens": max((r.output_tokens for r in calls), default=0),
        "max_answer_total": max(answers, default=0),
        "mean_answer_total": round(statistics.mean(answers)) if answers else 0,
        "truncated": sum(1 for r in calls if r.truncated),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("questions")
    parser.add_argument("--jurisdiction", default="DE")
    parser.add_argument("--language", default="de", choices=["de", "en"])
    parser.add_argument("--max-output-tokens", type=int, default=4096)
    args = parser.parse_args()

    with open(args.questions, encoding="utf-8") as handle:
        questions = [line.strip() for line in handle if line.strip() and not line.startswith("#")]

    provider = build_llm_client_from_env(max_output_tokens=args.max_output_tokens)
    embedding_model = EmbeddingModel()
    engine = create_engine(os.environ["NORMLY_DATABASE_URL"])
    rows = []
    with Session(engine) as session:
        segments = PostgresSegmentRepository(session)
        for question in questions:
            client = RecordingLlmClient(provider)
            build_synthesis_answer(
                question, args.jurisdiction, args.language, embedding_model, segments, client,
            )
            rows.append(client.results)
            calls = ", ".join(f"{r.input_tokens}+{r.output_tokens}" for r in client.results)
            print(f"{calls or 'no model call'}\t{question}")
    print(summarize(rows))


if __name__ == "__main__":
    main()
```

Create `chat/measurement/questions_de.txt` with twelve representative synthesis questions (no norm designation, so none is classified structural):

```text
# One question per line. Lines starting with # are ignored.
Welche Schutzausrüstung ist beim Schweißen vorgeschrieben?
Wie oft müssen ortsveränderliche elektrische Betriebsmittel geprüft werden?
Welche Anforderungen gelten für Fluchtwege in Arbeitsstätten?
Was muss eine Gefährdungsbeurteilung enthalten?
Wann ist ein Gehörschutz zu tragen?
Welche Pflichten hat der Arbeitgeber bei der Unterweisung der Beschäftigten?
Wie sind Leitern vor der Benutzung zu prüfen?
Welche Beleuchtungsstärke ist für Büroarbeitsplätze vorgesehen?
Was gilt für die Lagerung brennbarer Flüssigkeiten?
Welche Erste-Hilfe-Einrichtungen muss ein Betrieb vorhalten?
Wie lange dürfen Beschäftigte ohne Pause am Bildschirm arbeiten?
Welche Maßnahmen schützen vor Absturz bei Arbeiten auf Dächern?
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd chat && ../.venv/bin/pytest tests/test_measure_usage.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add chat/src/normly_chat/measure_usage.py chat/measurement/questions_de.txt chat/tests/test_measure_usage.py
git commit -s -m "feat(chat): add a module to measure token usage per synthesis answer" \
  -m "Refs #40" -m "Assisted-by: Claude Code"
```

---

### Task 8: Frontend — forward caller headers and add the usage route

**Files:**
- Modify: `frontend/src/app/api/chat/route.ts`
- Create: `frontend/src/app/api/account/usage/route.ts`
- Test: `frontend/tests/unit/chat-route.test.ts`, `frontend/tests/unit/account-usage-route.test.ts`

**Interfaces:**
- Consumes: `rateLimitHeaders(request)` from `@/lib/rate-limit-headers`, `getBackendUrls().chat`, `readSessionCookies`.
- Produces: `GET /api/account/usage` → passes the chat service's JSON and status through; 401 `{ detail: "not authenticated" }` without the account cookie.

- [ ] **Step 1: Write the failing tests**

Append to `frontend/tests/unit/chat-route.test.ts` (inside the existing `describe`):

```ts
  it("forwards the anonymous caller headers to chat/", async () => {
    vi.stubEnv("NORMLY_API_BASE_URL", "http://api.internal");
    vi.stubEnv("NORMLY_ACCOUNTS_BASE_URL", "http://accounts.internal");
    vi.stubEnv("NORMLY_CHAT_BASE_URL", "http://chat.internal");
    global.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ answer: "a", answer_type: "synthesis", citations: [] }), { status: 200 }),
    );

    const request = new NextRequest("http://localhost/api/chat", {
      method: "POST",
      body: JSON.stringify({ jurisdiction: "DE", language: "de", message: "Frage" }),
      headers: {
        "content-type": "application/json",
        cookie: "normly_anon_id=anon-123",
        "x-forwarded-for": "1.2.3.4",
      },
    });
    await POST(request);

    const [, init] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(init.headers).toMatchObject({
      "X-Normly-Anon-Id": "anon-123",
      "X-Forwarded-For": "1.2.3.4",
    });
  });

  it("passes a 429 body through unchanged", async () => {
    vi.stubEnv("NORMLY_API_BASE_URL", "http://api.internal");
    vi.stubEnv("NORMLY_ACCOUNTS_BASE_URL", "http://accounts.internal");
    vi.stubEnv("NORMLY_CHAT_BASE_URL", "http://chat.internal");
    const detail = { reason: "quota_exhausted", resets_at: "2026-10-23T00:00:00Z", anonymous: true };
    global.fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail }), { status: 429 }));

    const response = await POST(new NextRequest("http://localhost/api/chat", {
      method: "POST",
      body: JSON.stringify({ jurisdiction: "DE", language: "de", message: "Frage" }),
      headers: { "content-type": "application/json" },
    }));

    expect(response.status).toBe(429);
    expect(await response.json()).toEqual({ detail });
  });
```

Create `frontend/tests/unit/account-usage-route.test.ts`:

```ts
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { afterEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";
import { GET } from "@/app/api/account/usage/route";

const originalFetch = global.fetch;

describe("GET /api/account/usage", () => {
  afterEach(() => {
    global.fetch = originalFetch;
    vi.unstubAllEnvs();
  });

  it("answers 401 without an account session", async () => {
    global.fetch = vi.fn();
    const response = await GET(new NextRequest("http://localhost/api/account/usage"));

    expect(response.status).toBe(401);
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it("asks chat/ with the account token, uncached, and passes the body through", async () => {
    vi.stubEnv("NORMLY_API_BASE_URL", "http://api.internal");
    vi.stubEnv("NORMLY_ACCOUNTS_BASE_URL", "http://accounts.internal");
    vi.stubEnv("NORMLY_CHAT_BASE_URL", "http://chat.internal");
    const usage = {
      used: 7, limit: 30, resets_at: "2026-10-23T00:00:00Z", pool_exhausted: false, pool_resets_at: null,
    };
    global.fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify(usage), { status: 200 }));

    const response = await GET(new NextRequest("http://localhost/api/account/usage", {
      headers: { cookie: "normly_session=account-token" },
    }));

    expect(global.fetch).toHaveBeenCalledWith("http://chat.internal/v1/chat/usage", {
      headers: { Authorization: "Bearer account-token" },
      cache: "no-store",
    });
    expect(await response.json()).toEqual(usage);
  });
});
```

Check `frontend/src/lib/session-cookies.ts` for the real account cookie name and use it instead of `normly_session` if it differs (see `frontend/tests/unit/account-sessions-route.test.ts` for how the existing tests set it).

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd frontend && npx vitest run tests/unit/chat-route.test.ts tests/unit/account-usage-route.test.ts`
Expected: FAIL — headers missing; usage route module not found.

- [ ] **Step 3: Implement**

In `frontend/src/app/api/chat/route.ts`, import `rateLimitHeaders` and build the headers as:

```ts
  // The anonymous caller key for chat/'s quota, the same headers api/ gets.
  const headers: Record<string, string> = {
    "content-type": "application/json",
    ...rateLimitHeaders(request),
  };
```

Create `frontend/src/app/api/account/usage/route.ts`:

```ts
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { NextRequest, NextResponse } from "next/server";
import { getBackendUrls } from "@/lib/backend-urls";
import { readSessionCookies } from "@/lib/session-cookies";

export async function GET(request: NextRequest): Promise<NextResponse> {
  const { accountSessionToken } = readSessionCookies(request);
  if (!accountSessionToken) {
    return NextResponse.json({ detail: "not authenticated" }, { status: 401 });
  }

  // Uncached for the same reason as /api/account/sessions: a session-scoped GET.
  const backendResponse = await fetch(`${getBackendUrls().chat}/v1/chat/usage`, {
    headers: { Authorization: `Bearer ${accountSessionToken}` },
    cache: "no-store",
  });
  const body = await backendResponse.json();
  return NextResponse.json(body, { status: backendResponse.status });
}
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd frontend && npx vitest run tests/unit/chat-route.test.ts tests/unit/account-usage-route.test.ts`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/app/api/chat/route.ts frontend/src/app/api/account/usage/route.ts \
  frontend/tests/unit/chat-route.test.ts frontend/tests/unit/account-usage-route.test.ts
git commit -s -m "feat(frontend): forward the caller key to chat and proxy the usage endpoint" \
  -m "Refs #40" -m "Assisted-by: Claude Code"
```

---

### Task 9: Frontend — limit notices in the chat

**Files:**
- Create: `frontend/src/lib/i18n/interpolate.ts`, `frontend/src/lib/reset-time.ts`, `frontend/src/lib/chat-error-notice.ts`
- Modify: `frontend/src/app/home-page-content.tsx`, `frontend/src/components/chat/chat-input.tsx`, `frontend/src/lib/i18n/de.json`, `frontend/src/lib/i18n/en.json`
- Test: `frontend/tests/unit/reset-time.test.ts`, `frontend/tests/unit/chat-error-notice.test.ts`, `frontend/tests/unit/chat-input.test.tsx`

**Interfaces:**
- Produces: `interpolate(template: string, values: Record<string, string>): string`; `formatResetTime(resetsAt: string, locale: string, now?: Date): string`; `formatRelativeReset(resetsAt: string, locale: string, now?: Date): string`; `MAX_MESSAGE_CHARS = 2000`; `chatErrorNotice(response: Response, t: (key: TranslationKey) => string, locale: string, now?: Date): Promise<string>`.
- i18n keys (`chat.*`): `quotaExhausted`, `quotaExhaustedAnonymous`, `poolExhausted`, `messageTooLong`.

- [ ] **Step 1: Add the translations**

In `frontend/src/lib/i18n/de.json`, inside `"chat"`:

```json
    "quotaExhausted": "Du hast heute alle KI-Antworten genutzt. Wieder verfügbar ab {time}.",
    "quotaExhaustedAnonymous": "Du hast heute alle KI-Antworten ohne Anmeldung genutzt. Melde dich an, um mehr zu erhalten, oder versuche es ab {time} erneut.",
    "poolExhausted": "KI-Antworten sind heute ausgelastet, wieder ab {time}. Suche und Normauskünfte (Gültigkeit, Nachfolger, Verweise) funktionieren weiterhin.",
    "messageTooLong": "Deine Frage ist zu lang. Bitte kürze sie auf höchstens {max} Zeichen.",
```

In `frontend/src/lib/i18n/en.json`, inside `"chat"`:

```json
    "quotaExhausted": "You have used all your AI answers for today. Available again from {time}.",
    "quotaExhaustedAnonymous": "You have used all AI answers available without signing in today. Sign in to get more, or try again from {time}.",
    "poolExhausted": "AI answers are at capacity today, available again from {time}. Search and norm information (validity, successors, references) keep working.",
    "messageTooLong": "Your question is too long. Please shorten it to at most {max} characters.",
```

Note: there is an unrelated `rateLimited` key at line 97 of both files; it belongs to the search page and stays.

- [ ] **Step 2: Write the failing tests**

Create `frontend/tests/unit/reset-time.test.ts`:

```ts
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { describe, expect, it } from "vitest";
import { interpolate } from "@/lib/i18n/interpolate";
import { formatRelativeReset, formatResetTime } from "@/lib/reset-time";

const now = new Date("2026-10-22T19:00:00Z");

describe("reset time formatting", () => {
  it("shows only the time for a reset within a day", () => {
    const expected = new Date("2026-10-23T00:00:00Z").toLocaleTimeString("de", {
      hour: "2-digit", minute: "2-digit",
    });
    expect(formatResetTime("2026-10-23T00:00:00Z", "de", now)).toBe(expected);
  });

  it("includes the date for a later reset", () => {
    expect(formatResetTime("2026-11-01T00:00:00Z", "de", now)).toMatch(/November|Okt/);
  });

  it("describes the remaining time in hours, then days", () => {
    expect(formatRelativeReset("2026-10-23T00:00:00Z", "de", now)).toBe("in 5 Stunden");
    expect(formatRelativeReset("2026-11-01T00:00:00Z", "en", now)).toBe("in 9 days");
  });

  it("interpolates placeholders", () => {
    expect(interpolate("{used} von {limit}", { used: "7", limit: "30" })).toBe("7 von 30");
  });
});
```

Create `frontend/tests/unit/chat-error-notice.test.ts`:

```ts
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { describe, expect, it } from "vitest";
import de from "@/lib/i18n/de.json";
import { chatErrorNotice } from "@/lib/chat-error-notice";
import type { TranslationKey } from "@/lib/i18n/dictionary-keys";

const t = (key: TranslationKey) =>
  key.split(".").reduce<unknown>((node, part) => (node as Record<string, unknown>)[part], de) as string;
const now = new Date("2026-10-22T19:00:00Z");

function limited(detail: unknown): Response {
  return new Response(JSON.stringify({ detail }), { status: 429 });
}

describe("chatErrorNotice", () => {
  it("tells an anonymous user to sign in when their quota is spent", async () => {
    const notice = await chatErrorNotice(
      limited({ reason: "quota_exhausted", resets_at: "2026-10-23T00:00:00Z", anonymous: true }),
      t, "de", now,
    );
    expect(notice).toContain("Melde dich an");
  });

  it("names only the reset time for a registered user's spent quota", async () => {
    const notice = await chatErrorNotice(
      limited({ reason: "quota_exhausted", resets_at: "2026-10-23T00:00:00Z", anonymous: false }),
      t, "de", now,
    );
    expect(notice).toContain("Du hast heute alle KI-Antworten genutzt");
  });

  it("says that search and norm information keep working when a pool is spent", async () => {
    for (const reason of ["pool_daily_exhausted", "pool_monthly_exhausted"]) {
      const notice = await chatErrorNotice(
        limited({ reason, resets_at: "2026-11-01T00:00:00Z", anonymous: true }), t, "de", now,
      );
      expect(notice).toContain("Suche und Normauskünfte");
    }
  });

  it("explains an oversized message", async () => {
    const response = new Response(JSON.stringify({ detail: "message_too_long" }), { status: 400 });
    expect(await chatErrorNotice(response, t, "de", now)).toContain("2000 Zeichen");
  });

  it("falls back to the generic error for anything else", async () => {
    const response = new Response("oops", { status: 503 });
    expect(await chatErrorNotice(response, t, "de", now)).toBe(t("chat.errorAnswer"));
  });
});
```

Append to `frontend/tests/unit/chat-input.test.tsx` (inside its `describe`, reusing its render setup):

```tsx
  it("limits the question to the server's maximum length", () => {
    render(
      <LocaleProvider initialLocale="de">
        <ChatInput onSend={() => {}} disabled={false} />
      </LocaleProvider>,
    );
    expect(screen.getByRole("textbox")).toHaveAttribute("maxLength", "2000");
  });
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `cd frontend && npx vitest run tests/unit/reset-time.test.ts tests/unit/chat-error-notice.test.ts tests/unit/chat-input.test.tsx`
Expected: FAIL — modules not found, no `maxLength`.

- [ ] **Step 4: Implement the helpers**

`frontend/src/lib/i18n/interpolate.ts`:

```ts
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

// Replaces {name} placeholders in a translated string.
export function interpolate(template: string, values: Record<string, string>): string {
  return template.replace(/\{(\w+)\}/g, (match, name: string) => values[name] ?? match);
}
```

`frontend/src/lib/reset-time.ts`:

```ts
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

const HOUR_MS = 3_600_000;
const DAY_MS = 24 * HOUR_MS;

// Resets are UTC instants; they are shown in the viewer's local time.
export function formatResetTime(resetsAt: string, locale: string, now: Date = new Date()): string {
  const reset = new Date(resetsAt);
  const options: Intl.DateTimeFormatOptions =
    reset.getTime() - now.getTime() < DAY_MS
      ? { hour: "2-digit", minute: "2-digit" }
      : { day: "numeric", month: "long", hour: "2-digit", minute: "2-digit" };
  return new Intl.DateTimeFormat(locale, options).format(reset);
}

export function formatRelativeReset(resetsAt: string, locale: string, now: Date = new Date()): string {
  const remaining = new Date(resetsAt).getTime() - now.getTime();
  const format = new Intl.RelativeTimeFormat(locale, { numeric: "always" });
  if (remaining < 2 * DAY_MS) {
    return format.format(Math.max(1, Math.round(remaining / HOUR_MS)), "hour");
  }
  return format.format(Math.round(remaining / DAY_MS), "day");
}
```

`frontend/src/lib/chat-error-notice.ts`:

```ts
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import type { TranslationKey } from "@/lib/i18n/dictionary-keys";
import { interpolate } from "@/lib/i18n/interpolate";
import { formatResetTime } from "@/lib/reset-time";

// Mirrors NORMLY_CHAT_MAX_MESSAGE_CHARS' default; the server's 400 stays the
// backstop if an operator lowers it.
export const MAX_MESSAGE_CHARS = 2000;

interface BudgetDetail {
  reason: string;
  resets_at: string;
  anonymous: boolean;
}

function isBudgetDetail(value: unknown): value is BudgetDetail {
  const detail = value as BudgetDetail | null;
  return (
    typeof detail === "object" && detail !== null &&
    typeof detail.reason === "string" && typeof detail.resets_at === "string"
  );
}

// The assistant-bubble text for a failed chat request.
export async function chatErrorNotice(
  response: Response,
  t: (key: TranslationKey) => string,
  locale: string,
  now: Date = new Date(),
): Promise<string> {
  const body = await response.json().catch(() => null);
  const detail = body?.detail;
  if (response.status === 429 && isBudgetDetail(detail)) {
    const time = formatResetTime(detail.resets_at, locale, now);
    const key: TranslationKey =
      detail.reason === "quota_exhausted"
        ? detail.anonymous ? "chat.quotaExhaustedAnonymous" : "chat.quotaExhausted"
        : "chat.poolExhausted";
    return interpolate(t(key), { time });
  }
  if (response.status === 400 && detail === "message_too_long") {
    return interpolate(t("chat.messageTooLong"), { max: String(MAX_MESSAGE_CHARS) });
  }
  return t("chat.errorAnswer");
}
```

- [ ] **Step 5: Use them**

In `frontend/src/app/home-page-content.tsx`, replace the `!response.ok` branch in `sendMessage`:

```tsx
      if (!response.ok) {
        const notice = await chatErrorNotice(response, t, locale);
        if (viewUnchanged) {
          setMessages((prev) => [...prev, { role: "assistant", content: notice }]);
        }
        return;
      }
```

(import `chatErrorNotice` from `@/lib/chat-error-notice`; `locale` is already available from `useTranslation()` in this component — if not, destructure it there).

In `frontend/src/components/chat/chat-input.tsx`, import `MAX_MESSAGE_CHARS` and add `maxLength={MAX_MESSAGE_CHARS}` to the `<Textarea>`.

- [ ] **Step 6: Run the tests to verify they pass**

Run: `cd frontend && npx vitest run`
Expected: PASS (whole suite — `home-page-content.test.tsx` must still pass).

- [ ] **Step 7: Commit**

```bash
git add frontend/src/lib frontend/src/app/home-page-content.tsx frontend/src/components/chat/chat-input.tsx \
  frontend/tests/unit/reset-time.test.ts frontend/tests/unit/chat-error-notice.test.ts \
  frontend/tests/unit/chat-input.test.tsx
git commit -s -m "feat(frontend): explain spent AI-answer limits in the chat" \
  -m "Refs #40" -m "Assisted-by: Claude Code"
```

---

### Task 10: Frontend — usage section in the profile

**Files:**
- Create: `frontend/src/components/ui/progress.tsx` (via shadcn CLI)
- Create: `frontend/src/components/account/usage-section.tsx`
- Modify: `frontend/src/components/account/profile-overlay.tsx`, `frontend/src/lib/i18n/de.json`, `frontend/src/lib/i18n/en.json`
- Test: `frontend/tests/unit/usage-section.test.tsx`, `frontend/tests/unit/profile-overlay.test.tsx`

**Interfaces:**
- Consumes: `GET /api/account/usage` (Task 8), `interpolate`, `formatResetTime`, `formatRelativeReset` (Task 9), `chat.poolExhausted` key.
- Produces: `UsageSection()` component; i18n keys `account.usageTitle`, `account.usageDescription`, `account.usageAiAnswersToday`, `account.usageResetsAt`, `account.usageLoadError`.

- [ ] **Step 1: Add the shadcn Progress component**

Run: `cd frontend && npx shadcn@latest add progress`
Expected: creates `src/components/ui/progress.tsx` and adds `@radix-ui/react-progress` to `package.json`/`package-lock.json`. Add the AGPL license header (two comment lines, as in `src/components/ui/switch.tsx`) to the generated file if the CLI did not.

- [ ] **Step 2: Add the translations**

`de.json`, inside `"account"`:

```json
    "usageTitle": "Nutzung",
    "usageDescription": "Wie viele KI-Antworten du heute noch erhalten kannst.",
    "usageAiAnswersToday": "KI-Antworten heute: {used} von {limit}",
    "usageResetsAt": "Wird zurückgesetzt um {time} ({relative})",
    "usageLoadError": "Die Nutzung konnte nicht geladen werden.",
```

`en.json`, inside `"account"`:

```json
    "usageTitle": "Usage",
    "usageDescription": "How many AI answers you can still get today.",
    "usageAiAnswersToday": "AI answers today: {used} of {limit}",
    "usageResetsAt": "Resets at {time} ({relative})",
    "usageLoadError": "Usage could not be loaded.",
```

- [ ] **Step 3: Write the failing tests**

Create `frontend/tests/unit/usage-section.test.tsx`:

```tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { LocaleProvider } from "@/lib/i18n/provider";
import { UsageSection } from "@/components/account/usage-section";

const originalFetch = global.fetch;

function usage(overrides: Record<string, unknown> = {}) {
  return new Response(
    JSON.stringify({
      used: 7, limit: 30, resets_at: "2099-01-01T00:00:00Z",
      pool_exhausted: false, pool_resets_at: null, ...overrides,
    }),
    { status: 200 },
  );
}

function renderSection() {
  render(
    <LocaleProvider initialLocale="de">
      <UsageSection />
    </LocaleProvider>,
  );
}

describe("UsageSection", () => {
  afterEach(() => {
    global.fetch = originalFetch;
  });

  it("shows used and limit with a progress bar and the reset", async () => {
    global.fetch = vi.fn().mockResolvedValue(usage());
    renderSection();

    await waitFor(() => expect(screen.getByText("KI-Antworten heute: 7 von 30")).toBeInTheDocument());
    expect(screen.getByRole("progressbar")).toBeInTheDocument();
    expect(screen.getByText(/Wird zurückgesetzt um/)).toBeInTheDocument();
    expect(screen.queryByText(/ausgelastet/)).not.toBeInTheDocument();
    expect(global.fetch).toHaveBeenCalledWith("/api/account/usage");
  });

  it("shows the capacity notice when the pool is exhausted", async () => {
    global.fetch = vi.fn().mockResolvedValue(
      usage({ pool_exhausted: true, pool_resets_at: "2099-01-01T00:00:00Z" }),
    );
    renderSection();

    await waitFor(() => expect(screen.getByText(/KI-Antworten sind heute ausgelastet/)).toBeInTheDocument());
  });

  it("shows an error when loading fails", async () => {
    global.fetch = vi.fn().mockResolvedValue(new Response("{}", { status: 503 }));
    renderSection();

    await waitFor(() =>
      expect(screen.getByText("Die Nutzung konnte nicht geladen werden.")).toBeInTheDocument(),
    );
  });
});
```

In `frontend/tests/unit/profile-overlay.test.tsx`, add a test in the style of its existing section-navigation tests: open the overlay with an account, click the "Nutzung" nav button, and assert `fetch` was called with `/api/account/usage`. If an existing test asserts the number or order of sections, update it to include "Nutzung" between "Sitzungen" and the data section.

- [ ] **Step 4: Run the tests to verify they fail**

Run: `cd frontend && npx vitest run tests/unit/usage-section.test.tsx tests/unit/profile-overlay.test.tsx`
Expected: FAIL — `usage-section` not found; no "Nutzung" button.

- [ ] **Step 5: Implement the section**

Create `frontend/src/components/account/usage-section.tsx`:

```tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

"use client";

import * as React from "react";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { interpolate } from "@/lib/i18n/interpolate";
import { useTranslation } from "@/lib/i18n/provider";
import { formatRelativeReset, formatResetTime } from "@/lib/reset-time";

interface RawUsage {
  used: number;
  limit: number;
  resets_at: string;
  pool_exhausted: boolean;
  pool_resets_at: string | null;
}

export function UsageSection() {
  const { t, locale } = useTranslation();
  const [usage, setUsage] = React.useState<RawUsage | null>(null);
  const [status, setStatus] = React.useState<"loading" | "ready" | "error">("loading");

  React.useEffect(() => {
    fetch("/api/account/usage")
      .then((response) => (response.ok ? response.json() : Promise.reject(new Error("load failed"))))
      .then((body: RawUsage) => {
        setUsage(body);
        setStatus("ready");
      })
      .catch(() => setStatus("error"));
  }, []);

  return (
    <section className="flex flex-col gap-3">
      <h2 className="text-lg font-semibold">{t("account.usageTitle")}</h2>
      <p className="text-sm text-muted-foreground">{t("account.usageDescription")}</p>
      {status === "loading" && <Skeleton className="h-20 w-full" />}
      {status === "error" && <p className="text-sm text-destructive">{t("account.usageLoadError")}</p>}
      {status === "ready" && usage && (
        <div className="flex flex-col gap-2 rounded-lg border p-4">
          <p className="text-sm font-medium">
            {interpolate(t("account.usageAiAnswersToday"), {
              used: String(usage.used), limit: String(usage.limit),
            })}
          </p>
          <Progress
            value={usage.limit > 0 ? Math.min(100, (usage.used / usage.limit) * 100) : 100}
            aria-label={t("account.usageTitle")}
          />
          <p className="text-xs text-muted-foreground">
            {interpolate(t("account.usageResetsAt"), {
              time: formatResetTime(usage.resets_at, locale),
              relative: formatRelativeReset(usage.resets_at, locale),
            })}
          </p>
        </div>
      )}
      {status === "ready" && usage?.pool_exhausted && usage.pool_resets_at && (
        <p role="status" className="rounded-md border bg-muted p-3 text-sm">
          {interpolate(t("chat.poolExhausted"), {
            time: formatResetTime(usage.pool_resets_at, locale),
          })}
        </p>
      )}
    </section>
  );
}
```

In `frontend/src/components/account/profile-overlay.tsx`:
- `type SectionId = "profile" | "notifications" | "email" | "password" | "sessions" | "usage" | "data";`
- add `{ id: "usage", labelKey: "account.usageTitle" },` after the sessions entry in `SECTIONS`;
- import `UsageSection` and render `{activeSection === "usage" && <UsageSection />}` after the sessions line.

- [ ] **Step 6: Run the tests to verify they pass**

Run: `cd frontend && npx vitest run`
Expected: PASS.

- [ ] **Step 7: Check it visually**

Run the app (`run` skill or `cd frontend && npm run dev` against the local compose backend), sign in, open the profile, open "Nutzung", and check light and dark mode and a narrow (phone) width. The section must look like the other account sections (same heading size, spacing, muted description, bordered card).

- [ ] **Step 8: Commit**

```bash
git add frontend/src/components/ui/progress.tsx frontend/src/components/account/usage-section.tsx \
  frontend/src/components/account/profile-overlay.tsx frontend/src/lib/i18n/de.json \
  frontend/src/lib/i18n/en.json frontend/package.json frontend/package-lock.json \
  frontend/tests/unit/usage-section.test.tsx frontend/tests/unit/profile-overlay.test.tsx
git commit -s -m "feat(frontend): add a usage section to the profile" \
  -m "Refs #40" -m "Assisted-by: Claude Code"
```

---

### Task 11: End-to-end checks

**Files:**
- Create: `frontend/tests/e2e/usage-limits.spec.ts`

**Interfaces:**
- Consumes: the running local stack (as the existing e2e specs do).

- [ ] **Step 1: Write the spec**

```ts
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { test, expect } from "@playwright/test";

test.describe("AI answer limits", () => {
  test("a spent quota shows the sign-in notice in the chat", async ({ page }) => {
    // The limit itself is covered by chat/'s tests; this checks the UI path
    // from a 429 to the notice without spending real quota.
    await page.route("**/api/chat", (route) =>
      route.fulfill({
        status: 429,
        contentType: "application/json",
        body: JSON.stringify({
          detail: { reason: "quota_exhausted", resets_at: "2099-01-01T00:00:00Z", anonymous: true },
        }),
      }),
    );
    await page.goto("/");
    await page.getByRole("textbox").fill("Welche Schutzausrüstung ist beim Schweißen vorgeschrieben?");
    await page.keyboard.press("Enter");

    await expect(page.getByText(/Melde dich an, um mehr zu erhalten/)).toBeVisible();
  });

  test("a signed-in user sees their AI answers in the profile", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("link", { name: "Anmelden" }).click();
    await page.getByRole("link", { name: "Registrieren" }).click();
    await expect(page).toHaveURL("http://localhost:3000/signup");
    await page.getByLabel("E-Mail-Adresse").fill(`e2e-usage-${Date.now()}@example.de`);
    await page.getByLabel("Passwort").fill("correct horse battery staple");
    await page.getByRole("button", { name: "Konto erstellen" }).click();
    await expect(page).toHaveURL("http://localhost:3000/");

    // Open the profile the same way account-management.spec.ts does.
    await page.getByRole("button", { name: /Konto|Profil/ }).click();
    await page.getByRole("button", { name: "Nutzung" }).click();

    await expect(page.getByText(/KI-Antworten heute: 0 von \d+/)).toBeVisible();
  });
});
```

Copy the exact profile-opening steps from `frontend/tests/e2e/account-management.spec.ts` if the button name differs.

- [ ] **Step 2: Run it against the local stack**

Run: `cd frontend && npx playwright test tests/e2e/usage-limits.spec.ts`
Expected: PASS (requires the compose stack, like the other e2e specs).

- [ ] **Step 3: Commit**

```bash
git add frontend/tests/e2e/usage-limits.spec.ts
git commit -s -m "test(frontend): cover the AI answer limit notice and usage section end to end" \
  -m "Refs #40" -m "Assisted-by: Claude Code"
```

---

### Task 12: Documentation and configuration

**Files:**
- Modify: `docs/adr/README.md`, `docs/srs/03-requirements.md`, `docs/guide/operations.md`, `.env.example`

- [ ] **Step 1: ADR-029**

Run `git fetch origin && git show origin/develop:docs/adr/README.md | grep "^## ADR-" | tail -1`. If ADR-029 is taken, use the next number everywhere below and in code comments that mention ADR-029.

Insert before `## Open items` in `docs/adr/README.md`:

```markdown
## ADR-029 — LLM cost caps enforced by normly

**Status:** accepted

**Decision:** normly bounds its own inference costs. Two cost pools
(anonymous, registered) each have a daily and a monthly token budget,
counted from the usage the model endpoint reports after each call. Every
caller has a daily quota of AI answers (synthesis answers); graph answers
are never counted. When a budget or quota is spent, the chat service answers
429 with a reason and the reset time, and the Lead Maintainers get a mail at
50/80/100 % of a monthly budget and when a daily budget is spent. Counting
is server-side and fail-closed: no model call without counting.

**Rationale:** STACKIT AI Model Serving offers rate limits only (requests and
tokens per minute, pooled per project), no spending cap — checked in the
portal on 2026-10-22. Rate limits bound the speed of spending, not the total,
and one abuser can exhaust them for everyone. Separate pools keep anonymous
abuse from using up what registered users get.

**Knowingly accepted:** A pool can overshoot its budget by the requests in
flight, at most `concurrent requests × 2 calls × (input cap + output cap)`.
Address-based anonymous counting can be circumvented by changing addresses;
the pool budget still bounds the total.

**Rejected:** A separate LLM gateway service — more to operate than needed
now. Counting in the frontend — bypassable. Reserving tokens before a call —
stricter, but more logic for little gain given the per-call cap.
```

- [ ] **Step 2: SRS**

In `docs/srs/03-requirements.md`, extend REQ-ACC-003 (line ~1203):
- Statement: add "Registered users have a higher quota. The quota counts AI answers (synthesis answers) per day; answers from the reference graph are not counted. When the quota is reached, the user is told when it resets; anonymous users are additionally referred to sign-in."
- Acceptance criteria: add "registered quota configurable; graph answers never counted; the signed-in user can see used quota and reset time in the profile."

Add a new requirement after REQ-ACC-003, using the next free `REQ-ACC-` number (check the index in `docs/srs/README.md`), and add it to the index:

```markdown
### REQ-ACC-00X — Cost budget for language-model use

**Statement:** Inference costs are bounded by a daily and a monthly token budget, separately for anonymous and registered use. A spent budget stops AI answers of that group until the reset; search and answers from the reference graph keep working. The Lead Maintainers are notified at 50, 80 and 100 % of a monthly budget and when a daily budget is spent.

**Rationale:** The model provider offers no spending cap (ADR-029). Separate budgets keep anonymous abuse from affecting registered users.

**Acceptance criteria:** Budgets configurable; counting server-side and fail-closed; one notification per threshold and period.

**Acceptance test:** With a spent budget no model call is made, the user gets a notice with the reset time, and a graph question is still answered.
```

- [ ] **Step 3: Operations guide and `.env.example`**

Add a section `## LLM cost caps` to `docs/guide/operations.md` before `## Backups`, containing: the table of variables and defaults from the spec's Configuration section; that `NORMLY_LLM_BUDGET_ALERT_RECIPIENTS` holds the Lead Maintainers' addresses and is set only in the VM's `.env`; the worst-case formula; how to measure (`docker compose exec chat python -m normly_chat.measure_usage chat/measurement/questions_de.txt` — check the path inside the image and adjust); and how to read today's usage:

```bash
docker compose exec chat python -c "
from datetime import date; import os
from sqlalchemy import create_engine; from sqlalchemy.orm import Session
from normly_core.graph.postgres.repositories import PostgresLlmUsageRepository
with Session(create_engine(os.environ['NORMLY_DATABASE_URL'])) as s:
    r = PostgresLlmUsageRepository(s)
    for pool in ('anonymous', 'registered'):
        print(pool, r.pool_totals(pool=pool, day=date.today()))"
```

In `.env.example`, after the LLM block, add the nine variables commented out with their defaults and a one-line comment pointing to the operations guide.

- [ ] **Step 4: Check the docs build**

Run: `pip install "zensical==0.0.60" "mkdocstrings==1.0.6" "mkdocstrings-python==2.0.8" "griffelib==2.3.0" "pymdown-extensions==12.1"` into a scratch venv if not present, then the docs build command from `.github/workflows/ci.yml` (the step after the install).
Expected: builds without warnings about the new pages.

- [ ] **Step 5: Commit**

```bash
git add docs/adr/README.md docs/srs/03-requirements.md docs/srs/README.md docs/guide/operations.md .env.example
git commit -s -m "docs: record the LLM cost caps (ADR-029, SRS, operations)" \
  -m "Refs #40" -m "Assisted-by: Claude Code"
```

---

### Task 13: Measure, set the defaults, final review (with the user)

This task needs the user: the measurement runs against STACKIT with the production key, which exists only on the VM.

- [ ] **Step 1: Run the full suites**

Run: `cd core && ../.venv/bin/pytest`, `cd chat && ../.venv/bin/pytest --ignore=tests/test_structural_end_to_end.py`, `cd frontend && npm test`
Expected: all PASS. Report any failure with its output.

- [ ] **Step 2: Ask the user to run the measurement**

Hand the user the command (locally with `NORMLY_LLM_PROVIDER=openai-compatible`, the STACKIT base URL/model/key and a database with the knowledge base, or in the chat container on the VM after a deploy):

```bash
python -m normly_chat.measure_usage chat/measurement/questions_de.txt
```

- [ ] **Step 3: Derive and record the values**

From the summary: output cap = 2 × `max_output_tokens`, rounded up to the next 256. Per-answer cost = `max_answer_total`. Daily pool budget = quota × daily expected users × `mean_answer_total` (agree the expected users with the user). Monthly = 20 × daily unless the user decides otherwise. Add a "Measurement" section to the spec with the date, model, raw summary and derivation; update the defaults in `chat/src/normly_chat/budget_settings.py`, `chat/tests/test_budget_settings.py`, the spec table, the operations guide and `.env.example` if they change.

- [ ] **Step 4: Commit**

```bash
git add -A docs chat .env.example
git commit -s -m "chore(chat): set cost-cap defaults from the model measurement" \
  -m "Refs #40" -m "Assisted-by: Claude Code"
```

- [ ] **Step 5: Final whole-branch review**

Dispatch a reviewer over `git diff origin/develop...HEAD` against the spec. Fix findings, then hand over to the user for push and PR (`gh pr create --base develop`, linked to #40). Edit issue #40 only after the user agrees: remove the "bounded chat history" item and item 6.
