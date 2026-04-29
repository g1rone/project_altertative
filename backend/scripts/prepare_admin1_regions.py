from __future__ import annotations

import json
import math
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from shapely.geometry import box, mapping
from shapely.ops import unary_union

from cartography_common import (
    BASE_DIR,
    DIAGNOSTICS_DIR,
    EUROPE_MICROSTATE_TAGS,
    PROCESSED_DIR,
    RAW_DIR,
    clean_feature_geometry,
    clean_name,
    ensure_processed_countries,
    feature_bbox,
    fixed_shape,
    is_ugly_label,
    label_size_from_area,
    read_json,
    slug,
    title_case,
    write_json,
)


ADMIN1_SOURCE_PATHS = [
    RAW_DIR / "ne_10m_admin_1_states_provinces.geojson",
    RAW_DIR / "ne_10m_admin_1_states_provinces.json",
    RAW_DIR / "ne_50m_admin_1_states_provinces.geojson",
    RAW_DIR / "ne_50m_admin_1_states_provinces.json",
    RAW_DIR / "geoBoundaries_ADM1.geojson",
    RAW_DIR / "geoboundaries_adm1.geojson",
]
ADMIN1_DOWNLOAD_URL = (
    "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/"
    "geojson/ne_10m_admin_1_states_provinces.geojson"
)
DEFAULT_ADMIN1_PATH = RAW_DIR / "ne_10m_admin_1_states_provinces.geojson"

REGIONS_GEOJSON_PATH = PROCESSED_DIR / "regions_1933.geojson"
REGION_LABELS_PATH = PROCESSED_DIR / "region_label_points_1933.geojson"
REGIONS_JSON_PATH = BASE_DIR / "regions_1933.json"
LEGACY_REGIONS_GEOJSON_PATH = BASE_DIR / "regions_1933.geojson"
DIAGNOSTICS_PATH = DIAGNOSTICS_DIR / "region_diagnostics_1933.json"

ISO_TO_TAG = {
    "DEU": "GER",
    "FRA": "FRA",
    "GBR": "GBR",
    "ITA": "ITA",
    "POL": "POL",
    "RUS": "SOV",
    "SUN": "SOV",
    "ESP": "ESP",
    "TUR": "TUR",
    "USA": "UNI",
    "CAN": "CAN",
    "CHN": "CHI",
    "JPN": "JAP",
    "BRA": "BRA",
    "IND": "IND",
    "AUT": "AUS",
    "CZE": "CZE",
    "HUN": "HUN",
    "ROU": "ROM",
    "BGR": "BUL",
    "GRC": "GRE",
    "IRN": "PER",
    "IRQ": "IRQ",
    "SYR": "SYR",
    "EGY": "EGY",
    "MNG": "MNG",
    "IRL": "IRE",
    "YUG": "YUG",
    "UKR": "SOV",
    "BLR": "SOV",
    "MDA": "SOV",
    "GEO": "SOV",
    "ARM": "SOV",
    "AZE": "SOV",
    "KAZ": "SOV",
    "UZB": "SOV",
    "TKM": "SOV",
    "KGZ": "SOV",
    "TJK": "SOV",
    "KOR": "JAP",
    "PRK": "JAP",
    "PAK": "IND",
    "BGD": "IND",
    "MMR": "GBR",
    "CYP": "CYP",
    "LUX": "LUX",
    "GRL": "GRL",
}

COUNTRY_NAME_TO_TAG = {
    "germany": "GER",
    "france": "FRA",
    "united kingdom": "GBR",
    "italy": "ITA",
    "poland": "POL",
    "russia": "SOV",
    "soviet union": "SOV",
    "ukraine": "SOV",
    "belarus": "SOV",
    "spain": "ESP",
    "turkey": "TUR",
    "united states": "UNI",
    "united states of america": "UNI",
    "canada": "CAN",
    "china": "CHI",
    "japan": "JAP",
    "brazil": "BRA",
    "india": "IND",
    "austria": "AUS",
    "czechoslovakia": "CZE",
    "hungary": "HUN",
    "romania": "ROM",
    "bulgaria": "BUL",
    "greece": "GRE",
    "iran": "PER",
    "iraq": "IRQ",
    "syria": "SYR",
    "egypt": "EGY",
    "mongolia": "MNG",
    "ireland": "IRE",
    "yugoslavia": "YUG",
    "cyprus": "CYP",
    "luxembourg": "LUX",
    "greenland": "GRL",
}

