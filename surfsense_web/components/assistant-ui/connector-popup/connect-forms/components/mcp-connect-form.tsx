"use client";

import { Plus, Trash2, Webhook } from "lucide-react";
import { type FC, useCallback, useRef, useState } from "react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
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
import { EnumConnectorName } from "@/contracts/enums/connector";
import type { MCPToolConfig } from "@/contracts/types/mcp.types";
import type { ConnectFormProps } from "..";

const HTTP_METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE"] as const;
const AUTH_TYPES = ["none", "bearer", "api_key", "basic"] as const;

export const MCPConnectForm: FC<ConnectFormProps> = ({ onSubmit, isSubmitting }) => {
	const isSubmittingRef = useRef(false);
	const [name, setName] = useState("Custom API Tools");
	const [tools, setTools] = useState<MCPToolConfig[]>([
		{
			name: "",
			description: "",
			endpoint: "",
			method: "GET",
			auth_type: "none",
			auth_config: {},
			parameters: { type: "object", properties: {} },
			verify_ssl: true,
		},
	]);

	const addTool = () => {
		setTools([
			...tools,
			{
				name: "",
				description: "",
				endpoint: "",
				method: "GET",
				auth_type: "none",
				auth_config: {},
				parameters: { type: "object", properties: {} },
				verify_ssl: true,
			},
		]);
	};

	const removeTool = (index: number) => {
		setTools(tools.filter((_, i) => i !== index));
	};

	const updateTool = (index: number, field: keyof MCPToolConfig, value: unknown) => {
		const newTools = [...tools];
		newTools[index] = { ...newTools[index], [field]: value };
		setTools(newTools);
	};

	const updateAuthConfig = (index: number, key: string, value: string) => {
		const newTools = [...tools];
		newTools[index] = {
			...newTools[index],
			auth_config: { ...newTools[index].auth_config, [key]: value },
		};
		setTools(newTools);
	};

	const handleSubmit = async (e: React.FormEvent) => {
		e.preventDefault();

		// Prevent multiple submissions
		if (isSubmittingRef.current || isSubmitting) {
			return;
		}

		// Basic validation
		const hasValidTool = tools.some(
			(tool) =>
				tool.name.trim() && tool.description.trim() && tool.endpoint.trim() && tool.method
		);

		if (!hasValidTool) {
			alert("Please add at least one complete tool configuration");
			return;
		}

		isSubmittingRef.current = true;
		try {
			await onSubmit({
				name,
				connector_type: EnumConnectorName.MCP_CONNECTOR,
				config: { tools },
				is_indexable: false,
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
				<Webhook className="h-4 w-4 shrink-0 ml-1" />
				<div className="-ml-1">
					<AlertTitle className="text-xs sm:text-sm">Custom API Tools</AlertTitle>
					<AlertDescription className="text-[10px] sm:text-xs !pl-0">
						Add your own API endpoints as tools that the AI can call during conversations.
						Supports various authentication methods and HTTP methods.
					</AlertDescription>
				</div>
			</Alert>

			<form id="mcp-connect-form" onSubmit={handleSubmit} className="space-y-6">
				<div className="rounded-xl border border-border bg-slate-400/5 dark:bg-white/5 p-4 sm:p-6 space-y-4">
					<div className="space-y-2">
						<Label htmlFor="connector-name">Connector Name</Label>
						<Input
							id="connector-name"
							value={name}
							onChange={(e) => setName(e.target.value)}
							placeholder="My Custom API Tools"
							required
						/>
					</div>

					<div className="space-y-4">
						<div className="flex items-center justify-between">
							<Label className="text-base">Tools</Label>
							<Button type="button" onClick={addTool} variant="outline" size="sm">
								<Plus className="h-4 w-4 mr-1" />
								Add Tool
							</Button>
						</div>

						{tools.map((tool, index) => (
							<div
								key={index}
								className="rounded-lg border border-border bg-background p-4 space-y-4"
							>
								<div className="flex items-center justify-between">
									<Label className="text-sm font-semibold">Tool {index + 1}</Label>
									{tools.length > 1 && (
										<Button
											type="button"
											onClick={() => removeTool(index)}
											variant="ghost"
											size="sm"
										>
											<Trash2 className="h-4 w-4" />
										</Button>
									)}
								</div>

								<div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
									<div className="space-y-2">
										<Label>Tool Name *</Label>
										<Input
											value={tool.name}
											onChange={(e) => updateTool(index, "name", e.target.value)}
											placeholder="get_weather"
											required
										/>
									</div>

									<div className="space-y-2">
										<Label>HTTP Method *</Label>
										<Select
											value={tool.method}
											onValueChange={(value) => updateTool(index, "method", value)}
										>
											<SelectTrigger>
												<SelectValue />
											</SelectTrigger>
											<SelectContent>
												{HTTP_METHODS.map((method) => (
													<SelectItem key={method} value={method}>
														{method}
													</SelectItem>
												))}
											</SelectContent>
										</Select>
									</div>
								</div>

								<div className="space-y-2">
									<Label>
										Description *{" "}
										<span className="text-xs text-muted-foreground font-normal">
											(Be explicit - tell the AI exactly when to use this tool)
										</span>
									</Label>
									<Input
										value={tool.description}
										onChange={(e) => updateTool(index, "description", e.target.value)}
										placeholder="Get current weather for a location"
										required
									/>
								</div>

								<div className="space-y-2">
									<Label>API Endpoint *</Label>
									<Input
										value={tool.endpoint}
										onChange={(e) => updateTool(index, "endpoint", e.target.value)}
										placeholder="https://api.example.com/weather"
										type="url"
										required
									/>
								</div>
							<div className="flex items-center space-x-2">
								<Checkbox
									id={`verify-ssl-${index}`}
									checked={tool.verify_ssl ?? true}
									onCheckedChange={(checked) =>
										updateTool(index, "verify_ssl", checked === true)
									}
								/>
								<Label htmlFor={`verify-ssl-${index}`} className="text-sm font-normal cursor-pointer">
									Verify SSL certificate (recommended for security)
								</Label>
							</div>
								<div className="space-y-2">
									<Label>Authentication Type</Label>
									<Select
										value={tool.auth_type}
										onValueChange={(value) => updateTool(index, "auth_type", value)}
									>
										<SelectTrigger>
											<SelectValue />
										</SelectTrigger>
										<SelectContent>
											<SelectItem value="none">None</SelectItem>
											<SelectItem value="bearer">Bearer Token</SelectItem>
											<SelectItem value="api_key">API Key</SelectItem>
											<SelectItem value="basic">Basic Auth</SelectItem>
										</SelectContent>
									</Select>
								</div>

								{tool.auth_type === "bearer" && (
									<div className="space-y-2">
										<Label>Bearer Token *</Label>
										<Input
											value={tool.auth_config.token || ""}
											onChange={(e) => updateAuthConfig(index, "token", e.target.value)}
											placeholder="your-bearer-token"
											type="password"
											required
										/>
									</div>
								)}

								{tool.auth_type === "api_key" && (
									<>
										<div className="space-y-2">
											<Label>API Key Name *</Label>
											<Input
												value={tool.auth_config.key_name || ""}
												onChange={(e) => updateAuthConfig(index, "key_name", e.target.value)}
												placeholder="X-API-Key"
												required
											/>
										</div>
										<div className="space-y-2">
											<Label>API Key Value *</Label>
											<Input
											value={tool.auth_config.api_key || ""}
											onChange={(e) => updateAuthConfig(index, "api_key", e.target.value)}
												placeholder="your-api-key"
												type="password"
												required
											/>
										</div>
									</>
								)}

								{tool.auth_type === "basic" && (
									<>
										<div className="space-y-2">
											<Label>Username *</Label>
											<Input
												value={tool.auth_config.username || ""}
												onChange={(e) => updateAuthConfig(index, "username", e.target.value)}
												placeholder="username"
												required
											/>
										</div>
										<div className="space-y-2">
											<Label>Password *</Label>
											<Input
												value={tool.auth_config.password || ""}
												onChange={(e) => updateAuthConfig(index, "password", e.target.value)}
												placeholder="password"
												type="password"
												required
											/>
										</div>
									</>
								)}

								<div className="space-y-2">
									<Label>Parameters JSON Schema (Optional)</Label>
									<Textarea
										value={JSON.stringify(tool.parameters, null, 2)}
										onChange={(e) => {
											try {
												const parsed = JSON.parse(e.target.value);
												updateTool(index, "parameters", parsed);
											} catch {
												// Invalid JSON, don't update
											}
										}}
										placeholder={'{\n  "type": "object",\n  "properties": {}\n}'}
										rows={4}
										className="font-mono text-xs"
									/>
								</div>
							</div>
						))}
					</div>
				</div>
			</form>
		</div>
	);
};
