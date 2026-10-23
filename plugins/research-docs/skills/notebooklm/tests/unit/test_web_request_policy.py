"""Bound Web policy through real construction, refresh, dispatch and transfers."""

from __future__ import annotations

import json
from urllib.parse import parse_qs

import httpx
import pytest

from notebooklm._env import get_base_url
from notebooklm._request_context import request_policy_scope
from notebooklm._request_policy import resolve_web_policy
from notebooklm.auth import AuthTokens
from notebooklm.client import NotebookLMClient
from notebooklm.options import ClientConfig, WebBackendConfig, WebRequestOptions
from notebooklm.rpc import RPCMethod

PERSONAL = "https://notebook.google.com"
LEGACY = "https://notebooklm.google.com"
ENTERPRISE = "https://notebooklm.cloud.google.com"
HTML = '"SNlM0e":"fresh-csrf" "FdrFJe":"fresh-session"'


def config(**kwargs):
    return ClientConfig(backend=WebBackendConfig(request=WebRequestOptions(**kwargs)))


def client_for(configuration=None):
    return NotebookLMClient(
        AuthTokens(cookies={"SID": "secret"}, csrf_token="original", session_id="old"),
        config=configuration,
    )


def install_http(monkeypatch, requests):
    original = httpx.AsyncClient

    def handler(request):
        requests.append(request)
        if request.url.path == "/":
            return httpx.Response(200, text=HTML)
        if request.url.path.startswith("/upload/"):
            return httpx.Response(
                200,
                headers={
                    "x-goog-upload-url": f"{request.url.scheme}://{request.url.host}/upload/_/?upload_id=id"
                },
            )
        if "rpcids" in request.url.params:
            rpcid = request.url.params["rpcids"]
            if rpcid == RPCMethod.GET_SHARE_STATUS.value:
                result = [None, [1]]
            elif rpcid == RPCMethod.CREATE_ARTIFACT.value:
                result = [["generated", None, None, None, 1]]
            else:
                result = []
            return httpx.Response(
                200, text=")]}'\n" + json.dumps([["wrb.fr", rpcid, json.dumps(result)]])
            )
        return httpx.Response(200, content=b"media")

    class Client(original):
        def __init__(self, **kwargs):
            super().__init__(**kwargs, transport=httpx.MockTransport(handler))

    monkeypatch.setattr(httpx, "AsyncClient", Client)
    monkeypatch.setenv("NOTEBOOKLM_DISABLE_KEEPALIVE_POKE", "1")
    return Client


def test_request_option_is_additive_and_redacts_recovery(monkeypatch):
    monkeypatch.setenv("NOTEBOOKLM_REFRESH_CMD", "sensitive-recovery-secret")
    bound = client_for(config())
    policy = bound._web_runtime.executor.request_policy
    assert policy is not None
    assert "sensitive-recovery-secret" not in repr(policy)
    assert "sensitive-recovery-secret" not in repr(config())
    assert "sensitive-recovery-secret" not in policy.identity
    assert client_for()._web_runtime.executor.request_policy is None
    assert WebBackendConfig().request is None
    with pytest.raises(TypeError):
        WebBackendConfig(request="bound")


@pytest.mark.parametrize(
    "base", ["http://notebook.google.com", "https://evil.invalid", PERSONAL + "/?secret=x"]
)
def test_bound_host_rejected_before_io(base):
    with pytest.raises(ValueError, match="must use https"):
        client_for(config(base_url=base))


