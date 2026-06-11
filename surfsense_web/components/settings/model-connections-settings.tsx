"use client";

import { useAtom, useAtomValue } from "jotai";
import { CheckCircle2, PlugZap, Plus, RefreshCcw, Trash2, XCircle } from "lucide-react";
import { useState } from "react";
import {
	addManualModelMutationAtom,
	createModelConnectionMutationAtom,
	deleteModelConnectionMutationAtom,
	discoverConnectionModelsMutationAtom,
	testModelMutationAtom,
	updateModelConnectionMutationAtom,
	updateModelMutationAtom,
	updateModelRolesMutationAtom,
	verifyModelConnectionMutationAtom,
} from "@/atoms/model-connections/model-connections-mutation.atoms";
import {
	globalModelConnectionsAtom,
	modelConnectionsAtom,
	modelProvidersAtom,
	modelRolesAtom,
} from "@/atoms/model-connections/model-connections-query.atoms";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";
import type { ConnectionRead, ModelRead } from "@/contracts/types/model-connections.types";
import { getProviderIcon } from "@/lib/provider-icons";

// Free-text URL hints (datalist), mirroring OpenWebUI. These never restrict
// what the user can type — any OpenAI-compatible endpoint works.
const URL_SUGGESTIONS = [
	"https://api.openai.com/v1",
	"https://api.anthropic.com/v1",
	"https://openrouter.ai/api/v1",
	"https://generativelanguage.googleapis.com/v1beta/openai",
	"https://api.groq.com/openai/v1",
	"https://api.mistral.ai/v1",
	"https://api.deepseek.com/v1",
	"https://api.x.ai/v1",
	"http://host.docker.internal:11434",
	"http://host.docker.internal:1234/v1",
	"http://host.docker.internal:8000/v1",
];

function modelLabel(model: ModelRead) {
	return model.display_name || model.model_id;
}

function capability(model: ModelRead, key: "chat" | "vision" | "image_gen") {
	if (key === "chat") return Boolean(model.supports_chat);
	if (key === "vision") return Boolean(model.supports_image_input);
	return Boolean(model.supports_image_generation);
}

type ModelCapabilityFilter = "chat" | "vision" | "image_gen";

const MODEL_CAPABILITY_FILTERS: { key: ModelCapabilityFilter; label: string }[] = [
	{ key: "chat", label: "Chat" },
	{ key: "vision", label: "Vision" },
	{ key: "image_gen", label: "Image" },
];

function StatusBadge({ connection }: { connection: ConnectionRead }) {
	if (connection.last_status === "OK") {
		return (
			<Badge variant="outline" className="gap-1 text-green-600">
				<CheckCircle2 className="h-3 w-3" /> Healthy
			</Badge>
		);
	}
	if (connection.last_status) {
		return (
			<Badge variant="outline" className="gap-1 text-destructive">
				<XCircle className="h-3 w-3" /> {connection.last_status}
			</Badge>
		);
	}
	return <Badge variant="secondary">Not tested</Badge>;
}

function flattenModels(connections: ConnectionRead[]) {
	return connections.flatMap((connection) =>
		connection.models.map((model) => ({
			...model,
			connectionName: connection.provider,
			connectionId: connection.id,
			provider: connection.provider,
		}))
	);
}

