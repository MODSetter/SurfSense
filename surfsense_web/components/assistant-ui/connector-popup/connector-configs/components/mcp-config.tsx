"use client";

import { CheckCircle2, ChevronDown, ChevronUp, Server, XCircle } from "lucide-react";
import type { FC } from "react";
import { useEffect, useState } from "react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { EnumConnectorName } from "@/contracts/enums/connector";
import type { MCPServerConfig, MCPToolDefinition } from "@/contracts/types/mcp.types";
import type { ConnectorConfigProps } from "../index";
import {
	parseMCPConfig,
	testMCPConnection,
	type MCPConnectionTestResult,
} from "../../utils/mcp-config-validator";

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

	// Initialize form from connector config (only on mount)
	useEffect(() => {
		if (connector.name) {
			setName(connector.name);
		}
		
		const serverConfig = connector.config?.server_config as MCPServerConfig | undefined;
		if (serverConfig) {
			// Convert server config to JSON string for editing (name is in separate field)
			const configObj = {
				command: serverConfig.command || "",
				args: serverConfig.args || [],
				env: serverConfig.env || {},
				transport: serverConfig.transport || "stdio",
			};
			setConfigJson(JSON.stringify(configObj, null, 2));
		}
	}, []);

	// Validate that this is an MCP connector (after hooks)
	if (connector.connector_type !== EnumConnectorName.MCP_CONNECTOR) {
		console.error(
			"MCPConfig received non-MCP connector:",
			connector.connector_type
		);
		return (
			<Alert className="border-red-500/50 bg-red-500/10">
				<XCircle className="h-4 w-4 text-red-600" />
				<AlertTitle>Invalid Connector Type</AlertTitle>
				<AlertDescription>
					This component can only be used with MCP connectors.
				</AlertDescription>
			</Alert>
		);
	}

	const handleNameChange = (value: string) => {
		setName(value);
		if (onNameChange) {
			onNameChange(value);
		}
	};

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
		if (jsonError) {
			setJsonError(null);
		}
		
		// Use shared utility for validation and parsing (with caching)
		const result = parseMCPConfig(value);
		
		if (result.config && onConfigChange) {
			// Valid config - update parent immediately
			onConfigChange({ server_config: result.config });
		}
		// Ignore errors while typing - only show errors when user tests or saves
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

		// Update parent with the config
		if (onConfigChange) {
			onConfigChange({ server_config: serverConfig });
		}

		setIsTesting(true);
		setTestResult(null);

		const result = await testMCPConnection(serverConfig);
		setTestResult(result);
		setIsTesting(false);
	};

	return (
		<div className="space-y-6">
			{/* Server Name */}
			<div className="rounded-xl border border-border bg-slate-400/5 dark:bg-white/5 p-3 sm:p-6 space-y-3 sm:space-y-4">
				<div className="space-y-2">
					<Label htmlFor="name" className="text-xs sm:text-sm">Server Name</Label>
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
							rows={16}
							className={`font-mono text-xs ${jsonError ? "border-red-500" : ""}`}
						/>
						{jsonError && (
							<p className="text-xs text-red-500">JSON Error: {jsonError}</p>
						)}
						<p className="text-[10px] sm:text-xs text-muted-foreground">
							Edit your MCP server configuration. Must include: name, command, args (optional), env (optional), transport (optional).
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
							{isTesting ? "Testing Connection..." : "Test Connection"}
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
									{showDetails && testResult.tools.length > 0 && (
										<div className="mt-3 pt-3 border-t border-green-500/20">
											<p className="font-semibold mb-2">
												Available tools:
											</p>
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
