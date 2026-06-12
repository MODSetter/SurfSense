import { useCallback, useState } from "react";
import {
	Dialog,
	DialogContent,
	DialogDescription,
	DialogHeader,
	DialogTitle,
} from "@/components/ui/dialog";
import { Separator } from "@/components/ui/separator";
import type { ModelProviderRead } from "@/contracts/types/model-connections.types";
import { AzureConnectForm } from "./azure-connect-form";
import { BedrockConnectForm } from "./bedrock-connect-form";
import { ConnectFormFooter } from "./connect-fields";
import { DefaultConnectForm } from "./default-connect-form";
import type { SelectableModel } from "./model-utils";
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
	previewModels?: SelectableModel[];
	isPreviewingModels?: boolean;
	onPreviewModels?: (draft: ConnectionDraft) => void;
	onAddPreviewModel?: (modelId: string) => void;
	onTogglePreviewModel?: (model: SelectableModel, enabled: boolean) => void;
	onBulkTogglePreviewModels?: (models: SelectableModel[], enabled: boolean) => void;
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
	previewModels = [],
	isPreviewingModels = false,
	onPreviewModels,
	onAddPreviewModel,
	onTogglePreviewModel,
	onBulkTogglePreviewModels,
}: ProviderConnectDialogProps) {
	const meta = providerDisplay(provider);
	const isAzure = provider === "azure";
	const isBedrock = provider === "bedrock";
	const isVertex = provider === "vertex_ai";
	const [currentDraft, setCurrentDraft] = useState<ConnectionDraft>({
		base_url: null,
		api_key: null,
		extra: {},
	});
	const [canSubmit, setCanSubmit] = useState(false);

	const handleDraftChange = useCallback((draft: ConnectionDraft, nextCanSubmit: boolean) => {
		setCurrentDraft(draft);
		setCanSubmit(nextCanSubmit);
	}, []);

	const formProps: ProviderConnectFormProps = {
		provider,
		defaultBaseUrl: providerDefaultBaseUrl(provider, selectedProvider?.default_base_url),
		baseUrlRequired: Boolean(selectedProvider?.base_url_required),
		onDraftChange: handleDraftChange,
	};

	const modelDescription = (() => {
		if (isAzure) {
			return "Select the models to enable for Azure OpenAI";
		}
		if (isBedrock) {
			return "Select the models to enable for Amazon Bedrock";
		}
		if (isVertex) {
			return "Select the models to enable for Gemini";
		}
		return "Select the models to enable for this provider";
	})();

	const canRefreshModels = !isAzure && !isVertex && (!isBedrock || canSubmit);

	return (
		<Dialog open={open} onOpenChange={onOpenChange}>
			<DialogContent className="flex h-[85vh] max-h-[760px] min-h-[640px] max-w-2xl flex-col overflow-hidden bg-popover p-0 text-popover-foreground">
				<DialogHeader className="shrink-0 border-b px-6 py-5">
					<div className="flex items-center gap-3">
						{providerIcon(provider, "size-5")}
						<div>
							<DialogTitle>Connect {meta.name}</DialogTitle>
							<DialogDescription>{meta.subtitle}</DialogDescription>
						</div>
					</div>
				</DialogHeader>
				<div className="min-h-0 flex-1 space-y-5 overflow-y-auto px-6 py-5">
					{provider === "azure" ? (
						<AzureConnectForm {...formProps} />
					) : provider === "bedrock" ? (
						<BedrockConnectForm {...formProps} />
					) : provider === "vertex_ai" ? (
						<VertexConnectForm {...formProps} />
					) : (
						<DefaultConnectForm {...formProps} />
					)}

					<Separator className="bg-muted-foreground/20" />

					<ModelsSelectionPanel
						models={previewModels}
						description={modelDescription}
						isRefreshing={isPreviewingModels}
						refreshLabel={`Refresh ${meta.name} models`}
						onRefresh={canRefreshModels ? () => onPreviewModels?.(currentDraft) : undefined}
						onAddManual={onAddPreviewModel}
						onToggleModel={onTogglePreviewModel}
						onBulkToggle={onBulkTogglePreviewModels}
					/>
				</div>
				<ConnectFormFooter
					onCancel={() => onOpenChange(false)}
					onSubmit={() => onSubmit(currentDraft)}
					canSubmit={canSubmit}
					isPending={isPending}
				/>
			</DialogContent>
		</Dialog>
	);
}