function ConnectionCard({ connection }: { connection: ConnectionRead }) {
	const verifyConnection = useAtomValue(verifyModelConnectionMutationAtom);
	const discoverModels = useAtomValue(discoverConnectionModelsMutationAtom);
	const updateConnection = useAtomValue(updateModelConnectionMutationAtom);
	const deleteConnection = useAtomValue(deleteModelConnectionMutationAtom);
	const addManualModel = useAtomValue(addManualModelMutationAtom);
	const updateModel = useAtomValue(updateModelMutationAtom);
	const testModel = useAtomValue(testModelMutationAtom);

	const allowlist = Array.isArray(connection.extra?.model_ids)
		? (connection.extra.model_ids as string[])
		: [];
	const [allowlistText, setAllowlistText] = useState(allowlist.join(", "));
	const [manualModelId, setManualModelId] = useState("");
	const [modelFilter, setModelFilter] = useState<ModelCapabilityFilter | null>(null);

	const providerLabel = connection.provider;
	const isLocal =
		connection.provider === "ollama_chat" ||
		connection.provider === "lm_studio" ||
		!connection.base_url?.startsWith("https");
	const filteredModels = modelFilter
		? connection.models.filter((model) => capability(model, modelFilter))
		: connection.models;

	function saveAllowlist() {
		const ids = allowlistText
			.split(",")
			.map((value) => value.trim())
			.filter(Boolean);
		updateConnection.mutate({
			id: connection.id,
			data: { extra: { ...(connection.extra ?? {}), model_ids: ids } },
		});
	}

	function addModel() {
		const modelId = manualModelId.trim();
		if (!modelId) return;
		addManualModel.mutate(
			{ connectionId: connection.id, data: { model_id: modelId } },
			{ onSuccess: () => setManualModelId("") }
		);
	}

	function deleteCurrentConnection() {
		const confirmed = window.confirm(
			`Delete the ${providerLabel} connection and all of its models? This cannot be undone.`
		);
		if (!confirmed) return;
		deleteConnection.mutate(connection.id);
	}

	return (
		<div className="rounded-lg border p-4">
			<div className="flex flex-wrap items-center justify-between gap-3">
				<div>
					<div className="flex items-center gap-2 font-medium">
						{getProviderIcon(providerLabel, { className: "size-4" })}
						{providerLabel}
					</div>
					<div className="text-sm text-muted-foreground">
						{connection.base_url || "Provider default endpoint"}
					</div>
				</div>
				<div className="flex flex-wrap items-center gap-2">
					<StatusBadge connection={connection} />
					<Button
						variant="outline"
						size="sm"
						onClick={() => verifyConnection.mutate(connection.id)}
					>
						Test
					</Button>
					<Button variant="outline" size="sm" onClick={() => discoverModels.mutate(connection.id)}>
						<RefreshCcw className="mr-2 h-4 w-4" /> Discover
					</Button>
					<Button
						variant="destructive"
						size="sm"
						onClick={deleteCurrentConnection}
						disabled={deleteConnection.isPending}
					>
						<Trash2 className="mr-2 h-4 w-4" /> Delete
					</Button>
				</div>
			</div>

			{connection.last_status && connection.last_status !== "OK" ? (
				<p className="mt-2 text-sm text-amber-600 dark:text-amber-500">
					{connection.last_error || "Could not list models."} Chat may still work — add model IDs
					manually below.
				</p>
			) : null}

			{!isLocal ? (
				<div className="mt-4 space-y-1">
					<Label className="text-xs">Model IDs filter (optional)</Label>
					<div className="flex gap-2">
						<Input
							value={allowlistText}
							onChange={(event) => setAllowlistText(event.target.value)}
							placeholder="Comma-separated, e.g. anthropic/claude-sonnet-4-5, google/gemini-2.5-pro"
						/>
						<Button
							variant="outline"
							size="sm"
							onClick={saveAllowlist}
							disabled={updateConnection.isPending}
						>
							Save filter
						</Button>
					</div>
					<p className="text-xs text-muted-foreground">
						Leave empty to discover all models. Recommended for providers with large catalogs (e.g.
						OpenRouter).
					</p>
				</div>
			) : null}

			<div className="mt-4 flex gap-2">
				<Input
					value={manualModelId}
					onChange={(event) => setManualModelId(event.target.value)}
					onKeyDown={(event) => {
						if (event.key === "Enter") {
							event.preventDefault();
							addModel();
						}
					}}
					placeholder="Add a model ID manually (for providers without /models)"
				/>
				<Button
					variant="outline"
					size="sm"
					onClick={addModel}
					disabled={addManualModel.isPending || !manualModelId.trim()}
				>
					<Plus className="mr-2 h-4 w-4" /> Add model
				</Button>
			</div>

			{connection.models.length > 0 ? (
				<div className="mt-4 flex flex-wrap items-center gap-2">
					<span className="text-xs font-medium text-muted-foreground">Filter models</span>
					{MODEL_CAPABILITY_FILTERS.map((filter) => {
						const count = connection.models.filter((model) => capability(model, filter.key)).length;
						const isActive = modelFilter === filter.key;

						return (
							<Button
								key={filter.key}
								type="button"
								variant={isActive ? "secondary" : "outline"}
								size="sm"
								className="h-7 rounded-full px-3 text-xs"
								onClick={() => setModelFilter(isActive ? null : filter.key)}
							>
								{filter.label}
								<span className="ml-1 text-muted-foreground">{count}</span>
							</Button>
						);
					})}
				</div>
			) : null}

			<div className="mt-4 grid gap-2">
				{filteredModels.length === 0 && modelFilter ? (
					<div className="rounded-md bg-muted/30 px-3 py-2 text-xs text-muted-foreground">
						No {MODEL_CAPABILITY_FILTERS.find((filter) => filter.key === modelFilter)?.label.toLowerCase()}{" "}
						models found on this connection.
					</div>
				) : null}
				{filteredModels.map((model) => (
					<div
						key={model.id}
						className="flex flex-wrap items-center justify-between gap-2 rounded-md bg-muted/40 px-3 py-2"
					>
						<div>
							<div className="flex items-center gap-2 text-sm font-medium">
								{getProviderIcon(providerLabel, { className: "size-4" })}
								{modelLabel(model)}
								{model.source === "MANUAL" ? (
									<Badge variant="outline" className="text-[10px]">
										manual
									</Badge>
								) : null}
							</div>
							<div className="text-xs text-muted-foreground">
								{["chat", "vision", "image_gen"]
									.filter((key) => capability(model, key as "chat" | "vision" | "image_gen"))
									.join(", ") || "No discovered capabilities"}
							</div>
						</div>
						<div className="flex gap-2">
							<Button variant="outline" size="sm" onClick={() => testModel.mutate(model.id)}>
								Test
							</Button>
							<Button
								variant={model.enabled ? "secondary" : "outline"}
								size="sm"
								onClick={() =>
									updateModel.mutate({ id: model.id, data: { enabled: !model.enabled } })
								}
							>
								{model.enabled ? "Enabled" : "Enable"}
							</Button>
						</div>
					</div>
				))}
			</div>
		</div>
	);
}

