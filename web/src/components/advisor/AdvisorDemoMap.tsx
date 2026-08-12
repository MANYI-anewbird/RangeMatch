import { useEffect, useRef } from "react";
import * as maplibregl from "maplibre-gl";
import type { FeatureCollection, Polygon } from "geojson";
import "maplibre-gl/dist/maplibre-gl.css";
import { OSM_RASTER_STYLE, resolveMapStyle } from "../../config/map";

type MapLayer = {
  layer_id: string;
  candidate_type?: string;
  display_name?: string | null;
  bbox?: number[];
};

function bboxPolygon(bbox: number[]): Polygon {
  const [west, south, east, north] = bbox;
  return {
    type: "Polygon",
    coordinates: [
      [
        [west, south],
        [east, south],
        [east, north],
        [west, north],
        [west, south],
      ],
    ],
  };
}

export function AdvisorDemoMap({
  parcel,
  layers,
}: {
  parcel: FeatureCollection;
  layers: MapLayer[];
}) {
  const ref = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!ref.current) return;
    const map = new maplibregl.Map({
      container: ref.current,
      style: resolveMapStyle() || OSM_RASTER_STYLE,
      center: [-104.7625, 40.8235],
      zoom: 13,
      attributionControl: {},
    });
    map.on("load", () => {
      map.addSource("advisor-parcel", { type: "geojson", data: parcel });
      map.addLayer({
        id: "advisor-parcel-fill",
        type: "fill",
        source: "advisor-parcel",
        paint: { "fill-color": "#2f5d3a", "fill-opacity": 0.12 },
      });
      map.addLayer({
        id: "advisor-parcel-line",
        type: "line",
        source: "advisor-parcel",
        paint: { "line-color": "#1f3f28", "line-width": 2 },
      });
      const features = layers
        .filter((row) => Array.isArray(row.bbox) && row.bbox.length >= 4)
        .map((row) => ({
          type: "Feature" as const,
          properties: {
            id: row.layer_id,
            label: row.display_name || row.candidate_type || "Mapped area",
          },
          geometry: bboxPolygon(row.bbox as number[]),
        }));
      map.addSource("advisor-water", {
        type: "geojson",
        data: { type: "FeatureCollection", features },
      });
      map.addLayer({
        id: "advisor-water-fill",
        type: "fill",
        source: "advisor-water",
        paint: { "fill-color": "#1e4d6b", "fill-opacity": 0.28 },
      });
      map.addLayer({
        id: "advisor-water-line",
        type: "line",
        source: "advisor-water",
        paint: { "line-color": "#1e4d6b", "line-width": 1.5 },
      });
      const bounds = new maplibregl.LngLatBounds();
      let any = false;
      const walk = (coords: unknown): void => {
        if (!Array.isArray(coords)) return;
        if (typeof coords[0] === "number" && typeof coords[1] === "number") {
          bounds.extend([coords[0] as number, coords[1] as number]);
          any = true;
          return;
        }
        for (const item of coords) walk(item);
      };
      for (const feature of parcel.features) walk(feature.geometry);
      for (const feature of features) walk(feature.geometry.coordinates);
      if (any) map.fitBounds(bounds, { padding: 36, maxZoom: 15 });
    });
    return () => map.remove();
  }, [parcel, layers]);

  return <div className="advisor-map" ref={ref} data-testid="advisor-demo-map" />;
}
