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
}

export const MCPConfig: FC<MCPConfigProps> = ({ connector, onConfigChange, onNameChange }) => {
	const [name, setName] = useState<string>(connector.name || "");
	const [configJson, setConfigJson] = useState("");
	const [jsonError, setJsonError] = useState<string | null>(null);
	const [isTesting, setIsTesting] = useState(false);
	const [testResult, setTestResult] = useState<{
		status: "success" | "error";
		message: string;
		tools: MCPToolDefinition[];
	} | null>(null);

	// Initialize from connector config
	useEffect(() => {
		const serverConfig = (connector.config?.server_config as MCPServerConfig) || {
			command: "",
			args: [],
			env: {},
			transport: "stdio",
		};
		setConfigJson(JSON.stringify(serverConfig, null, 2));
		setName(connector.name || "");
	}, [connector.config, connector.name]);


	const handleNameChange = (value: string) => {
		setName(value);
		if (onNameChange) {
			onNameChange(value);
		}
	};

	const parseConfig = (): MCPServerConfig | null => {
		try {
			const parsed = JSON.parse(configJson);
			setJsonError(null);
			return {
				command: parsed.command || "",
				args: parsed.args || [],
				env: parsed.env || {},
				transport: parsed.transport || "stdio",
			};
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

		// Try to parse and update config
		try {
			const parsed = JSON.parse(value);
			if (onConfigChange) {
				onConfigChange({
					server_config: {
						command: parsed.command || "",
						args: parsed.args || [],
						env: parsed.env || {},
						transport: parsed.transport || "stdio",
					},
				});
			}
		} catch {
			// Invalid JSON, don't update config yet
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

		if (!serverConfig.command.trim()) {
			setTestResult({
				status: "error",
				message: "Command is required in configuration",
				tools: [],
			});
			return;
		}

		setIsTesting(true);
		setTestResult(null);

		try {
			const result = await connectorsApiService.testMCPConnection(serverConfig);
			setTestResult(result);
		} catch (error) {
			setTestResult({
				status: "error",
				message: error instanceof Error ? error.message : "Failed to connect to MCP server",
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
						<Label className="text-xs sm:text-sm">
							Server Configuration (JSON)
						</Label>
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
							Edit your MCP server configuration. Required fields: command, args, env, transport.
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
