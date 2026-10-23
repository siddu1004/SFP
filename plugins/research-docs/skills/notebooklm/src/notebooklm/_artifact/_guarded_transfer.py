"""Backend-neutral guarded streaming transfer for generated artifact assets."""

from __future__ import annotations

import asyncio
import os
import sys
import tempfile
from collections.abc import AsyncGenerator, Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, NamedTuple
from urllib.parse import urljoin

import httpx

from .._hop_credentials import CredentialPolicy, HopCredentials
from ..exceptions import AuthError

MAX_DOWNLOAD_REDIRECTS = 20
MAX_APPLICATION_REDIRECT_BYTES = 8_192
# Bytes per request on hosts the caller marks as ranged. googlevideo throttles a
# whole-file GET, an open-ended range, or any range above about 10 MiB to roughly
# playback speed (~32 KiB/s, measured 2026-10-14), while ranges of up to 10 MiB
# arrive at full speed. Read at call time so tests can shrink it.
RANGED_TRANSFER_CHUNK_BYTES = 8 * 1024 * 1024


@dataclass(frozen=True)
class FormatPolicy:
    """Allowed content types and magic-byte checks for one representation format."""

    media_types: frozenset[str]
    signature_checks: tuple[tuple[bytes, int], ...]
    suffix_replacement: tuple[str, str] | None = None


@dataclass(frozen=True)
class TransferPolicy:
    """Bounded content policy for one artifact representation."""

    artifact_type: str
    formats: tuple[FormatPolicy, ...]
    max_bytes: int
    capability_initial_hosts: frozenset[str] = frozenset()


@dataclass(frozen=True)
class TransferFailure:
    """Bounded failure receipt that cannot retain a capability URL or response."""

    code: str
    approved_host: str
    hop: int


@dataclass(frozen=True)
class TransferSuccess:
    output_path: str
    byte_count: int


def _clear_client_cookies(client: Any) -> None:
    """Keep every manually validated hop free of ambient response cookies."""

    for owner in (client, getattr(client, "_curl", None)):
        cookies = getattr(owner, "cookies", None)
        clear = getattr(cookies, "clear", None)
        if callable(clear):
            clear()


async def _capture_advisory_cleanup(cleanup: Awaitable[Any]) -> BaseException | None:
    """Observe every cleanup outcome without leaving an unhandled task error."""

    try:
        await cleanup
    except BaseException as error:
        return error
    return None


async def _await_advisory_cleanup(
    cleanup: Awaitable[Any],
    *,
    pending_error: BaseException | None,
) -> None:
    """Finish advisory cleanup while preserving cancellation and exit precedence."""

    cleanup_task = asyncio.create_task(_capture_advisory_cleanup(cleanup))
    cancellation: asyncio.CancelledError | None = None
    while True:
        try:
            cleanup_error = await asyncio.shield(cleanup_task)
            break
        except asyncio.CancelledError as error:
            if cancellation is None:
                cancellation = error

    process_exit = (
        cleanup_error if isinstance(cleanup_error, (KeyboardInterrupt, SystemExit)) else None
    )
    cleanup_cancellation = (
        cleanup_error if isinstance(cleanup_error, asyncio.CancelledError) else None
    )
    preserve_pending = isinstance(
        pending_error,
        (asyncio.CancelledError, KeyboardInterrupt, SystemExit),
    )
    del cleanup, cleanup_error, cleanup_task, pending_error
    if process_exit is not None:
        raise process_exit
    if preserve_pending:
        return
    if cancellation is not None:
        raise cancellation
    if cleanup_cancellation is not None:
        raise cleanup_cancellation


def _single_location(headers: Any) -> str | None:
    get_list = getattr(headers, "get_list", None)
    values = get_list("location") if callable(get_list) else []
    if not values:
        value = headers.get("location")
        values = [] if value is None else [value]
    if len(values) != 1:
        return None
    location, *_unexpected = values
    return location or None


def _format_for_media_type(policy: TransferPolicy, media_type: str) -> FormatPolicy | None:
    return next((item for item in policy.formats if media_type in item.media_types), None)


def _declared_content_length(headers: Any) -> int | None:
    raw = headers.get("content-length")
    if raw is None:
        return None
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return -1
    return value if value >= 0 else -1


class _RangeMismatch(Exception):
    """A ranged response broke the contiguous single-entity contract."""


