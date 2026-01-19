"use client";

import { Server } from "lucide-react";
import { type FC, useRef, useState } from "react";
import { toast } from "sonner";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { EnumConnectorName } from "@/contracts/enums/connector";
import type { ConnectFormProps } from "..";
import {
	extractServerName,
	parseMCPConfig,
	testMCPConnection,
} from "../../utils/mcp-config-validator";

export const MCPConnectForm: FC<ConnectFormProps> = ({ onSubmit, isSubmitting }) => {
	const isSubmittingRef = useRef(false);
	const [configJson, setConfigJson] = useState("");
	const [jsonError, setJsonError] = useState<string | null>(null);
	const [isTesting, setIsTesting] = useState(false);

	const DEFAULT_CONFIG = JSON.stringify(
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
			toast.error("Invalid configuration", {
				description: jsonError || "Please check your MCP server configuration JSON.",
			});
			return;
		}

		setIsTesting(true);

		const result = await testMCPConnection(serverConfig);
		
		if (result.status === "success") {
			toast.success("Connection Successful", {
				description: result.message,
			});
		} else {
			toast.error("Connection Failed", {
				description: result.message,
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
			<div className="flex items-center gap-2">
				<Server className="h-4 w-4 shrink-0" />
				<AlertDescription className="text-[10px] sm:text-xs">
					Connect to an MCP (Model Context Protocol) server. Each MCP server is added as a separate connector.
				</AlertDescription>
			</div>
		</Alert>

			<form id="mcp-connect-form" onSubmit={handleSubmit} className="space-y-6">
				<div className="rounded-xl border border-border bg-slate-400/5 dark:bg-white/5 p-4 sm:p-6 space-y-4">
					<div className="space-y-2">
						<Label htmlFor="config">MCP Server Configuration (JSON)</Label>
						<Textarea
							id="config"
							value={configJson}
							onChange={(e) => handleConfigChange(e.target.value)}
							placeholder={DEFAULT_CONFIG}
							rows={16}
							className={`font-mono text-xs ${jsonError ? "border-red-500" : ""}`}
						/>
						{jsonError && (
							<p className="text-xs text-red-500">{jsonError}</p>
						)}
						<p className="text-[10px] sm:text-xs text-muted-foreground">
							Paste a single MCP server configuration. Must include: name, command, args (optional), env (optional), transport (optional).
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
							{isTesting ? "Testing Connection" : "Test Connection"}
						</Button>
					</div>
				</div>
			</form>
		</div>
	);
};