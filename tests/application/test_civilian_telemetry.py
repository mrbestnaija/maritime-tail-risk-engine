"""Test Suite for Civilian Multi-Sensor OSINT Telemetry.

Validates:
1. CivilianSensorTelemetry domain entity temporal paradox enforcement (TemporalParadoxError)
2. Physical MetOcean small-skiff boarding constraint (Hs in [0.0, 25.0] m)
3. Spaceborne SAR dark vessel ratio bounds ([0.0, 1.0])
4. Pydantic frozen model immutability
5. SQLite persistence and strict bi-temporal point-in-time retrieval
6. Complete ingestion and SHA-256 cryptographic lineage tracking of 36+ row telemetry dataset
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import sqlite3
import pytest
from pydantic import ValidationError

from core.models import CivilianSensorTelemetry, TemporalParadoxError
from infrastructure.osint_feed_loader import OSINTFeedLoader
from infrastructure.sqlite_storage import SCHEMA_SQL, SQLiteIncidentRepository, SQLiteTelemetryRepository


def test_civilian_telemetry_model_valid():
    """Verify valid CivilianSensorTelemetry instantiation."""
    now = datetime.now(timezone.utc)
    tel = CivilianSensorTelemetry(
        telemetry_id="TEL-TEST-001",
        corridor_id="GOG_BONNY_BRASS_FAIRWAY",
        observation_timestamp=now,
        publication_timestamp=now + timedelta(hours=3),
        sar_provider="GFW_SENTINEL1_SAR",
        metocean_provider="COPERNICUS_ERA5_METOCEAN",
        ais_provider="IMF_PORTWATCH_AIS",
        significant_wave_height_m=1.45,
        sar_dark_vessel_ratio=0.22,
        anchorage_waiting_hours=32.0,
        viirs_flaring_continuity_idx=0.94,
    )
    assert tel.telemetry_id == "TEL-TEST-001"
    assert tel.significant_wave_height_m == 1.45
    assert tel.sar_dark_vessel_ratio == 0.22


def test_civilian_telemetry_temporal_paradox_raises_error():
    """Publication timestamp preceding observation timestamp must raise TemporalParadoxError."""
    now = datetime.now(timezone.utc)
    with pytest.raises((TemporalParadoxError, ValidationError, ValueError)):
        CivilianSensorTelemetry(
            telemetry_id="TEL-PARADOX",
            corridor_id="GOG_BONNY_BRASS_FAIRWAY",
            observation_timestamp=now,
            publication_timestamp=now - timedelta(hours=2),  # earlier than observation!
            significant_wave_height_m=1.5,
            sar_dark_vessel_ratio=0.2,
            anchorage_waiting_hours=24.0,
        )


def test_civilian_telemetry_physical_constraints():
    """Out of bound wave height and dark vessel ratio must fail validation."""
    now = datetime.now(timezone.utc)
    later = now + timedelta(hours=2)

    # Wave height > 25.0m
    with pytest.raises(ValidationError):
        CivilianSensorTelemetry(
            telemetry_id="TEL-WAVE-ERR",
            corridor_id="GOG_BONNY_BRASS_FAIRWAY",
            observation_timestamp=now,
            publication_timestamp=later,
            significant_wave_height_m=28.0,
            sar_dark_vessel_ratio=0.2,
            anchorage_waiting_hours=24.0,
        )

    # SAR ratio > 1.0
    with pytest.raises(ValidationError):
        CivilianSensorTelemetry(
            telemetry_id="TEL-SAR-ERR",
            corridor_id="GOG_BONNY_BRASS_FAIRWAY",
            observation_timestamp=now,
            publication_timestamp=later,
            significant_wave_height_m=1.5,
            sar_dark_vessel_ratio=1.4,
            anchorage_waiting_hours=24.0,
        )


def test_civilian_telemetry_frozen_immutability():
    """CivilianSensorTelemetry is frozen (immutable) after construction."""
    now = datetime.now(timezone.utc)
    tel = CivilianSensorTelemetry(
        telemetry_id="TEL-FROZEN",
        corridor_id="GOG_BONNY_BRASS_FAIRWAY",
        observation_timestamp=now,
        publication_timestamp=now + timedelta(hours=1),
        significant_wave_height_m=1.5,
        sar_dark_vessel_ratio=0.15,
        anchorage_waiting_hours=12.0,
    )
    with pytest.raises(TypeError):
        tel.significant_wave_height_m = 2.0  # type: ignore


def test_sqlite_bitemporal_point_in_time_filtering():
    """Verify that SQLiteTelemetryRepository strictly filters by publication_timestamp <= as_of_time."""
    conn = sqlite3.connect(":memory:")
    repo = SQLiteTelemetryRepository(conn)

    t0 = datetime(2023, 1, 15, 6, 0, 0, tzinfo=timezone.utc)
    t1_pub = datetime(2023, 1, 15, 8, 0, 0, tzinfo=timezone.utc)
    t2_pub = datetime(2023, 1, 15, 14, 0, 0, tzinfo=timezone.utc)
    t3_pub = datetime(2023, 1, 16, 10, 0, 0, tzinfo=timezone.utc)

    tel1 = CivilianSensorTelemetry(
        telemetry_id="TEL-001",
        corridor_id="GOG_BONNY_BRASS_FAIRWAY",
        observation_timestamp=t0,
        publication_timestamp=t1_pub,
        significant_wave_height_m=1.2,
        sar_dark_vessel_ratio=0.1,
        anchorage_waiting_hours=20.0,
    )
    tel2 = CivilianSensorTelemetry(
        telemetry_id="TEL-002",
        corridor_id="GOG_BONNY_BRASS_FAIRWAY",
        observation_timestamp=t0 + timedelta(hours=4),
        publication_timestamp=t2_pub,
        significant_wave_height_m=1.3,
        sar_dark_vessel_ratio=0.15,
        anchorage_waiting_hours=22.0,
    )
    tel3 = CivilianSensorTelemetry(
        telemetry_id="TEL-003",
        corridor_id="GOG_BONNY_BRASS_FAIRWAY",
        observation_timestamp=t0 + timedelta(hours=20),
        publication_timestamp=t3_pub,
        significant_wave_height_m=1.8,
        sar_dark_vessel_ratio=0.25,
        anchorage_waiting_hours=35.0,
    )

    repo.insert_telemetry_batch([tel1, tel2, tel3])

    # Query as of 2023-01-15 10:00:00 UTC -> Only TEL-001 was published
    as_of_10am = datetime(2023, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
    res_10am = repo.load_telemetry_point_in_time(as_of_time=as_of_10am)
    assert len(res_10am) == 1
    assert res_10am[0].telemetry_id == "TEL-001"

    # Query as of 2023-01-15 15:00:00 UTC -> TEL-001 and TEL-002 published
    as_of_3pm = datetime(2023, 1, 15, 15, 0, 0, tzinfo=timezone.utc)
    res_3pm = repo.load_telemetry_point_in_time(as_of_time=as_of_3pm)
    assert len(res_3pm) == 2
    assert [r.telemetry_id for r in res_3pm] == ["TEL-001", "TEL-002"]

    # Query as of 2023-01-17 00:00:00 UTC -> All 3 published
    as_of_next_day = datetime(2023, 1, 17, 0, 0, 0, tzinfo=timezone.utc)
    res_all = repo.load_telemetry_point_in_time(as_of_time=as_of_next_day)
    assert len(res_all) == 3


def test_36_row_civilian_telemetry_dataset_ingestion():
    """Verify data/gog_bonny_brass_civilian_telemetry.json contains 36+ valid rows with SHA-256."""
    test_dir = Path(__file__).resolve().parent
    engine_root = test_dir.parent.parent
    telemetry_file = engine_root / "data" / "gog_bonny_brass_civilian_telemetry.json"

    assert telemetry_file.exists(), f"Telemetry file missing at {telemetry_file}"

    telemetries, sha256_hash = OSINTFeedLoader.load_civilian_telemetry_from_json(telemetry_file)

    assert len(telemetries) >= 36, f"Expected at least 36 rows, got {len(telemetries)}"
    assert len(sha256_hash) == 64, "SHA-256 digest must be 64 hexadecimal characters"

    for tel in telemetries:
        assert tel.corridor_id == "GOG_BONNY_BRASS_FAIRWAY"
        assert 0.0 <= tel.significant_wave_height_m <= 25.0
        assert 0.0 <= tel.sar_dark_vessel_ratio <= 1.0
        assert tel.anchorage_waiting_hours >= 0.0
        assert 0.0 <= tel.viirs_flaring_continuity_idx <= 1.0
        assert tel.publication_timestamp >= tel.observation_timestamp
