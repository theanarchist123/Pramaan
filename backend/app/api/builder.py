"""Admin 'feature on demand' API (Shilpkar)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import plugins_loader
from app.agents import shilpkar
from app.agents.events import RunContext, start_run
from app.config import get_settings
from app.core.ratelimit import check_rate_limit
from app.db import get_session, get_sessionmaker
from app.deps import Principal, require_admin
from app.llm.client import LLMError, LLMRefusal
from app.models import CodeChange, FieldDefinition
from app.services import code_guard, sandbox

router = APIRouter(prefix="/v1/admin/builder", tags=["builder"])
MAX_REPAIRS = 2  # the model may fix its own code at most twice; then a human decides


class RequestIn(BaseModel):
    request: str = Field(min_length=5, max_length=600)


class ChangeOut(BaseModel):
    id: uuid.UUID
    request: str
    slug: str
    summary: str
    status: str
    files: dict[str, str]
    checks: dict[str, Any]
    created_at: datetime
    applied_at: datetime | None
    model_config = {"from_attributes": True}


def _limit(principal: Principal) -> None:
    ok, _ = check_rate_limit(f"builder:{principal.user.id}", 20)
    if not ok:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Slow down — too many builder requests")


# --------------------------------------------------------------------------- fields (no code)
@router.post("/field-proposal")
async def field_proposal(
    body: RequestIn, principal: Principal = Depends(require_admin), session: AsyncSession = Depends(get_session)
):
    """Turn a sentence into a field definition. Nothing is created until you POST /v1/admin/fields."""
    _limit(principal)
    existing = {k for (k,) in (await session.execute(select(FieldDefinition.key))).all()}
    ctx = await start_run("shilpkar_field")
    try:
        proposal, errors = await shilpkar.propose_field(ctx, body.request.strip(), existing)
    except (LLMError, LLMRefusal) as exc:
        await ctx.finish("failed", "model unavailable")
        raise HTTPException(502, "The builder agent is unavailable right now — you can still create the field by hand.") from exc
    await ctx.finish("done", f"proposed {proposal.key}")
    return {"proposal": proposal.model_dump(), "errors": errors, "run_id": str(ctx.run_id)}


# --------------------------------------------------------------------------- plugins (code)
async def _process(change_id: uuid.UUID, ctx: RunContext) -> None:
    """propose → guard → sandbox. Always lands in a terminal state a human can read."""

    async def save(**fields: Any) -> None:
        async with get_sessionmaker()() as s:
            row = await s.get(CodeChange, change_id)
            for k, v in fields.items():
                setattr(row, k, v)
            await s.commit()

    try:
        async with get_sessionmaker()() as s:
            request = (await s.get(CodeChange, change_id)).request
        proposal = await shilpkar.propose_plugin(ctx, request)
        files = {f.path: f.content for f in proposal.files}
        await save(slug=proposal.slug, summary=proposal.summary, files=files)

        if (plugins_loader.plugins_dir() / f"{proposal.slug}.py").exists() or proposal.slug in plugins_loader.loaded:
            await save(status="checks_failed", checks={"guard": [f"a plugin named '{proposal.slug}' already exists"]})
            await ctx.emit("Prahari", "warning", f"Plugin name '{proposal.slug}' is taken — ask for a different one")
            await ctx.finish("done", "name taken")
            return

        # One bounded loop. Every iteration re-runs the guard on whatever the author produced, then the
        # sandbox. A failure of either (a formatting glitch, an unused import, a wrong assertion) is shown
        # to the author, who may fix it — at most MAX_REPAIRS times — and nothing skips a check.
        history: list[dict[str, str]] = []
        for attempt in range(MAX_REPAIRS + 1):
            await ctx.emit("Prahari", "tool", "Static guard: checking the code against the allow-list")
            violations = code_guard.check_files(proposal.slug, files)
            if violations:
                history.append({"step": "code guard", "output": "\n".join(violations)[-600:]})
                if attempt == MAX_REPAIRS:
                    await save(status="rejected_by_guard", files=files,
                               checks={"guard": violations, "attempts": attempt, "history": history})
                    await ctx.emit("Prahari", "warning", f"Guard rejected the code ({len(violations)} violation(s)): {violations[0]}")
                    await ctx.finish("done", "rejected by guard")
                    return
                await ctx.emit("Prahari", "warning", f"Guard rejected the code ({violations[0]}) — asking the author to fix it")
                fixed = await shilpkar.repair_plugin(ctx, request, proposal.slug, files, "code guard", "\n".join(violations))
                files = {f.path: f.content for f in fixed.files}
                continue
            await ctx.emit("Prahari", "result", "Guard passed — code only reads approved public data", confidence=1.0)

            await ctx.emit("Shilpkar", "tool", "Running lint, security scan and tests in an isolated container (no network)")
            result = await sandbox.run_checks(proposal.slug, files)
            checks = {"guard": [], "sandbox": result, "attempts": attempt, "history": history}
            if not result["ran"]:
                await save(status="checks_failed", checks=checks)
                await ctx.emit("Prahari", "warning", f"Could not verify safely: {result['reason']}")
                await ctx.finish("done", "sandbox unavailable")
                return
            if result["passed"]:
                await save(status="ready", files=files, checks=checks)
                note = f" (after {attempt} automatic fix{'es' if attempt != 1 else ''})" if attempt else ""
                await ctx.emit("Prahari", "handoff", f"All checks passed{note} — ready for your review and approval", confidence=1.0)
                await ctx.finish("done", "ready for approval")
                return
            failed = next(s for s in result["steps"] if not s["ok"])
            history.append({"step": failed["name"], "output": failed["output"][-600:]})
            if attempt == MAX_REPAIRS:
                await save(status="checks_failed", files=files, checks=checks)
                await ctx.emit("Prahari", "warning", f"Still failing {failed['name']} after {attempt} fix attempt(s) — not eligible for approval")
                await ctx.finish("done", f"failed {failed['name']}")
                return
            fixed = await shilpkar.repair_plugin(ctx, request, proposal.slug, files, failed["name"], failed["output"])
            files = {f.path: f.content for f in fixed.files}
    except (LLMError, LLMRefusal):
        await save(status="checks_failed", checks={"guard": ["The AI could not draft the plugin right now. Try again."]})
        await ctx.finish("failed", "model unavailable")
    except Exception as exc:  # noqa: BLE001 - never leave a change stuck in 'proposed'
        await save(status="checks_failed", checks={"guard": [f"Internal error: {type(exc).__name__}"]})
        await ctx.finish("failed", "internal error")


@router.post("/changes", status_code=status.HTTP_202_ACCEPTED)
async def propose_change(
    body: RequestIn,
    background: BackgroundTasks,
    principal: Principal = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    _limit(principal)
    change = CodeChange(request=body.request.strip(), slug="pending")
    session.add(change)
    await session.commit()
    ctx = await start_run("shilpkar_plugin")
    background.add_task(_process, change.id, ctx)
    return {"id": str(change.id), "run_id": str(ctx.run_id)}


@router.get("/changes", response_model=list[ChangeOut])
async def list_changes(_: Principal = Depends(require_admin), session: AsyncSession = Depends(get_session)):
    rows = await session.execute(select(CodeChange).order_by(CodeChange.created_at.desc()).limit(30))
    return rows.scalars().all()


@router.get("/changes/{change_id}", response_model=ChangeOut)
async def get_change(change_id: uuid.UUID, _: Principal = Depends(require_admin), session: AsyncSession = Depends(get_session)):
    change = await session.get(CodeChange, change_id)
    if change is None:
        raise HTTPException(404, "Change not found")
    return change


@router.post("/changes/{change_id}/apply", response_model=ChangeOut)
async def apply_change(
    change_id: uuid.UUID,
    request: Request,
    _: Principal = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    """The human approval. Only a change that passed the guard AND the sandbox can be applied."""
    change = await session.get(CodeChange, change_id)
    if change is None:
        raise HTTPException(404, "Change not found")
    if change.status != "ready":
        raise HTTPException(409, f"Only a change whose checks passed can be applied (this one is '{change.status}')")
    if not get_settings().plugins_enabled:
        raise HTTPException(409, "Plugins are disabled on this server (set PLUGINS_ENABLED=true). Nothing was changed.")

    # Re-verify at the last moment: what we write must be exactly what was checked.
    violations = code_guard.check_files(change.slug, change.files)
    if violations:
        raise HTTPException(409, f"Guard re-check failed: {violations[0]}")
    target = plugins_loader.plugins_dir()
    target.mkdir(parents=True, exist_ok=True)
    written = []
    try:
        for rel, src in change.files.items():
            path = target / rel.split("/", 1)[1]
            path.write_text(src, encoding="utf-8")
            written.append(path)
        plugins_loader.load_plugin(request.app, change.slug)
    except plugins_loader.PluginRejected as exc:
        for p in written:
            p.unlink(missing_ok=True)
        raise HTTPException(409, f"Plugin could not be loaded: {exc}") from exc

    change.status, change.applied_at = "applied", datetime.now(timezone.utc)
    await session.commit()
    await session.refresh(change)
    return change


@router.post("/changes/{change_id}/reject", response_model=ChangeOut)
async def reject_change(change_id: uuid.UUID, _: Principal = Depends(require_admin), session: AsyncSession = Depends(get_session)):
    change = await session.get(CodeChange, change_id)
    if change is None:
        raise HTTPException(404, "Change not found")
    if change.status == "applied":
        raise HTTPException(409, "Already applied — remove the plugin file and restart the API to undo it")
    change.status = "rejected"
    await session.commit()
    await session.refresh(change)
    return change


@router.get("/plugins")
async def loaded_plugins(_: Principal = Depends(require_admin)):
    return {"enabled": get_settings().plugins_enabled, "plugins": list(plugins_loader.loaded.values())}