class _PartStatus(Exception):
    """A later part was answered with neither 200 nor 206."""

    def __init__(self, status: int) -> None:
        super().__init__()
        self.status = status


class _LifecycleFenced(Exception):
    """Carry a lifecycle fence raised between parts past the transport catch-all."""

    def __init__(self, error: Exception) -> None:
        super().__init__()
        self.error = error


class _ContentRange(NamedTuple):
    start: int
    end: int
    total: int


def _content_range(headers: Any) -> _ContentRange | None:
    """Parse ``bytes START-END/TOTAL`` with a known total, or return ``None``."""

    raw = headers.get("content-range") or ""
    unit, _, spec = raw.strip().partition(" ")
    span, _, total = spec.partition("/")
    first, _, last = span.partition("-")
    if unit.lower() != "bytes" or not all(
        part.isascii() and part.isdigit() for part in (first, last, total)
    ):
        return None
    try:
        start, end, size = int(first), int(last), int(total)
    except ValueError:  # beyond the interpreter's integer-string digit limit
        return None
    if start > end or end >= size:
        return None
    return _ContentRange(start, end, size)


def _validators(headers: Any) -> tuple[str | None, str | None]:
    """Return ``(ETag, Last-Modified)``, treating blank values and weak ETags as absent.

    A weak ETag promises only semantic equivalence, not identical bytes, so it
    cannot vouch for stitching byte ranges together (RFC 9110 section 8.8.1).
    """

    etag = (headers.get("etag") or "").strip() or None
    if etag is not None and etag.startswith("W/"):
        etag = None
    last_modified = (headers.get("last-modified") or "").strip() or None
    return etag, last_modified


