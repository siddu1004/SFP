"""Package-aware import scanner shared by the three adapter boundary guards.

The adapter boundary is an authored-code rule. Imports under ``TYPE_CHECKING``
and literal dynamic imports still express a dependency, so this scanner records
them alongside ordinary absolute and relative imports.
"""

from __future__ import annotations

import ast
import importlib.util
from dataclasses import dataclass
from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parents[2] / "src" / "notebooklm"


@dataclass(frozen=True)
class AdapterImport:
    target: str
    line: int
    type_only: bool


def module_identity(path: Path) -> tuple[str, str]:
    """Return the module name and package used for relative-import resolution."""
    parts = list(path.relative_to(SRC_ROOT).with_suffix("").parts)
    if parts[-1] == "__init__":
        parts.pop()
        module = ".".join(("notebooklm", *parts))
        return module, module
    module = ".".join(("notebooklm", *parts))
    return module, module.rpartition(".")[0]


def _is_type_checking_guard(node: ast.AST) -> bool:
    return (isinstance(node, ast.Name) and node.id == "TYPE_CHECKING") or (
        isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == "typing"
        and node.attr == "TYPE_CHECKING"
    )


class _Visitor(ast.NodeVisitor):
    def __init__(self, package: str) -> None:
        self._package = package
        self._type_only = False
        self.imports: list[AdapterImport] = []
        self._loaders = {"__import__": "__import__", "import_module": "import_module"}
        self._loader_modules = {"importlib": "importlib", "builtins": "builtins"}

    def visit_If(self, node: ast.If) -> None:
        if not _is_type_checking_guard(node.test):
            self.generic_visit(node)
            return
        old_type_only = self._type_only
        self._type_only = True
        for child in node.body:
            self.visit(child)
        self._type_only = old_type_only
        for child in node.orelse:
            self.visit(child)

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            self._record(alias.name, node.lineno)
            if alias.name in {"importlib", "builtins"}:
                self._loader_modules[alias.asname or alias.name] = alias.name

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        module = node.module or ""
        if node.level:
            module = importlib.util.resolve_name(f"{'.' * node.level}{module}", self._package)
        for alias in node.names:
            self._record(f"{module}.{alias.name}", node.lineno)
            if (module, alias.name) in {("importlib", "import_module"), ("builtins", "__import__")}:
                self._loaders[alias.asname or alias.name] = alias.name

    @staticmethod
    def _argument(node: ast.Call, position: int, name: str) -> ast.AST | None:
        return next(
            (keyword.value for keyword in node.keywords if keyword.arg == name),
            node.args[position] if len(node.args) > position else None,
        )

    def _loader(self, function: ast.AST) -> str | None:
        if isinstance(function, ast.Name):
            return self._loaders.get(function.id)
        if isinstance(function, ast.Attribute) and isinstance(function.value, ast.Name):
            module = self._loader_modules.get(function.value.id)
            if (module, function.attr) in {
                ("importlib", "import_module"),
                ("builtins", "__import__"),
            }:
                return function.attr
        return None

    def visit_Call(self, node: ast.Call) -> None:
        loader = self._loader(node.func)
        name = self._argument(node, 0, "name")
        if loader is not None and isinstance(name, ast.Constant) and isinstance(name.value, str):
            target = name.value
            if loader == "import_module":
                package_node = self._argument(node, 1, "package")
                package = self._package
                if isinstance(package_node, ast.Constant) and isinstance(package_node.value, str):
                    package = package_node.value
                if target.startswith("."):
                    target = importlib.util.resolve_name(target, package)
            else:
                level = self._argument(node, 4, "level")
                if isinstance(level, ast.Constant) and isinstance(level.value, int) and level.value:
                    target = importlib.util.resolve_name("." * level.value + target, self._package)
            self._record(target, node.lineno)
            if loader == "__import__":
                fromlist = self._argument(node, 3, "fromlist")
                if isinstance(fromlist, ast.List | ast.Tuple):
                    for member in fromlist.elts:
                        if isinstance(member, ast.Constant) and isinstance(member.value, str):
                            self._record(f"{target}.{member.value}", node.lineno)
        self.generic_visit(node)

    def _record(self, target: str, line: int) -> None:
        self.imports.append(AdapterImport(target=target, line=line, type_only=self._type_only))


