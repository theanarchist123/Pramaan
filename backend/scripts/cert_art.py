"""Make the certificate art library: generate once, look at every picture, freeze the ones you approve.

    cd backend
    .venv\\Scripts\\python scripts\\cert_art.py status
    .venv\\Scripts\\python scripts\\cert_art.py generate --sector Science --count 6      # needs CLOUDFLARE_ACCOUNT_ID and CLOUDFLARE_API_TOKEN in .env
    .venv\\Scripts\\python scripts\\cert_art.py generate --all --count 4 --max-calls 40
    .venv\\Scripts\\python scripts\\cert_art.py sheet                                      # writes contact-sheet.html; open it and LOOK at every picture
    .venv\\Scripts\\python scripts\\cert_art.py approve gen-science-01 gen-science-03 --reviewed
    .venv\\Scripts\\python scripts\\cert_art.py approve --all --reviewed                    # everything waiting, in one go (add --skip ID ID to leave some out)
    .venv\\Scripts\\python scripts\\cert_art.py reject gen-science-02

Free-tier friendly: it stops cleanly when the daily allowance is used up (run again tomorrow; finished pictures are skipped), pauses between calls, and
never makes more than --max-calls requests in one run. Candidates live in backend/data/cert_art/candidates (not committed); approved pictures go to
apps/web/public/certificate-photos/ and app/generated_art.json (committed), which is what certificates use. Review rule: reject any picture that shows a
face or person, a flag, a logo, letters or words, or religious imagery.
"""
from __future__ import annotations

import argparse
import html
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import generated_art  # noqa: E402
from app.agents import chitrakar  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.services import art_library as lib  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
PUBLIC = ROOT / "apps" / "web" / "public" / "certificate-photos"


def candidates_dir() -> Path:
    d = get_settings().data_dir / "cert_art" / "candidates"
    d.mkdir(parents=True, exist_ok=True)
    return d


def sync_photo_manifest() -> None:
    """Keep app/photo_manifest.json (the hash of EVERY file in the certificate-photos folder) in step, exactly as scripts/make_photo_manifest.py does."""
    import hashlib
    import json

    manifest = {p.stem: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(PUBLIC.glob("*.jpg"))}
    out = Path(__file__).resolve().parents[1] / "app" / "photo_manifest.json"
    out.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def cmd_status(_: argparse.Namespace) -> int:
    cdir, idx, done = candidates_dir(), lib._candidates_index(candidates_dir()), generated_art.approved()
    print(f"{'sector':<16} {'approved':>8} {'waiting':>8}")
    for sector in chitrakar.MOTIFS:
        a = sum(1 for m in done.values() if m.get("sector") == sector)
        w = sum(1 for i, m in idx.items() if m.get("sector") == sector and i not in done and (cdir / f"{i}.jpg").exists())
        print(f"{sector:<16} {a:>8} {w:>8}")
    return 0


def cmd_generate(a: argparse.Namespace) -> int:
    sectors = list(chitrakar.MOTIFS) if a.all else [a.sector]
    if not a.all and not a.sector:
        print("Say --sector NAME or --all")
        return 2
    cdir, done = candidates_dir(), generated_art.approved()
    todo = []
    for s in sectors:
        try:
            todo += [p for p in lib.plan_candidates(s, a.count) if p.id not in done and not (cdir / f"{p.id}.jpg").exists()]
        except lib.ArtError as exc:
            print(exc)
            return 2
    todo = todo[: a.max_calls]
    if not todo:
        print("Nothing to do: every planned picture already exists.")
        return 0
    if a.dry_run:
        for p in todo:
            print(f"{p.id}\n   {p.prompt}")
        print(f"\n{len(todo)} picture(s) would be requested.")
        return 0
    s = get_settings()
    try:
        client = lib.FluxClient(s.cloudflare_account_id, s.cloudflare_api_token)
    except lib.AuthFailed as exc:
        print(exc)
        return 2
    made = failed_in_row = 0
    for p in todo:
        data, used = None, ""
        try:
            for variant in lib.prompt_variants(p):
                try:
                    data, used = lib.process_image(client.generate(variant, steps=a.steps)), variant
                    break
                except lib.PromptRejected:
                    time.sleep(a.delay)  # the filter is fuzzy: try a plainer wording of the same idea
        except lib.QuotaExhausted as exc:
            print(f"\nStopped: {exc}\nRun the same command again later; the {made} finished picture(s) are kept.")
            return 0
        except lib.AuthFailed as exc:
            print(f"\nStopped: {exc}")
            return 2
        except lib.ArtError as exc:
            failed_in_row += 1
            print(f"  {p.id}: skipped ({exc})")
            if failed_in_row >= 3:
                print("Three failures in a row; stopping. Try again later.")
                return 1
            continue
        if data is None:
            failed_in_row += 1
            print(f"  {p.id}: skipped (the safety filter refused every wording; try again later or with a different --count)")
            if failed_in_row >= 3:
                print("Three failures in a row; stopping.")
                return 1
            continue
        failed_in_row = 0
        (cdir / f"{p.id}.jpg").write_bytes(data)
        lib.record_candidate(cdir, p, data, prompt=used)
        made += 1
        print(f"  {p.id}: saved ({len(data) // 1024} KB)")
        time.sleep(a.delay)
    print(f"\nDone: {made} new picture(s). Next: `cert_art.py sheet`, look at them, then `approve`.")
    return 0


