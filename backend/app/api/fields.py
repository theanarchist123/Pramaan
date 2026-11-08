from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.deps import Principal, require_admin
from app.models import FieldDefinition
from app.services import fields as svc

router = APIRouter(tags=["fields"])


class FieldOut(BaseModel):
    id: uuid.UUID
    key: str
    label: str
    type: str
    options: list[str]
    help_text: str
    searchable: bool
    active: bool
    created_by: str
    created_at: datetime
    model_config = {"from_attributes": True}


class FieldIn(BaseModel):
    key: str = Field(max_length=40)
    label: str = Field(max_length=120)
    type: str = "text"
    options: list[str] = []
    help_text: str = Field(default="", max_length=300)
    searchable: bool = True
    created_by: str = Field(default="admin", pattern="^(admin|shilpkar)$")


class FieldPatch(BaseModel):
    label: str | None = Field(default=None, max_length=120)
    help_text: str | None = Field(default=None, max_length=300)
    searchable: bool | None = None
    active: bool | None = None
    options: list[str] | None = None


@router.get("/v1/fields", response_model=list[FieldOut])
async def public_fields(session: AsyncSession = Depends(get_session)):
    """The extra fields every profile form, profile page and search understands."""
    return await svc.active_definitions(session)


@router.get("/v1/admin/fields", response_model=list[FieldOut])
async def all_fields(_: Principal = Depends(require_admin), session: AsyncSession = Depends(get_session)):
    rows = await session.execute(select(FieldDefinition).order_by(FieldDefinition.created_at))
    return rows.scalars().all()


@router.post("/v1/admin/fields", response_model=FieldOut, status_code=status.HTTP_201_CREATED)
async def create_field(
    body: FieldIn, _: Principal = Depends(require_admin), session: AsyncSession = Depends(get_session)
):
    options = [o.strip() for o in body.options if o.strip()]
    errors = svc.validate_definition(body.key, body.label, body.type, options)
    if (await session.execute(select(FieldDefinition).where(FieldDefinition.key == body.key))).scalar_one_or_none():
        errors.append(f"a field with key '{body.key}' already exists")
    if errors:
        raise HTTPException(422, "; ".join(errors))
    field = FieldDefinition(
        key=body.key, label=body.label.strip(), type=body.type, options=options, help_text=body.help_text,
        searchable=body.searchable, created_by=body.created_by,
    )
    session.add(field)
    await session.commit()
    await session.refresh(field)
    return field


@router.patch("/v1/admin/fields/{field_id}", response_model=FieldOut)
async def patch_field(
    field_id: uuid.UUID,
    body: FieldPatch,
    _: Principal = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    """Fields are never deleted — deactivating hides them but keeps every stored value."""
    field = await session.get(FieldDefinition, field_id)
    if field is None:
        raise HTTPException(404, "Field not found")
    data = body.model_dump(exclude_unset=True)
    if "options" in data:
        if field.type != "select":
            raise HTTPException(422, "only select fields take options")
        opts = [o.strip() for o in data["options"] if o.strip()]
        if not set(field.options) <= set(opts):
            raise HTTPException(422, "options can be added but not removed (existing values would become invalid)")
        data["options"] = opts
    if "label" in data and not (data["label"] or "").strip():
        raise HTTPException(422, "label is required")
    for k, v in data.items():
        setattr(field, k, v)
    await session.commit()
    await session.refresh(field)
    return field
