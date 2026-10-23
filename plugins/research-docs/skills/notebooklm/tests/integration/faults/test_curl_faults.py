"""Optional real curl lane: TLS, sessions, streaming uploads and publication."""

from __future__ import annotations

import asyncio
import ssl
import time

import pytest

pytest.importorskip("curl_cffi", reason="requires the optional [impersonate] extra")

from tests._fault_server.curl_scenarios import SCENARIOS, run_scenario  # noqa: E402

pytestmark = pytest.mark.allow_no_vcr


@pytest.mark.parametrize("scenario", SCENARIOS)
async def test_curl_fault_scenario(scenario: str) -> None:
    result = await asyncio.wait_for(run_scenario(scenario, operation_id=f"pytest-{scenario}"), 20)
    assert result.checks and all(result.checks.values())
    assert any(event["kind"] == "cleanup" for event in result.events)
    assert set(result.events[0]["required_checks"]) <= result.checks.keys()
    transport = next(event for event in result.events if event["kind"] == "transport")
    assert transport["selected"] == "curl_cffi"
    assert transport["tls_peer_verified"] and transport["tls_hostname_verified"]
    if scenario.startswith("curl_upload_"):
        assert transport["upload_handles"] == 2
        assert transport["body_descriptors"] == 2


@pytest.mark.parametrize("scenario", ["curl_download_body_stall", "curl_download_cancel"])
async def test_download_fault_survives_slow_tls_setup(
    scenario: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A slow real TLS handshake must not preempt the subsequent body fault."""
    original = ssl.SSLContext.load_cert_chain

    def load_with_slow_handshake(context, *args, **kwargs):
        original(context, *args, **kwargs)
        # Delay server-side TLS beyond the old 0.5-second connect deadline.
        # This is intentionally synchronous: a loaded Windows event loop may
        # also resume only after libcurl's wall-clock deadline has elapsed.
        context.sni_callback = lambda *_: time.sleep(0.6)

    monkeypatch.setattr(ssl.SSLContext, "load_cert_chain", load_with_slow_handshake)
    await test_curl_fault_scenario(scenario)


@pytest.mark.parametrize("scenario", ["curl_read_recovery", "curl_upload_cancel"])
async def test_read_and_upload_faults_survive_slow_tls_setup(
    scenario: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A slow TLS handshake must not fail a read or upload scenario's setup.

    Both scenarios failed on loaded Windows runners when the first loopback
    handshake outlasted the old 0.5-second request deadline.
    """
    original = ssl.SSLContext.load_cert_chain

    def load_with_slow_handshake(context, *args, **kwargs):
        original(context, *args, **kwargs)
        # Synchronous, like a starved event loop: libcurl's clock keeps running.
        context.sni_callback = lambda *_: time.sleep(0.8)

    monkeypatch.setattr(ssl.SSLContext, "load_cert_chain", load_with_slow_handshake)
    await test_curl_fault_scenario(scenario)
