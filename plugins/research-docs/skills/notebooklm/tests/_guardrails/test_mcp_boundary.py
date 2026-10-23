"""Dependency boundary for the MCP adapter."""

from __future__ import annotations

from pathlib import Path

import pytest

from ._adapter_import_boundary import SRC_ROOT, adapter_violations, scan_path, scan_source

MCP_DIR = SRC_ROOT / "mcp"


def _mcp_files() -> list[Path]:
    return sorted(MCP_DIR.rglob("*.py"))


def _violations(path: Path) -> list[str]:
    return adapter_violations(scan_path(path), relative=path.relative_to(SRC_ROOT).as_posix())


def test_mcp_dir_exists() -> None:
    assert MCP_DIR.is_dir(), f"expected MCP package at {MCP_DIR}"


@pytest.mark.parametrize(
    "path", _mcp_files(), ids=lambda p: str(p.relative_to(SRC_ROOT.parent.parent))
)
def test_mcp_imports_follow_adapter_boundary(path: Path) -> None:
    bad = _violations(path)
    assert not bad, f"{path.relative_to(SRC_ROOT)} imports forbidden dependencies: {bad}"


@pytest.mark.parametrize(
    "source",
    (
        "from ...server import app\n",
        "from ... import server\n",
        "if TYPE_CHECKING:\n    from ..._web import transport\n",
        "import importlib\nimportlib.import_module('notebooklm.cli.context')\n",
    ),
)
def test_mcp_scanner_resolves_relative_type_only_and_literal_dynamic_edges(source: str) -> None:
    assert adapter_violations(
        scan_source(source, package="notebooklm.mcp.tools"),
        relative="mcp/tools/sources.py",
    )
