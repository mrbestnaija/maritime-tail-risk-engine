"""AST Architecture Boundary Verification Test.

MANDATORY AUDIT PROTOCOL:
This test MUST parse the Python Abstract Syntax Tree (AST) using `ast.parse` and
inspect `ast.Import` and `ast.ImportFrom` nodes. Naive string matching (e.g. checking
if the string 'import application' appears in the file) is strictly rejected as blind
and non-deterministic.

Enforces:
The Domain Core (`core/`) layer must have ZERO dependencies on outer layers
(`application/`, `infrastructure/`).
"""

from __future__ import annotations

import ast
from pathlib import Path
import pytest


def test_core_layer_ast_architecture_boundaries():
    """Verify via Python AST that core/ contains zero imports from application or infrastructure."""
    # Locate core directory
    test_file_dir = Path(__file__).resolve().parent
    engine_root = test_file_dir.parent.parent
    core_dir = engine_root / "core"

    assert core_dir.exists(), f"Core directory not found at {core_dir}"

    forbidden_modules = {"application", "infrastructure"}
    violations = []

    core_py_files = list(core_dir.rglob("*.py"))
    assert len(core_py_files) > 0, "No Python files found in core/"

    for py_file in core_py_files:
        content = py_file.read_text(encoding="utf-8")
        # Perform genuine AST parsing
        tree = ast.parse(content, filename=str(py_file))

        for node in ast.walk(tree):
            # 1. Check direct imports: `import application...`
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root_pkg = alias.name.split(".")[0]
                    if root_pkg in forbidden_modules:
                        violations.append(
                            f"{py_file.name}:{node.lineno} - Forbidden direct import '{alias.name}' "
                            f"from outer layer '{root_pkg}' detected via AST."
                        )

            # 2. Check from imports: `from application.xyz import ...`
            elif isinstance(node, ast.ImportFrom) and node.module:
                root_pkg = node.module.split(".")[0]
                if root_pkg in forbidden_modules:
                    violations.append(
                        f"{py_file.name}:{node.lineno} - Forbidden from import '{node.module}' "
                        f"from outer layer '{root_pkg}' detected via AST."
                    )

    # Invariant enforcement
    assert not violations, (
        f"Clean Architecture Boundary Violation in core/:\n" + "\n".join(violations)
    )
