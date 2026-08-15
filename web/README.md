# RangeMatch Web UI (Advisor Demo)

Buyer-facing Demo for the Mireye-first cattle natural-environment advisor. The browser consumes Advisor HTTP APIs only — no Factor/Planner/Engine logic in the client.

## Stack

Vite + React + TypeScript + React Router + **MapLibre GL JS** (2D parcel map).
Vitest + Testing Library.

Basemap: default embedded OpenStreetMap raster style (`web/src/config/map.ts`). Override with `VITE_MAP_STYLE_URL`. No Mapbox/paid credentials. No Cesium / 3D.

## Run (two terminals)

```bash
# Terminal A — API
cd /path/to/RangeMatch
python -m pip install -e ".[api]"
export PYTHONPATH=src
.venv/bin/uvicorn rangematch.api:app --reload --port 8001 --env-file .env \
  --reload-exclude '.venv' --reload-exclude '.venv-livegate' --reload-exclude 'web'

# Terminal B — UI
cd web
npm install
npm run dev
```

Open **http://127.0.0.1:5273/advisor-demo**. RangeMatch pins Vite to port **5273** (`strictPort: true`).

The Demo requests `collection_mode=MIREYE_FIRST`, requires boundary confirmation, builds the Mireye Environmental Profile, runs deterministic gap planning and only necessary supplements, projects a Natural Cattle Profile, generates a validated natural-foundation interpretation, accepts one buyer answer, downloads a Natural Cattle Foundation PDF (variable-length narrative + Appendix on a new page), and opens open-ended two-brain grounded chat. Failed calls are never replaced with another parcel or fixture.

By default the Vite proxy targets `127.0.0.1:8001` (change `web/vite.config.ts` or set `VITE_API_BASE_URL`).

## Demo flow

```text
Enter U.S. address or lat,lng (or explicit Nambe / example places)
→ Mireye lookup
→ Confirm exactly one polygon on the map
→ Natural cattle foundation view + one refining question
→ Answer → updated interpretation
→ Download report PDF
→ Optional Property chat (place materials + cattle knowledge)
```

Not supported in this Demo entry: APN-only lookup, cattle-vs-sheep product mode switch, silent Nambe/CPER substitution.

## Tests

```bash
cd web
npm test
```

Current baseline includes Advisor Demo coverage (`tests/advisor-demo.test.tsx`) plus legacy buyer UI tests (`tests/ui.test.tsx`).

## Notes

- In-memory Advisor runs clear when the API process restarts — re-run analysis after restart.
- Chat is read-only against Packet / Profile / Interpretation / Deal Context.
- Map is parcel confirmation and evidence visualization — not a suitability score surface.
- Product authority: `../docs/RANGEMATCH_PRODUCT_AND_AGENT_CODE_FLOW.md`
- Chat contract: `../docs/TWO_BRAIN_ADVISOR_CHAT_CONTRACT.md`
