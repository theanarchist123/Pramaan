from __future__ import annotations

import secrets
import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.deps import Principal, require_scope
from app.models import Webhook, WebhookDelivery
from app.services import webhooks as svc

router = APIRouter(prefix="/v1/webhooks", tags=["developer"])
MAX_PER_USER = 10


class WebhookIn(BaseModel):
    url: str = Field(max_length=500, description="https endpoint that will receive POSTed events")
    events: list[str] = Field(min_length=1, description="Event names from GET /v1/webhooks/events")


class WebhookPatch(BaseModel):
    active: bool | None = None
    events: list[str] | None = None


class WebhookOut(BaseModel):
    id: uuid.UUID
    url: str
    events: list[str]
    active: bool
    created_at: datetime
    model_config = {"from_attributes": True}


class WebhookCreated(WebhookOut):
    secret: str = Field(description="Signing secret. Shown ONCE — store it to verify X-Pramaan-Signature.")


class DeliveryOut(BaseModel):
    delivery_id: str
    event: str
    attempt: int
    status_code: int | None
    ok: bool
    error: str
    duration_ms: int
    created_at: datetime
    model_config = {"from_attributes": True}


@router.get("/events")
async def list_events():
    """Public catalogue of subscribable events."""
    return [{"name": n, "description": d, "admin_only": n in svc.ADMIN_ONLY} for n, d in svc.EVENTS.items()]


def _validate_events(events: list[str], principal: Principal) -> None:
    unknown = set(events) - set(svc.EVENTS)
    if unknown:
        raise HTTPException(422, f"Unknown events: {sorted(unknown)}")
    if set(events) & svc.ADMIN_ONLY and not principal.is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Some of these events are for administrators only")


async def _mine(session: AsyncSession, hook_id: uuid.UUID, principal: Principal) -> Webhook:
    hook = await session.get(Webhook, hook_id)
    if hook is None or hook.owner_id != principal.user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Webhook not found")
    return hook


@router.get("", response_model=list[WebhookOut])
async def list_webhooks(
    principal: Principal = Depends(require_scope("webhooks:manage")), session: AsyncSession = Depends(get_session)
):
    rows = await session.execute(
        select(Webhook).where(Webhook.owner_id == principal.user.id).order_by(Webhook.created_at.desc())
    )
    return rows.scalars().all()


@router.post("", response_model=WebhookCreated, status_code=status.HTTP_201_CREATED)
async def create_webhook(
    body: WebhookIn,
    principal: Principal = Depends(require_scope("webhooks:manage")),
    session: AsyncSession = Depends(get_session),
):
    _validate_events(body.events, principal)
    try:
        svc.check_url(body.url)
    except svc.UnsafeURL as exc:
        raise HTTPException(422, str(exc)) from exc
    count = len((await session.execute(select(Webhook.id).where(Webhook.owner_id == principal.user.id))).all())
    if count >= MAX_PER_USER:
        raise HTTPException(status.HTTP_409_CONFLICT, f"At most {MAX_PER_USER} webhooks per account")
    hook = Webhook(
        owner_id=principal.user.id, url=body.url, events=sorted(set(body.events)),
        secret="whsec_" + secrets.token_urlsafe(24),
    )
    session.add(hook)
    await session.commit()
    await session.refresh(hook)
    return WebhookCreated(**WebhookOut.model_validate(hook).model_dump(), secret=hook.secret)


@router.patch("/{hook_id}", response_model=WebhookOut)
async def update_webhook(
    hook_id: uuid.UUID,
    body: WebhookPatch,
    principal: Principal = Depends(require_scope("webhooks:manage")),
    session: AsyncSession = Depends(get_session),
):
    hook = await _mine(session, hook_id, principal)
    if body.events is not None:
        _validate_events(body.events, principal)
        hook.events = sorted(set(body.events))
    if body.active is not None:
        hook.active = body.active
    await session.commit()
    await session.refresh(hook)
    return hook


@router.post("/{hook_id}/rotate-secret", response_model=WebhookCreated)
async def rotate_secret(
    hook_id: uuid.UUID,
    principal: Principal = Depends(require_scope("webhooks:manage")),
    session: AsyncSession = Depends(get_session),
):
    hook = await _mine(session, hook_id, principal)
    hook.secret = "whsec_" + secrets.token_urlsafe(24)
    await session.commit()
    await session.refresh(hook)
    return WebhookCreated(**WebhookOut.model_validate(hook).model_dump(), secret=hook.secret)


@router.delete("/{hook_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_webhook(
    hook_id: uuid.UUID,
    principal: Principal = Depends(require_scope("webhooks:manage")),
    session: AsyncSession = Depends(get_session),
):
    await session.delete(await _mine(session, hook_id, principal))
    await session.commit()


@router.post("/{hook_id}/test")
async def send_test(
    hook_id: uuid.UUID,
    principal: Principal = Depends(require_scope("webhooks:manage")),
    session: AsyncSession = Depends(get_session),
):
    """Send a sample `ping` event now and report whether your endpoint accepted it."""
    hook = await _mine(session, hook_id, principal)
    data: dict[str, Any] = {"message": "Test event from Pramaan", "webhook_id": str(hook.id)}
    ok = await svc.deliver(hook.id, "ping", data)
    last = (
        await session.execute(
            select(WebhookDelivery).where(WebhookDelivery.webhook_id == hook.id)
            .order_by(WebhookDelivery.created_at.desc()).limit(1)
        )
    ).scalar_one_or_none()
    return {"ok": ok, "status_code": last.status_code if last else None, "error": last.error if last else ""}


@router.get("/{hook_id}/deliveries", response_model=list[DeliveryOut])
async def deliveries(
    hook_id: uuid.UUID,
    principal: Principal = Depends(require_scope("webhooks:manage")),
    session: AsyncSession = Depends(get_session),
):
    hook = await _mine(session, hook_id, principal)
    rows = await session.execute(
        select(WebhookDelivery).where(WebhookDelivery.webhook_id == hook.id)
        .order_by(WebhookDelivery.created_at.desc()).limit(50)
    )
    return rows.scalars().all()
