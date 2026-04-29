from __future__ import annotations

import hashlib
import json
import math
import re
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Iterable

from shapely.geometry import GeometryCollection, MultiPolygon, Polygon, mapping, shape
from shapely.ops import unary_union
from shapely.validation import make_valid


BACKEND_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BACKEND_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
BASE_DIR = DATA_DIR / "base"
PROCESSED_DIR = DATA_DIR / "processed"
DIAGNOSTICS_DIR = DATA_DIR / "diagnostics"
TILES_DIR = DATA_DIR / "tiles"

STATE_PATH = DATA_DIR / "game_state_1933.json"
BASE_COUNTRIES_PATH = BASE_DIR / "countries_1933.geojson"
BASE_MAP_PATH = DATA_DIR / "europe_1933.geojson"
PROCESSED_COUNTRIES_PATH = PROCESSED_DIR / "countries_1933.geojson"

ADMIN0_SOURCE_PATHS = [
    RAW_DIR / "ne_10m_admin_0_map_units.geojson",
    RAW_DIR / "ne_10m_admin_0_countries.geojson",
    RAW_DIR / "ne_10m_admin_0_sovereignty.geojson",
    RAW_DIR / "ne_10m_admin_0_subunits.geojson",
    RAW_DIR / "ne_50m_admin_0_map_units.geojson",
    RAW_DIR / "ne_50m_admin_0_countries.geojson",
]
ADMIN0_DOWNLOAD_URL = (
    "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/"
    "geojson/ne_10m_admin_0_map_units.geojson"
)
DEFAULT_ADMIN0_PATH = RAW_DIR / "ne_10m_admin_0_map_units.geojson"

LABEL_NAMES = {
    "GER": "GERMANY",
    "SOV": "SOVIET UNION",
    "GBR": "UNITED KINGDOM",
    "FRA": "FRANCE",
    "ITA": "ITALY",
    "POL": "POLAND",
    "ESP": "SPAIN",
    "TUR": "TURKEY",
    "USA": "UNITED STATES",
    "UNI": "UNITED STATES",
    "CHI": "CHINA",
    "CHN": "CHINA",
    "JAP": "JAPAN",
    "MNG": "MONGOLIA",
    "CAN": "CANADA",
    "BRA": "BRAZIL",
    "IND": "INDIA",
}

NAME_TAG_OVERRIDES = {
    "united states of america": "UNI",
    "united states": "UNI",
    "united arab emirates": "UAE",
    "free city of danzig": "DAN",
    "danzig": "DAN",
    "mongolia": "MNG",
    "austria": "AUS",
    "australia": "AST",
    "belize": "BLZ",
    "belgium": "BEL",
    "cameroon": "CMR",
    "cambodia (kampuchea)": "KHM",
    "chile": "CHL",
    "china": "CHI",
    "congo": "COG",
    "congo, democratic republic of (zaire)": "COD",
    "french guyana": "GUF",
    "french polynesia": "PYF",
    "guadeloupe": "GLP",
    "guatemala": "GUA",
    "guinea-bissau": "GNB",
    "guinea": "GIN",
    "india": "IND",
    "indonesia": "IDN",
    "italy/sardinia": "ITA",
    "italian somaliland": "ITA_SOM",
    "liberia": "LBR",
    "libya": "LBY",
    "malta": "MLT",
    "mali": "MLI",
    "malawi": "MWI",
    "maldives": "MDV",
    "mauritania": "MRT",
    "mauritius": "MUS",
    "newfoundland": "NFL",
    "new guinea (german new guinea) (kaiser wilhelmsland)": "PNG",
    "new zealand": "NZL",
    "new caledonia and dependencies": "NCL",
    "niger": "NER",
    "nigeria": "NGA",
    "south africa": "SAF",
    "southern sakhalin island": "SAK",
    "spanish morocco": "ESM",
    "spanish west africa": "ESW",
    "british togoland": "GBR_TOG",
    "british cameroons": "GBR_CMR",
    "british somaliland (somaliland republic)": "GBR_SOM",
}

