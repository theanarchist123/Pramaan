import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import API_KEY_SCOPES, TEST_KEY_SCOPES, generate_api_key
from app.db import get_session
from app.deps import Principal, get_principal
from app.models import ApiKey
from app.services import usage
from app.schemas import ApiKeyCreated, ApiKeyIn, ApiKeyOut

router = APIRouter(prefix="/v1/api-keys", tags=["developer"])


def _jwt_only(principal: Principal) -> Principal:
    # Keys are managed by a signed-in human, never by another API key.
    if principal.via != "jwt":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Manage API keys while signed in")
    return principal


@router.get("", response_model=list[ApiKeyOut])
async def list_keys(
    principal: Principal = Depends(get_principal), session: AsyncSession = Depends(get_session)
):
    _jwt_only(principal)
    rows = await session.execute(
        select(ApiKey).where(ApiKey.owner_id == principal.user.id).order_by(ApiKey.created_at.desc())
    )
    return [ApiKeyOut.model_validate(r).model_copy(update={"mode": "test" if r.prefix.startswith("t") else "live"}) for r in rows.scalars().all()]


@router.post("", response_model=ApiKeyCreated, status_code=status.HTTP_201_CREATED)
async def create_key(
    body: ApiKeyIn,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
):
    _jwt_only(principal)
    unknown = set(body.scopes) - API_KEY_SCOPES
    if unknown:
        raise HTTPException(422, f"Unknown scopes: {sorted(unknown)}")
    if body.mode == "test" and set(body.scopes) - TEST_KEY_SCOPES:
        raise HTTPException(422, f"A test key is read-only; these scopes need a live key: {sorted(set(body.scopes) - TEST_KEY_SCOPES)}")
    full, prefix, key_hash = generate_api_key(body.mode)
    row = ApiKey(
        owner_id=principal.user.id,
        name=body.name,
        prefix=prefix,
        key_hash=key_hash,
        scopes=body.scopes,
        rate_limit_per_min=body.rate_limit_per_min,
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return ApiKeyCreated(**{**ApiKeyOut.model_validate(row).model_dump(), "mode": body.mode}, key=full)


@router.get("/{key_id}/usage")
async def key_usage(
    key_id: uuid.UUID,
    days: int = Query(default=30, ge=1, le=90),
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
):
    """Requests per day for one of your own keys (counts only)."""
    _jwt_only(principal)
    row = await session.get(ApiKey, key_id)
    if row is None or row.owner_id != principal.user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "API key not found")
    data = await usage.series(session, key_id, days)
    return {"key_id": key_id, "days": data, "total": sum(d["requests"] for d in data), "throttled": sum(d["throttled"] for d in data)}


@router.delete("/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_key(
    key_id: uuid.UUID,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
):
    _jwt_only(principal)
    row = await session.get(ApiKey, key_id)
    if row is None or row.owner_id != principal.user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "API key not found")
    row.revoked_at = datetime.now(timezone.utc)
    await session.commit()
