# Pax 1933 Starter

Browser grand-strategy sandbox prototype.

- Backend: Python + FastAPI
- Frontend: React + TypeScript + Vite + MapLibre GL JS
- Main map: CShapes-derived country-level GeoJSON for 1933
- Extra map data: MVP province/debug layer and manual player-visible region labels
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

`backend/data/base/provinces_1933.geojson` is an MVP province dataset for debugging and future gameplay. It is not the final province map and is hidden by default in the frontend.

`backend/data/base/regions_1933.json` contains generated engine regions plus a small manual set of player-visible regions:

- Рейнская область
- Бавария
- Саксония
- Восточная Пруссия
- Данциг
- Эльзас-Лотарингия
- Украина
- Ломбардия
- Англия
- Анатолия

Generated regions are kept for engine experiments but are not shown as player-facing labels.

`backend/data/save/campaign_state.json` stores province ownership, divisions, visual orders, and events for the current campaign.

## Known Issues

- Province geometry is MVP/debug, not final.
- Region geometry is not historically accurate yet.
- Country labels are safe point labels, not HOI-style curved labels.
- Greenland and microstates need better source geometry later; fake rectangle fallback polygons are intentionally disabled.
- No AI judge, combat model, or full pathfinding yet.
