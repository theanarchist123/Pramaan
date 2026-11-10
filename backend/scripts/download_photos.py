"""Download the curated certificate photos once, so certificates never depend on Unsplash at runtime.

    backend\.venv\Scripts\python backend\scripts\download_photos.py

Writes apps/web/public/certificate-photos/<id>.jpg (900px wide). Commit the folder. Photos are from Unsplash and
used under the Unsplash License (free to use and copy, no attribution required); see LICENSE.txt written beside them.
"""
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.domain import SECTOR_PHOTOS  # noqa: E402

out = Path(__file__).resolve().parents[2] / "apps" / "web" / "public" / "certificate-photos"
out.mkdir(parents=True, exist_ok=True)
ids = sorted({i for v in SECTOR_PHOTOS.values() for i in v})
failed = []
with httpx.Client(timeout=30, follow_redirects=True) as c:
    for pid in ids:
        dest = out / f"{pid}.jpg"
        if dest.exists():
            continue
        r = c.get(f"https://images.unsplash.com/photo-{pid}?w=900&q=75&fm=jpg&fit=crop&crop=entropy")
        if r.status_code == 200 and r.headers.get("content-type", "").startswith("image"):
            dest.write_bytes(r.content)
        else:
            failed.append(pid)
(out / "LICENSE.txt").write_text(
    "These photos come from Unsplash (https://unsplash.com) and are used under the Unsplash License:\n"
    "https://unsplash.com/license  (free for commercial use; no permission or attribution required).\n"
)
print(f"{len(ids) - len(failed)}/{len(ids)} photos in {out}")
if failed:
    print("FAILED:", failed)
    sys.exit(1)
