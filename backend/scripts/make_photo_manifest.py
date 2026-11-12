"""Write app/photo_manifest.json: the SHA-256 of every frozen certificate photo (apps/web/public/certificate-photos/*.jpg).
    python scripts/make_photo_manifest.py
A certificate carries the hash of the photo it was issued with, so swapping a file later is detectable."""
import hashlib
import json
from pathlib import Path

root = Path(__file__).resolve().parents[2]
folder = root / "apps" / "web" / "public" / "certificate-photos"
manifest = {p.stem: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(folder.glob("*.jpg"))}
out = Path(__file__).resolve().parents[1] / "app" / "photo_manifest.json"
out.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(f"wrote {out} ({len(manifest)} photos)")
