"use client";

import * as RadioGroup from "@radix-ui/react-radio-group";
import { KeyRound, Server } from "lucide-react";
import type { FC } from "react";
import { useEffect, useId, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import type { ConnectorConfigProps } from "../index";

export interface ElasticsearchConfigProps extends ConnectorConfigProps {
	onNameChange?: (name: string) => void;
}

export const ElasticsearchConfig: FC<ElasticsearchConfigProps> = ({
	connector,
	onConfigChange,
	onNameChange,
}) => {
	const authBasicId = useId();
	const authApiKeyId = useId();

	const [name, setName] = useState<string>(connector.name || "");
	const [endpointUrl, setEndpointUrl] = useState<string>(
		(connector.config?.ELASTICSEARCH_URL as string) || ""
	);
	const [authMethod, setAuthMethod] = useState<"basic" | "api_key">(
		(connector.config?.ELASTICSEARCH_API_KEY ? "api_key" : "basic") as "basic" | "api_key"
	);
	const [username, setUsername] = useState<string>(
		(connector.config?.ELASTICSEARCH_USERNAME as string) || ""
	);
	const [password, setPassword] = useState<string>(
		(connector.config?.ELASTICSEARCH_PASSWORD as string) || ""
	);
	const [apiKey, setApiKey] = useState<string>(
		(connector.config?.ELASTICSEARCH_API_KEY as string) || ""
	);
	const [indices, setIndices] = useState<string>(
		Array.isArray(connector.config?.ELASTICSEARCH_INDEX)
			? (connector.config?.ELASTICSEARCH_INDEX as string[]).join(", ")
			: (connector.config?.ELASTICSEARCH_INDEX as string) || ""
	);
	const [query, setQuery] = useState<string>(
		(connector.config?.ELASTICSEARCH_QUERY as string) || "*"
	);
	const [searchFields, setSearchFields] = useState<string>(
		Array.isArray(connector.config?.ELASTICSEARCH_FIELDS)
			? (connector.config?.ELASTICSEARCH_FIELDS as string[]).join(", ")
			: ""
	);
	const [maxDocuments, setMaxDocuments] = useState<string>(
		connector.config?.ELASTICSEARCH_MAX_DOCUMENTS
			? String(connector.config.ELASTICSEARCH_MAX_DOCUMENTS)
			: ""
	);

	// Update values when connector changes
	useEffect(() => {
		setName(connector.name || "");
		setEndpointUrl((connector.config?.ELASTICSEARCH_URL as string) || "");
		setAuthMethod(
			(connector.config?.ELASTICSEARCH_API_KEY ? "api_key" : "basic") as "basic" | "api_key"
		);
		setUsername((connector.config?.ELASTICSEARCH_USERNAME as string) || "");
		setPassword((connector.config?.ELASTICSEARCH_PASSWORD as string) || "");
		setApiKey((connector.config?.ELASTICSEARCH_API_KEY as string) || "");
		setIndices(
			Array.isArray(connector.config?.ELASTICSEARCH_INDEX)
				? (connector.config?.ELASTICSEARCH_INDEX as string[]).join(", ")
				: (connector.config?.ELASTICSEARCH_INDEX as string) || ""
		);
		setQuery((connector.config?.ELASTICSEARCH_QUERY as string) || "*");
		setSearchFields(
			Array.isArray(connector.config?.ELASTICSEARCH_FIELDS)
				? (connector.config?.ELASTICSEARCH_FIELDS as string[]).join(", ")
				: ""
		);
		setMaxDocuments(
			connector.config?.ELASTICSEARCH_MAX_DOCUMENTS
				? String(connector.config.ELASTICSEARCH_MAX_DOCUMENTS)
				: ""
		);
	}, [connector.config, connector.name]);

	const stringToArray = (str: string): string[] => {
		const items = str
			.split(",")
			.map((item) => item.trim())
			.filter((item) => item.length > 0);
		return Array.from(new Set(items));
	};

	const updateConfig = (updates: Record<string, unknown>) => {
		if (onConfigChange) {
			// Filter out undefined values to remove keys
			const filteredUpdates = Object.fromEntries(
				Object.entries(updates).filter(([_, value]) => value !== undefined)
			);
			const newConfig = {
				...connector.config,
				...filteredUpdates,
			};
			// Remove keys that were set to undefined
			Object.keys(updates).forEach((key) => {
				if (updates[key] === undefined) {
					delete newConfig[key];
				}
			});
			onConfigChange(newConfig);
		}
	};

	const handleNameChange = (value: string) => {
		setName(value);
		if (onNameChange) {
			onNameChange(value);
		}
	};

	const handleEndpointUrlChange = (value: string) => {
		setEndpointUrl(value);
		updateConfig({ ELASTICSEARCH_URL: value });
	};

	const handleAuthMethodChange = (value: "basic" | "api_key") => {
		setAuthMethod(value);
		if (value === "basic") {
			updateConfig({
				ELASTICSEARCH_API_KEY: undefined,
			});
		} else {
			updateConfig({
				ELASTICSEARCH_USERNAME: undefined,
				ELASTICSEARCH_PASSWORD: undefined,
			});
		}
	};

	const handleUsernameChange = (value: string) => {
		setUsername(value);
		updateConfig({ ELASTICSEARCH_USERNAME: value });
	};

	const handlePasswordChange = (value: string) => {
		setPassword(value);
		updateConfig({ ELASTICSEARCH_PASSWORD: value });
	};

	const handleApiKeyChange = (value: string) => {
		setApiKey(value);
		updateConfig({ ELASTICSEARCH_API_KEY: value });
	};

	const handleIndicesChange = (value: string) => {
		setIndices(value);
		const indicesArr = stringToArray(value);
		const indexValue =
			indicesArr.length === 0 ? "*" : indicesArr.length === 1 ? indicesArr[0] : indicesArr;
		updateConfig({ ELASTICSEARCH_INDEX: indexValue });
	};

	const handleQueryChange = (value: string) => {
		setQuery(value);
		if (value && value !== "*") {
			updateConfig({ ELASTICSEARCH_QUERY: value });
		} else {
			// Remove the key by setting it to undefined
			updateConfig({ ELASTICSEARCH_QUERY: undefined });
		}
	};

	const handleSearchFieldsChange = (value: string) => {
		setSearchFields(value);
		if (value.trim()) {
			const fields = stringToArray(value);
			updateConfig({
				ELASTICSEARCH_FIELDS: fields,
				ELASTICSEARCH_CONTENT_FIELDS: fields,
				ELASTICSEARCH_TITLE_FIELD: fields.includes("title") ? "title" : undefined,
			});
		} else {
			// Remove the keys by setting them to undefined
			updateConfig({
				ELASTICSEARCH_FIELDS: undefined,
				ELASTICSEARCH_CONTENT_FIELDS: undefined,
				ELASTICSEARCH_TITLE_FIELD: undefined,
			});
		}
	};

	const handleMaxDocumentsChange = (value: string) => {
		setMaxDocuments(value);
		if (value && value.trim()) {
			const num = parseInt(value, 10);
			if (!isNaN(num) && num > 0) {
				updateConfig({ ELASTICSEARCH_MAX_DOCUMENTS: num });
			}
		} else {
			// Remove the key by setting it to undefined
			updateConfig({ ELASTICSEARCH_MAX_DOCUMENTS: undefined });
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
						placeholder="My Elasticsearch Connector"
						className="border-slate-400/20 focus-visible:border-slate-400/40"
					/>
					<p className="text-[10px] sm:text-xs text-muted-foreground">
						A friendly name to identify this connector.
					</p>
				</div>
			</div>

			{/* Connection Details */}
			<div className="rounded-xl border border-border bg-slate-400/5 dark:bg-white/5 p-3 sm:p-6 space-y-3 sm:space-y-4">
				<div className="space-y-1 sm:space-y-2">
					<h3 className="font-medium text-sm sm:text-base flex items-center gap-2">
						<Server className="h-4 w-4" />
						Connection Details
					</h3>
				</div>

				<div className="space-y-2">
					<Label className="text-xs sm:text-sm">Elasticsearch Endpoint URL</Label>
					<Input
						type="url"
						value={endpointUrl}
						onChange={(e) => handleEndpointUrlChange(e.target.value)}
						placeholder="https://your-cluster.es.region.aws.com:443"
						className="border-slate-400/20 focus-visible:border-slate-400/40"
					/>
					<p className="text-[10px] sm:text-xs text-muted-foreground">
						Update the Elasticsearch endpoint URL if needed.
					</p>
				</div>
			</div>

			{/* Authentication */}
			<div className="rounded-xl border border-border bg-slate-400/5 dark:bg-white/5 p-3 sm:p-6 space-y-3 sm:space-y-4">
				<div className="space-y-1 sm:space-y-2">
					<h3 className="font-medium text-sm sm:text-base flex items-center gap-2">
						<KeyRound className="h-4 w-4" />
						Authentication
					</h3>
				</div>

				<div className="space-y-4">
					<RadioGroup.Root
						value={authMethod}
						onValueChange={(value) => handleAuthMethodChange(value as "basic" | "api_key")}
						className="flex flex-col space-y-2"
					>
						<div className="flex items-center space-x-2">
							<RadioGroup.Item
								value="api_key"
								id={authApiKeyId}
								className="aspect-square h-4 w-4 rounded-full border border-primary text-primary ring-offset-background focus:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 data-[state=checked]:bg-primary data-[state=checked]:text-primary-foreground"
							>
								<RadioGroup.Indicator className="flex items-center justify-center">
									<div className="h-2.5 w-2.5 rounded-full bg-current" />
								</RadioGroup.Indicator>
							</RadioGroup.Item>
							<Label htmlFor={authApiKeyId} className="text-xs sm:text-sm">
								API Key
							</Label>
						</div>

						<div className="flex items-center space-x-2">
							<RadioGroup.Item
								value="basic"
								id={authBasicId}
								className="aspect-square h-4 w-4 rounded-full border border-primary text-primary ring-offset-background focus:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 data-[state=checked]:bg-primary data-[state=checked]:text-primary-foreground"
							>
								<RadioGroup.Indicator className="flex items-center justify-center">
									<div className="h-2.5 w-2.5 rounded-full bg-current" />
								</RadioGroup.Indicator>
							</RadioGroup.Item>
							<Label htmlFor={authBasicId} className="text-xs sm:text-sm">
								Username & Password
							</Label>
						</div>
					</RadioGroup.Root>

					{authMethod === "basic" && (
						<div className="grid grid-cols-1 md:grid-cols-2 gap-4">
							<div className="space-y-2">
								<Label className="text-xs sm:text-sm">Username</Label>
								<Input
									value={username}
									onChange={(e) => handleUsernameChange(e.target.value)}
									placeholder="elastic"
									className="border-slate-400/20 focus-visible:border-slate-400/40"
								/>
							</div>
							<div className="space-y-2">
								<Label className="text-xs sm:text-sm">Password</Label>
								<Input
									type="password"
									value={password}
									onChange={(e) => handlePasswordChange(e.target.value)}
									placeholder="Password"
									className="border-slate-400/20 focus-visible:border-slate-400/40"
								/>
							</div>
						</div>
					)}

					{authMethod === "api_key" && (
						<div className="space-y-2">
							<Label className="text-xs sm:text-sm">API Key</Label>
							<Input
								type="password"
								value={apiKey}
								onChange={(e) => handleApiKeyChange(e.target.value)}
								placeholder="Your API Key Here"
								className="border-slate-400/20 focus-visible:border-slate-400/40"
							/>
							<p className="text-[10px] sm:text-xs text-muted-foreground">
								Update the Elasticsearch API key if needed.
							</p>
						</div>
					)}
				</div>
			</div>

			{/* Index Selection */}
			<div className="rounded-xl border border-border bg-slate-400/5 dark:bg-white/5 p-3 sm:p-6 space-y-3 sm:space-y-4">
				<div className="space-y-1 sm:space-y-2">
					<h3 className="font-medium text-sm sm:text-base">Index Selection</h3>
				</div>

				<div className="space-y-2">
					<Label className="text-xs sm:text-sm">Indices</Label>
					<Input
						value={indices}
						onChange={(e) => handleIndicesChange(e.target.value)}
						placeholder="logs-*, documents-*, app-logs"
						className="border-slate-400/20 focus-visible:border-slate-400/40"
					/>
					<p className="text-[10px] sm:text-xs text-muted-foreground">
						Comma-separated indices to search (e.g., "logs-*, documents-*").
					</p>
				</div>

				{indices.trim() && (
					<div className="rounded-lg border border-border bg-muted/50 p-3">
						<h4 className="text-[10px] sm:text-xs font-medium mb-2">Selected Indices:</h4>
						<div className="flex flex-wrap gap-2">
							{stringToArray(indices).map((index) => (
								<Badge key={index} variant="secondary" className="text-[10px]">
									{index}
								</Badge>
							))}
						</div>
					</div>
				)}
			</div>

			{/* Advanced Configuration */}
			<div className="rounded-xl border border-border bg-slate-400/5 dark:bg-white/5 p-3 sm:p-6 space-y-3 sm:space-y-4">
				<div className="space-y-1 sm:space-y-2">
					<h3 className="font-medium text-sm sm:text-base">Advanced Configuration</h3>
				</div>

				<div className="space-y-4">
					<div className="space-y-2">
						<Label className="text-xs sm:text-sm">
							Default Search Query <span className="text-muted-foreground">(Optional)</span>
						</Label>
						<Input
							value={query}
							onChange={(e) => handleQueryChange(e.target.value)}
							placeholder="*"
							className="border-slate-400/20 focus-visible:border-slate-400/40"
						/>
						<p className="text-[10px] sm:text-xs text-muted-foreground">
							Default Elasticsearch query to use for searches. Use "*" to match all documents.
						</p>
					</div>

					<div className="space-y-2">
						<Label className="text-xs sm:text-sm">
							Search Fields <span className="text-muted-foreground">(Optional)</span>
						</Label>
						<Input
							value={searchFields}
							onChange={(e) => handleSearchFieldsChange(e.target.value)}
							placeholder="title, content, description"
							className="border-slate-400/20 focus-visible:border-slate-400/40"
						/>
						<p className="text-[10px] sm:text-xs text-muted-foreground">
							Comma-separated list of specific fields to search in.
						</p>
					</div>

					{searchFields.trim() && (
						<div className="rounded-lg border border-border bg-muted/50 p-3">
							<h4 className="text-[10px] sm:text-xs font-medium mb-2">Search Fields:</h4>
							<div className="flex flex-wrap gap-2">
								{stringToArray(searchFields).map((field) => (
									<Badge key={field} variant="outline" className="text-[10px]">
										{field}
									</Badge>
								))}
							</div>
						</div>
					)}

					<div className="space-y-2">
						<Label className="text-xs sm:text-sm">
							Maximum Documents <span className="text-muted-foreground">(Optional)</span>
						</Label>
						<Input
							type="number"
							value={maxDocuments}
							onChange={(e) => handleMaxDocumentsChange(e.target.value)}
							placeholder="1000"
							min="1"
							max="10000"
							className="border-slate-400/20 focus-visible:border-slate-400/40"
						/>
						<p className="text-[10px] sm:text-xs text-muted-foreground">
							Maximum number of documents to retrieve per search (1-10,000).
						</p>
					</div>
				</div>
			</div>
		</div>
	);
};
