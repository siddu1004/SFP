"""Release metadata must declare runtime dependencies without relying on extras."""

from pathlib import Path
from zipfile import ZipFile

import pytest
from scripts.check_base_wheel import EXPECTED_BROWSER_FILES, _inspect_wheel


@pytest.mark.parametrize(
    "requirement",
    [
        "",
        'Requires-Dist: typing-extensions>=4.4; extra == "dev"\n',
        'Requires-Dist: typing-extensions>=4.4; python_version < "3.11"\n',
        "Requires-Dist: typing-extensions-other>=4.4\n",
    ],
    ids=["missing", "extra-only", "older-python-only", "different-package"],
)
def test_wheel_rejects_missing_unconditional_typing_extensions(
    tmp_path: Path, requirement: str
) -> None:
    """Conditional requirements and distinct package names cannot satisfy the guard."""
    wheel = _wheel(tmp_path, requirement)

    with pytest.raises(RuntimeError, match="no unconditional typing_extensions requirement"):
        _inspect_wheel(wheel)


@pytest.mark.parametrize(
    "name", ["typing-extensions", "typing_extensions", "typing.extensions", "Typing__Extensions"]
)
def test_wheel_accepts_direct_typing_extensions_dependency(tmp_path: Path, name: str) -> None:
    """Equivalent distribution-name spellings satisfy the direct dependency guard."""
    _inspect_wheel(_wheel(tmp_path, f"Requires-Dist: {name}<5,>=4.4\n"))


def _wheel(tmp_path: Path, typing_requirement: str) -> Path:
    """Build a minimal wheel with configurable runtime dependency metadata."""
    wheel = tmp_path / "notebooklm_py-0.8.5-py3-none-any.whl"
    with ZipFile(wheel, "w") as archive:
        for name in EXPECTED_BROWSER_FILES:
            archive.writestr(f"notebooklm/_browser/{name}", "")
        archive.writestr(
            "notebooklm_py-0.8.5.dist-info/METADATA",
            "Metadata-Version: 2.3\n"
            "Name: notebooklm-py\n"
            "Version: 0.8.5\n"
            'Requires-Dist: playwright>=1.40.0; extra == "browser"\n' + typing_requirement,
        )
    return wheel