export function ModelConnectionsSettings({ searchSpaceId }: { searchSpaceId: number }) {
	const [{ data: globalConnections = [] }] = useAtom(globalModelConnectionsAtom);
	const [{ data: connections = [] }] = useAtom(modelConnectionsAtom);
	const [{ data: providers = [] }] = useAtom(modelProvidersAtom);
	const [{ data: roles }] = useAtom(modelRolesAtom);
	const createConnection = useAtomValue(createModelConnectionMutationAtom);
	const updateRoles = useAtomValue(updateModelRolesMutationAtom);

	const [provider, setProvider] = useState("openai_compatible");
	const [baseUrl, setBaseUrl] = useState("");
	const [apiKey, setApiKey] = useState("");
	const selectedProvider = providers.find((item) => item.provider === provider);
	const isOllama = provider === "ollama_chat";

	const allConnections = [...globalConnections, ...connections];
	const enabledModels = flattenModels(allConnections).filter((model) => model.enabled);
	const chatModels = enabledModels.filter((model) => capability(model, "chat"));
	const visionModels = enabledModels.filter((model) => capability(model, "vision"));
	const imageModels = enabledModels.filter((model) => capability(model, "image_gen"));

	function handleCreate() {
		createConnection.mutate(
			{
				provider,
				base_url: baseUrl || null,
				api_key: apiKey || null,
				scope: "SEARCH_SPACE",
				search_space_id: searchSpaceId,
				extra: {},
				enabled: true,
			},
			{ onSuccess: () => setApiKey("") }
		);
	}

	function renderModelOption(model: ModelRead & { connectionName: string; provider: string }) {
		return (
			<SelectItem key={model.id} value={String(model.id)}>
				<span className="inline-flex items-center gap-2">
					{getProviderIcon(model.provider, { className: "size-4" })}
					{modelLabel(model)} · {model.connectionName}
				</span>
			</SelectItem>
		);
	}

	return (
		<div className="flex flex-col gap-6">
			<Card>
				<CardHeader>
					<CardTitle>Model Connections</CardTitle>
					<CardDescription>
						Add credentials or local endpoints once, then discover reusable models.
					</CardDescription>
				</CardHeader>
				<CardContent className="space-y-6">
					<div className="grid gap-3 md:grid-cols-[220px_1fr_1fr_auto]">
						<div className="space-y-2">
							<Label>Provider</Label>
							<Select
								value={provider}
								onValueChange={(value) => {
									setProvider(value);
									const next = providers.find((item) => item.provider === value);
									if (next?.default_base_url) setBaseUrl(next.default_base_url);
								}}
							>
								<SelectTrigger>
									<SelectValue />
								</SelectTrigger>
								<SelectContent>
									{providers.map((item) => (
										<SelectItem key={item.provider} value={item.provider}>
											{item.provider}
										</SelectItem>
									))}
								</SelectContent>
							</Select>
						</div>
						<div className="space-y-2">
							<Label>Base URL</Label>
							<Input
								value={baseUrl}
								onChange={(event) => setBaseUrl(event.target.value)}
								placeholder={
									isOllama ? "http://host.docker.internal:11434" : "https://api.example.com/v1"
								}
								list="model-conn-url-suggestions"
							/>
							<datalist id="model-conn-url-suggestions">
								{URL_SUGGESTIONS.map((url) => (
									<option key={url} value={url} />
								))}
							</datalist>
						</div>
						<div className="space-y-2">
							<Label>{isOllama ? "API Key (optional)" : "API Key"}</Label>
							<Input
								value={apiKey}
								onChange={(event) => setApiKey(event.target.value)}
								placeholder={isOllama ? "Optional for Ollama" : "API key"}
								type="password"
							/>
						</div>
						<div className="flex items-end">
							<Button
								onClick={handleCreate}
								disabled={
									createConnection.isPending ||
									Boolean(selectedProvider?.base_url_required && !baseUrl.trim())
								}
							>
								<PlugZap className="mr-2 h-4 w-4" /> Add
							</Button>
						</div>
					</div>
					<div className="space-y-3">
						<p className="text-xs text-muted-foreground">
							{selectedProvider
								? `${selectedProvider.transport} transport, ${selectedProvider.discovery} discovery.`
								: "Choose a provider preset."}{" "}
							Base URL is explicit and editable. Local URLs are tested from the backend container,
							so use host.docker.internal instead of localhost.
						</p>
					</div>

					<div className="space-y-3">
						{connections.map((connection) => (
							<ConnectionCard key={connection.id} connection={connection} />
						))}
					</div>
				</CardContent>
			</Card>

			<Card>
				<CardHeader>
					<CardTitle>Model Roles</CardTitle>
					<CardDescription>
						Pick which enabled model powers chat, vision, and image generation for this search
						space.
					</CardDescription>
				</CardHeader>
				<CardContent className="grid gap-4 md:grid-cols-3">
					<div className="space-y-2">
						<Label>Chat model</Label>
						<Select
							value={String(roles?.chat_model_id ?? 0)}
							onValueChange={(value) => updateRoles.mutate({ chat_model_id: Number(value) })}
						>
							<SelectTrigger>
								<SelectValue />
							</SelectTrigger>
							<SelectContent>
								<SelectItem value="0">Auto</SelectItem>
								{chatModels.map(renderModelOption)}
							</SelectContent>
						</Select>
					</div>
					<div className="space-y-2">
						<Label>Vision</Label>
						<Select
							value={String(roles?.vision_model_id ?? 0)}
							onValueChange={(value) => updateRoles.mutate({ vision_model_id: Number(value) })}
						>
							<SelectTrigger>
								<SelectValue />
							</SelectTrigger>
							<SelectContent>
								<SelectItem value="0">Auto / use chat model when possible</SelectItem>
								{visionModels.map(renderModelOption)}
							</SelectContent>
						</Select>
					</div>
					<div className="space-y-2">
						<Label>Image generation</Label>
						<Select
							value={String(roles?.image_gen_model_id ?? 0)}
							onValueChange={(value) => updateRoles.mutate({ image_gen_model_id: Number(value) })}
						>
							<SelectTrigger>
								<SelectValue />
							</SelectTrigger>
							<SelectContent>
								<SelectItem value="0">Auto / None</SelectItem>
								{imageModels.map(renderModelOption)}
							</SelectContent>
						</Select>
					</div>
				</CardContent>
			</Card>
		</div>
	);
}