MID_COUNTRIES = {"GER", "POL", "FRA", "ITA", "ESP", "TUR"}
LARGE_COUNTRIES = {"SOV", "CHI", "CHN", "UNI", "USA", "CAN", "BRA", "IND"}
COUNTRY_NAMES = {
    "GER": "Germany",
    "POL": "Poland",
    "FRA": "France",
    "ITA": "Italy",
    "ESP": "Spain",
    "TUR": "Turkey",
    "SOV": "Soviet Union",
    "CHI": "China",
    "CHN": "China",
    "UNI": "United States",
    "USA": "United States",
    "CAN": "Canada",
    "BRA": "Brazil",
    "IND": "India",
}


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    admin1_path = first_existing(ADMIN1_SOURCE_PATHS) or download_admin1_source()
    countries = ensure_processed_countries()
    country_geometries, country_names = build_country_geometries(countries)
    admin1 = read_json(admin1_path)

    grouped: dict[str, list[dict[str, Any]]] = {tag: [] for tag in country_geometries}
    diagnostics: dict[str, Any] = {
        "source": str(admin1_path),
        "loadedAdmin1Features": len(admin1.get("features", [])),
        "matchedAdmin1Features": 0,
        "skippedTinyOrInvalid": 0,
        "countries": {},
    }

    for index, feature in enumerate(admin1.get("features", []), start=1):
        props = feature.get("properties", {})
        tag = admin1_country_tag(props)
        if not tag or tag not in country_geometries:
            continue
        diagnostics["matchedAdmin1Features"] += 1
        if tag in EUROPE_MICROSTATE_TAGS:
            continue

        geometry = fixed_shape(feature.get("geometry"))
        if geometry is None:
            diagnostics["skippedTinyOrInvalid"] += 1
            continue
        clipped = clean_feature_geometry(geometry.intersection(country_geometries[tag]), simplify=0.005)
        if clipped is None or clipped.area < tiny_threshold(country_geometries[tag]):
            diagnostics["skippedTinyOrInvalid"] += 1
            continue

        name = admin1_name(props) or f"{country_names.get(tag, tag)} Region"
        display_name = clean_name(name)
        center = clipped.representative_point()
        grouped.setdefault(tag, []).append(
            {
                "regionId": f"{tag}_{slug(display_name)}_{index:04d}",
                "name": display_name,
                "displayName": display_name,
                "englishName": display_name,
                "ownerTag": tag,
                "countryTag": tag,
                "isGenerated": False,
                "isPlayerVisible": True,
                "centerLon": center.x,
                "centerLat": center.y,
                "labelSize": label_size_from_area(clipped.area, base=10, cap=13),
                "labelRank": 1,
                "aliases": unique_aliases([name, props.get("name_en"), props.get("gn_name")]),
                "source": "natural-earth-admin1" if "ne_" in admin1_path.name else "geoboundaries-adm1",
                "_geometry": clipped,
            }
        )

    output_features: list[dict[str, Any]] = []
    for tag, country_geometry in sorted(country_geometries.items()):
        if tag in EUROPE_MICROSTATE_TAGS:
            continue
        raw_regions = grouped.get(tag, [])
        target_min, target_max = target_range_for_country(tag, country_geometry)
        mode = "admin1"

        if len(raw_regions) > target_max:
            final_regions = grid_aggregate_regions(tag, country_names.get(tag, tag), raw_regions, target_max)
            mode = "grid-aggregate"
        elif len(raw_regions) < target_min and country_geometry.area > 8.0:
            final_regions = grid_split_country(tag, country_names.get(tag, tag), country_geometry, target_min)
            mode = "grid-split"
        elif raw_regions:
            final_regions = raw_regions
        else:
            final_regions = single_country_region(tag, country_names.get(tag, tag), country_geometry)
            mode = "single-country"

        features = [region_feature(region) for region in final_regions]
        output_features.extend(features)
        diagnostics["countries"][tag] = {
            "countryName": country_names.get(tag, tag),
            "inputAdmin1Regions": len(raw_regions),
            "outputRegions": len(features),
            "mode": mode,
            "targetRange": [target_min, target_max],
        }

    regions_json = {
        feature["properties"]["regionId"]: {k: v for k, v in feature["properties"].items() if not k.startswith("_")}
        for feature in output_features
    }
    labels = build_region_label_points(output_features)

    write_json(REGIONS_GEOJSON_PATH, {"type": "FeatureCollection", "features": output_features})
    write_json(REGION_LABELS_PATH, labels)
    write_json(REGIONS_JSON_PATH, {"regions": regions_json})
    write_json(LEGACY_REGIONS_GEOJSON_PATH, {"type": "FeatureCollection", "features": output_features})
    write_json(DIAGNOSTICS_PATH, diagnostics)

    print(f"loaded Admin-1 features: {diagnostics['loadedAdmin1Features']}")
    print(f"matched Admin-1 features: {diagnostics['matchedAdmin1Features']}")
    print(f"created processed regions: {len(output_features)}")
    print(f"saved: {REGIONS_GEOJSON_PATH}")
    print(f"saved: {REGION_LABELS_PATH}")
    print(f"saved diagnostics: {DIAGNOSTICS_PATH}")
    for tag in ["GER", "POL", "FRA", "ITA", "ESP", "TUR", "SOV", "CHI", "UNI", "CAN", "BRA", "IND"]:
        if tag in diagnostics["countries"]:
            print(f"{tag}: {diagnostics['countries'][tag]['outputRegions']} regions ({diagnostics['countries'][tag]['mode']})")


