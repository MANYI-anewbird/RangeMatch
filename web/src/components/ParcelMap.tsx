import { useEffect, useRef, useState } from "react";
import * as maplibregl from "maplibre-gl";
import type { Map, MapMouseEvent, LngLatBoundsLike, GeoJSONSource } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import type { Feature, FeatureCollection, Geometry, MultiPolygon, Polygon } from "geojson";
import type { ParcelCandidate } from "../api/client";
import {
  CANDIDATE_FILL,
  CANDIDATE_LINE,
  CANDIDATE_SOURCE,
  CONFIRMED_LINE,
  OSM_RASTER_STYLE,
  SELECTED_FILL,
  SELECTED_LINE,
  resolveMapStyle,
} from "../config/map";

function featureCollectionFromCandidates(
  candidates: ParcelCandidate[],
  selectedId: string | null,
  confirmed: boolean,
): FeatureCollection {
  const features: Feature[] = [];
  for (const c of candidates) {
    const geom = c.parcel_geometry;
    if (!geom || typeof geom !== "object") continue;
    const gtype = (geom as { type?: string }).type;
    let featureGeoms: Geometry[] = [];
    if (gtype === "FeatureCollection") {
      const feats = ((geom as unknown as FeatureCollection).features || []) as Feature[];
      for (const f of feats) {
        if (f?.geometry) featureGeoms.push(f.geometry);
      }
    } else if (gtype === "Feature") {
      const g = (geom as unknown as Feature).geometry;
      if (g) featureGeoms.push(g);
    } else if (gtype === "Polygon" || gtype === "MultiPolygon") {
      featureGeoms.push(geom as unknown as Polygon | MultiPolygon);
    }
    for (const geometry of featureGeoms) {
      if (geometry.type !== "Polygon" && geometry.type !== "MultiPolygon") continue;
      features.push({
        type: "Feature",
        id: c.candidate_id,
        properties: {
          candidate_id: c.candidate_id,
          label: c.label,
          selected: c.candidate_id === selectedId,
          confirmed: confirmed && c.candidate_id === selectedId,
          geometry_hash: c.geometry_hash || "",
        },
        geometry,
      });
    }
  }
  return { type: "FeatureCollection", features };
}

function boundsFromFc(fc: FeatureCollection): LngLatBoundsLike | null {
  const b = new maplibregl.LngLatBounds();
  let any = false;
  const extend = (coords: unknown): void => {
    if (!Array.isArray(coords)) return;
    if (typeof coords[0] === "number" && typeof coords[1] === "number") {
      b.extend([coords[0] as number, coords[1] as number]);
      any = true;
      return;
    }
    for (const c of coords) extend(c);
  };
  for (const f of fc.features) {
    if (f.geometry) extend((f.geometry as Polygon | MultiPolygon).coordinates);
  }
  return any ? b : null;
}

export type ParcelMapProps = {
  candidates: ParcelCandidate[];
  selectedCandidateId: string | null;
  confirmed: boolean;
  onSelectCandidate: (candidateId: string) => void;
  interactive?: boolean;
  /** When true, empty-map clicks set a query pin (COORDINATE intake). */
  pinDropEnabled?: boolean;
  queryPin?: { latitude: number; longitude: number } | null;
  onDropPin?: (latitude: number, longitude: number) => void;
};

/**
 * MapLibre evidence visualization for parcel candidates.
 * Does not make suitability decisions. MapLibre demo / OSM basemap — no Mapbox token.
 */
