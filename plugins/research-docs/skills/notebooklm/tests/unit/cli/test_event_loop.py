"""Tests for the Windows event-loop selection behind ``run_async`` (#79, #2485).

Most tests simulate Windows by faking ``sys.platform`` and standing in recording
subclasses of the host's selector loop for ``asyncio.ProactorEventLoop`` and
``asyncio.SelectorEventLoop``, so the selection logic runs real loops on every
OS. The Windows-only tests at the end run the real loop classes.
"""

from __future__ import annotations

import asyncio
import sys
import warnings

import pytest

from notebooklm.cli import runtime
from notebooklm.exceptions import ConfigurationError

ENV = runtime.WINDOWS_EVENT_LOOP_ENV
_HOST_SELECTOR_LOOP = asyncio.SelectorEventLoop


class _FakeProactorLoop(asyncio.SelectorEventLoop):
    pass


class _FakeSelectorLoop(asyncio.SelectorEventLoop):
    pass


@pytest.fixture
def simulated_windows(monkeypatch):
    """Fake win32 with recording loop classes; fail on any policy change."""
    monkeypatch.setattr(asyncio, "ProactorEventLoop", _FakeProactorLoop, raising=False)
    monkeypatch.setattr(asyncio, "SelectorEventLoop", _FakeSelectorLoop)
    monkeypatch.setattr(
        asyncio,
        "set_event_loop_policy",
        lambda policy: pytest.fail("the Windows loop choice must not touch the policy"),
    )
    monkeypatch.setattr(runtime.sys, "platform", "win32")


async def _running_loop_type() -> type:
    return type(asyncio.get_running_loop())


class TestWindowsEventLoopChoice:
    def test_ignored_off_windows(self, monkeypatch):
        monkeypatch.setattr(runtime.sys, "platform", "linux")
        monkeypatch.setenv(ENV, "selector")
        assert runtime.windows_event_loop_choice() is None

    @pytest.mark.parametrize("value", [None, "", "   "])
    def test_unset_means_default(self, monkeypatch, value):
        monkeypatch.setattr(runtime.sys, "platform", "win32")
        if value is None:
            monkeypatch.delenv(ENV, raising=False)
        else:
            monkeypatch.setenv(ENV, value)
        assert runtime.windows_event_loop_choice() is None

    @pytest.mark.parametrize(
        ("value", "expected"),
        [("selector", "selector"), (" Selector ", "selector"), ("PROACTOR", "proactor")],
    )
    def test_known_values(self, monkeypatch, value, expected):
        monkeypatch.setattr(runtime.sys, "platform", "win32")
        monkeypatch.setenv(ENV, value)
        assert runtime.windows_event_loop_choice() == expected

    def test_unknown_value_raises(self, monkeypatch):
        monkeypatch.setattr(runtime.sys, "platform", "win32")
        monkeypatch.setenv(ENV, "selectr")
        with pytest.raises(ConfigurationError, match=ENV):
            runtime.windows_event_loop_choice()


