"""Behavioral probes use the same boundary predicate as the ordinary PR lane."""

import pytest

from ._adapter_import_boundary import adapter_violations, scan_source


@pytest.mark.parametrize("adapter,peer", [("cli", "mcp"), ("mcp", "server"), ("server", "cli")])
@pytest.mark.parametrize(
    "shape", ["absolute", "relative", "type_only", "dynamic", "dynamic_relative"]
)
def test_forbidden_adapter_edges_are_rejected(adapter: str, peer: str, shape: str) -> None:
    source = {
        "absolute": f"from notebooklm.{peer} import api",
        "relative": f"from .. import {peer}",
        "type_only": f"if TYPE_CHECKING:\n    from ..{peer} import api",
        "dynamic": f"__import__('notebooklm.{peer}.api')",
        "dynamic_relative": f"importlib.import_module('..{peer}.api', __package__)",
    }[shape]
    assert adapter_violations(
        scan_source(source, package=f"notebooklm.{adapter}"), relative=f"{adapter}/example.py"
    )


@pytest.mark.parametrize("adapter,folder", [("mcp", "tools"), ("server", "routes")])
@pytest.mark.parametrize("symbol", ["delete_batch", "*", "preserve_batch_other_failure"])
def test_settlement_exception_does_not_admit_other_symbols(
    adapter: str, folder: str, symbol: str
) -> None:
    source = f"from notebooklm._source.batch import {symbol}"
    assert adapter_violations(
        scan_source(source, package=f"notebooklm.{adapter}.{folder}"),
        relative=f"{adapter}/{folder}/sources.py",
    )


@pytest.mark.parametrize("adapter,folder", [("mcp", "tools"), ("server", "routes")])
@pytest.mark.parametrize(
    "symbol", ["preserve_batch_call_failure", "preserve_batch_projection_failure"]
)
def test_exact_settlement_symbols_are_confined_to_source_adapter(
    adapter: str, folder: str, symbol: str
) -> None:
    source = f"from ..._source.batch import {symbol}"
    imports = scan_source(source, package=f"notebooklm.{adapter}.{folder}")
    assert not adapter_violations(imports, relative=f"{adapter}/{folder}/sources.py")
    assert adapter_violations(imports, relative=f"{adapter}/{folder}/notebooks.py")


@pytest.mark.parametrize(
    "source",
    [
        "from notebooklm._web import assembly",
        "importlib.import_module('.._web.assembly', package='notebooklm.mcp')",
        "from notebooklm.types import _secret",
        "from notebooklm import _atomic_io",
        "from notebooklm.rpc.types import ArtifactType",
    ],
)
def test_private_domain_and_rpc_edges_are_rejected(source: str) -> None:
    assert adapter_violations(
        scan_source(source, package="notebooklm.mcp"), relative="mcp/server.py"
    )


def test_public_facades_and_local_private_modules_are_allowed() -> None:
    source = "from ...types import Artifact\nfrom ...io import atomic_write_json\nfrom ._payloads import render\nfrom ..._app.download import execute_download"
    assert not adapter_violations(
        scan_source(source, package="notebooklm.mcp.tools"), relative="mcp/tools/studio.py"
    )


@pytest.mark.parametrize("adapter,peer", [("cli", "mcp"), ("mcp", "server"), ("server", "cli")])
@pytest.mark.parametrize(
    "shape",
    [
        "function_alias",
        "module_alias",
        "fromlist_keyword",
        "fromlist_positional",
        "relative_alias",
        "builtin_alias",
    ],
)
def test_literal_dynamic_alias_and_fromlist_edges_cannot_bypass_boundary(adapter, peer, shape):
    source = {
        "function_alias": f"from importlib import import_module as load\nload('notebooklm.{peer}.api')",
        "module_alias": f"import importlib as il\nil.import_module('notebooklm.{peer}.api')",
        "fromlist_keyword": f"__import__('notebooklm', fromlist=['{peer}'])",
        "fromlist_positional": f"__import__('notebooklm', None, None, ('{peer}',))",
        "relative_alias": f"from importlib import import_module as load\nload('..{peer}.api', package='notebooklm.{adapter}')",
        "builtin_alias": f"from builtins import __import__ as load\nload('notebooklm', fromlist=['{peer}'])",
    }[shape]
    assert adapter_violations(
        scan_source(source, package=f"notebooklm.{adapter}"), relative=f"{adapter}/example.py"
    )


@pytest.mark.parametrize(
    "source",
    [
        "__import__('notebooklm', fromlist=['_auth'])",
        "import builtins as bi\nbi.__import__('notebooklm.types', fromlist=['_secret'])",
        "from importlib import import_module as load\nif TYPE_CHECKING:\n    load('notebooklm._web.assembly')",
        "__import__('_web', globals(), locals(), ['assembly'], 2)",
        "from importlib import import_module as load\nload(name='.._web.assembly', package=__package__)",
    ],
)
def test_private_literal_dynamic_aliases_and_relative_levels_are_rejected(source):
    assert adapter_violations(
        scan_source(source, package="notebooklm.mcp"), relative="mcp/server.py"
    )


def test_literal_dynamic_aliases_preserve_local_and_public_imports():
    source = (
        "from importlib import import_module as load\n"
        "load('._payloads', 'notebooklm.mcp.tools')\n"
        "__import__('notebooklm', fromlist=['types', 'io'])"
    )
    assert not adapter_violations(
        scan_source(source, package="notebooklm.mcp.tools"), relative="mcp/tools/studio.py"
    )
