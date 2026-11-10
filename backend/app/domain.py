"""Shared vocabulary: keeps agents, search, the map and certificates speaking the same language."""

SECTORS = [
    "Science", "Technology", "Healthcare", "Education", "Arts & Culture", "Literature",
    "Sports", "Business", "Public Service", "Law", "Media", "Social Work",
    "Agriculture", "Energy", "Other",
]

INDIAN_STATES = [
    "Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar", "Chhattisgarh", "Goa", "Gujarat",
    "Haryana", "Himachal Pradesh", "Jharkhand", "Karnataka", "Kerala", "Madhya Pradesh",
    "Maharashtra", "Manipur", "Meghalaya", "Mizoram", "Nagaland", "Odisha", "Punjab",
    "Rajasthan", "Sikkim", "Tamil Nadu", "Telangana", "Tripura", "Uttar Pradesh",
    "Uttarakhand", "West Bengal",
    # Union territories
    "Andaman and Nicobar Islands", "Chandigarh", "Dadra and Nagar Haveli and Daman and Diu",
    "Delhi", "Jammu and Kashmir", "Ladakh", "Lakshadweep", "Puducherry",
]

CLAIM_FIELDS = ["award", "position", "education", "publication", "achievement", "membership", "other"]

# Verification ladder
STATUS_SELF = "self"          # said by the person; never certified
STATUS_WEB = "web"            # independently supported by a public source (capped at 0.9)
STATUS_DOCUMENT = "document"  # backed by an uploaded credential whose holder matches
WEB_CONFIDENCE_CAP = 0.9
DOCUMENT_CONFIDENCE = 0.97
AUTO_APPROVE_THRESHOLD = 0.95  # from the spec: below 95% a human must review


# Verified (HTTP 200, contact-sheet checked) Unsplash photos per sector. Hot-linked from
# images.unsplash.com — free for commercial use, no API key, no attribution required.
SECTOR_PHOTOS: dict[str, list[str]] = {
    "Science": ["1532094349884-543bc11b234d", "1507413245164-6160d8298b31", "1576086213369-97a306d36557"],
    "Technology": ["1518770660439-4636190af475", "1550751827-4bd374c3f58b", "1461749280684-dccba630e2f6", "1451187580459-43490279c0fa"],
    "Healthcare": ["1576091160399-112ba8d25d1d", "1579684385127-1ef15d508118", "1631217868264-e5b90bb7e133"],
    "Education": ["1503676260728-1c00da094a0b", "1427504494785-3a9ca7044f45"],
    "Arts & Culture": ["1513364776144-60967b0f800f", "1460661419201-fd4cecdf8a8b", "1541961017774-22349e4a1262", "1578301978693-85fa9c0320b9"],
    "Literature": ["1457369804613-52c61a468e7d", "1481627834876-b7833e8f5570", "1495446815901-a7297e633e8d"],
    "Sports": ["1461896836934-ffe607ba8211", "1517649763962-0c623066013b", "1530549387789-4c1017266635"],
    "Business": ["1486406146926-c627a92ad1ab", "1454165804606-c3d57bc86b40"],
    "Public Service": ["1532375810709-75b1da00537c", "1575505586569-646b2ca898fc"],
    "Law": ["1589829545856-d10d557cf95f", "1450101499163-c8848c66ca85", "1505664194779-8beaceb93744"],
    "Media": ["1495020689067-958852a7765e", "1504711434969-e33886168f5c", "1478737270239-2f02b77fc618"],
    "Social Work": ["1469571486292-0ba58a3f068b", "1488521787991-ed7bbaae773c", "1559027615-cd4628902d4a"],
    "Agriculture": ["1500382017468-9049fed747ef", "1625246333195-78d9c38ad449", "1574943320219-553eb213f72d"],
    "Energy": ["1508514177221-188b1cf16e9d", "1497435334941-8c899ee9e8e9", "1521618755572-156ae0cdd74d", "1509391366360-2e959784a276", "1613665813446-82a78c468a1d"],
    "Other": ["1506905925346-21bda4d32df4", "1470071459604-3b5ec3a7fe05", "1446776811953-b23d57bd21aa"],
}


def pick_photo(sector: str, seed: str) -> str:
    """Deterministic: the same certificate always gets the same photo."""
    options = SECTOR_PHOTOS.get(sector) or SECTOR_PHOTOS["Other"]
    return options[int(seed[:8], 16) % len(options)]


def is_known_photo(photo_id: str) -> bool:
    """Only photos from our own vetted list may be hot-linked (the id is pasted into a URL)."""
    return any(photo_id in ids for ids in SECTOR_PHOTOS.values())
