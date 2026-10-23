"""Freeze the remaining 0.x auth-owned Web-bootstrap compatibility island."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

pytestmark = pytest.mark.repo_lint

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src" / "notebooklm"
AUTH_ROOT = SRC_ROOT / "_auth"

_EXPECTED_CALLERS = {
    "_auth.refresh._fetch_tokens_with_refresh_core",
    "_auth.refresh._cold_fallbacks.run_refresh_attempt",
    "_auth.refresh._cold_fallbacks.validate_recovered",
    "_auth.refresh._cold_fallbacks.fetch_recovered",
    "_auth.refresh.fetch_tokens_passive",
    "_auth.tokens._ProductionTokenAcquirer.acquire",
    "scripts.diagnose_get_notebook.run_diagnosis",
}
_WEB_TYPE_NAMES = {
    "AuthRefreshCoordinator",
    "CookiePersistence",
    "Kernel",
    "WebRuntime",
    "WebSessionAuth",
    "WebTransportLifecycle",
}


def _production_paths() -> list[Path]:
    return [
        *sorted(SRC_ROOT.rglob("*.py")),
        *sorted((REPO_ROOT / "scripts").rglob("*.py")),
    ]


def _module_label(path: Path) -> str:
    if path.is_relative_to(SRC_ROOT):
        return path.relative_to(SRC_ROOT).with_suffix("").as_posix().replace("/", ".")
    return path.relative_to(REPO_ROOT).with_suffix("").as_posix().replace("/", ".")


def _direct_callers(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    callers: set[str] = set()
    direct_names = {"_fetch_tokens_with_jar"}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            direct_names.update(
                item.asname
                for item in node.names
                if item.name == "_fetch_tokens_with_jar" and item.asname is not None
            )

    class Visitor(ast.NodeVisitor):
        def __init__(self) -> None:
            self.owners: list[str] = []

        def visit_ClassDef(self, node: ast.ClassDef) -> None:
            self.owners.append(node.name)
            self.generic_visit(node)
            self.owners.pop()

        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            self.owners.append(node.name)
            self.generic_visit(node)
            self.owners.pop()

        visit_AsyncFunctionDef = visit_FunctionDef

        def visit_Call(self, node: ast.Call) -> None:
            direct = isinstance(node.func, ast.Name) and node.func.id in direct_names
            qualified = (
                isinstance(node.func, ast.Attribute) and node.func.attr == "_fetch_tokens_with_jar"
            )
            if direct or qualified:
                callers.add(".".join((_module_label(path), *self.owners)))
            self.generic_visit(node)

    Visitor().visit(tree)
    return callers


def test_direct_fetch_tokens_with_jar_callers_are_exact_and_shrink_only() -> None:
    actual = set().union(*(_direct_callers(path) for path in _production_paths()))
    assert actual == _EXPECTED_CALLERS
    assert not any(
        caller.startswith(("_android.", "_runtime.", "client.", "_client_assembly."))
        or ".assembly." in caller
        for caller in actual
    )


def _static_string(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left = _static_string(node.left)
        right = _static_string(node.right)
        if left is not None and right is not None:
            return left + right
    return None


def _provider_escapes(path: Path, tree: ast.Module) -> list[str]:
    parents = {child: parent for parent in ast.walk(tree) for child in ast.iter_child_nodes(parent)}
    violations: list[str] = []
    facade_path = SRC_ROOT / "auth.py"

    def is_direct_call_target(node: ast.AST) -> bool:
        parent = parents.get(node)
        return isinstance(parent, ast.Call) and parent.func is node

    def is_frozen_facade_alias(node: ast.AST) -> bool:
        parent = parents.get(node)
        return (
            path == facade_path
            and isinstance(parent, ast.Assign)
            and len(parent.targets) == 1
            and isinstance(parent.targets[0], ast.Name)
            and parent.targets[0].id == "_fetch_tokens_with_jar"
            and (parent.value is node or parent.targets[0] is node)
        )

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for item in node.names:
                if item.name == "_fetch_tokens_with_jar" and item.asname is not None:
                    violations.append(f"{node.lineno}:import-alias:{item.asname}")
        elif isinstance(node, ast.Name) and node.id == "_fetch_tokens_with_jar":
            if not is_direct_call_target(node) and not is_frozen_facade_alias(node):
                violations.append(f"{node.lineno}:provider-name")
        elif isinstance(node, ast.Attribute) and node.attr == "_fetch_tokens_with_jar":
            if not is_direct_call_target(node) and not is_frozen_facade_alias(node):
                violations.append(f"{node.lineno}:provider-attribute")
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id in {"getattr", "hasattr"} and len(node.args) >= 2:
                if _static_string(node.args[1]) == "_fetch_tokens_with_jar":
                    violations.append(f"{node.lineno}:dynamic-lookup")
        elif isinstance(node, ast.Subscript):
            if _static_string(node.slice) == "_fetch_tokens_with_jar":
                violations.append(f"{node.lineno}:dynamic-subscript")
    return violations


def test_fetch_tokens_with_jar_has_no_dynamic_provider_escape() -> None:
    violations = {
        str(path.relative_to(REPO_ROOT)): found
        for path in _production_paths()
        if (
            found := _provider_escapes(
                path,
                ast.parse(path.read_text(encoding="utf-8"), filename=str(path)),
            )
        )
    }
    assert violations == {}


@pytest.mark.parametrize(
    "source",
    [
        "provider = _fetch_tokens_with_jar\nprovider()\n",
        "provider = refresh._fetch_tokens_with_jar\nprovider()\n",
        "from notebooklm._auth.refresh import _fetch_tokens_with_jar as provider\nprovider()\n",
        "provider = getattr(refresh, '_fetch_tokens_' + 'with_jar')\n",
        "provider = registry['_fetch_tokens_' + 'with_jar']\n",
        "if TYPE_CHECKING:\n    from x import _fetch_tokens_with_jar as Provider\n",
    ],
)
def test_dynamic_provider_escape_guard_bites(source: str) -> None:
    path = SRC_ROOT / "synthetic.py"
    assert _provider_escapes(path, ast.parse(source))


def _resolve_import_from(path: Path, node: ast.ImportFrom) -> str:
    if node.level == 0:
        return node.module or ""
    module_parts = list(path.relative_to(REPO_ROOT / "src").with_suffix("").parts)
    package_parts = module_parts[:-1]
    keep = len(package_parts) - (node.level - 1)
    resolved = package_parts[:keep]
    if node.module:
        resolved.extend(node.module.split("."))
    return ".".join(resolved)


def _auth_web_violations(path: Path, tree: ast.Module) -> list[str]:
    violations: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for item in node.names:
                if item.name == "notebooklm._web" or item.name.startswith("notebooklm._web."):
                    violations.append(f"{path.name}:{node.lineno}:import:{item.name}")
        elif isinstance(node, ast.ImportFrom):
            resolved = _resolve_import_from(path, node)
            if resolved == "notebooklm._web" or resolved.startswith("notebooklm._web."):
                violations.append(f"{path.name}:{node.lineno}:from:{resolved}")
        elif isinstance(node, ast.Name) and node.id in _WEB_TYPE_NAMES:
            violations.append(f"{path.name}:{node.lineno}:name:{node.id}")
        elif isinstance(node, ast.Constant) and node.value in _WEB_TYPE_NAMES:
            violations.append(f"{path.name}:{node.lineno}:string:{node.value}")
    return violations


def test_auth_has_no_web_import_or_concrete_type_knowledge() -> None:
    violations: list[str] = []
    for path in sorted(AUTH_ROOT.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        violations.extend(_auth_web_violations(path, tree))
    assert violations == []


@pytest.mark.parametrize(
    "source",
    [
        "from ..._web import assembly\n",
        "if TYPE_CHECKING:\n    from ..._web.transport.auth import AuthRefreshCoordinator\n",
        "value: 'WebRuntime'\n",
    ],
)
def test_nested_auth_web_boundary_guard_bites(source: str) -> None:
    path = AUTH_ROOT / "refresh" / "_cold_fallbacks.py"
    assert _auth_web_violations(path, ast.parse(source))


def test_deleted_auth_session_module_stays_deleted() -> None:
    assert not (AUTH_ROOT / "session.py").exists()


def test_root_assembly_has_no_client_capturing_refresh_callback() -> None:
    path = SRC_ROOT / "_client_assembly.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    assembly = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "_assemble_client"
    )
    nested_async = [
        node
        for node in ast.walk(assembly)
        if isinstance(node, ast.AsyncFunctionDef) and node is not assembly
    ]
    assert nested_async == []
