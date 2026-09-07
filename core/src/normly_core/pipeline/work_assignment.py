# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from __future__ import annotations

import uuid
from dataclasses import dataclass

from normly_core.graph.domain import DocumentRepository, EdgeType
from normly_core.pipeline.domain import RawRecord

_WORK_LINKING_EDGE_TYPES = {EdgeType.REPLACES, EdgeType.WITHDRAWN_BY, EdgeType.ADOPTED_FROM}


@dataclass(frozen=True)
class WorkAssignmentResult:
    work_id: uuid.UUID | None
    is_ambiguous: bool
    reason: str | None


def determine_work_assignment(
    record: RawRecord, document_repo: DocumentRepository
) -> WorkAssignmentResult:
    """
    Only REPLACES/WITHDRAWN_BY/ADOPTED_FROM references count as a Work-linking
    signal -- REFERENCES and BASED_ON_LAW connect documents that are never the
    same Regelwerk. A reference whose target cannot be resolved yet is treated
    as no signal at all (not ambiguous): that document either does not exist
    yet, or the separate `reference_target_not_found` identity-resolution case
    that `references.extract_references` raises for it is the right place to
    flag the problem, not this one.
    """
    candidate_work_ids: set[uuid.UUID] = set()
    for reference in record.raw_references:
        if reference.edge_type not in _WORK_LINKING_EDGE_TYPES:
            continue
        target = document_repo.find_by_designation(
            reference.target_issuer, reference.target_designation
        )
        if target is None:
            continue
        candidate_work_ids.add(target.work_id)

    if len(candidate_work_ids) > 1:
        return WorkAssignmentResult(work_id=None, is_ambiguous=True, reason="conflicting_work_signal")
    if len(candidate_work_ids) == 1:
        return WorkAssignmentResult(work_id=next(iter(candidate_work_ids)), is_ambiguous=False, reason=None)
    return WorkAssignmentResult(work_id=None, is_ambiguous=False, reason=None)