async def _ranged_body(
    client: Any,
    url: str,
    headers: dict[str, str],
    first: Any,
    first_range: _ContentRange,
    media_type: str,
    approved_host: str,
    assert_active: Callable[[], None],
) -> AsyncGenerator[bytes, None]:
    """Yield one entity from contiguous range responses, starting with ``first``.

    Every part must continue exactly where the previous one ended, describe the
    same total, media type and validators, and carry exactly its declared byte
    count. googlevideo ignores ``If-Range``, so a changed entity is detected by
    comparing ``ETag`` and ``Last-Modified`` on every part instead; a first part
    with neither cannot be continued.
    """

    start, end, size = first_range
    validators = _validators(first.headers)
    # Shortened parts are accepted, but must not turn one download into an
    # unbounded number of requests.
    parts_left = 2 * -(-size // RANGED_TRANSFER_CHUNK_BYTES) - 1
    response = first
    response_cm: Any | None = None
    try:
        while True:
            received = 0
            async for chunk in response.aiter_bytes():
                received += len(chunk)
                if received > end - start + 1:
                    raise _RangeMismatch
                yield chunk
            if received != end - start + 1:
                raise _RangeMismatch
            if end == size - 1:
                return
            # Without a validator, parts cannot be shown to be one entity.
            if parts_left == 0 or validators == (None, None):
                raise _RangeMismatch
            parts_left -= 1
            if response_cm is not None:
                cm, response_cm = response_cm, None
                await _await_advisory_cleanup(cm.__aexit__(None, None, None), pending_error=None)
            try:
                assert_active()
            except Exception as error:
                raise _LifecycleFenced(error) from None
            next_start = end + 1
            next_end = min(next_start + RANGED_TRANSFER_CHUNK_BYTES, size) - 1
            _clear_client_cookies(client)
            response_cm = client.stream(
                "GET",
                url,
                headers={**headers, "Range": f"bytes={next_start}-{next_end}"},
                follow_redirects=False,
            )
            response = await response_cm.__aenter__()
            status = int(response.status_code)
            if status in {401, 403}:
                raise _auth_error(status, approved_host)
            if status not in {200, 206}:
                raise _PartStatus(status)
            part = _content_range(response.headers) if status == 206 else None
            part_type = response.headers.get("content-type", "").split(";", 1)[0].strip().lower()
            if (
                part is None
                or part.start != next_start
                or part.end > next_end
                or part.total != size
                or part_type != media_type
                or _validators(response.headers) != validators
            ):
                raise _RangeMismatch
            start, end, _ = part
    finally:
        pending_error = sys.exc_info()[1]
        try:
            if response_cm is not None:
                await _await_advisory_cleanup(
                    response_cm.__aexit__(None, None, None),
                    pending_error=pending_error,
                )
        finally:
            _clear_client_cookies(client)
            del first, headers, pending_error, response, response_cm, url


def _fsync_directory(path: Path) -> None:
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError:
        return
    try:
        os.fsync(descriptor)
    except OSError:
        pass
    finally:
        os.close(descriptor)


async def _bounded_text(response: Any) -> bytes | None:
    body = bytearray()
    async for chunk in response.aiter_bytes():
        body.extend(chunk)
        if len(body) > MAX_APPLICATION_REDIRECT_BYTES:
            return None
    return bytes(body)


async def _credentials_for_hop(
    credential_for: CredentialPolicy,
    url: str,
    assert_active: Callable[[], None],
) -> HopCredentials | None:
    """Acquire one hop credential without retaining it on acquisition failure."""

    credentials = None
    try:
        credentials = await credential_for(url)
        assert_active()
        return credentials
    finally:
        del assert_active, credential_for, credentials, url


def _auth_error(status: int, approved_host: str) -> AuthError:
    return AuthError(
        f"Authentication required for {approved_host} (HTTP {status}) -- try `notebooklm login`"
    )


async def guarded_transfer(
    client: Any,
    url: str,
    output_path: str,
    *,
    policy: TransferPolicy,
    credential_for: CredentialPolicy,
    validate_url: Callable[[str], str | None],
    safe_host: Callable[[str], str],
    assert_active: Callable[[], None],
    chain: bool = False,
    max_redirects: int = MAX_DOWNLOAD_REDIRECTS,
    ranged_hosts: Callable[[str], bool] | None = None,
) -> TransferSuccess | TransferFailure:
    """Transfer one representation with per-hop URL, credential, and content checks.

    On a hop whose approved host satisfies ``ranged_hosts``, the body is fetched
    as contiguous ranges of at most ``RANGED_TRANSFER_CHUNK_BYTES``. A server
    that ignores the range and answers 200 is streamed as usual.
    """

    current_url: str | None = url
    staging: Path | None = None
    try:
        for hop in range(max_redirects + 1):
            assert_active()
            assert current_url is not None
            host = validate_url(current_url)
            if host is None:
                return TransferFailure("url_policy", safe_host(current_url), hop)

            credentials = await _credentials_for_hop(credential_for, current_url, assert_active)

            response_cm: Any | None = None
            response: Any | None = None
            ranged_parts: AsyncGenerator[bytes, None] | None = None
            first_range: _ContentRange | None = None
            lifecycle_failure: BaseException | None = None
            ranged = ranged_hosts is not None and ranged_hosts(host)
            try:
                _clear_client_cookies(client)
                headers = {} if credentials is None else dict(credentials.headers)
                response_cm = client.stream(
                    "GET",
                    current_url,
                    headers=(
                        {**headers, "Range": f"bytes=0-{RANGED_TRANSFER_CHUNK_BYTES - 1}"}
                        if ranged
                        else headers
                    ),
                    follow_redirects=False,
                )
                response = await response_cm.__aenter__()
                status = int(response.status_code)

                if status in {301, 302, 303, 307, 308}:
                    location = _single_location(response.headers)
                    if location is None:
                        return TransferFailure("redirect", host, hop)
                    current_url = urljoin(current_url, location)
                    continue
                if status in {401, 403}:
                    public_error = _auth_error(status, host)
                    if chain and isinstance(response, httpx.Response):
                        raw_error = httpx.HTTPStatusError(
                            f"HTTP {status}", request=response.request, response=response
                        )
                        raise public_error from raw_error
                    raise public_error from None
                if ranged and status == 206:
                    first_range = _content_range(response.headers)
                    if first_range is None or first_range.start != 0:
                        return TransferFailure("range", host, hop)
                elif status != 200:
                    return TransferFailure(f"http_{status}", host, hop)

                content_type = response.headers.get("content-type", "")
                media_type = content_type.split(";", 1)[0].strip().lower()
                if media_type == "text/plain" and first_range is not None:
                    return TransferFailure("range", host, hop)
                if media_type == "text/plain":
                    body = await _bounded_text(response)
                    if body is None:
                        return TransferFailure("application_redirect_size", host, hop)
                    try:
                        redirect_url = body.decode("utf-8", errors="strict").strip()
                    except UnicodeDecodeError:
                        return TransferFailure("application_redirect_encoding", host, hop)
                    if not redirect_url or any(ord(char) < 32 for char in redirect_url):
                        return TransferFailure("application_redirect", host, hop)
                    current_url = redirect_url
                    continue

                format_policy = _format_for_media_type(policy, media_type)
                if format_policy is None:
                    return TransferFailure("content_type", host, hop)
                declared_length = (
                    _declared_content_length(response.headers)
                    if first_range is None
                    else first_range.total
                )
                if declared_length is not None and (
                    declared_length < 0 or declared_length > policy.max_bytes
                ):
                    return TransferFailure("size", host, hop)

                destination = Path(output_path)
                if (
                    format_policy.suffix_replacement is not None
                    and destination.suffix.lower() == format_policy.suffix_replacement[0]
                ):
                    destination = destination.with_suffix(format_policy.suffix_replacement[1])
                destination.parent.mkdir(parents=True, exist_ok=True)
                fd, staging_name = tempfile.mkstemp(
                    prefix=f".{destination.name}.", suffix=".part", dir=destination.parent
                )
                staging = Path(staging_name)
                total = 0
                prefix = bytearray()
                signatures = format_policy.signature_checks
                required_prefix = max(
                    (offset + len(signature) for signature, offset in signatures),
                    default=0,
                )
                if first_range is not None:
                    ranged_parts = _ranged_body(
                        client,
                        current_url,
                        headers,
                        response,
                        first_range,
                        media_type,
                        host,
                        assert_active,
                    )
                with os.fdopen(fd, "wb") as handle:
                    async for chunk in (
                        response.aiter_bytes() if ranged_parts is None else ranged_parts
                    ):
                        if not chunk:
                            continue
                        if total + len(chunk) > policy.max_bytes:
                            return TransferFailure("size", host, hop)
                        if len(prefix) < required_prefix:
                            prefix.extend(chunk[: required_prefix - len(prefix)])
                        handle.write(chunk)
                        total += len(chunk)
                    handle.flush()
                    os.fsync(handle.fileno())
                if total == 0:
                    return TransferFailure("empty", host, hop)
                if not all(
                    bytes(prefix[offset : offset + len(signature)]) == signature
                    for signature, offset in signatures
                ):
                    return TransferFailure("signature", host, hop)
                try:
                    assert_active()
                except BaseException as error:
                    # Lifecycle fences are not transport failures. Defer the
                    # raise until the response has been closed and credentials
                    # have been deleted by the hop finalizer below.
                    lifecycle_failure = error
                if lifecycle_failure is None:
                    os.replace(staging, destination)
                    staging = None
                    _fsync_directory(destination.parent)
                    return TransferSuccess(str(destination), total)
            except asyncio.CancelledError:
                raise
            except (KeyboardInterrupt, SystemExit):
                raise
            except AuthError:
                raise
            except _RangeMismatch:
                return TransferFailure("range", host, hop)
            except _PartStatus as part_status:
                return TransferFailure(f"http_{part_status.status}", host, hop)
            except _LifecycleFenced as fenced:
                # Like the pre-publish fence: raise after the hop is closed.
                lifecycle_failure = fenced.error
            except BaseException:
                return TransferFailure("transport", host, hop)
            finally:
                pending_error = sys.exc_info()[1]
                try:
                    if ranged_parts is not None:
                        # Close an abandoned continuation part before the first.
                        await _await_advisory_cleanup(
                            ranged_parts.aclose(),
                            pending_error=pending_error,
                        )
                finally:
                    try:
                        if response_cm is not None:
                            await _await_advisory_cleanup(
                                response_cm.__aexit__(None, None, None),
                                pending_error=pending_error,
                            )
                    finally:
                        _clear_client_cookies(client)
                        del credentials, pending_error, ranged_parts, response, response_cm
            if lifecycle_failure is not None:
                raise lifecycle_failure
        return TransferFailure("too_many_hops", safe_host(current_url or ""), max_redirects)
    finally:
        if staging is not None:
            try:
                staging.unlink(missing_ok=True)
            except OSError:
                pass
        del current_url, policy, staging, url


__all__ = [
    "FormatPolicy",
    "MAX_DOWNLOAD_REDIRECTS",
    "TransferFailure",
    "TransferPolicy",
    "TransferSuccess",
    "guarded_transfer",
]
