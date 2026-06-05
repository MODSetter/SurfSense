"""MCP (Model Context Protocol) integration: client, tool loading, and cache.

Split by responsibility:
- ``client``: the low-level :class:`MCPClient` connection wrapper.
- ``tool``: discovery + LangChain tool construction and cache invalidation.
- ``cache``: the connector tool-cache refresh helpers.
"""
