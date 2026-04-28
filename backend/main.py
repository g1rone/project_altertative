from __future__ import annotations

import json
import hashlib
from pathlib import Path
from typing import Any, Dict, List

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
BASE_DATA_DIR = DATA_DIR / "base"
SAVE_DATA_DIR = DATA_DIR / "save"
STATE_PATH = DATA_DIR / "game_state_1933.json"
MAP_PATH = DATA_DIR / "europe_1933.geojson"
BASE_PROVINCES_PATH = BASE_DATA_DIR / "provinces_1933.geojson"
BASE_REGIONS_PATH = BASE_DATA_DIR / "regions_1933.json"
PROVINCE_ADJACENCY_PATH = BASE_DATA_DIR / "province_adjacency_1933.json"
CAMPAIGN_STATE_PATH = SAVE_DATA_DIR / "campaign_state.json"


app = FastAPI(title="Pax 1933 Backend", version="0.1.0")

# На старте разрешаем локальный frontend Vite.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class CountryState(BaseModel):
    tag: str
    name: str
    color: str
    ideology: str
    stability: int = Field(ge=0, le=100)
    economy: int = Field(ge=0, le=100)
    military: int = Field(ge=0, le=100)
    legitimacy: int = Field(ge=0, le=100)


class Event(BaseModel):
    turn: int
    actor: str
    action: str
    action_class: str
    summary: str
    effects: Dict[str, int]


class GameState(BaseModel):
    year: int
    turn: int
    countries: Dict[str, CountryState]
    events: List[Event]


class TurnRequest(BaseModel):
    actor: str
    action: str


class TurnResponse(BaseModel):
    state: GameState
    event: Event


class TransferProvincesRequest(BaseModel):
    provinceIds: List[str]
    newOwner: str


class MoveDivisionRequest(BaseModel):
    divisionId: str
    toProvinceId: str


class ParseOrderRequest(BaseModel):
    actorTag: str
    text: str


class ExecuteOrderRequest(BaseModel):
    type: str
    actorTag: str
    divisionCount: int = 1
    targetRegionId: str | None = None


def load_state() -> GameState:
    if not STATE_PATH.exists():
        raise HTTPException(status_code=500, detail="game_state_1933.json not found")

    with STATE_PATH.open("r", encoding="utf-8") as f:
        raw = json.load(f)

    return GameState.model_validate(raw)


def save_state(state: GameState) -> None:
    with STATE_PATH.open("w", encoding="utf-8") as f:
        json.dump(state.model_dump(), f, ensure_ascii=False, indent=2)


def read_json(path: Path) -> Any:
    if not path.exists():
        raise HTTPException(status_code=500, detail=f"Missing data file: {path.name}")
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def load_base_provinces() -> dict:
    return read_json(BASE_PROVINCES_PATH)


def load_regions() -> dict:
    return read_json(BASE_REGIONS_PATH)


def load_province_adjacency() -> dict[str, list[str]]:
    return read_json(PROVINCE_ADJACENCY_PATH)


def load_campaign_state() -> dict:
    return read_json(CAMPAIGN_STATE_PATH)


def save_campaign_state(campaign_state: dict) -> None:
    write_json(CAMPAIGN_STATE_PATH, campaign_state)


def apply_campaign_ownership_to_provinces() -> dict:
    provinces = load_base_provinces()
    campaign_state = load_campaign_state()
    ownership = campaign_state.get("provinceOwnership", {})
    features = []

    for feature in provinces.get("features", []):
        copied = json.loads(json.dumps(feature))
        props = copied.setdefault("properties", {})
        province_id = props.get("provinceId")
        current = ownership.get(province_id, {})
        props["ownerTag"] = current.get("ownerTag", props.get("ownerTag"))
        props["controllerTag"] = current.get("controllerTag", props.get("controllerTag"))
        props["color"] = country_color(props["ownerTag"])
        features.append(copied)

    return {"type": "FeatureCollection", "features": features}