def cmd_sheet(_: argparse.Namespace) -> int:
    cdir, idx, done = candidates_dir(), lib._candidates_index(candidates_dir()), generated_art.approved()
    cards = []
    for i, m in sorted(idx.items()):
        if not (cdir / f"{i}.jpg").exists():
            continue
        state = "approved" if i in done else "waiting"
        cards.append(
            f'<figure><img src="{html.escape(i)}.jpg" alt="{html.escape(i)}"><figcaption><b>{html.escape(i)}</b> <em>{state}</em>'
            f'<br><small>{html.escape(m["prompt"])}</small></figcaption></figure>'
        )
    page = (
        "<!doctype html><meta charset=utf-8><title>Certificate art review</title>"
        "<style>body{font:15px system-ui;margin:24px;background:#fafafa}figure{display:inline-block;width:300px;margin:8px;vertical-align:top}"
        "img{width:300px;height:300px;object-fit:cover;border:1px solid #ccc}small{color:#555}em{color:#0a6}</style>"
        "<h1>Certificate art review</h1><p><b>Reject any picture that shows</b> a face or a person, a flag, a logo, letters or words, or religious imagery. "
        "Approve with: <code>cert_art.py approve ID ID --reviewed</code></p>" + "".join(cards)
    )
    out = cdir / "contact-sheet.html"
    out.write_text(page, encoding="utf-8")
    print(f"Wrote {out}\nOpen it in your browser and look at every picture.")
    return 0


def cmd_approve(a: argparse.Namespace) -> int:
    if not a.reviewed:
        print("Add --reviewed to confirm you have looked at every one of these pictures (no faces, flags, logos, letters or religious imagery).")
        return 2
    ids = list(a.ids)
    if a.all:
        skip = set(a.skip or [])
        ids = [i for i in lib.waiting_ids(candidates_dir()) if i not in skip]
        print(f"Approving {len(ids)} waiting picture(s)" + (f", skipping {len(skip)}" if skip else "") + ".")
    if not ids:
        print("Nothing to approve. Give picture ids, or use --all.")
        return 1
    code = 0
    for i in ids:
        try:
            lib.approve(i, candidates_dir=candidates_dir(), public_dir=PUBLIC)
            print(f"  {i}: approved and frozen")
        except lib.ArtError as exc:
            print(f"  {i}: {exc}")
            code = 1
    if any((PUBLIC / f"{i}.jpg").exists() for i in ids):
        sync_photo_manifest()
        print("\nFrozen. Commit apps/web/public/certificate-photos, app/photo_manifest.json and app/generated_art.json.")
    return code


def cmd_reject(a: argparse.Namespace) -> int:
    cdir, idx = candidates_dir(), lib._candidates_index(candidates_dir())
    for i in a.ids:
        if i in generated_art.approved():
            print(f"  {i}: already approved; remove it from app/generated_art.json by hand if it must go")
            continue
        (cdir / f"{i}.jpg").unlink(missing_ok=True)
        idx.pop(i, None)
        print(f"  {i}: rejected and deleted")
    import json

    (cdir / "candidates.json").write_text(json.dumps(idx, indent=2, sort_keys=True), encoding="utf-8")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status").set_defaults(fn=cmd_status)
    g = sub.add_parser("generate")
    g.add_argument("--sector")
    g.add_argument("--all", action="store_true")
    g.add_argument("--count", type=int, default=6, help="pictures per sector")
    g.add_argument("--max-calls", type=int, default=40, help="most requests in one run (protects the free allowance)")
    g.add_argument("--steps", type=int, default=4, choices=range(1, 9), help="diffusion steps (1-8)")
    g.add_argument("--delay", type=float, default=1.5, help="seconds between requests")
    g.add_argument("--dry-run", action="store_true", help="print the prompts; make no requests")
    g.set_defaults(fn=cmd_generate)
    sub.add_parser("sheet").set_defaults(fn=cmd_sheet)
    ap_ = sub.add_parser("approve")
    ap_.add_argument("ids", nargs="*")
    ap_.add_argument("--all", action="store_true", help="approve EVERY waiting picture (after you have looked at the contact sheet)")
    ap_.add_argument("--skip", nargs="+", metavar="ID", help="with --all: leave these out")
    ap_.add_argument("--reviewed", action="store_true")
    ap_.set_defaults(fn=cmd_approve)
    rj = sub.add_parser("reject")
    rj.add_argument("ids", nargs="+")
    rj.set_defaults(fn=cmd_reject)
    a = ap.parse_args()
    return a.fn(a)


if __name__ == "__main__":
    raise SystemExit(main())
