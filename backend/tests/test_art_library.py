"""Generated certificate art (blueprint module 3): made once with an image model, reviewed by a person, then FROZEN.

What must hold: the prompt can only come from Chitrakar's closed vocabulary (so no faces, flags, logos, text or religious imagery can be asked for);
the model call is fully mockable and never needs the network here; a quota/auth failure stops cleanly instead of looping; a downloaded image is
re-encoded (no hidden metadata) and size-checked; only an APPROVED asset is ever used on a certificate, with its SHA-256 in the signed art block;
and with no approved assets, behaviour is exactly what it was before (stock photos).
"""
from __future__ import annotations

import base64
import hashlib
import io
import json
import re

import httpx
import pytest
from PIL import Image

from app import domain, generated_art
from app.agents import chitrakar
from app.services import art_library as lib


def _jpeg(size=(1024, 1024), exif=False) -> bytes:
    img = Image.new("RGB", size, (200, 150, 40))
    buf = io.BytesIO()
    if exif:
        ex = Image.Exif()
        ex[0x010E] = "SECRET DESCRIPTION"
        img.save(buf, "JPEG", exif=ex)
    else:
        img.save(buf, "JPEG")
    return buf.getvalue()


# ---- prompts come only from the closed vocabulary --------------------------------------------------------------------------------------------
def test_every_prompt_uses_only_vocabulary_motifs_and_no_banned_word():
    for sector in chitrakar.MOTIFS:
        for plan in lib.plan_candidates(sector, 6):
            p = plan.prompt
            assert 20 < len(p) < 2048
            words = set(re.findall(r"[a-z]+", p.lower()))
            assert not (words & set(chitrakar.BANNED_WORDS)), (sector, words & set(chitrakar.BANNED_WORDS))
            assert all(m in chitrakar.MOTIFS[sector] for m in plan.motifs)


def test_planning_is_deterministic_and_ids_are_stable_and_unique():
    a, b = lib.plan_candidates("Science", 5), lib.plan_candidates("Science", 5)
    assert [x.id for x in a] == [x.id for x in b] == [f"gen-science-{i:02d}" for i in range(1, 6)]
    assert [x.prompt for x in a] == [x.prompt for x in b]
    assert len({x.prompt for x in a}) > 1  # not five copies of one prompt
    assert lib.plan_candidates("Arts & Culture", 1)[0].id == "gen-arts-culture-01"


def test_an_unknown_sector_is_refused():
    with pytest.raises(lib.ArtError):
        lib.plan_candidates("Not a sector", 1)


# ---- the model client: mocked, never the network -----------------------------------------------------------------------------------------------
def _client(handler):
    return lib.FluxClient("acct123", "tok-secret", transport=httpx.MockTransport(handler))


def test_a_good_response_returns_image_bytes_and_sends_only_prompt_and_steps():
    seen = {}

    def handler(req: httpx.Request):
        seen["url"], seen["auth"], seen["body"] = str(req.url), req.headers["authorization"], json.loads(req.content)
        return httpx.Response(200, json={"result": {"image": base64.b64encode(_jpeg()).decode()}, "success": True})

    out = _client(handler).generate("a pattern", steps=4)
    assert out[:2] == b"\xff\xd8"
    assert seen["url"].endswith("/accounts/acct123/ai/run/@cf/black-forest-labs/flux-1-schnell")
    assert seen["auth"] == "Bearer tok-secret" and seen["body"] == {"prompt": "a pattern", "steps": 4}  # no seed: the real API rejects it (HTTP 400)


def test_the_bare_image_shape_is_accepted_too():
    out = _client(lambda r: httpx.Response(200, json={"image": base64.b64encode(_jpeg()).decode()})).generate("x")
    assert out[:2] == b"\xff\xd8"


@pytest.mark.parametrize("status,exc", [(429, lib.QuotaExhausted), (401, lib.AuthFailed), (403, lib.AuthFailed)])
def test_quota_and_auth_failures_are_distinct_clear_errors(status, exc):
    with pytest.raises(exc) as e:
        _client(lambda r: httpx.Response(status, json={"success": False, "errors": [{"code": 1, "message": "nope"}]})).generate("x")
    assert "tok-secret" not in str(e.value)  # the token never appears in an error


def test_a_daily_limit_message_in_a_400_is_treated_as_quota():
    body = {"success": False, "errors": [{"code": 3036, "message": "you have used up your daily free allocation of 10,000 neurons"}]}
    with pytest.raises(lib.QuotaExhausted):
        _client(lambda r: httpx.Response(400, json=body)).generate("x")


