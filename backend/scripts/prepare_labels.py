from __future__ import annotations

import math
import sys
from typing import Any

from shapely.geometry import LineString, MultiLineString, Point, mapping
from shapely.ops import unary_union

from cartography_common import (
    DIAGNOSTICS_DIR,
    LABEL_NAMES,
    PROCESSED_DIR,
    clean_name,
    ensure_processed_countries,
    fixed_shape,
    is_ugly_label,
    label_for_country,
    largest_polygon,
    read_json,
    write_json,
)


COUNTRY_LABEL_LINES_PATH = PROCESSED_DIR / "country_label_lines_1933.geojson"
COUNTRY_LABEL_POINTS_PATH = PROCESSED_DIR / "country_label_points_1933.geojson"
REGIONS_PATH = PROCESSED_DIR / "regions_1933.geojson"
REGION_LABEL_POINTS_PATH = PROCESSED_DIR / "region_label_points_1933.geojson"
MICROSTATES_PATH = PROCESSED_DIR / "microstates_1933.geojson"
MICROSTATE_LABEL_POINTS_PATH = PROCESSED_DIR / "microstate_label_points_1933.geojson"
LABEL_DIAGNOSTICS_PATH = DIAGNOSTICS_DIR / "label_diagnostics_1933.json"

LINE_LABEL_TAGS = {
    "GER",
    "FRA",
    "GBR",
    "ITA",
    "POL",
    "ESP",
    "TUR",
    "SOV",
    "CHI",
    "CHN",
    "UNI",
    "USA",
    "CAN",
    "BRA",
    "IND",
    "MNG",
    "JAP",
}
MANDATORY_LABEL_TAGS = set(LABEL_NAMES)
SKIP_COUNTRY_LABEL_TAGS = {"AND", "MCO", "LIE", "SMR", "VAT", "LUX", "DAN", "DNZ", "MLT"}

MAINLAND_ANCHOR_BOUNDS = {
    "UNI": (-126.0, 24.0, -66.0, 50.5),
    "USA": (-126.0, 24.0, -66.0, 50.5),
    "GBR": (-9.5, 49.0, 2.5, 61.5),
    "FRA": (-6.0, 41.0, 10.5, 52.0),
    "ITA": (6.0, 36.0, 19.0, 48.0),
    "JAP": (129.0, 30.0, 146.5, 46.0),
    "SOV": (25.0, 35.0, 180.0, 78.0),
    "GER": (5.0, 47.0, 17.5, 56.0),
    "POL": (13.0, 48.0, 29.0, 56.0),
    "ESP": (-10.0, 35.0, 5.0, 44.5),
    "TUR": (25.0, 35.0, 46.0, 42.5),
    "IND": (60.0, 5.0, 102.0, 38.0),
    "CHI": (73.0, 18.0, 135.0, 54.0),
}


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    countries = ensure_processed_countries()
    country_line_features, country_point_features, label_diagnostics = build_country_labels(countries)
    write_json(COUNTRY_LABEL_LINES_PATH, {"type": "FeatureCollection", "features": country_line_features})
    write_json(COUNTRY_LABEL_POINTS_PATH, {"type": "FeatureCollection", "features": country_point_features})

    region_labels = build_region_labels(label_diagnostics)
    write_json(REGION_LABEL_POINTS_PATH, region_labels)

    microstate_labels = build_microstate_labels()
    if microstate_labels is not None:
        write_json(MICROSTATE_LABEL_POINTS_PATH, microstate_labels)
    write_json(LABEL_DIAGNOSTICS_PATH, label_diagnostics)

    print(f"country line labels: {len(country_line_features)}")
    print(f"country point labels: {len(country_point_features)}")
    print(f"region labels: {len(region_labels.get('features', []))}")
    if microstate_labels is not None:
        print(f"microstate labels: {len(microstate_labels.get('features', []))}")
    print(f"saved: {COUNTRY_LABEL_LINES_PATH}")
    print(f"saved: {COUNTRY_LABEL_POINTS_PATH}")
    print(f"saved: {REGION_LABEL_POINTS_PATH}")
    print(f"saved diagnostics: {LABEL_DIAGNOSTICS_PATH}")


