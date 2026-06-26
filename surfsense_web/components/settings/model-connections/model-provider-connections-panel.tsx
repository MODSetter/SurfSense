"use client";

import { useAtomValue } from "jotai";
import { type ReactNode, useState } from "react";
import { toast } from "sonner";
import {
	createModelConnectionMutationAtom,
	previewConnectionModelsMutationAtom,
	testPreviewModelMutationAtom,
} from "@/atoms/model-connections/model-connections-mutation.atoms";
import { modelProvidersAtom } from "@/atoms/model-connections/model-connections-query.atoms";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import type { ConnectionRead, ModelSelection } from "@/contracts/types/model-connections.types";
import { ConnectionCard } from "./connection-card";
import { capability, type SelectableModel } from "./model-utils";
import { ProviderConnectDialog } from "./provider-connect-dialog";
import {
	type ConnectionDraft,
	PROVIDER_ORDER,
	providerDisplay,
	providerIcon,
} from "./provider-metadata";

interface ModelProviderConnectionsPanelProps {
	searchSpaceId: number;
	connections: ConnectionRead[];
	className?: string;
	addProviderTitle?: string;
	addProviderDescription?: string;
	availableProvidersTitle?: string;
	footerAction?: ReactNode;
	showAddProviderHeader?: boolean;
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

export function ModelProviderConnectionsPanel({
	searchSpaceId,
	connections,
	className,
	addProviderTitle = "Add Provider",
	addProviderDescription = "SurfSense supports popular providers and self-hosted model endpoints.",
	availableProvidersTitle = "Available Providers",
	footerAction,
	showAddProviderHeader = true,
}: ModelProviderConnectionsPanelProps) {
	const { data: providers = [] } = useAtomValue(modelProvidersAtom);
	const createConnection = useAtomValue(createModelConnectionMutationAtom);
	const previewModels = useAtomValue(previewConnectionModelsMutationAtom);
	const testPreviewModel = useAtomValue(testPreviewModelMutationAtom);

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

	function resetConnectState() {
		setConnectModels([]);
	}

	function handleConnectOpenChange(open: boolean) {
		setIsAddProviderOpen(open);
		if (!open) {
			resetConnectState();
		}
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

	return (
		<div className={className ?? "flex flex-col gap-6"}>
			<div className="flex flex-col gap-3">
				{showAddProviderHeader ? (
					<div>
						<h3 className="text-base font-semibold">{addProviderTitle}</h3>
						<p className="text-sm text-muted-foreground">{addProviderDescription}</p>
					</div>
				) : null}
				<div className="grid gap-3 md:grid-cols-2">
					{sortedProviders.map((item) => {
						const meta = providerDisplay(item.provider);

						return (
							<Button
								key={item.provider}
								variant="ghost"
								type="button"
								className="h-auto justify-between gap-3 whitespace-normal rounded-lg border border-border/60 p-4 text-left transition-colors hover:bg-accent hover:text-accent-foreground"
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
								<span className="shrink-0 text-sm font-medium text-muted-foreground">Connect</span>
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
				onTogglePreviewModel={toggleConnectModel}
				onBulkTogglePreviewModels={bulkToggleConnectModels}
			/>

			{connections.length > 0 ? (
				<div className="flex flex-col gap-3">
					<Separator />
					<h3 className="text-base font-semibold">{availableProvidersTitle}</h3>
					<div className="flex flex-col gap-3">
						{connections.map((connection) => (
							<ConnectionCard key={connection.id} connection={connection} />
						))}
					</div>
				</div>
			) : null}
			{footerAction ? <div className="flex justify-center pt-2">{footerAction}</div> : null}
		</div>
	);
}
