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
MICROSTATE_POINTS_PATH = BASE_DIR / "microstate_points_1933.geojson"
MANUAL_REGIONS_PATH = BASE_DIR / "manual_regions_1933.json"
REGIONS_GEOJSON_PATH = BASE_DIR / "regions_1933.geojson"
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

FALLBACK_MICROSTATE_POINTS = [
    ("AND", "Andorra", 1.6, 42.55),
    ("MCO", "Monaco", 7.42, 43.74),
    ("LIE", "Liechtenstein", 9.55, 47.16),
    ("SMR", "San Marino", 12.46, 43.94),
    ("VAT", "Vatican", 12.45, 41.9),
]

# TODO: real Greenland geometry should come from Natural Earth/Admin-0 map units later.

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
        "centerLon": 7.2,
        "centerLat": 50.5,
    },
    {
        "regionId": "GER_BAVARIA",
        "tag": "GER",
        "name": "Bavaria",
        "displayName": "Бавария",
        "aliases": ["Бавария", "Баварию", "Bavaria"],
        "bbox": (9.0, 47.0, 13.8, 50.8),
        "centerLon": 11.5,
        "centerLat": 48.9,
    },
    {
        "regionId": "GER_SAXONY",
        "tag": "GER",
        "name": "Saxony",
        "displayName": "Саксония",
        "aliases": ["Саксония", "Саксонию", "Saxony"],
        "bbox": (11.5, 50.0, 15.2, 52.0),
        "centerLon": 13.2,
        "centerLat": 51.1,
    },
    {
        "regionId": "GER_EAST_PRUSSIA",
        "tag": "GER",
        "name": "East Prussia",
        "displayName": "Восточная Пруссия",
        "aliases": ["Восточная Пруссия", "Восточную Пруссию", "East Prussia"],
        "bbox": (19.0, 53.0, 23.5, 55.5),
        "centerLon": 21.2,
        "centerLat": 54.4,
    },
    {
        "regionId": "POL_DANZIG",
        "tag": "POL",
        "name": "Danzig",
        "displayName": "Данциг",
        "aliases": ["Данциг", "Danzig"],
        "bbox": (18.3, 53.8, 19.3, 54.8),
        "centerLon": 18.65,
        "centerLat": 54.35,
    },
    {
        "regionId": "FRA_ALSACE_LORRAINE",
        "tag": "FRA",
        "name": "Alsace-Lorraine",
        "displayName": "Эльзас-Лотарингия",
        "aliases": ["Эльзас-Лотарингия", "Эльзас", "Alsace-Lorraine"],
        "bbox": (6.5, 47.3, 8.5, 49.5),
        "centerLon": 7.3,
        "centerLat": 48.4,
    },
    {
        "regionId": "SOV_UKRAINE",
        "tag": "SOV",
        "name": "Ukraine",
        "displayName": "Украина",
        "aliases": ["Украина", "Украину", "Ukraine"],
        "bbox": (22.0, 44.0, 41.0, 53.0),
        "centerLon": 31.0,
        "centerLat": 49.0,
    },
    {
        "regionId": "ITA_LOMBARDY",
        "tag": "ITA",
        "name": "Lombardy",
        "displayName": "Ломбардия",
        "aliases": ["Ломбардия", "Ломбардию", "Lombardy"],
        "bbox": (8.5, 44.7, 11.5, 46.8),
        "centerLon": 9.8,
        "centerLat": 45.6,
    },
    {
        "regionId": "GBR_ENGLAND",
        "tag": "GBR",
        "name": "England",
        "displayName": "Англия",
        "aliases": ["Англия", "Англию", "England"],
        "bbox": (-6.5, 49.5, 2.5, 56.0),
        "centerLon": -1.5,
        "centerLat": 52.6,
    },
    {
        "regionId": "TUR_ANATOLIA",
        "tag": "TUR",
        "name": "Anatolia",
        "displayName": "Анатолия",
        "aliases": ["Анатолия", "Анатолию", "Anatolia"],
        "bbox": (25.0, 35.0, 45.0, 42.5),
        "centerLon": 34.5,
        "centerLat": 39.0,
    },
]

