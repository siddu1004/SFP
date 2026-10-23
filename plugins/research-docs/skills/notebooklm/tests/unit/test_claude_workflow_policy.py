"""Static policy contracts for the maintainer-triggered Claude workflow."""

from pathlib import Path

import pytest
import yaml

pytestmark = pytest.mark.repo_lint

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "claude.yml"


def test_checkout_ref_tracks_the_pr_for_every_pr_comment_event() -> None:
    workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    checkout = next(
        step
        for step in workflow["jobs"]["claude"]["steps"]
        if str(step.get("uses", "")).startswith("actions/checkout@")
    )

    checkout_ref = " ".join(str(checkout["with"]["ref"]).split())
    assert checkout_ref == (
        "${{ (github.event_name == 'issue_comment' && "
        "github.event.issue.pull_request != null && "
        "format('refs/pull/{0}/head', github.event.issue.number)) || "
        "((github.event_name == 'pull_request_review_comment' || "
        "github.event_name == 'pull_request_review') && "
        "github.event.pull_request.head.sha) || github.sha }}"
    )
