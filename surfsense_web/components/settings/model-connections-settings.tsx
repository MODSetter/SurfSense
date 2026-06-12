"use client";

import { useAtom, useAtomValue } from "jotai";
import { Dot, Trash2 } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import {
	createModelConnectionMutationAtom,
	deleteModelConnectionMutationAtom,
	previewConnectionModelsMutationAtom,
	testPreviewModelMutationAtom,
	updateModelRolesMutationAtom,
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
import { Label } from "@/components/ui/label";
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
	ModelRead,
	ModelSelection,
} from "@/contracts/types/model-connections.types";
import { ConnectionSettingsDialog } from "./model-connections/connection-settings-dialog";
import { capability, modelLabel, type SelectableModel } from "./model-connections/model-utils";
import { ProviderConnectDialog } from "./model-connections/provider-connect-dialog";
import {
	type ConnectionDraft,
	PROVIDER_ORDER,
	providerDisplay,
	providerIcon,
} from "./model-connections/provider-metadata";

function flattenModels(connections: ConnectionRead[]) {
	return connections.flatMap((connection) =>
		connection.models.map((model) => ({
			...model,
			connectionName: providerDisplay(connection.provider).name,
			connectionId: connection.id,
			provider: connection.provider,
		}))
	);
}

function ConnectionCard({ connection }: { connection: ConnectionRead }) {
	const deleteConnection = useAtomValue(deleteModelConnectionMutationAtom);

	const providerMeta = providerDisplay(connection.provider);
	const providerLabel = providerMeta.name;

	function deleteCurrentConnection() {
		deleteConnection.mutate(connection.id);
	}

	return (
		<div className="rounded-lg border border-border/60 overflow-hidden">
			<div className="flex items-center justify-between gap-3 p-4 transition-colors hover:bg-accent">
				<div className="min-w-0">
					<div className="flex items-center gap-2 font-semibold">
						{providerIcon(connection.provider)}
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
					<ConnectionSettingsDialog connection={connection} providerLabel={providerLabel} />
					<AlertDialog>
						<AlertDialogTrigger asChild>
							<Button
								variant="ghost"
								size="icon"
								className="text-muted-foreground hover:text-accent-foreground"
								disabled={deleteConnection.isPending}
								aria-label={`Delete ${providerLabel}`}
							>
								<Trash2 className="h-4 w-4" />
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
	const previewModels = useAtomValue(previewConnectionModelsMutationAtom);
	const testPreviewModel = useAtomValue(testPreviewModelMutationAtom);
	const updateRoles = useAtomValue(updateModelRolesMutationAtom);

	const [isAddProviderOpen, setIsAddProviderOpen] = useState(false);
	const [provider, setProvider] = useState("openai_compatible");
	const [connectModels, setConnectModels] = useState<ModelSelection[]>([]);
	const selectedProvider = providers.find((item) => item.provider === provider);

	const sortedProviders = [...providers].sort((left, right) => {
		const leftIndex = PROVIDER_ORDER.indexOf(left.provider);
		const rightIndex = PROVIDER_ORDER.indexOf(right.provider);
		if (leftIndex !== -1 || rightIndex !== -1) {
			return (
				(leftIndex === -1 ? Number.MAX_SAFE_INTEGER : leftIndex) -
				(rightIndex === -1 ? Number.MAX_SAFE_INTEGER : rightIndex)
			);
		}
		return providerDisplay(left.provider).name.localeCompare(providerDisplay(right.provider).name);
	});

	const allConnections = [...globalConnections, ...connections];
	const enabledModels = flattenModels(allConnections).filter((model) => model.enabled);
	const chatModels = enabledModels.filter((model) => capability(model, "chat"));
	const visionModels = enabledModels.filter((model) => capability(model, "vision"));
	const imageModels = enabledModels.filter((model) => capability(model, "image_gen"));

	function resetConnectState() {
		setConnectModels([]);
	}

	function handleConnectOpenChange(open: boolean) {
		setIsAddProviderOpen(open);
		if (!open) {
			resetConnectState();
		}
	}

	function toModelSelection(model: SelectableModel): ModelSelection {
		return {
			model_id: model.model_id,
			display_name: model.display_name,
			source: model.source || "DISCOVERED",
			supports_chat: model.supports_chat,
			max_input_tokens: model.max_input_tokens,
			supports_image_input: model.supports_image_input,
			supports_tools: model.supports_tools,
			supports_image_generation: model.supports_image_generation,
			enabled: model.enabled,
			metadata: "metadata" in model ? (model.metadata ?? {}) : (model.catalog ?? {}),
		};
	}

	function mergePreviewModels(fetchedModels: SelectableModel[]) {
		setConnectModels((current) => {
			const currentById = new Map(current.map((model) => [model.model_id, model]));
			return fetchedModels.map((model) => {
				const prior = currentById.get(model.model_id);
				return {
					...toModelSelection(model),
					enabled: prior ? prior.enabled : model.enabled,
				};
			});
		});
	}

	function connectionModelsForDraft(draft: ConnectionDraft) {
		const models = [...connectModels];
		if (draft.seedModelId && !models.some((model) => model.model_id === draft.seedModelId)) {
			models.push({
				model_id: draft.seedModelId,
				display_name: draft.seedModelId,
				source: "MANUAL",
				enabled: true,
				metadata: {},
			});
		}
		return models;
	}

	function representativeTestModel(models: ModelSelection[]) {
		const enabledModels = models.filter((model) => model.enabled);
		return enabledModels.find((model) => capability(model, "chat")) ?? enabledModels[0];
	}

	// Each provider connect form builds its own credential payload; the backend
	// resolver (`to_litellm`) forwards `extra.litellm_params` straight to LiteLLM.
	function handleCreate(draft: ConnectionDraft) {
		const models = connectionModelsForDraft(draft);
		const testModel = representativeTestModel(models);
		if (!testModel) {
			toast.error("Select at least one model before connecting");
			return;
		}

		const request = {
			provider,
			base_url: draft.base_url,
			api_key: draft.api_key,
			scope: "SEARCH_SPACE" as const,
			search_space_id: searchSpaceId,
			extra: draft.extra,
			enabled: true,
			models,
		};

		testPreviewModel.mutate(
			{ ...request, model_id: testModel.model_id },
			{
				onSuccess: (result) => {
					if (!result.ok) return;
					createConnection.mutate(request, {
						onSuccess: () => {
							setIsAddProviderOpen(false);
							resetConnectState();
						},
					});
				},
			}
		);
	}

	function openProviderDialog(providerId: string) {
		resetConnectState();
		setProvider(providerId);
		setIsAddProviderOpen(true);
		if (providerId === "vertex_ai") {
			previewModels.mutate(
				{
					provider: providerId,
					base_url: null,
					api_key: null,
					scope: "SEARCH_SPACE",
					search_space_id: searchSpaceId,
					extra: {},
					enabled: true,
					models: [],
				},
				{
					onSuccess: mergePreviewModels,
				}
			);
		}
	}

	function refreshConnectModels(draft: ConnectionDraft) {
		previewModels.mutate(
			{
				provider,
				base_url: draft.base_url,
				api_key: draft.api_key,
				scope: "SEARCH_SPACE",
				search_space_id: searchSpaceId,
				extra: draft.extra,
				enabled: true,
				models: [],
			},
			{
				onSuccess: mergePreviewModels,
			}
		);
	}

	function addConnectModel(modelId: string) {
		setConnectModels((current) => {
			if (current.some((model) => model.model_id === modelId)) return current;
			return [
				...current,
				{
					model_id: modelId,
					display_name: modelId,
					source: "MANUAL",
					enabled: true,
					metadata: {},
				},
			];
		});
	}

	function toggleConnectModel(model: SelectableModel, enabled: boolean) {
		setConnectModels((current) =>
			current.map((item) => (item.model_id === model.model_id ? { ...item, enabled } : item))
		);
	}

	function bulkToggleConnectModels(models: SelectableModel[], enabled: boolean) {
		const modelIds = new Set(models.map((model) => model.model_id));
		setConnectModels((current) =>
			current.map((item) => (modelIds.has(item.model_id) ? { ...item, enabled } : item))
		);
	}

	function renderModelOption(model: ModelRead & { connectionName: string; provider: string }) {
		return (
			<SelectItem key={model.id} value={String(model.id)}>
				<span className="inline-flex items-center gap-2">
					{providerIcon(model.provider)}
					<span className="inline-flex items-center gap-1">
						<span>{modelLabel(model)}</span>
						<Dot className="size-4 text-muted-foreground" aria-hidden="true" />
						<span>{model.connectionName}</span>
					</span>
				</span>
			</SelectItem>
		);
	}

	return (
		<div className="flex flex-col gap-6">
			<div className="flex flex-col gap-4">
				<div>
					<h3 className="text-sm font-semibold">Model Roles</h3>
					<p className="text-xs text-muted-foreground">
						Pick which enabled model powers chat, vision, and image generation for this search
						space.
					</p>
				</div>
				<div className="flex w-full max-w-2xl flex-col gap-4">
					<div className="flex flex-col gap-2">
						<Label>Chat model</Label>
						<Select
							value={String(roles?.chat_model_id ?? 0)}
							onValueChange={(value) => updateRoles.mutate({ chat_model_id: Number(value) })}
						>
							<SelectTrigger className="w-full">
								<SelectValue />
							</SelectTrigger>
							<SelectContent>
								<SelectItem value="0">Auto mode</SelectItem>
								{chatModels.map(renderModelOption)}
							</SelectContent>
						</Select>
					</div>
					<div className="flex flex-col gap-2">
						<Label>Vision model</Label>
						<Select
							value={String(roles?.vision_model_id ?? 0)}
							onValueChange={(value) => updateRoles.mutate({ vision_model_id: Number(value) })}
						>
							<SelectTrigger className="w-full">
								<SelectValue />
							</SelectTrigger>
							<SelectContent>
								<SelectItem value="0">Auto mode</SelectItem>
								{visionModels.map(renderModelOption)}
							</SelectContent>
						</Select>
					</div>
					<div className="flex flex-col gap-2">
						<Label>Image generation model</Label>
						<Select
							value={String(roles?.image_gen_model_id ?? 0)}
							onValueChange={(value) => updateRoles.mutate({ image_gen_model_id: Number(value) })}
						>
							<SelectTrigger className="w-full">
								<SelectValue />
							</SelectTrigger>
							<SelectContent>
								<SelectItem value="0">Auto mode</SelectItem>
								{imageModels.map(renderModelOption)}
							</SelectContent>
						</Select>
					</div>
				</div>
			</div>

			<Separator />

			<div className="flex flex-col gap-6">
				<div className="flex flex-col gap-3">
					<div>
						<h3 className="text-sm font-semibold">Add Provider</h3>
						<p className="text-xs text-muted-foreground">
							SurfSense supports popular providers and self-hosted model endpoints.
						</p>
					</div>
					<div className="grid gap-3 md:grid-cols-2">
						{sortedProviders.map((item) => {
							const meta = providerDisplay(item.provider);

							return (
								<Button
									key={item.provider}
									variant="ghost"
									type="button"
									className="h-auto justify-between gap-3 rounded-lg border border-border/60 p-4 text-left whitespace-normal transition-colors hover:bg-accent hover:text-accent-foreground"
									onClick={() => openProviderDialog(item.provider)}
								>
									<span className="flex min-w-0 items-center gap-3">
										{providerIcon(item.provider, "size-5")}
										<span className="min-w-0">
											<span className="block truncate text-sm font-semibold">{meta.name}</span>
											<span className="block truncate text-xs text-muted-foreground">
												{meta.subtitle}
											</span>
										</span>
									</span>
									<span className="shrink-0 text-sm font-medium text-muted-foreground">
										Connect
									</span>
								</Button>
							);
						})}
					</div>
				</div>

				<ProviderConnectDialog
					open={isAddProviderOpen}
					onOpenChange={handleConnectOpenChange}
					provider={provider}
					selectedProvider={selectedProvider}
					isPending={createConnection.isPending || testPreviewModel.isPending}
					onSubmit={handleCreate}
					previewModels={connectModels}
					isPreviewingModels={previewModels.isPending}
					onPreviewModels={refreshConnectModels}
					onAddPreviewModel={addConnectModel}
					onTogglePreviewModel={toggleConnectModel}
					onBulkTogglePreviewModels={bulkToggleConnectModels}
				/>

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
			</div>
		</div>
	);
}
