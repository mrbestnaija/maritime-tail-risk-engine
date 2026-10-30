"""Database Isolation & Sandbox Environment Guard.

Mandatory Invariant:
When `env_mode="sandbox"`, the execution environment MUST PHYSICALLY raise an
unrecoverable `PermissionError` if any attempt is made to open, connect to, or
mutate `prod_maritime_vintage.db`. A passive boolean flag or soft warning is
strictly forbidden.
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

PROD_DB_NAME = "prod_maritime_vintage.db"


def get_isolated_database_connection(
    env_mode: str,
    db_path: str | Path | None = None,
    **sqlite_kwargs,
) -> sqlite3.Connection:
    """Acquire an isolated SQLite connection with physical sandbox environment verification.
    
    Raises:
        PermissionError: If env_mode is 'sandbox' and db_path targets or contains 'prod_maritime_vintage.db'.
        ValueError: If env_mode is unrecognized.
    """
    mode = env_mode.strip().lower()
    if mode not in ("sandbox", "production", "testing"):
        raise ValueError(f"Unrecognized env_mode: '{env_mode}'. Must be 'sandbox', 'testing', or 'production'.")

    # --- MANDATORY AUDIT INVARIANT 4: PHYSICAL ISOLATION ENFORCEMENT ---
    if mode == "sandbox":
        if db_path is not None:
            db_str = str(db_path).replace("\\", "/")
            base_name = os.path.basename(db_str)
            if PROD_DB_NAME in db_str or base_name == PROD_DB_NAME:
                raise PermissionError(
                    f"PHYSICAL ISOLATION BREACH: Environment mode 'sandbox' physically prohibited "
                    f"from accessing production database: '{PROD_DB_NAME}'."
                )

        # In sandbox mode, default to in-memory database if no path specified
        target = str(db_path) if db_path is not None else ":memory:"
        conn = sqlite3.connect(target, **sqlite_kwargs)
        # Enable foreign keys and verification
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    elif mode in ("production", "testing"):
        target = str(db_path) if db_path is not None else PROD_DB_NAME
        conn = sqlite3.connect(target, **sqlite_kwargs)
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    raise PermissionError("Access denied.")
