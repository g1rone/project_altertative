# Pax 1933 Starter

Browser grand-strategy sandbox prototype.

- Backend: Python + FastAPI
- Frontend: React + TypeScript + Vite + MapLibre GL JS
- Main map renderer: PMTiles/vector tiles generated from processed Cartography V1 layers
- GeoJSON files: preparation, diagnostics, and debug/fallback endpoints only
- Not included yet: AI, combat, politics, statistics, pathfinding, users/sessions

## Backend

```powershell
cd backend
.\.venv\Scripts\activate
pip install -r requirements.txt
python scripts/prepare_microstates.py
python scripts/prepare_admin1_regions.py
python scripts/prepare_rivers.py
python scripts/prepare_labels.py
python scripts/build_pmtiles.py
uvicorn main:app --reload
```

On Windows, build PMTiles with Docker after running the preparation scripts:

```powershell
cd backend
powershell -ExecutionPolicy Bypass -File .\scripts\build_pmtiles_docker.ps1
```

Backend runs at:

```text
http://127.0.0.1:8000
```

Useful checks:

```text
http://127.0.0.1:8000/api/health
http://127.0.0.1:8000/api/map/1933/tile-metadata
http://127.0.0.1:8000/api/map/1933/tile-status
http://127.0.0.1:8000/tiles/pax1933_map.pmtiles
```

## Frontend

```powershell
cd frontend
npm install
npm run dev
```

Frontend usually runs at:

```text
http://localhost:5173
```

## Cartography V1

The frontend's normal map path uses a MapLibre vector source:

```text
pmtiles://http://127.0.0.1:8000/tiles/pax1933_map.pmtiles
```

The PMTiles archive is built from:

```text
backend/data/processed/countries_1933.geojson
backend/data/processed/regions_1933.geojson
backend/data/processed/microstates_1933.geojson
backend/data/processed/rivers_1933.geojson
backend/data/processed/country_label_lines_1933.geojson
backend/data/processed/country_label_points_1933.geojson
backend/data/processed/region_label_points_1933.geojson
backend/data/processed/microstate_label_points_1933.geojson
```

Source layers inside `pax1933_map.pmtiles`:

```text
countries
regions
microstates
rivers
country_label_lines
country_label_points
region_label_points
microstate_label_points
```

`backend/data/raw` is intentionally not committed. Put large CShapes and Natural Earth source files there locally. The preparation scripts can auto-download the Natural Earth Admin-0, Admin-1, and river files when the network is available.

Old GeoJSON endpoints are still available for debug/fallback, but the normal frontend route does not load the huge `regions_1933.geojson`. Province borders are lazy-loaded only when the debug toggle is enabled.

## Data Notes

Countries come from the CShapes-derived 1933 country map, with Natural Earth Admin-0 used for missing map units such as Greenland and microstate polygons. Regions come from Natural Earth Admin-1 clipped to the 1933 country geometries; oversized or over-detailed countries are grid-aggregated/split only through real intersections, never saved as raw rectangles.

Microstates are polygons when Natural Earth or CShapes has polygon geometry. Labels and hitboxes are separate point layers so tiny states remain readable and clickable.

Country labels are generated from current country geometry into line labels where safe, otherwise representative-point labels. Region labels use readable title-case names and hide technical IDs such as `TAG_STATE_001`.

Dynamic ownership overlay is planned later. AI, combat, politics, statistics, full pathfinding, and user/session isolation are later systems, not part of Cartography V1.
