/** MapLibre basemap configuration — no paid Mapbox credentials. */

/**
 * Optional vector style URL (e.g. MapLibre demotiles).
 * Default build uses OSM raster tiles below so screenshots and local demo
 * work without a style host or Mapbox token.
 */
export const DEFAULT_MAP_STYLE_URL = "https://demotiles.maplibre.org/style.json";

/** Free OSM raster style — default basemap (no API key). */
export const OSM_RASTER_STYLE = {
  version: 8 as const,
  name: "OpenStreetMap raster",
  sources: {
    osm: {
      type: "raster" as const,
      tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
      tileSize: 256,
      attribution: "© OpenStreetMap contributors",
      maxzoom: 19,
    },
  },
  layers: [
    {
      id: "osm",
      type: "raster" as const,
      source: "osm",
    },
  ],
};

export function resolveMapStyle(): string | typeof OSM_RASTER_STYLE {
  const fromEnv = (import.meta.env.VITE_MAP_STYLE_URL as string | undefined)?.trim();
  if (fromEnv) return fromEnv;
  // Prefer embedded OSM raster: no paid credentials, no external style JSON host.
  return OSM_RASTER_STYLE;
}

export const CANDIDATE_SOURCE = "rm-parcel-candidates";
export const CANDIDATE_FILL = "rm-parcel-candidates-fill";
export const CANDIDATE_LINE = "rm-parcel-candidates-line";
export const SELECTED_FILL = "rm-parcel-selected-fill";
export const SELECTED_LINE = "rm-parcel-selected-line";
export const CONFIRMED_LINE = "rm-parcel-confirmed-line";