class TestRunAsyncLoopSelection:
    @pytest.mark.parametrize(
        ("choice", "loop_type"),
        [("selector", _FakeSelectorLoop), ("proactor", _FakeProactorLoop)],
    )
    @pytest.mark.skipif(
        not hasattr(asyncio, "Runner"),
        reason="loop factories need asyncio.Runner (3.11+); 3.10 is covered below",
    )
    @pytest.mark.usefixtures("simulated_windows")
    def test_runs_on_the_chosen_loop(self, monkeypatch, choice, loop_type):
        monkeypatch.setenv(ENV, choice)
        assert runtime.run_async(_running_loop_type()) is loop_type

    @pytest.mark.usefixtures("simulated_windows")
    def test_default_uses_asyncio_run(self, monkeypatch):
        monkeypatch.delenv(ENV, raising=False)
        monkeypatch.setattr(
            asyncio, "Runner", lambda **kwargs: pytest.fail("no Runner by default"), raising=False
        )
        loop_type = runtime.run_async(_running_loop_type())
        assert loop_type not in (_FakeSelectorLoop, _FakeProactorLoop)

    @pytest.mark.skipif(
        sys.platform == "win32", reason="faking linux on a real Windows loop is not meaningful"
    )
    def test_off_windows_ignores_the_variable(self, monkeypatch):
        monkeypatch.setattr(runtime.sys, "platform", "linux")
        monkeypatch.setenv(ENV, "selector")
        monkeypatch.setattr(
            asyncio, "Runner", lambda **kwargs: pytest.fail("no Runner off Windows"), raising=False
        )
        assert runtime.run_async(asyncio.sleep(0, result="done")) == "done"

    @pytest.mark.usefixtures("simulated_windows")
    def test_unknown_value_closes_the_coroutine(self, monkeypatch):
        monkeypatch.setenv(ENV, "iocp")
        coro = asyncio.sleep(0)
        with warnings.catch_warnings():
            warnings.simplefilter("error", RuntimeWarning)
            with pytest.raises(ConfigurationError, match=ENV):
                runtime.run_async(coro)
        assert coro.cr_frame is None  # closed, so no "never awaited" warning

    @pytest.mark.usefixtures("simulated_windows")
    def test_nested_call_is_refused_before_creating_a_loop(self, monkeypatch):
        monkeypatch.setenv(ENV, "selector")
        monkeypatch.setattr(
            asyncio,
            "Runner",
            lambda **kwargs: pytest.fail("no loop may be created inside a running loop"),
            raising=False,
        )

        async def driver() -> RuntimeError:
            coro = asyncio.sleep(0)
            with warnings.catch_warnings():
                warnings.simplefilter("error", RuntimeWarning)
                with pytest.raises(RuntimeError) as exc_info:
                    runtime.run_async(coro)
            assert coro.cr_frame is None
            return exc_info.value

        outer_loop = _HOST_SELECTOR_LOOP()
        try:
            err = outer_loop.run_until_complete(driver())
        finally:
            outer_loop.close()
        assert "existing event loop" in str(err)

    @pytest.mark.skipif(not hasattr(asyncio, "Runner"), reason="loop factories need 3.11+")
    @pytest.mark.usefixtures("simulated_windows")
    def test_loop_creation_failure_closes_the_coroutine(self, monkeypatch):
        """If the loop can't be built, the error surfaces without 'never awaited'."""

        def broken_loop():
            raise OSError("IOCP unavailable")

        monkeypatch.setattr(asyncio, "SelectorEventLoop", broken_loop)
        monkeypatch.setenv(ENV, "selector")
        coro = asyncio.sleep(0)
        with warnings.catch_warnings():
            warnings.simplefilter("error", RuntimeWarning)
            with pytest.raises(OSError, match="IOCP unavailable"):
                runtime.run_async(coro)
        assert coro.cr_frame is None

    @pytest.mark.parametrize("choice", ["selector", "proactor"])
    def test_python_310_falls_back_to_the_policy(self, monkeypatch, choice):
        """Without ``asyncio.Runner`` the opt-in sets the (undeprecated) policy."""

        class _SelectorPolicy:
            pass

        class _ProactorPolicy:
            pass

        policies: list[object] = []
        runs: list[object] = []

        def fake_run(coro):
            runs.append(coro)
            coro.close()
            return "ran"

        monkeypatch.delattr(asyncio, "Runner", raising=False)
        monkeypatch.setattr(
            asyncio, "WindowsSelectorEventLoopPolicy", _SelectorPolicy, raising=False
        )
        monkeypatch.setattr(
            asyncio, "WindowsProactorEventLoopPolicy", _ProactorPolicy, raising=False
        )
        original_policy = object()
        monkeypatch.setattr(asyncio, "get_event_loop_policy", lambda: original_policy)
        monkeypatch.setattr(asyncio, "set_event_loop_policy", policies.append)
        monkeypatch.setattr(asyncio, "run", fake_run)
        monkeypatch.setattr(runtime.sys, "platform", "win32")
        monkeypatch.setenv(ENV, choice)

        assert runtime.run_async(asyncio.sleep(0)) == "ran"
        assert len(runs) == 1
        expected = _SelectorPolicy if choice == "selector" else _ProactorPolicy
        # Set for the run, then the caller's policy is put back.
        assert type(policies[0]) is expected
        assert policies[1:] == [original_policy]


@pytest.mark.skipif(sys.platform != "win32", reason="Windows-only test")
@pytest.mark.usefixtures("restore_event_loop_policy")
class TestRealWindowsLoops:
    def test_default_is_proactor(self, monkeypatch):
        monkeypatch.delenv(ENV, raising=False)
        assert runtime.run_async(_running_loop_type()) is asyncio.ProactorEventLoop

    def test_selector_opt_in_leaves_the_policy_alone(self, monkeypatch):
        monkeypatch.setenv(ENV, "selector")
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            before = asyncio.get_event_loop_policy()
        loop_type = runtime.run_async(_running_loop_type())
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            after = asyncio.get_event_loop_policy()
        assert issubclass(loop_type, asyncio.SelectorEventLoop)
        if sys.version_info >= (3, 11):
            assert after is before
