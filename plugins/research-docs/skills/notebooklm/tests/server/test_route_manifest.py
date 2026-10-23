"""Exact REST method/path inventory for the supported adapter surface."""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ROUTES = ROOT / "src" / "notebooklm" / "server" / "routes"
HTTP_METHODS = frozenset({"delete", "get", "patch", "post", "put"})

EXPECTED_ROUTES = frozenset(
    {
        # Notebooks
        ("GET", "/v1/notebooks"),
        ("POST", "/v1/notebooks"),
        ("GET", "/v1/notebooks/{notebook_id}"),
        ("PATCH", "/v1/notebooks/{notebook_id}"),
        ("DELETE", "/v1/notebooks/{notebook_id}"),
        ("GET", "/v1/notebooks/{notebook_id}/suggested-prompts"),
        # Sources
        ("GET", "/v1/notebooks/{notebook_id}/sources"),
        ("GET", "/v1/notebooks/{notebook_id}/sources/{source_id}"),
        ("GET", "/v1/notebooks/{notebook_id}/sources/{source_id}/content"),
        ("POST", "/v1/notebooks/{notebook_id}/sources/url"),
        ("POST", "/v1/notebooks/{notebook_id}/sources/text"),
        ("POST", "/v1/notebooks/{notebook_id}/sources/file"),
        ("POST", "/v1/notebooks/{notebook_id}/sources/drive"),
        ("POST", "/v1/notebooks/{notebook_id}/sources/batch"),
        ("POST", "/v1/notebooks/{notebook_id}/sources/wait"),
        ("PATCH", "/v1/notebooks/{notebook_id}/sources/{source_id}"),
        ("DELETE", "/v1/notebooks/{notebook_id}/sources/{source_id}"),
        # Notes and chat
        ("GET", "/v1/notebooks/{notebook_id}/notes"),
        ("POST", "/v1/notebooks/{notebook_id}/notes"),
        ("GET", "/v1/notebooks/{notebook_id}/notes/{note_id}"),
        ("PUT", "/v1/notebooks/{notebook_id}/notes/{note_id}"),
        ("DELETE", "/v1/notebooks/{notebook_id}/notes/{note_id}"),
        ("POST", "/v1/notebooks/{notebook_id}/chat"),
        ("POST", "/v1/notebooks/{notebook_id}/chat/configure"),
        # Artifacts
        ("GET", "/v1/notebooks/{notebook_id}/artifacts"),
        ("POST", "/v1/notebooks/{notebook_id}/artifacts"),
        ("GET", "/v1/notebooks/{notebook_id}/artifacts/{task_id}"),
        ("GET", "/v1/notebooks/{notebook_id}/artifacts/{artifact_id}/prompt"),
        ("PATCH", "/v1/notebooks/{notebook_id}/artifacts/{artifact_id}"),
        ("POST", "/v1/notebooks/{notebook_id}/artifacts/{artifact_id}/retry"),
        ("DELETE", "/v1/notebooks/{notebook_id}/artifacts/{artifact_id}"),
        ("POST", "/v1/notebooks/{notebook_id}/artifacts/download"),
        # Research and sharing
        ("POST", "/v1/notebooks/{notebook_id}/research"),
        ("GET", "/v1/notebooks/{notebook_id}/research/{run_id}"),
        ("DELETE", "/v1/notebooks/{notebook_id}/research/{run_id}"),
        ("POST", "/v1/notebooks/{notebook_id}/research/{run_id}/import"),
        ("GET", "/v1/notebooks/{notebook_id}/share"),
        ("POST", "/v1/notebooks/{notebook_id}/share/public"),
        ("POST", "/v1/notebooks/{notebook_id}/share/users"),
        ("PATCH", "/v1/notebooks/{notebook_id}/share/users/{email}"),
        ("DELETE", "/v1/notebooks/{notebook_id}/share/users/{email}"),
        ("POST", "/v1/notebooks/{notebook_id}/share/view-level"),
        # Process metadata
        ("GET", "/v1/server/info"),
    }
)


def _literal_string(node: ast.AST) -> str | None:
    return node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else None


def _route_prefix(tree: ast.Module) -> str | None:
    for node in tree.body:
        if not isinstance(node, ast.Assign) or not any(
            isinstance(target, ast.Name) and target.id == "router" for target in node.targets
        ):
            continue
        if not isinstance(node.value, ast.Call):
            continue
        for keyword in node.value.keywords:
            if keyword.arg == "prefix":
                return _literal_string(keyword.value)
    return None


def _route_inventory() -> frozenset[tuple[str, str]]:
    found: set[tuple[str, str]] = set()
    for path in sorted(ROUTES.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        prefix = _route_prefix(tree)
        if prefix is None:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef)):
                continue
            for decorator in node.decorator_list:
                if (
                    not isinstance(decorator, ast.Call)
                    or not isinstance(decorator.func, ast.Attribute)
                    or not isinstance(decorator.func.value, ast.Name)
                    or decorator.func.value.id != "router"
                    or decorator.func.attr not in HTTP_METHODS
                    or not decorator.args
                ):
                    continue
                suffix = _literal_string(decorator.args[0])
                if suffix is not None:
                    found.add((decorator.func.attr.upper(), f"/v1{prefix}{suffix}"))
    return frozenset(found)


def test_rest_route_manifest_is_exact() -> None:
    """A REST capability change requires an explicit supported-surface update."""
    assert _route_inventory() == EXPECTED_ROUTES
    assert len(EXPECTED_ROUTES) == 43
