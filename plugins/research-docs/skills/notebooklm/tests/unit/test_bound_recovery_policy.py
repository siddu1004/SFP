"""Compatible policy flights and success epochs, with shared physical storage locks."""

from __future__ import annotations

import asyncio
import subprocess
from contextlib import contextmanager

import httpx
import pytest

from notebooklm._auth import recovery, refresh, single_flight
from notebooklm._auth.cookie_types import CookieJar
from notebooklm._auth.cookies import _clone_cookie_jar, _LoadedCookiePair
from notebooklm._auth.extraction import _LoginRedirectError
from notebooklm._auth.storage import snapshot_cookie_jar
from notebooklm._browser.headless_reauth import headless_reauth_env_enabled, resolve_cdp_url
from notebooklm._env import get_base_url
from notebooklm._request_context import policy_env, policy_key, request_policy_scope
from notebooklm._request_policy import resolve_web_policy
from notebooklm.options import WebRequestOptions

PERSONAL = "https://notebook.google.com"
LEGACY = "https://notebooklm.google.com"


def policy(monkeypatch, *, base=PERSONAL, command="echo first-secret", shell="0", headless="0"):
    monkeypatch.setenv("NOTEBOOKLM_REFRESH_CMD", command)
    monkeypatch.setenv("NOTEBOOKLM_REFRESH_CMD_USE_SHELL", shell)
    monkeypatch.setenv("NOTEBOOKLM_HEADLESS_REAUTH", headless)
    monkeypatch.setenv("NOTEBOOKLM_HEADLESS_REAUTH_CDP_URL", "http://localhost:9222")
    return resolve_web_policy(WebRequestOptions(base_url=base, language="fr", build_label="bound"))


@pytest.mark.asyncio
async def test_command_shell_headless_and_child_environment_are_bound(
    monkeypatch, tmp_path, caplog
):
    selected = policy(monkeypatch, shell="1", headless="1")
    monkeypatch.setenv("NOTEBOOKLM_REFRESH_CMD", "echo later-secret")
    monkeypatch.setenv("NOTEBOOKLM_REFRESH_CMD_USE_SHELL", "0")
    monkeypatch.setenv("NOTEBOOKLM_HEADLESS_REAUTH", "0")
    monkeypatch.setenv("NOTEBOOKLM_HEADLESS_REAUTH_CDP_URL", "http://localhost:9333")
    monkeypatch.setenv("NOTEBOOKLM_BASE_URL", LEGACY)
    monkeypatch.setenv("NOTEBOOKLM_HL", "ja")
    monkeypatch.setenv("NOTEBOOKLM_BL", "later")
    monkeypatch.setenv("NOTEBOOKLM_TRANSPORT", "curl_cffi")
    monkeypatch.setenv("NOTEBOOKLM_AUTH_JSON", "never-forward-inline-secret")
    monkeypatch.setenv("NOTEBOOKLM_SERVER_TOKEN", "never-forward-server-secret")
    monkeypatch.setenv("UNRELATED_OPERATIONAL_SETTING", "current")
    calls = []

    def run(target, **kwargs):
        calls.append((target, kwargs))
        return subprocess.CompletedProcess(target, 0, "", "")

    monkeypatch.setattr(subprocess, "run", run)
    storage = tmp_path / "storage_state.json"
    storage.write_text("{}")
    with request_policy_scope(selected):
        assert headless_reauth_env_enabled()
        assert resolve_cdp_url() == "http://localhost:9222"
        await refresh._run_refresh_cmd(storage, "work")
    target, kwargs = calls[0]
    assert target == "echo first-secret"
    assert kwargs["shell"] is True
    env = kwargs["env"]
    assert env["NOTEBOOKLM_BASE_URL"] == PERSONAL
    assert env["NOTEBOOKLM_HL"] == "fr"
    assert env["NOTEBOOKLM_BL"] == "bound"
    assert env["NOTEBOOKLM_TRANSPORT"] == "httpx"
    assert env["NOTEBOOKLM_HEADLESS_REAUTH"] == "1"
    assert env["NOTEBOOKLM_REFRESH_STORAGE_PATH"] == str(storage)
    assert env["UNRELATED_OPERATIONAL_SETTING"] == "current"
    assert "NOTEBOOKLM_AUTH_JSON" not in env
    assert "NOTEBOOKLM_SERVER_TOKEN" not in env
    assert "first-secret" not in repr(selected)
    assert "first-secret" not in caplog.text
    assert not headless_reauth_env_enabled()
    assert resolve_cdp_url() == "http://localhost:9333"


