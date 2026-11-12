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


async def _limit(principal: Principal) -> None:
    ok, _ = await check_rate_limit(f"builder:{principal.user.id}", 20)
    if not ok:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Slow down — too many builder requests")


# --------------------------------------------------------------------------- fields (no code)
@router.post("/field-proposal")
async def field_proposal(
    body: RequestIn, principal: Principal = Depends(require_admin), session: AsyncSession = Depends(get_session)
):
    """Turn a sentence into a field definition. Nothing is created until you POST /v1/admin/fields."""
    await _limit(principal)
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
async def process_change(change_id: uuid.UUID, ctx: RunContext) -> None:
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
                from app.services.plugin_risk import assess

                checks["risk"] = assess(files)  # shown to the approver; it never approves anything itself
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
    await _limit(principal)
    ctx = await start_run("shilpkar_plugin")
    inline = get_settings().sandbox_in_api
    # The sandbox needs Docker, which the deployed API image does not (and should not) have. Outside local
    # development the job is queued and a separate worker (`python -m app.worker`) runs it.
    change = CodeChange(request=body.request.strip(), slug="pending", run_id=ctx.run_id,
                        status="proposed" if inline else "queued")
    session.add(change)
    await session.commit()
    if inline:
        background.add_task(process_change, change.id, ctx)
    return {"id": str(change.id), "run_id": str(ctx.run_id), "queued": not inline}


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
    if change.slug.startswith("mig_"):
        raise HTTPException(409, "A database migration is never applied by the app: after two approvals a person adds it to the repository through a pull request")
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


# ----- tier T2: views as data (AGT-10) -----
views_public = APIRouter(prefix="/v1/views", tags=["views"])
views_admin = APIRouter(prefix="/v1/admin/views", tags=["builder"])


class ViewRequestIn(BaseModel):
    request: str = Field(min_length=5, max_length=500)


class ViewSpecIn(BaseModel):
    spec: dict


def _view_out(v) -> dict:
    return {"id": str(v.id), "slug": v.slug, "status": v.status, "version": v.version, "spec": v.spec, "request": v.request,
            "has_previous": v.previous_spec is not None, "has_pending_draft": v.draft_spec is not None, "created_by": str(v.created_by) if v.created_by else None, "published_at": v.published_at}


@views_public.get("")
async def list_views(session: AsyncSession = Depends(get_session)):
    from app.models import ViewSpecRow

    rows = (await session.execute(select(ViewSpecRow).where(ViewSpecRow.status == "published").order_by(ViewSpecRow.slug))).scalars().all()
    return [{"slug": r.slug, "title": (r.spec or {}).get("title", r.slug)} for r in rows]


@views_public.get("/{slug}")
async def get_view(slug: str, session: AsyncSession = Depends(get_session)):
    from app.models import ViewSpecRow

    v = (await session.execute(select(ViewSpecRow).where(ViewSpecRow.slug == slug, ViewSpecRow.status == "published"))).scalar_one_or_none()
    if v is None:
        raise HTTPException(404, "No such page")
    return {"slug": v.slug, "version": v.version, "spec": v.spec, "published_at": v.published_at}


@views_admin.get("")
async def admin_list_views(_: Principal = Depends(require_admin), session: AsyncSession = Depends(get_session)):
    from app.models import ViewSpecRow

    rows = (await session.execute(select(ViewSpecRow).order_by(ViewSpecRow.created_at.desc()).limit(50))).scalars().all()
    return [_view_out(r) for r in rows]