def build_current_countries_from_provinces() -> dict:
    provinces = apply_campaign_ownership_to_provinces()
    if province_data_looks_rectangular(provinces):
        return color_country_features(read_json(MAP_PATH))

    state = load_state()
    grouped: dict[str, list[dict]] = {}

    for province in provinces.get("features", []):
        owner = province.get("properties", {}).get("ownerTag", "UNK")
        grouped.setdefault(owner, []).append(province)

    features = []
    for tag, owned_provinces in sorted(grouped.items()):
        country_state = state.countries.get(tag)
        geometries = [province["geometry"] for province in owned_provinces if province.get("geometry")]
        if not geometries:
            continue
        region_count = len({province["properties"].get("regionId") for province in owned_provinces})
        features.append(
            {
                "type": "Feature",
                "properties": {
                    "tag": tag,
                    "name": country_state.name if country_state else tag,
                    "displayName": (country_state.name if country_state else tag).upper(),
                    "color": country_state.color if country_state else stable_color(tag),
                    "provinceCount": len(owned_provinces),
                    "regionCount": region_count,
                },
                "geometry": collect_geometries(geometries),
            }
        )

    return {"type": "FeatureCollection", "features": features}


def color_country_features(countries: dict) -> dict:
    features = []
    for feature in countries.get("features", []):
        copied = json.loads(json.dumps(feature))
        props = copied.setdefault("properties", {})
        tag = props.get("tag", "UNK")
        country = load_state().countries.get(tag)
        props["displayName"] = (country.name if country else props.get("name", tag)).upper()
        props["color"] = country.color if country else stable_color(tag)
        features.append(copied)
    return {"type": "FeatureCollection", "features": features}


def province_data_looks_rectangular(provinces: dict) -> bool:
    features = provinces.get("features", [])
    if len(features) < 20:
        return False

    rectangular = 0
    for feature in features:
        geometry = feature.get("geometry", {})
        if geometry.get("type") != "Polygon":
            continue
        rings = geometry.get("coordinates", [])
        if len(rings) != 1 or len(rings[0]) != 5:
            continue
        lon_values = {round(point[0], 6) for point in rings[0]}
        lat_values = {round(point[1], 6) for point in rings[0]}
        if len(lon_values) == 2 and len(lat_values) == 2:
            rectangular += 1

    return rectangular / len(features) > 0.5


def build_current_country_label_lines() -> dict:
    countries = build_current_countries_from_provinces()
    features = []

    for country in countries.get("features", []):
        bbox = geometry_bbox(country.get("geometry"))
        if not bbox:
            continue
        min_lon, min_lat, max_lon, max_lat = bbox
        width = max_lon - min_lon
        height = max_lat - min_lat
        if width * height < 3:
            continue
        center_lat = (min_lat + max_lat) / 2
        label_size = max(12, min(30, 10 + width / 5))
        features.append(
            {
                "type": "Feature",
                "properties": {
                    "tag": country["properties"]["tag"],
                    "label": country["properties"]["displayName"],
                    "labelSize": label_size,
                    "labelSpacing": 0.12 if width > height else 0.04,
                    "labelRank": 1,
                },
                "geometry": {
                    "type": "LineString",
                    "coordinates": [
                        [min_lon + width * 0.15, center_lat],
                        [max_lon - width * 0.15, center_lat],
                    ],
                },
            }
        )

    return {"type": "FeatureCollection", "features": features}


def build_region_geometries_from_provinces() -> dict:
    provinces = apply_campaign_ownership_to_provinces()
    regions = load_regions().get("regions", {})
    grouped: dict[str, list[dict]] = {}

    for province in provinces.get("features", []):
        region_id = province.get("properties", {}).get("regionId")
        if region_id:
            grouped.setdefault(region_id, []).append(province)

    features = []
    for region_id, region_provinces in grouped.items():
        region = regions.get(region_id, {})
        geometries = [province["geometry"] for province in region_provinces if province.get("geometry")]
        if not geometries:
            continue
        center_lon, center_lat = average_centers(region_provinces)
        features.append(
            {
                "type": "Feature",
                "properties": {
                    "regionId": region_id,
                    "label": region.get("displayName", region_id),
                    "displayName": region.get("displayName", region_id),
                    "aliases": region.get("aliases", []),
                    "provinceCount": len(region_provinces),
                    "centerLon": center_lon,
                    "centerLat": center_lat,
                },
                "geometry": collect_geometries(geometries),
            }
        )

    return {"type": "FeatureCollection", "features": features}


