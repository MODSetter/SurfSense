"use client";

import { useAtom, useAtomValue } from "jotai";
import { CheckCircle2, PlugZap, RefreshCcw, XCircle } from "lucide-react";
import { useMemo, useState } from "react";
import {
	createModelConnectionMutationAtom,
	discoverConnectionModelsMutationAtom,
	testModelMutationAtom,
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

export function ModelConnectionsSettings({ searchSpaceId }: { searchSpaceId: number }) {
	const [{ data: globalConnections = [] }] = useAtom(globalModelConnectionsAtom);
	const [{ data: connections = [] }] = useAtom(modelConnectionsAtom);
	const [{ data: roles }] = useAtom(modelRolesAtom);
	const createConnection = useAtomValue(createModelConnectionMutationAtom);
	const verifyConnection = useAtomValue(verifyModelConnectionMutationAtom);
	const discoverModels = useAtomValue(discoverConnectionModelsMutationAtom);
	const updateModel = useAtomValue(updateModelMutationAtom);
	const testModel = useAtomValue(testModelMutationAtom);
	const updateRoles = useAtomValue(updateModelRolesMutationAtom);

	const visiblePresets = useMemo(
		() => PRESETS.filter((preset) => !(isCloud() && preset.local)),
		[]
	);
	const [presetId, setPresetId] = useState(visiblePresets[0]?.id ?? "openai");
	const preset = visiblePresets.find((item) => item.id === presetId) ?? visiblePresets[0];
	const [baseUrl, setBaseUrl] = useState(preset?.baseUrl ?? "");
	const [apiKey, setApiKey] = useState("");

	const allConnections = [...globalConnections, ...connections];
	const enabledModels = flattenModels(allConnections).filter((model) => model.enabled);
	const chatModels = enabledModels.filter((model) => capability(model, "chat"));
	const visionModels = enabledModels.filter((model) => capability(model, "vision"));
	const imageModels = enabledModels.filter((model) => capability(model, "image_gen"));

	function onPresetChange(value: string) {
		setPresetId(value);
		const next = visiblePresets.find((item) => item.id === value);
		setBaseUrl(next?.baseUrl ?? "");
	}

	function handleCreate() {
		if (!preset) return;
		createConnection.mutate({
			protocol: preset.protocol,
			native_provider: preset.nativeProvider,
			base_url: baseUrl || null,
			api_key: apiKey || null,
			scope: "SEARCH_SPACE",
			search_space_id: searchSpaceId,
			extra: {},
			enabled: true,
		});
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
							<Label>Preset</Label>
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
							<Label>Base URL</Label>
							<Input
								value={baseUrl}
								onChange={(event) => setBaseUrl(event.target.value)}
								placeholder="https://api.example.com/v1"
							/>
						</div>
						<div className="space-y-2">
							<Label>API Key</Label>
							<Input
								value={apiKey}
								onChange={(event) => setApiKey(event.target.value)}
								placeholder="Optional for local models"
								type="password"
							/>
						</div>
						<div className="flex items-end">
							<Button onClick={handleCreate} disabled={createConnection.isPending}>
								<PlugZap className="mr-2 h-4 w-4" /> Add
							</Button>
						</div>
					</div>
					{preset?.local ? (
						<p className="text-xs text-muted-foreground">
							Local URLs are tested from the backend container. Use host.docker.internal instead of
							localhost.
						</p>
					) : null}

					<div className="space-y-3">
						{connections.map((connection) => (
							<div key={connection.id} className="rounded-lg border p-4">
								<div className="flex flex-wrap items-center justify-between gap-3">
									<div>
										<div className="flex items-center gap-2 font-medium">
											{getProviderIcon(connection.native_provider || connection.protocol, {
												className: "size-4",
											})}
											{connection.native_provider || connection.protocol}
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
								{connection.last_error ? (
									<p className="mt-2 text-sm text-destructive">{connection.last_error}</p>
								) : null}
								<div className="mt-4 grid gap-2">
									{connection.models.map((model) => (
										<div
											key={model.id}
											className="flex flex-wrap items-center justify-between gap-2 rounded-md bg-muted/40 px-3 py-2"
										>
											<div>
												<div className="flex items-center gap-2 text-sm font-medium">
													{getProviderIcon(connection.native_provider || connection.protocol, {
														className: "size-4",
													})}
													{modelLabel(model)}
												</div>
												<div className="text-xs text-muted-foreground">
													{["chat", "vision", "image_gen"]
														.filter((key) => Boolean(model.capabilities?.[key]))
														.join(", ") || "No verified capabilities"}
												</div>
											</div>
											<div className="flex gap-2">
												<Button
													variant="outline"
													size="sm"
													onClick={() => testModel.mutate(model.id)}
												>
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
