"""Derivation and growth policy for backend compatibility-shim allowlists."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_BOUNDARY_TEST = _PROJECT_ROOT / "tests" / "_guardrails" / "test_backend_boundaries.py"
_ALLOWLIST_NAME = "LAZY_WEB_IMPORT_ALLOWLIST"


def _literal_allowlist() -> set[tuple[str, str]]:
    tree = ast.parse(_BOUNDARY_TEST.read_text(encoding="utf-8"), filename=str(_BOUNDARY_TEST))
    assignment = next(
        node
        for node in tree.body
        if isinstance(node, (ast.Assign, ast.AnnAssign))
        and any(
            isinstance(target, ast.Name) and target.id == _ALLOWLIST_NAME
            for target in (node.targets if isinstance(node, ast.Assign) else [node.target])
        )
    )
    value = assignment.value
    if not (
        isinstance(value, ast.Call)
        and isinstance(value.func, ast.Name)
        and value.func.id == "frozenset"
        and len(value.args) == 1
        and not value.keywords
    ):
        raise AssertionError(f"{_ALLOWLIST_NAME} must remain one literal frozenset")
    parsed = ast.literal_eval(value.args[0])
    if not isinstance(parsed, set) or not all(
        isinstance(item, tuple) and len(item) == 2 and all(isinstance(part, str) for part in item)
        for item in parsed
    ):
        raise AssertionError(f"{_ALLOWLIST_NAME} must contain only (module, scope) strings")
    return parsed


def derive_backend_boundary() -> dict[str, list[dict[str, str]]]:
    """Return the exact current lazy public-type-to-Web compatibility edges."""
    return {
        "lazy_web_import_allowlist": [
            {"module": module, "scope": scope} for module, scope in sorted(_literal_allowlist())
        ]
    }


def _entries(value: object) -> set[tuple[str, str]]:
    if not isinstance(value, dict):
        raise TypeError("backend-boundary baseline must be a JSON object")
    rows: Any = value.get("lazy_web_import_allowlist")
    if not isinstance(rows, list):
        raise TypeError("lazy_web_import_allowlist must be a JSON list")
    return {(row["module"], row["scope"]) for row in rows}


def backend_boundary_growth(previous: object, current: object) -> list[str]:
    """Describe newly added compatibility edges; removals are always permitted."""
    return [
        f"lazy_web_import_allowlist: added {module}.{scope}"
        for module, scope in sorted(_entries(current) - _entries(previous))
    ]
