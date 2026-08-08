"""Read-only F04 live gate for the CPER engineering test geometry."""

from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from urllib.parse import urlencode
from xml.etree import ElementTree

from pyproj import Transformer
from shapely import union_all
from shapely.geometry import shape
from shapely.geometry import Polygon
from shapely.ops import transform


PROJECT = Path("/Users/hongmanyi/RangeMatch")
PARCEL_PATH = PROJECT / "test-data/engineering_test_geometry_cper_001.geojson"
OUTPUT_DIR = Path("/tmp/rangematch_f04/live")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def load_env(path: Path) -> None:
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key, value.strip().strip('"').strip("'"))


def post_json(url: str, payload: dict, headers: dict | None = None) -> dict:
    request_headers = {"Content-Type": "application/json"}
    request_headers.update(headers or {})
    request = Request(
        url,
        data=json.dumps(payload).encode(),
        headers=request_headers,
        method="POST",
    )
    try:
        with urlopen(request, timeout=90) as response:
            return json.loads(response.read())
    except HTTPError as error:
        detail = error.read().decode(errors="replace")
        raise RuntimeError(f"HTTP {error.code} from {url}: {detail}") from error


load_env(PROJECT / ".env")
parcel_bytes = PARCEL_PATH.read_bytes()
parcel_geojson = json.loads(parcel_bytes)
parcel = shape(parcel_geojson["features"][0]["geometry"])
centroid = parcel.centroid

mireye_fields = [
    "soil_map_unit_name",
    "soil_drainage_class",
    "soil_ponding_frequency_class",
    "soil_hydrologic_group",
    "soil_restrictive_layer_depth_cm",
    "soil_restrictive_layer_kind",
    "soil_available_water_capacity",
]
mireye = post_json(
    os.environ["MIREYE_API_BASE_URL"].rstrip("/") + "/v1/fetch",
    {"lat": centroid.y, "lng": centroid.x, "fields": mireye_fields},
    {"Authorization": "Bearer " + os.environ["MIREYE_API_KEY"]},
)
(OUTPUT_DIR / "cper_mireye_f04_centroid.json").write_text(json.dumps(mireye, indent=2) + "\n")

wkt = parcel.wkt.replace("'", "''")
sql = f"""
SELECT
  mu.mukey, mu.musym, mu.muname,
  c.cokey, c.compname, c.comppct_r, c.majcompflag,
  c.drainagecl, c.hydgrp,
  ec.ecoclassid, ec.ecoclassname, ec.ecoclasstypename
FROM SDA_Get_Mukey_from_intersection_with_WktWgs84('{wkt}') AS i
JOIN mapunit AS mu ON mu.mukey = i.mukey
JOIN component AS c ON c.mukey = mu.mukey
LEFT JOIN coecoclass AS ec ON ec.cokey = c.cokey
ORDER BY mu.mukey, c.comppct_r DESC, c.cokey, ec.ecoclassid
"""
sda = post_json(
    "https://sdmdataaccess.sc.egov.usda.gov/Tabular/post.rest",
    {"query": sql, "format": "JSON+COLUMNNAME+METADATA"},
)
(OUTPUT_DIR / "cper_sda_mapunit_component_ecosite.json").write_text(
    json.dumps(sda, indent=2) + "\n"
)

horizon_sql = f"""
SELECT
  c.mukey, c.cokey, c.compname, c.comppct_r,
  ch.chkey, ch.hzname, ch.hzdept_r, ch.hzdepb_r,
  ch.awc_r, ch.ec_r, ch.ph1to1h2o_r
FROM SDA_Get_Mukey_from_intersection_with_WktWgs84('{wkt}') AS i
JOIN component AS c ON c.mukey = i.mukey
JOIN chorizon AS ch ON ch.cokey = c.cokey
ORDER BY c.mukey, c.comppct_r DESC, c.cokey, ch.hzdept_r, ch.chkey
"""
horizons = post_json(
    "https://sdmdataaccess.sc.egov.usda.gov/Tabular/post.rest",
    {"query": horizon_sql, "format": "JSON+COLUMNNAME+METADATA"},
)
(OUTPUT_DIR / "cper_sda_horizons.json").write_text(json.dumps(horizons, indent=2) + "\n")