OWNER_TAG_BY_NAME = {
    "alaska": "UNI",
    "hawaii": "UNI",
    "puerto rico": "UNI",
    "philippines": "UNI",
    "bahamas": "GBR",
    "jamaica": "GBR",
    "trinidad and tobago": "GBR",
    "barbados": "GBR",
    "belize": "GBR",
    "guyana": "GBR",
    "gambia": "GBR",
    "sierra leone": "GBR",
    "ghana": "GBR",
    "nigeria": "GBR",
    "kenya": "GBR",
    "uganda": "GBR",
    "tanzania (tanganyika)": "GBR",
    "zanzibar": "GBR",
    "british togoland": "GBR",
    "british cameroons": "GBR",
    "british somaliland (somaliland republic)": "GBR",
    "sudan": "GBR",
    "palestine": "GBR",
    "jordan": "GBR",
    "cyprus": "GBR",
    "malta": "GBR",
    "sri lanka (ceylon)": "GBR",
    "federated malay states": "GBR",
    "unfederated malay states": "GBR",
    "sabah (north borneo)": "GBR",
    "sarawak": "GBR",
    "straits settlements": "GBR",
    "brunei": "GBR",
    "fiji": "GBR",
    "solomon islands": "GBR",
    "guadeloupe": "FRA",
    "martinique": "FRA",
    "french guyana": "FRA",
    "french polynesia": "FRA",
    "inini": "FRA",
    "algeria": "FRA",
    "tunisia": "FRA",
    "morocco": "FRA",
    "senegal": "FRA",
    "benin": "FRA",
    "mauritania": "FRA",
    "niger": "FRA",
    "cote d'ivoire": "FRA",
    "guinea": "FRA",
    "mali": "FRA",
    "cameroon": "FRA",
    "togo": "FRA",
    "gabon": "FRA",
    "central african republic": "FRA",
    "chad": "FRA",
    "congo": "FRA",
    "madagascar (malagasy)": "FRA",
    "reunion": "FRA",
    "djibouti": "FRA",
    "syria": "FRA",
    "lebanon": "FRA",
    "cambodia (kampuchea)": "FRA",
    "laos": "FRA",
    "vietnam (annam/cochin china/tonkin)": "FRA",
    "eritrea": "ITA",
    "libya": "ITA",
    "italian somaliland": "ITA",
    "spanish morocco": "ESP",
    "spanish west africa": "ESP",
    "equatorial guinea": "ESP",
    "cape verde": "POR",
    "guinea-bissau": "POR",
    "angola": "POR",
    "mozambique": "POR",
    "east timor": "POR",
    "congo, democratic republic of (zaire)": "BEL",
    "rwanda-urundi": "BEL",
    "surinam": "NLD",
    "indonesia": "NLD",
    "taiwan": "JAP",
    "korea": "JAP",
    "southern sakhalin island": "JAP",
    "papua": "AST",
    "new guinea (german new guinea) (kaiser wilhelmsland)": "AST",
    "new caledonia and dependencies": "FRA",
    "greenland": "DEN",
}

COLONY_REASON_BY_NAME = {
    name: "detached territory / colony / non-mainland"
    for name in OWNER_TAG_BY_NAME
}

NON_LABEL_OWNER_TAGS = {"AND", "MCO", "LIE", "SMR", "VAT", "LUX", "DAN", "DNZ", "MLT"}

MICROSTATE_TARGETS = {
    "AND": {"label": "Andorra", "names": ["andorra"]},
    "MCO": {"label": "Monaco", "names": ["monaco"]},
    "LIE": {"label": "Liechtenstein", "names": ["liechtenstein"]},
    "SMR": {"label": "San Marino", "names": ["san marino"]},
    "VAT": {"label": "Vatican", "names": ["vatican", "vatican city"]},
    "LUX": {"label": "Luxembourg", "names": ["luxembourg"]},
    "DAN": {"label": "Danzig", "names": ["danzig", "free city of danzig"]},
    "DNZ": {"label": "Danzig", "names": ["danzig", "free city of danzig"]},
    "MLT": {"label": "Malta", "names": ["malta"]},
    "GRL": {"label": "Greenland", "names": ["greenland"]},
    "CYP": {"label": "Cyprus", "names": ["cyprus"]},
}

EUROPE_MICROSTATE_TAGS = {"AND", "MCO", "LIE", "SMR", "VAT", "LUX", "DAN", "DNZ", "MLT"}


def read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def load_state_countries() -> dict[str, dict[str, Any]]:
    if not STATE_PATH.exists():
        return {}
    return read_json(STATE_PATH).get("countries", {})


def stable_color(tag: str) -> str:
    digest = hashlib.sha256(tag.encode("utf-8")).hexdigest()
    palette = ["#64748b", "#2563eb", "#16a34a", "#dc2626", "#f59e0b", "#7c3aed", "#0891b2", "#be123c"]
    return palette[int(digest[:2], 16) % len(palette)]


