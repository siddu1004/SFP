"""Guardrail: Web vs Android public-behavior inventory stays published.

Callers (and future refactors) must not treat every remaining backend split as
a defect or every defect as "just the wire." The committed inventory classifies
each known public difference and points at pinning tests.

This gate fails if the inventory page or table disappears, a required row is
missing, a row drops its class / pinning-test / issue link, or ``python-api.md``
stops linking the contract page. It does **not** implement #2384.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from pathlib import Path

import pytest

pytestmark = pytest.mark.repo_lint

REPO_ROOT = Path(__file__).resolve().parents[2]
INVENTORY_DOC = REPO_ROOT / "docs" / "web-android-public-behavior.md"
PYTHON_API = REPO_ROOT / "docs" / "python-api.md"
DEPRECATIONS = REPO_ROOT / "docs" / "deprecations.md"

INVENTORY_LINK = "web-android-public-behavior.md"
NON_GOAL_NEEDLES = (
    "unifying protobuf vs batchexecute codecs",
    "extracting a generic mutation executor",
    "#2384",
)


@dataclass(frozen=True)
class InventoryRow:
    """One required public-behavior split that must stay in the inventory table."""

    key: str
    class_needle: str
    test_needles: tuple[str, ...]
    extra_needles: tuple[str, ...] = ()


REQUIRED_ROWS: tuple[InventoryRow, ...] = (
    InventoryRow(
        key="artifacts.generate_*",
        class_needle="Deliberate policy",
        test_needles=("tests/unit/test_creation_conformance.py",),
        extra_needles=("source_ids=[]", "language", "instructions", "enum"),
    ),
    InventoryRow(
        key="artifacts.generate_report",
        class_needle="Capability metadata",
        test_needles=("tests/unit/test_creation_conformance.py",),
        extra_needles=("CONCEPT_EXPLANATION",),
    ),
    InventoryRow(
        key="mind-map instructions",
        class_needle="Deliberate policy",
        test_needles=("tests/unit/test_creation_conformance.py",),
        extra_needles=("whitespace",),
    ),
    InventoryRow(
        key="sources.add_file",
        class_needle="Projection difference",
        test_needles=("tests/unit/android/test_source_upload.py", "tests/unit/test_types.py"),
        extra_needles=(".csv", ".docx", ".pptx", "GOOGLE_DRIVE"),
    ),
    InventoryRow(
        key="notes.get after notes.delete",
        class_needle="Projection difference",
        test_needles=("tests/e2e/test_android_notes_conformance.py",),
        extra_needles=("tombstone", "NoteNotFoundError"),
    ),
    InventoryRow(
        key="chat.get_history",
        class_needle="Resolved bug",
        test_needles=(
            "tests/unit/test_chat_characterization.py",
            "tests/unit/android/test_chat.py",
        ),
        extra_needles=("#2384",),
    ),
    InventoryRow(
        key="get_prompt(..., require_complete=False)",
        class_needle="Tracked default flip",
        test_needles=(
            "tests/unit/test_artifact_completeness.py",
            "tests/unit/android/test_artifacts.py",
        ),
        extra_needles=("C3-02", "deprecations.md"),
    ),
    InventoryRow(
        key="mind_maps.generate",
        class_needle="Tracked default flip",
        test_needles=(
            "tests/unit/test_creation_conformance.py",
            "tests/unit/test_mind_maps_base.py",
        ),
        extra_needles=("C5A-01", "failure_policy", "deprecations.md"),
    ),
    InventoryRow(
        key="research.import_sources",
        class_needle="Deliberate policy",
        test_needles=(
            "tests/unit/test_research_import_helpers.py",
            "tests/unit/android/test_research_guards.py",
        ),
        extra_needles=("canonical UUID",),
    ),
    InventoryRow(
        key="mind-map language",
        class_needle="Capability metadata",
        test_needles=("tests/unit/test_creation_conformance.py",),
        extra_needles=("does not encode",),
    ),
    InventoryRow(
        key="notebooks.get_raw",
        class_needle="Raw escape hatch",
        test_needles=(
            "tests/integration/test_notebooks_integration.py",
            "tests/unit/android/test_notebook_source_reads.py",
        ),
        extra_needles=("message_to_known_dict",),
    ),
    InventoryRow(
        key="notes.list_mind_maps",
        class_needle="Raw/compat rows",
        test_needles=(
            "tests/e2e/test_android_notes_conformance.py",
            "tests/unit/android/test_notes_frontend_parity.py",
        ),
        extra_needles=("[id, content]",),
    ),
    InventoryRow(
        key="chat.get_conversation_turns",
        class_needle="Raw",
        test_needles=(
            "tests/unit/test_chat_characterization.py",
            "tests/unit/android/test_chat.py",
        ),
        extra_needles=("protobuf",),
    ),
)


def _parse_markdown_tables(text: str) -> list[list[tuple[str, ...]]]:
    """Return GitHub-style pipe tables as lists of cell tuples (header first)."""
    tables: list[list[tuple[str, ...]]] = []
    current: list[tuple[str, ...]] | None = None
    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        if not stripped.startswith("|"):
            if current:
                tables.append(current)
                current = None
            continue
        cells = tuple(cell.strip() for cell in stripped.strip("|").split("|"))
        if cells and all(cell and set(cell) <= {"-", ":"} for cell in cells):
            continue
        if current is None:
            current = [cells]
        else:
            current.append(cells)
    if current:
        tables.append(current)
    return tables


def _inventory_table(text: str) -> list[tuple[str, ...]]:
    for table in _parse_markdown_tables(text):
        header = " | ".join(table[0]).lower()
        if "method" in header and "class" in header and "pinning" in header:
            return table
    return []


@dataclass(frozen=True)
class PinningTestReference:
    """A cited module and the test identifiers named beside it."""

    module: str
    identifiers: tuple[str, ...]


def _pinning_test_references(cell: str) -> list[PinningTestReference]:
    return [
        PinningTestReference(module, tuple(re.findall(r"`(test_\w+)`", description)))
        for module, description in re.findall(
            r"`(tests/[^`]+\.py)`(.*?)(?=`tests/[^`]+\.py`|$)", cell
        )
    ]


def inventory_problems(text: str) -> list[str]:
    """Return human-readable problems for a candidate inventory document."""
    problems: list[str] = []
    lowered = text.lower()
    for needle in NON_GOAL_NEEDLES:
        if needle.lower() not in lowered:
            problems.append(f"missing non-goal: {needle}")

    table = _inventory_table(text)
    if not table or len(table) < 2:
        problems.append("missing inventory table with Method / Class / Pinning tests columns")
        return problems

    data_rows = table[1:]
    for required in REQUIRED_ROWS:
        matched = next(
            (row for row in data_rows if required.key in row[0].replace("`", "")),
            None,
        )
        if matched is None:
            problems.append(f"missing inventory row: {required.key}")
            continue
        haystack = " | ".join(matched)
        if required.class_needle not in haystack:
            problems.append(f"{required.key}: missing class {required.class_needle!r}")
        for test_path in required.test_needles:
            if test_path not in haystack:
                problems.append(f"{required.key}: missing pinning test {test_path}")
        for extra in required.extra_needles:
            if extra not in haystack:
                problems.append(f"{required.key}: missing {extra!r}")
        for reference in _pinning_test_references(matched[-1]):
            path = REPO_ROOT / reference.module
            if not path.is_file():
                problems.append(f"pinning test {reference.module} does not exist")
                continue
            definitions = {
                node.name
                for node in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            }
            for identifier in reference.identifiers:
                if identifier not in definitions:
                    problems.append(f"pinning test {reference.module}::{identifier} does not exist")
    return problems


def test_inventory_detector_reports_a_missing_table_and_row() -> None:
    """The detector is not a no-op: an empty page and a gutted table both fail."""
    empty_problems = inventory_problems("# empty\n")
    assert "missing inventory table with Method / Class / Pinning tests columns" in empty_problems
    assert any(problem.startswith("missing non-goal:") for problem in empty_problems)

    gutted = """