def build_country_labels(countries: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    line_features: list[dict[str, Any]] = []
    point_features: list[dict[str, Any]] = []
    grouped: dict[str, dict[str, Any]] = {}
    diagnostics: dict[str, Any] = {
        "countryLabels": {},
        "skippedTerritories": [],
        "regionLabels": {"written": 0, "skipped": []},
    }

    for feature in countries.get("features", []):
        props = feature.get("properties", {})
        tag = str(props.get("tag") or "")
        owner_tag = str(props.get("labelOwnerTag") or props.get("ownerTag") or tag)
        name = str(props.get("name") or props.get("displayName") or tag)
        if owner_tag in SKIP_COUNTRY_LABEL_TAGS:
            continue

        geometry = fixed_shape(feature.get("geometry"))
        if geometry is None:
            continue

        if not bool(props.get("isLabelEligible", True)):
            diagnostics["skippedTerritories"].append(
                {
                    "tag": tag,
                    "ownerTag": owner_tag,
                    "labelOwnerTag": owner_tag,
                    "name": name,
                    "reason": props.get("territoryReason") or "not label eligible",
                }
            )
            continue

        bucket = grouped.setdefault(owner_tag, {"name": name, "geometries": [], "parts": []})
        if tag == owner_tag or owner_tag in LABEL_NAMES:
            bucket["name"] = name
        bucket["geometries"].append(geometry)
        bucket["parts"].append({"tag": tag, "name": name, "area": round(float(geometry.area), 4)})

    for owner_tag, bucket in grouped.items():
        name = str(bucket["name"])
        geometry = unary_union(bucket["geometries"])
        polygon = select_label_polygon(geometry, owner_tag)
        if polygon is None:
            continue
        area = polygon.area
        if owner_tag not in MANDATORY_LABEL_TAGS and area < 18.0:
            diagnostics["countryLabels"][owner_tag] = {
                "label": label_for_country(owner_tag, name),
                "method": "hidden",
                "reason": "label component too small",
                "area": round(float(area), 4),
                "parts": bucket["parts"],
            }
            continue

        label = label_for_country(owner_tag, name)
        label_class, label_size, label_spacing, label_rank, min_zoom, max_zoom = country_label_style(owner_tag, area)
        base_props = {
            "tag": owner_tag,
            "ownerTag": owner_tag,
            "label": label,
            "labelClass": label_class,
            "labelSize": label_size,
            "labelSpacing": label_spacing,
            "labelRank": label_rank,
            "minZoom": min_zoom,
            "maxZoom": max_zoom,
            "labelPriority": label_rank * 100 + max(1, int(1000 - area)),
        }

        line = label_line_for_polygon(polygon, owner_tag, label)
        if line is not None:
            line_features.append({"type": "Feature", "properties": base_props, "geometry": mapping(line)})
            method = "line"
        else:
            point = polygon.representative_point()
            point_features.append(
                {"type": "Feature", "properties": base_props, "geometry": {"type": "Point", "coordinates": [point.x, point.y]}}
            )
            method = "point"
        point = polygon.representative_point()
        diagnostics["countryLabels"][owner_tag] = {
            "label": label,
            "method": method,
            "labelClass": label_class,
            "labelSize": label_size,
            "componentArea": round(float(area), 4),
            "componentPoint": [round(point.x, 4), round(point.y, 4)],
            "parts": bucket["parts"],
        }

    return line_features, point_features, diagnostics


def select_label_polygon(geometry: Any, tag: str) -> Any | None:
    polygon = largest_polygon(geometry)
    if polygon is None:
        return None
    polygons = list(geometry.geoms) if hasattr(geometry, "geoms") else [polygon]
    bounds = MAINLAND_ANCHOR_BOUNDS.get(tag)
    if not bounds:
        return polygon
    minx, miny, maxx, maxy = bounds
    anchored = []
    for candidate in polygons:
        point = candidate.representative_point()
        if minx <= point.x <= maxx and miny <= point.y <= maxy:
            anchored.append(candidate)
    return max(anchored, key=lambda item: item.area) if anchored else polygon


def country_label_style(tag: str, area: float) -> tuple[str, float, float, int, float, float]:
    if tag in {"SOV", "UNI", "USA", "CAN", "BRA", "IND", "CHI", "CHN"}:
        return "country-continental", round(min(34, max(28, 24 + math.sqrt(max(area, 0)) * 0.18)), 2), 0.3, 0, 2.0, 6.9
    if tag in {"GER", "FRA", "GBR", "ITA", "POL", "ESP", "TUR", "JAP", "MNG"}:
        return "country-major", round(min(30, max(24, 23 + math.sqrt(max(area, 0)) * 0.8)), 2), 0.28, 1, 2.2, 6.8
    return "country-standard", round(min(21, max(14, 12 + math.sqrt(max(area, 0)) * 0.5)), 2), 0.18, 3, 2.8, 6.7


def label_line_for_polygon(polygon: Any, tag: str, label: str) -> LineString | None:
    if tag not in LINE_LABEL_TAGS:
        return None
    width = polygon.bounds[2] - polygon.bounds[0]
    height = polygon.bounds[3] - polygon.bounds[1]
    if width < 3.0 or height < 1.5:
        return None

    center = polygon.representative_point()
    axis = principal_axis(polygon)
    if axis is None:
        return None

    length = max(width, height) * 2.2
    candidate = LineString(
        [
            (center.x - axis[0] * length, center.y - axis[1] * length),
            (center.x + axis[0] * length, center.y + axis[1] * length),
        ]
    )
    interior = polygon.buffer(-0.03)
    if interior.is_empty:
        interior = polygon
    clipped = candidate.intersection(interior)
    segment = longest_line_segment(clipped)
    if segment is None:
        return None

    min_required = min(9.0, max(2.2, len(label) * 0.28))
    if segment.length < min_required:
        return None
    line = shrink_line(segment, 0.68)
    if not polygon.buffer(0.03).contains(line):
        return None
    return line


def principal_axis(polygon: Any) -> tuple[float, float] | None:
    coords = list(polygon.exterior.coords)
    if len(coords) < 4:
        return None
    mean_x = sum(point[0] for point in coords) / len(coords)
    mean_y = sum(point[1] for point in coords) / len(coords)
    centered = [(point[0] - mean_x, point[1] - mean_y) for point in coords]
    xx = sum(point[0] * point[0] for point in centered) / len(centered)
    xy = sum(point[0] * point[1] for point in centered) / len(centered)
    yy = sum(point[1] * point[1] for point in centered) / len(centered)
    angle = 0.5 * math.atan2(2 * xy, xx - yy)
    axis = (math.cos(angle), math.sin(angle))
    if axis[0] < 0:
        axis = (-axis[0], -axis[1])
    return axis


def longest_line_segment(geometry: Any) -> LineString | None:
    if isinstance(geometry, LineString):
        return geometry if geometry.length > 0 else None
    if isinstance(geometry, MultiLineString):
        lines = [line for line in geometry.geoms if line.length > 0]
        return max(lines, key=lambda line: line.length) if lines else None
    lines = []
    if hasattr(geometry, "geoms"):
        for part in geometry.geoms:
            line = longest_line_segment(part)
            if line is not None:
                lines.append(line)
    return max(lines, key=lambda line: line.length) if lines else None


def shrink_line(line: LineString, factor: float) -> LineString:
    start = line.interpolate((1 - factor) * line.length / 2)
    end = line.interpolate(line.length - (1 - factor) * line.length / 2)
    return LineString([(start.x, start.y), (end.x, end.y)])


def build_region_labels(diagnostics: dict[str, Any]) -> dict[str, Any]:
    if not REGIONS_PATH.exists():
        return {"type": "FeatureCollection", "features": []}
    regions = read_json(REGIONS_PATH)
    features = []
    for feature in regions.get("features", []):
        props = feature.get("properties", {})
        label = clean_name(props.get("displayName") or props.get("name") or "")
        if is_ugly_label(label):
            diagnostics["regionLabels"]["skipped"].append({"regionId": props.get("regionId"), "label": label, "reason": "ugly label"})
            continue
        geometry = fixed_shape(feature.get("geometry"))
        if geometry is None or geometry.area < 0.01:
            diagnostics["regionLabels"]["skipped"].append({"regionId": props.get("regionId"), "label": label, "reason": "tiny or invalid geometry"})
            continue
        point = geometry.representative_point()
        min_zoom = region_label_min_zoom(label, geometry.area)
        features.append(
            {
                "type": "Feature",
                "properties": {
                    "regionId": props.get("regionId"),
                    "countryTag": props.get("countryTag"),
                    "ownerTag": props.get("ownerTag"),
                    "label": label,
                    "labelSize": props.get("labelSize", 11),
                    "labelRank": props.get("labelRank", 1),
                    "minZoom": props.get("minZoom", min_zoom),
                    "maxZoom": props.get("maxZoom", 9.0),
                    "labelPriority": props.get("labelPriority", region_label_priority(label, geometry.area)),
                },
                "geometry": {"type": "Point", "coordinates": [point.x, point.y]},
            }
        )
    diagnostics["regionLabels"]["written"] = len(features)
    return {"type": "FeatureCollection", "features": features}


def region_label_min_zoom(label: str, area: float) -> float:
    if len(label) > 24 or area < 0.25:
        return 5.6
    if len(label) > 18 or area < 0.7:
        return 5.1
    return 4.7


def region_label_priority(label: str, area: float) -> int:
    return max(1, int(10000 - min(area, 200) * 25 + len(label) * 20))


def build_microstate_labels() -> dict[str, Any] | None:
    if not MICROSTATES_PATH.exists():
        return None
    microstates = read_json(MICROSTATES_PATH)
    features = []
    for feature in microstates.get("features", []):
        props = feature.get("properties", {})
        label = str(props.get("label") or props.get("displayName") or props.get("name") or props.get("tag"))
        geometry = fixed_shape(feature.get("geometry"))
        point = None
        if geometry is not None:
            point = geometry.representative_point()
        elif feature.get("geometry", {}).get("type") == "Point":
            coordinates = feature["geometry"].get("coordinates", [0, 0])
            point = Point(coordinates[0], coordinates[1])
        if point is None:
            continue
        features.append(
            {
                "type": "Feature",
                "properties": {
                    "tag": props.get("tag"),
                    "ownerTag": props.get("ownerTag") or props.get("tag"),
                    "label": label,
                    "labelSize": 12 if props.get("tag") != "GRL" else 16,
                    "labelRank": 1,
                    "color": props.get("color"),
                },
                "geometry": {"type": "Point", "coordinates": [point.x, point.y]},
            }
        )
    return {"type": "FeatureCollection", "features": features}


if __name__ == "__main__":
    main()