@views_admin.post("", status_code=status.HTTP_201_CREATED)
async def propose_view_endpoint(body: ViewRequestIn, principal: Principal = Depends(require_admin), session: AsyncSession = Depends(get_session)):
    """Shilpkar drafts a view spec. It is validated and saved as a DRAFT (public to no one); a second person publishes it."""
    from app.agents import sutradhar
    from app.models import ViewSpecRow
    from app.services import viewspec

    await _limit(principal)
    adm = await sutradhar.admit("shilpkar")
    if not adm.ok:
        raise HTTPException(409, adm.reason)
    ctx = await start_run("shilpkar_view")
    try:
        p = await shilpkar.propose_view(ctx, body.request.strip())
    except (LLMError, LLMRefusal):
        await ctx.finish("failed", "model unavailable")
        raise HTTPException(502, "The designer is temporarily unavailable") from None
    spec, problems = viewspec.validate(p.spec)
    if spec is None:
        await ctx.finish("done", "rejected: " + "; ".join(problems)[:120])
        raise HTTPException(422, "The proposed view broke the rules: " + "; ".join(problems))
    base = viewspec.slugify(spec.title)
    slug, n = base, 2
    while (await session.execute(select(ViewSpecRow.id).where(ViewSpecRow.slug == slug))).first():
        slug, n = f"{base}-{n}", n + 1
    row = ViewSpecRow(slug=slug, request=body.request.strip(), spec=spec.model_dump(), status="draft", created_by=principal.user.id)
    session.add(row)
    await session.commit()
    await ctx.finish("done", f"draft view {slug}")
    return _view_out(row)


async def _view(session: AsyncSession, view_id: uuid.UUID):
    from app.models import ViewSpecRow

    v = await session.get(ViewSpecRow, view_id)
    if v is None:
        raise HTTPException(404, "View not found")
    return v


@views_admin.put("/{view_id}")
async def replace_view(view_id: uuid.UUID, body: ViewSpecIn, principal: Principal = Depends(require_admin), session: AsyncSession = Depends(get_session)):
    """Save a new version of the spec. A draft is replaced in place. A published view keeps serving its live version until a second person publishes this one."""
    from app.services import viewspec

    v = await _view(session, view_id)
    if v.status == "archived":
        raise HTTPException(409, "An archived view cannot be edited")
    spec, problems = viewspec.validate(body.spec)
    if spec is None:
        raise HTTPException(422, "; ".join(problems))
    if v.status == "published":
        v.draft_spec = spec.model_dump()
    else:
        v.spec = spec.model_dump()
    v.edited_by = principal.user.id
    await session.commit()
    return _view_out(v)


@views_admin.post("/{view_id}/publish")
async def publish_view(view_id: uuid.UUID, principal: Principal = Depends(require_admin), session: AsyncSession = Depends(get_session)):
    """Make the draft live. Never the person who proposed or last edited it: two people look at every view before the public can."""
    from app.services import viewspec

    v = await _view(session, view_id)
    if principal.user.id in (v.created_by, v.edited_by):
        raise HTTPException(403, "A second person must publish this view")
    if v.status == "archived":
        raise HTTPException(409, "An archived view cannot be published")
    if v.status == "published" and v.draft_spec is None:
        raise HTTPException(409, "There is nothing new to publish")
    candidate = v.draft_spec if v.status == "published" else v.spec
    spec, problems = viewspec.validate(candidate)  # checked again at the last moment: what goes live is exactly what passed
    if spec is None:
        raise HTTPException(409, "The saved view no longer passes the rules: " + "; ".join(problems))
    if v.status == "published":
        v.previous_spec = v.spec
    v.spec, v.draft_spec = spec.model_dump(), None
    v.status, v.version = "published", (v.version or 0) + 1
    v.published_by, v.published_at = principal.user.id, datetime.now(timezone.utc)
    await session.commit()
    return _view_out(v)


@views_admin.post("/{view_id}/rollback")
async def rollback_view(view_id: uuid.UUID, principal: Principal = Depends(require_admin), session: AsyncSession = Depends(get_session)):
    v = await _view(session, view_id)
    if v.status != "published" or v.previous_spec is None:
        raise HTTPException(409, "There is no earlier version to go back to")
    v.spec, v.previous_spec = v.previous_spec, v.spec
    v.version = (v.version or 0) + 1
    v.published_by, v.published_at = principal.user.id, datetime.now(timezone.utc)
    await session.commit()
    return _view_out(v)