def build_region_labels() -> dict:
    regions_geojson = build_region_geometries_from_provinces()
    regions = load_regions().get("regions", {})
    features = []

    for region in regions_geojson.get("features", []):
        props = region.get("properties", {})
        region_data = regions.get(props.get("regionId"), {})
        features.append(
            {
                "type": "Feature",
                "properties": {
                    "regionId": props.get("regionId"),
                    "label": props.get("displayName"),
                    "labelSize": region_data.get("labelSize", 13),
                    "labelRank": region_data.get("labelRank", 1),
                    "aliases": region_data.get("aliases", []),
                },
                "geometry": {
                    "type": "Point",
                    "coordinates": [props.get("centerLon", 0), props.get("centerLat", 0)],
                },
            }
        )

    return {"type": "FeatureCollection", "features": features}


def build_microstate_points() -> dict:
    provinces = apply_campaign_ownership_to_provinces()
    features = []

    for province in provinces.get("features", []):
        props = province.get("properties", {})
        if not props.get("isMicroProvince") and props.get("areaApprox", 99) >= 1:
            continue
        features.append(
            {
                "type": "Feature",
                "properties": {
                    "provinceId": props.get("provinceId"),
                    "tag": props.get("ownerTag"),
                    "label": props.get("displayName") or props.get("name"),
                    "color": country_color(props.get("ownerTag", "UNK")),
                },
                "geometry": {
                    "type": "Point",
                    "coordinates": [props.get("centerLon", 0), props.get("centerLat", 0)],
                },
            }
        )

    return {"type": "FeatureCollection", "features": features}


def build_visual_orders() -> dict:
    campaign_state = load_campaign_state()
    features = []
    for order in campaign_state.get("visualOrders", []):
        if order.get("coordinates"):
            features.append(
                {
                    "type": "Feature",
                    "properties": {
                        "actorTag": order.get("actorTag"),
                        "label": order.get("label", ""),
                        "color": country_color(order.get("actorTag", "UNK")),
                    },
                    "geometry": {"type": "LineString", "coordinates": order["coordinates"]},
                }
            )
    return {"type": "FeatureCollection", "features": features}


def parse_order_text(actor_tag: str, text: str) -> dict:
    normalized = text.lower()
    regions = load_regions().get("regions", {})
    matches = []
    for region_id, region in regions.items():
        aliases = region.get("aliases", []) + [region.get("displayName", ""), region.get("name", "")]
        if any(alias and alias.lower() in normalized for alias in aliases):
            matches.append(region)

    action_type = "GENERAL_ORDER"
    if any(word in normalized for word in ["зайти", "ввести", "перебросить", "двигать"]):
        action_type = "MOVE_DIVISIONS"
    elif any(word in normalized for word in ["передать", "отдать", "аннексировать"]):
        action_type = "TRANSFER_REGION"
    elif "вывести" in normalized:
        action_type = "WITHDRAW_DIVISIONS"

    division_count = parse_number(normalized)
    alternatives = [
        {"regionId": region["regionId"], "displayName": region.get("displayName", region["regionId"])}
        for region in matches
    ]
    target_region = matches[0] if len(matches) == 1 else None
    return {
        "type": action_type,
        "actorTag": actor_tag,
        "divisionCount": division_count,
        "targetRegionId": target_region["regionId"] if target_region else None,
        "targetProvinceIds": target_region.get("provinceIds", []) if target_region else [],
        "confidence": 0.92 if target_region else 0.35,
        "needsClarification": len(matches) != 1,
        "alternatives": alternatives,
    }


