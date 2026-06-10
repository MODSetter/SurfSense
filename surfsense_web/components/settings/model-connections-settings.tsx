"use client";

import { useAtom, useAtomValue } from "jotai";
import { CheckCircle2, PlugZap, Plus, RefreshCcw, XCircle } from "lucide-react";
import { useMemo, useState } from "react";
import {
	addManualModelMutationAtom,
	createModelConnectionMutationAtom,
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
import type {
	ConnectionProtocol,
	ConnectionRead,
	ModelRead,
} from "@/contracts/types/model-connections.types";
import { isCloud } from "@/lib/env-config";
import { getProviderIcon } from "@/lib/provider-icons";

type Preset = {
	id: string;
	label: string;
	protocol: ConnectionProtocol;
	nativeProvider?: string;
	baseUrl?: string;
	local?: boolean;
};

const PRESETS: Preset[] = [
	{ id: "custom", label: "OpenAI-compatible (any URL)", protocol: "OPENAI_COMPATIBLE" },
	{ id: "openai", label: "OpenAI", protocol: "NATIVE", nativeProvider: "OPENAI" },
	{ id: "anthropic", label: "Anthropic", protocol: "NATIVE", nativeProvider: "ANTHROPIC" },
	{ id: "openrouter", label: "OpenRouter", protocol: "NATIVE", nativeProvider: "OPENROUTER" },
	{
		id: "ollama",
		label: "Ollama",
		protocol: "OLLAMA",
		baseUrl: "http://host.docker.internal:11434",
		local: true,
	},
	{
		id: "lmstudio",
		label: "LM Studio",
		protocol: "OPENAI_COMPATIBLE",
		baseUrl: "http://host.docker.internal:1234/v1",
		local: true,
	},
	{
		id: "llamacpp",
		label: "llama.cpp",
		protocol: "OPENAI_COMPATIBLE",
		baseUrl: "http://host.docker.internal:8080/v1",
		local: true,
	},
	{
		id: "localai",
		label: "LocalAI",
		protocol: "OPENAI_COMPATIBLE",
		baseUrl: "http://host.docker.internal:8080/v1",
		local: true,
	},
	{
		id: "vllm",
		label: "vLLM",
		protocol: "OPENAI_COMPATIBLE",
		baseUrl: "http://host.docker.internal:8000/v1",
		local: true,
	},
];

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
	return Boolean(model.capabilities?.[key]);
}

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
			connectionName: connection.native_provider || connection.protocol,
			connectionId: connection.id,
			provider: connection.native_provider || connection.protocol,
		}))
	);
}