MANUAL_REGION_ROWS = [
    ("GER_RHINELAND", "GER", "Рейнская область", "Rhineland", ["Рейнская область", "Рейнланд", "Rhineland", "рейнскую область"], (5.8, 49.0, 8.4, 51.6)),
    ("GER_BAVARIA", "GER", "Бавария", "Bavaria", ["Бавария", "Bavaria", "баварию"], (9.0, 47.1, 13.8, 50.7)),
    ("GER_SAXONY", "GER", "Саксония", "Saxony", ["Саксония", "Saxony", "саксонию"], (11.5, 50.0, 15.2, 52.0)),
    ("GER_EAST_PRUSSIA", "GER", "Восточная Пруссия", "East Prussia", ["Восточная Пруссия", "East Prussia", "восточную пруссию"], (19.0, 53.1, 23.4, 55.3)),
    ("GER_WESTPHALIA", "GER", "Вестфалия", "Westphalia", ["Вестфалия", "Westphalia"], (6.2, 50.8, 9.2, 52.6)),
    ("GER_HAMBURG", "GER", "Гамбург", "Hamburg", ["Гамбург", "Hamburg"], (8.5, 53.1, 10.6, 54.0)),
    ("GER_BERLIN", "GER", "Берлин", "Berlin", ["Берлин", "Berlin"], (12.5, 52.0, 14.2, 53.0)),
    ("GER_SILESIA", "GER", "Силезия", "Silesia", ["Силезия", "Silesia"], (14.4, 50.0, 18.5, 52.2)),
    ("GER_BRANDENBURG", "GER", "Бранденбург", "Brandenburg", ["Бранденбург", "Brandenburg"], (11.3, 51.4, 14.8, 53.7)),
    ("GER_BADEN_WURTTEMBERG", "GER", "Баден-Вюртемберг", "Baden-Wurttemberg", ["Баден-Вюртемберг", "Baden-Wurttemberg"], (7.5, 47.4, 10.5, 49.8)),
    ("POL_DANZIG", "POL", "Данциг", "Danzig", ["Данциг", "Danzig", "вольный город данциг"], (18.3, 53.8, 19.3, 54.8)),
    ("POL_POZNAN", "POL", "Познань", "Poznan", ["Познань", "Poznan"], (15.5, 51.0, 18.5, 53.3)),
    ("POL_WARSAW", "POL", "Варшава", "Warsaw", ["Варшава", "Warsaw"], (19.0, 51.5, 22.5, 53.5)),
    ("POL_POMERANIA", "POL", "Померания", "Pomerania", ["Померания", "Pomerania"], (15.0, 53.0, 19.2, 55.0)),
    ("POL_GALICIA", "POL", "Галиция", "Galicia", ["Галиция", "Galicia"], (20.0, 48.5, 24.8, 50.8)),
    ("POL_VILNIUS", "POL", "Вильнюс", "Vilnius", ["Вильнюс", "Vilnius"], (23.0, 53.5, 26.5, 55.8)),
    ("POL_LODZ", "POL", "Лодзь", "Lodz", ["Лодзь", "Lodz"], (17.8, 50.5, 20.5, 52.2)),
    ("POL_LUBLIN", "POL", "Люблин", "Lublin", ["Люблин", "Lublin"], (21.5, 50.0, 24.5, 52.2)),
    ("FRA_PARIS", "FRA", "Париж", "Paris", ["Париж", "Paris"], (1.3, 48.0, 3.5, 49.5)),
    ("FRA_NORMANDY", "FRA", "Нормандия", "Normandy", ["Нормандия", "Normandy"], (-2.0, 48.3, 1.5, 50.2)),
    ("FRA_BRITTANY", "FRA", "Бретань", "Brittany", ["Бретань", "Brittany"], (-5.4, 47.2, -1.2, 49.0)),
    ("FRA_ALSACE_LORRAINE", "FRA", "Эльзас-Лотарингия", "Alsace-Lorraine", ["Эльзас", "Эльзас-Лотарингия", "Alsace-Lorraine"], (6.5, 47.3, 8.5, 49.5)),
    ("FRA_AQUITAINE", "FRA", "Аквитания", "Aquitaine", ["Аквитания", "Aquitaine"], (-1.8, 43.0, 1.2, 46.2)),
    ("FRA_PROVENCE", "FRA", "Прованс", "Provence", ["Прованс", "Provence"], (4.5, 43.0, 7.8, 44.8)),
    ("FRA_BURGUNDY", "FRA", "Бургундия", "Burgundy", ["Бургундия", "Burgundy"], (3.5, 46.2, 6.2, 48.2)),
    ("FRA_OCCITANIA", "FRA", "Окситания", "Occitania", ["Окситания", "Occitania"], (0.0, 42.5, 4.8, 45.2)),
    ("ITA_LOMBARDY", "ITA", "Ломбардия", "Lombardy", ["Ломбардия", "Lombardy"], (8.5, 44.7, 11.5, 46.8)),
    ("ITA_PIEDMONT", "ITA", "Пьемонт", "Piedmont", ["Пьемонт", "Piedmont"], (6.7, 44.0, 8.8, 46.4)),
    ("ITA_VENETO", "ITA", "Венето", "Veneto", ["Венето", "Veneto"], (11.0, 44.8, 13.2, 46.6)),
    ("ITA_TUSCANY", "ITA", "Тоскана", "Tuscany", ["Тоскана", "Tuscany"], (9.5, 42.8, 12.2, 44.5)),
    ("ITA_LAZIO", "ITA", "Лацио", "Lazio", ["Лацио", "Lazio"], (11.5, 41.0, 13.5, 42.8)),
    ("ITA_SICILY", "ITA", "Сицилия", "Sicily", ["Сицилия", "Sicily"], (12.2, 36.4, 15.8, 38.4)),
    ("ITA_SARDINIA", "ITA", "Сардиния", "Sardinia", ["Сардиния", "Sardinia"], (8.0, 38.8, 9.8, 41.3)),
    ("ITA_NAPLES", "ITA", "Неаполь", "Naples", ["Неаполь", "Naples"], (13.0, 39.5, 17.5, 42.0)),
    ("ESP_CASTILE", "ESP", "Кастилия", "Castile", ["Кастилия", "Castile"], (-6.0, 39.0, -1.5, 42.5)),
    ("ESP_CATALONIA", "ESP", "Каталония", "Catalonia", ["Каталония", "Catalonia"], (0.0, 40.5, 3.4, 42.8)),
    ("ESP_ANDALUSIA", "ESP", "Андалусия", "Andalusia", ["Андалусия", "Andalusia"], (-7.5, 36.0, -1.5, 38.8)),
    ("ESP_BASQUE", "ESP", "Страна Басков", "Basque Country", ["Страна Басков", "Basque"], (-3.5, 42.4, -1.2, 43.5)),
    ("ESP_GALICIA", "ESP", "Галисия", "Galicia", ["Галисия", "Galicia"], (-9.3, 41.8, -6.5, 43.8)),
    ("ESP_VALENCIA", "ESP", "Валенсия", "Valencia", ["Валенсия", "Valencia"], (-1.0, 38.0, 0.8, 40.6)),
    ("ESP_ARAGON", "ESP", "Арагон", "Aragon", ["Арагон", "Aragon"], (-1.8, 40.0, 1.0, 42.5)),
    ("GBR_ENGLAND", "GBR", "Англия", "England", ["Англия", "England"], (-6.5, 49.5, 2.5, 56.0)),
    ("GBR_SCOTLAND", "GBR", "Шотландия", "Scotland", ["Шотландия", "Scotland"], (-7.8, 55.0, -1.0, 59.2)),
    ("GBR_WALES", "GBR", "Уэльс", "Wales", ["Уэльс", "Wales"], (-5.5, 51.2, -2.7, 53.5)),
    ("GBR_NORTHERN_IRELAND", "GBR", "Северная Ирландия", "Northern Ireland", ["Северная Ирландия", "Northern Ireland"], (-7.5, 54.0, -5.3, 55.4)),
    ("IRE_IRELAND", "IRE", "Ирландия", "Ireland", ["Ирландия", "Ireland"], (-10.5, 51.2, -5.5, 55.4)),
    ("SOV_UKRAINE", "SOV", "Украина", "Ukraine", ["Украина", "Ukraine", "украину"], (22.0, 44.0, 41.0, 53.0)),
    ("SOV_BELARUS", "SOV", "Беларусь", "Belarus", ["Беларусь", "Belarus"], (23.0, 51.0, 32.5, 56.5)),
    ("SOV_LENINGRAD", "SOV", "Ленинград", "Leningrad", ["Ленинград", "Leningrad"], (27.0, 58.0, 33.5, 61.8)),
    ("SOV_MOSCOW", "SOV", "Москва", "Moscow", ["Москва", "Moscow"], (33.0, 54.0, 40.5, 57.8)),
    ("SOV_CAUCASUS", "SOV", "Кавказ", "Caucasus", ["Кавказ", "Caucasus"], (37.0, 41.0, 49.0, 45.5)),
    ("SOV_URAL", "SOV", "Урал", "Ural", ["Урал", "Ural"], (54.0, 52.0, 66.0, 61.5)),
    ("SOV_VOLGA", "SOV", "Поволжье", "Volga", ["Поволжье", "Volga"], (44.0, 48.0, 55.0, 56.0)),
    ("SOV_CENTRAL_ASIA", "SOV", "Средняя Азия", "Central Asia", ["Средняя Азия", "Central Asia"], (55.0, 37.0, 75.0, 48.0)),
    ("SOV_SIBERIA", "SOV", "Сибирь", "Siberia", ["Сибирь", "Siberia"], (70.0, 50.0, 105.0, 65.0)),
    ("AUS_AUSTRIA", "AUS", "Австрия", "Austria", ["Австрия", "Austria"], (9.5, 46.3, 17.2, 49.2)),
    ("CZE_BOHEMIA", "CZE", "Богемия", "Bohemia", ["Богемия", "Bohemia"], (12.0, 48.5, 16.5, 51.2)),
    ("CZE_SLOVAKIA", "CZE", "Словакия", "Slovakia", ["Словакия", "Slovakia"], (16.5, 47.5, 22.5, 49.8)),
    ("HUN_HUNGARY", "HUN", "Венгрия", "Hungary", ["Венгрия", "Hungary"], (16.0, 45.5, 23.0, 48.7)),
    ("ROM_WALLACHIA", "ROM", "Валахия", "Wallachia", ["Валахия", "Wallachia"], (23.0, 43.5, 29.5, 45.8)),
    ("ROM_TRANSYLVANIA", "ROM", "Трансильвания", "Transylvania", ["Трансильвания", "Transylvania"], (21.5, 45.5, 26.5, 48.5)),
    ("YUG_SERBIA", "YUG", "Сербия", "Serbia", ["Сербия", "Serbia"], (19.0, 43.0, 23.0, 46.0)),
    ("YUG_CROATIA", "YUG", "Хорватия", "Croatia", ["Хорватия", "Croatia"], (14.0, 44.0, 18.8, 46.6)),
    ("BUL_BULGARIA", "BUL", "Болгария", "Bulgaria", ["Болгария", "Bulgaria"], (22.0, 41.0, 28.5, 44.3)),
    ("GRE_GREECE", "GRE", "Греция", "Greece", ["Греция", "Greece"], (19.5, 36.0, 26.5, 41.8)),
    ("TUR_ISTANBUL", "TUR", "Стамбул", "Istanbul", ["Стамбул", "Istanbul"], (26.0, 40.0, 30.5, 42.0)),
    ("TUR_ANATOLIA", "TUR", "Анатолия", "Anatolia", ["Анатолия", "Anatolia"], (29.0, 36.0, 39.0, 41.5)),
    ("TUR_KURDISTAN", "TUR", "Курдистан", "Kurdistan", ["Курдистан", "Kurdistan"], (38.0, 36.5, 44.5, 41.5)),
    ("TUR_ARMENIA", "TUR", "Армения", "Armenia", ["Армения", "Armenia"], (39.0, 39.0, 44.8, 42.5)),
    ("PER_PERSIA", "PER", "Персия", "Persia", ["Персия", "Persia"], (45.0, 25.0, 62.0, 39.5)),
    ("IRQ_IRAQ", "IRQ", "Ирак", "Iraq", ["Ирак", "Iraq"], (38.0, 29.0, 49.0, 37.8)),
    ("SYR_SYRIA", "SYR", "Сирия", "Syria", ["Сирия", "Syria"], (35.5, 32.0, 42.5, 37.5)),
    ("PAL_PALESTINE", "PAL", "Палестина", "Palestine", ["Палестина", "Palestine"], (34.0, 30.0, 36.0, 33.5)),
    ("EGY_EGYPT", "EGY", "Египет", "Egypt", ["Египет", "Egypt"], (25.0, 22.0, 36.5, 31.8)),
    ("CHI_NORTH_CHINA", "CHI", "Северный Китай", "North China", ["Северный Китай", "North China"], (108.0, 34.0, 120.0, 41.5)),
    ("CHI_SICHUAN", "CHI", "Сычуань", "Sichuan", ["Сычуань", "Sichuan"], (97.0, 27.0, 108.0, 33.5)),
    ("CHI_GUANGDONG", "CHI", "Гуандун", "Guangdong", ["Гуандун", "Guangdong"], (109.0, 20.0, 117.5, 25.5)),
    ("CHI_YUNNAN", "CHI", "Юньнань", "Yunnan", ["Юньнань", "Yunnan"], (97.0, 21.0, 106.0, 28.5)),
    ("CHI_MANCHURIA", "CHI", "Маньчжурия", "Manchuria", ["Маньчжурия", "Manchuria"], (120.0, 40.0, 132.0, 50.5)),
    ("MNG_MONGOLIA", "MNG", "Монголия", "Mongolia", ["Монголия", "Mongolia"], (87.0, 42.0, 119.0, 52.0)),
    ("JAP_HOME_ISLANDS", "JAP", "Японские острова", "Home Islands", ["Японские острова", "Home Islands"], (130.0, 31.0, 146.0, 45.5)),
    ("JAP_KOREA", "JAP", "Корея", "Korea", ["Корея", "Korea"], (125.0, 34.0, 130.5, 43.5)),
]


