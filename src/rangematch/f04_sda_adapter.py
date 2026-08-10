"""Live USDA-NRCS Soil Data Access adapter for F04 confirmed parcels.

The adapter only collects parcel soil/site context required by the frozen F04
contract. It does not create a soil score or directional suitability rule.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any, Mapping
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from xml.etree import ElementTree

from pyproj import Transformer
from shapely.geometry import Polygon, shape
from shapely.ops import transform, unary_union

from rangematch.f04_derivation import derive_f04_parcel_facts
from rangematch.f06_derivation import select_working_crs


SDA_TABULAR_URL = "https://sdmdataaccess.sc.egov.usda.gov/Tabular/post.rest"
SDA_WFS_URL = "https://SDMDataAccess.sc.egov.usda.gov/Spatial/SDMWGS84Geographic.wfs"
ADAPTER_ID = "F04_USDA_NRCS_SDA_ADAPTER@0.1.0"


class F04SDAAdapterError(RuntimeError):
    pass


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _post_query(sql: str, *, timeout_s: int = 120) -> dict[str, Any]:
    request_payload = {"query": sql, "format": "JSON+COLUMNNAME+METADATA"}
    try:
        import requests

        session = requests.Session()
        session.trust_env = False
        response = session.post(
            SDA_TABULAR_URL,
            json=request_payload,
            headers={"User-Agent": "RangeMatch/0.1"},
            timeout=timeout_s,
        )
        response.raise_for_status()
        result = response.json()
    except ImportError:
        payload = json.dumps(request_payload).encode()
        request = Request(
            SDA_TABULAR_URL,
            data=payload,
            headers={"Content-Type": "application/json", "User-Agent": "RangeMatch/0.1"},
            method="POST",
        )
        with urlopen(request, timeout=timeout_s) as response:
            result = json.loads(response.read())
    if not isinstance(result, dict) or "Table" not in result:
        raise F04SDAAdapterError("SDA tabular response did not include Table")
    return result


def _fetch_wfs_spatial_coverage(parcel, *, timeout_s: int = 120) -> dict[str, Any]:
    minx, miny, maxx, maxy = parcel.bounds
    params = {
        "SERVICE": "WFS",
        "VERSION": "1.1.0",
        "REQUEST": "GetFeature",
        "TYPENAME": "MapunitPoly",
        "BBOX": f"{minx},{miny},{maxx},{maxy}",
        "SRSNAME": "EPSG:4326",
        "OUTPUTFORMAT": "GML2",
        "MAXFEATURES": "1000",
    }
    url = SDA_WFS_URL + "?" + urlencode(params)
    try:
        import requests

        session = requests.Session()
        session.trust_env = False
        response = session.get(url, headers={"User-Agent": "RangeMatch/0.1"}, timeout=timeout_s)
        response.raise_for_status()
        xml = response.content
    except ImportError:
        request = Request(url, headers={"User-Agent": "RangeMatch/0.1"})
        with urlopen(request, timeout=timeout_s) as response:
            xml = response.read()
    root = ElementTree.fromstring(xml)
    features_by_mukey: dict[str, list[Any]] = {}
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
            coords = []
            for pair in node.text.strip().split():
                parts = pair.split(",")
                if len(parts) >= 2:
                    # SDA WFS 1.1 emits latitude,longitude for EPSG:4326.
                    coords.append((float(parts[1]), float(parts[0])))
            if len(coords) >= 4:
                polygon = Polygon(coords)
                if polygon.is_valid and not polygon.is_empty:
                    features_by_mukey.setdefault(str(mukey), []).append(polygon)

    crs_selection = select_working_crs(parcel)
    if not crs_selection.get("ok"):
        raise F04SDAAdapterError("Unable to select projected CRS for parcel")
    working_crs = str(crs_selection["working_crs"])
    project = Transformer.from_crs("EPSG:4326", working_crs, always_xy=True).transform
    parcel_projected = transform(project, parcel)
    intersections = []
    mapunit_areas = []
    for mukey, polygons in sorted(features_by_mukey.items()):
        intersection = transform(project, unary_union(polygons)).intersection(parcel_projected)
        if intersection.area > 0:
            intersections.append(intersection)
            mapunit_areas.append(
                {"mukey": mukey, "intersection_area_m2": float(intersection.area)}
            )
    covered_area = float(unary_union(intersections).area) if intersections else 0.0
    requested_area = float(parcel_projected.area)
    return {
        "requested_area_m2": requested_area,
        "covered_area_m2": covered_area,
        "coverage_fraction": min(1.0, covered_area / requested_area) if requested_area else 0.0,
        "mapunit_polygon_count": sum(len(items) for items in features_by_mukey.values()),
        "intersecting_mapunit_count": len(mapunit_areas),
        "mapunit_intersection_areas": mapunit_areas,
        "working_crs": working_crs,
    }


def collect_f04_from_usda_sda(
    *,
    geometry: Mapping[str, Any],
    geometry_id: str,
    geometry_hash: str,
    mireye_context: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Collect and derive F04 for exactly one confirmed parcel geometry."""
    features = list(geometry.get("features") or [])
    if geometry.get("type") != "FeatureCollection" or len(features) != 1:
        raise F04SDAAdapterError("F04 requires exactly one confirmed parcel Feature")
    parcel = shape(features[0].get("geometry"))
    if parcel.is_empty or not parcel.is_valid:
        raise F04SDAAdapterError("F04 parcel geometry is invalid or empty")
    wkt = parcel.wkt.replace("'", "''")
    intersection = f"SDA_Get_Mukey_from_intersection_with_WktWgs84('{wkt}')"
    components = _post_query(f"""
SELECT mu.mukey, mu.musym, mu.muname, c.cokey, c.compname, c.comppct_r,
 c.majcompflag, c.drainagecl, c.hydgrp, ec.ecoclassid, ec.ecoclassname,
 ec.ecoclasstypename
FROM {intersection} AS i JOIN mapunit AS mu ON mu.mukey=i.mukey
JOIN component AS c ON c.mukey=mu.mukey
LEFT JOIN coecoclass AS ec ON ec.cokey=c.cokey
ORDER BY mu.mukey, c.comppct_r DESC, c.cokey, ec.ecoclassid
""")
    horizons = _post_query(f"""
SELECT c.mukey, c.cokey, c.compname, c.comppct_r, ch.chkey, ch.hzname,
 ch.hzdept_r, ch.hzdepb_r, ch.awc_r, ch.ec_r, ch.ph1to1h2o_r
FROM {intersection} AS i JOIN component AS c ON c.mukey=i.mukey
JOIN chorizon AS ch ON ch.cokey=c.cokey
ORDER BY c.mukey, c.comppct_r DESC, c.cokey, ch.hzdept_r, ch.chkey
""")
    restrictions = _post_query(f"""
SELECT c.mukey, c.cokey, c.compname, c.comppct_r, cr.corestrictkey,
 cr.reskind, cr.resdept_r
FROM {intersection} AS i JOIN component AS c ON c.mukey=i.mukey
LEFT JOIN corestrictions AS cr ON cr.cokey=c.cokey
ORDER BY c.mukey, c.comppct_r DESC, c.cokey, cr.resdept_r, cr.corestrictkey
""")
    wetness = _post_query(f"""
SELECT c.mukey, c.cokey, c.compname, c.comppct_r, cm.comonthkey,
 cm.monthseq, cm.flodfreqcl, cm.pondfreqcl
FROM {intersection} AS i JOIN component AS c ON c.mukey=i.mukey
LEFT JOIN comonth AS cm ON cm.cokey=c.cokey
ORDER BY c.mukey, c.comppct_r DESC, c.cokey, cm.monthseq
""")
    spatial = _fetch_wfs_spatial_coverage(parcel)

    # EDIT access is deliberately not inferred from an ID. The link is preserved,
    # while current accessibility remains unknown until a separately audited fetch.
    table = components.get("Table") or []
    ecological_ids: list[str] = []
    if table and "ecoclassid" in table[0]:
        idx = table[0].index("ecoclassid")
        for row in table[1:]:
            if row and not str(row[0]).startswith("ColumnOrdinal=") and row[idx]:
                value = str(row[idx])
                if value not in ecological_ids:
                    ecological_ids.append(value)
    ecological_access = [
        {
            "ecological_site_id": site_id,
            "public_description_accessible": None,
            "access_status": "UNKNOWN",
            "note": "EDIT live accessibility not fetched by confirmed-parcel F04 adapter v0.1.",
        }
        for site_id in ecological_ids
    ]
    mireye_point = None
    if mireye_context:
        mireye_point = {
            "fetched_at": (mireye_context.get("provenance") or {}).get("retrieved_at"),
            "fields": mireye_context.get("fields") or mireye_context.get("data"),
            "partial_failures": mireye_context.get("partial_failures") or [],
        }
    derived = derive_f04_parcel_facts(
        spatial_coverage=spatial,
        components_table=components,
        horizons_table=horizons,
        restrictions_table=restrictions,
        monthly_wetness_table=wetness,
        ecological_site_access=ecological_access,
        mireye_point=mireye_point,
        geometry_hash=geometry_hash,
        fetched_at=_utc_now(),
        source_fixture_references=[
            f"live://{ADAPTER_ID}/{geometry_id}/spatial",
            f"live://{ADAPTER_ID}/{geometry_id}/components",
            f"live://{ADAPTER_ID}/{geometry_id}/horizons",
            f"live://{ADAPTER_ID}/{geometry_id}/restrictions",
            f"live://{ADAPTER_ID}/{geometry_id}/monthly_wetness",
        ],
    )
    derived["adapter"] = {
        "adapter_id": ADAPTER_ID,
        "canonical_source": "USDA_NRCS_SDA_SSURGO",
        "geometry_id": geometry_id,
        "edit_access_fetched": False,
    }
    return derived
