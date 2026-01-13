"use client";

import { CheckCircle2, Server, XCircle } from "lucide-react";
import { type FC, useRef, useState } from "react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { EnumConnectorName } from "@/contracts/enums/connector";
import type { MCPServerConfig, MCPToolDefinition } from "@/contracts/types/mcp.types";
import { connectorsApiService } from "@/lib/apis/connectors-api.service";
import type { ConnectFormProps } from "..";

const DEFAULT_CONFIG = `[
  {
    "name": "MCP Server 1",
    "command": "npx",
    "args": ["-y", "@modelcontextprotocol/server-filesystem", "/path/to/allowed/directory"],
    "env": {},
    "transport": "stdio"
  }
]`;

interface MCPServerWithName extends MCPServerConfig {
	name: string;
}

export const MCPConnectForm: FC<ConnectFormProps> = ({ onSubmit, isSubmitting }) => {
	const isSubmittingRef = useRef(false);
	const [configJson, setConfigJson] = useState(DEFAULT_CONFIG);
	const [jsonError, setJsonError] = useState<string | null>(null);
	const [isTesting, setIsTesting] = useState(false);
	const [testResults, setTestResults] = useState<Array<{
		name: string;
		status: "success" | "error";
		message: string;
		tools: MCPToolDefinition[];
	}> | null>(null);

	const parseConfigs = (): { configs: MCPServerWithName[] | null; error: string | null } => {
		try {
			const parsed = JSON.parse(configJson);
			
			// Must be an array
			if (!Array.isArray(parsed)) {
				return {
					configs: null,
					error: "Configuration must be an array of MCP server objects",
				};
			}

			if (parsed.length === 0) {
				return {
					configs: null,
					error: "Array must contain at least one MCP server configuration",
				};
			}

			// Validate each server config
			const configs: MCPServerWithName[] = [];
			for (let i = 0; i < parsed.length; i++) {
				const server = parsed[i];
				
				if (!server.name || typeof server.name !== "string") {
					return {
						configs: null,
						error: `Server ${i + 1}: 'name' field is required and must be a string`,
					};
				}

				if (!server.command || typeof server.command !== "string") {
					return {
						configs: null,
						error: `Server ${i + 1} (${server.name}): 'command' field is required and must be a string`,
					};
				}

				configs.push({
					name: server.name,
					command: server.command,
					args: Array.isArray(server.args) ? server.args : [],
					env: typeof server.env === "object" && server.env !== null ? server.env : {},
					transport: server.transport || "stdio",
				});
			}

			return { configs, error: null };
		} catch (error) {
			return {
				configs: null,
				error: error instanceof Error ? error.message : "Invalid JSON",
			};
		}
	};

	const handleConfigChange = (value: string) => {
		setConfigJson(value);
		if (jsonError) {
			setJsonError(null);
		}
	};

	const handleTestConnection = async () => {
		const { configs, error } = parseConfigs();
		
		if (!configs || error) {
			setJsonError(error);
			setTestResults([{
				name: "Parse Error",
				status: "error",
				message: error || "Invalid configuration",
				tools: [],
			}]);
			return;
		}

		setIsTesting(true);
		setTestResults(null);
		setJsonError(null);

		const results: Array<{
			name: string;
			status: "success" | "error";
			message: string;
			tools: MCPToolDefinition[];
		}> = [];

		for (const config of configs) {
			try {
				const result = await connectorsApiService.testMCPConnection(config);
				results.push({
					name: config.name,
					...result,
				});
			} catch (error) {
				results.push({
					name: config.name,
					status: "error",
					message: error instanceof Error ? error.message : "Failed to connect to MCP server",
					tools: [],
				});
			}
		}

		setTestResults(results);
		setIsTesting(false);
	};

	const handleSubmit = async (e: React.FormEvent) => {
		e.preventDefault();

		// Prevent multiple submissions
		if (isSubmittingRef.current || isSubmitting) {
			return;
		}

		const { configs, error } = parseConfigs();
		
		if (!configs || error) {
			setJsonError(error);
			alert(error || "Invalid JSON configuration");
			return;
		}

		isSubmittingRef.current = true;
		try {
			// Submit all servers
			for (const config of configs) {
				await onSubmit({
					name: config.name,
					connector_type: EnumConnectorName.MCP_CONNECTOR,
					config: { server_config: config },
					is_indexable: false,
					is_active: true,
					last_indexed_at: null,
					periodic_indexing_enabled: false,
					indexing_frequency_minutes: null,
					next_scheduled_at: null,
				});
			}
		} finally {
			isSubmittingRef.current = false;
		}
	};

	return (
		<div className="space-y-6 pb-6">
			<Alert className="bg-slate-400/5 dark:bg-white/5 border-slate-400/20 p-2 sm:p-3 flex items-start [&>svg]:relative [&>svg]:left-0 [&>svg]:top-1">
				<Server className="h-4 w-4 shrink-0 ml-1" />
				<div className="-ml-1">
					<AlertTitle className="text-xs sm:text-sm">MCP Servers</AlertTitle>
					<AlertDescription className="text-[10px] sm:text-xs pl-0!">
						Connect to one or more MCP (Model Context Protocol) servers. Paste a JSON array of server configurations below.
					</AlertDescription>
				</div>
			</Alert>

			<form id="mcp-connect-form" onSubmit={handleSubmit} className="space-y-6">
				<div className="rounded-xl border border-border bg-slate-400/5 dark:bg-white/5 p-4 sm:p-6 space-y-4">
					<div className="space-y-2">
						<Label htmlFor="config">MCP Servers Configuration (JSON Array)</Label>
						<Textarea
							id="config"
							value={configJson}
							onChange={(e) => handleConfigChange(e.target.value)}
							placeholder={DEFAULT_CONFIG}
							rows={16}
							className={`font-mono text-xs ${jsonError ? "border-red-500" : ""}`}
						/>
						{jsonError && (
							<p className="text-xs text-red-500">JSON Error: {jsonError}</p>
						)}
						<p className="text-[10px] sm:text-xs text-muted-foreground">
							Paste an array of MCP server configurations. Each object must have: name, command, args (optional), env (optional), transport (optional).
						</p>
					</div>

					<div className="pt-4">
						<Button
							type="button"
							onClick={handleTestConnection}
							disabled={isTesting}
							variant="outline"
							className="w-full"
						>
							{isTesting ? "Testing All Servers..." : "Test All Connections"}
						</Button>
					</div>

					{testResults && testResults.length > 0 && (
						<div className="space-y-3">
							{testResults.map((result, index) => (
								<Alert
									key={index}
									className={
										result.status === "success"
											? "border-green-500/50 bg-green-500/10"
											: "border-red-500/50 bg-red-500/10"
									}
								>
									{result.status === "success" ? (
										<CheckCircle2 className="h-4 w-4 text-green-500" />
									) : (
										<XCircle className="h-4 w-4 text-red-500" />
									)}
									<div>
										<AlertTitle className="text-sm">
											{result.name}: {result.status === "success" ? "Connected" : "Failed"}
										</AlertTitle>
										<AlertDescription className="text-xs">
											{result.message}
											{result.status === "success" && result.tools.length > 0 && (
												<div className="mt-2">
													<p className="font-semibold mb-1">
														Found {result.tools.length} tools:
													</p>
													<ul className="list-disc list-inside space-y-1">
														{result.tools.map((tool, i) => (
															<li key={i} className="text-xs">
																<strong>{tool.name}</strong>: {tool.description}
															</li>
														))}
													</ul>
												</div>
											)}
										</AlertDescription>
									</div>
								</Alert>
							))}
						</div>
					)}
				</div>
			</form>
		</div>
	);
};