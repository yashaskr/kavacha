"""Convert OpenCity Bengaluru reference KMLs to browser-ready GeoJSON.

Outputs are geography only — never join crime counts onto these polygons.
"""

from __future__ import annotations

import json
import math
import re
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REF = ROOT / "data" / "reference"
OUT = ROOT / "web" / "data" / "geo"

NS = {"kml": "http://www.opengis.net/kml/2.2"}

LAYERS = [
    {
        "id": "police_stations",
        "label": "Police stations",
        "path": REF
        / "opencity_police_stations"
        / "2026-10-11"
        / "Bengaluru Urban Police Station Locations.kml",
        "name_fields": ("POL_STAName", "name", "Name"),
        "simplify": 0.0,
        "default_on": True,
    },
    {
        "id": "police_jurisdictions",
        "label": "Police jurisdictions",
        "path": REF
        / "opencity_police_jurisdictions"
        / "2026-10-11"
        / "Bengaluru Police Jurisdictions Map.kml",
        "name_fields": ("PS_BOUNDName", "name", "Name"),
        "simplify": 0.00012,
        "default_on": True,
    },
    {
        "id": "bbmp_wards_2023",
        "label": "BBMP wards (2023)",
        "path": REF
        / "opencity_bbmp_wards_2023"
        / "2026-10-11"
        / "BBMP Final Wards Map - 2023.kml",
        "name_fields": ("WardName", "WARD_NAME", "name", "Name"),
        "simplify": 0.00018,
        "default_on": False,
    },
]


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _text(el: ET.Element | None) -> str:
    if el is None or el.text is None:
        return ""
    return el.text.strip()


def _parse_coords(text: str) -> list[list[float]]:
    pts: list[list[float]] = []
    for token in re.split(r"\s+", text.strip()):
        if not token:
            continue
        parts = token.split(",")
        if len(parts) < 2:
            continue
        try:
            lon, lat = float(parts[0]), float(parts[1])
        except ValueError:
            continue
        pts.append([lon, lat])
    return pts


def _perp_dist(p: list[float], a: list[float], b: list[float]) -> float:
    if a == b:
        return math.hypot(p[0] - a[0], p[1] - a[1])
    t = ((p[0] - a[0]) * (b[0] - a[0]) + (p[1] - a[1]) * (b[1] - a[1])) / (
        (b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2
    )
    t = max(0.0, min(1.0, t))
    proj = [a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1])]
    return math.hypot(p[0] - proj[0], p[1] - proj[1])


def _douglas_peucker(points: list[list[float]], epsilon: float) -> list[list[float]]:
    if epsilon <= 0 or len(points) < 3:
        return points
    stack = [(0, len(points) - 1)]
    keep = {0, len(points) - 1}
    while stack:
        start, end = stack.pop()
        a, b = points[start], points[end]
        idx, dist = -1, 0.0
        for i in range(start + 1, end):
            d = _perp_dist(points[i], a, b)
            if d > dist:
                idx, dist = i, d
        if idx >= 0 and dist > epsilon:
            keep.add(idx)
            stack.append((start, idx))
            stack.append((idx, end))
    return [points[i] for i in sorted(keep)]


def _simplify_ring(ring: list[list[float]], epsilon: float) -> list[list[float]]:
    if len(ring) < 4:
        return ring
    closed = ring[0] == ring[-1]
    body = ring[:-1] if closed else ring
    simplified = _douglas_peucker(body, epsilon)
    if closed:
        if simplified[0] != simplified[-1]:
            simplified.append(simplified[0])
    return simplified if len(simplified) >= 4 else ring


def _placemark_props(pm: ET.Element, name_fields: tuple[str, ...]) -> dict:
    props: dict[str, str | int | float] = {}
    for sd in pm.iter():
        if _local(sd.tag) != "SimpleData":
            continue
        key = sd.attrib.get("name")
        if not key:
            continue
        val = _text(sd)
        if val:
            props[key] = val
    name_el = None
    for child in pm:
        if _local(child.tag) == "name":
            name_el = child
            break
    name = _text(name_el)
    for field in name_fields:
        if field in props and props[field]:
            name = str(props[field])
            break
    if name:
        props["name"] = name
    return props


