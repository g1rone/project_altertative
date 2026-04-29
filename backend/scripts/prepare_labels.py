from __future__ import annotations

import math
import sys
from typing import Any

from shapely.geometry import LineString, MultiLineString, Point, mapping
from shapely.ops import unary_union

from cartography_common import (
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

LINE_LABEL_TAGS = {"GER", "FRA", "ITA", "POL", "ESP", "TUR", "SOV", "CHI", "CHN", "UNI", "USA", "CAN", "BRA", "IND", "MNG"}
MANDATORY_LABEL_TAGS = set(LABEL_NAMES)
SKIP_COUNTRY_LABEL_TAGS = {"AND", "MCO", "LIE", "SMR", "VAT", "LUX", "DAN", "DNZ", "MLT"}


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    countries = ensure_processed_countries()
    country_line_features, country_point_features = build_country_labels(countries)
    write_json(COUNTRY_LABEL_LINES_PATH, {"type": "FeatureCollection", "features": country_line_features})
    write_json(COUNTRY_LABEL_POINTS_PATH, {"type": "FeatureCollection", "features": country_point_features})

    region_labels = build_region_labels()
    write_json(REGION_LABEL_POINTS_PATH, region_labels)

    microstate_labels = build_microstate_labels()
    if microstate_labels is not None:
        write_json(MICROSTATE_LABEL_POINTS_PATH, microstate_labels)

    print(f"country line labels: {len(country_line_features)}")
    print(f"country point labels: {len(country_point_features)}")
    print(f"region labels: {len(region_labels.get('features', []))}")
    if microstate_labels is not None:
        print(f"microstate labels: {len(microstate_labels.get('features', []))}")
    print(f"saved: {COUNTRY_LABEL_LINES_PATH}")
    print(f"saved: {COUNTRY_LABEL_POINTS_PATH}")
    print(f"saved: {REGION_LABEL_POINTS_PATH}")


def build_country_labels(countries: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    line_features: list[dict[str, Any]] = []
    point_features: list[dict[str, Any]] = []
    grouped: dict[str, dict[str, Any]] = {}

    for feature in countries.get("features", []):
        props = feature.get("properties", {})
        tag = str(props.get("tag") or "")
        name = str(props.get("name") or props.get("displayName") or tag)
        if tag in SKIP_COUNTRY_LABEL_TAGS:
            continue
        if tag == "UNI" and "emirates" in name.lower():
            continue

        geometry = fixed_shape(feature.get("geometry"))
        if geometry is None:
            continue
        bucket = grouped.setdefault(tag, {"name": name, "geometries": []})
        if "emirates" not in bucket["name"].lower():
            bucket["name"] = name
        bucket["geometries"].append(geometry)

    for tag, bucket in grouped.items():
        name = str(bucket["name"])
        geometry = unary_union(bucket["geometries"])
        polygon = largest_polygon(geometry)
        if polygon is None:
            continue
        area = polygon.area
        if tag not in MANDATORY_LABEL_TAGS and area < 18.0:
            continue

        label = label_for_country(tag, name)
        label_class, label_size, label_spacing, label_rank = country_label_style(tag, area)
        base_props = {
            "tag": tag,
            "label": label,
            "labelClass": label_class,
            "labelSize": label_size,
            "labelSpacing": label_spacing,
            "labelRank": label_rank,
        }

        line = label_line_for_polygon(polygon, tag, label)
        if line is not None:
            line_features.append({"type": "Feature", "properties": base_props, "geometry": mapping(line)})
        else:
            point = polygon.representative_point()
            point_features.append(
                {"type": "Feature", "properties": base_props, "geometry": {"type": "Point", "coordinates": [point.x, point.y]}}
            )

    return line_features, point_features


def country_label_style(tag: str, area: float) -> tuple[str, float, float, int]:
    if tag in {"SOV", "UNI", "USA", "CAN", "BRA", "IND", "CHI", "CHN"}:
        return "continental", round(min(28, 18 + math.sqrt(max(area, 0)) * 0.35), 2), 0.18, 0
    if tag in {"GER", "FRA", "GBR", "ITA", "POL", "ESP", "TUR", "JAP", "MNG"}:
        return "major", round(min(24, 15 + math.sqrt(max(area, 0)) * 0.45), 2), 0.16, 1
    return "standard", round(min(18, 12 + math.sqrt(max(area, 0)) * 0.4), 2), 0.12, 3


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

    length = max(width, height) * 2.0
    candidate = LineString(
        [
            (center.x - axis[0] * length, center.y - axis[1] * length),
            (center.x + axis[0] * length, center.y + axis[1] * length),
        ]
    )
    interior = polygon.buffer(-0.02)
    if interior.is_empty:
        interior = polygon
    clipped = candidate.intersection(interior)
    segment = longest_line_segment(clipped)
    if segment is None:
        return None

    min_required = min(9.0, max(2.2, len(label) * 0.28))
    if segment.length < min_required:
        return None
    return shrink_line(segment, 0.78)


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


def build_region_labels() -> dict[str, Any]:
    if not REGIONS_PATH.exists():
        return {"type": "FeatureCollection", "features": []}
    regions = read_json(REGIONS_PATH)
    features = []
    for feature in regions.get("features", []):
        props = feature.get("properties", {})
        label = clean_name(props.get("displayName") or props.get("name") or "")
        if is_ugly_label(label):
            continue
        geometry = fixed_shape(feature.get("geometry"))
        if geometry is None or geometry.area < 0.01:
            continue
        point = geometry.representative_point()
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
                },
                "geometry": {"type": "Point", "coordinates": [point.x, point.y]},
            }
        )
    return {"type": "FeatureCollection", "features": features}


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
