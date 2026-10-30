"""Test Suite for Database Isolation & Physical Sandbox Boundary.

MANDATORY AUDIT PROTOCOL:
If `env_mode="sandbox"`, the code MUST PHYSICALLY raise an unrecoverable
`PermissionError` when attempting to open or connect to `prod_maritime_vintage.db`.
A passive boolean flag or advisory warning is unacceptable.
"""

from __future__ import annotations

import pytest
from application.isolation import get_isolated_database_connection, PROD_DB_NAME


def test_sandbox_physically_raises_permission_error_on_prod_db():
    """Verify that sandbox mode physically raises PermissionError when targeting prod_maritime_vintage.db."""
    with pytest.raises(PermissionError) as exc_info:
        # Attempt to open production DB while in sandbox mode
        get_isolated_database_connection(
            env_mode="sandbox",
            db_path=PROD_DB_NAME,
        )

    # Invariant: Must be a physical error stating isolation breach
    assert "PHYSICAL ISOLATION BREACH" in str(exc_info.value)
    assert PROD_DB_NAME in str(exc_info.value)


def test_sandbox_allows_in_memory_or_temp_db():
    """Verify sandbox mode succeeds cleanly for in-memory or throwaway test databases."""
    conn = get_isolated_database_connection(env_mode="sandbox", db_path=":memory:")
    assert conn is not None
    cursor = conn.execute("SELECT 1;")
    assert cursor.fetchone()[0] == 1
    conn.close()


def test_invalid_env_mode_rejected():
    """Verify unrecognized environment mode raises ValueError."""
    with pytest.raises(ValueError):
        get_isolated_database_connection(env_mode="invalid_unrecognized_mode")
