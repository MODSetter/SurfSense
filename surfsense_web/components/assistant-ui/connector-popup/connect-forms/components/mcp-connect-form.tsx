"use client";

import { CheckCircle2, ChevronDown, ChevronUp, Server, XCircle } from "lucide-react";
import { type FC, useRef, useState } from "react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { EnumConnectorName } from "@/contracts/enums/connector";
import {
	extractServerName,
	type MCPConnectionTestResult,
	parseMCPConfig,
	testMCPConnection,
} from "../../utils/mcp-config-validator";
import type { ConnectFormProps } from "..";

export const MCPConnectForm: FC<ConnectFormProps> = ({ onSubmit, isSubmitting }) => {
	const isSubmittingRef = useRef(false);
	const [configJson, setConfigJson] = useState("");
	const [jsonError, setJsonError] = useState<string | null>(null);
	const [isTesting, setIsTesting] = useState(false);
	const [showDetails, setShowDetails] = useState(false);
	const [testResult, setTestResult] = useState<MCPConnectionTestResult | null>(null);

	// Default config for stdio transport (local process)
	const DEFAULT_STDIO_CONFIG = JSON.stringify(
		{
			name: "My MCP Server",
			command: "npx",
			args: ["-y", "@modelcontextprotocol/server-filesystem", "/path/to/directory"],
			env: {
				API_KEY: "your_api_key_here",
			},
			transport: "stdio",
		},
		null,
		2
	);

	// Default config for HTTP transport (remote server)
	const DEFAULT_HTTP_CONFIG = JSON.stringify(
		{
			name: "My Remote MCP Server",
			url: "https://your-mcp-server.com/mcp",
			headers: {
				API_KEY: "your_api_key_here",
			},
			transport: "streamable-http",
		},
		null,
		2
	);

	const DEFAULT_CONFIG = DEFAULT_STDIO_CONFIG;

	const parseConfig = () => {
		const result = parseMCPConfig(configJson);
		if (result.error) {
			setJsonError(result.error);
		} else {
			setJsonError(null);
		}
		return result.config;
	};

	const handleConfigChange = (value: string) => {
		setConfigJson(value);

		// Clear previous error
		if (jsonError) {
			setJsonError(null);
		}

		// Validate immediately to show errors as user types (with debouncing via parseMCPConfig cache)
		if (value.trim()) {
			const result = parseMCPConfig(value);
			if (result.error) {
				setJsonError(result.error);
			}
		}
	};

	const handleTestConnection = async () => {
		const serverConfig = parseConfig();
		if (!serverConfig) {
			setTestResult({
				status: "error",
				message: jsonError || "Invalid configuration",
				tools: [],
			});
			return;
		}

		setIsTesting(true);
		setTestResult(null);

		const result = await testMCPConnection(serverConfig);
		setTestResult(result);
		setIsTesting(false);
	};

	const handleSubmit = async (e: React.FormEvent) => {
		e.preventDefault();

		// Prevent multiple submissions
		if (isSubmittingRef.current || isSubmitting) {
			return;
		}

		const serverConfig = parseConfig();
		if (!serverConfig) {
			return;
		}

		// Extract server name from config if provided
		const serverName = extractServerName(configJson);

		isSubmittingRef.current = true;
		try {
			await onSubmit({
				name: serverName,
				connector_type: EnumConnectorName.MCP_CONNECTOR,
				config: { server_config: serverConfig },
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
			<Alert className="bg-slate-400/5 dark:bg-white/5 border-slate-400/20 p-2 sm:p-3 [&>svg]:top-2 sm:[&>svg]:top-3">
				<Server className="h-4 w-4 shrink-0" />
				<AlertDescription className="text-[10px] sm:text-xs">
					Connect to an MCP (Model Context Protocol) server. Each MCP server is added as a separate
					connector.
				</AlertDescription>
			</Alert>

			<form id="mcp-connect-form" onSubmit={handleSubmit} className="space-y-6">
				<div className="rounded-xl border border-border bg-slate-400/5 dark:bg-white/5 p-4 sm:p-6 space-y-4">
					<div className="space-y-2">
						<div className="flex items-center justify-between flex-wrap gap-2">
							<Label htmlFor="config">MCP Server Configuration (JSON)</Label>
							{!configJson && (
								<div className="flex gap-1">
									<Button
										type="button"
										variant="ghost"
										size="sm"
										className="h-6 px-2 text-xs text-muted-foreground hover:text-foreground"
										onClick={() => handleConfigChange(DEFAULT_STDIO_CONFIG)}
									>
										Local Example
									</Button>
									<Button
										type="button"
										variant="ghost"
										size="sm"
										className="h-6 px-2 text-xs text-muted-foreground hover:text-foreground"
										onClick={() => handleConfigChange(DEFAULT_HTTP_CONFIG)}
									>
										Remote Example
									</Button>
								</div>
							)}
						</div>
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
							placeholder={DEFAULT_CONFIG}
							rows={16}
							className={`font-mono text-xs ${jsonError ? "border-red-500" : ""}`}
						/>
						{jsonError && <p className="text-xs text-red-500">JSON Error: {jsonError}</p>}
						<p className="text-[10px] sm:text-xs text-muted-foreground">
							Paste a single MCP server configuration. Must include: name, command, args (optional),
							env (optional), transport (optional).
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
								<div className="flex items-center justify-between">
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
								<AlertDescription className="text-[10px] sm:text-xs mt-1">
									{testResult.message}
									{showDetails && testResult.tools.length > 0 && (
										<div className="mt-3 pt-3 border-t border-green-500/20">
											<p className="font-semibold mb-2">Available tools:</p>
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
