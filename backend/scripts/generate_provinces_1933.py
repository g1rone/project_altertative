from __future__ import annotations

import hashlib
import json
import math
import shutil
from pathlib import Path
from typing import Any

try:
    from shapely.geometry import box, mapping, shape
    from shapely.ops import unary_union
    from shapely.validation import make_valid

    HAS_SHAPELY = True
except ImportError:
    HAS_SHAPELY = False


BACKEND_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BACKEND_DIR / "data"
BASE_DIR = DATA_DIR / "base"
SAVE_DIR = DATA_DIR / "save"

COUNTRIES_PATH = BASE_DIR / "countries_1933.geojson"
SOURCE_COUNTRIES_PATH = DATA_DIR / "europe_1933.geojson"
PROVINCES_PATH = BASE_DIR / "provinces_1933.geojson"
REGIONS_PATH = BASE_DIR / "regions_1933.json"
ADJACENCY_PATH = BASE_DIR / "province_adjacency_1933.json"
CAMPAIGN_PATH = SAVE_DIR / "campaign_state.json"
STATE_PATHS = [
    DATA_DIR / "game_state_1933.json",
    DATA_DIR / "game_state_1933.initial.json",
]

IMPORTANT_TERRITORIES = [
    "Greenland",
    "Andorra",
    "Monaco",
    "Liechtenstein",
    "San Marino",
    "Vatican",
    "Malta",
    "Danzig",
]

FALLBACK_COUNTRIES = [
    ("GRL", "Greenland", (-73.5, 59.8, -12.0, 83.7)),
    ("AND", "Andorra", (1.4, 42.4, 1.8, 42.7)),
    ("MCO", "Monaco", (7.38, 43.72, 7.45, 43.76)),
    ("LIE", "Liechtenstein", (9.47, 47.05, 9.65, 47.27)),
    ("SMR", "San Marino", (12.38, 43.88, 12.55, 44.0)),
    ("VAT", "Vatican", (12.44, 41.9, 12.46, 41.91)),
]

SPECIAL_REGIONS = [
    {
        "regionId": "GER_RHINELAND",
        "tag": "GER",
        "name": "Rhineland",
        "displayName": "Рейнская область",
        "aliases": [
            "Рейнская область",
            "Рейнланд",
            "Rhineland",
            "рейнскую область",
            "демилитаризованная зона",
        ],
        "bbox": (5.5, 49.0, 8.5, 52.5),
    },
    {
        "regionId": "GER_BAVARIA",
        "tag": "GER",
        "name": "Bavaria",
        "displayName": "Бавария",
        "aliases": ["Бавария", "Баварию", "Bavaria"],
        "bbox": (9.0, 47.0, 13.8, 50.8),
    },
    {
        "regionId": "GER_SAXONY",
        "tag": "GER",
        "name": "Saxony",
        "displayName": "Саксония",
        "aliases": ["Саксония", "Саксонию", "Saxony"],
        "bbox": (11.5, 50.0, 15.2, 52.0),
    },
    {
        "regionId": "GER_EAST_PRUSSIA",
        "tag": "GER",
        "name": "East Prussia",
        "displayName": "Восточная Пруссия",
        "aliases": ["Восточная Пруссия", "Восточную Пруссию", "East Prussia"],
        "bbox": (19.0, 53.0, 23.5, 55.5),
    },
    {
        "regionId": "POL_DANZIG",
        "tag": "POL",
        "name": "Danzig",
        "displayName": "Данциг",
        "aliases": ["Данциг", "Danzig"],
        "bbox": (18.3, 53.8, 19.3, 54.8),
    },
    {
        "regionId": "FRA_ALSACE_LORRAINE",
        "tag": "FRA",
        "name": "Alsace-Lorraine",
        "displayName": "Эльзас-Лотарингия",
        "aliases": ["Эльзас-Лотарингия", "Эльзас", "Alsace-Lorraine"],
        "bbox": (6.5, 47.3, 8.5, 49.5),
    },
    {
        "regionId": "SOV_UKRAINE",
        "tag": "SOV",
        "name": "Ukraine",
        "displayName": "Украина",
        "aliases": ["Украина", "Украину", "Ukraine"],
        "bbox": (22.0, 44.0, 41.0, 53.0),
    },
    {
        "regionId": "ITA_LOMBARDY",
        "tag": "ITA",
        "name": "Lombardy",
        "displayName": "Ломбардия",
        "aliases": ["Ломбардия", "Ломбардию", "Lombardy"],
        "bbox": (8.5, 44.7, 11.5, 46.8),
    },
    {
        "regionId": "GBR_ENGLAND",
        "tag": "GBR",
        "name": "England",
        "displayName": "Англия",
        "aliases": ["Англия", "Англию", "England"],
        "bbox": (-6.5, 49.5, 2.5, 56.0),
    },
    {
        "regionId": "TUR_ANATOLIA",
        "tag": "TUR",
        "name": "Anatolia",
        "displayName": "Анатолия",
        "aliases": ["Анатолия", "Анатолию", "Anatolia"],
        "bbox": (25.0, 35.0, 45.0, 42.5),
    },
]


