import { Button } from "@/components/ui/button";
import {
	Dialog,
	DialogContent,
	DialogDescription,
	DialogFooter,
	DialogHeader,
	DialogTitle,
} from "@/components/ui/dialog";
import type {
	ConnectionRead,
	ModelProviderRead,
	ModelRead,
} from "@/contracts/types/model-connections.types";
import { AzureConnectForm } from "./azure-connect-form";
import { BedrockConnectForm } from "./bedrock-connect-form";
import { DefaultConnectForm } from "./default-connect-form";
import { ModelsSelectionPanel } from "./models-selection-panel";
import {
	type ConnectionDraft,
	type ProviderConnectFormProps,
	providerDefaultBaseUrl,
	providerDisplay,
	providerIcon,
} from "./provider-metadata";
import { VertexConnectForm } from "./vertex-connect-form";

interface ProviderConnectDialogProps {
	open: boolean;
	onOpenChange: (open: boolean) => void;
	provider: string;
	selectedProvider?: ModelProviderRead;
	isPending: boolean;
	onSubmit: (draft: ConnectionDraft) => void;
	connectedConnection?: ConnectionRead | null;
	connectModels?: ModelRead[];
	isDiscoveringModels?: boolean;
	isAddingManualModel?: boolean;
	isUpdatingModel?: boolean;
	isBulkUpdatingModels?: boolean;
	onRefreshModels?: () => void;
	onAddManualModel?: (modelId: string) => void;
	onToggleModel?: (model: ModelRead, enabled: boolean) => void;
	onBulkToggleModels?: (models: ModelRead[], enabled: boolean) => void;
	onDone?: () => void;
}

/**
 * Shared dialog shell for the "Add Provider" flow. It owns the header and routes
 * to the provider-specific connect form. Forms remount on open (Radix unmounts
 * closed content), so each gets fresh, prefilled state.
 */
export function ProviderConnectDialog({
	open,
	onOpenChange,
	provider,
	selectedProvider,
	isPending,
	onSubmit,
	connectedConnection,
	connectModels = [],
	isDiscoveringModels = false,
	isAddingManualModel = false,
	isUpdatingModel = false,
	isBulkUpdatingModels = false,
	onRefreshModels,
	onAddManualModel,
	onToggleModel,
	onBulkToggleModels,
	onDone,
}: ProviderConnectDialogProps) {
	const meta = providerDisplay(provider);
	const isModelSelectionStep = Boolean(connectedConnection);

	const formProps: ProviderConnectFormProps = {
		provider,
		defaultBaseUrl: providerDefaultBaseUrl(provider, selectedProvider?.default_base_url),
		baseUrlRequired: Boolean(selectedProvider?.base_url_required),
		isPending,
		onCancel: () => onOpenChange(false),
		onSubmit,
	};

	return (
		<Dialog open={open} onOpenChange={onOpenChange}>
			<DialogContent
				className={`flex max-h-[90vh] ${
					isModelSelectionStep ? "max-w-2xl" : "max-w-xl"
				} flex-col overflow-hidden bg-popover p-0 text-popover-foreground`}
			>
				<DialogHeader className="shrink-0 border-b px-6 py-5">
					<div className="flex items-center gap-3">
						{providerIcon(provider, "size-5")}
						<div>
							<DialogTitle>
								{isModelSelectionStep ? `Select ${meta.name} models` : `Connect ${meta.name}`}
							</DialogTitle>
							<DialogDescription>
								{isModelSelectionStep
									? selectedProvider?.discovery === "static"
										? "Choose from known model IDs or add one manually."
										: "Choose which discovered models should be available in this search space."
									: meta.subtitle}
							</DialogDescription>
						</div>
					</div>
				</DialogHeader>
				{isModelSelectionStep ? (
					<>
						<div className="min-h-0 flex-1 overflow-y-auto px-6 py-5">
							<ModelsSelectionPanel
								models={connectModels}
								description={
									selectedProvider?.discovery === "static"
										? "These are known model IDs for this provider. Select the ones to make available."
										: "Select models to make available for this provider."
								}
								emptyMessage={
									isDiscoveringModels
										? "Discovering models..."
										: "No models found. You can refresh discovery or add a model ID manually."
								}
								isRefreshing={isDiscoveringModels}
								isAddingManual={isAddingManualModel}
								isUpdatingModel={isUpdatingModel}
								isBulkUpdating={isBulkUpdatingModels}
								refreshLabel={`Refresh ${meta.name} models`}
								onRefresh={onRefreshModels}
								onAddManual={onAddManualModel}
								onToggleModel={onToggleModel}
								onBulkToggle={onBulkToggleModels}
							/>
						</div>
						<DialogFooter className="shrink-0 border-t bg-popover px-6 py-4">
							<Button onClick={onDone}>Done</Button>
						</DialogFooter>
					</>
				) : (
					<div className="overflow-y-auto px-6 py-5">
						{provider === "azure" ? (
							<AzureConnectForm {...formProps} />
						) : provider === "bedrock" ? (
							<BedrockConnectForm {...formProps} />
						) : provider === "vertex_ai" ? (
							<VertexConnectForm {...formProps} />
						) : (
							<DefaultConnectForm {...formProps} />
						)}
					</div>
				)}
			</DialogContent>
		</Dialog>
	);
}
