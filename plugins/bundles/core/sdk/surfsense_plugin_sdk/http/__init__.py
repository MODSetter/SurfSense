"""The plugin's own HTTP, limited to the hosts its manifest declares."""

from surfsense_plugin_sdk.http.declared_hosts import HostNotDeclared
from surfsense_plugin_sdk.http.response import Response
from surfsense_plugin_sdk.http.sending import get, post, request

__all__ = ["HostNotDeclared", "Response", "get", "post", "request"]
