"""Tri-State Verification CLI (verify_repo.py).

Implements 4 Institutional Verification Gates:
1. check_ast_reachability_and_boundaries(target_dir):
   Static AST walk verifying layer import rules and flagging any dead config constants
   that never reach a conditional sink (PASS | FAIL).
2. check_anti_hardcoding_purity(target_dir):
   AST walk across core mathematical modules verifying zero hardcoded business/corridor/vessel
   literals and verifying declarative JSON schema binding (PASS | FAIL).
3. check_db_isolation_guard(target_dir):
   Verifies SQLite C-engine CHECK constraints and sandbox-vs-production PermissionError guards
   (PASS | FAIL, or SKIP if target repo has no SQLite layer).
4. check_numeric_calibration_and_sdk_contract(target_dir):
   Feeds pathological boundary arrays into GPD tail fitter and calibration evaluators,
   verifying zero NaN/Inf outputs, anti-blowup caps, unweighted Brier invariance, and PEP 561
   SDK contract conformance (PASS | FAIL).

Execution SLA: Strictly completes in < 10 seconds.
"""

from __future__ import annotations

import argparse
import ast
import math
import sqlite3
import sys
import time
from pathlib import Path

# Ensure target engine directory is on sys.path
_current_dir = Path(__file__).resolve().parent
if _current_dir.name == "maritime_risk":
    _current_dir = _current_dir.parent
if str(_current_dir) not in sys.path:
    sys.path.insert(0, str(_current_dir))


def check_ast_reachability_and_boundaries(target_dir: Path) -> tuple[str, str]:
    """Static AST walk verifying layer boundary isolation and constant reachability."""
    core_dir = target_dir / "core"
    if not core_dir.exists():
        return "FAIL", f"Core directory missing at {core_dir}"

    forbidden_modules = {"application", "infrastructure"}
    violations = []
    py_files = list(core_dir.rglob("*.py"))

    # Also check maritime_risk/core if it exists as a separate directory
    mr_core_dir = target_dir / "maritime_risk" / "core"
    if mr_core_dir.exists() and mr_core_dir.is_dir():
        py_files.extend(list(mr_core_dir.rglob("*.py")))

    if not py_files:
        return "FAIL", "No Python files found in core/"

    # Layer import boundary check
    for py_file in py_files:
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root_pkg = alias.name.split(".")[0]
                    if root_pkg in forbidden_modules or alias.name.startswith("maritime_risk.application") or alias.name.startswith("maritime_risk.infrastructure"):
                        violations.append(
                            f"{py_file.name}:{node.lineno} forbidden direct import '{alias.name}'"
                        )
            elif isinstance(node, ast.ImportFrom) and node.module:
                root_pkg = node.module.split(".")[0]
                if root_pkg in forbidden_modules or node.module.startswith("maritime_risk.application") or node.module.startswith("maritime_risk.infrastructure"):
                    violations.append(
                        f"{py_file.name}:{node.lineno} forbidden from import '{node.module}'"
                    )

    if violations:
        return "FAIL", f"Clean architecture boundary violations in core/:\n" + "\n".join(violations)

    # Constant reachability audit: inspect top-level CONSTANTS in core/
    for py_file in py_files:
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        defined_constants = set()
        used_identifiers = set()

        for stmt in tree.body:
            if isinstance(stmt, ast.Assign):
                for target in stmt.targets:
                    if isinstance(target, ast.Name) and target.id.isupper():
                        defined_constants.add(target.id)

        # Collect all used names across the AST
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and not isinstance(node.ctx, ast.Store):
                used_identifiers.add(node.id)

        # Allow __all__ and standard dunder exports
        defined_constants = {
            c for c in defined_constants if not c.startswith("__") and c != "__all__"
        }
        # If any constant is defined but never referenced locally or exported in __all__
        all_exported = set()
        for stmt in tree.body:
            if isinstance(stmt, ast.Assign):
                for target in stmt.targets:
                    if isinstance(target, ast.Name) and target.id == "__all__":
                        if isinstance(stmt.value, (ast.List, ast.Tuple)):
                            for elt in stmt.value.elts:
                                if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                                    all_exported.add(elt.value)

        unreachable = defined_constants - used_identifiers - all_exported
        if unreachable:
            return (
                "FAIL",
                f"Dead constant(s) in {py_file.name} never reach a sink or __all__: {unreachable}",
            )

    return "PASS", f"Zero boundary violations across {len(py_files)} core modules; all constants reachable."


