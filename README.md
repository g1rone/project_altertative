# Pax 1933 Starter

Browser grand-strategy sandbox prototype.

- Backend: Python + FastAPI
- Frontend: React + TypeScript + Vite + MapLibre GL JS
- Main map: CShapes-derived country-level GeoJSON for 1933
- Extra map data: Cartography V1 dynamic country labels, manual region layer, and province debug layer
- Order flow: command parser skeleton, no AI judge or combat system yet

## Backend

```powershell
cd backend
.\.venv\Scripts\activate
pip install -r requirements.txt
python scripts\generate_provinces_1933.py
uvicorn main:app --reload
```

Backend runs at:

```text
http://127.0.0.1:8000
```

Useful checks:

```text
http://127.0.0.1:8000/api/health
http://127.0.0.1:8000/api/map/1933
http://127.0.0.1:8000/api/map/1933/current-countries
http://127.0.0.1:8000/api/map/1933/current-labels
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

## Current Architecture

`/api/map/1933` returns the historical country-level CShapes map. This is the stable political map used for the main visual layer.

`/api/map/1933/current-labels` builds country labels dynamically from the current country geometry. The backend groups current provinces by `ownerTag`, builds country geometry, and generates label lines/points from that geometry. After ownership changes, labels can be recalculated with the new borders.

`backend/data/base/provinces_1933.geojson` is an MVP province dataset for debugging and future gameplay. It is not the final province map and is hidden by default in the frontend. The `Show provinces` button enables only thin province borders, not province fill.

`backend/data/base/manual_regions_1933.json` contains rough player-visible regions for Cartography V1. These are approximate polygons meant for readable borders, labels, and command parsing. Generated regions are kept for engine experiments but are not shown as player-facing labels.

Current manual regions cover Germany, Poland, France, Italy, Spain, the British Isles, the Soviet Union, Central Europe, the Balkans, Turkey/Middle East, and East Asia.

Generated regions are kept for engine experiments but are not shown as player-facing labels.

`backend/data/save/campaign_state.json` stores province ownership, divisions, visual orders, and events for the current campaign.

TODO: saves are currently global. Later they should be isolated per user/session/campaign, for example `backend/data/save/{campaignId}/campaign_state.json` or a database-backed `campaigns` table.

## Known Issues

- Province geometry is MVP/debug, not final.
- Region polygons are rough Cartography V1 approximations, not final historical administrative borders.
- Country labels are dynamic geometry-based labels, but not final HOI-style typography yet.
- Greenland and microstates need better source geometry later; fake rectangle fallback polygons are intentionally disabled.
- No AI judge, combat model, or full pathfinding yet.
- User/session-isolated saves are planned later.
