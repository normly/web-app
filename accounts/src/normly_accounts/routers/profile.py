# accounts/src/normly_accounts/routers/profile.py
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from __future__ import annotations

import hashlib
import io

from fastapi import APIRouter, Depends, File, HTTPException, Request, Response, UploadFile
from PIL import Image, UnidentifiedImageError
from sqlalchemy.orm import Session

from normly_core.graph.domain import Account, NotificationPreference
from normly_core.graph.postgres.repositories import PostgresAccountRepository

from normly_accounts.dependencies import get_current_account, get_session
from normly_accounts.schemas import AccountResponse, UpdateProfileRequest

profile_router = APIRouter(prefix="/v1/accounts", tags=["profile"])

_MAX_UPLOAD_BYTES = 5 * 1024 * 1024
_AVATAR_SIZE = (256, 256)


def _account_response(account: Account) -> AccountResponse:
    return AccountResponse(
        id=account.id, email=account.email,
        email_verified=account.email_verified_at is not None,
        first_name=account.first_name, last_name=account.last_name,
        has_avatar=account.avatar_image is not None,
        has_password=account.password_hash is not None,
        notification_preference=account.notification_preference.value,
    )


@profile_router.patch("/profile", response_model=AccountResponse)
def update_profile(
    payload: UpdateProfileRequest, account: Account = Depends(get_current_account),
    session: Session = Depends(get_session),
) -> AccountResponse:
    # The set of field names actually present in the request body.
    fields_set = payload.model_fields_set
    first_name = payload.first_name if "first_name" in fields_set else account.first_name
    last_name = payload.last_name if "last_name" in fields_set else account.last_name

    account_repo = PostgresAccountRepository(session)
    account_repo.update_profile_names(account.id, first_name=first_name, last_name=last_name)
    if "notification_preference" in fields_set and payload.notification_preference is not None:
        try:
            preference = NotificationPreference(payload.notification_preference)
        except ValueError:
            raise HTTPException(status_code=400, detail="invalid notification_preference")
        account_repo.update_notification_preference(account.id, preference=preference)
    session.commit()
    updated = account_repo.get_account_by_id(account.id)
    return _account_response(updated)


@profile_router.post("/avatar", response_model=AccountResponse)
def upload_avatar(
    avatar: UploadFile = File(...), account: Account = Depends(get_current_account),
    session: Session = Depends(get_session),
) -> AccountResponse:
    raw = avatar.file.read(_MAX_UPLOAD_BYTES + 1)
    if len(raw) > _MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=400, detail="avatar image exceeds the 5 MB limit")

    try:
        image = Image.open(io.BytesIO(raw))
        image.verify()
        # verify() invalidates the file handle for further use -- Image.open
        # again on the same bytes to get a usable image for resizing.
        image = Image.open(io.BytesIO(raw))
        if image.format not in ("JPEG", "PNG", "WEBP"):
            raise HTTPException(
                status_code=400, detail="avatar must be a JPEG, PNG, or WebP image"
            )
        # Pixel data isn't decoded until convert()/thumbnail() actually read
        # it, so a truncated/corrupt body can pass open() and verify() clean
        # and only raise OSError here -- keep these calls inside the try.
        image = image.convert("RGB")
        image.thumbnail(_AVATAR_SIZE, Image.LANCZOS)
    except (UnidentifiedImageError, OSError):
        raise HTTPException(status_code=400, detail="avatar must be a valid image file")

    # thumbnail() preserves aspect ratio and may not fill both dimensions --
    # paste onto a fixed 256x256 canvas so every avatar is exactly the same
    # size the frontend expects, centered rather than stretched/distorted.
    canvas = Image.new("RGB", _AVATAR_SIZE, (255, 255, 255))
    offset = ((_AVATAR_SIZE[0] - image.width) // 2, (_AVATAR_SIZE[1] - image.height) // 2)
    canvas.paste(image, offset)

    buffer = io.BytesIO()
    canvas.save(buffer, format="JPEG", quality=85)

    account_repo = PostgresAccountRepository(session)
    account_repo.set_avatar(
        account.id, avatar_image=buffer.getvalue(), avatar_content_type="image/jpeg"
    )
    session.commit()
    updated = account_repo.get_account_by_id(account.id)
    return _account_response(updated)


@profile_router.delete("/avatar", response_model=AccountResponse)
def delete_avatar(
    account: Account = Depends(get_current_account), session: Session = Depends(get_session),
) -> AccountResponse:
    account_repo = PostgresAccountRepository(session)
    account_repo.clear_avatar(account.id)
    session.commit()
    updated = account_repo.get_account_by_id(account.id)
    return _account_response(updated)


@profile_router.get("/avatar")
def get_avatar(
    request: Request, account: Account = Depends(get_current_account),
) -> Response:
    if account.avatar_image is None:
        raise HTTPException(status_code=404, detail="no avatar set")

    etag = f'"{hashlib.sha256(account.avatar_image).hexdigest()}"'
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304)

    return Response(
        content=account.avatar_image,
        media_type=account.avatar_content_type,
        headers={
            "ETag": etag,
            "Cache-Control": "private, max-age=0, must-revalidate",
        },
    )