restriction_sql = f"""
SELECT
  c.mukey, c.cokey, c.compname, c.comppct_r,
  cr.corestrictkey, cr.reskind, cr.resdept_r
FROM SDA_Get_Mukey_from_intersection_with_WktWgs84('{wkt}') AS i
JOIN component AS c ON c.mukey = i.mukey
LEFT JOIN corestrictions AS cr ON cr.cokey = c.cokey
ORDER BY c.mukey, c.comppct_r DESC, c.cokey, cr.resdept_r, cr.corestrictkey
"""
restrictions = post_json(
    "https://sdmdataaccess.sc.egov.usda.gov/Tabular/post.rest",
    {"query": restriction_sql, "format": "JSON+COLUMNNAME+METADATA"},
)
(OUTPUT_DIR / "cper_sda_restrictions.json").write_text(
    json.dumps(restrictions, indent=2) + "\n"
)

wetness_sql = f"""
SELECT
  c.mukey, c.cokey, c.compname, c.comppct_r,
  cm.comonthkey, cm.monthseq, cm.flodfreqcl, cm.pondfreqcl
FROM SDA_Get_Mukey_from_intersection_with_WktWgs84('{wkt}') AS i
JOIN component AS c ON c.mukey = i.mukey
LEFT JOIN comonth AS cm ON cm.cokey = c.cokey
ORDER BY c.mukey, c.comppct_r DESC, c.cokey, cm.monthseq
"""
wetness = post_json(
    "https://sdmdataaccess.sc.egov.usda.gov/Tabular/post.rest",
    {"query": wetness_sql, "format": "JSON+COLUMNNAME+METADATA"},
)
(OUTPUT_DIR / "cper_sda_monthly_wetness.json").write_text(
    json.dumps(wetness, indent=2) + "\n"
)

ecological_site_ids = [
    "R067BY002CO",
    "R067BY024CO",
    "R067BY033CO",
    "R067BY042CO",
    "R067BY045CO",
    "R067BY063CO",
]
ecological_site_access = []
for site_id in ecological_site_ids:
    mlra = site_id[1:5]
    url = f"https://edit.sc.egov.usda.gov/catalogs/esd/{mlra}/{site_id}"
    try:
        with urlopen(url, timeout=15) as response:
            content = response.read()
            final_url = response.geturl()
            status = response.status
        title_match = re.search(rb"<title[^>]*>(.*?)</title>", content, re.I | re.S)
        title = (
            re.sub(r"\s+", " ", title_match.group(1).decode(errors="replace")).strip()
            if title_match
            else None
        )
        ecological_site_access.append(
            {
                "ecological_site_id": site_id,
                "requested_url": url,
                "final_url": final_url,
                "http_status": status,
                "title": title,
                "response_sha256": hashlib.sha256(content).hexdigest(),
                "public_description_accessible": status == 200,
            }
        )
    except Exception as error:
        ecological_site_access.append(
            {
                "ecological_site_id": site_id,
                "requested_url": url,
                "public_description_accessible": False,
                "error_type": type(error).__name__,
            }
        )
(OUTPUT_DIR / "cper_ecological_site_access.json").write_text(
    json.dumps(ecological_site_access, indent=2) + "\n"
)

minx, miny, maxx, maxy = parcel.bounds
wfs_parameters = {
    "SERVICE": "WFS",
    "VERSION": "1.1.0",
    "REQUEST": "GetFeature",
    "TYPENAME": "MapunitPoly",
    "BBOX": f"{minx},{miny},{maxx},{maxy}",
    "SRSNAME": "EPSG:4326",
    "OUTPUTFORMAT": "GML2",
    "MAXFEATURES": "1000",
}
wfs_url = (
    "https://SDMDataAccess.sc.egov.usda.gov/Spatial/SDMWGS84Geographic.wfs?"
    + urlencode(wfs_parameters)
)
with urlopen(wfs_url, timeout=90) as response:
    wfs_xml = response.read()
(OUTPUT_DIR / "cper_sda_mapunit_polygons.gml").write_bytes(wfs_xml)

