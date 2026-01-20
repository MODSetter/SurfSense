"use client";

import { CheckCircle2, ChevronDown, ChevronUp, Server, XCircle } from "lucide-react";
import type { FC } from "react";
import { useCallback, useEffect, useRef, useState } from "react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { EnumConnectorName } from "@/contracts/enums/connector";
import type { MCPServerConfig } from "@/contracts/types/mcp.types";
import {
	type MCPConnectionTestResult,
	parseMCPConfig,
	testMCPConnection,
} from "../../utils/mcp-config-validator";
import type { ConnectorConfigProps } from "../index";

interface MCPConfigProps extends ConnectorConfigProps {
	onNameChange?: (name: string) => void;
}

export const MCPConfig: FC<MCPConfigProps> = ({ connector, onConfigChange, onNameChange }) => {
	const [name, setName] = useState<string>("");
	const [configJson, setConfigJson] = useState("");
	const [jsonError, setJsonError] = useState<string | null>(null);
	const [isTesting, setIsTesting] = useState(false);
	const [showDetails, setShowDetails] = useState(false);
	const [testResult, setTestResult] = useState<MCPConnectionTestResult | null>(null);
	const initializedRef = useRef(false);

	// Check if this is a valid MCP connector
	const isValidConnector = connector.connector_type === EnumConnectorName.MCP_CONNECTOR;

	// Initialize form from connector config (only on mount)
	// We intentionally only read connector.name and connector.config on initial mount
	// to preserve user edits during the session
	useEffect(() => {
		if (!isValidConnector || initializedRef.current) return;
		initializedRef.current = true;

		if (connector.name) {
			setName(connector.name);
		}

		const serverConfig = connector.config?.server_config as MCPServerConfig | undefined;
		if (serverConfig) {
			const transport = serverConfig.transport || "stdio";

			// Build config object based on transport type
			let configObj: Record<string, unknown>;

			if (transport === "streamable-http" || transport === "http" || transport === "sse") {
				// HTTP transport - use url and headers
				configObj = {
					url: (serverConfig as any).url || "",
					headers: (serverConfig as any).headers || {},
					transport: transport,
				};
			} else {
				// stdio transport (default) - use command, args, env
				configObj = {
					command: (serverConfig as any).command || "",
					args: (serverConfig as any).args || [],
					env: (serverConfig as any).env || {},
					transport: transport,
				};
			}

			setConfigJson(JSON.stringify(configObj, null, 2));
		}
	}, [isValidConnector, connector.name, connector.config?.server_config]);

	const handleNameChange = useCallback(
		(value: string) => {
			setName(value);
			if (onNameChange) {
				onNameChange(value);
			}
		},
		[onNameChange]
	);

	const parseConfig = useCallback(() => {
		const result = parseMCPConfig(configJson);
		if (result.error) {
			setJsonError(result.error);
		} else {
			setJsonError(null);
		}
		return result.config;
	}, [configJson]);

	const handleConfigChange = useCallback(
		(value: string) => {
			setConfigJson(value);
			setJsonError(null);

			// Use shared utility for validation and parsing (with caching)
			const result = parseMCPConfig(value);

			if (result.config && onConfigChange) {
				// Valid config - update parent immediately
				onConfigChange({ server_config: result.config });
			}
			// Ignore errors while typing - only show errors when user tests or saves
		},
		[onConfigChange]
	);

	const handleTestConnection = useCallback(async () => {
		const serverConfig = parseConfig();
		if (!serverConfig) {
			setTestResult({
				status: "error",
				message: jsonError || "Invalid configuration",
				tools: [],
			});
			return;
		}

		// Update parent with the config
		if (onConfigChange) {
			onConfigChange({ server_config: serverConfig });
		}

		setIsTesting(true);
		setTestResult(null);

		const result = await testMCPConnection(serverConfig);
		setTestResult(result);
		setIsTesting(false);
	}, [parseConfig, jsonError, onConfigChange]);

	// Validate that this is an MCP connector - must be after all hooks
	if (!isValidConnector) {
		console.error("MCPConfig received non-MCP connector:", connector.connector_type);
		return (
			<Alert className="border-red-500/50 bg-red-500/10">
				<XCircle className="h-4 w-4 text-red-600" />
				<AlertTitle>Invalid Connector Type</AlertTitle>
				<AlertDescription>This component can only be used with MCP connectors.</AlertDescription>
			</Alert>
		);
	}

	return (
		<div className="space-y-6">
			{/* Server Name */}
			<div className="rounded-xl border border-border bg-slate-400/5 dark:bg-white/5 p-3 sm:p-6 space-y-3 sm:space-y-4">
				<div className="space-y-2">
					<Label htmlFor="name" className="text-xs sm:text-sm">
						Server Name
					</Label>
					<Input
						id="name"
						value={name}
						onChange={(e) => handleNameChange(e.target.value)}
						placeholder="e.g., Filesystem Server"
						className="border-slate-400/20 focus-visible:border-slate-400/40"
						required
					/>
					<p className="text-[10px] sm:text-xs text-muted-foreground">
						A friendly name to identify this connector.
					</p>
				</div>
			</div>

			{/* Server Configuration */}
			<div className="space-y-4">
				<h3 className="font-medium text-sm sm:text-base flex items-center gap-2">
					<Server className="h-4 w-4" />
					Server Configuration
				</h3>

				<div className="rounded-xl border border-border bg-slate-400/5 dark:bg-white/5 p-3 sm:p-6 space-y-4">
					<div className="space-y-2">
						<Label htmlFor="config">MCP Server Configuration (JSON)</Label>
						<Textarea
							id="config"
							value={configJson}
							onChange={(e) => handleConfigChange(e.target.value)}
							onKeyDown={(e) => {
								if (e.key === "Tab") {
									e.preventDefault();
									const target = e.target as HTMLTextAreaElement;
									const start = target.selectionStart;
									const end = target.selectionEnd;
									const indent = "  "; // 2 spaces for JSON
									const newValue =
										configJson.substring(0, start) + indent + configJson.substring(end);
									handleConfigChange(newValue);
									// Set cursor position after the inserted tab
									requestAnimationFrame(() => {
										target.selectionStart = target.selectionEnd = start + indent.length;
									});
								}
							}}
							rows={16}
							className={`font-mono text-xs ${jsonError ? "border-red-500" : ""}`}
						/>
						{jsonError && <p className="text-xs text-red-500">JSON Error: {jsonError}</p>}
						<p className="text-[10px] sm:text-xs text-muted-foreground">
							<strong>Local (stdio):</strong> command, args, env, transport: "stdio"
							<br />
							<strong>Remote (HTTP):</strong> url, headers, transport: "streamable-http"
						</p>
					</div>

					{/* Test Connection */}
					<div className="pt-4">
						<Button
							type="button"
							onClick={handleTestConnection}
							disabled={isTesting}
							variant="secondary"
							className="w-full h-8 text-[13px] px-3 rounded-lg font-medium bg-white text-slate-700 hover:bg-slate-50 border-0 shadow-xs dark:bg-secondary dark:text-secondary-foreground dark:hover:bg-secondary/80"
						>
							{isTesting ? "Testing Connection" : "Test Connection"}
						</Button>
					</div>

					{/* Test Result */}
					{testResult && (
						<Alert
							className={
								testResult.status === "success"
									? "border-green-500/50 bg-green-500/10"
									: "border-red-500/50 bg-red-500/10"
							}
						>
							{testResult.status === "success" ? (
								<CheckCircle2 className="h-4 w-4 text-green-600" />
							) : (
								<XCircle className="h-4 w-4 text-red-600" />
							)}
							<div className="flex-1">
								<div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 sm:gap-0">
									<AlertTitle className="text-sm">
										{testResult.status === "success"
											? "Connection Successful"
											: "Connection Failed"}
									</AlertTitle>
									{testResult.tools.length > 0 && (
										<Button
											type="button"
											variant="ghost"
											size="sm"
											className="h-6 px-2 self-start sm:self-auto text-xs"
											onClick={(e) => {
												e.preventDefault();
												e.stopPropagation();
												setShowDetails(!showDetails);
											}}
										>
											{showDetails ? (
												<>
													<ChevronUp className="h-3 w-3 mr-1" />
													<span className="hidden sm:inline">Hide Details</span>
													<span className="sm:hidden">Hide</span>
												</>
											) : (
												<>
													<ChevronDown className="h-3 w-3 mr-1" />
													<span className="hidden sm:inline">Show Details</span>
													<span className="sm:hidden">Show</span>
												</>
											)}
										</Button>
									)}
								</div>
								<AlertDescription className="text-xs mt-1">
									{testResult.message}
									{showDetails && testResult.tools.length > 0 && (
										<div className="mt-3 pt-3 border-t border-green-500/20">
											<p className="font-semibold mb-2">Available tools:</p>
											<ul className="list-disc list-inside text-xs space-y-0.5">
												{testResult.tools.map((tool) => (
													<li key={tool.name}>{tool.name}</li>
												))}
											</ul>
										</div>
									)}
								</AlertDescription>
							</div>
						</Alert>
					)}
				</div>
			</div>
		</div>
	);
};
