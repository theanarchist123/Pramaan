"""Verify candidate Unsplash photo IDs load without an API key and build a contact sheet to eyeball.

Unsplash allows hot-linking images.unsplash.com/photo-<id> (free, no attribution required).
Run:  .venv\\Scripts\\python.exe scripts\\curate_photos.py <out_dir>
"""
import io
import sys
from pathlib import Path

import httpx
from PIL import Image, ImageDraw

CANDIDATES: dict[str, list[str]] = {
    "Science": ["1532094349884-543bc11b234d", "1507413245164-6160d8298b31", "1576086213369-97a306d36557", "1581093458791-9f3c3250a8b0"],
    "Technology": ["1518770660439-4636190af475", "1550751827-4bd374c3f58b", "1461749280684-dccba630e2f6", "1451187580459-43490279c0fa"],
    "Healthcare": ["1576091160399-112ba8d25d1d", "1579684385127-1ef15d508118", "1631217868264-e5b90bb7e133"],
    "Education": ["1523050854058-8df90110c9f1", "1503676260728-1c00da094a0b", "1427504494785-3a9ca7044f45"],
    "Arts & Culture": ["1513364776144-60967b0f800f", "1460661419201-fd4cecdf8a8b", "1541961017774-22349e4a1262", "1578301978693-85fa9c0320b9"],
    "Literature": ["1457369804613-52c61a468e7d", "1481627834876-b7833e8f5570", "1495446815901-a7297e633e8d"],
    "Sports": ["1461896836934-ffe607ba8211", "1517649763962-0c623066013b", "1530549387789-4c1017266635"],
    "Business": ["1486406146926-c627a92ad1ab", "1497366216548-37526070297c", "1454165804606-c3d57bc86b40"],
    "Public Service": ["1589829545856-d10d557cf95f", "1532375810709-75b1da00537c", "1575505586569-646b2ca898fc"],
    "Law": ["1450101499163-c8848c66ca85", "1505664194779-8beaceb93744", "1589829545856-d10d557cf95f"],
    "Media": ["1495020689067-958852a7765e", "1504711434969-e33886168f5c", "1478737270239-2f02b77fc618"],
    "Social Work": ["1469571486292-0ba58a3f068b", "1488521787991-ed7bbaae773c", "1559027615-cd4628902d4a"],
    "Agriculture": ["1500382017468-9049fed747ef", "1625246333195-78d9c38ad449", "1574943320219-553eb213f72d"],
    "Energy": ["1508514177221-188b1cf16e9d", "1497435334941-8c899ee9e8e9", "1521618755572-156ae0cdd74d", "1509391366360-2e959784a276", "1613665813446-82a78c468a1d"],
    "Other": ["1506905925346-21bda4d32df4", "1470071459604-3b5ec3a7fe05", "1446776811953-b23d57bd21aa"],
}

out = Path(sys.argv[1] if len(sys.argv) > 1 else "photos")
out.mkdir(parents=True, exist_ok=True)
T = 200
good: dict[str, list[str]] = {}
tiles: list[tuple[str, str, Image.Image]] = []
with httpx.Client(timeout=20, follow_redirects=True) as c:
    for sector, ids in CANDIDATES.items():
        for pid in dict.fromkeys(ids):
            r = c.get(f"https://images.unsplash.com/photo-{pid}?w=240&h=170&fit=crop&q=60&fm=jpg")
            ok = r.status_code == 200 and r.headers.get("content-type", "").startswith("image")
            print(f"{'OK  ' if ok else 'FAIL'} {sector:15s} {pid}")
            if ok:
                good.setdefault(sector, []).append(pid)
                tiles.append((sector, pid, Image.open(io.BytesIO(r.content)).convert("RGB")))

cols = 6
rows = (len(tiles) + cols - 1) // cols
sheet = Image.new("RGB", (cols * 246, rows * 196), "white")
d = ImageDraw.Draw(sheet)
for i, (sector, pid, im) in enumerate(tiles):
    x, y = (i % cols) * 246, (i // cols) * 196
    sheet.paste(im.resize((240, 170)), (x + 3, y + 3))
    d.rectangle((x + 3, y + 3, x + 130, y + 17), fill="black")
    d.text((x + 6, y + 4), f"{i}:{sector[:14]}", fill="white")
sheet.save(out / "contact.png")
print(f"\n{len(tiles)} loadable -> {out / 'contact.png'}")
for i, (s, p, _) in enumerate(tiles):
    print(i, s, p)