def _geometries(pm: ET.Element, simplify: float) -> list[dict]:
    geos: list[dict] = []
    for el in pm.iter():
        tag = _local(el.tag)
        if tag == "Point":
            coords_el = next((c for c in el if _local(c.tag) == "coordinates"), None)
            pts = _parse_coords(_text(coords_el))
            if pts:
                geos.append({"type": "Point", "coordinates": pts[0]})
        elif tag == "Polygon":
            rings: list[list[list[float]]] = []
            for ring_parent in el:
                rtag = _local(ring_parent.tag)
                if rtag not in {"outerBoundaryIs", "innerBoundaryIs"}:
                    continue
                coords_el = None
                for node in ring_parent.iter():
                    if _local(node.tag) == "coordinates":
                        coords_el = node
                        break
                ring = _parse_coords(_text(coords_el))
                if simplify:
                    ring = _simplify_ring(ring, simplify)
                if len(ring) >= 4:
                    rings.append(ring)
            if rings:
                geos.append({"type": "Polygon", "coordinates": rings})
        elif tag == "LineString":
            coords_el = next((c for c in el if _local(c.tag) == "coordinates"), None)
            pts = _parse_coords(_text(coords_el))
            if simplify:
                pts = _douglas_peucker(pts, simplify)
            if len(pts) >= 2:
                geos.append({"type": "LineString", "coordinates": pts})
    return geos


def kml_to_feature_collection(path: Path, name_fields: tuple[str, ...], simplify: float) -> dict:
    tree = ET.parse(path)
    root = tree.getroot()
    features: list[dict] = []
    for pm in root.iter():
        if _local(pm.tag) != "Placemark":
            continue
        props = _placemark_props(pm, name_fields)
        geos = _geometries(pm, simplify)
        if not geos:
            continue
        if len(geos) == 1:
            geom = geos[0]
        else:
            # MultiGeometry collapse
            gtype = geos[0]["type"]
            if all(g["type"] == gtype for g in geos):
                if gtype == "Polygon":
                    geom = {
                        "type": "MultiPolygon",
                        "coordinates": [g["coordinates"] for g in geos],
                    }
                elif gtype == "Point":
                    geom = {
                        "type": "MultiPoint",
                        "coordinates": [g["coordinates"] for g in geos],
                    }
                else:
                    geom = geos[0]
            else:
                geom = geos[0]
        features.append({"type": "Feature", "properties": props, "geometry": geom})
    return {"type": "FeatureCollection", "features": features}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = {
        "disclaimer": (
            "Reference geography only. These layers are administrative / facility "
            "boundaries and locations. They are not crime incident points and must "
            "not be used for choropleth safety scores without official sub-city counts."
        ),
        "layers": [],
    }
    for layer in LAYERS:
        src: Path = layer["path"]
        if not src.exists():
            print(f"missing {src}")
            continue
        fc = kml_to_feature_collection(src, layer["name_fields"], float(layer["simplify"]))
        out_path = OUT / f"{layer['id']}.geojson"
        out_path.write_text(json.dumps(fc, separators=(",", ":")), encoding="utf-8")
        size_kb = out_path.stat().st_size / 1024
        entry = {
            "id": layer["id"],
            "label": layer["label"],
            "file": f"data/geo/{layer['id']}.geojson",
            "feature_count": len(fc["features"]),
            "bytes": out_path.stat().st_size,
            "default_on": layer["default_on"],
            "source_kml": str(src.relative_to(ROOT)).replace("\\", "/"),
        }
        manifest["layers"].append(entry)
        print(
            f"{layer['id']}: {len(fc['features'])} features -> "
            f"{out_path.relative_to(ROOT)} ({size_kb:.0f} KB)"
        )
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"wrote {OUT / 'manifest.json'}")


if __name__ == "__main__":
    main()
