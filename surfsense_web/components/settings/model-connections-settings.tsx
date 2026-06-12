"use client";

import { useAtom, useAtomValue } from "jotai";
import {
	Check,
	CheckCircle2,
	ChevronsUpDown,
	Eye,
	EyeOff,
	RefreshCcw,
	Settings,
	Trash2,
	XCircle,
} from "lucide-react";
import { useState } from "react";
import {
	addManualModelMutationAtom,
	bulkUpdateModelsMutationAtom,
	createModelConnectionMutationAtom,
	deleteModelConnectionMutationAtom,
	discoverConnectionModelsMutationAtom,
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
import {
	AlertDialog,
	AlertDialogAction,
	AlertDialogCancel,
	AlertDialogContent,
	AlertDialogDescription,
	AlertDialogFooter,
	AlertDialogHeader,
	AlertDialogTitle,
	AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import {
	Command,
	CommandEmpty,
	CommandGroup,
	CommandInput,
	CommandItem,
	CommandList,
} from "@/components/ui/command";
import {
	Dialog,
	DialogContent,
	DialogDescription,
	DialogFooter,
	DialogHeader,
	DialogTitle,
	DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";
import { Separator } from "@/components/ui/separator";
import type {
	ConnectionRead,
	ConnectionUpdateRequest,
	ModelRead,
} from "@/contracts/types/model-connections.types";
import { getProviderIcon } from "@/lib/provider-icons";
import { cn } from "@/lib/utils";

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

function UrlSuggestionCombobox({
	value,
	onChange,
	placeholder,
}: {
	value: string;
	onChange: (value: string) => void;
	placeholder: string;
}) {
	const [open, setOpen] = useState(false);

	return (
		<Popover open={open} onOpenChange={setOpen}>
			<PopoverTrigger asChild>
				<Button
					variant="outline"
					role="combobox"
					aria-expanded={open}
					className="w-full justify-between bg-transparent font-normal"
				>
					<span className={cn("truncate", !value && "text-muted-foreground")}>
						{value || placeholder}
					</span>
					<ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
				</Button>
			</PopoverTrigger>
			<PopoverContent className="w-[var(--radix-popover-trigger-width)] p-0" align="start">
				<Command className="bg-transparent">
					<CommandInput
						placeholder="Search or type URL..."
						value={value}
						onValueChange={onChange}
					/>
					<CommandList>
						<CommandEmpty>
							<span className="text-xs text-muted-foreground">Use the custom URL you typed</span>
						</CommandEmpty>
						<CommandGroup>
							{URL_SUGGESTIONS.map((url) => (
								<CommandItem
									key={url}
									value={url}
									onSelect={() => {
										onChange(url);
										setOpen(false);
									}}
								>
									<Check
										className={cn("mr-2 h-4 w-4", value === url ? "opacity-100" : "opacity-0")}
									/>
									<span className="truncate font-mono text-sm">{url}</span>
								</CommandItem>
							))}
						</CommandGroup>
					</CommandList>
				</Command>
			</PopoverContent>
		</Popover>
	);
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
	const bulkUpdateModels = useAtomValue(bulkUpdateModelsMutationAtom);

	const allowlist = Array.isArray(connection.extra?.model_ids)
		? (connection.extra.model_ids as string[])
		: [];
	const [isSettingsOpen, setIsSettingsOpen] = useState(false);
	const [baseUrlDraft, setBaseUrlDraft] = useState(connection.base_url ?? "");
	const [apiKeyDraft, setApiKeyDraft] = useState("");
	const [showApiKey, setShowApiKey] = useState(false);
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
	const allFilteredModelsEnabled =
		filteredModels.length > 0 && filteredModels.every((model) => model.enabled);
	const hasConnectionChanges =
		baseUrlDraft.trim() !== (connection.base_url ?? "") ||
		apiKeyDraft.trim() !== (connection.api_key ?? "");

	function handleSettingsOpenChange(open: boolean) {
		setIsSettingsOpen(open);
		if (open) {
			setBaseUrlDraft(connection.base_url ?? "");
			setApiKeyDraft(connection.api_key ?? "");
			setShowApiKey(false);
			setAllowlistText(allowlist.join(", "));
		}
	}

	function saveConnectionSettings() {
		const data: ConnectionUpdateRequest = {
			base_url: baseUrlDraft.trim() || null,
		};

		if (apiKeyDraft.trim() !== (connection.api_key ?? "")) {
			data.api_key = apiKeyDraft.trim() || null;
		}

		updateConnection.mutate(
			{ id: connection.id, data },
			{
				onSuccess: () => setApiKeyDraft(""),
			}
		);
	}

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
		deleteConnection.mutate(connection.id);
	}

	function toggleFilteredModels() {
		const nextEnabled = !allFilteredModelsEnabled;
		const modelIds = filteredModels
			.filter((model) => model.enabled !== nextEnabled)
			.map((model) => model.id);

		if (modelIds.length === 0) return;

		bulkUpdateModels.mutate({
			connectionId: connection.id,
			data: { model_ids: modelIds, enabled: nextEnabled },
		});
	}

	return (
		<div className="rounded-xl border bg-background p-4 shadow-sm">
			<div className="flex items-center justify-between gap-3">
				<div className="min-w-0">
					<div className="flex items-center gap-2 font-semibold">
						{getProviderIcon(providerLabel, { className: "size-4" })}
						<span className="truncate">{providerLabel}</span>
						{connection.scope === "GLOBAL" ? (
							<Badge variant="outline" className="text-[10px]">
								Default
							</Badge>
						) : null}
					</div>
					<div className="truncate text-sm text-muted-foreground">
						{connection.base_url || "Provider default endpoint"}
					</div>
				</div>
				<div className="flex shrink-0 items-center gap-2">
					<StatusBadge connection={connection} />
					<Dialog open={isSettingsOpen} onOpenChange={handleSettingsOpenChange}>
						<DialogTrigger asChild>
							<Button variant="ghost" size="icon" aria-label={`Configure ${providerLabel}`}>
								<Settings className="h-4 w-4" />
							</Button>
						</DialogTrigger>
						<DialogContent className="flex max-h-[90vh] max-w-3xl flex-col overflow-hidden bg-popover p-0 text-popover-foreground">
							<DialogHeader className="shrink-0 border-b px-6 py-5">
								<div className="flex items-center gap-3">
									{getProviderIcon(providerLabel, { className: "size-5" })}
									<div>
										<DialogTitle>
											Configure <span className="italic">{providerLabel}</span>
										</DialogTitle>
										<DialogDescription>
											Manage credentials and choose which models are available from this provider.
										</DialogDescription>
									</div>
								</div>
							</DialogHeader>

							<div className="min-h-0 flex-1 overflow-y-auto px-6 py-5">
								<div className="space-y-6">
									<div className="space-y-2">
										<Label>API Base URL</Label>
										<UrlSuggestionCombobox
											value={baseUrlDraft}
											onChange={setBaseUrlDraft}
											placeholder="https://api.example.com/v1"
										/>
										<p className="text-xs text-muted-foreground">
											Leave empty to use the provider default endpoint.
										</p>
									</div>

									<div className="space-y-2">
										<Label>API Key</Label>
										<div className="relative">
											<Input
												value={apiKeyDraft}
												onChange={(event) => setApiKeyDraft(event.target.value)}
												placeholder={connection.has_api_key ? "Saved API key" : "Paste an API key"}
												type={showApiKey ? "text" : "password"}
												className="pr-11"
											/>
											<Button
												type="button"
												variant="ghost"
												size="icon"
												className="absolute top-1/2 right-1 size-8 -translate-y-1/2 text-muted-foreground"
												onClick={() => setShowApiKey((current) => !current)}
												disabled={!apiKeyDraft}
												aria-label={showApiKey ? "Hide API key" : "Show API key"}
											>
												{showApiKey ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
											</Button>
										</div>
									</div>

									{!isLocal ? (
										<div className="space-y-2">
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
												Leave empty to discover all models. Recommended for providers with large
												catalogs.
											</p>
										</div>
									) : null}

									<Separator className="bg-muted-foreground/20" />

									<div className="space-y-3">
										<div className="flex flex-wrap items-start justify-between gap-3">
											<div>
												<div className="font-semibold">Models</div>
												<p className="text-sm text-muted-foreground">
													Select models to make available for this provider.
												</p>
											</div>
											<div className="flex flex-wrap items-center gap-2">
												<Button
													variant="ghost"
													size="sm"
													type="button"
													onClick={toggleFilteredModels}
													disabled={bulkUpdateModels.isPending || filteredModels.length === 0}
												>
													{allFilteredModelsEnabled ? "Deselect All" : "Select All"}
												</Button>
												<Button
													variant="outline"
													size="icon"
													onClick={() => discoverModels.mutate(connection.id)}
													disabled={discoverModels.isPending}
													aria-label={`Refresh ${providerLabel} models`}
												>
													<RefreshCcw className="h-4 w-4" />
												</Button>
											</div>
										</div>

										<div className="flex gap-2">
											<Input
												value={manualModelId}
												onChange={(event) => setManualModelId(event.target.value)}
												onKeyDown={(event) => {
													if (event.key === "Enter") {
														event.preventDefault();
														addModel();
													}
												}}
												placeholder="Add a model ID manually"
											/>
											<Button
												variant="outline"
												size="sm"
												onClick={addModel}
												disabled={addManualModel.isPending || !manualModelId.trim()}
											>
												Add model
											</Button>
										</div>

										{connection.models.length > 0 ? (
											<div className="flex flex-wrap items-center gap-2">
												<span className="text-xs font-medium text-muted-foreground">
													Filter models
												</span>
												{MODEL_CAPABILITY_FILTERS.map((filter) => {
													const count = connection.models.filter((model) =>
														capability(model, filter.key)
													).length;
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

										<div className="max-h-80 overflow-y-auto rounded-xl border bg-muted/20 p-2">
											{connection.models.length === 0 ? (
												<div className="rounded-lg px-3 py-6 text-center text-sm text-muted-foreground">
													No models yet. Use the refresh button to discover models or add one
													manually.
												</div>
											) : null}
											{filteredModels.length === 0 && modelFilter ? (
												<div className="rounded-lg px-3 py-6 text-center text-sm text-muted-foreground">
													No{" "}
													{MODEL_CAPABILITY_FILTERS.find(
														(filter) => filter.key === modelFilter
													)?.label.toLowerCase()}{" "}
													models found on this connection.
												</div>
											) : null}
											<div className="space-y-2">
												{filteredModels.map((model) => (
													<div
														key={model.id}
														className="flex items-center gap-3 rounded-lg px-3 py-2 transition-colors hover:bg-background"
													>
														<Checkbox
															checked={model.enabled}
															onCheckedChange={(checked) =>
																updateModel.mutate({
																	id: model.id,
																	data: { enabled: checked === true },
																})
															}
															disabled={updateModel.isPending}
														/>
														<div className="min-w-0 flex-1">
															<div className="flex items-center gap-2 text-sm font-medium">
																<span className="truncate">{modelLabel(model)}</span>
																{model.source === "MANUAL" ? (
																	<Badge variant="outline" className="text-[10px]">
																		manual
																	</Badge>
																) : null}
															</div>
															<div className="text-xs text-muted-foreground">
																{["chat", "vision", "image_gen"]
																	.filter((key) =>
																		capability(model, key as "chat" | "vision" | "image_gen")
																	)
																	.join(", ") || "No discovered capabilities"}
															</div>
														</div>
													</div>
												))}
											</div>
										</div>
									</div>

									{connection.last_status && connection.last_status !== "OK" ? (
										<p className="rounded-lg bg-amber-500/10 px-3 py-2 text-sm text-amber-600 dark:text-amber-500">
											{connection.last_error || "Could not list models."} Chat may still work; add
											model IDs manually if discovery is unavailable.
										</p>
									) : null}
								</div>
							</div>

							<DialogFooter className="shrink-0 border-t bg-popover px-6 py-4">
								<Button
									variant="secondary"
									onClick={() => verifyConnection.mutate(connection.id)}
									disabled={verifyConnection.isPending}
								>
									Test
								</Button>
								<Button
									onClick={saveConnectionSettings}
									disabled={updateConnection.isPending || !hasConnectionChanges}
								>
									Update
								</Button>
							</DialogFooter>
						</DialogContent>
					</Dialog>
					<AlertDialog>
						<AlertDialogTrigger asChild>
							<Button
								variant="ghost"
								size="icon"
								disabled={deleteConnection.isPending}
								aria-label={`Delete ${providerLabel}`}
							>
								<Trash2 className="h-4 w-4 text-destructive" />
							</Button>
						</AlertDialogTrigger>
						<AlertDialogContent>
							<AlertDialogHeader>
								<AlertDialogTitle>Delete this provider?</AlertDialogTitle>
								<AlertDialogDescription>
									<span className="font-medium text-foreground">{providerLabel}</span> and all of
									its models will be removed from this search space. This cannot be undone.
								</AlertDialogDescription>
							</AlertDialogHeader>
							<AlertDialogFooter>
								<AlertDialogCancel disabled={deleteConnection.isPending}>Cancel</AlertDialogCancel>
								<AlertDialogAction
									onClick={deleteCurrentConnection}
									disabled={deleteConnection.isPending}
									className="bg-destructive text-white hover:bg-destructive/90"
								>
									Delete
								</AlertDialogAction>
							</AlertDialogFooter>
						</AlertDialogContent>
					</AlertDialog>
				</div>
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
							<UrlSuggestionCombobox
								value={baseUrl}
								onChange={setBaseUrl}
								placeholder={
									isOllama ? "http://host.docker.internal:11434" : "https://api.example.com/v1"
								}
							/>
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
								Add
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

					{connections.length > 0 ? (
						<div className="flex flex-col gap-3">
							<Separator />
							<h3 className="text-sm font-semibold">Available Providers</h3>
							<div className="flex flex-col gap-3">
								{connections.map((connection) => (
									<ConnectionCard key={connection.id} connection={connection} />
								))}
							</div>
						</div>
					) : null}
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