def country_color(tag: str, state_countries: dict[str, dict[str, Any]] | None = None) -> str:
    state_countries = state_countries if state_countries is not None else load_state_countries()
    country = state_countries.get(tag)
    return str(country.get("color")) if country and country.get("color") else stable_color(tag)


def country_display_name(tag: str, name: str) -> str:
    normalized = name.strip()
    if normalized.lower() in {"united states of america", "united states"}:
        return "United States"
    return LABEL_NAMES.get(tag, normalized.upper()).title() if not normalized else normalized


def label_for_country(tag: str, name: str) -> str:
    normalized = name.strip().lower()
    if normalized in {"united states of america", "united states"}:
        return "UNITED STATES"
    if normalized == "united arab emirates":
        return "UNITED ARAB EMIRATES"
    return LABEL_NAMES.get(tag, name.upper())


def normalized_country_tag(original_tag: str, name: str) -> str:
    normalized_name = name.strip().lower()
    override = NAME_TAG_OVERRIDES.get(normalized_name)
    if override:
        return override
    return original_tag


def territory_classification(tag: str, original_tag: str, name: str, geometry: Any) -> dict[str, Any]:
    normalized_name = name.strip().lower()
    owner_tag = OWNER_TAG_BY_NAME.get(normalized_name, tag)
    is_colony = owner_tag != tag
    is_detached = is_colony
    is_mainland = not is_colony
    is_label_eligible = is_mainland and tag not in NON_LABEL_OWNER_TAGS
    reason = "" if is_label_eligible else COLONY_REASON_BY_NAME.get(normalized_name, "small state / non-main country label")

    return {
        "originalTag": original_tag,
        "ownerTag": owner_tag,
        "controllerTag": owner_tag,
        "sovereignTag": owner_tag,
        "labelOwnerTag": owner_tag,
        "isMainland": is_mainland,
        "isColony": is_colony,
        "isDetachedTerritory": is_detached,
        "isLabelEligible": is_label_eligible,
        "territoryReason": reason,
        "area": float(geometry.area) if geometry is not None else 0.0,
    }


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
        geometry = polygonal_only(geometry)
        return geometry if geometry is not None and not geometry.is_empty else None
    except Exception:
        return None


def polygonal_only(geometry: Any) -> Any | None:
    if geometry is None or geometry.is_empty:
        return None
    if isinstance(geometry, (Polygon, MultiPolygon)):
        return geometry
    if isinstance(geometry, GeometryCollection):
        polygons = [part for part in geometry.geoms if isinstance(part, (Polygon, MultiPolygon)) and not part.is_empty]
        if not polygons:
            return None
        return unary_union(polygons)
    return None


def largest_polygon(geometry: Any) -> Polygon | None:
    geometry = polygonal_only(geometry)
    if geometry is None or geometry.is_empty:
        return None
    if isinstance(geometry, Polygon):
        return geometry
    polygons = list(geometry.geoms)
    return max(polygons, key=lambda item: item.area) if polygons else None


def clean_feature_geometry(geometry: Any, *, simplify: float = 0.0) -> Any | None:
    geometry = fixed_geometry(geometry)
    if geometry is None:
        return None
    if simplify > 0:
        geometry = geometry.simplify(simplify, preserve_topology=True)
        geometry = fixed_geometry(geometry)
    return geometry


def slug(value: str, fallback: str = "REGION") -> str:
    asciiish = re.sub(r"[^A-Za-z0-9]+", "_", value.upper()).strip("_")
    return asciiish[:44] or fallback


def title_case(value: str) -> str:
    words = re.split(r"(\s+|-)", value.replace("_", " ").strip())
    return "".join(word.capitalize() if word.isalpha() else word for word in words)


def clean_name(value: Any) -> str:
    if not value:
        return ""
    text = str(value).strip()
    text = re.sub(r"\s+", " ", text)
    return title_case(text)


def is_ugly_label(value: str) -> bool:
    if not value:
        return True
    text = value.strip()
    upper = text.upper()
    if len(text) > 34:
        return True
    if "_STATE_" in upper or upper.startswith("TAG_"):
        return True
    if re.fullmatch(r"[A-Z]{2,4}[_-]?[0-9]{2,4}", upper):
        return True
    return False


def first_existing(paths: Iterable[Path]) -> Path | None:
    return next((path for path in paths if path.exists()), None)


