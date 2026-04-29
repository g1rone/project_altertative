from __future__ import annotations

import sys
from typing import Any

from shapely.geometry import Point, mapping

from cartography_common import (
    MICROSTATE_TARGETS,
    PROCESSED_DIR,
    clean_feature_geometry,
    country_color,
    ensure_processed_countries,
    feature_bbox,
    find_admin0_source,
    find_named_feature,
    fixed_shape,
    largest_polygon,
    load_state_countries,
    read_json,
    write_json,
)


MICROSTATES_PATH = PROCESSED_DIR / "microstates_1933.geojson"
MICROSTATE_LABELS_PATH = PROCESSED_DIR / "microstate_label_points_1933.geojson"

FALLBACK_POINTS = {
    "AND": (1.56, 42.54),
    "MCO": (7.42, 43.74),
    "LIE": (9.55, 47.16),
    "SMR": (12.46, 43.94),
    "VAT": (12.45, 41.90),
    "DAN": (18.65, 54.35),
    "DNZ": (18.65, 54.35),
    "MLT": (14.38, 35.94),
    "LUX": (6.13, 49.77),
    "GRL": (-41.0, 72.0),
    "CYP": (33.23, 35.05),
}


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    countries = ensure_processed_countries()
    country_by_tag = {feature["properties"]["tag"]: feature for feature in countries.get("features", [])}
    admin0 = read_json(find_admin0_source())
    state_countries = load_state_countries()

    polygon_features: list[dict[str, Any]] = []
    label_features: list[dict[str, Any]] = []
    seen: set[str] = set()

    for requested_tag, spec in MICROSTATE_TARGETS.items():
        tag = "DAN" if requested_tag == "DNZ" else requested_tag
        if tag in seen:
            continue

        source_feature = find_named_feature(admin0, spec["names"], [tag])
        source_name = "natural-earth-admin0"
        if not source_feature and tag in country_by_tag:
            source_feature = country_by_tag[tag]
            source_name = source_feature.get("properties", {}).get("source", "cshapes-1933")

        geometry = clean_feature_geometry(fixed_shape(source_feature.get("geometry")) if source_feature else None, simplify=0.001)
        fallback_point = geometry is None

        label_point = None
        if geometry is not None:
            polygon = largest_polygon(geometry)
            if polygon is not None and not polygon.is_empty:
                label_point = polygon.representative_point()
            else:
                label_point = geometry.representative_point()
        else:
            lon, lat = FALLBACK_POINTS.get(tag, (0.0, 0.0))
            geometry = Point(lon, lat).buffer(0.08)
            label_point = Point(lon, lat)

        min_lon, min_lat, max_lon, max_lat = feature_bbox(geometry)
        label = str(spec["label"])
        props = {
            "tag": tag,
            "name": label,
            "displayName": label,
            "label": label,
            "ownerTag": tag,
            "controllerTag": tag,
            "color": country_color(tag, state_countries),
            "isMicrostate": True,
            "fallbackPoint": fallback_point,
            "source": source_name if not fallback_point else "fallback-hitbox",
            "minLon": min_lon,
            "minLat": min_lat,
            "maxLon": max_lon,
            "maxLat": max_lat,
            "centerLon": label_point.x,
            "centerLat": label_point.y,
        }
        polygon_features.append({"type": "Feature", "properties": props, "geometry": mapping(geometry)})
        label_features.append(
            {
                "type": "Feature",
                "properties": {
                    "tag": tag,
                    "name": label,
                    "label": label,
                    "labelSize": 12 if tag not in {"GRL"} else 16,
                    "labelRank": 1 if tag in {"LUX", "GRL", "CYP", "DAN"} else 2,
                    "color": props["color"],
                    "ownerTag": tag,
                },
                "geometry": {"type": "Point", "coordinates": [label_point.x, label_point.y]},
            }
        )
        seen.add(tag)

    write_json(MICROSTATES_PATH, {"type": "FeatureCollection", "features": polygon_features})
    write_json(MICROSTATE_LABELS_PATH, {"type": "FeatureCollection", "features": label_features})

    print(f"saved: {MICROSTATES_PATH}")
    print(f"saved: {MICROSTATE_LABELS_PATH}")
    print(f"microstate polygons: {len(polygon_features)}")
    missing_polygons = [feature["properties"]["tag"] for feature in polygon_features if feature["properties"].get("fallbackPoint")]
    if missing_polygons:
        print("fallback hitboxes:", ", ".join(missing_polygons))


if __name__ == "__main__":
    main()