def main() -> None:
    BASE_DIR.mkdir(parents=True, exist_ok=True)
    SAVE_DIR.mkdir(parents=True, exist_ok=True)

    if not COUNTRIES_PATH.exists():
        shutil.copyfile(SOURCE_COUNTRIES_PATH, COUNTRIES_PATH)

    with COUNTRIES_PATH.open("r", encoding="utf-8") as f:
        countries = json.load(f)
    add_fallback_countries(countries)

    provinces: list[dict[str, Any]] = []
    regions: dict[str, dict[str, Any]] = {}
    countries_without_provinces: list[str] = []
    tag_counts: dict[str, int] = {}
    raw_cells_created = 0
    discarded_empty = 0
    discarded_tiny = 0
    bbox_warnings: list[str] = []

    for country in countries.get("features", []):
        props = country.get("properties", {})
        geometry = normalize_geometry(country.get("geometry"))
        bbox = geometry_bbox(geometry)
        tag = str(props.get("tag") or "UNK")
        name = str(props.get("name") or tag)

        if not geometry or not bbox:
            countries_without_provinces.append(tag)
            continue

        province_geometries, stats = generate_country_province_geometries(tag, bbox, geometry, props)
        raw_cells_created += stats["raw_cells"]
        discarded_empty += stats["discarded_empty"]
        discarded_tiny += stats["discarded_tiny"]

        if not province_geometries:
            countries_without_provinces.append(tag)
            continue

        for province_geometry in province_geometries:
            tag_counts[tag] = tag_counts.get(tag, 0) + 1
            index = tag_counts[tag]
            province_id = f"{tag}_{index:03d}"
            province_bbox = geometry_bbox(province_geometry) or bbox
            center_lon, center_lat = bbox_center(province_bbox)
            region_seed = region_for_cell(tag, center_lon, center_lat)
            region_id = region_seed["regionId"] if region_seed else generated_region_id(tag, index)
            display_name = f"{name} {index}"
            province_area = bbox_area(province_bbox)

            if bbox_exceeds(province_bbox, bbox, tolerance=0.5):
                bbox_warnings.append(province_id)

            provinces.append(
                {
                    "type": "Feature",
                    "properties": {
                        "provinceId": province_id,
                        "regionId": region_id,
                        "originalCountryTag": tag,
                        "ownerTag": tag,
                        "controllerTag": tag,
                        "name": display_name,
                        "displayName": display_name,
                        "terrain": "plains",
                        "centerLon": center_lon,
                        "centerLat": center_lat,
                        "areaApprox": province_area,
                        "isMicroProvince": province_area < 1.0,
                    },
                    "geometry": province_geometry,
                }
            )

            region = regions.setdefault(
                region_id,
                make_region(region_id, tag, region_seed, center_lon, center_lat),
            )
            region["provinceIds"].append(province_id)

    for region in regions.values():
        region_provinces = [
            province
            for province in provinces
            if province["properties"]["provinceId"] in region["provinceIds"]
        ]
        center_lon, center_lat = average_centers(region_provinces)
        region["centerLon"] = center_lon
        region["centerLat"] = center_lat

    adjacency = build_adjacency(provinces)
    campaign_state = build_campaign_state(provinces)
    if CAMPAIGN_PATH.exists():
        campaign_state = merge_existing_campaign_state(campaign_state)

    write_json(PROVINCES_PATH, {"type": "FeatureCollection", "features": provinces})
    write_json(REGIONS_PATH, {"regions": regions})
    write_json(ADJACENCY_PATH, adjacency)
    write_json(CAMPAIGN_PATH, campaign_state)
    update_game_states(provinces, countries)

    country_names = [feature.get("properties", {}).get("name", "") for feature in countries.get("features", [])]
    missing_important = [
        name
        for name in IMPORTANT_TERRITORIES
        if not any(name.lower() in str(country_name).lower() for country_name in country_names)
    ]

    print(f"countries read: {len(countries.get('features', []))}")
    print(f"raw cells created: {raw_cells_created}")
    print(f"provinces created: {len(provinces)}")
    print(f"discarded empty cells: {discarded_empty}")
    print(f"discarded tiny cells: {discarded_tiny}")
    print(f"regions created: {len(regions)}")
    print(f"adjacency links created: {sum(len(v) for v in adjacency.values()) // 2}")
    print(f"countries without provinces: {countries_without_provinces}")
    print(f"important missing territories: {missing_important}")
    if bbox_warnings:
        print(f"warning: province bbox outside source bbox: {bbox_warnings[:20]}")


