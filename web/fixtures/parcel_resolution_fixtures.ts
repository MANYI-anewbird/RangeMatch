import type { ParcelCandidate, ParcelResolution } from "../src/api/client";

const polyA = {
  type: "FeatureCollection",
  features: [
    {
      type: "Feature",
      id: "DEMO_PARCEL_001",
      properties: {},
      geometry: {
        type: "Polygon",
        coordinates: [
          [
            [-104.9, 40.5],
            [-104.89, 40.5],
            [-104.89, 40.49],
            [-104.9, 40.49],
            [-104.9, 40.5],
          ],
        ],
      },
    },
  ],
};

const polyB = {
  type: "FeatureCollection",
  features: [
    {
      type: "Feature",
      id: "DEMO_PARCEL_B",
      properties: {},
      geometry: {
        type: "Polygon",
        coordinates: [
          [
            [-104.889, 40.5],
            [-104.879, 40.5],
            [-104.879, 40.49],
            [-104.889, 40.49],
            [-104.889, 40.5],
          ],
        ],
      },
    },
  ],
};

export const HASH_A =
  "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa";
export const HASH_B =
  "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb";

export const candidateA: ParcelCandidate = {
  candidate_id: "cand_demo_001",
  label: "Demo Ranch Parcel A",
  parcel_geometry: polyA,
  source_crs: "EPSG:4326",
  geometry_hash: HASH_A,
  validation_status: "VALID",
  validation_errors: [],
};

export const candidateB: ParcelCandidate = {
  candidate_id: "cand_demo_B",
  label: "East tract",
  parcel_geometry: polyB,
  source_crs: "EPSG:4326",
  geometry_hash: HASH_B,
  validation_status: "VALID",
  validation_errors: [],
};

export function oneCandidateResolution(
  overrides: Partial<ParcelResolution> = {},
): ParcelResolution {
  return {
    resolution_id: "pres_one_demo",
    status: "NEEDS_BOUNDARY_CONFIRMATION",
    normalized_address: "100 Demo Ranch Rd, Weld County, CO 80701",
    input: {
      raw_address: "100 Demo Ranch Rd, Weld County, CO 80701",
      normalized_address: "100 Demo Ranch Rd, Weld County, CO 80701",
    },
    candidates: [candidateA],
    selection: {
      selected_candidate_id: "cand_demo_001",
      confirmed_at: null,
      confirmation_method: "PENDING",
    },
    confirmation_status: { confirmed: false },
    confirmed_parcel: null,
    evidence_invalidation_required: false,
    provenance: { provider: "FIXTURE" },
    limitations: ["Demo fixture"],
    errors: [],
    ...overrides,
  };
}

export function multiCandidateResolution(
  overrides: Partial<ParcelResolution> = {},
): ParcelResolution {
  return {
    resolution_id: "pres_multi_demo",
    status: "NEEDS_USER_SELECTION",
    normalized_address: "200 Split Ranch Rd, Weld County, CO 80701",
    input: {
      raw_address: "200 Split Ranch Rd, Weld County, CO 80701",
      normalized_address: "200 Split Ranch Rd, Weld County, CO 80701",
    },
    candidates: [candidateA, candidateB],
    selection: {
      selected_candidate_id: null,
      confirmed_at: null,
      confirmation_method: "PENDING",
    },
    confirmation_status: { confirmed: false },
    confirmed_parcel: null,
    evidence_invalidation_required: false,
    provenance: { provider: "FIXTURE" },
    limitations: ["Demo fixture"],
    errors: [],
    ...overrides,
  };
}

export function confirmedResolution(
  base: ParcelResolution = oneCandidateResolution(),
): ParcelResolution {
  return {
    ...base,
    status: "PARCEL_CONFIRMED",
    confirmation_status: {
      confirmed: true,
      selected_candidate_id: "cand_demo_001",
      confirmation_method: "USER_BOUNDARY_CONFIRMATION",
    },
    selection: {
      selected_candidate_id: "cand_demo_001",
      confirmed_at: "2026-08-08T12:00:00+00:00",
      confirmation_method: "USER_BOUNDARY_CONFIRMATION",
    },
    confirmed_parcel: {
      parcel_geometry: polyA,
      geometry_id: "DEMO_PARCEL_001",
      geometry_reference: "fixture:cand_demo_001",
      geometry_hash: HASH_A,
      source_crs: "EPSG:4326",
    },
    planner_binding: {
      parcel_geometry: polyA,
      geometry_id: "DEMO_PARCEL_001",
      geometry_reference: "fixture:cand_demo_001",
      geometry_hash: HASH_A,
      source_crs: "EPSG:4326",
    },
  };
}

export const blockedLiveResolution: ParcelResolution = {
  resolution_id: "pres_live_blocked",
  status: "BLOCKED_EXTERNAL",
  normalized_address: "123 Main St, Denver, CO 80202",
  candidates: [],
  confirmation_status: { confirmed: false },
  confirmed_parcel: null,
  limitations: [
    "LIVE parcel/geocode provider is not configured in this slice.",
    "CPER/demo fixtures were not substituted.",
  ],
  errors: [{ code: "BLOCKED_EXTERNAL", message: "provider blocked" }],
  provenance: { provider: "LIVE" },
};