root = ElementTree.fromstring(wfs_xml)
features_by_mukey: dict[str, list] = {}
for member in root.iter():
    if member.tag.split("}")[-1] != "featureMember":
        continue
    descendants = list(member.iter())
    mukey = next(
        (
            node.text.strip()
            for node in descendants
            if node.tag.split("}")[-1].lower() == "mukey" and node.text
        ),
        None,
    )
    if not mukey:
        continue
    for node in descendants:
        if node.tag.split("}")[-1] != "coordinates" or not node.text:
            continue
        coordinates = []
        for pair in node.text.strip().split():
            parts = pair.split(",")
            if len(parts) >= 2:
                # SDA WFS 1.1 emits EPSG:4326 coordinates in latitude,longitude axis order.
                coordinates.append((float(parts[1]), float(parts[0])))
        if len(coordinates) >= 4:
            polygon = Polygon(coordinates)
            if polygon.is_valid and not polygon.is_empty:
                features_by_mukey.setdefault(mukey, []).append(polygon)

project_utm = Transformer.from_crs("EPSG:4326", "EPSG:32613", always_xy=True).transform
parcel_utm = transform(project_utm, parcel)
mapunit_areas = []
intersections = []
for mukey, polygons in sorted(features_by_mukey.items()):
    geometry = union_all(polygons)
    intersection = transform(project_utm, geometry).intersection(parcel_utm)
    if intersection.area > 0:
        intersections.append(intersection)
        mapunit_areas.append({"mukey": mukey, "intersection_area_m2": intersection.area})
covered = union_all(intersections).area if intersections else 0.0
spatial_summary = {
    "requested_area_m2": parcel_utm.area,
    "covered_area_m2": covered,
    "coverage_fraction": min(1.0, covered / parcel_utm.area) if parcel_utm.area else None,
    "mapunit_polygon_count": sum(len(value) for value in features_by_mukey.values()),
    "intersecting_mapunit_count": len(mapunit_areas),
    "mapunit_intersection_areas": mapunit_areas,
}
(OUTPUT_DIR / "cper_sda_spatial_coverage.json").write_text(
    json.dumps(spatial_summary, indent=2) + "\n"
)

summary = {
    "executed_at": datetime.now(timezone.utc).isoformat(),
    "geometry_sha256": hashlib.sha256(parcel_bytes).hexdigest(),
    "centroid": {"lat": centroid.y, "lng": centroid.x},
    "mireye_requested_fields": mireye_fields,
    "mireye_returned_fields": sorted((mireye.get("fields") or {}).keys()),
    "mireye_partial_failures": mireye.get("partial_failures") or [],
    "sda_table_count": len(sda.get("Table", [])),
    "sda_horizon_table_count": len(horizons.get("Table", [])),
    "sda_restriction_table_count": len(restrictions.get("Table", [])),
    "sda_monthly_wetness_table_count": len(wetness.get("Table", [])),
    "public_ecological_site_descriptions_accessible": sum(
        item["public_description_accessible"] for item in ecological_site_access
    ),
    "sda_spatial_coverage": spatial_summary,
    "artifact_sha256": {
        "mireye_point": hashlib.sha256(
            (OUTPUT_DIR / "cper_mireye_f04_centroid.json").read_bytes()
        ).hexdigest(),
        "sda_tabular": hashlib.sha256(
            (OUTPUT_DIR / "cper_sda_mapunit_component_ecosite.json").read_bytes()
        ).hexdigest(),
        "sda_wfs_gml": hashlib.sha256(wfs_xml).hexdigest(),
        "sda_spatial_summary": hashlib.sha256(
            (OUTPUT_DIR / "cper_sda_spatial_coverage.json").read_bytes()
        ).hexdigest(),
        "sda_horizons": hashlib.sha256(
            (OUTPUT_DIR / "cper_sda_horizons.json").read_bytes()
        ).hexdigest(),
        "sda_restrictions": hashlib.sha256(
            (OUTPUT_DIR / "cper_sda_restrictions.json").read_bytes()
        ).hexdigest(),
        "sda_monthly_wetness": hashlib.sha256(
            (OUTPUT_DIR / "cper_sda_monthly_wetness.json").read_bytes()
        ).hexdigest(),
        "ecological_site_access": hashlib.sha256(
            (OUTPUT_DIR / "cper_ecological_site_access.json").read_bytes()
        ).hexdigest(),
    },
}
(OUTPUT_DIR / "cper_f04_live_gate_summary.json").write_text(
    json.dumps(summary, indent=2) + "\n"
)
print(json.dumps(summary, indent=2))