def main() -> None:
    BASE_DIR.mkdir(parents=True, exist_ok=True)
    SAVE_DIR.mkdir(parents=True, exist_ok=True)

    shutil.copyfile(SOURCE_COUNTRIES_PATH, COUNTRIES_PATH)

    with COUNTRIES_PATH.open("r", encoding="utf-8") as f:
        countries = json.load(f)

    microstate_points = build_fallback_microstate_points(countries)

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
        if not region.get("isGenerated"):
            continue
        region_provinces = [
            province
            for province in provinces
            if province["properties"]["provinceId"] in region["provinceIds"]
        ]
        center_lon, center_lat = average_centers(region_provinces)
        region["centerLon"] = center_lon
        region["centerLat"] = center_lat

    for seed in SPECIAL_REGIONS:
        region_id = seed["regionId"]
        regions.setdefault(
            region_id,
            make_region(
                region_id,
                seed["tag"],
                seed,
                seed["centerLon"],
                seed["centerLat"],
            ),
        )

    manual_regions = build_manual_regions()
    for region_id, manual_region in manual_regions["regions"].items():
        regions.setdefault(region_id, manual_region)

    adjacency = build_adjacency(provinces)
    campaign_state = build_campaign_state(provinces)
    if CAMPAIGN_PATH.exists():
        campaign_state = merge_existing_campaign_state(campaign_state)

    write_json(PROVINCES_PATH, {"type": "FeatureCollection", "features": provinces})
    write_json(REGIONS_PATH, {"regions": regions})
    write_json(MANUAL_REGIONS_PATH, manual_regions)
    write_json(REGIONS_GEOJSON_PATH, build_manual_regions_geojson(manual_regions))
    write_json(ADJACENCY_PATH, adjacency)
    write_json(MICROSTATE_POINTS_PATH, microstate_points)
    write_json(CAMPAIGN_PATH, campaign_state)
    update_game_states(provinces, countries)

    country_names = [feature.get("properties", {}).get("name", "") for feature in countries.get("features", [])]
    fallback_point_names = {
        feature.get("properties", {}).get("name", "")
        for feature in microstate_points.get("features", [])
    }
    missing_important = []
    for name in IMPORTANT_TERRITORIES:
        in_countries = any(name.lower() in str(country_name).lower() for country_name in country_names)
        in_fallback_points = name in fallback_point_names
        if not in_countries and not in_fallback_points:
            missing_important.append(name)

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


