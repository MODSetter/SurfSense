"""Shared helpers for the Oxylabs AI Studio integration."""

_INTEGRATION_TAG = "surfsense"
_tag_set = False


def ensure_integration_tag() -> None:
    """Stamp SurfSense's integration tag into the Oxylabs SDK User-Agent.

    The ``oxylabs-ai-studio`` SDK resolves its outbound ``User-Agent`` from a
    module-level ``_UA_API`` variable, defaulting to ``"python-sdk"`` when
    unset. Setting it once before any client is constructed makes every Oxylabs
    request from SurfSense carry ``User-Agent: surfsense``, giving the vendor
    accurate source attribution.

    Idempotent (runs once per process) and best-effort: if the SDK is not
    importable yet, the client-construction site surfaces the ImportError.
    A value the user already set is not overwritten.
    """
    global _tag_set
    if _tag_set:
        return
    try:
        import oxylabs_ai_studio.client as _client

        if not getattr(_client, "_UA_API", None):
            _client._UA_API = _INTEGRATION_TAG
        _tag_set = True
    except Exception:
        # SDK not importable here — leave it to the actual client construction
        # site to surface the install error.
        pass