def execute_order(order: ExecuteOrderRequest) -> dict:
    if order.type != "MOVE_DIVISIONS" or not order.targetRegionId:
        raise HTTPException(status_code=400, detail="Only MOVE_DIVISIONS is implemented in MVP")

    campaign_state = load_campaign_state()
    regions = load_regions().get("regions", {})
    target_region = regions.get(order.targetRegionId)
    if not target_region:
        raise HTTPException(status_code=404, detail="Unknown target region")

    target_province_ids = target_region.get("provinceIds", [])
    if not target_province_ids:
        raise HTTPException(status_code=400, detail="Target region has no provinces")

    moved = []
    target_province_id = target_province_ids[0]
    province_lookup = province_center_lookup()
    for division in campaign_state.get("divisions", {}).values():
        if division.get("ownerTag") != order.actorTag or len(moved) >= order.divisionCount:
            continue
        from_province_id = division.get("provinceId")
        division["provinceId"] = target_province_id
        division["movementTarget"] = None
        moved.append(division["id"])
        if from_province_id in province_lookup and target_province_id in province_lookup:
            campaign_state.setdefault("visualOrders", []).append(
                {
                    "actorTag": order.actorTag,
                    "label": f"{division['id']} -> {order.targetRegionId}",
                    "coordinates": [
                        province_lookup[from_province_id],
                        province_lookup[target_province_id],
                    ],
                }
            )

    campaign_state.setdefault("events", []).insert(
        0,
        {
            "turn": campaign_state.get("turn", 1),
            "actor": order.actorTag,
            "action": f"MOVE_DIVISIONS to {order.targetRegionId}",
            "summary": f"Moved {len(moved)} divisions to {order.targetRegionId}",
        },
    )
    save_campaign_state(campaign_state)
    return build_map_payload() | {"movedDivisions": moved}


def build_map_payload() -> dict:
    return {
        "provinces": apply_campaign_ownership_to_provinces(),
        "currentCountries": build_current_countries_from_provinces(),
        "currentLabels": build_current_country_label_lines(),
        "regionsGeojson": build_region_geometries_from_provinces(),
        "regionLabels": build_region_labels(),
        "microstates": build_microstate_points(),
        "visualOrders": build_visual_orders(),
        "state": load_campaign_state(),
    }


def transfer_provinces(province_ids: list[str], new_owner: str) -> dict:
    campaign_state = load_campaign_state()
    ownership = campaign_state.setdefault("provinceOwnership", {})
    missing = [province_id for province_id in province_ids if province_id not in ownership]
    if missing:
        raise HTTPException(status_code=404, detail=f"Unknown provinceIds: {missing}")

    for province_id in province_ids:
        ownership[province_id]["ownerTag"] = new_owner
        ownership[province_id]["controllerTag"] = new_owner

    save_campaign_state(campaign_state)
    return build_map_payload()


def move_division(division_id: str, to_province_id: str) -> dict:
    campaign_state = load_campaign_state()
    divisions = campaign_state.get("divisions", {})
    division = divisions.get(division_id)
    if not division:
        raise HTTPException(status_code=404, detail="Unknown division")

    adjacency = load_province_adjacency()
    from_province_id = division.get("provinceId")
    if to_province_id not in adjacency.get(from_province_id, []):
        raise HTTPException(status_code=400, detail="Target province is not adjacent")

    centers = province_center_lookup()
    division["provinceId"] = to_province_id
    campaign_state.setdefault("visualOrders", []).append(
        {
            "actorTag": division.get("ownerTag"),
            "label": f"{division_id} -> {to_province_id}",
            "coordinates": [centers[from_province_id], centers[to_province_id]],
        }
    )
    save_campaign_state(campaign_state)
    return build_map_payload()


def province_center_lookup() -> dict[str, list[float]]:
    provinces = apply_campaign_ownership_to_provinces()
    return {
        feature["properties"]["provinceId"]: [
            feature["properties"].get("centerLon", 0),
            feature["properties"].get("centerLat", 0),
        ]
        for feature in provinces.get("features", [])
    }


def collect_geometries(geometries: list[dict]) -> dict:
    polygons = []
    for geometry in geometries:
        if geometry.get("type") == "Polygon":
            polygons.append(geometry.get("coordinates", []))
        elif geometry.get("type") == "MultiPolygon":
            polygons.extend(geometry.get("coordinates", []))
    return {"type": "MultiPolygon", "coordinates": polygons}


