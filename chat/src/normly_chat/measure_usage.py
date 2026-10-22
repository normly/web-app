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
