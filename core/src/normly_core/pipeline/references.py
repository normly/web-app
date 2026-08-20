# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from __future__ import annotations

import uuid

from normly_core.graph.domain import DocumentRepository, EdgeRepository, IdentityResolutionRepository, Layer
from normly_core.pipeline.domain import RawRecord, RightsRule


def extract_references(
    record: RawRecord,
    document_id: uuid.UUID,
    delivery_id: uuid.UUID,
    document_repo: DocumentRepository,
    edge_repo: EdgeRepository,
    identity_repo: IdentityResolutionRepository,
    rule: RightsRule,
) -> None:
    # The edge follows the record's classification instead of claiming to be
    # free regardless: an edge drawn from a document that may not be exported
    # freely belongs in the commercial layer, or a free export would carry the
    # reference structure of content it may not carry.
    layer = Layer.FREE if rule.may_export_free else Layer.COMMERCIAL

    for reference in record.raw_references:
        target = document_repo.find_by_designation(
            reference.target_issuer, reference.target_designation
        )
        if target is None:
            identity_repo.enqueue_case(
                delivery_id=delivery_id,
                raw_designation=reference.target_designation,
                raw_issuer=reference.target_issuer,
                reason="reference_target_not_found",
            )
            continue
        edge_repo.create_edge(
            from_document_id=document_id,
            to_document_id=target.id,
            edge_type=reference.edge_type,
            jurisdiction=None,
            layer=layer,
            delivery_id=delivery_id,
        )