def geometry_bbox(geometry: dict | None) -> tuple[float, float, float, float] | None:
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


def average_centers(provinces: list[dict]) -> tuple[float, float]:
    lon = sum(province["properties"].get("centerLon", 0) for province in provinces) / max(len(provinces), 1)
    lat = sum(province["properties"].get("centerLat", 0) for province in provinces) / max(len(provinces), 1)
    return lon, lat


def stable_color(tag: str) -> str:
    digest = hashlib.sha256(tag.encode("utf-8")).hexdigest()
    palette = ["#64748b", "#2563eb", "#16a34a", "#dc2626", "#f59e0b", "#7c3aed", "#0891b2", "#be123c"]
    return palette[int(digest[:2], 16) % len(palette)]


def country_color(tag: str) -> str:
    state = load_state()
    country = state.countries.get(tag)
    return country.color if country else stable_color(tag)


def parse_number(text: str) -> int:
    words = {
        "одну": 1,
        "один": 1,
        "две": 2,
        "два": 2,
        "три": 3,
        "тремя": 3,
        "четыре": 4,
        "пять": 5,
    }
    for word, value in words.items():
        if word in text:
            return value
    for token in text.split():
        if token.isdigit():
            return int(token)
    return 1


def clamp_0_100(value: int) -> int:
    return max(0, min(100, value))


def classify_action(action: str) -> str:
    """
    Первый грубый классификатор.
    Потом заменим на AI-судью, но игровой движок уже будет готов.
    """
    a = action.lower()

    atrocity_words = [
        "геноцид", "истреб", "сжечь", "жечь", "депорт", "расстрел",
        "лагер", "массов", "евре", "этническ", "репресс"
    ]
    authoritarian_words = [
        "цензур", "запрет", "полиция", "чулк", "форма", "диктат",
        "культ", "пропаганд", "тайная полиция"
    ]
    military_words = [
        "арм", "вооруж", "мобилизац", "флот", "авиац", "танк",
        "укреп", "границ", "штаб"
    ]
    economic_words = [
        "налог", "завод", "индустриал", "эконом", "торгов",
        "банк", "инфраструкт", "железн"
    ]

    if any(w in a for w in atrocity_words):
        return "ATROCITY_POLICY"
    if any(w in a for w in authoritarian_words):
        return "AUTHORITARIAN_POLICY"
    if any(w in a for w in military_words):
        return "MILITARY_POLICY"
    if any(w in a for w in economic_words):
        return "ECONOMIC_POLICY"

    return "GENERAL_POLICY"


def fake_adjudicate(
    action_class: str,
    actor_name: str,
    action: str,
) -> tuple[str, Dict[str, int]]:
    """
    Временный движок последствий.
    Потом сюда воткнём AI, но effects всё равно должен применять backend.
    """
    if action_class == "ATROCITY_POLICY":
        return (
            f"{actor_name} проводит крайне жёсткую внутреннюю политику. "
            "Краткосрочный контроль растёт, но легитимность, экономика и стабильность резко проседают.",
            {
                "stability": -18,
                "economy": -14,
                "military": 0,
                "legitimacy": -25,
            },
        )

    if action_class == "AUTHORITARIAN_POLICY":
        return (
            f"{actor_name} вводит авторитарное распоряжение. "
            "Государственный контроль слегка усиливается, но общественное раздражение растёт.",
            {
                "stability": -6,
                "economy": -2,
                "military": 0,
                "legitimacy": -8,
            },
        )

    if action_class == "MILITARY_POLICY":
        return (
            f"{actor_name} усиливает военный курс. Армия получает ресурсы, но экономика и стабильность платят цену.",
            {
                "stability": -3,
                "economy": -5,
                "military": 8,
                "legitimacy": -1,
            },
        )

    if action_class == "ECONOMIC_POLICY":
        return (
            f"{actor_name} запускает экономическую программу. Экономика получает импульс, но эффект не бесплатный.",
            {
                "stability": -1,
                "economy": 7,
                "military": 0,
                "legitimacy": 2,
            },
        )

    return (
        f"{actor_name} проводит общий политический курс. Последствия умеренные и пока неопределённые.",
        {
            "stability": 0,
            "economy": 1,
            "military": 0,
            "legitimacy": 0,
        },
    )


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "service": "pax-1933-backend"}