def build_fallback_microstate_points(countries: dict[str, Any]) -> dict[str, Any]:
    features = countries.get("features", [])
    existing_names = {
        str(feature.get("properties", {}).get("name", "")).lower()
        for feature in features
    }
    point_features = []

    for tag, name, center_lon, center_lat in FALLBACK_MICROSTATE_POINTS:
        if any(name.lower() in existing for existing in existing_names):
            continue
        point_features.append(
            {
                "type": "Feature",
                "properties": {
                    "tag": tag,
                    "name": name,
                    "label": name,
                    "centerLon": center_lon,
                    "centerLat": center_lat,
                    "fallbackPoint": True,
                },
                "geometry": {
                    "type": "Point",
                    "coordinates": [center_lon, center_lat],
                },
            }
        )

    return {"type": "FeatureCollection", "features": point_features}


def build_manual_regions() -> dict[str, Any]:
    regions = {}
    for region_id, owner_tag, display_name, english_name, aliases, bbox in MANUAL_REGION_ROWS:
        center_lon, center_lat = bbox_center(bbox)
        regions[region_id] = {
            "regionId": region_id,
            "displayName": display_name,
            "englishName": english_name,
            "name": english_name,
            "aliases": aliases,
            "ownerTag": owner_tag,
            "originalCountryTag": owner_tag,
            "isGenerated": False,
            "isPlayerVisible": True,
            "centerLon": center_lon,
            "centerLat": center_lat,
            "labelSize": 13,
            "labelRank": 1,
            "provinceIds": [],
            "roughPolygon": bbox_ring(bbox),
        }

    return {"regions": regions}