def first_existing(paths: list[Path]) -> Path | None:
    return next((path for path in paths if path.exists()), None)


def download_admin1_source() -> Path:
    print("Admin-1 source missing. Attempting auto-download:")
    print(f"  {ADMIN1_DOWNLOAD_URL}")
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    try:
        with urllib.request.urlopen(ADMIN1_DOWNLOAD_URL, timeout=90) as response:
            DEFAULT_ADMIN1_PATH.write_bytes(response.read())
    except (urllib.error.URLError, TimeoutError) as exc:
        raise RuntimeError(
            "Admin-1 source missing. Put ne_10m_admin_1_states_provinces.geojson into backend/data/raw "
            "or allow auto-download."
        ) from exc
    print(f"Downloaded Admin-1 source: {DEFAULT_ADMIN1_PATH}")
    return DEFAULT_ADMIN1_PATH


def build_country_geometries(countries: dict[str, Any]) -> tuple[dict[str, Any], dict[str, str]]:
    grouped: dict[str, list[Any]] = {}
    names: dict[str, str] = {}
    for feature in countries.get("features", []):
        props = feature.get("properties", {})
        tag = props.get("tag")
        geometry = fixed_shape(feature.get("geometry"))
        if tag and geometry is not None and not geometry.is_empty:
            grouped.setdefault(tag, []).append(geometry)
            names.setdefault(tag, str(props.get("displayName") or props.get("name") or tag))

    result = {}
    for tag, geometries in grouped.items():
        geometry = clean_feature_geometry(unary_union(geometries), simplify=0.003)
        if geometry is not None and not geometry.is_empty:
            result[tag] = geometry
    return result, names


def admin1_country_tag(props: dict[str, Any]) -> str | None:
    candidates = [
        props.get("adm0_a3"),
        props.get("iso_a3"),
        props.get("iso_a2"),
        props.get("gu_a3"),
        props.get("sr_adm0_a3"),
        props.get("shapeGroup"),
    ]
    for value in candidates:
        if not value:
            continue
        normalized = str(value).upper()
        if normalized in ISO_TO_TAG:
            return ISO_TO_TAG[normalized]
        if len(normalized) == 3:
            return normalized
    for key in ["admin", "geonunit", "sovereign", "adm0_name", "shapeGroup"]:
        value = props.get(key)
        if not value:
            continue
        tag = COUNTRY_NAME_TO_TAG.get(str(value).lower())
        if tag:
            return tag
    return None