def download_file(url: str, path: Path, label: str) -> Path:
    print(f"{label} source missing. Attempting auto-download:")
    print(f"  {url}")
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with urllib.request.urlopen(url, timeout=90) as response:
            path.write_bytes(response.read())
    except (urllib.error.URLError, TimeoutError) as exc:
        raise RuntimeError(f"{label} source missing and auto-download failed. Put the file into {RAW_DIR}.") from exc
    print(f"Downloaded {label} source: {path}")
    return path


def find_admin0_source() -> Path:
    return first_existing(ADMIN0_SOURCE_PATHS) or download_file(ADMIN0_DOWNLOAD_URL, DEFAULT_ADMIN0_PATH, "Natural Earth Admin-0")


def property_names(properties: dict[str, Any]) -> list[str]:
    keys = ["NAME", "NAME_EN", "ADMIN", "SOVEREIGNT", "GEOUNIT", "NAME_LONG", "BRK_NAME", "SUBUNIT", "FORMAL_EN"]
    return [str(properties.get(key, "")) for key in keys if properties.get(key)]


def find_named_feature(collection: dict[str, Any], names: list[str], tags: list[str] | None = None) -> dict[str, Any] | None:
    lowered_names = [name.lower() for name in names]
    tags = tags or []
    for feature in collection.get("features", []):
        props = feature.get("properties", {})
        haystack = " | ".join(property_names(props)).lower()
        candidate_tags = {
            str(props.get(key, "")).upper()
            for key in ["ADM0_A3", "ISO_A3", "SU_A3", "GU_A3", "SOV_A3", "BRK_A3"]
            if props.get(key)
        }
        if any(tag in candidate_tags for tag in tags) or any(name in haystack for name in lowered_names):
            if feature.get("geometry"):
                return feature
    return None


def feature_bbox(geometry: Any) -> tuple[float, float, float, float]:
    minx, miny, maxx, maxy = geometry.bounds
    return float(minx), float(miny), float(maxx), float(maxy)


def bbox_dimensions(geometry: Any) -> tuple[float, float]:
    minx, miny, maxx, maxy = geometry.bounds
    return maxx - minx, maxy - miny


def line_length_degrees(geometry: Any) -> float:
    try:
        return float(geometry.length)
    except Exception:
        return 0.0


def label_size_from_area(area: float, *, base: float = 12.0, cap: float = 27.0) -> float:
    return round(max(base, min(cap, base + math.sqrt(max(area, 0.0)) * 0.7)), 2)