Non-goals: unifying protobuf vs batchexecute codecs; extracting a generic
mutation executor; do not implement #2384.

| Method | What is actually true | Class | Pinning tests |
| --- | --- | --- | --- |
| `notes.get` after `notes.delete` | tombstone | Projection difference | tests/e2e/test_android_notes_conformance.py NoteNotFoundError |
"""
    gutted_problems = inventory_problems(gutted)
    assert "missing inventory row: chat.get_history" in gutted_problems


def test_inventory_detector_rejects_a_stale_named_test() -> None:
    text = INVENTORY_DOC.read_text(encoding="utf-8").replace(
        "test_get_history_raises_on_chat_error", "test_removed_history_case"
    )
    assert any("::test_removed_history_case does not exist" in p for p in inventory_problems(text))


def test_web_android_public_behavior_inventory_is_complete() -> None:
    """The committed inventory retains every classified public split."""
    assert INVENTORY_DOC.is_file(), (
        f"{INVENTORY_DOC.relative_to(REPO_ROOT)} must exist as the Web vs Android "
        "public-behavior contract page"
    )
    text = INVENTORY_DOC.read_text(encoding="utf-8")
    problems = inventory_problems(text)
    assert not problems, (
        f"{INVENTORY_DOC.relative_to(REPO_ROOT)} is missing required inventory content: {problems}"
    )

    python_api = PYTHON_API.read_text(encoding="utf-8")
    assert f"]({INVENTORY_LINK})" in python_api, (
        "docs/python-api.md must link the Web vs Android public-behavior inventory"
    )

    deprecations = DEPRECATIONS.read_text(encoding="utf-8")
    assert "C3-02" in deprecations and "C5A-01" in deprecations

    for required in REQUIRED_ROWS:
        for test_path in required.test_needles:
            path = REPO_ROOT / test_path
            assert path.is_file(), f"pinning test {test_path} does not exist"
