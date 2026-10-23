"""Wire regressions for rejected note operations and unconfirmed sharing grants."""

import json

import pytest

from notebooklm import NotebookLMClient
from notebooklm._app.errors import classify, unconfirmed_hint
from notebooklm.exceptions import DecodingError, RPCError
from notebooklm.options import ClientConfig, RetryOptions, WebBackendConfig
from notebooklm.outcomes import CommitState, RecoveryAction
from notebooklm.rpc import RPCMethod
from notebooklm.types import SharePermission


def _status_response(method: RPCMethod, code: int | None) -> str:
    """Build a null response carrying a recognized server status, or an empty success."""
    status = None if code is None else [code]
    chunk = json.dumps([["wrb.fr", method.value, None, None, None, status, "generic"]])
    return ")]}'\n" + str(len(chunk)) + "\n" + chunk + "\n"


def _config() -> ClientConfig:
    """Disable transport retries so every rejection test counts the original requests."""
    return ClientConfig(backend=WebBackendConfig(), retry=RetryOptions(server_error_max_retries=0))


@pytest.mark.parametrize("code", [3, 7, 13])
@pytest.mark.parametrize("note_ids", ["note-1", ["note-1", "note-2"]])
async def test_note_delete_rejection_is_not_success(auth_tokens, httpx_mock, code, note_ids):
    """Single and batch deletes propagate explicit refusals instead of returning None."""
    httpx_mock.add_response(text=_status_response(RPCMethod.DELETE_NOTE, code))
    async with NotebookLMClient(auth_tokens, config=_config()) as client:
        with pytest.raises(RPCError) as caught:
            await client.notes.delete("nb-1", note_ids)
    assert caught.value.rpc_code == code
    assert caught.value.method_id == RPCMethod.DELETE_NOTE.value
    assert len(httpx_mock.get_requests()) == 1


@pytest.mark.parametrize("code", [3, 5, 7, 13])
@pytest.mark.parametrize("lookup", [False, True])
async def test_note_inventory_rejection_is_not_absence(auth_tokens, httpx_mock, code, lookup):
    """Neither an empty list nor a missing-note result can stand in for a denied read."""
    httpx_mock.add_response(text=_status_response(RPCMethod.GET_NOTES_AND_MIND_MAPS, code))
    async with NotebookLMClient(auth_tokens, config=_config()) as client:
        with pytest.raises(RPCError) as caught:
            if lookup:
                await client.notes.get_or_none("nb-1", "note-1")
            else:
                await client.notes.list("nb-1")
    assert caught.value.rpc_code == code


@pytest.mark.parametrize("code", [None, 0, 5])
async def test_note_delete_keeps_empty_and_missing_single_success(auth_tokens, httpx_mock, code):
    """Empty successes and a single already-absent note keep the idempotent contract."""
    httpx_mock.add_response(text=_status_response(RPCMethod.DELETE_NOTE, code))
    async with NotebookLMClient(auth_tokens, config=_config()) as client:
        assert await client.notes.delete("nb-1", "note-1") is None
    assert len(httpx_mock.get_requests()) == 1


@pytest.mark.parametrize("remaining", [False, True])
@pytest.mark.parametrize("layout", ["wrapped", "timestamped", "flat"])
async def test_note_batch_not_found_verifies_every_member(
    auth_tokens, httpx_mock, build_rpc_response, remaining, layout
):
    """A batch NOT_FOUND is benign only when fresh inventory proves all targets absent."""
    rows = [["note-1", None, 2], ["other", ["other", "Unselected", None, None, "Other"]]]
    if remaining:
        rows.append(["note-2", ["note-2", "Still present", None, None, "Second"]])
    inventory = rows if layout == "flat" else [rows]
    if layout == "timestamped":
        inventory.append([123, 0])
    httpx_mock.add_response(text=_status_response(RPCMethod.DELETE_NOTE, 5))
    httpx_mock.add_response(text=build_rpc_response(RPCMethod.GET_NOTES_AND_MIND_MAPS, inventory))
    async with NotebookLMClient(auth_tokens, config=_config()) as client:
        if remaining:
            with pytest.raises(RPCError) as caught:
                await client.notes.delete("nb-1", ["note-1", "note-2"])
            assert caught.value.rpc_code == 5
        else:
            assert await client.notes.delete("nb-1", ["note-1", "note-2"]) is None
    assert len(httpx_mock.get_requests()) == 2