@pytest.mark.asyncio
async def test_bound_rpc_refresh_upload_and_assets_keep_policy_and_live_auth(monkeypatch, tmp_path):
    requests = []
    chosen_factory = install_http(monkeypatch, requests)
    monkeypatch.setenv("NOTEBOOKLM_BASE_URL", PERSONAL)
    monkeypatch.setenv("NOTEBOOKLM_HL", "de")
    monkeypatch.setenv("NOTEBOOKLM_BL", "build-one")
    first = client_for(config())
    second = client_for(config(base_url=LEGACY, language="fr", build_label="build-two"))
    monkeypatch.setenv("NOTEBOOKLM_BASE_URL", ENTERPRISE)
    monkeypatch.setenv("NOTEBOOKLM_HL", "ja")
    monkeypatch.setenv("NOTEBOOKLM_BL", "changed-build")
    monkeypatch.setenv("NOTEBOOKLM_TRANSPORT", "invalid-after-capture")
    async with first, second:
        for client, expected_base, language, build in (
            (first, PERSONAL, "de", "build-one"),
            (second, LEGACY, "fr", "build-two"),
        ):
            web = client._web_runtime
            assert web.kernel._async_client_factory is chosen_factory
            await client.refresh_auth()
            assert requests[-1].url == expected_base + "/"
            web.kernel.cookies.set("LIVE", language, domain=".google.com")
            await client.notebooks.list()
            request = requests[-1]
            assert str(request.url).startswith(expected_base + "/_")
            assert request.url.params["hl"] == language
            assert request.url.params["f.sid"] == "fresh-session"
            assert parse_qs(request.content.decode())["at"] == ["fresh-csrf"]
            assert "LIVE=" + language in request.headers["cookie"]
            snapshot = await web.auth_coord.snapshot(auth=client.auth, expected_epoch=1)
            url, body, _ = client.chat._build_chat_request(
                snapshot=snapshot,
                notebook_id="nb",
                question="hello",
                source_ids=[],
                conversation_history=None,
                conversation_id=None,
                reqid=1,
            )
            assert url.startswith(expected_base)
            assert httpx.URL(url).params["hl"] == language
            assert httpx.URL(url).params["bl"] == build
            assert "at=fresh-csrf" in body
            async with web.source_uploader.transport_operation_scope("test-upload") as epoch:
                upload = await web.source_uploader.start_resumable_upload(
                    "nb",
                    "file.txt",
                    5,
                    "source",
                    "text/plain",
                    expected_epoch=epoch,
                )
            assert upload.startswith(expected_base + "/upload/")
            assert str(requests[-1].url).startswith(expected_base + "/upload/")
            assert "LIVE=" + language in requests[-1].headers["cookie"]
            output = tmp_path / language
            await client.artifacts._download_to_path(expected_base + "/media", str(output))
            assert output.read_bytes() == b"media"
            assert "LIVE=" + language in requests[-1].headers["cookie"]
            assert client.notebooks.get_share_url("a/b").startswith(
                expected_base + "/notebook/a%2Fb"
            )
            status = await client.sharing.get_status("a/b")
            assert status.share_url == expected_base + "/notebook/a%2Fb"
            for explicit_language, expected_language in ((None, language), ("ko", "ko")):
                await client.artifacts.generate_audio(
                    "nb", source_ids=[], language=explicit_language
                )
                wire = json.loads(parse_qs(requests[-1].content.decode())["f.req"][0])
                params = json.loads(wire[0][0][1])
                assert expected_language in json.dumps(params)
                assert '"ja"' not in json.dumps(params)
    assert get_base_url() == ENTERPRISE


@pytest.mark.asyncio
async def test_from_storage_captures_policy_at_call_before_deferred_loading(monkeypatch):
    requests = []
    install_http(monkeypatch, requests)
    names = ("SID", "HSID", "SSID", "APISID", "SAPISID", "__Secure-1PSID", "__Secure-1PSIDTS")
    monkeypatch.setenv(
        "NOTEBOOKLM_AUTH_JSON",
        json.dumps(
            {
                "cookies": [
                    {"name": name, "value": "secret", "domain": ".google.com", "path": "/"}
                    for name in names
                ]
            }
        ),
    )
    monkeypatch.setenv("NOTEBOOKLM_BASE_URL", LEGACY)
    monkeypatch.setenv("NOTEBOOKLM_HL", "es")
    pending = NotebookLMClient.from_storage(config=config())
    assert requests == []
    monkeypatch.setenv("NOTEBOOKLM_BASE_URL", "invalid-after-call")
    monkeypatch.setenv("NOTEBOOKLM_TRANSPORT", "invalid-after-call")
    monkeypatch.setenv("NOTEBOOKLM_HL", "ja")
    async with pending as client:
        assert requests[0].url == LEGACY + "/"
        await client.notebooks.list()
        assert requests[-1].url.host == "notebooklm.google.com"
        assert requests[-1].url.params["hl"] == "es"
        assert client._web_runtime.executor.request_policy is pending.request_policy


