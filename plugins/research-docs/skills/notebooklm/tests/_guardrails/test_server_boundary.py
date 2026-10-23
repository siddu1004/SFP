"""Dependency boundary for the REST adapter."""

from __future__ import annotations

from pathlib import Path

import pytest

from ._adapter_import_boundary import SRC_ROOT, adapter_violations, scan_path, scan_source

SERVER_DIR = SRC_ROOT / "server"


def _server_files() -> list[Path]:
    return sorted(SERVER_DIR.rglob("*.py"))


def _violations(path: Path) -> list[str]:
    return adapter_violations(scan_path(path), relative=path.relative_to(SRC_ROOT).as_posix())


def test_server_dir_exists() -> None:
    assert SERVER_DIR.is_dir(), f"expected server package at {SERVER_DIR}"


@pytest.mark.parametrize(
    "path", _server_files(), ids=lambda p: str(p.relative_to(SRC_ROOT.parent.parent))
)
def test_server_imports_follow_adapter_boundary(path: Path) -> None:
    bad = _violations(path)
    assert not bad, f"{path.relative_to(SRC_ROOT)} imports forbidden dependencies: {bad}"


@pytest.mark.parametrize(
    "source",
    (
        "from ...mcp import server\n",
        "from ... import mcp\n",
        "if TYPE_CHECKING:\n    from ..._web import transport\n",
        "__import__('notebooklm.cli.context')\n",
    ),
)
def test_server_scanner_resolves_relative_type_only_and_literal_dynamic_edges(source: str) -> None:
    assert adapter_violations(
        scan_source(source, package="notebooklm.server.routes"),
        relative="server/routes/sources.py",
    )