def admin1_name(props: dict[str, Any]) -> str | None:
    for key in ["name", "name_en", "name_local", "gn_name", "region", "shapeName"]:
        value = props.get(key)
        if value:
            return str(value)
    return None


def target_range_for_country(tag: str, geometry: Any) -> tuple[int, int]:
    if tag in MID_COUNTRIES:
        return 8, 25
    if tag in LARGE_COUNTRIES:
        return 25, 80
    area = geometry.area
    if area > 900:
        return 18, 55
    if area > 160:
        return 8, 24
    if area > 30:
        return 4, 12
    return 1, 5


def tiny_threshold(country_geometry: Any) -> float:
    return max(country_geometry.area * 0.00003, 0.002)


def desired_grid_dimensions(bounds: tuple[float, float, float, float], target: int) -> tuple[int, int]:
    minx, miny, maxx, maxy = bounds
    width = max(maxx - minx, 0.1)
    height = max(maxy - miny, 0.1)
    aspect = width / height
    columns = max(1, round(math.sqrt(target * aspect)))
    rows = max(1, math.ceil(target / columns))
    return columns, rows


def directional_name(country_name: str, lon: float, lat: float, bounds: tuple[float, float, float, float]) -> str:
    minx, miny, maxx, maxy = bounds
    x = (lon - minx) / max(maxx - minx, 0.1)
    y = (lat - miny) / max(maxy - miny, 0.1)
    vertical = "Northern" if y > 0.66 else "Southern" if y < 0.34 else "Central"
    horizontal = "Western" if x < 0.34 else "Eastern" if x > 0.66 else ""
    if vertical == "Central" and horizontal:
        return f"{horizontal} {country_name}"
    if horizontal:
        return f"{vertical} {horizontal} {country_name}"
    return f"{vertical} {country_name}"


def grid_split_country(tag: str, country_name: str, country_geometry: Any, target: int) -> list[dict[str, Any]]:
    bounds = country_geometry.bounds
    columns, rows = desired_grid_dimensions(bounds, target)
    minx, miny, maxx, maxy = bounds
    cell_width = (maxx - minx) / columns
    cell_height = (maxy - miny) / rows
    regions: list[dict[str, Any]] = []

    for row in range(rows):
        for column in range(columns):
            cell = box(
                minx + column * cell_width,
                miny + row * cell_height,
                minx + (column + 1) * cell_width,
                miny + (row + 1) * cell_height,
            )
            clipped = clean_feature_geometry(country_geometry.intersection(cell), simplify=0.003)
            if clipped is None or clipped.area < tiny_threshold(country_geometry):
                continue
            center = clipped.representative_point()
            name = directional_name(COUNTRY_NAMES.get(tag, country_name), center.x, center.y, bounds)
            regions.append(region_record(tag, name, clipped, "natural-earth-admin1-grid-split", len(regions) + 1))

    return regions or single_country_region(tag, country_name, country_geometry)