@pytest.mark.asyncio
async def test_legacy_client_still_resolves_dynamic_request_environment(monkeypatch):
    requests = []
    install_http(monkeypatch, requests)
    monkeypatch.setenv("NOTEBOOKLM_BASE_URL", PERSONAL)
    legacy = client_for()
    async with legacy:
        monkeypatch.setenv("NOTEBOOKLM_BASE_URL", LEGACY)
        monkeypatch.setenv("NOTEBOOKLM_HL", "it")
        await legacy.notebooks.list()
        assert requests[-1].url.host == "notebooklm.google.com"
        assert requests[-1].url.params["hl"] == "it"
        monkeypatch.setenv("NOTEBOOKLM_BASE_URL", PERSONAL)
        await legacy.refresh_auth()
        assert requests[-1].url == PERSONAL + "/"


def test_construction_inside_other_clients_scope_does_not_inherit_its_policy(monkeypatch):
    first = resolve_web_policy(WebRequestOptions(base_url=PERSONAL))
    monkeypatch.setenv("NOTEBOOKLM_BASE_URL", LEGACY)
    with request_policy_scope(first):
        nested = client_for(config())
    assert nested._web_runtime.executor.request_policy.base_url == LEGACY


@pytest.mark.asyncio
async def test_bound_policy_survives_close_and_reopen(monkeypatch):
    requests = []
    install_http(monkeypatch, requests)
    client = client_for(config(base_url=PERSONAL, language="fr"))
    async with client:
        await client.notebooks.list()
    monkeypatch.setenv("NOTEBOOKLM_BASE_URL", LEGACY)
    monkeypatch.setenv("NOTEBOOKLM_HL", "ja")
    async with client:
        await client.refresh_auth()
        await client.notebooks.list()
        assert requests[-1].url.host == "notebook.google.com"
        assert requests[-1].url.params["hl"] == "fr"


def test_bound_transport_factory_retains_curl_fingerprint(monkeypatch):
    from notebooklm import _curl_cffi_transport as transport

    calls = []
    monkeypatch.setattr(transport, "make_curl_cffi_factory", lambda value=None: calls.append(value))
    bound = resolve_web_policy(WebRequestOptions(transport="curl_cffi", impersonate="chrome124"))
    monkeypatch.setenv("NOTEBOOKLM_TRANSPORT", "httpx")
    monkeypatch.setenv("NOTEBOOKLM_IMPERSONATE", "changed")
    with request_policy_scope(bound):
        transport.resolve_transport_factory()
    assert calls == ["chrome124"]
    assert transport.resolve_transport_factory() is httpx.AsyncClient
    monkeypatch.setenv("NOTEBOOKLM_TRANSPORT", "curl_cffi")
    transport.resolve_transport_factory()
    assert calls == ["chrome124", None]  # legacy fingerprint stays deferred to client creation


@pytest.mark.asyncio
async def test_bound_policy_preserves_paired_live_account_adoption(monkeypatch):
    from notebooklm._auth.cookie_types import CookieJar

    requests = []
    install_http(monkeypatch, requests)
    client = client_for(config(base_url=PERSONAL, language="fr"))
    monkeypatch.setenv("NOTEBOOKLM_BASE_URL", LEGACY)
    async with client:
        web = client._web_runtime
        live = web.kernel.cookies
        source = httpx.Cookies({"SID": "adopted-secret"})
        adopted = await web.auth_coord.install_profile_session(
            auth=client.auth,
            target_cookie_jar=live,
            source_cookie_jar=source,
            expected_cookie_jar=CookieJar.from_httpx(live),
            expected_authuser=0,
            expected_account_email=None,
            expected_generation=client.auth._profile_session_generation,
            authuser=2,
            account_email="adopted@example.com",
            expected_epoch=1,
        )
        assert adopted
        await client.notebooks.list()
        assert requests[-1].url.host == "notebook.google.com"
        assert requests[-1].url.params["authuser"] == "adopted@example.com"
        assert "SID=adopted-secret" in requests[-1].headers["cookie"]
        assert "adopted-secret" not in repr(web.executor.request_policy)
