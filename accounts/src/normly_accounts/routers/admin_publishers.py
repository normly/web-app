# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from normly_core.graph.domain import Account, AdminAction, PublisherNameTakenError
from normly_core.graph.postgres.repositories import (
    PostgresAdminAuditRepository,
    PostgresPublisherRepository,
)

from normly_accounts.admin_schemas import CreatePublisherRequest, PublisherResponse
from normly_accounts.dependencies import get_session, require_capability
from normly_accounts.permissions import USER_MANAGEMENT

admin_publishers_router = APIRouter(prefix="/v1/admin/publishers", tags=["admin"])


@admin_publishers_router.get("", response_model=list[PublisherResponse])
def list_publishers(
    admin: Account = Depends(require_capability(USER_MANAGEMENT)),
    session: Session = Depends(get_session),
) -> list[PublisherResponse]:
    return [
        PublisherResponse(id=p.id, name=p.name, created_at=p.created_at)
        for p in PostgresPublisherRepository(session).list_publishers()
    ]


@admin_publishers_router.post("", response_model=PublisherResponse, status_code=201)
def create_publisher(
    payload: CreatePublisherRequest,
    admin: Account = Depends(require_capability(USER_MANAGEMENT)),
    session: Session = Depends(get_session),
) -> PublisherResponse:
    now = datetime.now(timezone.utc)
    try:
        publisher = PostgresPublisherRepository(session).create_publisher(
            name=payload.name, created_at=now
        )
    except PublisherNameTakenError:
        raise HTTPException(status_code=409, detail="publisher_name_taken")
    PostgresAdminAuditRepository(session).record(
        action=AdminAction.PUBLISHER_CREATED, actor_account_id=admin.id, occurred_at=now,
        target_publisher_id=publisher.id,
    )
    session.commit()
    return PublisherResponse(id=publisher.id, name=publisher.name, created_at=publisher.created_at)