@pytest.mark.parametrize("response", [
    httpx.Response(200, json={"success": True, "result": {}}),
    httpx.Response(200, json={"result": {"image": "!!!not base64!!!"}}),
    httpx.Response(200, json={"result": {"image": base64.b64encode(b"hello world, not an image").decode()}}),
    httpx.Response(500, text="boom"),
    httpx.Response(200, text="<html>not json</html>"),
])
def test_malformed_or_failed_responses_raise_art_error(response):
    with pytest.raises(lib.ArtError):
        _client(lambda r: response).generate("x")


# ---- images are re-encoded and checked ------------------------------------------------------------------------------------------------------
def test_processing_drops_metadata_caps_size_and_returns_a_jpeg():
    raw = _jpeg((2400, 1800), exif=True)
    assert b"SECRET DESCRIPTION" in raw
    out = lib.process_image(raw)
    assert b"SECRET DESCRIPTION" not in out and out[:2] == b"\xff\xd8"
    assert max(Image.open(io.BytesIO(out)).size) <= lib.MAX_SIDE


def test_a_too_small_image_is_refused():
    with pytest.raises(lib.ArtError):
        lib.process_image(_jpeg((300, 300)))


# ---- only approved assets are used, and the manifest drives certificates ---------------------------------------------------------------------
@pytest.fixture
def library(tmp_path, monkeypatch):
    manifest = tmp_path / "generated_art.json"
    manifest.write_text(json.dumps({"assets": {}}))
    cand, public = tmp_path / "cand", tmp_path / "public"
    cand.mkdir()
    public.mkdir()
    monkeypatch.setattr(generated_art, "ART_MANIFEST_PATH", manifest)
    generated_art.clear_cache()
    yield {"manifest": manifest, "candidates": cand, "public": public}
    generated_art.clear_cache()


def test_with_no_approved_assets_certificates_keep_using_stock_photos(library):
    assert generated_art.ids_for_sector("Science") == []
    assert domain.pick_photo("Science", "ab" * 32) in domain.SECTOR_PHOTOS["Science"]


def test_approving_a_candidate_freezes_it_and_certificates_then_prefer_it(library):
    plan = lib.plan_candidates("Science", 1)[0]
    data = lib.process_image(_jpeg())
    (library["candidates"] / f"{plan.id}.jpg").write_bytes(data)
    lib.record_candidate(library["candidates"], plan, data)
    lib.approve(plan.id, candidates_dir=library["candidates"], public_dir=library["public"], manifest_path=library["manifest"])

    frozen = library["public"] / f"{plan.id}.jpg"
    assert frozen.read_bytes() == data
    entry = json.loads(library["manifest"].read_text())["assets"][plan.id]
    assert entry["sha256"] == hashlib.sha256(data).hexdigest() and entry["sector"] == "Science" and entry["prompt"] == plan.prompt
    assert entry["licence"] and entry["model"] == lib.MODEL

    generated_art.clear_cache()
    assert generated_art.ids_for_sector("Science") == [plan.id]
    assert domain.pick_photo("Science", "00" * 32) == plan.id  # preferred over the stock list
    assert domain.pick_photo("Law", "00" * 32) in domain.SECTOR_PHOTOS["Law"]  # other sectors untouched
    assert domain.is_known_photo(plan.id)


def test_the_signed_art_block_carries_the_hash_and_an_honest_source_label(library):
    plan = lib.plan_candidates("Energy", 1)[0]
    data = lib.process_image(_jpeg())
    lib.record_candidate(library["candidates"], plan, data)
    (library["candidates"] / f"{plan.id}.jpg").write_bytes(data)
    lib.approve(plan.id, candidates_dir=library["candidates"], public_dir=library["public"], manifest_path=library["manifest"])
    generated_art.clear_cache()
    brief = chitrakar.fallback_brief("Energy", "seed")
    block = chitrakar.art_block(brief, plan.id, "fallback")
    assert block["photo"]["sha256"] == hashlib.sha256(data).hexdigest()
    assert "FLUX" in block["photo"]["source"] and "Unsplash" not in block["photo"]["source"]
    stock = chitrakar.art_block(brief, domain.SECTOR_PHOTOS["Energy"][0], "fallback")
    assert stock["photo"]["source"] == "Unsplash License"


def test_approval_refuses_a_candidate_whose_file_changed_after_it_was_recorded(library):
    plan = lib.plan_candidates("Law", 1)[0]
    data = lib.process_image(_jpeg())
    lib.record_candidate(library["candidates"], plan, data)
    (library["candidates"] / f"{plan.id}.jpg").write_bytes(lib.process_image(_jpeg((1100, 1100))))  # swapped after review
    with pytest.raises(lib.ArtError):
        lib.approve(plan.id, candidates_dir=library["candidates"], public_dir=library["public"], manifest_path=library["manifest"])
    assert json.loads(library["manifest"].read_text())["assets"] == {}