function ConnectionCard({ connection }: { connection: ConnectionRead }) {
	const verifyConnection = useAtomValue(verifyModelConnectionMutationAtom);
	const discoverModels = useAtomValue(discoverConnectionModelsMutationAtom);
	const updateConnection = useAtomValue(updateModelConnectionMutationAtom);
	const addManualModel = useAtomValue(addManualModelMutationAtom);
	const updateModel = useAtomValue(updateModelMutationAtom);
	const testModel = useAtomValue(testModelMutationAtom);

	const allowlist = Array.isArray(connection.extra?.model_ids)
		? (connection.extra.model_ids as string[])
		: [];
	const [allowlistText, setAllowlistText] = useState(allowlist.join(", "));
	const [manualModelId, setManualModelId] = useState("");

	const providerLabel = connection.native_provider || connection.protocol;
	const isLocal = connection.protocol === "OLLAMA" || !connection.base_url?.startsWith("https");

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
					<Button
						variant="outline"
						size="sm"
						onClick={() => discoverModels.mutate(connection.id)}
					>
						<RefreshCcw className="mr-2 h-4 w-4" /> Discover
					</Button>
				</div>
			</div>

			{connection.last_status && connection.last_status !== "OK" ? (
				<p className="mt-2 text-sm text-amber-600 dark:text-amber-500">
					{connection.last_error || "Could not list models."} Chat may still work — add model
					IDs manually below.
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
						Leave empty to discover all models. Recommended for providers with large catalogs
						(e.g. OpenRouter).
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

			<div className="mt-4 grid gap-2">
				{connection.models.map((model) => (
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
									.filter((key) => Boolean(model.capabilities?.[key]))
									.join(", ") || "No verified capabilities"}
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
	const [{ data: roles }] = useAtom(modelRolesAtom);
	const createConnection = useAtomValue(createModelConnectionMutationAtom);
	const updateRoles = useAtomValue(updateModelRolesMutationAtom);

	const visiblePresets = useMemo(
		() => PRESETS.filter((preset) => !(isCloud() && preset.local)),
		[]
	);
	const [presetId, setPresetId] = useState(visiblePresets[0]?.id ?? "custom");
	const preset = visiblePresets.find((item) => item.id === presetId) ?? visiblePresets[0];
	const [baseUrl, setBaseUrl] = useState(preset?.baseUrl ?? "");
	const [apiKey, setApiKey] = useState("");
	// Native providers carry their endpoint inside LiteLLM, so Base URL is hidden
	// by default and only revealed for power users who want to override it.
	const [showCustomEndpoint, setShowCustomEndpoint] = useState(false);

	const isNative = preset?.protocol === "NATIVE";
	const requiresUrl = !isNative;

	const allConnections = [...globalConnections, ...connections];
	const enabledModels = flattenModels(allConnections).filter((model) => model.enabled);
	const chatModels = enabledModels.filter((model) => capability(model, "chat"));
	const visionModels = enabledModels.filter((model) => capability(model, "vision"));
	const imageModels = enabledModels.filter((model) => capability(model, "image_gen"));

	function onPresetChange(value: string) {
		setPresetId(value);
		const next = visiblePresets.find((item) => item.id === value);
		// Native providers use LiteLLM's built-in endpoint; everything else needs
		// (and may prefill) a Base URL.
		setBaseUrl(next?.protocol === "NATIVE" ? "" : (next?.baseUrl ?? ""));
		setShowCustomEndpoint(false);
	}

	function handleCreate() {
		if (!preset) return;
		createConnection.mutate(
			{
				protocol: preset.protocol,
				native_provider: preset.nativeProvider,
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
							<Select value={presetId} onValueChange={onPresetChange}>
								<SelectTrigger>
									<SelectValue />
								</SelectTrigger>
								<SelectContent>
									{visiblePresets.map((item) => (
										<SelectItem key={item.id} value={item.id}>
											<span className="inline-flex items-center gap-2">
												{getProviderIcon(item.nativeProvider || item.protocol, {
													className: "size-4",
												})}
												{item.label}
											</span>
										</SelectItem>
									))}
								</SelectContent>
							</Select>
						</div>
						<div className="space-y-2">
							<Label>{isNative ? "Base URL (optional)" : "Base URL"}</Label>
							{isNative && !showCustomEndpoint ? (
								<div className="space-y-1">
									<div className="flex h-9 items-center text-sm text-muted-foreground">
										Uses provider default
									</div>
									<button
										type="button"
										className="text-xs text-primary hover:underline"
										onClick={() => setShowCustomEndpoint(true)}
									>
										Override endpoint
									</button>
								</div>
							) : (
								<>
									<Input
										value={baseUrl}
										onChange={(event) => setBaseUrl(event.target.value)}
										placeholder="https://api.example.com/v1"
										list="model-conn-url-suggestions"
									/>
									<datalist id="model-conn-url-suggestions">
										{URL_SUGGESTIONS.map((url) => (
											<option key={url} value={url} />
										))}
									</datalist>
								</>
							)}
						</div>
						<div className="space-y-2">
							<Label>{preset?.local ? "API Key (optional)" : "API Key"}</Label>
							<Input
								value={apiKey}
								onChange={(event) => setApiKey(event.target.value)}
								placeholder={preset?.local ? "Optional for local models" : "API key"}
								type="password"
							/>
						</div>
						<div className="flex items-end">
							<Button
								onClick={handleCreate}
								disabled={createConnection.isPending || (requiresUrl && !baseUrl.trim())}
							>
								<PlugZap className="mr-2 h-4 w-4" /> Add
							</Button>
						</div>
					</div>
					{preset?.local ? (
						<p className="text-xs text-muted-foreground">
							Local URLs are tested from the backend container. Use host.docker.internal instead of
							localhost.
						</p>
					) : isNative ? (
						<p className="text-xs text-muted-foreground">
							Just paste an API key — {preset?.label} routes through its native endpoint
							automatically. After adding, hit Discover (or add model IDs manually).
						</p>
					) : preset?.protocol === "OPENAI_COMPATIBLE" ? (
						<p className="text-xs text-muted-foreground">
							Enter any OpenAI-compatible endpoint (OpenRouter, Together, Groq, vLLM, LM Studio…).
							After adding, hit Discover to list models.
						</p>
					) : null}

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
