"""First-party construction policy expressed through the public options API."""

from __future__ import annotations

import os

from ..options import (
    AUTO,
    AndroidBackendConfig,
    ClientConfig,
    FeatureOptions,
    ReadWindow,
    WebBackendConfig,
    WebRequestOptions,
    WebSessionOptions,
    WebTransportOptions,
)


def adapter_client_config(
    *,
    backend: str | None = None,
    keepalive: float | None = None,
    timeout: float = 30.0,
    chat_timeout: ReadWindow = AUTO,
) -> ClientConfig:
    """Select Web's bound preview while preserving Android selection and budgets."""
    selected = backend if backend is not None else os.environ.get("NOTEBOOKLM_BACKEND", "web")
    owner: AndroidBackendConfig | WebBackendConfig
    if selected == "android":
        owner = AndroidBackendConfig(rpc_timeout=timeout)
    elif selected == "web":
        owner = WebBackendConfig(
            request=WebRequestOptions(),
            transport=WebTransportOptions(
                read_timeout=timeout, write_timeout=timeout, pool_timeout=timeout
            ),
            session=WebSessionOptions(keepalive_interval=keepalive),
        )
    else:
        raise ValueError("NotebookLM backend must be 'web' or 'android'")
    return ClientConfig(backend=owner, features=FeatureOptions(chat_timeout=chat_timeout))
