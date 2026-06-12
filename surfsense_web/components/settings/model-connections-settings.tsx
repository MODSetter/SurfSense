"use client";

import { useAtom, useAtomValue } from "jotai";
import { CheckCircle2, Trash2, XCircle } from "lucide-react";
import { useState } from "react";
import {
	addManualModelMutationAtom,
	bulkUpdateModelsMutationAtom,
	createModelConnectionMutationAtom,
	deleteModelConnectionMutationAtom,
	discoverConnectionModelsMutationAtom,
	updateModelMutationAtom,
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
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";
import { Separator } from "@/components/ui/separator";
import type { ConnectionRead, ModelRead } from "@/contracts/types/model-connections.types";
import { ConnectionSettingsDialog } from "./model-connections/connection-settings-dialog";
import { capability, modelLabel } from "./model-connections/model-utils";
import { ProviderConnectDialog } from "./model-connections/provider-connect-dialog";
import {
	type ConnectionDraft,
	PROVIDER_ORDER,
	providerDisplay,
	providerIcon,
} from "./model-connections/provider-metadata";

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
			<div className="flex items-center justify-between gap-3 p-4 transition-colors hover:bg-accent hover:text-accent-foreground">
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
					<StatusBadge connection={connection} />
					<ConnectionSettingsDialog connection={connection} providerLabel={providerLabel} />
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
	const addManualModel = useAtomValue(addManualModelMutationAtom);
	const discoverModels = useAtomValue(discoverConnectionModelsMutationAtom);
	const updateModel = useAtomValue(updateModelMutationAtom);
	const bulkUpdateModels = useAtomValue(bulkUpdateModelsMutationAtom);
	const updateRoles = useAtomValue(updateModelRolesMutationAtom);

	const [isAddProviderOpen, setIsAddProviderOpen] = useState(false);
	const [provider, setProvider] = useState("openai_compatible");
	const [connectedConnection, setConnectedConnection] = useState<ConnectionRead | null>(null);
	const [connectModels, setConnectModels] = useState<ModelRead[]>([]);
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
		setConnectedConnection(null);
		setConnectModels([]);
	}

	function handleConnectOpenChange(open: boolean) {
		setIsAddProviderOpen(open);
		if (!open) {
			resetConnectState();
		}
	}

	function replaceConnectModels(updatedModels: ModelRead[]) {
		setConnectModels((current) =>
			current.map((model) => updatedModels.find((updated) => updated.id === model.id) ?? model)
		);
	}

	// Each provider connect form builds its own credential payload; the backend
	// resolver (`to_litellm`) forwards `extra.litellm_params` straight to LiteLLM.
	function handleCreate(draft: ConnectionDraft) {
		createConnection.mutate(
			{
				provider,
				base_url: draft.base_url,
				api_key: draft.api_key,
				scope: "SEARCH_SPACE",
				search_space_id: searchSpaceId,
				extra: draft.extra,
				enabled: true,
			},
			{
				onSuccess: (created) => {
					setConnectedConnection(created);
					setConnectModels([]);
					if (draft.seedModelId) {
						addManualModel.mutate(
							{
								connectionId: created.id,
								data: { model_id: draft.seedModelId },
							},
							{
								onSuccess: (model) => setConnectModels([model]),
							}
						);
					} else {
						discoverModels.mutate(created.id, {
							onSuccess: (models) => setConnectModels(models),
						});
					}
				},
			}
		);
	}

	function openProviderDialog(providerId: string) {
		resetConnectState();
		setProvider(providerId);
		setIsAddProviderOpen(true);
	}

	function refreshConnectModels() {
		if (!connectedConnection) return;
		discoverModels.mutate(connectedConnection.id, {
			onSuccess: (models) => setConnectModels(models),
		});
	}

	function addConnectModel(modelId: string) {
		if (!connectedConnection) return;
		addManualModel.mutate(
			{ connectionId: connectedConnection.id, data: { model_id: modelId } },
			{
				onSuccess: (model) => setConnectModels((current) => [...current, model]),
			}
		);
	}

	function toggleConnectModel(model: ModelRead, enabled: boolean) {
		updateModel.mutate(
			{ id: model.id, data: { enabled } },
			{
				onSuccess: (updated) => replaceConnectModels([updated]),
			}
		);
	}

	function bulkToggleConnectModels(models: ModelRead[], enabled: boolean) {
		if (!connectedConnection) return;
		bulkUpdateModels.mutate(
			{
				connectionId: connectedConnection.id,
				data: { model_ids: models.map((model) => model.id), enabled },
			},
			{
				onSuccess: replaceConnectModels,
			}
		);
	}

	function finishConnectFlow() {
		setIsAddProviderOpen(false);
		resetConnectState();
	}

	function renderModelOption(model: ModelRead & { connectionName: string; provider: string }) {
		return (
			<SelectItem key={model.id} value={String(model.id)}>
				<span className="inline-flex items-center gap-2">
					{providerIcon(model.provider)}
					{modelLabel(model)} · {model.connectionName}
				</span>
			</SelectItem>
		);
	}

	return (
		<div className="flex flex-col gap-6">
			<div className="space-y-6">
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
					isPending={createConnection.isPending}
					onSubmit={handleCreate}
					connectedConnection={connectedConnection}
					connectModels={connectModels}
					isDiscoveringModels={discoverModels.isPending}
					isAddingManualModel={addManualModel.isPending}
					isUpdatingModel={updateModel.isPending}
					isBulkUpdatingModels={bulkUpdateModels.isPending}
					onRefreshModels={refreshConnectModels}
					onAddManualModel={addConnectModel}
					onToggleModel={toggleConnectModel}
					onBulkToggleModels={bulkToggleConnectModels}
					onDone={finishConnectFlow}
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