@pytest.mark.asyncio
async def test_incompatible_refresh_policies_never_join_or_share_success_epoch(
    monkeypatch, tmp_path
):
    first = policy(monkeypatch)
    same = policy(monkeypatch)
    other = policy(monkeypatch, base=LEGACY, command="echo other-secret", shell="1")
    assert first.identity == same.identity
    assert first.identity != other.identity
    path = tmp_path / "storage_state.json"
    path.write_text("{}")
    first_entered = asyncio.Event()
    second_entered = asyncio.Event()
    release = asyncio.Event()
    calls = []

    async def runner(storage, profile):
        calls.append((storage, policy_env("NOTEBOOKLM_REFRESH_CMD"), get_base_url()))
        (first_entered if get_base_url() == PERSONAL else second_entered).set()
        await release.wait()

    deps = refresh.RefreshCmdDeps(
        run_refresh_cmd=runner, derive_refresh_lock_path=lambda path: None
    )

    async def run(selected):
        with request_policy_scope(selected):
            await refresh._coalesced_run_refresh_cmd(str(path), path, "work", deps=deps)

    a = asyncio.create_task(run(first))
    await asyncio.wait_for(first_entered.wait(), 2)
    follower = asyncio.create_task(run(same))
    b = asyncio.create_task(run(other))
    await asyncio.wait_for(second_entered.wait(), 2)
    assert len(calls) == 2
    keys = list(single_flight.SingleFlight.process_default()._flights)
    assert all("secret" not in repr(key) for key in keys)
    release.set()
    await asyncio.gather(a, b, follower)
    with request_policy_scope(first):
        assert single_flight.read_success_epoch(policy_key(str(path))) == 1
    with request_policy_scope(other):
        assert single_flight.read_success_epoch(policy_key(str(path))) == 1
    assert single_flight.read_success_epoch(str(path)) == 0


@pytest.mark.asyncio
async def test_bound_refresh_contention_runs_own_command_under_shared_profile_lock(
    monkeypatch, tmp_path
):
    selected = policy(monkeypatch)
    path = tmp_path / "storage_state.json"
    lock_path = tmp_path / "shared.lock"
    events = []
    held = True

    @contextmanager
    def flock(candidate):
        assert candidate == lock_path
        events.append("contended" if held else "acquired")
        yield not held

    async def wait(candidate):
        nonlocal held
        assert candidate == lock_path
        events.append("wait")
        held = False
        return True

    async def runner(storage, profile):
        assert storage == path
        events.append("own-command")

    from notebooklm._auth.bound_refresh import run_bound_refresh

    with request_policy_scope(selected):
        await run_bound_refresh(
            path, "work", runner=runner, lock_path=lock_path, flock=flock, wait_for_holder=wait
        )
    assert events == ["contended", "wait", "acquired", "own-command"]