async def test_note_batch_not_found_does_not_hide_denied_verification(auth_tokens, httpx_mock):
    """An unavailable verification read cannot turn a refused batch into success."""
    httpx_mock.add_response(text=_status_response(RPCMethod.DELETE_NOTE, 5))
    httpx_mock.add_response(text=_status_response(RPCMethod.GET_NOTES_AND_MIND_MAPS, 7))
    async with NotebookLMClient(auth_tokens, config=_config()) as client:
        with pytest.raises(RPCError) as caught:
            await client.notes.delete("nb-1", ["note-1", "note-2"])
    assert caught.value.rpc_code == 7
    assert len(httpx_mock.get_requests()) == 2


@pytest.mark.parametrize("code", [None, 0])
@pytest.mark.parametrize(
    "users",
    [
        [],
        [["viewer@example.test", 3]],
        [["viewer@example.test", 3], ["editor@example.test", 3]],
    ],
    ids=["all-missing", "partially-applied", "wrong-permission"],
)
async def test_sharing_requires_every_requested_grant(
    auth_tokens, httpx_mock, build_rpc_response, code, users
):
    """An accepted or rejected write with mismatched readback never reports an update."""
    httpx_mock.add_response(text=_status_response(RPCMethod.SHARE_NOTEBOOK, code))
    httpx_mock.add_response(text=build_rpc_response(RPCMethod.GET_SHARE_STATUS, [users, None]))
    # The enclosing operation must retain the non-replay recovery guidance.
    with pytest.raises(RPCError, match="Sharing readback did not confirm") as caught:
        async with NotebookLMClient(auth_tokens, config=_config()) as client, client.operation():
            await client.sharing.set_users(
                "nb-1",
                [
                    ("viewer@example.test", SharePermission.VIEWER),
                    ("editor@example.test", SharePermission.EDITOR),
                ],
                notify=True,
            )
    error = caught.value
    assert error.unconfirmed
    assert error.operation_metadata.recovery_action is RecoveryAction.INSPECT_AND_RECONCILE
    assert not classify(error).retriable
    assert "invitation emails" in unconfirmed_hint(error)
    assert [request.url.params["rpcids"] for request in httpx_mock.get_requests()] == [
        RPCMethod.SHARE_NOTEBOOK.value,
        RPCMethod.GET_SHARE_STATUS.value,
    ]


@pytest.mark.parametrize("code", [None, 0])
async def test_sharing_accepts_verified_grants_and_domain_case(
    auth_tokens, httpx_mock, build_rpc_response, code
):
    """Empty and OK write responses succeed when readback verifies every grant."""
    httpx_mock.add_response(text=_status_response(RPCMethod.SHARE_NOTEBOOK, code))
    httpx_mock.add_response(
        text=build_rpc_response(
            RPCMethod.GET_SHARE_STATUS,
            [[["Viewer@EXAMPLE.TEST", 3], ["editor@example.test", 2]], None],
        )
    )
    async with NotebookLMClient(auth_tokens, config=_config()) as client:
        status = await client.sharing.set_users(
            "nb-1",
            [
                ("Viewer@example.test", SharePermission.VIEWER),
                ("editor@example.test", SharePermission.EDITOR),
            ],
            notify=False,
        )
    assert len(status.shared_users) == 2
    assert len(httpx_mock.get_requests()) == 2


@pytest.mark.parametrize("code", [3, 7, 13])
async def test_sharing_rejection_never_uses_an_existing_grant_as_success(
    auth_tokens, httpx_mock, build_rpc_response, code
):
    """A denied write cannot prove that notifications were sent, even if the ACL matches."""
    httpx_mock.add_response(text=_status_response(RPCMethod.SHARE_NOTEBOOK, code))
    httpx_mock.add_response(
        text=build_rpc_response(RPCMethod.GET_SHARE_STATUS, [[["user@example.test", 3]], None]),
        is_optional=True,
    )
    async with NotebookLMClient(auth_tokens, config=_config()) as client:
        with pytest.raises(RPCError) as caught:
            await client.sharing.set_users(
                "nb-1",
                [("user@example.test", SharePermission.VIEWER)],
                notify=True,
                welcome_message="Welcome",
            )
    error = caught.value
    assert error.rpc_code == code
    assert error.unconfirmed
    assert error.commit_state is CommitState.UNKNOWN
    assert not classify(error).retriable
    assert len(httpx_mock.get_requests()) == 1


