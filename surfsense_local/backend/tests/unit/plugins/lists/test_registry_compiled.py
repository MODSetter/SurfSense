from urllib.parse import urlsplit

import pytest

from modules.egress.service import BUILT_IN, PLUGIN_HOST, host_of
from modules.plugins.lists import plugin_host
from modules.plugins.lists.registry.registry_keys import REGISTRY_PUBLIC_KEYS_HEX

pytestmark = pytest.mark.unit


def test_the_production_registry_key_is_compiled_in() -> None:
    """The key CI signs with, so a shipped app trusts the published list."""
    assert REGISTRY_PUBLIC_KEYS_HEX[0] == (
        "9498a1606105a625feeaa655648df03885410421a387478a72ec763188f10395"
    )


def test_settings_network_lists_the_host_the_registry_is_fetched_from() -> None:
    """The built-in destination names the host the list is fetched from."""
    assert PLUGIN_HOST in BUILT_IN
    assert host_of(PLUGIN_HOST) == urlsplit(plugin_host.PLUGIN_HOST).hostname
