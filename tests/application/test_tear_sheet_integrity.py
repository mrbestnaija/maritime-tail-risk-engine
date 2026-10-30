"""Test Suite for Tear Sheet Integrity & Forensic Compliance.

MANDATORY AUDIT PROTOCOL:
Validates that `PHASE1_VINTAGE_AUDIT_GOG_BONNY_BRASS_FAIRWAY.md`:
1. Contains the exact `COMMERCIAL_DISCLAIMER` verbatim.
2. Contains the complete `IDENTITY & AUDIT BLOCK`.
3. Displays the SHA-256 cryptographic lineage hash of the ingested dataset.
4. Quantifies reporting-lag blind-spot distortion metrics.
"""

from __future__ import annotations

import sys
from pathlib import Path
import pytest

# Ensure engine directory is on sys.path regardless of where pytest is invoked from
_engine_dir = str(Path(__file__).resolve().parent.parent.parent)
if _engine_dir not in sys.path:
    sys.path.insert(0, _engine_dir)

from generate_tear_sheet import COMMERCIAL_DISCLAIMER, run_phase1_audit


def test_tear_sheet_contains_mandatory_disclaimer_and_sha256(tmp_path: Path):
    """Verify tear sheet contains exact disclaimer, identity block, and SHA-256 hash."""
    test_dir = Path(__file__).resolve().parent
    engine_root = test_dir.parent.parent
    dataset_file = engine_root / "data" / "sample_gog_osint_vintage.csv"
    out_file = tmp_path / "TEST_TEAR_SHEET.md"

    res = run_phase1_audit(dataset_file, out_file)

    content = out_file.read_text(encoding="utf-8")

    # --- MANDATORY AUDIT PROTOCOL 3: DISCLAIMER INTEGRITY ---
    assert COMMERCIAL_DISCLAIMER in content, (
        "Tear sheet is missing the exact verbatim COMMERCIAL_DISCLAIMER"
    )

    # --- MANDATORY AUDIT PROTOCOL 3: IDENTITY BLOCK ---
    assert "### IDENTITY & AUDIT BLOCK" in content
    assert "Gulf of Guinea (GoG) - Bonny / Brass Fairway" in content
    assert "Python-Native Verification" in content

    # --- MANDATORY AUDIT PROTOCOL 3: DATASET SHA-256 LINEAGE HASH ---
    expected_hash = res["dataset_sha256"]
    assert len(expected_hash) == 64, "SHA-256 digest must be 64 hexadecimal characters"
    assert f"Dataset SHA-256 Lineage Hash**: `{expected_hash}`" in content, (
        f"Tear sheet must explicitly publish dataset SHA-256 lineage hash ({expected_hash})"
    )

    # Reporting lag blind spot distortion check
    assert "Reporting-Lag Blind-Spot Distortion Analysis" in content
    assert "Mean Reporting Lag" in content
    assert "Underwriter Blind-Spot Hazard" in content

    # Underwriter tail risk metrics check
    assert "Value at Risk" in content
    assert "Expected Shortfall" in content
    assert "Union Envelope Severity" in content
