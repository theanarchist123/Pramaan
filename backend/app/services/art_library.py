"""Generate certificate art once, review it, freeze it (blueprint module 3).

    plan (closed vocabulary) -> prompt -> image model -> re-encode + size check -> CANDIDATE -> a person looks -> APPROVE -> frozen asset + manifest

* Prompts are built only from Chitrakar's closed per-sector motif vocabulary plus a fixed style line, and are checked against the same banned-word list, so
  nothing about faces, flags, logos, text or religious imagery can be asked for (invariant I-3: no free text from anyone reaches the model).
* The model is Cloudflare Workers AI's `@cf/black-forest-labs/flux-1-schnell` (FLUX.1 [schnell], Apache-2.0). See docs/adr/0014. Nothing at certificate time calls it.
* An approved asset's SHA-256 goes into the signed art block, so the picture on a certificate cannot be swapped later.
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import io
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import httpx
from PIL import Image, UnidentifiedImageError

from app import generated_art
from app.agents import chitrakar

MODEL = "@cf/black-forest-labs/flux-1-schnell"
LICENCE = "FLUX.1 [schnell], Apache-2.0 (generated with Cloudflare Workers AI)"
API_BASE = "https://api.cloudflare.com/client/v4"
MAX_SIDE = 1400
MIN_SIDE = 512
STYLE = (
    "ornamental guilloche engraving, fine concentric linework, perfectly symmetrical, elegant, "
    "warm marigold gold and deep indigo colour palette, high detail, the pattern fills the entire frame edge to edge, no empty background, flat print texture"
)
_QUOTA_HINTS = ("neuron", "quota", "allocation", "limit", "rate")


class ArtError(Exception):
    """Anything that stops an image from being made or approved. The message is safe to print (it never contains the token)."""


class QuotaExhausted(ArtError):
    """The free daily allowance (or a rate limit) is used up: stop, and run again later."""


class PromptRejected(ArtError):
    """Cloudflare's safety filter refused the prompt (a fuzzy classifier: innocent words can trip it, and the same words can pass in another prompt)."""


class AuthFailed(ArtError):
    """Cloudflare refused the account id or token."""


# ---------------------------------------------------------------------------------------------------- planning
@dataclass(frozen=True)
class Plan:
    id: str
    sector: str
    motifs: tuple[str, ...]
    density: str
    symmetry: str
    prompt: str


