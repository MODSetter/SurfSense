/**
 * MCP client setup catalog: one entry per popular agent, with the exact
 * config file, steps, and snippet needed to connect the SurfSense MCP server.
 * Shared by the marketing /mcp-server page and the API playground so the
 * instructions can never drift apart.
 */

export interface McpSnippetOptions {
	/** SurfSense backend URL the server should call. */
	baseUrl: string;
	/** API key value or placeholder to show in the snippet. */
	apiKey: string;
	/** Absolute path to the surfsense_mcp directory. */
	serverDir: string;
}

export interface McpClient {
	id: string;
	label: string;
	/** Where the snippet goes: a file path or "Terminal". */
	configFile: string;
	language: "json" | "toml" | "bash";
	steps: string[];
	buildConfig: (options: McpSnippetOptions) => string;
}

export const DEFAULT_SERVER_DIR = "/path/to/SurfSense/surfsense_mcp";
export const API_KEY_PLACEHOLDER = "ss_pat_your_key_here";

function serverArgs(serverDir: string): string[] {
	return ["run", "--directory", serverDir, "python", "-m", "surfsense_mcp"];
}

function json(value: unknown): string {
	return JSON.stringify(value, null, 2);
}

/** The `mcpServers` JSON shape shared by Cursor, Claude Desktop, Windsurf, and Gemini CLI. */
function standardJson({ baseUrl, apiKey, serverDir }: McpSnippetOptions): string {
	return json({
		mcpServers: {
			surfsense: {
				command: "uv",
				args: serverArgs(serverDir),
				env: { SURFSENSE_BASE_URL: baseUrl, SURFSENSE_API_KEY: apiKey },
			},
		},
	});
}

export const MCP_CLIENTS: McpClient[] = [
	{
		id: "claude-code",
		label: "Claude Code",
		configFile: "Terminal",
		language: "bash",
		steps: [
			"Run this command in a terminal (any directory).",
			"Start Claude Code and run /mcp — surfsense should be listed as connected.",
		],
		buildConfig: ({ baseUrl, apiKey, serverDir }) =>
			[
				"claude mcp add surfsense \\",
				`  -e SURFSENSE_BASE_URL=${baseUrl} \\`,
				`  -e SURFSENSE_API_KEY=${apiKey} \\`,
				`  -- uv run --directory ${serverDir} python -m surfsense_mcp`,
			].join("\n"),
	},
	{
		id: "codex",
		label: "Codex",
		configFile: "~/.codex/config.toml",
		language: "toml",
		steps: [
			"Add this to ~/.codex/config.toml (or run `codex mcp add surfsense -- uv run --directory <dir> python -m surfsense_mcp`).",
			"Restart Codex; `codex mcp list` should show surfsense.",
		],
		buildConfig: ({ baseUrl, apiKey, serverDir }) =>
			[
				"[mcp_servers.surfsense]",
				'command = "uv"',
				`args = ${JSON.stringify(serverArgs(serverDir))}`,
				"",
				"[mcp_servers.surfsense.env]",
				`SURFSENSE_BASE_URL = "${baseUrl}"`,
				`SURFSENSE_API_KEY = "${apiKey}"`,
			].join("\n"),
	},
	{
		id: "opencode",
		label: "OpenCode",
		configFile: "opencode.json",
		language: "json",
		steps: [
			"Add this to opencode.json in your project root (or ~/.config/opencode/opencode.json for all projects).",
			"Note OpenCode's format: the key is `mcp`, the command is one array, and env vars go under `environment`.",
		],
		buildConfig: ({ baseUrl, apiKey, serverDir }) =>
			json({
				$schema: "https://opencode.ai/config.json",
				mcp: {
					surfsense: {
						type: "local",
						command: ["uv", ...serverArgs(serverDir)],
						enabled: true,
						environment: { SURFSENSE_BASE_URL: baseUrl, SURFSENSE_API_KEY: apiKey },
					},
				},
			}),
	},
	{
		id: "cursor",
		label: "Cursor",
		configFile: "~/.cursor/mcp.json",
		language: "json",
		steps: [
			"Add this to ~/.cursor/mcp.json (global, keeps the key out of your repo) or a project's .cursor/mcp.json.",
			"Refresh the server in Cursor Settings → MCP; its 18 tools should appear.",
		],
		buildConfig: standardJson,
	},
	{
		id: "claude-desktop",
		label: "Claude Desktop",
		configFile: "claude_desktop_config.json",
		language: "json",
		steps: [
			"Open Settings → Developer → Edit Config to reach claude_desktop_config.json and add this.",
			"Restart Claude Desktop; surfsense appears under the tools icon.",
		],
		buildConfig: standardJson,
	},
	{
		id: "vscode",
		label: "VS Code",
		configFile: ".vscode/mcp.json",
		language: "json",
		steps: [
			"Add this to .vscode/mcp.json in your workspace (or run the MCP: Add Server command).",
			"Open Copilot Chat in agent mode and click the tools icon to confirm surfsense is loaded.",
		],
		buildConfig: ({ baseUrl, apiKey, serverDir }) =>
			json({
				servers: {
					surfsense: {
						type: "stdio",
						command: "uv",
						args: serverArgs(serverDir),
						env: { SURFSENSE_BASE_URL: baseUrl, SURFSENSE_API_KEY: apiKey },
					},
				},
			}),
	},
	{
		id: "windsurf",
		label: "Windsurf",
		configFile: "~/.codeium/windsurf/mcp_config.json",
		language: "json",
		steps: [
			"Add this to ~/.codeium/windsurf/mcp_config.json (or Windsurf Settings → Cascade → MCP Servers).",
			"Press the refresh button in the MCP panel to pick up the server.",
		],
		buildConfig: standardJson,
	},
	{
		id: "gemini-cli",
		label: "Gemini CLI",
		configFile: "~/.gemini/settings.json",
		language: "json",
		steps: [
			"Add this to ~/.gemini/settings.json (or .gemini/settings.json in a project).",
			"Run /mcp inside Gemini CLI to confirm the surfsense server and its tools.",
		],
		buildConfig: standardJson,
	},
];
