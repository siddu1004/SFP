# ADR-0039: Backend-specific credential surfaces

## Status

Accepted. The design is ready; the public cut is separately release-gated by the
[release migration gates](../deprecations.md#release-migration-gates) and does not take effect until C9b.

## Context

The 0.x constructor requires a mutable, Web-shaped `AuthTokens` even when the selected backend is
Android. Stored Android construction first loads Web cookies and fetches Web request tokens before
the Android runtime reads `master_token.json`. The root client consequently exposes Web CSRF,
session, cookie, and `authuser` state for an Android runtime whose actual credential is a durable
master token. The deprecated `rpc_call()` wrapper is the only typed Android-client feature that
needs the lazy Web compatibility sidecar.

ADR-0032 already fixes the Web destination: `AuthTokens` becomes an immutable bootstrap value with
`initial_cookies`, while the Web runtime owns mutable cookies and request tokens. ADR-0023 and
ADR-0034 already assign master-token persistence, locking, redaction, and minting to `ProfileStore`,
`MasterTokenFile`, `MintService`, and the bearer provider. The missing decision is the public
boundary between those two credential families.

The boundary is a v1 change. ADR acceptance establishes the destination, but it does not prove that
the warning window shipped. The exact public and behavioral breaks, including later C3/C4/C5
migrations, remain independently gated in the release ledger.

## Decision

The v1 client selects a backend before credential loading, accepts only that backend's credential
kind, and keeps credentials outside `ClientConfig`.

### Direct construction

The v1 direct signature is conceptually:

```python
NotebookLMClient(
    credential: AuthTokens | AndroidMasterToken,
    *,
    config: ClientConfig | None = None,
)
```

`AuthTokens` is explicitly the Web bootstrap credential and takes ADR-0032's frozen destination
shape: `initial_cookies`, initial `csrf_token` and `session_id`, `authuser`, `account_email`, and
optional `storage_path`. `initial_cookies` is copied once into Web runtime ownership. It is not a
live cookie jar, and the object is not mutated by refresh.

`AndroidMasterToken` is a public frozen, redacted direct credential with `email`, `android_id`, and
a secret master-token value excluded from repr, errors, logs, metrics, and serialization helpers.
It is the public projection of the existing internal `MasterToken` value; implementation must keep
one canonical value rather than introduce a second independent token model.

The selected backend comes from `ClientConfig.backend`, then `NOTEBOOKLM_BACKEND`, then the Web
default. A credential never selects or overrides the backend implicitly. Web plus
`AndroidMasterToken`, or Android plus `AuthTokens`, raises `ConfigurationError` synchronously before
filesystem access, optional-dependency checks, credential acquisition, or network I/O. Android does
not accept an empty or fabricated `AuthTokens` placeholder.

### Stored construction and precedence

`NotebookLMClient.from_storage(path, profile, allow_headless, *, config=...)` remains the canonical
factory. It resolves the backend using the same frozen preference before it parses or loads any
credential source.

For Web, precedence remains:

1. an explicit `path`;
2. presence of `NOTEBOOKLM_AUTH_JSON`, including an empty or malformed value that fails as Web
   input rather than falling through;
3. the explicit, environment-selected, active, or default profile.

For Android, precedence is:

1. an explicit `path`, interpreted as the profile storage-state location whose sibling is
   `master_token.json`; the storage-state file itself need not exist;
2. the explicit, environment-selected, active, or default profile and its nominal
   `master_token.json`.

Android ignores `NOTEBOOKLM_AUTH_JSON` without parsing it because that value is not an Android
credential. An explicit path wins over `profile` for both backends; `profile` may remain contextual
metadata but cannot redirect the credential read. C9b removes the pre-profiles home-root fallback
and preserves the relative order above. Android path resolution must start from the nominal profile
directory and cannot let a legacy cookie-file fallback redirect master-token lookup.

Direct credentials are already resolved and therefore outrank every stored source. Direct Web
`AuthTokens.storage_path` only selects its persistence target. A direct Android token remains
in-memory unless a separate explicit persistence operation writes it; construction never silently
stores a durable account credential.

Existing `ProfileStore` transaction semantics remain authoritative: canonical paths and profile
locks are resolved once; writes use the existing inter-process locks, atomic replacement,
permissions, snapshot/CAS rules, and account-route checks. Backend dispatch changes which loader
runs, not the on-disk formats or transaction guarantees. Missing, unreadable, malformed, and
wrong-account sources remain distinguishable and secret-free.

### Public identity and refresh

`client.auth` becomes a selected-backend view:

- Web returns the immutable Web `AuthTokens` bootstrap value. Mutable live cookies, CSRF/session
  replacements, persistence baselines, and generation/CAS state stay private to Web owners.
- Android returns a frozen, secret-free `AndroidAuth` view containing the authoritative master-token
  `email` and `android_id`. It never exposes the durable master-token secret or Web fields.

This ends ADR-0016's mutable `AuthTokens` identity invariant at the C9b cut. ADR-0016's logger-name
decision remains unchanged. Code that needs the account identity uses
`get_account_email()` rather than reading backend-specific credential fields.

`get_account_email()` remains backend-neutral and network-free when identity is already known.
For Android, the master-token email is authoritative after the credential is loaded; stale Web
cookie/profile account metadata is irrelevant. Directly constructed clients may report their
credential's identity before open. A stored client does not exist until the factory has loaded its
credential, so it has the same identity once yielded or returned.

`get_account_authuser()` is Web-only at v1. On Android it raises the public
`UnsupportedOperationError` before I/O. Web retains the route paired with its current Web account
state.

`refresh_auth(*, allow_headless=False)` is side-effect-only and returns `None` on both backends.
Web refreshes its live cookie/request-token owners and persists through the existing transaction
boundary. Android invalidates and re-mints its bearer from the selected master token without Web
I/O. `allow_headless=True` is a Web-only recovery request and raises `UnsupportedOperationError` on
Android. Refresh neither replaces nor reveals the Android durable credential.

### Compatibility and release gates

C9b removes the root `rpc_call()` wrapper and `LazyWebSidecar`; typed Android operations, import,
construction, open, refresh, close, CLI, MCP, and REST must then load no Web implementation module,
allocate no Web object, parse no Web inline credential, and make no Web request.

The release cut also completes ADR-0032's scheduled `AuthTokens` removals, the deprecated public
row decoders, awaitable storage factory, flat tuning arguments, polling/confirmation transitions,
and every other row in the full P8 registry. API-audit allowances apply only to breaks the audit
actually reports. Behavioral-only changes remain in the v1 runway registry and behavioral tests.
No C9b change may borrow another row's warning date, and no source comment or unreleased registry
entry counts as a shipped warning.

## Consequences

Android can be constructed and opened from only `master_token.json`, without a cookie file,
homepage request, Web optional dependency, or fake Web credential. Credential mismatch failures
move to a deterministic pre-I/O boundary. Web keeps the accepted ADR-0032 bootstrap model, and
`ClientConfig` remains safe to inspect because it contains policy rather than secrets.

The public surface gains `AndroidMasterToken` and `AndroidAuth`, and changes constructor,
`client.auth`, `refresh_auth()`, and Android `get_account_authuser()` contracts. Those are real API
or behavior migrations and require their own shipped notice evidence recorded in the ledger; ADR
acceptance alone cannot authorize them.

Backend-specific views mean callers that inspect raw authentication details must branch on the
selected backend. The backend-neutral account-email method is the stable identity seam. A direct
Android caller holds the durable secret it supplied, while a stored-auth caller cannot retrieve
that secret through the client.

## Alternatives considered

**Keep requiring `AuthTokens` and manufacture empty Web fields for Android.** Rejected because it
preserves a false credential type, makes invalid state constructible, and keeps Android bootstrap
coupled to Web failure timing.

**Put credentials on `ClientConfig`.** Rejected because configuration is frozen, inspectable policy;
placing cookie or master-token secrets there would mix precedence, persistence, diagnostics, and
redaction responsibilities.

**Let the credential choose the backend.** Rejected because backend preference is already an
independent explicit/env/default decision. Implicit selection makes configuration mistakes silently
change transport and prevents a clean mismatch-before-I/O contract.

**Expose the stored Android master-token secret through `client.auth`.** Rejected because the token
is a durable account-equivalent credential. Identity is useful to callers; secret retrieval is not
required for client operation and would widen the exfiltration surface.

**Unify Web cookies and Android bearer refresh behind one public mutable credential provider.**
Rejected because the two backends have different credential tiers, storage, wire lifetimes, and
security impact. Neutral lifecycle coordination does not require a universal public auth object.