@pytest.mark.asyncio
async def test_cold_flights_and_success_generations_are_policy_qualified(monkeypatch, tmp_path):
    first = policy(monkeypatch)
    other = policy(monkeypatch, base=LEGACY, command="echo other-secret")
    state, flights = recovery.ColdRecoveryState(), single_flight.SingleFlight()
    path = tmp_path / "storage_state.json"
    entered, release = asyncio.Event(), asyncio.Event()
    headless_calls = []
    validations = []

    def pair():
        return _LoadedCookiePair(httpx.Cookies({"SID": "recovered"}), CookieJar())

    async def headless(path, allowed):
        headless_calls.append(get_base_url())
        if get_base_url() == PERSONAL:
            entered.set()
            await release.wait()
        return pair()

    async def master(path):
        pytest.fail("headless succeeded")

    async def validate(jar):
        validations.append(get_base_url())

    async def run(selected):
        with request_policy_scope(selected):
            return await recovery.ColdRecoveryCoordinator._coalesce_cold(
                state=state,
                single_flight=flights,
                storage_path=path,
                allow_headless=True,
                load_cookie_pair=lambda path: pair(),
                run_headless_attempt=headless,
                run_master_token_attempt=master,
                validate_recovered=validate,
                snapshot_cookie_jar=snapshot_cookie_jar,
                clone_cookie_jar=_clone_cookie_jar,
                raise_on_exhaustion=True,
                initial_error=_LoginRedirectError("expired"),
            )

    a = asyncio.create_task(run(first))
    await asyncio.wait_for(entered.wait(), 2)
    b = asyncio.create_task(run(other))
    for _ in range(10):
        await asyncio.sleep(0)
    assert len(flights._flights) == 2
    # The profile lock is still shared: B has a distinct flight but waits for A.
    assert headless_calls == [PERSONAL]
    release.set()
    results = await asyncio.gather(a, b)
    assert all(result is not None for result in results)
    assert headless_calls == [PERSONAL, LEGACY]
    assert validations == [PERSONAL, LEGACY]
    with request_policy_scope(first):
        assert state.success_generation(path) == 1
        shared_lock = state.path_lock(path)
    with request_policy_scope(other):
        assert state.success_generation(path) == 1
        assert state.path_lock(path) is shared_lock
    assert state.success_generation(path) == 0
    assert not flights._flights


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error",
    [
        subprocess.TimeoutExpired(["secret-executable", "secret-arg"], 60),
        OSError("secret-path and secret-arg"),
    ],
)
async def test_bound_subprocess_execution_errors_do_not_disclose_command(
    monkeypatch, tmp_path, caplog, error
):
    import traceback

    selected = policy(monkeypatch, command="secret-executable secret-arg")

    def fail(*args, **kwargs):
        raise error

    monkeypatch.setattr(subprocess, "run", fail)
    path = tmp_path / "storage.json"
    path.write_text("{}")
    with request_policy_scope(selected), pytest.raises(RuntimeError) as caught:
        await refresh._run_refresh_cmd(path, "work")
    rendered = "".join(traceback.format_exception(caught.value))
    assert "secret-" not in rendered
    assert "secret-" not in caplog.text


@pytest.mark.asyncio
async def test_legacy_recovery_command_and_child_environment_remain_dynamic(monkeypatch, tmp_path):
    selected = policy(monkeypatch)
    monkeypatch.setenv("NOTEBOOKLM_REFRESH_CMD", "echo later")
    monkeypatch.setenv("NOTEBOOKLM_BASE_URL", LEGACY)
    calls = []

    def run(target, **kwargs):
        calls.append((target, kwargs["env"]))
        return subprocess.CompletedProcess(target, 0, "", "")

    monkeypatch.setattr(subprocess, "run", run)
    path = tmp_path / "storage.json"
    path.write_text("{}")
    with request_policy_scope(selected), request_policy_scope(None):
        await refresh._run_refresh_cmd(path, "work")
    assert calls[0][0] == ["echo", "later"]
    assert calls[0][1]["NOTEBOOKLM_BASE_URL"] == LEGACY


def test_headless_policy_outcomes_are_distinct_but_browser_lock_is_shared(monkeypatch, tmp_path):
    from notebooklm._browser.headless_reauth import HeadlessReauthState

    state = HeadlessReauthState()
    first = policy(monkeypatch)
    other = policy(monkeypatch, command="echo other-secret")
    path = tmp_path / "storage.json"
    with request_policy_scope(first):
        one = state.drive_record(path, source="profile")
    with request_policy_scope(other):
        two = state.drive_record(path, source="profile")
        assert state.drive_record(path, source="profile") is two
    assert one is not two
    assert one.drive_lock is two.drive_lock
    assert one._state_lock is not two._state_lock
    assert "secret" not in repr(state._records_by_key)
    with one.drive_lock, pytest.raises(RuntimeError, match="active"):
        state.reset_if_quiescent()
    state.reset_if_quiescent()
    assert not state._drive_locks