def ensure_processed_countries() -> dict[str, Any]:
    source_path = BASE_COUNTRIES_PATH if BASE_COUNTRIES_PATH.exists() else BASE_MAP_PATH
    if not source_path.exists():
        raise FileNotFoundError("Missing country source: backend/data/base/countries_1933.geojson")

    state_countries = load_state_countries()
    countries = read_json(source_path)
    features: list[dict[str, Any]] = []
    territory_diagnostics: list[dict[str, Any]] = []

    for feature in countries.get("features", []):
        props = feature.get("properties", {})
        name = str(props.get("name") or props.get("displayName") or props.get("tag") or "Unknown")
        original_tag = str(props.get("tag") or "UNK")
        tag = normalized_country_tag(original_tag, name)
        geometry = clean_feature_geometry(fixed_shape(feature.get("geometry")), simplify=0.01)
        if geometry is None:
            continue
        classification = territory_classification(tag, original_tag, name, geometry)
        owner_tag = str(props.get("ownerTag") or classification["ownerTag"])
        classification["ownerTag"] = owner_tag
        classification["controllerTag"] = str(props.get("controllerTag") or props.get("ownerTag") or classification["controllerTag"])
        classification["sovereignTag"] = str(props.get("sovereignTag") or classification["sovereignTag"])
        classification["labelOwnerTag"] = str(props.get("labelOwnerTag") or classification["labelOwnerTag"])
        min_lon, min_lat, max_lon, max_lat = feature_bbox(geometry)
        out_props = {
            "tag": tag,
            "originalTag": original_tag,
            "name": name,
            "displayName": country_display_name(tag, name),
            "ownerTag": classification["ownerTag"],
            "controllerTag": classification["controllerTag"],
            "sovereignTag": classification["sovereignTag"],
            "labelOwnerTag": classification["labelOwnerTag"],
            "isMainland": classification["isMainland"],
            "isColony": classification["isColony"],
            "isDetachedTerritory": classification["isDetachedTerritory"],
            "isLabelEligible": classification["isLabelEligible"],
            "territoryReason": classification["territoryReason"],
            "color": country_color(classification["ownerTag"], state_countries),
            "isMicrostate": bool(props.get("isMicrostate")) or tag in EUROPE_MICROSTATE_TAGS,
            "smallCountry": bool(props.get("smallCountry")) or geometry.area < 2.0,
            "minLon": min_lon,
            "minLat": min_lat,
            "maxLon": max_lon,
            "maxLat": max_lat,
            "centerLon": (min_lon + max_lon) / 2,
            "centerLat": (min_lat + max_lat) / 2,
            "source": props.get("source") or "cshapes-1933",
        }
        features.append({"type": "Feature", "properties": out_props, "geometry": mapping(geometry)})
        if classification["isDetachedTerritory"] or not classification["isLabelEligible"]:
            territory_diagnostics.append(
                {
                    "tag": tag,
                    "originalTag": original_tag,
                    "name": name,
                    "ownerTag": classification["ownerTag"],
                    "labelOwnerTag": classification["labelOwnerTag"],
                    "isDetachedTerritory": classification["isDetachedTerritory"],
                    "isColony": classification["isColony"],
                    "isMainland": classification["isMainland"],
                    "isLabelEligible": classification["isLabelEligible"],
                    "reason": classification["territoryReason"],
                    "bounds": [min_lon, min_lat, max_lon, max_lat],
                    "area": round(float(geometry.area), 6),
                }
            )

    admin0 = read_json(find_admin0_source())
    existing_tags = {feature["properties"]["tag"] for feature in features}
    for tag, spec in MICROSTATE_TARGETS.items():
        canonical = "DAN" if tag == "DNZ" else tag
        if canonical in existing_tags and canonical != "DAN":
            continue
        if canonical == "DAN" and any(feature["properties"]["tag"] == "DAN" for feature in features):
            continue
        source_feature = find_named_feature(admin0, spec["names"], [canonical])
        if not source_feature:
            continue
        geometry = clean_feature_geometry(fixed_shape(source_feature.get("geometry")), simplify=0.002)
        if geometry is None:
            continue
        name = spec["label"]
        classification = territory_classification(canonical, canonical, name, geometry)
        min_lon, min_lat, max_lon, max_lat = feature_bbox(geometry)
        features.append(
            {
                "type": "Feature",
                "properties": {
                    "tag": canonical,
                    "originalTag": canonical,
                    "name": name,
                    "displayName": name,
                    "ownerTag": classification["ownerTag"],
                    "controllerTag": classification["controllerTag"],
                    "sovereignTag": classification["sovereignTag"],
                    "labelOwnerTag": classification["labelOwnerTag"],
                    "isMainland": classification["isMainland"],
                    "isColony": classification["isColony"],
                    "isDetachedTerritory": classification["isDetachedTerritory"],
                    "isLabelEligible": classification["isLabelEligible"],
                    "territoryReason": classification["territoryReason"],
                    "color": country_color(classification["ownerTag"], state_countries),
                    "isMicrostate": canonical in EUROPE_MICROSTATE_TAGS,
                    "smallCountry": geometry.area < 8.0,
                    "minLon": min_lon,
                    "minLat": min_lat,
                    "maxLon": max_lon,
                    "maxLat": max_lat,
                    "centerLon": (min_lon + max_lon) / 2,
                    "centerLat": (min_lat + max_lat) / 2,
                    "source": "natural-earth-admin0",
                },
                "geometry": mapping(geometry),
            }
        )
        if classification["isDetachedTerritory"] or not classification["isLabelEligible"]:
            territory_diagnostics.append(
                {
                    "tag": canonical,
                    "originalTag": canonical,
                    "name": name,
                    "ownerTag": classification["ownerTag"],
                    "labelOwnerTag": classification["labelOwnerTag"],
                    "isDetachedTerritory": classification["isDetachedTerritory"],
                    "isColony": classification["isColony"],
                    "isMainland": classification["isMainland"],
                    "isLabelEligible": classification["isLabelEligible"],
                    "reason": classification["territoryReason"],
                    "bounds": [min_lon, min_lat, max_lon, max_lat],
                    "area": round(float(geometry.area), 6),
                }
            )
        existing_tags.add(canonical)

    processed = {"type": "FeatureCollection", "features": features}
    write_json(PROCESSED_COUNTRIES_PATH, processed)
    write_json(
        DIAGNOSTICS_DIR / "territory_diagnostics_1933.json",
        {
            "source": str(source_path),
            "features": territory_diagnostics,
        },
    )
    return processed
