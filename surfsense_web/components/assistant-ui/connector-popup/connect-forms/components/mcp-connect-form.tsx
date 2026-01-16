"use client";

import { CheckCircle2, ChevronDown, ChevronUp, Server, XCircle } from "lucide-react";
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
	const [showDetails, setShowDetails] = useState(false);
	const [testResult, setTestResult] = useState<{
		status: "success" | "error";
		message: string;
		tools: MCPToolDefinition[];
		errors?: string[];
	} | null>(null);

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
			setTestResult({
				status: "error",
				message: error || "Invalid configuration",
				tools: [],
			});
			return;
		}

		setIsTesting(true);
		setTestResult(null);
		setJsonError(null);

		const allTools: MCPToolDefinition[] = [];
		const errors: string[] = [];

		for (const config of configs) {
			try {
				const result = await connectorsApiService.testMCPConnection(config);
				if (result.status === "success") {
					allTools.push(...result.tools);
				} else {
					errors.push(`${config.name}: ${result.message}`);
				}
			} catch (error) {
				errors.push(`${config.name}: ${error instanceof Error ? error.message : "Failed to connect"}`);
			}
		}

		if (errors.length === 0) {
			setTestResult({
				status: "success",
				message: `Successfully connected to ${configs.length} server${configs.length !== 1 ? 's' : ''}. Found ${allTools.length} tool${allTools.length !== 1 ? 's' : ''}.`,
				tools: allTools,
			});
		} else if (allTools.length > 0) {
			setTestResult({
				status: "success",
				message: `Partially successful. Connected ${allTools.length} tool${allTools.length !== 1 ? 's' : ''}.`,
				tools: allTools,
				errors,
			});
		} else {
			setTestResult({
				status: "error",
				message: "Failed to connect to all servers",
				tools: [],
				errors,
			});
		}

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
			// Submit all servers as a single connector with server_configs array
			// This creates one connector instead of N connectors (one toast instead of N toasts)
			await onSubmit({
				name: configs.length === 1 ? configs[0].name : "MCPs",
				connector_type: EnumConnectorName.MCP_CONNECTOR,
				config: { server_configs: configs },
				is_indexable: false,
				is_active: true,
				last_indexed_at: null,
				periodic_indexing_enabled: false,
				indexing_frequency_minutes: null,
				next_scheduled_at: null,
			});
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

					{testResult && (
						<Alert
							className={
								testResult.status === "success"
									? "border-green-500/50 bg-green-500/10"
									: "border-red-500/50 bg-red-500/10"
							}
						>
							{testResult.status === "success" ? (
								<CheckCircle2 className="h-4 w-4 text-green-500" />
							) : (
								<XCircle className="h-4 w-4 text-red-500" />
							)}
							<div className="flex-1">
								<div className="flex items-center justify-between">
									<AlertTitle className="text-sm">
										{testResult.status === "success" ? "Connection Successful" : "Connection Failed"}
									</AlertTitle>
									{testResult.tools.length > 0 && (
										<Button
											type="button"
											variant="ghost"
											size="sm"
											className="h-6 px-2"
											onClick={(e) => {
												e.preventDefault();
												e.stopPropagation();
												setShowDetails(!showDetails);
											}}
										>
											{showDetails ? (
												<>
													<ChevronUp className="h-3 w-3 mr-1" />
													Hide Details
												</>
											) : (
												<>
													<ChevronDown className="h-3 w-3 mr-1" />
													Show Details
												</>
											)}
										</Button>
									)}
								</div>
								<AlertDescription className="text-xs mt-1">
									{testResult.message}
									{testResult.errors && testResult.errors.length > 0 && (
										<div className="mt-2 text-red-600">
											<p className="font-semibold">Errors:</p>
											{testResult.errors.map((err, i) => (
												<div key={i}>• {err}</div>
											))}
										</div>
									)}
									{showDetails && testResult.tools.length > 0 && (
										<div className="mt-3 pt-3 border-t border-green-500/20">
											<p className="font-semibold mb-2">
												Available tools:
											</p>
											<ul className="list-disc list-inside text-xs space-y-0.5">
												{testResult.tools.map((tool, i) => (
													<li key={i}>{tool.name}</li>
												))}
											</ul>
										</div>
									)}
								</AlertDescription>
							</div>
						</Alert>
					)}
				</div>
			</form>
		</div>
	);
};