@app.get("/api/state", response_model=GameState)
def get_state() -> GameState:
    return load_state()


@app.post("/api/reset", response_model=GameState)
def reset_state() -> GameState:
    initial_path = DATA_DIR / "game_state_1933.initial.json"
    if not initial_path.exists():
        raise HTTPException(status_code=500, detail="Initial state file not found")

    with initial_path.open("r", encoding="utf-8") as f:
        raw = json.load(f)

    with STATE_PATH.open("w", encoding="utf-8") as f:
        json.dump(raw, f, ensure_ascii=False, indent=2)

    return GameState.model_validate(raw)


@app.get("/api/map/1933")
def get_map_1933() -> dict:
    if not MAP_PATH.exists():
        raise HTTPException(status_code=500, detail="GeoJSON map not found")

    with MAP_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


@app.get("/api/map/1933/provinces")
def get_map_1933_provinces() -> dict:
    return apply_campaign_ownership_to_provinces()


@app.get("/api/map/1933/current-countries")
def get_map_1933_current_countries() -> dict:
    return build_current_countries_from_provinces()


@app.get("/api/map/1933/current-labels")
def get_map_1933_current_labels() -> dict:
    return build_current_country_label_lines()


@app.get("/api/map/1933/regions-geojson")
def get_map_1933_regions_geojson() -> dict:
    return build_region_geometries_from_provinces()


@app.get("/api/map/1933/region-labels")
def get_map_1933_region_labels() -> dict:
    return build_region_labels()


@app.get("/api/map/1933/microstates")
def get_map_1933_microstates() -> dict:
    return build_microstate_points()


@app.get("/api/map/1933/regions")
def get_map_1933_regions() -> dict:
    return load_regions()


@app.get("/api/map/1933/province-adjacency")
def get_map_1933_province_adjacency() -> dict:
    return load_province_adjacency()


@app.get("/api/map/1933/visual-orders")
def get_map_1933_visual_orders() -> dict:
    return build_visual_orders()


@app.post("/api/debug/transfer-provinces")
def debug_transfer_provinces(req: TransferProvincesRequest) -> dict:
    return transfer_provinces(req.provinceIds, req.newOwner)


@app.post("/api/debug/move-division")
def debug_move_division(req: MoveDivisionRequest) -> dict:
    return move_division(req.divisionId, req.toProvinceId)


@app.post("/api/orders/parse")
def parse_order(req: ParseOrderRequest) -> dict:
    return parse_order_text(req.actorTag, req.text)


@app.post("/api/orders/execute")
def execute_parsed_order(req: ExecuteOrderRequest) -> dict:
    return execute_order(req)


@app.post("/api/turn", response_model=TurnResponse)
def make_turn(req: TurnRequest) -> TurnResponse:
    state = load_state()

    if req.actor not in state.countries:
        raise HTTPException(status_code=404, detail=f"Unknown country tag: {req.actor}")

    action = req.action.strip()
    if not action:
        raise HTTPException(status_code=400, detail="Action must not be empty")

    country = state.countries[req.actor]
    action_class = classify_action(action)
    summary, effects = fake_adjudicate(action_class, country.name, action)

    # Применяем effects только к выбранной стране.
    updated = country.model_copy(deep=True)
    for key, delta in effects.items():
        if hasattr(updated, key):
            old_value = getattr(updated, key)
            setattr(updated, key, clamp_0_100(old_value + delta))

    state.countries[req.actor] = updated

    event = Event(
        turn=state.turn,
        actor=req.actor,
        action=action,
        action_class=action_class,
        summary=summary,
        effects=effects,
    )

    state.events.insert(0, event)
    state.turn += 1

    save_state(state)

    return TurnResponse(state=state, event=event)
