"""Real same-profile bootstrap and refresh with incompatible bound execution policies."""

from __future__ import annotations

import asyncio
import json
import subprocess

import httpx
import pytest

from notebooklm._auth import single_flight
from notebooklm._request_context import policy_key, request_policy_scope
from notebooklm.client import NotebookLMClient
from notebooklm.options import ClientConfig, WebBackendConfig, WebRequestOptions


@pytest.mark.asyncio
async def test_same_profile_concurrent_bootstrap_and_refresh_execute_own_policies(
    monkeypatch, tmp_path
):
    monkeypatch.setenv("NOTEBOOKLM_HOME", str(tmp_path))
    path = tmp_path / "profiles" / "work" / "storage_state.json"
    path.parent.mkdir(parents=True)
    names = (
        "SID",
        "HSID",
        "SSID",
        "APISID",
        "SAPISID",
        "LSID",
        "__Secure-1PSID",
        "__Secure-1PSIDTS",
    )
    path.write_text(
        json.dumps(
            {
                "cookies": [
                    {"name": name, "value": "live-cookie", "domain": ".google.com", "path": "/"}
                    for name in names
                ],
                "origins": [],
            }
        )
    )
    monkeypatch.setenv("NOTEBOOKLM_DISABLE_KEEPALIVE_POKE", "1")
    monkeypatch.setenv("NOTEBOOKLM_REFRESH_CMD_MIDSESSION", "1")
    monkeypatch.setenv("NOTEBOOKLM_HEADLESS_REAUTH", "0")
    monkeypatch.setenv("NOTEBOOKLM_REFRESH_CMD_USE_SHELL", "0")
    original = httpx.AsyncClient
    ready = asyncio.Event()
    entered: set[str] = set()
    recovered: set[str] = set()
    requests = []
    commands = []

    async def handle(request):
        requests.append(request)
        if request.url.host == "accounts.google.com":
            return httpx.Response(200, text="Login required")
        if request.url.path == "/":
            base = f"https://{request.url.host}"
            if base not in recovered:
                # Both owners must encounter rejection before either can recover.
                entered.add(base)
                if len(entered) == 2:
                    ready.set()
                await asyncio.wait_for(ready.wait(), 2)
                return httpx.Response(
                    302, headers={"location": "https://accounts.google.com/login"}
                )
            return httpx.Response(200, text=f'"SNlM0e":"csrf-{request.url.host}" "FdrFJe":"fresh"')
        rpcid = request.url.params["rpcids"]
        return httpx.Response(200, text=")]}'\n" + json.dumps([["wrb.fr", rpcid, "[]"]]))

    class Client(original):
        def __init__(self, **kwargs):
            super().__init__(**kwargs, transport=httpx.MockTransport(handle))

    def run(target, **kwargs):
        env = kwargs["env"]
        commands.append((target, kwargs["shell"], env))
        recovered.add(env["NOTEBOOKLM_BASE_URL"])
        return subprocess.CompletedProcess(target, 0, "", "")

    monkeypatch.setattr(httpx, "AsyncClient", Client)
    monkeypatch.setattr(subprocess, "run", run)
    pending = []
    for base, command, shell in (
        ("https://notebook.google.com", "echo first-secret", "0"),
        ("https://notebooklm.google.com", "echo second-secret", "1"),
    ):
        monkeypatch.setenv("NOTEBOOKLM_REFRESH_CMD", command)
        monkeypatch.setenv("NOTEBOOKLM_REFRESH_CMD_USE_SHELL", shell)
        pending.append(
            NotebookLMClient.from_storage(
                path=path,
                profile="work",
                config=ClientConfig(
                    backend=WebBackendConfig(request=WebRequestOptions(base_url=base))
                ),
            )
        )
    monkeypatch.setenv("NOTEBOOKLM_REFRESH_CMD", "echo must-never-run")
    monkeypatch.setenv("NOTEBOOKLM_BASE_URL", "invalid-after-call")
    monkeypatch.setenv("NOTEBOOKLM_TRANSPORT", "invalid-after-call")
    clients = await asyncio.gather(*(context.__aenter__() for context in pending))
    try:
        assert len(commands) == 2
        for context in pending:
            with request_policy_scope(context.request_policy):
                assert single_flight.read_success_epoch(policy_key(str(path))) == 1
        entered.clear()
        recovered.clear()
        ready.clear()
        await asyncio.gather(*(client.refresh_auth() for client in clients))
        assert len(commands) == 4
        await asyncio.gather(*(client.notebooks.list() for client in clients))
        for client, context in zip(clients, pending, strict=True):
            selected = context.request_policy
            assert selected is not None
            assert client.auth.csrf_token == "csrf-" + httpx.URL(selected.base_url).host
            with request_policy_scope(selected):
                assert single_flight.read_success_epoch(policy_key(str(path))) == 2
        for target, shell, env in commands:
            assert env["NOTEBOOKLM_REFRESH_STORAGE_PATH"] == str(path)
            assert env["NOTEBOOKLM_REFRESH_PROFILE"] == "work"
            assert env["NOTEBOOKLM_TRANSPORT"] == "httpx"
            if env["NOTEBOOKLM_BASE_URL"] == "https://notebook.google.com":
                assert target == ["echo", "first-secret"] and shell is False
            else:
                assert target == "echo second-secret" and shell is True
        assert {r.url.host for r in requests} == {
            "notebook.google.com",
            "notebooklm.google.com",
            "accounts.google.com",
        }
    finally:
        await asyncio.gather(*(context.__aexit__(None, None, None) for context in pending))
