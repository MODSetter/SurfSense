# Plugins

A plugin is a remote [MCP](https://modelcontextprotocol.io) server that gives SurfSense's agent tools. Its publisher hosts the server; SurfSense lists it, asks the user before connecting, and calls it. Any MCP server that works in other MCP clients works here unchanged. How SurfSense handles plugins is in [plugins](../../docs/architecture/plugins.md).

| Folder | What it holds |
|---|---|
| [`registry/`](registry/) | The list of third-party plugins, their icons, the check every entry passes, and the container that serves them |
| [`host/`](host/), [`mcp_server/`](mcp_server/), [`proprietary/`](proprietary/) | SurfSense's own plugins and the plugin host that runs them, in the one [backend](../../docs/architecture/backend.md). Maintainers only for `proprietary/` |
| [`bundles/`](bundles/README.md) | Deferred. The earlier, local design's SDK and tooling, kept for plugins that run on the user's machine |

**Want to add your plugin?** Read [**Add your plugin to SurfSense**](registry/README.md): what a plugin is, how to get your MCP server ready, try it in the app, and list it with one pull request. It is written for coding agents as well as people.
