"""RangeMatch deterministic MVP engine."""

from .demo_report import build_demo_closure_payload, write_demo_closure
from .engine import evaluate_land_profile
from .explanation import explain_match_result
from .f04_derivation import derive_available_water_storage, derive_f04_from_fixture_dir
from .f06_derivation import derive_f06_from_geometry_path, evaluate_f06_signal
from .f07_derivation import derive_f07_from_inputs, evaluate_f07_signal
from .f07_tiger_adapter import derive_f07_via_tiger_adapter, run_cper_f07_live_gate
from .f08_derivation import (
    derive_f08_from_coverV3_artifact,
    derive_f08_reusing_f02_artifact,
    evaluate_f08_signal,
    run_cper_f08_data_reuse_gate,
)
from .geometry_replace import replace_geometry, write_replaced_profile
from .planner import build_investigation_plan
from .unified_output import (
    hash_match_result,
    project_unified_output,
    validate_unified_output,
)

__all__ = [
    "evaluate_land_profile",
    "derive_f04_from_fixture_dir",
    "derive_available_water_storage",
    "derive_f06_from_geometry_path",
    "evaluate_f06_signal",
    "derive_f07_from_inputs",
    "evaluate_f07_signal",
    "derive_f07_via_tiger_adapter",
    "run_cper_f07_live_gate",
    "derive_f08_from_coverV3_artifact",
    "derive_f08_reusing_f02_artifact",
    "evaluate_f08_signal",
    "run_cper_f08_data_reuse_gate",
    "explain_match_result",
    "build_demo_closure_payload",
    "write_demo_closure",
    "replace_geometry",
    "write_replaced_profile",
    "project_unified_output",
    "validate_unified_output",
    "hash_match_result",
    "build_investigation_plan",
]