def slug(sector: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", sector.lower()).strip("-")


def _words(text: str) -> set[str]:
    return set(re.findall(r"[a-z]+", text.lower()))


def build_prompt(motifs: tuple[str, ...], density: str, symmetry: str) -> str:
    sym = {"mirror": "mirror symmetry"}.get(symmetry, symmetry.replace("radial_", "").replace("_", " ") + "-fold radial symmetry")
    prompt = f"abstract {', '.join(m.replace('_', ' ') for m in motifs)}, {density} density, {sym}, {STYLE}"
    bad = _words(prompt) & set(chitrakar.BANNED_WORDS)
    if bad:  # cannot happen with the current vocabulary; this is the guard that keeps it true if the vocabulary ever changes
        raise ArtError(f"the prompt would contain banned word(s): {sorted(bad)}")
    return prompt


def plan_candidates(sector: str, count: int) -> list[Plan]:
    """A deterministic plan: the same sector and count always give the same ids and prompts (so a re-run resumes, never duplicates). The image itself is not reproducible: the API takes no seed."""
    if sector not in chitrakar.MOTIFS:
        raise ArtError(f"unknown sector {sector!r}")
    vocab = chitrakar.MOTIFS[sector]
    out: list[Plan] = []
    for i in range(1, count + 1):
        h = hashlib.sha256(f"{sector}:{i}".encode()).digest()
        n = 1 + h[0] % min(chitrakar.MAX_MOTIFS, len(vocab))
        start = h[1] % len(vocab)
        motifs = tuple(vocab[(start + k) % len(vocab)] for k in range(n))
        density = chitrakar.DENSITIES[h[2] % len(chitrakar.DENSITIES)]
        symmetry = chitrakar.SYMMETRIES[h[3] % len(chitrakar.SYMMETRIES)]
        out.append(Plan(f"gen-{slug(sector)}-{i:02d}", sector, motifs, density, symmetry, build_prompt(motifs, density, symmetry)))
    return out


def prompt_variants(plan: Plan) -> list[str]:
    """The same idea worded up to three ways, from fullest to plainest, for when the safety filter refuses one. Every variant uses only the plan's own
    vocabulary motifs and the same banned-word check."""
    motifs = ", ".join(m.replace("_", " ") for m in plan.motifs)
    out = [plan.prompt, f"abstract {motifs}, {STYLE}", f"abstract {motifs} pattern, gold and indigo"]
    for p in out:
        if _words(p) & set(chitrakar.BANNED_WORDS):
            raise ArtError("a prompt variant would contain a banned word")
    return out


# ---------------------------------------------------------------------------------------------------- the model
class FluxClient:
    """Cloudflare Workers AI REST client for FLUX.1 [schnell]. The token is only ever put in the Authorization header."""

    def __init__(self, account_id: str, token: str, *, transport: httpx.BaseTransport | None = None, timeout: float = 90.0):
        if not account_id or not token:
            raise AuthFailed("Cloudflare account id and API token are required (CLOUDFLARE_ACCOUNT_ID, CLOUDFLARE_API_TOKEN in .env)")
        self._url = f"{API_BASE}/accounts/{account_id}/ai/run/{MODEL}"
        self._http = httpx.Client(timeout=timeout, transport=transport, headers={"Authorization": f"Bearer {token}"})

    def generate(self, prompt: str, steps: int = 4) -> bytes:
        """One image. Only `prompt` and `steps` are sent: the REST API refuses any other property (a `seed` is rejected with HTTP 400)."""
        try:
            r = self._http.post(self._url, json={"prompt": prompt, "steps": steps})
        except httpx.HTTPError as exc:
            raise ArtError(f"could not reach Cloudflare ({type(exc).__name__})") from exc
        detail = _errors(r)
        if r.status_code in (401, 403):
            raise AuthFailed(f"Cloudflare refused the credentials (HTTP {r.status_code}). Check the account id and that the token has Workers AI access. {detail}".strip())
        if r.status_code == 400 and "nsfw" in detail.lower():
            raise PromptRejected("the safety filter refused this prompt")
        if r.status_code in (402, 429) or (r.status_code >= 400 and any(h in detail.lower() for h in _QUOTA_HINTS)):
            raise QuotaExhausted(f"the free allowance or a rate limit was reached (HTTP {r.status_code}). {detail}".strip())
        if r.status_code >= 400:
            raise ArtError(f"Cloudflare returned HTTP {r.status_code}. {detail}".strip())
        try:
            body = r.json()
        except ValueError as exc:
            raise ArtError("Cloudflare returned something that is not JSON") from exc
        result = body.get("result") if isinstance(body, dict) and isinstance(body.get("result"), dict) else body
        b64 = result.get("image") if isinstance(result, dict) else None
        if not b64 or not isinstance(b64, str):
            raise ArtError("the response had no image")
        try:
            raw = base64.b64decode(b64, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ArtError("the image was not valid base64") from exc
        if not (raw.startswith(b"\xff\xd8") or raw.startswith(b"\x89PNG")):
            raise ArtError("the image was not a JPEG or PNG")
        return raw


def _errors(r: httpx.Response) -> str:
    try:
        errs = r.json().get("errors") or []
        return "; ".join(str(e.get("message", e)) for e in errs)[:300]
    except (ValueError, AttributeError):
        return ""


# ---------------------------------------------------------------------------------------------------- images
def process_image(raw: bytes) -> bytes:
    """Decode and re-encode as a JPEG: nothing hidden in the file survives, and a size ceiling keeps certificates light."""
    try:
        img = Image.open(io.BytesIO(raw))
        img.load()
    except (UnidentifiedImageError, OSError) as exc:
        raise ArtError("that is not a readable image") from exc
    if min(img.size) < MIN_SIDE:
        raise ArtError(f"the image is too small ({img.size[0]}x{img.size[1]}; at least {MIN_SIDE}px on each side)")
    img = img.convert("RGB")
    img.thumbnail((MAX_SIDE, MAX_SIDE))
    out = io.BytesIO()
    img.save(out, "JPEG", quality=88, optimize=True)
    return out.getvalue()


# ---------------------------------------------------------------------------------------------------- candidates and approval
def _candidates_index(candidates_dir: Path) -> dict:
    p = candidates_dir / "candidates.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def record_candidate(candidates_dir: Path, plan: Plan, data: bytes, prompt: str | None = None) -> None:
    """Remember what a candidate was made from and the hash of its file as reviewed, so approval can prove the file did not change afterwards."""
    candidates_dir.mkdir(parents=True, exist_ok=True)
    idx = _candidates_index(candidates_dir)
    idx[plan.id] = {
        "sector": plan.sector, "prompt": prompt or plan.prompt, "motifs": list(plan.motifs), "model": MODEL, "licence": LICENCE,
        "sha256": hashlib.sha256(data).hexdigest(), "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    (candidates_dir / "candidates.json").write_text(json.dumps(idx, indent=2, sort_keys=True), encoding="utf-8")


def waiting_ids(candidates_dir: Path, approved_ids: set[str] | None = None) -> list[str]:
    """Every candidate that has a picture on disk and is not approved yet, in a stable order."""
    done = set(generated_art.approved()) if approved_ids is None else approved_ids
    return [i for i in sorted(_candidates_index(candidates_dir)) if (candidates_dir / f"{i}.jpg").exists() and i not in done]


def approve(candidate_id: str, *, candidates_dir: Path, public_dir: Path, manifest_path: Path | None = None) -> dict:
    """Freeze a reviewed candidate: copy it into the public certificate folder and add it to the manifest with its SHA-256."""
    manifest_path = manifest_path or generated_art.ART_MANIFEST_PATH
    meta = _candidates_index(candidates_dir).get(candidate_id)
    src = candidates_dir / f"{candidate_id}.jpg"
    if meta is None or not src.exists():
        raise ArtError(f"no such candidate: {candidate_id}")
    data = src.read_bytes()
    if hashlib.sha256(data).hexdigest() != meta["sha256"]:
        raise ArtError(f"{candidate_id} changed after it was generated; generate it again and re-review")
    public_dir.mkdir(parents=True, exist_ok=True)
    (public_dir / f"{candidate_id}.jpg").write_bytes(data)
    doc = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {"assets": {}}
    entry = {**meta, "approved_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    doc.setdefault("assets", {})[candidate_id] = entry
    manifest_path.write_text(json.dumps(doc, indent=2, sort_keys=True), encoding="utf-8")
    generated_art.clear_cache()
    return entry
