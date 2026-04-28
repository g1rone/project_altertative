from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

try:
    from shapely.geometry import mapping, shape
    from shapely.ops import unary_union
    from shapely.validation import make_valid

    HAS_SHAPELY = True
except ImportError:
    HAS_SHAPELY = False


BACKEND_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BACKEND_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
BASE_DIR = DATA_DIR / "base"

COUNTRIES_PATHS = [
    BASE_DIR / "countries_1933.geojson",
    DATA_DIR / "europe_1933.geojson",
]
ADMIN1_SOURCE_PATHS = [
    RAW_DIR / "ne_10m_admin_1_states_provinces.geojson",
    RAW_DIR / "ne_10m_admin_1_states_provinces.json",
    RAW_DIR / "ne_50m_admin_1_states_provinces.geojson",
    RAW_DIR / "ne_50m_admin_1_states_provinces.json",
    RAW_DIR / "geoBoundaries_ADM1.geojson",
    RAW_DIR / "geoboundaries_adm1.geojson",
]
REGIONS_GEOJSON_PATH = BASE_DIR / "regions_1933.geojson"
REGIONS_JSON_PATH = BASE_DIR / "regions_1933.json"

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
    "USA": "USA",
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
}


def main() -> None:
    BASE_DIR.mkdir(parents=True, exist_ok=True)
    countries_path = first_existing(COUNTRIES_PATHS)
    admin1_path = first_existing(ADMIN1_SOURCE_PATHS)

    if not admin1_path:
        print("No Admin-1 GeoJSON source found in backend/data/raw.")
        print("Expected one of:")
        for path in ADMIN1_SOURCE_PATHS:
            print(f"  - {path.name}")
        print("Writing empty safe region layer; no rough rectangles will be rendered.")
        write_outputs([], {})
        return

    if not countries_path:
        raise FileNotFoundError("Missing CShapes country map: countries_1933.geojson or europe_1933.geojson")

    if not HAS_SHAPELY:
        print("Shapely is not available, so Admin-1 clipping cannot run safely.")
        print("Writing empty safe region layer; no fake polygons will be rendered.")
        write_outputs([], {})
        return

    countries = read_json(countries_path)
    admin1 = read_json(admin1_path)
    country_geometries = build_country_geometries(countries)
    features = []
    countries_matched: set[str] = set()
    sample_names: dict[str, list[str]] = {}

    for index, feature in enumerate(admin1.get("features", []), start=1):
        props = feature.get("properties", {})
        tag = admin1_country_tag(props)
        if not tag or tag not in country_geometries:
            continue

        region_geometry = fixed_shape(feature.get("geometry"))
        if region_geometry is None:
            continue

        clipped = fixed_geometry(region_geometry.intersection(country_geometries[tag]))
        if clipped is None or clipped.is_empty or clipped.area < 0.01:
            continue

        name = admin1_name(props) or f"{tag} Region {index:03d}"
        region_id = f"{tag}_{slug(name)}_{index:03d}"
        center = clipped.representative_point()
        region_props = {
            "regionId": region_id,
            "name": name,
            "displayName": name,
            "englishName": name,
            "ownerTag": tag,
            "countryTag": tag,
            "isGenerated": False,
            "isPlayerVisible": True,
            "centerLon": center.x,
            "centerLat": center.y,
            "labelSize": 12,
            "labelRank": 1,
            "aliases": unique_aliases([name, props.get("name_en"), props.get("gn_name")]),
            "source": "natural-earth-admin1" if "ne_" in admin1_path.name else "geoboundaries-adm1",
        }
        features.append(
            {
                "type": "Feature",
                "properties": region_props,
                "geometry": mapping(clipped),
            }
        )
        countries_matched.add(tag)
        sample_names.setdefault(tag, []).append(name)

    regions = {feature["properties"]["regionId"]: feature["properties"] for feature in features}
    write_outputs(features, regions)

    print(f"Loaded Admin-1 features: {len(admin1.get('features', []))}")
    print(f"Created clipped region features: {len(features)}")
    print(f"Countries matched: {len(countries_matched)}")
    missing = sorted(set(country_geometries) - countries_matched)
    print(f"Countries without regions: {len(missing)}")
    if missing:
        print("First missing countries:", ", ".join(missing[:30]))
    for tag in ["GER", "POL", "FRA", "ITA", "SOV"]:
        names = sample_names.get(tag, [])[:20]
        print(f"{tag} regions:", ", ".join(names) if names else "(none)")


def first_existing(paths: list[Path]) -> Path | None:
    return next((path for path in paths if path.exists()), None)


def read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def write_outputs(features: list[dict[str, Any]], regions: dict[str, Any]) -> None:
    write_json(REGIONS_GEOJSON_PATH, {"type": "FeatureCollection", "features": features})
    write_json(REGIONS_JSON_PATH, {"regions": regions})


def build_country_geometries(countries: dict[str, Any]) -> dict[str, Any]:
    grouped: dict[str, list[Any]] = {}
    for feature in countries.get("features", []):
        tag = feature.get("properties", {}).get("tag")
        geometry = fixed_shape(feature.get("geometry"))
        if tag and geometry is not None and not geometry.is_empty:
            grouped.setdefault(tag, []).append(geometry)

    result = {}
    for tag, geometries in grouped.items():
        geometry = fixed_geometry(unary_union(geometries))
        if geometry is not None and not geometry.is_empty:
            result[tag] = geometry
    return result


def admin1_country_tag(props: dict[str, Any]) -> str | None:
    candidates = [
        props.get("adm0_a3"),
        props.get("iso_a3"),
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
    return None


def admin1_name(props: dict[str, Any]) -> str | None:
    for key in ["name", "name_en", "gn_name", "region", "shapeName"]:
        value = props.get(key)
        if value:
            return str(value)
    return None


def fixed_shape(geometry: dict[str, Any] | None) -> Any | None:
    if not geometry:
        return None
    try:
        return fixed_geometry(shape(geometry))
    except Exception:
        return None


def fixed_geometry(geometry: Any) -> Any | None:
    if geometry is None or geometry.is_empty:
        return None
    try:
        if not geometry.is_valid:
            geometry = make_valid(geometry)
        if not geometry.is_valid:
            geometry = geometry.buffer(0)
        return geometry if not geometry.is_empty else None
    except Exception:
        return None


def slug(value: str) -> str:
    asciiish = re.sub(r"[^A-Za-z0-9]+", "_", value.upper()).strip("_")
    return asciiish[:36] or "REGION"


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
