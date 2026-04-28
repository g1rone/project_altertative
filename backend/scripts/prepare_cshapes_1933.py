from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any


BACKEND_DIR = Path(__file__).resolve().parents[1]
RAW_PATH = BACKEND_DIR / "data" / "raw" / "CShapes-2.0.geojson"
OUT_PATH = BACKEND_DIR / "data" / "europe_1933.geojson"
TARGET_DATE = date(1933, 1, 1)
REGION_MODE = "world"
EUROPE_BBOX = (-15.0, 33.0, 65.0, 72.0)
MICROSTATE_MAX_BBOX_WIDTH = 1.0
MICROSTATE_MAX_BBOX_HEIGHT = 1.0
SMALL_COUNTRY_MAX_BBOX_AREA = 4.0

GWCODE_TO_TAG = {
    200: "GBR",
    205: "IRE",
    210: "NLD",
    211: "BEL",
    212: "LUX",
    220: "FRA",
    225: "SWI",
    230: "ESP",
    235: "POR",
    255: "GER",
    290: "POL",
    305: "AUS",
    310: "HUN",
    315: "CZE",
    325: "ITA",
    339: "ALB",
    345: "YUG",
    350: "GRE",
    355: "BUL",
    360: "ROM",
    365: "SOV",
    366: "EST",
    367: "LAT",
    368: "LIT",
    375: "FIN",
    380: "SWE",
    385: "NOR",
    390: "DEN",
    395: "ICE",
    640: "TUR",
    630: "IRN",
    645: "IRQ",
    651: "EGY",
    652: "SYR",
    660: "LEB",
}


def main() -> None:
    if not RAW_PATH.exists():
        raise FileNotFoundError(f"CShapes file not found: {RAW_PATH}")

    with RAW_PATH.open("r", encoding="utf-8") as f:
        source = json.load(f)

    prepared_features = []
    for feature in source.get("features", []):
        properties = feature.get("properties", {})
        geometry = feature.get("geometry")

        if not geometry:
            continue
        if not is_active_on(properties, TARGET_DATE):
            continue

        bbox = geometry_bbox(geometry)
        if bbox is None:
            continue
        if not is_in_region(bbox):
            continue

        gwcode = as_int(properties.get("gwcode"))
        name = str(properties.get("cntry_name") or f"GW {gwcode}")
        tag = tag_for_country(gwcode, name)
        min_lon, min_lat, max_lon, max_lat = bbox
        bbox_width = max_lon - min_lon
        bbox_height = max_lat - min_lat
        bbox_area = bbox_width * bbox_height
        is_microstate = (
            bbox_width <= MICROSTATE_MAX_BBOX_WIDTH
            and bbox_height <= MICROSTATE_MAX_BBOX_HEIGHT
        )
        small_country = is_microstate or bbox_area <= SMALL_COUNTRY_MAX_BBOX_AREA

        prepared_features.append(
            {
                "type": "Feature",
                "properties": {
                    "tag": tag,
                    "name": name,
                    "isMicrostate": is_microstate,
                    "smallCountry": small_country,
                    "minLon": min_lon,
                    "minLat": min_lat,
                    "maxLon": max_lon,
                    "maxLat": max_lat,
                    "centerLon": (min_lon + max_lon) / 2,
                    "centerLat": (min_lat + max_lat) / 2,
                },
                "geometry": geometry,
            }
        )

    prepared = {
        "type": "FeatureCollection",
        "features": prepared_features,
    }

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUT_PATH.open("w", encoding="utf-8") as f:
        json.dump(prepared, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print(f"saved: {OUT_PATH}")
    print(f"region mode: {REGION_MODE}")
    print(f"features: {len(prepared_features)}")
    print("tags:")
    for tag in sorted({feature["properties"]["tag"] for feature in prepared_features}):
        print(f"- {tag}")


def is_active_on(properties: dict[str, Any], target: date) -> bool:
    start = parse_cshapes_date(
        properties,
        date_field="gwsdate",
        year_field="gwsyear",
        month_field="gwsmonth",
        day_field="gwsday",
        default=date.min,
    )
    end = parse_cshapes_date(
        properties,
        date_field="gwedate",
        year_field="gweyear",
        month_field="gwemonth",
        day_field="gweday",
        default=date.max,
    )

    return start <= target <= end


def is_in_region(bbox: tuple[float, float, float, float]) -> bool:
    if REGION_MODE == "world":
        return True
    if REGION_MODE == "europe":
        return intersects_bbox(bbox, EUROPE_BBOX)
    raise ValueError(f"Unsupported REGION_MODE: {REGION_MODE}")


def parse_cshapes_date(
    properties: dict[str, Any],
    *,
    date_field: str,
    year_field: str,
    month_field: str,
    day_field: str,
    default: date,
) -> date:
    raw_date = properties.get(date_field)
    parsed = parse_raw_date(raw_date)
    if parsed is not None:
        return parsed

    year = as_int(properties.get(year_field))
    if year is None or year <= 0:
        return default

    month = as_int(properties.get(month_field)) or 1
    day = as_int(properties.get(day_field)) or 1
    return date(year, max(1, month), max(1, day))


def parse_raw_date(value: Any) -> date | None:
    if value in (None, "", 0, -9, "0", "-9"):
        return None

    text = str(value).strip()
    if not text:
        return None

    for separator in ("-", "/", "."):
        if separator in text:
            parts = text.split(separator)
            if len(parts) >= 3:
                year, month, day = (as_int(part) for part in parts[:3])
                if year and month and day:
                    return date(year, month, day)

    if len(text) == 8 and text.isdigit():
        return date(int(text[:4]), int(text[4:6]), int(text[6:8]))

    return None


def intersects_bbox(
    geom_bbox: tuple[float, float, float, float],
    bbox: tuple[float, float, float, float],
) -> bool:
    min_lon, min_lat, max_lon, max_lat = geom_bbox
    bbox_min_lon, bbox_min_lat, bbox_max_lon, bbox_max_lat = bbox
    return not (
        max_lon < bbox_min_lon
        or min_lon > bbox_max_lon
        or max_lat < bbox_min_lat
        or min_lat > bbox_max_lat
    )


def geometry_bbox(geometry: dict[str, Any]) -> tuple[float, float, float, float] | None:
    points = list(iter_points(geometry.get("coordinates")))
    if not points:
        return None

    lon_values = [point[0] for point in points]
    lat_values = [point[1] for point in points]
    return min(lon_values), min(lat_values), max(lon_values), max(lat_values)


def iter_points(coordinates: Any):
    if not isinstance(coordinates, list):
        return
    if len(coordinates) >= 2 and all(isinstance(value, (int, float)) for value in coordinates[:2]):
        yield float(coordinates[0]), float(coordinates[1])
        return
    for item in coordinates:
        yield from iter_points(item)


def tag_for_country(gwcode: int | None, name: str) -> str:
    if gwcode in GWCODE_TO_TAG:
        return GWCODE_TO_TAG[gwcode]

    letters = "".join(char for char in name.upper() if "A" <= char <= "Z")
    return letters[:3] or f"GW{gwcode or 'UNK'}"


def as_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


if __name__ == "__main__":
    main()
