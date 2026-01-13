"use client";

import { CheckCircle2, Server, XCircle } from "lucide-react";
import type { FC } from "react";
import { useEffect, useState } from "react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import type { MCPServerConfig, MCPToolDefinition } from "@/contracts/types/mcp.types";
import { connectorsApiService } from "@/lib/apis/connectors-api.service";
import type { ConnectorConfigProps } from "../index";

interface MCPConfigProps extends ConnectorConfigProps {
	onNameChange?: (name: string) => void;
	searchSpaceId?: string;
}

export const MCPConfig: FC<MCPConfigProps> = ({ connector, onConfigChange, onNameChange, searchSpaceId }) => {
	const [name, setName] = useState<string>("MCPs");
	const [configJson, setConfigJson] = useState("");
	const [jsonError, setJsonError] = useState<string | null>(null);
	const [isTesting, setIsTesting] = useState(false);
	const [testResult, setTestResult] = useState<{
		status: "success" | "error";
		message: string;
		tools: MCPToolDefinition[];
	} | null>(null);
	const [allMCPConnectors, setAllMCPConnectors] = useState<any[]>([]);

	// Load all MCP connectors for this search space
	useEffect(() => {
		const loadAllMCPConnectors = async () => {
			if (!searchSpaceId) return;
			
			try {
				const connectors = await connectorsApiService.getConnectors({
					queryParams: { search_space_id: parseInt(searchSpaceId, 10) }
				});
				const mcpConnectors = connectors.filter((c: any) => c.connector_type === "MCP_CONNECTOR");
				setAllMCPConnectors(mcpConnectors);
				
				// Collect all server configs from all MCP connectors
				const allServerConfigs: MCPServerConfig[] = [];
				for (const mcpConn of mcpConnectors) {
					const serverConfigs = mcpConn.config?.server_configs as MCPServerConfig[] | undefined;
					if (serverConfigs && Array.isArray(serverConfigs)) {
						allServerConfigs.push(...serverConfigs);
					} else {
						// Fallback to single server_config
						const serverConfig = mcpConn.config?.server_config as MCPServerConfig | undefined;
						if (serverConfig) {
							allServerConfigs.push(serverConfig);
						}
					}
				}
				
				if (allServerConfigs.length > 0) {
					setConfigJson(JSON.stringify(allServerConfigs, null, 2));
				} else {
					setConfigJson(JSON.stringify([{
						command: "",
						args: [],
						env: {},
						transport: "stdio",
					}], null, 2));
				}
			} catch (error) {
				console.error("Failed to load MCP connectors:", error);
			}
		};
		
		loadAllMCPConnectors();
	}, [searchSpaceId]);


	const handleNameChange = (value: string) => {
		setName(value);
		if (onNameChange) {
			onNameChange(value);
		}
	};

	const parseConfig = (): MCPServerConfig[] | null => {
		try {
			const parsed = JSON.parse(configJson);
			
			// Handle both single object and array
			const configs = Array.isArray(parsed) ? parsed : [parsed];
			
			// Validate each config
			const validConfigs: MCPServerConfig[] = [];
			for (let i = 0; i < configs.length; i++) {
				const cfg = configs[i];
				if (!cfg.command || typeof cfg.command !== "string") {
					setJsonError(`Config ${i + 1}: 'command' field is required and must be a string`);
					return null;
				}
				validConfigs.push({
					command: cfg.command,
					args: cfg.args || [],
					env: cfg.env || {},
					transport: cfg.transport || "stdio",
				});
			}
			
			setJsonError(null);
			return validConfigs;
		} catch (error) {
			setJsonError(error instanceof Error ? error.message : "Invalid JSON");
			return null;
		}
	};

	const handleConfigChange = (value: string) => {
		setConfigJson(value);
		// Clear error when user starts typing
		if (jsonError) {
			setJsonError(null);
		}
	};

	const handleTestConnection = async () => {
		const serverConfigs = parseConfig();
		if (!serverConfigs || serverConfigs.length === 0) {
			setTestResult({
				status: "error",
				message: jsonError || "Invalid configuration",
				tools: [],
			});
			return;
		}

		// Update parent with the config array
		if (onConfigChange) {
			onConfigChange({ server_configs: serverConfigs });
		}

		setIsTesting(true);
		setTestResult(null);

		try {
			// Test all servers and collect results
			const allTools: MCPToolDefinition[] = [];
			const errors: string[] = [];
			
			for (const serverConfig of serverConfigs) {
				try {
					const result = await connectorsApiService.testMCPConnection(serverConfig);
					if (result.status === "success") {
						allTools.push(...result.tools);
					} else {
						errors.push(`${serverConfig.command}: ${result.message}`);
					}
				} catch (error) {
					errors.push(`${serverConfig.command}: ${error instanceof Error ? error.message : "Failed to connect"}`);
				}
			}
			
			if (errors.length === 0) {
				setTestResult({
					status: "success",
					message: `Successfully connected to ${serverConfigs.length} server(s)`,
					tools: allTools,
				});
			} else if (allTools.length > 0) {
				setTestResult({
					status: "success",
					message: `Partially successful. Errors: ${errors.join("; ")}`,
					tools: allTools,
				});
			} else {
				setTestResult({
					status: "error",
					message: errors.join("; "),
					tools: [],
				});
			}
		} catch (error) {
			setTestResult({
				status: "error",
				message: error instanceof Error ? error.message : "Failed to connect to MCP servers",
				tools: [],
			});
		} finally {
			setIsTesting(false);
		}
	};

	return (
		<div className="space-y-6">
			{/* Connector Name */}
			<div className="rounded-xl border border-border bg-slate-400/5 dark:bg-white/5 p-3 sm:p-6 space-y-3 sm:space-y-4">
				<div className="space-y-2">
					<Label className="text-xs sm:text-sm">Connector Name</Label>
					<Input
						value={name}
						onChange={(e) => handleNameChange(e.target.value)}
						placeholder="My MCP Server"
						className="border-slate-400/20 focus-visible:border-slate-400/40"
					/>
					<p className="text-[10px] sm:text-xs text-muted-foreground">
						A friendly name to identify this MCP server.
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
						<Textarea
							value={configJson}
							onChange={(e) => handleConfigChange(e.target.value)}
							rows={12}
							className={`font-mono text-xs border-slate-400/20 focus-visible:border-slate-400/40 ${
								jsonError ? "border-red-500" : ""
							}`}
						/>
						{jsonError && (
							<p className="text-xs text-red-500">
								JSON Error: {jsonError}
							</p>
						)}
						<p className="text-[10px] sm:text-xs text-muted-foreground">
							Edit your MCP server configurations (array format). Each server requires: command, args, env, transport.
						</p>
					</div>

					{/* Test Connection */}
					<div className="pt-4">
						<Button
							type="button"
							onClick={handleTestConnection}
							disabled={isTesting}
							variant="outline"
							className="w-full"
						>
							{isTesting ? "Testing..." : "Test Connection"}
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
								<CheckCircle2 className="h-4 w-4 text-green-500" />
							) : (
								<XCircle className="h-4 w-4 text-red-500" />
							)}
							<div>
								<AlertTitle className="text-sm">
									{testResult.status === "success" ? "Connection Successful" : "Connection Failed"}
								</AlertTitle>
								<AlertDescription className="text-xs">
									{testResult.message}
									{testResult.status === "success" && testResult.tools.length > 0 && (
										<div className="mt-2">
											<p className="font-semibold mb-1">
												Found {testResult.tools.length} tools:
											</p>
											<ul className="list-disc list-inside space-y-1">
												{testResult.tools.map((tool, i) => (
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
					)}
				</div>
			</div>
		</div>
	);
};