@views_admin.post("/{view_id}/archive")
async def archive_view(view_id: uuid.UUID, principal: Principal = Depends(require_admin), session: AsyncSession = Depends(get_session)):
    v = await _view(session, view_id)
    v.status = "archived"
    await session.commit()
    return _view_out(v)


# ----- tier T3: a proposed database migration (AGT-10) -----
class MigrationRequestIn(BaseModel):
    request: str = Field(min_length=10, max_length=500)


@router.post("/migrations", status_code=status.HTTP_201_CREATED, response_model=ChangeOut)
async def propose_migration_endpoint(body: MigrationRequestIn, principal: Principal = Depends(require_admin), session: AsyncSession = Depends(get_session)):
    """Shilpkar drafts an expand-only migration; it is linted and rehearsed on a scratch database. Passing makes it READY for two approvals; nothing is applied."""
    import re

    from app.agents import sutradhar
    from app.services import migration_check as mc

    await _limit(principal)
    adm = await sutradhar.admit("shilpkar")
    if not adm.ok:
        raise HTTPException(409, adm.reason)
    ctx = await start_run("shilpkar_migration")
    head = mc.current_head()
    try:
        p = await shilpkar.propose_migration(ctx, body.request.strip(), head)
    except (LLMError, LLMRefusal):
        await ctx.finish("failed", "model unavailable")
        raise HTTPException(502, "The designer is temporarily unavailable") from None
    rev_m = re.search(r'^revision\s*=\s*"([^"]+)"', p.source, re.M)
    rev = rev_m.group(1) if rev_m and mc.REV_RE.match(rev_m.group(1)) else "0000_invalid"
    checks: dict = {"lint": mc.lint(p.source), "head": head}
    status_ = "checks_failed"
    if not checks["lint"]:
        result = await mc.rehearse(p.source, skip_lint=True)
        checks["rehearsal"] = result.as_dict()
        status_ = "ready" if result.ok else "checks_failed"
    change = CodeChange(request=body.request.strip(), slug=("mig_" + rev)[:40], summary=p.summary[:300], files={f"migrations/versions/{rev}.py": p.source},
                        status=status_, checks=checks, run_id=ctx.run_id)
    session.add(change)
    await session.commit()
    await ctx.finish("done", f"migration {rev}: {status_}")
    await session.refresh(change)
    return change


@router.post("/migrations/{change_id}/approve", response_model=ChangeOut)
async def approve_migration(change_id: uuid.UUID, principal: Principal = Depends(require_admin), session: AsyncSession = Depends(get_session)):
    """Four eyes: two DIFFERENT people must approve a migration that passed its checks. Approval does not run it; it produces a release note for a person."""
    change = await session.get(CodeChange, change_id)
    if change is None or not change.slug.startswith("mig_"):
        raise HTTPException(404, "Migration not found")
    if change.status != "ready":
        raise HTTPException(409, f"Only a migration whose checks passed can be approved (this one is '{change.status}')")
    who = str(principal.user.id)
    checks = dict(change.checks or {})
    approvals = list(checks.get("approvals", []))
    if who in approvals:
        raise HTTPException(409, "You have already approved this; a second person must")
    approvals.append(who)
    checks["approvals"] = approvals
    if len(approvals) >= 2:
        change.status = "approved_for_release"
        fname = next(iter(change.files)).rsplit("/", 1)[-1]
        checks["release_note"] = (f"Add {fname} to backend/migrations/versions/ in a pull request (a protected path: human code review). Deploy it as a canary and judge it with "
                                  f"scripts/canary_watch.py. Rollback plan: alembic downgrade {checks.get('head', '')}.")
    change.checks = checks
    await session.commit()
    await session.refresh(change)
    return change