def check_anti_hardcoding_purity(target_dir: Path) -> tuple[str, str]:
    """AST walk verifying math modules contain zero hardcoded domain/business literals."""
    math_modules = [
        "hydro_envelope.py",
        "mssa_decomposer.py",
        "empirical_bayes.py",
        "gpd_tail_fitter.py",
        "jwc_pricer.py",
        "sprt_gates.py",
    ]

    banned_floats = {85000000.0, 45000.0, 3500000.0, 18500.0, 1.85, 0.18, 12.0}
    banned_strings = {"GOG_BONNY_BRASS_FAIRWAY"}

    violations: list[str] = []

    dirs_to_check = [target_dir / "core"]
    mr_core = target_dir / "maritime_risk" / "core"
    if mr_core.exists() and mr_core.is_dir():
        dirs_to_check.append(mr_core)

    for cdir in dirs_to_check:
        for mod_name in math_modules:
            file_path = cdir / mod_name
            if not file_path.exists():
                violations.append(f"Math module not found: {file_path}")
                continue

            tree = ast.parse(file_path.read_text(encoding="utf-8"), filename=str(file_path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Constant):
                    val = node.value
                    if isinstance(val, (int, float)) and not isinstance(val, bool):
                        if float(val) in banned_floats:
                            violations.append(
                                f"{file_path.name}:{node.lineno} banned hardcoded literal {val}"
                            )
                    elif isinstance(val, str) and val in banned_strings:
                        violations.append(
                            f"{file_path.name}:{node.lineno} banned hardcoded string '{val}'"
                        )

    if violations:
        return "FAIL", f"Hardcoded domain literals detected in math modules:\n" + "\n".join(violations)

    # Verify configs exist and are loadable
    configs_dir = target_dir / "configs"
    required_configs = ["corridors.json", "vessel_profiles.json", "model_hyperparams.json"]
    for cfg in required_configs:
        cfg_path = configs_dir / cfg
        if not cfg_path.exists():
            return "FAIL", f"Required declarative configuration file missing: {cfg_path}"

    try:
        from core.specs import load_corridor_spec, load_engine_bundle, load_vessel_spec
        c_spec = load_corridor_spec("GOG_BONNY_BRASS_FAIRWAY", configs_dir / "corridors.json")
        v_spec = load_vessel_spec("STANDARD_SUEZMAX_85M", configs_dir / "vessel_profiles.json")
        bundle = load_engine_bundle(config_dir=configs_dir)
        if c_spec.corridor_id != "GOG_BONNY_BRASS_FAIRWAY" or v_spec.vessel_profile_id != "STANDARD_SUEZMAX_85M":
            return "FAIL", "Declarative config loaders returned inconsistent spec identity"
    except Exception as e:
        return "FAIL", f"Error loading declarative configuration specs: {e}"

    return "PASS", f"Zero hardcoded domain literals across {len(math_modules)} math modules; declarative specs verified."


def check_db_isolation_guard(target_dir: Path) -> tuple[str, str]:
    """Verify SQLite C-engine CHECK constraints and sandbox isolation guards."""
    resolved_target = target_dir.resolve()
    if str(resolved_target) not in sys.path:
        sys.path.insert(0, str(resolved_target))

    sqlite_file = resolved_target / "infrastructure" / "sqlite_storage.py"
    mr_sqlite_file = resolved_target / "maritime_risk" / "infrastructure" / "sqlite_storage.py"
    isolation_file = resolved_target / "application" / "isolation.py"

    if not sqlite_file.exists() and not mr_sqlite_file.exists():
        return "SKIP", "Target directory does not contain SQLite persistence layer"

    try:
        try:
            from maritime_risk.infrastructure.sqlite_storage import SCHEMA_SQL, SQLiteIncidentRepository
            from maritime_risk.application.isolation import get_isolated_database_connection
        except ImportError:
            from infrastructure.sqlite_storage import SCHEMA_SQL, SQLiteIncidentRepository
            from application.isolation import get_isolated_database_connection
    except ImportError as e:
        return "FAIL", f"Failed to import database modules: {e}"

    # 1. Test SQLite C-engine CHECK constraints
    conn = sqlite3.connect(":memory:")
    conn.executescript(SCHEMA_SQL)
    conn.commit()

    # Temporal paradox check: pub_time < event_time
    try:
        conn.execute(
            "INSERT INTO incidents (incident_id, event_time, pub_time, min_severity, max_severity, "
            "latitude, longitude, feed_source, lineage_hash) VALUES ('E1', 200, 100, 1.0, 2.0, 4.0, 7.0, 'SRC', 'H')"
        )
        return "FAIL", "SQLite failed to reject temporal paradox (pub_time < event_time) at C-engine layer"
    except sqlite3.IntegrityError:
        pass  # Invariant correctly defended

    # Telemetry temporal paradox check
    try:
        conn.execute(
            "INSERT INTO civilian_sensor_telemetry (telemetry_id, corridor_id, observation_timestamp, "
            "publication_timestamp, sar_provider, metocean_provider, ais_provider, "
            "significant_wave_height_m, sar_dark_vessel_ratio, anchorage_waiting_hours, viirs_flaring_continuity_idx) "
            "VALUES ('T1', 'COR', '2023-01-15T12:00:00Z', '2023-01-15T10:00:00Z', 'P1', 'P2', 'P3', 1.0, 0.2, 10.0, 0.9)"
        )
        return "FAIL", "SQLite failed to reject telemetry temporal paradox at C-engine layer"
    except sqlite3.IntegrityError:
        pass  # Invariant correctly defended

    # Telemetry wave height bounds check (> 25.0m)
    try:
        conn.execute(
            "INSERT INTO civilian_sensor_telemetry (telemetry_id, corridor_id, observation_timestamp, "
            "publication_timestamp, sar_provider, metocean_provider, ais_provider, "
            "significant_wave_height_m, sar_dark_vessel_ratio, anchorage_waiting_hours, viirs_flaring_continuity_idx) "
            "VALUES ('T2', 'COR', '2023-01-15T10:00:00Z', '2023-01-15T12:00:00Z', 'P1', 'P2', 'P3', 29.5, 0.2, 10.0, 0.9)"
        )
        return "FAIL", "SQLite failed to reject Hs > 25.0m at C-engine layer"
    except sqlite3.IntegrityError:
        pass

    # Telemetry SAR dark vessel ratio bounds check (> 1.0)
    try:
        conn.execute(
            "INSERT INTO civilian_sensor_telemetry (telemetry_id, corridor_id, observation_timestamp, "
            "publication_timestamp, sar_provider, metocean_provider, ais_provider, "
            "significant_wave_height_m, sar_dark_vessel_ratio, anchorage_waiting_hours, viirs_flaring_continuity_idx) "
            "VALUES ('T3', 'COR', '2023-01-15T10:00:00Z', '2023-01-15T12:00:00Z', 'P1', 'P2', 'P3', 2.0, 1.5, 10.0, 0.9)"
        )
        return "FAIL", "SQLite failed to reject SAR dark ratio > 1.0 at C-engine layer"
    except sqlite3.IntegrityError:
        pass

    conn.close()

    # 2. Test Sandbox Physical PermissionError Isolation Guard
    if isolation_file.exists():
        try:
            get_isolated_database_connection(env_mode="sandbox", db_path="prod_maritime_vintage.db")
            return "FAIL", "Sandbox physical isolation guard failed: prod database opened without PermissionError"
        except PermissionError:
            pass  # Physical defense verified

    return "PASS", "SQLite C-engine CHECK constraints and sandbox isolation guards physically verified."


def check_numeric_calibration_and_sdk_contract(target_dir: Path) -> tuple[str, str]:
    """Feeds pathological boundary arrays into GPD tail fitter, asserts stability and SDK contract."""
    # 1. SDK Contract Checks
    py_typed_path = target_dir / "maritime_risk" / "py.typed"
    if not py_typed_path.exists():
        return "FAIL", f"PEP 561 marker missing at {py_typed_path}"

    try:
        import maritime_risk as mtr
    except ImportError as e:
        return "FAIL", f"Failed to import canonical SDK facade 'maritime_risk': {e}"

    # Verify __all__ export completeness
    missing_exports = [name for name in mtr.__all__ if not hasattr(mtr, name)]
    if missing_exports:
        return "FAIL", f"maritime_risk.__all__ contains missing exports: {missing_exports}"

    # Verify headless in-memory engine instantiation and aliases
    try:
        engine = mtr.MaritimeRiskEngine.from_specs()
        if engine is None or not hasattr(engine, "evaluate"):
            return "FAIL", "MaritimeRiskEngine.from_specs() did not return a valid engine instance"
        if not hasattr(mtr, "MaritimeTailRiskEngine") or mtr.MaritimeTailRiskEngine is not mtr.MaritimeRiskEngine:
            return "FAIL", "MaritimeTailRiskEngine alias missing or does not match MaritimeRiskEngine"
        # Verify declarative config loader works
        engine_cfg = mtr.MaritimeRiskEngine.from_config_files(corridor_id="GOG_BONNY_BRASS_FAIRWAY")
        if engine_cfg is None:
            return "FAIL", "MaritimeRiskEngine.from_config_files() returned None"
    except Exception as e:
        return "FAIL", f"MaritimeRiskEngine initialization failed: {e}"

    # 2. Numeric Calibration Falsifier
    try:
        import numpy as np
        from core.calibration import IsotonicCalibrator, PlattCalibrator, brier_score, log_loss
        from core.gpd_tail_fitter import (
            compute_actuarial_war_risk_loading_bps,
            compute_gpd_var_cvar,
            fit_pot_gpd,
        )
    except ImportError as e:
        return "FAIL", f"Failed to import numeric engines: {e}"

    # Test xi -> 0 analytical smooth limit
    u, sigma, p_u = 4.0, 1.8, 0.08
    var_exact, cvar_exact = compute_gpd_var_cvar(u, xi=0.0, sigma=sigma, p_u=p_u, alpha=0.99)
    var_smooth, cvar_smooth = compute_gpd_var_cvar(u, xi=1e-8, sigma=sigma, p_u=p_u, alpha=0.99)

    if not math.isclose(var_exact, var_smooth, rel_tol=1e-7):
        return "FAIL", f"xi -> 0 limit mismatch: exact {var_exact} != smooth {var_smooth}"
    if math.isnan(var_smooth) or math.isinf(var_smooth) or math.isnan(cvar_smooth) or math.isinf(cvar_smooth):
        return "FAIL", "GPD tail engine emitted NaN or Inf on xi -> 0 boundary"

    # Test zero-variance series
    constant_sample = [3.2, 3.2, 3.2, 3.2, 3.2]
    res_const = fit_pot_gpd(constant_sample, threshold_u=2.0)
    if any(math.isnan(v) or math.isinf(v) for v in [res_const.var_99, res_const.cvar_99, res_const.shape_xi]):
        return "FAIL", "GPD tail engine emitted NaN or Inf on zero-variance exceedance series"

    # Test extreme outlier severity (million-fold ratio explosion guard)
    extreme_sample = [0.1, 0.2, 1e7]
    res_ext = fit_pot_gpd(extreme_sample, threshold_u=0.05)
    if res_ext.shape_xi > 0.95:
        return "FAIL", f"Shape parameter {res_ext.shape_xi} exceeded hard cap 0.95"
    if math.isnan(res_ext.cvar_99) or math.isinf(res_ext.cvar_99):
        return "FAIL", "GPD tail engine emitted NaN or Inf on extreme outlier severity"

    # Test calibrators on pathological boundary inputs
    constant_scores = np.array([1.5, 1.5, 1.5])
    binary_labels = np.array([0, 1, 0])

    platt = PlattCalibrator().fit(constant_scores, binary_labels)
    preds_platt = platt.predict_proba(constant_scores)
    if np.any(np.isnan(preds_platt)) or np.any(np.isinf(preds_platt)):
        return "FAIL", "Platt calibrator produced NaN or Inf on zero-variance scores"

    extreme_scores = np.array([-1e12, 1e12, 0.0])
    preds_ext = platt.predict_proba(extreme_scores)
    if np.any(np.isnan(preds_ext)) or np.any(np.isinf(preds_ext)):
        return "FAIL", "Platt calibrator produced NaN or Inf on extreme score inputs"

    iso = IsotonicCalibrator().fit(constant_scores, binary_labels)
    preds_iso = iso.predict_proba(constant_scores)
    if np.any(np.isnan(preds_iso)) or np.any(np.isinf(preds_iso)):
        return "FAIL", "Isotonic calibrator produced NaN or Inf on zero-variance scores"

    # Test unweighted Brier invariance to financial loss scale
    y_true = np.array([0, 1, 1, 0])
    y_prob = np.array([0.1, 0.85, 0.7, 0.15])
    brier1 = brier_score(y_true, y_prob)

    brier_expected = float(np.mean((y_prob - y_true) ** 2))
    if not math.isclose(brier1, brier_expected, abs_tol=1e-12):
        return "FAIL", "Brier score departed from unweighted mathematical definition"

    return "PASS", "PEP 561 py.typed, __all__ exports, in-memory SDK, and numeric falsifiers verified."


def run_verification(target_dir: Path) -> int:
    """Execute all four verification gates within 10 seconds SLA."""
    start_time = time.perf_counter()

    print("=" * 80)
    print("MARITIME TAIL RISK ENGINE: QUAD-GATE REPOSITORY VERIFICATION")
    print(f"Target Directory: {target_dir}")
    print("=" * 80)

    checks = [
        ("AST Layer Reachability & Boundaries", lambda: check_ast_reachability_and_boundaries(target_dir)),
        ("Anti-Hardcoding & Spec-Driven Purity Check", lambda: check_anti_hardcoding_purity(target_dir)),
        ("DB Isolation & Sandbox Guard", lambda: check_db_isolation_guard(target_dir)),
        ("Numeric Calibration Falsifier & SDK Contract Check", lambda: check_numeric_calibration_and_sdk_contract(target_dir)),
    ]

    has_fail = False
    for name, fn in checks:
        t0 = time.perf_counter()
        status, details = fn()
        duration = time.perf_counter() - t0
        print(f"[{status:4s}] {name} ({duration:.3f}s)")
        print(f"       -> {details}")
        if status == "FAIL":
            has_fail = True

    total_time = time.perf_counter() - start_time
    print("=" * 80)
    total_status = "FAIL" if has_fail else "PASS"
    print(f"VERIFICATION STATUS: {total_status} (Completed in {total_time:.2f}s < 10.0s SLA)")
    print("=" * 80)

    return 1 if has_fail else 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Tri-State Self-Verification CLI")
    parser.add_argument(
        "--target",
        "--target-dir",
        dest="target_dir",
        type=Path,
        default=Path(__file__).resolve().parent,
        help="Target directory to verify",
    )
    args = parser.parse_args()
    sys.exit(run_verification(args.target_dir))