export function ParcelMap({
  candidates,
  selectedCandidateId,
  confirmed,
  onSelectCandidate,
  interactive = true,
  pinDropEnabled = false,
  queryPin = null,
  onDropPin,
}: ParcelMapProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<Map | null>(null);
  const markerRef = useRef<maplibregl.Marker | null>(null);
  const onSelectRef = useRef(onSelectCandidate);
  const onDropPinRef = useRef(onDropPin);
  const pinDropRef = useRef(pinDropEnabled);
  const [mapReady, setMapReady] = useState(false);
  const [mapFailed, setMapFailed] = useState(false);
  onSelectRef.current = onSelectCandidate;
  onDropPinRef.current = onDropPin;
  pinDropRef.current = pinDropEnabled;

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;
    if (
      typeof window !== "undefined" &&
      !(window as unknown as { WebGLRenderingContext?: unknown }).WebGLRenderingContext
    ) {
      setMapFailed(true);
      return;
    }
    const style = resolveMapStyle();
    let map: Map;
    try {
      map = new maplibregl.Map({
        container: containerRef.current,
        style,
        center: [-104.895, 40.495],
        zoom: 12,
        attributionControl: { compact: true },
      });
    } catch {
      try {
        map = new maplibregl.Map({
          container: containerRef.current,
          style: OSM_RASTER_STYLE,
          center: [-104.895, 40.495],
          zoom: 12,
        });
      } catch {
        setMapFailed(true);
        return;
      }
    }
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
    mapRef.current = map;

    const onClick = (e: MapMouseEvent) => {
      if (!interactive) return;
      const feats = map.queryRenderedFeatures(e.point, {
        layers: [CANDIDATE_FILL, SELECTED_FILL].filter((id) => map.getLayer(id)),
      });
      const id = feats[0]?.properties?.candidate_id;
      if (typeof id === "string" && id) {
        onSelectRef.current(id);
        return;
      }
      if (pinDropRef.current && onDropPinRef.current) {
        onDropPinRef.current(e.lngLat.lat, e.lngLat.lng);
      }
    };
    map.on("click", onClick);
    map.on("load", () => setMapReady(true));
    // Style/source failures only — ignore transient tile network noise.
    map.on("error", (e) => {
      const err = e?.error as { status?: number; message?: string } | undefined;
      const msg = String(err?.message || "");
      if (msg.includes("Failed to fetch") && msg.includes("style")) {
        setMapFailed(true);
      }
    });

    return () => {
      map.off("click", onClick);
      markerRef.current?.remove();
      markerRef.current = null;
      map.remove();
      mapRef.current = null;
    };
  }, [interactive]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapReady) return;
    if (!queryPin) {
      markerRef.current?.remove();
      markerRef.current = null;
      return;
    }
    const lngLat: [number, number] = [queryPin.longitude, queryPin.latitude];
    if (!markerRef.current) {
      markerRef.current = new maplibregl.Marker({ color: "#1f3f28" })
        .setLngLat(lngLat)
        .addTo(map);
    } else {
      markerRef.current.setLngLat(lngLat);
    }
    if (candidates.length === 0) {
      map.easeTo({ center: lngLat, zoom: Math.max(map.getZoom(), 12), duration: 300 });
    }
  }, [queryPin, mapReady, candidates.length]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapReady) return;

    const apply = () => {
      const fc = featureCollectionFromCandidates(
        candidates,
        selectedCandidateId,
        confirmed,
      );
      const source = map.getSource(CANDIDATE_SOURCE) as GeoJSONSource | undefined;
      if (source) {
        source.setData(fc);
      } else {
        map.addSource(CANDIDATE_SOURCE, { type: "geojson", data: fc });
        map.addLayer({
          id: CANDIDATE_FILL,
          type: "fill",
          source: CANDIDATE_SOURCE,
          paint: {
            "fill-color": [
              "case",
              ["==", ["get", "selected"], true],
              "#a7cf78",
              "#5f6b5c",
            ],
            "fill-opacity": [
              "case",
              ["==", ["get", "selected"], true],
              0.2,
              0.12,
            ],
          },
        });
        map.addLayer({
          id: CANDIDATE_LINE,
          type: "line",
          source: CANDIDATE_SOURCE,
          paint: {
            "line-color": "#5f6b5c",
            "line-width": 1.5,
          },
          filter: ["!=", ["get", "selected"], true],
        });
        map.addLayer({
          id: SELECTED_FILL,
          type: "fill",
          source: CANDIDATE_SOURCE,
          filter: ["==", ["get", "selected"], true],
          paint: {
            "fill-color": "#a7cf78",
            "fill-opacity": 0.18,
          },
        });
        map.addLayer({
          id: SELECTED_LINE,
          type: "line",
          source: CANDIDATE_SOURCE,
          filter: ["==", ["get", "selected"], true],
          paint: {
            "line-color": "#d8efae",
            "line-width": 3,
          },
        });
        map.addLayer({
          id: CONFIRMED_LINE,
          type: "line",
          source: CANDIDATE_SOURCE,
          filter: ["==", ["get", "confirmed"], true],
          paint: {
            "line-color": "#d8efae",
            "line-width": 4.5,
          },
        });
      }

      const bounds = boundsFromFc(fc);
      if (bounds && candidates.length > 0) {
        map.fitBounds(bounds, { padding: 48, maxZoom: 15, duration: 400 });
      }
    };

    apply();
  }, [candidates, selectedCandidateId, confirmed, mapReady]);

  return (
    <div className="parcel-map-wrap" data-testid="parcel-map">
      <div
        ref={containerRef}
        className={`parcel-map-canvas${confirmed ? " is-confirmed" : ""}`}
        role="img"
        aria-label="Parcel candidate map. Evidence visualization only."
      />
      {(candidates.length === 0 || mapFailed) && (
        <p className="parcel-map-empty muted">
          {mapFailed
            ? "Map canvas unavailable in this environment — use candidate list / accessible controls."
            : "Resolve an address to show parcel boundaries."}
        </p>
      )}
      <div className="parcel-map-a11y" aria-label="Map candidate selection">
        {candidates.map((c) => (
          <button
            key={c.candidate_id}
            type="button"
            className="sr-only-focusable"
            data-testid={`map-candidate-${c.candidate_id}`}
            disabled={!interactive}
            onClick={() => onSelectCandidate(c.candidate_id)}
          >
            Select {c.label} on map
          </button>
        ))}
      </div>
    </div>
  );
}
