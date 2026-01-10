"use client";

import { Plus, Trash2, Webhook } from "lucide-react";
import type { FC } from "react";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import type { MCPToolConfig } from "@/contracts/types/mcp.types";
import type { ConnectorConfigProps } from "../index";

interface MCPConfigProps extends ConnectorConfigProps {
	onNameChange?: (name: string) => void;
}

const HTTP_METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE"] as const;
const AUTH_TYPES = ["none", "bearer", "api_key", "basic"] as const;

export const MCPConfig: FC<MCPConfigProps> = ({ connector, onConfigChange, onNameChange }) => {
	const [name, setName] = useState<string>(connector.name || "");
	const [tools, setTools] = useState<MCPToolConfig[]>([]);

	// Initialize tools from connector config
	useEffect(() => {
		const configTools = (connector.config?.tools as MCPToolConfig[]) || [];
		setTools(configTools.length > 0 ? configTools : [createEmptyTool()]);
		setName(connector.name || "");
	}, [connector.config, connector.name]);

	const createEmptyTool = (): MCPToolConfig => ({
		name: "",
		description: "",
		endpoint: "",
		method: "GET",
		auth_type: "none",
		auth_config: {},
		parameters: {
			type: "object",
			properties: {},
		},
	});

	const handleNameChange = (value: string) => {
		setName(value);
		if (onNameChange) {
			onNameChange(value);
		}
	};

	const handleToolChange = (index: number, field: keyof MCPToolConfig, value: any) => {
		const newTools = [...tools];
		newTools[index] = { ...newTools[index], [field]: value };
		setTools(newTools);
		updateConfig(newTools);
	};

	const handleAuthConfigChange = (index: number, key: string, value: string) => {
		const newTools = [...tools];
		newTools[index] = {
			...newTools[index],
			auth_config: {
				...newTools[index].auth_config,
				[key]: value,
			},
		};
		setTools(newTools);
		updateConfig(newTools);
	};

	const handleParametersChange = (index: number, value: string) => {
		try {
			const parsed = JSON.parse(value);
			handleToolChange(index, "parameters", parsed);
		} catch {
			// Invalid JSON, don't update
		}
	};

	const addTool = () => {
		const newTools = [...tools, createEmptyTool()];
		setTools(newTools);
		updateConfig(newTools);
	};

	const removeTool = (index: number) => {
		if (tools.length === 1) return; // Keep at least one tool
		const newTools = tools.filter((_, i) => i !== index);
		setTools(newTools);
		updateConfig(newTools);
	};

	const updateConfig = (newTools: MCPToolConfig[]) => {
		if (onConfigChange) {
			onConfigChange({
				tools: newTools,
			});
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
						placeholder="My Custom API Tools"
						className="border-slate-400/20 focus-visible:border-slate-400/40"
					/>
					<p className="text-[10px] sm:text-xs text-muted-foreground">
						A friendly name to identify this MCP connector.
					</p>
				</div>
			</div>

			{/* Tools */}
			<div className="space-y-4">
				<div className="flex items-center justify-between">
					<h3 className="font-medium text-sm sm:text-base flex items-center gap-2">
						<Webhook className="h-4 w-4" />
						API Tools
					</h3>
					<Button
						type="button"
						variant="outline"
						size="sm"
						onClick={addTool}
						className="h-8 text-xs"
					>
						<Plus className="h-3 w-3 mr-1" />
						Add Tool
					</Button>
				</div>

				{tools.map((tool, index) => (
					<div
						key={index}
						className="rounded-xl border border-border bg-slate-400/5 dark:bg-white/5 p-3 sm:p-6 space-y-4"
					>
						{/* Tool Header */}
						<div className="flex items-center justify-between">
							<h4 className="font-medium text-sm">Tool {index + 1}</h4>
							{tools.length > 1 && (
								<Button
									type="button"
									variant="ghost"
									size="sm"
									onClick={() => removeTool(index)}
									className="h-8 text-xs text-destructive hover:text-destructive"
								>
									<Trash2 className="h-3 w-3" />
								</Button>
							)}
						</div>

						{/* Tool Name */}
						<div className="space-y-2">
							<Label className="text-xs sm:text-sm">Tool Name</Label>
							<Input
								value={tool.name}
								onChange={(e) => handleToolChange(index, "name", e.target.value)}
								placeholder="get_weather"
								className="border-slate-400/20 focus-visible:border-slate-400/40 font-mono text-xs"
							/>
							<p className="text-[10px] sm:text-xs text-muted-foreground">
								Unique identifier for this tool (lowercase, use underscores).
							</p>
						</div>

						{/* Description */}
						<div className="space-y-2">
							<Label className="text-xs sm:text-sm">Description</Label>
							<Textarea
								value={tool.description}
								onChange={(e) => handleToolChange(index, "description", e.target.value)}
								placeholder="Get current weather for a location"
								className="border-slate-400/20 focus-visible:border-slate-400/40 min-h-[60px] text-xs"
							/>
							<p className="text-[10px] sm:text-xs text-muted-foreground">
								Describe what this tool does for the AI agent.
							</p>
						</div>

						{/* Endpoint & Method */}
						<div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
							<div className="space-y-2 sm:col-span-2">
								<Label className="text-xs sm:text-sm">API Endpoint</Label>
								<Input
									value={tool.endpoint}
									onChange={(e) => handleToolChange(index, "endpoint", e.target.value)}
									placeholder="https://api.example.com/v1/endpoint"
									className="border-slate-400/20 focus-visible:border-slate-400/40 font-mono text-xs"
								/>
							</div>
							<div className="space-y-2">
								<Label className="text-xs sm:text-sm">Method</Label>
								<Select
									value={tool.method}
									onValueChange={(value) => handleToolChange(index, "method", value)}
								>
									<SelectTrigger className="border-slate-400/20 text-xs">
										<SelectValue />
									</SelectTrigger>
									<SelectContent>
										{HTTP_METHODS.map((method) => (
											<SelectItem key={method} value={method} className="text-xs">
												{method}
											</SelectItem>
										))}
									</SelectContent>
								</Select>
							</div>
						</div>

						{/* Authentication */}
						<div className="space-y-3">
							<div className="space-y-2">
								<Label className="text-xs sm:text-sm">Authentication Type</Label>
								<Select
									value={tool.auth_type}
									onValueChange={(value) => handleToolChange(index, "auth_type", value)}
								>
									<SelectTrigger className="border-slate-400/20 text-xs">
										<SelectValue />
									</SelectTrigger>
									<SelectContent>
										{AUTH_TYPES.map((type) => (
											<SelectItem key={type} value={type} className="text-xs">
												{type === "none" ? "None" : type === "bearer" ? "Bearer Token" : type === "api_key" ? "API Key" : "Basic Auth"}
											</SelectItem>
										))}
									</SelectContent>
								</Select>
							</div>

							{/* Auth Config Fields */}
							{tool.auth_type === "bearer" && (
								<div className="space-y-2">
									<Label className="text-xs sm:text-sm">Bearer Token</Label>
									<Input
										type="password"
										value={tool.auth_config.token || ""}
										onChange={(e) => handleAuthConfigChange(index, "token", e.target.value)}
										placeholder="your_bearer_token"
										className="border-slate-400/20 focus-visible:border-slate-400/40 font-mono text-xs"
									/>
								</div>
							)}

							{tool.auth_type === "api_key" && (
								<>
									<div className="space-y-2">
										<Label className="text-xs sm:text-sm">API Key</Label>
										<Input
											type="password"
											value={tool.auth_config.api_key || ""}
											onChange={(e) => handleAuthConfigChange(index, "api_key", e.target.value)}
											placeholder="your_api_key"
											className="border-slate-400/20 focus-visible:border-slate-400/40 font-mono text-xs"
										/>
									</div>
									<div className="space-y-2">
										<Label className="text-xs sm:text-sm">Header Name</Label>
										<Input
											value={tool.auth_config.api_key_header || "X-API-Key"}
											onChange={(e) => handleAuthConfigChange(index, "api_key_header", e.target.value)}
											placeholder="X-API-Key"
											className="border-slate-400/20 focus-visible:border-slate-400/40 font-mono text-xs"
										/>
									</div>
								</>
							)}

							{tool.auth_type === "basic" && (
								<>
									<div className="space-y-2">
										<Label className="text-xs sm:text-sm">Username</Label>
										<Input
											value={tool.auth_config.username || ""}
											onChange={(e) => handleAuthConfigChange(index, "username", e.target.value)}
											placeholder="username"
											className="border-slate-400/20 focus-visible:border-slate-400/40 font-mono text-xs"
										/>
									</div>
									<div className="space-y-2">
										<Label className="text-xs sm:text-sm">Password</Label>
										<Input
											type="password"
											value={tool.auth_config.password || ""}
											onChange={(e) => handleAuthConfigChange(index, "password", e.target.value)}
											placeholder="password"
											className="border-slate-400/20 focus-visible:border-slate-400/40 font-mono text-xs"
										/>
									</div>
								</>
							)}
						</div>

						{/* Parameters Schema */}
						<div className="space-y-2">
							<Label className="text-xs sm:text-sm">Parameters (JSON Schema)</Label>
							<Textarea
								value={JSON.stringify(tool.parameters, null, 2)}
								onChange={(e) => handleParametersChange(index, e.target.value)}
								placeholder={`{\n  "type": "object",\n  "properties": {\n    "location": {\n      "type": "string",\n      "description": "City name"\n    }\n  },\n  "required": ["location"]\n}`}
								className="border-slate-400/20 focus-visible:border-slate-400/40 font-mono text-xs min-h-[120px]"
							/>
							<p className="text-[10px] sm:text-xs text-muted-foreground">
								Define the parameters this tool accepts using JSON Schema format.
							</p>
						</div>
					</div>
				))}
			</div>
		</div>
	);
};