def test_approval_refuses_an_unknown_candidate(library):
    with pytest.raises(lib.ArtError):
        lib.approve("gen-science-99", candidates_dir=library["candidates"], public_dir=library["public"], manifest_path=library["manifest"])


def test_every_approved_asset_in_the_real_library_matches_its_file_and_the_photo_manifest():
    """Vacuously true until something is approved; after that it proves each frozen file is the one that was reviewed (and the stock manifest is in step)."""
    from pathlib import Path

    folder = Path(__file__).resolve().parents[2] / "apps" / "web" / "public" / "certificate-photos"
    manifest = chitrakar.photo_manifest()
    for pid, meta in generated_art.approved().items():
        f = folder / f"{pid}.jpg"
        assert f.exists(), f"{pid} is approved but its file is missing"
        digest = hashlib.sha256(f.read_bytes()).hexdigest()
        assert meta["sha256"] == digest and manifest.get(pid) == digest, f"{pid}: file, generated_art.json and photo_manifest.json disagree"
        assert meta["sector"] in chitrakar.MOTIFS and meta["licence"]


def test_a_safety_filter_refusal_is_its_own_retryable_error():
    body = {"success": False, "errors": [{"code": 3030, "message": "AiError: Input prompt contains NSFW content."}]}
    with pytest.raises(lib.PromptRejected):
        _client(lambda r: httpx.Response(400, json=body)).generate("x")


def test_prompt_variants_reuse_only_the_plans_own_motifs_and_stay_clean():
    for sector in chitrakar.MOTIFS:
        for plan in lib.plan_candidates(sector, 4):
            variants = lib.prompt_variants(plan)
            assert len(variants) == 3 and variants[0] == plan.prompt and len(set(variants)) == 3
            for v in variants:
                assert not (set(re.findall(r"[a-z]+", v.lower())) & set(chitrakar.BANNED_WORDS))
                assert all(m.replace("_", " ") in v for m in plan.motifs)


def test_the_wording_that_worked_is_what_gets_recorded(tmp_path):
    plan = lib.plan_candidates("Science", 1)[0]
    data = lib.process_image(_jpeg())
    lib.record_candidate(tmp_path, plan, data, prompt="abstract helix strands pattern, gold and indigo")
    assert json.loads((tmp_path / "candidates.json").read_text())[plan.id]["prompt"] == "abstract helix strands pattern, gold and indigo"


async def test_a_certificate_in_a_sector_with_approved_art_uses_it_and_signs_its_hash(client, make_user):
    """End to end on the test database: with the REAL approved library, a Science certificate gets a generated picture whose file hash is in the signed payload."""
    from tests.test_api_flow import _approved_profile_with_cert

    if not generated_art.ids_for_sector("Science"):
        pytest.skip("no approved Science art in this checkout")
    _, _, profile, cert = await _approved_profile_with_cert(client, make_user)
    assert cert["photo_id"] in generated_art.ids_for_sector("Science")
    from pathlib import Path

    f = Path(__file__).resolve().parents[2] / "apps" / "web" / "public" / "certificate-photos" / f"{cert['photo_id']}.jpg"
    detail = (await client.get(f"/v1/certificates/{cert['code']}")).json()
    art = (detail.get("payload") or {}).get("art") or {}
    assert art["photo"]["id"] == cert["photo_id"] and art["photo"]["sha256"] == hashlib.sha256(f.read_bytes()).hexdigest()
    assert "FLUX" in art["photo"]["source"]
    verify = (await client.get(f"/v1/verify/{cert['code']}")).json()
    assert verify["valid"] is True  # the signature still verifies with the generated-art block inside it


def test_waiting_ids_lists_only_pictures_that_exist_and_are_not_approved(tmp_path):
    for sector, n in (("Science", 2), ("Law", 1)):
        for plan in lib.plan_candidates(sector, n):
            data = lib.process_image(_jpeg())
            lib.record_candidate(tmp_path, plan, data)
            (tmp_path / f"{plan.id}.jpg").write_bytes(data)
    (tmp_path / "gen-law-01.jpg").unlink()  # recorded but the file is gone
    assert lib.waiting_ids(tmp_path, set()) == ["gen-science-01", "gen-science-02"]
    assert lib.waiting_ids(tmp_path, {"gen-science-01"}) == ["gen-science-02"]