def grid_aggregate_regions(tag: str, country_name: str, regions: list[dict[str, Any]], target_max: int) -> list[dict[str, Any]]:
    combined = unary_union([region["_geometry"] for region in regions])
    bounds = combined.bounds
    columns, rows = desired_grid_dimensions(bounds, target_max)
    minx, miny, maxx, maxy = bounds
    cell_width = (maxx - minx) / columns
    cell_height = (maxy - miny) / rows
    buckets: dict[tuple[int, int], list[Any]] = {}

    for region in regions:
        center = region["_geometry"].representative_point()
        column = min(columns - 1, max(0, int((center.x - minx) / max(cell_width, 0.0001))))
        row = min(rows - 1, max(0, int((center.y - miny) / max(cell_height, 0.0001))))
        buckets.setdefault((column, row), []).append(region["_geometry"])

    output: list[dict[str, Any]] = []
    for (column, row), geometries in sorted(buckets.items(), key=lambda item: (item[0][1], item[0][0])):
        geometry = clean_feature_geometry(unary_union(geometries), simplify=0.003)
        if geometry is None or geometry.area < 0.003:
            continue
        center = geometry.representative_point()
        name = directional_name(COUNTRY_NAMES.get(tag, country_name), center.x, center.y, bounds)
        output.append(region_record(tag, name, geometry, "natural-earth-admin1-grid-aggregate", len(output) + 1))

    if len(output) > target_max:
        output = merge_smallest_regions(tag, COUNTRY_NAMES.get(tag, country_name), output, target_max)
    return output or regions[:target_max]


def merge_smallest_regions(tag: str, country_name: str, regions: list[dict[str, Any]], target_max: int) -> list[dict[str, Any]]:
    merged = list(regions)
    while len(merged) > target_max:
        smallest_index = min(range(len(merged)), key=lambda index: merged[index]["_geometry"].area)
        smallest = merged.pop(smallest_index)
        center = smallest["_geometry"].representative_point()
        nearest_index = min(
            range(len(merged)),
            key=lambda index: center.distance(merged[index]["_geometry"].representative_point()),
        )
        combined = clean_feature_geometry(unary_union([smallest["_geometry"], merged[nearest_index]["_geometry"]]), simplify=0.003)
        if combined is None:
            continue
        combined_center = combined.representative_point()
        name = directional_name(country_name, combined_center.x, combined_center.y, combined.bounds)
        merged[nearest_index] = region_record(tag, name, combined, "natural-earth-admin1-grid-aggregate", nearest_index + 1)

    for index, region in enumerate(merged, start=1):
        region["regionId"] = f"{tag}_{slug(region['displayName'])}_{index:03d}"
    return merged


def single_country_region(tag: str, country_name: str, geometry: Any) -> list[dict[str, Any]]:
    return [region_record(tag, country_name, geometry, "country-geometry-single", 1)]


def region_record(tag: str, name: str, geometry: Any, source: str, index: int) -> dict[str, Any]:
    display_name = clean_name(name)
    center = geometry.representative_point()
    return {
        "regionId": f"{tag}_{slug(display_name)}_{index:03d}",
        "name": display_name,
        "displayName": display_name,
        "englishName": display_name,
        "ownerTag": tag,
        "countryTag": tag,
        "isGenerated": source != "natural-earth-admin1",
        "isPlayerVisible": True,
        "centerLon": center.x,
        "centerLat": center.y,
        "labelSize": label_size_from_area(geometry.area, base=10, cap=13),
        "labelRank": 1,
        "aliases": unique_aliases([display_name]),
        "source": source,
        "_geometry": geometry,
    }


def region_feature(region: dict[str, Any]) -> dict[str, Any]:
    geometry = region["_geometry"]
    props = {k: v for k, v in region.items() if k != "_geometry"}
    min_lon, min_lat, max_lon, max_lat = feature_bbox(geometry)
    props.update({"minLon": min_lon, "minLat": min_lat, "maxLon": max_lon, "maxLat": max_lat})
    return {"type": "Feature", "properties": props, "geometry": mapping(geometry)}


def build_region_label_points(features: list[dict[str, Any]]) -> dict[str, Any]:
    label_features = []
    for feature in features:
        props = feature.get("properties", {})
        label = clean_name(props.get("displayName") or props.get("name") or "")
        if is_ugly_label(label):
            continue
        geometry = fixed_shape(feature.get("geometry"))
        if geometry is None or geometry.area < 0.01:
            continue
        point = geometry.representative_point()
        label_features.append(
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
    return {"type": "FeatureCollection", "features": label_features}


def unique_aliases(values: list[Any]) -> list[str]:
    aliases = []
    for value in values:
        if not value:
            continue
        text = str(value)
        if text not in aliases:
            aliases.append(text)
    return aliases


if __name__ == "__main__":
    main()