def generate_country_province_geometries(
    tag: str,
    bbox: tuple[float, float, float, float],
    geometry: dict[str, Any],
    props: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    if not HAS_SHAPELY:
        return [geometry], {"raw_cells": 0, "discarded_empty": 0, "discarded_tiny": 0}

    country_shape = fix_shape(shape(geometry))
    if country_shape.is_empty:
        return [], {"raw_cells": 0, "discarded_empty": 1, "discarded_tiny": 0}

    min_lon, min_lat, max_lon, max_lat = bbox
    width = max_lon - min_lon
    height = max_lat - min_lat
    area = float(props.get("area") or 0)
    bbox_size = max(width * height, 0.01)

    if props.get("isMicrostate") or props.get("smallCountry") or bbox_size < 2:
        return [mapping(country_shape)], {"raw_cells": 0, "discarded_empty": 0, "discarded_tiny": 0}

    target = province_target_count(tag, area, bbox_size)
    cols = max(1, round(math.sqrt(target * max(width / max(height, 0.1), 0.2))))
    rows = max(1, math.ceil(target / cols))

    provinces: list[dict[str, Any]] = []
    raw_cells = 0
    discarded_empty_count = 0
    discarded_tiny_count = 0
    for row in range(rows):
        for col in range(cols):
            raw_cells += 1
            cell = (
                min_lon + width * col / cols,
                min_lat + height * row / rows,
                min_lon + width * (col + 1) / cols,
                min_lat + height * (row + 1) / rows,
            )
            clipped = fix_shape(country_shape.intersection(box(*cell)))
            if clipped.is_empty:
                discarded_empty_count += 1
                continue
            if clipped.area < max(country_shape.area * 0.0005, 0.00001):
                discarded_tiny_count += 1
                continue
            polygonal = polygonal_geometry(clipped)
            if polygonal is None:
                discarded_empty_count += 1
                continue
            provinces.append(mapping(polygonal))

    if not provinces:
        provinces = [mapping(country_shape)]

    return provinces, {
        "raw_cells": raw_cells,
        "discarded_empty": discarded_empty_count,
        "discarded_tiny": discarded_tiny_count,
    }


def fix_shape(geometry: Any) -> Any:
    if geometry.is_valid:
        return geometry
    try:
        return make_valid(geometry)
    except Exception:
        return geometry.buffer(0)


def polygonal_geometry(geometry: Any) -> Any | None:
    if geometry.geom_type in {"Polygon", "MultiPolygon"}:
        return geometry
    if geometry.geom_type == "GeometryCollection":
        parts = [
            part
            for part in geometry.geoms
            if part.geom_type in {"Polygon", "MultiPolygon"} and not part.is_empty
        ]
        if not parts:
            return None
        return parts[0] if len(parts) == 1 else fix_shape(unary_union(parts))
    return None


def add_fallback_countries(countries: dict[str, Any]) -> None:
    features = countries.setdefault("features", [])
    existing_names = {
        str(feature.get("properties", {}).get("name", "")).lower()
        for feature in features
    }
    existing_tags = {
        str(feature.get("properties", {}).get("tag", "")).upper()
        for feature in features
    }

    for tag, name, bbox in FALLBACK_COUNTRIES:
        if any(name.lower() in existing for existing in existing_names):
            continue
        features.append(
            {
                "type": "Feature",
                "properties": {
                    "tag": tag,
                    "name": name,
                    "isMicrostate": bbox_area(bbox) < 1,
                    "smallCountry": bbox_area(bbox) < 4,
                },
                "geometry": bbox_polygon(bbox),
            }
        )


def province_target_count(tag: str, area: float, bbox_size: float) -> int:
    if tag in {"SOV", "UNI", "CHI", "IND", "CAN", "BRA"}:
        return 36
    if area > 4_000_000 or bbox_size > 1_500:
        return 30
    if area > 1_000_000 or bbox_size > 500:
        return 18
    if area > 250_000 or bbox_size > 120:
        return 10
    if area > 75_000 or bbox_size > 30:
        return 6
    if area > 20_000 or bbox_size > 8:
        return 3
    return 1


def region_for_cell(tag: str, lon: float, lat: float) -> dict[str, Any] | None:
    for region in SPECIAL_REGIONS:
        min_lon, min_lat, max_lon, max_lat = region["bbox"]
        if region["tag"] == tag and min_lon <= lon <= max_lon and min_lat <= lat <= max_lat:
            return region
    return None


def generated_region_id(tag: str, province_index: int) -> str:
    return f"{tag}_STATE_{((province_index - 1) // 4) + 1:03d}"


def make_region(
    region_id: str,
    tag: str,
    seed: dict[str, Any] | None,
    center_lon: float,
    center_lat: float,
) -> dict[str, Any]:
    name = seed["name"] if seed else region_id.replace("_", " ").title()
    display_name = seed["displayName"] if seed else name
    aliases = seed["aliases"] if seed else [display_name, name]
    return {
        "regionId": region_id,
        "name": name,
        "displayName": display_name,
        "aliases": aliases,
        "originalCountryTag": tag,
        "ownerTag": tag,
        "provinceIds": [],
        "centerLon": center_lon,
        "centerLat": center_lat,
        "labelSize": 13,
        "labelRank": 1,
        "resources": {"steel": 0, "coal": 0, "oil": 0},
        "buildingSlots": 3,
        "victoryPoints": 0,
    }


def build_adjacency(provinces: list[dict[str, Any]]) -> dict[str, list[str]]:
    bboxes = {
        province["properties"]["provinceId"]: geometry_bbox(province["geometry"])
        for province in provinces
    }
    adjacency = {province["properties"]["provinceId"]: [] for province in provinces}
    ids = list(adjacency)

    for index, left_id in enumerate(ids):
        left_bbox = bboxes[left_id]
        if left_bbox is None:
            continue
        for right_id in ids[index + 1 :]:
            right_bbox = bboxes[right_id]
            if right_bbox is None:
                continue
            if bboxes_touch_or_near(left_bbox, right_bbox):
                adjacency[left_id].append(right_id)
                adjacency[right_id].append(left_id)

    return {key: sorted(value) for key, value in adjacency.items()}


def build_campaign_state(provinces: list[dict[str, Any]]) -> dict[str, Any]:
    ownership = {
        province["properties"]["provinceId"]: {
            "ownerTag": province["properties"]["ownerTag"],
            "controllerTag": province["properties"]["controllerTag"],
        }
        for province in provinces
    }
    divisions: dict[str, dict[str, Any]] = {}
    by_owner: dict[str, list[str]] = {}
    for province_id, owner in ownership.items():
        by_owner.setdefault(owner["ownerTag"], []).append(province_id)

    for tag in sorted(by_owner):
        for index, province_id in enumerate(by_owner[tag][:3], start=1):
            divisions[f"{tag}_DIV_{index:03d}"] = {
                "id": f"{tag}_DIV_{index:03d}",
                "ownerTag": tag,
                "provinceId": province_id,
                "strength": 100,
                "organization": 80,
                "movementTarget": None,
            }

    return {
        "year": 1933,
        "turn": 1,
        "provinceOwnership": ownership,
        "divisions": divisions,
        "visualOrders": [],
        "events": [],
    }


def merge_existing_campaign_state(default_state: dict[str, Any]) -> dict[str, Any]:
    with CAMPAIGN_PATH.open("r", encoding="utf-8") as f:
        existing = json.load(f)

    default_state["year"] = existing.get("year", default_state["year"])
    default_state["turn"] = existing.get("turn", default_state["turn"])
    default_state["events"] = existing.get("events", [])
    default_state["visualOrders"] = existing.get("visualOrders", [])
    default_state["divisions"].update(existing.get("divisions", {}))
    default_state["provinceOwnership"].update(existing.get("provinceOwnership", {}))
    return default_state


def update_game_states(provinces: list[dict[str, Any]], countries: dict[str, Any]) -> None:
    names = {
        feature.get("properties", {}).get("tag"): feature.get("properties", {}).get("name")
        for feature in countries.get("features", [])
    }
    tags = sorted({province["properties"]["ownerTag"] for province in provinces})

    for path in STATE_PATHS:
        if not path.exists():
            continue
        with path.open("r", encoding="utf-8") as f:
            state = json.load(f)
        country_state = state.setdefault("countries", {})
        for tag in tags:
            country_state.setdefault(
                tag,
                {
                    "tag": tag,
                    "name": names.get(tag) or tag,
                    "color": stable_color(tag),
                    "ideology": "unknown",
                    "stability": 50,
                    "economy": 40,
                    "military": 30,
                    "legitimacy": 50,
                },
            )
        write_json(path, state)


def stable_color(tag: str) -> str:
    digest = hashlib.sha256(tag.encode("utf-8")).hexdigest()
    hue = int(digest[:2], 16)
    palette = [
        "#64748b",
        "#2563eb",
        "#16a34a",
        "#dc2626",
        "#f59e0b",
        "#7c3aed",
        "#0891b2",
        "#be123c",
    ]
    return palette[hue % len(palette)]


def normalize_geometry(geometry: dict[str, Any] | None) -> dict[str, Any] | None:
    if not geometry:
        return None
    normalized = json.loads(json.dumps(geometry))
    normalize_coordinates(normalized.get("coordinates"))
    return normalized


def normalize_coordinates(coordinates: Any) -> None:
    if not isinstance(coordinates, list):
        return
    if len(coordinates) >= 2 and all(isinstance(value, (int, float)) for value in coordinates[:2]):
        lon = float(coordinates[0])
        if lon > 180:
            lon -= 360
        if lon < -180:
            lon += 360
        coordinates[0] = lon
        coordinates[1] = float(coordinates[1])
        return
    for item in coordinates:
        normalize_coordinates(item)


def point_in_geometry(lon: float, lat: float, geometry: dict[str, Any]) -> bool:
    geom_type = geometry.get("type")
    coordinates = geometry.get("coordinates", [])
    if geom_type == "Polygon":
        return point_in_polygon(lon, lat, coordinates)
    if geom_type == "MultiPolygon":
        return any(point_in_polygon(lon, lat, polygon) for polygon in coordinates)
    return False


def point_in_polygon(lon: float, lat: float, polygon: list[Any]) -> bool:
    if not polygon:
        return False
    ring = polygon[0]
    inside = False
    j = len(ring) - 1
    for i, point in enumerate(ring):
        xi, yi = point[:2]
        xj, yj = ring[j][:2]
        intersects = (yi > lat) != (yj > lat) and lon < (xj - xi) * (lat - yi) / ((yj - yi) or 1e-9) + xi
        if intersects:
            inside = not inside
        j = i
    return inside


def geometry_bbox(geometry: dict[str, Any] | None) -> tuple[float, float, float, float] | None:
    if not geometry:
        return None
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


def bbox_polygon(bbox: tuple[float, float, float, float]) -> dict[str, Any]:
    min_lon, min_lat, max_lon, max_lat = bbox
    return {
        "type": "Polygon",
        "coordinates": [
            [
                [min_lon, min_lat],
                [max_lon, min_lat],
                [max_lon, max_lat],
                [min_lon, max_lat],
                [min_lon, min_lat],
            ]
        ],
    }


def bbox_center(bbox: tuple[float, float, float, float]) -> tuple[float, float]:
    min_lon, min_lat, max_lon, max_lat = bbox
    return (min_lon + max_lon) / 2, (min_lat + max_lat) / 2


def bbox_area(bbox: tuple[float, float, float, float]) -> float:
    min_lon, min_lat, max_lon, max_lat = bbox
    return max(0.0, max_lon - min_lon) * max(0.0, max_lat - min_lat)


def bbox_intersects(
    left: tuple[float, float, float, float],
    right: tuple[float, float, float, float],
) -> bool:
    left_min_lon, left_min_lat, left_max_lon, left_max_lat = left
    right_min_lon, right_min_lat, right_max_lon, right_max_lat = right
    return not (
        left_max_lon < right_min_lon
        or left_min_lon > right_max_lon
        or left_max_lat < right_min_lat
        or left_min_lat > right_max_lat
    )


def bbox_exceeds(
    inner: tuple[float, float, float, float],
    outer: tuple[float, float, float, float],
    *,
    tolerance: float,
) -> bool:
    return (
        inner[0] < outer[0] - tolerance
        or inner[1] < outer[1] - tolerance
        or inner[2] > outer[2] + tolerance
        or inner[3] > outer[3] + tolerance
    )


def bboxes_touch_or_near(
    left: tuple[float, float, float, float],
    right: tuple[float, float, float, float],
) -> bool:
    gap_lon = max(left[0] - right[2], right[0] - left[2], 0)
    gap_lat = max(left[1] - right[3], right[1] - left[3], 0)
    return gap_lon <= 0.25 and gap_lat <= 0.25


def average_centers(provinces: list[dict[str, Any]]) -> tuple[float, float]:
    if not provinces:
        return 0.0, 0.0
    lon = sum(province["properties"]["centerLon"] for province in provinces) / len(provinces)
    lat = sum(province["properties"]["centerLat"] for province in provinces) / len(provinces)
    return lon, lat


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


if __name__ == "__main__":
    main()
