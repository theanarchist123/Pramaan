"""Build apps/web/public/india-states.json from the datameet states GeoJSON (Census-based).

Simplifies geometry (Douglas-Peucker) to a few hundred KB and renames features to the registry's
state names. The source predates the 2019 reorganisation, so Ladakh is part of the Jammu & Kashmir
polygon and the two Dadra/Daman UTs are separate; we merge the latter and let Ladakh share J&K's shape.

Run:  .venv\\Scripts\\python.exe scripts\\build_india_map.py data/india_states.geojson ../apps/web/public/india-states.json
"""
import json
import math
import sys

RENAME = {
    "Andaman & Nicobar Island": "Andaman and Nicobar Islands",
    "Arunanchal Pradesh": "Arunachal Pradesh",
    "Dadara & Nagar Havelli": "Dadra and Nagar Haveli and Daman and Diu",
    "Daman & Diu": "Dadra and Nagar Haveli and Daman and Diu",
    "Jammu & Kashmir": "Jammu and Kashmir",
    "NCT of Delhi": "Delhi",
}
TOL = 0.025  # degrees (~2.5 km): invisible at map scale, 50x smaller file


def dp(points: list, tol: float) -> list:
    """Iterative Douglas-Peucker on a list of [x, y]."""
    if len(points) < 3:
        return points
    keep = [False] * len(points)
    keep[0] = keep[-1] = True
    stack = [(0, len(points) - 1)]
    while stack:
        a, b = stack.pop()
        (x1, y1), (x2, y2) = points[a], points[b]
        dx, dy = x2 - x1, y2 - y1
        norm = math.hypot(dx, dy)
        best, idx = 0.0, -1
        for i in range(a + 1, b):
            x, y = points[i]
            d = math.hypot(x - x1, y - y1) if norm == 0 else abs(dy * x - dx * y + x2 * y1 - y2 * x1) / norm
            if d > best:
                best, idx = d, i
        if best > tol and idx != -1:
            keep[idx] = True
            stack += [(a, idx), (idx, b)]
    return [p for p, k in zip(points, keep) if k]


def ring_area(r: list) -> float:
    return abs(sum(r[i][0] * r[i + 1][1] - r[i + 1][0] * r[i][1] for i in range(len(r) - 1))) / 2


def simplify_polygons(polys: list) -> list:
    out = []
    for poly in polys:
        outer = poly[0]
        s = dp(outer, TOL)
        if len(s) < 4:
            # tiny island: keep a small rounded footprint so it stays visible/clickable
            s = dp(outer, TOL / 8)
            if len(s) < 4:
                continue
        out.append([[[round(x, 2), round(y, 2)] for x, y in s]])  # drop holes: irrelevant at this scale
    return out


def main(src: str, dst: str) -> None:
    data = json.load(open(src, encoding="utf-8"))
    merged: dict[str, list] = {}
    for f in data["features"]:
        name = RENAME.get(f["properties"]["ST_NM"], f["properties"]["ST_NM"])
        g = f["geometry"]
        polys = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
        merged.setdefault(name, []).extend(simplify_polygons(polys))
    feats = [
        {"type": "Feature", "properties": {"name": n}, "geometry": {"type": "MultiPolygon", "coordinates": p}}
        for n, p in sorted(merged.items())
    ]
    json.dump({"type": "FeatureCollection", "features": feats}, open(dst, "w", encoding="utf-8"), separators=(",", ":"))
    import os
    print(f"{len(feats)} regions -> {dst} ({os.path.getsize(dst) / 1024:.0f} KB)")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
