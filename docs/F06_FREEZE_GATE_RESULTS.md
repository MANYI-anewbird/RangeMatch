# F06 Parcel Configuration Freeze Gate Results

> Status: `PASSED — FROZEN_V0_1`
> Date: 2026-08-08
> Full test suite: `133 passed`

## Decision

F06 Parcel Configuration v0.1 is frozen for the RangeMatch demo. F07 Road and Physical Access Context is authorized for first-stage audit only.

## Gate evidence

- Canonical source is the declared parcel geometry.
- v0.1 accepts `EPSG:4326` source coordinates only and records the projected local UTM working CRS.
- Planar longitude/latitude measurement is prohibited.
- FeatureCollection requires exactly one Feature; zero or multiple Features fail closed to `NEEDS_VERIFICATION` without silent first-feature selection or automatic union.
- Longitude/latitude and supported-UTM bounds fail closed.
- Area subtracts interior rings under standard polygon semantics.
- Perimeter includes exterior rings only; holes are recorded as a limitation.
- Compactness uses `4πA/P²` without classification or threshold.
- International acres are display-only; canonical area remains square meters.
- Invalid geometry is not automatically repaired.
- Geometry replacement invalidates F06 evidence and requires recomputation.
- Complete geometry produces `CONTEXT_DEPENDENT`; missing or unusable inputs produce `UNKNOWN` or `NEEDS_VERIFICATION`.
- `ranking_effect` remains `NONE`; Cow-Calf and Sheep remain peers.
- No acreage/compactness suitability thresholds, fencing cost, carrying capacity, profitability, road-access claim, or species ranking is emitted.

## CPER result

```yaml
factor_id: F06_PARCEL_CONFIGURATION
input_quality_state: PARCEL_GEOMETRY_COMPLETE
signal: CONTEXT_DEPENDENT
ranking_effect: NONE
working_crs: EPSG:32613
geometry_validity: VALID
```

The CPER fixture is engineering evidence and not a legal survey or suitability ground truth.

## Verification

The full suite was independently rerun with:

```bash
PYTHONPATH=src .venv-livegate/bin/python -m unittest discover -s tests
```

Result: `Ran 133 tests ... OK`.

## Remaining limitations

- Geodesic comparison QA is deferred.
- UTM-zone-crossing parcels are unsupported in v0.1.
- Hole-ring perimeter, boundary complexity, narrow-section context, and automatic geometry repair are deferred.
- F06 does not establish road or legal access; that boundary belongs to F07.

## Next authorization

```yaml
f06_freeze_status: FROZEN_V0_1
f07_authorization: AUTHORIZED_FOR_FIRST_STAGE_AUDIT
f08_authorization: NOT_YET_AUTHORIZED
```
