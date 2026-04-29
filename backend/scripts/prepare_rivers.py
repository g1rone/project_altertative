from __future__ import annotations

import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from shapely.geometry import LineString, MultiLineString, mapping, shape

from cartography_common import PROCESSED_DIR, RAW_DIR, read_json, write_json


RIVER_SOURCE_PATHS = [
    RAW_DIR / "ne_10m_rivers_lake_centerlines.geojson",
    RAW_DIR / "ne_10m_rivers_lake_centerlines.json",
    RAW_DIR / "ne_50m_rivers_lake_centerlines.geojson",
    RAW_DIR / "ne_50m_rivers_lake_centerlines.json",
]
RIVER_DOWNLOAD_URL = (
    "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/"
    "geojson/ne_10m_rivers_lake_centerlines.geojson"
)
DEFAULT_RIVER_PATH = RAW_DIR / "ne_10m_rivers_lake_centerlines.geojson"
RIVERS_OUT_PATH = PROCESSED_DIR / "rivers_1933.geojson"


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    source_path = first_existing(RIVER_SOURCE_PATHS) or download_river_source()
    source = read_json(source_path)
    features: list[dict[str, Any]] = []

    for feature in source.get("features", []):
        props = feature.get("properties", {})
        scalerank = as_int(props.get("scalerank"), 99)
        name = river_name(props)
        if scalerank > 6 and not name:
            continue

        geometry = line_geometry(feature.get("geometry"))
        if geometry is None:
            continue
        if geometry.length < 3.0 and scalerank > 4:
            continue

        simplify = 0.025 if scalerank <= 3 else 0.04
        geometry = geometry.simplify(simplify, preserve_topology=True)
        if geometry.is_empty:
            continue
        importance = river_importance(scalerank, geometry.length)
        width_class = river_width_class(importance)

        features.append(
            {
                "type": "Feature",
                "properties": {
                    "name": name,
                    "rank": scalerank,
                    "scalerank": scalerank,
                    "importance": importance,
                    "widthClass": width_class,
                    "minZoom": river_min_zoom(width_class),
                    "source": "natural-earth-rivers-lake-centerlines",
                },
                "geometry": mapping(geometry),
            }
        )

    write_json(RIVERS_OUT_PATH, {"type": "FeatureCollection", "features": features})
    print(f"loaded river features: {len(source.get('features', []))}")
    print(f"saved major rivers: {len(features)}")
    print(f"saved: {RIVERS_OUT_PATH}")


def first_existing(paths: list[Path]) -> Path | None:
    return next((path for path in paths if path.exists()), None)


def download_river_source() -> Path:
    print("Natural Earth rivers source missing. Attempting auto-download:")
    print(f"  {RIVER_DOWNLOAD_URL}")
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    try:
        with urllib.request.urlopen(RIVER_DOWNLOAD_URL, timeout=90) as response:
            DEFAULT_RIVER_PATH.write_bytes(response.read())
    except (urllib.error.URLError, TimeoutError) as exc:
        raise RuntimeError(
            "Natural Earth rivers source missing. Put ne_10m_rivers_lake_centerlines.geojson into backend/data/raw "
            "or allow auto-download."
        ) from exc
    print(f"Downloaded rivers source: {DEFAULT_RIVER_PATH}")
    return DEFAULT_RIVER_PATH


def line_geometry(geometry: dict[str, Any] | None) -> LineString | MultiLineString | None:
    if not geometry:
        return None
    try:
        parsed = shape(geometry)
    except Exception:
        return None
    if isinstance(parsed, (LineString, MultiLineString)) and not parsed.is_empty:
        return parsed
    return None


def river_name(props: dict[str, Any]) -> str:
    for key in ["name", "name_en", "NAME", "name_alt"]:
        value = props.get(key)
        if value:
            return str(value)
    return ""


def as_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def river_importance(scalerank: int, length: float) -> int:
    if scalerank <= 3 or length >= 45:
        return 3
    if scalerank <= 5 or length >= 18:
        return 2
    return 1


def river_width_class(importance: int) -> int:
    return max(1, min(3, importance))


def river_min_zoom(width_class: int) -> float:
    if width_class >= 3:
        return 3.4
    if width_class == 2:
        return 4.2
    return 5.0


if __name__ == "__main__":
    main()