@pytest.mark.parametrize(
    "inventory",
    [
        [[{"id": "note-1", "content": "present"}]],
        [42],
        0,
        False,
        "",
        {},
        [[[""]]],
        pytest.param(None, id="null-result"),
        pytest.param([None], id="null-container"),
        pytest.param([None, [123, "bad"]], id="null-container-with-invalid-timestamp"),
        pytest.param([[["other"]]], id="missing-content"),
        pytest.param([[["other", 123]]], id="invalid-content"),
        pytest.param([[["other", None, 99]]], id="unknown-tombstone"),
        pytest.param([[], ["note-1", "Still present"]], id="empty-row-hides-live-note"),
        pytest.param(
            [[], ["note-1", ["note-1", "Still present", None, None, "Title"]]],
            id="empty-row-hides-current-note",
        ),
        pytest.param(
            [[], [123, 0], ["note-1", "Still present"]],
            id="extra-field-hides-live-note",
        ),
        pytest.param([[], ["123", 0]], id="string-timestamp"),
        pytest.param([[], [True, 0]], id="boolean-timestamp"),
        pytest.param([[], [123]], id="incomplete-timestamp"),
    ],
)
async def test_note_batch_not_found_requires_complete_inventory(
    auth_tokens, httpx_mock, build_rpc_response, inventory
):
    """Discarded malformed rows cannot prove that a refused deletion batch succeeded."""
    httpx_mock.add_response(text=_status_response(RPCMethod.DELETE_NOTE, 5))
    httpx_mock.add_response(text=build_rpc_response(RPCMethod.GET_NOTES_AND_MIND_MAPS, inventory))
    async with NotebookLMClient(auth_tokens, config=_config()) as client:
        with pytest.raises(DecodingError, match="Incomplete note inventory"):
            await client.notes.delete("nb-1", ["note-1", "note-2"])
    assert len(httpx_mock.get_requests()) == 2


@pytest.mark.parametrize("inventory", [[], [[]], [[], [123, 0]], [None, [1778873028, 870765000]]])
async def test_note_batch_not_found_accepts_explicit_empty_inventory(
    auth_tokens, httpx_mock, build_rpc_response, inventory
):
    """Empty row lists and the recorded timestamped empty envelope prove absence."""
    httpx_mock.add_response(text=_status_response(RPCMethod.DELETE_NOTE, 5))
    httpx_mock.add_response(text=build_rpc_response(RPCMethod.GET_NOTES_AND_MIND_MAPS, inventory))
    async with NotebookLMClient(auth_tokens, config=_config()) as client:
        assert await client.notes.delete("nb-1", ["note-1", "note-2"]) is None
    assert len(httpx_mock.get_requests()) == 2


@pytest.mark.parametrize("code", [None, 0])
async def test_note_batch_not_found_rejects_null_verification(auth_tokens, httpx_mock, code):
    """A null result is insufficient evidence even without an explicit RPC failure."""
    httpx_mock.add_response(text=_status_response(RPCMethod.DELETE_NOTE, 5))
    httpx_mock.add_response(text=_status_response(RPCMethod.GET_NOTES_AND_MIND_MAPS, code))
    async with NotebookLMClient(auth_tokens, config=_config()) as client:
        with pytest.raises(DecodingError, match="Incomplete note inventory"):
            await client.notes.delete("nb-1", ["note-1", "note-2"])
    assert len(httpx_mock.get_requests()) == 2


async def test_sharing_does_not_conflate_case_distinct_local_parts(
    auth_tokens, httpx_mock, build_rpc_response
):
    """One differently cased local part cannot prove both requested identities received access."""
    httpx_mock.add_response(text=_status_response(RPCMethod.SHARE_NOTEBOOK, None))
    httpx_mock.add_response(
        text=build_rpc_response(RPCMethod.GET_SHARE_STATUS, [[["User@example.test", 3]], None])
    )
    async with NotebookLMClient(auth_tokens, config=_config()) as client:
        with pytest.raises(RPCError, match="did not confirm 1"):
            await client.sharing.set_users(
                "nb-1",
                [
                    ("User@example.test", SharePermission.VIEWER),
                    ("user@example.test", SharePermission.VIEWER),
                ],
                notify=False,
            )


@pytest.mark.parametrize(
    "user",
    [
        ["user@example.test"],
        ["user@example.test", None],
        ["user@example.test", 99],
        ["user@example.test", 3.0],
    ],
)
async def test_sharing_does_not_verify_fabricated_viewer_defaults(
    auth_tokens, httpx_mock, build_rpc_response, user
):
    """Permissive display defaults cannot establish a successful viewer grant."""
    httpx_mock.add_response(text=_status_response(RPCMethod.SHARE_NOTEBOOK, None))
    httpx_mock.add_response(text=build_rpc_response(RPCMethod.GET_SHARE_STATUS, [[user], None]))
    async with NotebookLMClient(auth_tokens, config=_config()) as client:
        with pytest.raises(RPCError, match="incomplete user permissions") as caught:
            await client.sharing.set_users("nb-1", [("user@example.test", SharePermission.VIEWER)])
    assert caught.value.unconfirmed
    assert len(httpx_mock.get_requests()) == 2