def build_manual_regions_geojson(manual_regions: dict[str, Any]) -> dict[str, Any]:
    features = []
    for region in manual_regions["regions"].values():
        features.append(
            {
                "type": "Feature",
                "properties": {
                    "regionId": region["regionId"],
                    "label": region["displayName"],
                    "displayName": region["displayName"],
                    "ownerTag": region["ownerTag"],
                    "isGenerated": False,
                    "isPlayerVisible": True,
                    "centerLon": region["centerLon"],
                    "centerLat": region["centerLat"],
                },
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [region["roughPolygon"]],
                },
            }
        )

    return {"type": "FeatureCollection", "features": features}


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
    is_generated = seed is None
    return {
        "regionId": region_id,
        "name": name,
        "displayName": display_name,
        "aliases": aliases,
        "originalCountryTag": tag,
        "ownerTag": tag,
        "provinceIds": [],
        "centerLon": seed.get("centerLon", center_lon) if seed else center_lon,
        "centerLat": seed.get("centerLat", center_lat) if seed else center_lat,
        "labelSize": 13,
        "labelRank": 1,
        "isGenerated": is_generated,
        "isPlayerVisible": not is_generated,
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
    return {
        "type": "Polygon",
        "coordinates": [bbox_ring(bbox)],
    }


def bbox_ring(bbox: tuple[float, float, float, float]) -> list[list[float]]:
    min_lon, min_lat, max_lon, max_lat = bbox
    return [
        [min_lon, min_lat],
        [max_lon, min_lat],
        [max_lon, max_lat],
        [min_lon, max_lat],
        [min_lon, min_lat],
    ]


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