def scan_source(source: str, *, package: str) -> list[AdapterImport]:
    """Resolve every import authored by ``source`` in ``package``."""
    visitor = _Visitor(package)
    visitor.visit(ast.parse(source))
    return visitor.imports


def scan_path(path: Path) -> list[AdapterImport]:
    """Resolve every import authored by ``path``."""
    _, package = module_identity(path)
    return scan_source(path.read_text(encoding="utf-8"), package=package)


def is_module_or_child(target: str, parent: str) -> bool:
    return target == parent or target.startswith(f"{parent}.")


# Exact 0.x hosting/deprecation/settlement exceptions. Module imports and wildcard
# imports do not qualify: callers must name the audited symbols. Changes require
# a reviewed architectural disposition, not regeneration from current imports.
PRIVATE_SYMBOL_ALLOWANCES: dict[str, dict[str, frozenset[str]]] = {
    "notebooklm._adapter_support": {
        "AdapterRuntimeClient": frozenset({"mcp/_chattasks.py"}),
        "check_bind_allowed": frozenset({"mcp/__main__.py", "server/__main__.py"}),
        "is_loopback": frozenset({"mcp/__main__.py", "server/__main__.py"}),
        "LoopBoundPrimitive": frozenset({"mcp/_chattasks.py", "server/_limits.py"}),
        "_client_operation": frozenset({"mcp/_chattasks.py"}),
        "_detached_adapter_context": frozenset({"mcp/_chattasks.py"}),
        "client_generation_epoch": frozenset({"mcp/_chattasks.py"}),
        "redact": frozenset(
            {
                "mcp/_clientprovider.py",
                "mcp/_errors.py",
                "server/_errors.py",
                "server/routes/meta.py",
            }
        ),
        "host_header_is_loopback": frozenset({"mcp/_host_guard.py"}),
        "DEFAULT_SERVER_KEEPALIVE_INTERVAL": frozenset({"mcp/server.py", "server/app.py"}),
        "LOOPBACK_HOSTNAMES": frozenset({"server/_auth.py"}),
        "addr_is_loopback": frozenset({"server/_auth.py"}),
    },
    # Adapter-owned warnings retain registered compatibility behavior.
    "notebooklm._deprecation": {
        "DEPRECATION_SPECS": frozenset({"mcp/_confirm.py"}),
        "warn_registered_deprecation": frozenset({"mcp/_confirm.py"}),
        "warn_deprecated": frozenset({"mcp/tools/research.py"}),
    },
    # Public exception projections cannot attach settlement journal evidence.
    "notebooklm._source.batch": {
        "preserve_batch_call_failure": frozenset(
            {"mcp/tools/sources.py", "server/routes/sources.py"}
        ),
        "preserve_batch_projection_failure": frozenset(
            {"mcp/tools/sources.py", "server/routes/sources.py"}
        ),
    },
    # Hosting loop checks and installed-version rendering are adapter concerns.
    "notebooklm._loop_affinity": {
        "assert_bound_loop": frozenset({"server/_limits.py"}),
    },
    "notebooklm._version_info": {
        "version_string": frozenset({"mcp/tools/meta.py", "server/routes/meta.py"}),
    },
}


def adapter_violations(imports: list[AdapterImport], *, relative: str) -> list[str]:
    """Apply the same resolved dependency rule to real files and scanner probes."""
    adapter = relative.split("/", 1)[0]
    bad: list[str] = []
    for imported in imports:
        target = imported.target
        if is_module_or_child(target, f"notebooklm.{adapter}"):
            continue
        if adapter != "cli" and any(
            is_module_or_child(target, prefix) for prefix in ("click", "rich", "cli")
        ):
            bad.append(f"line {imported.line}: {target}")
            continue
        if not target.startswith("notebooklm."):
            continue
        if is_module_or_child(target, "notebooklm._app"):
            continue
        parts = target.split(".")[1:]
        forbidden = parts[0] in {"cli", "mcp", "server", "rpc"} or any(
            part.startswith("_") and not part.startswith("__") for part in parts
        )
        if not forbidden:
            continue
        module, _, symbol = target.rpartition(".")
        allowed_files = PRIVATE_SYMBOL_ALLOWANCES.get(module, {}).get(symbol, frozenset())
        if relative not in allowed_files:
            bad.append(f"line {imported.line}: {target}")
    return bad
