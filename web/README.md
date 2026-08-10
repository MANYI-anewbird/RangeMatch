# RangeMatch Web UI (buyer prototype)

Consumes the One-Parcel API only. No Factor/Planner/Engine logic in the browser.

## Stack

Vite + React + TypeScript + React Router + **MapLibre GL JS** (2D parcel map).
Vitest + Testing Library.

Basemap: default embedded OpenStreetMap raster style (`web/src/config/map.ts`). Override with `VITE_MAP_STYLE_URL` (e.g. MapLibre demotiles). No Mapbox/paid credentials. No Cesium / 3D.

## Run (two terminals)

```bash
# Terminal A — API
cd /path/to/RangeMatch
python -m pip install -e ".[api]"
export PYTHONPATH=src
uvicorn rangematch.api:app --reload --port 8001 --env-file .env

# Terminal B — UI
cd web
npm install
npm run dev
```

Open the Vite URL printed by the dev server (normally http://127.0.0.1:5173; it may use 5174 when 5173 is occupied).

By default the Vite proxy targets `127.0.0.1:8001` (change `web/vite.config.ts` or set `VITE_API_BASE_URL` if you use another API port).

## Parcel selection flow

Two entries, one confirmation path:

```text
Select your land
  [ Search by address ]
  or
  [ Drop a pin on the map ] / [ Enter coordinates ]   ← same COORDINATE kind
```

1. Choose address **or** pin/coordinates
2. **Resolve property** → `POST /v1/parcel-resolutions` (`input_kind` ADDRESS|COORDINATE)
3. Select candidate on map / list (multi-candidate required)
4. **Confirm this parcel** → `POST .../confirm` with geometry hash
5. Choose General Exploration / Cattle / Sheep
6. **Start Analysis** → `POST /v1/investigations` returns `QUEUED` immediately → navigate to progress page

Fixture mode is explicitly labeled as demo data. LIVE mode calls the configured Mireye resolver and fails visibly with no silent fixture substitution.
Not supported: APN, boundary upload, batch, multi-parcel, freehand draw, nationwide search.

## Tests

```bash
cd web
npm test
```

## Notes

- In-memory API store clears on API restart (investigations + parcel resolutions).
- Map is evidence visualization only — not a suitability decision surface.
- After navigation, Investigation page polls `GET /investigations/{id}` + `/trace`
  until terminal (`QUEUED` → `RUNNING` → `COMPLETED|PARTIAL|FAILED|…`).
- Buyer report is requested only after Unified Output exists.
- The Public Diligence Agent runs after deterministic evaluation and cannot alter F01–F08 or MatchResult.
- The result page has a decision dashboard, parcel-specific readable report, and collapsed evidence appendix.
- Buyer-facing `More evidence needed` maps to Engine `HOLD`; no fit score or winner is invented.
- Demo screenshots: `web/screenshots/`.
