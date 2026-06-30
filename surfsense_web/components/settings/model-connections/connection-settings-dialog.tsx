import { useAtomValue } from "jotai";
import { Eye, EyeOff, Settings } from "lucide-react";
import { useMemo, useState } from "react";
import {
	bulkUpdateModelsMutationAtom,
	discoverConnectionModelsMutationAtom,
	testPreviewModelMutationAtom,
	updateModelConnectionMutationAtom,
} from "@/atoms/model-connections/model-connections-mutation.atoms";
import { Button } from "@/components/ui/button";
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
import { Separator } from "@/components/ui/separator";
import { Spinner } from "@/components/ui/spinner";
import type {
	ConnectionRead,
	ConnectionUpdateRequest,
} from "@/contracts/types/model-connections.types";
import { capability, type SelectableModel } from "./model-utils";
import { ModelsSelectionPanel } from "./models-selection-panel";
import { providerIcon } from "./provider-metadata";

interface ConnectionSettingsDialogProps {
	connection: ConnectionRead;
	providerLabel: string;
}

function enabledModelIds(models: SelectableModel[]) {
	return new Set(
		models
			.filter((model) => typeof model.id === "number" && model.enabled)
			.map((model) => Number(model.id))
	);
}

export function ConnectionSettingsDialog({
	connection,
	providerLabel,
}: ConnectionSettingsDialogProps) {
	const discoverModels = useAtomValue(discoverConnectionModelsMutationAtom);
	const testPreviewModel = useAtomValue(testPreviewModelMutationAtom);
	const updateConnection = useAtomValue(updateModelConnectionMutationAtom);
	const bulkUpdateModels = useAtomValue(bulkUpdateModelsMutationAtom);

	const [isOpen, setIsOpen] = useState(false);
	const [baseUrlDraft, setBaseUrlDraft] = useState(connection.base_url ?? "");
	const [apiKeyDraft, setApiKeyDraft] = useState("");
	const [showApiKey, setShowApiKey] = useState(false);
	const [isSavingConnectionSettings, setIsSavingConnectionSettings] = useState(false);
	const [draftEnabledModelIds, setDraftEnabledModelIds] = useState(() =>
		enabledModelIds(connection.models)
	);

	const hasConnectionChanges =
		baseUrlDraft.trim() !== (connection.base_url ?? "") ||
		apiKeyDraft.trim() !== (connection.api_key ?? "");
	const draftModels = useMemo(
		() =>
			connection.models.map((model) =>
				typeof model.id === "number"
					? { ...model, enabled: draftEnabledModelIds.has(model.id) }
					: model
			),
		[connection.models, draftEnabledModelIds]
	);
	const hasModelChanges = connection.models.some(
		(model) => typeof model.id === "number" && draftEnabledModelIds.has(model.id) !== model.enabled
	);
	const canUpdate = hasConnectionChanges || hasModelChanges;

	function handleOpenChange(open: boolean) {
		setIsOpen(open);
		if (open) {
			setBaseUrlDraft(connection.base_url ?? "");
			setApiKeyDraft(connection.api_key ?? "");
			setShowApiKey(false);
			setIsSavingConnectionSettings(false);
			setDraftEnabledModelIds(enabledModelIds(connection.models));
		}
	}

	async function saveModelChanges() {
		const toEnable = connection.models
			.filter((model) => typeof model.id === "number" && draftEnabledModelIds.has(model.id))
			.filter((model) => !model.enabled)
			.map((model) => Number(model.id));
		const toDisable = connection.models
			.filter((model) => typeof model.id === "number" && !draftEnabledModelIds.has(model.id))
			.filter((model) => model.enabled)
			.map((model) => Number(model.id));

		if (toEnable.length > 0) {
			await bulkUpdateModels.mutateAsync({
				connectionId: connection.id,
				data: { model_ids: toEnable, enabled: true },
			});
		}
		if (toDisable.length > 0) {
			await bulkUpdateModels.mutateAsync({
				connectionId: connection.id,
				data: { model_ids: toDisable, enabled: false },
			});
		}
	}

	async function saveConnectionSettings() {
		if (isSavingConnectionSettings) return;

		const data: ConnectionUpdateRequest = {
			base_url: baseUrlDraft.trim() || null,
		};

		if (apiKeyDraft.trim() !== (connection.api_key ?? "")) {
			data.api_key = apiKeyDraft.trim() || null;
		}
		const apiKeyForTest = Object.hasOwn(data, "api_key")
			? (data.api_key ?? null)
			: (connection.api_key ?? null);

		const enabledModels = draftModels.filter((model) => model.enabled);
		const testModel = enabledModels.find((model) => capability(model, "chat")) ?? enabledModels[0];
		setIsSavingConnectionSettings(true);
		try {
			if (hasConnectionChanges) {
				if (testModel) {
					const result = await testPreviewModel.mutateAsync({
						provider: connection.provider,
						base_url: data.base_url,
						api_key: apiKeyForTest,
						scope: "SEARCH_SPACE",
						search_space_id: connection.search_space_id,
						extra: connection.extra ?? {},
						enabled: connection.enabled,
						models: [],
						model_id: testModel.model_id,
					});
					if (!result.ok) return;
				}
				await updateConnection.mutateAsync({ id: connection.id, data });
				setApiKeyDraft("");
			}

			if (hasModelChanges) {
				await saveModelChanges();
			}
		} finally {
			setIsSavingConnectionSettings(false);
		}
	}

	function handleToggleModel(model: SelectableModel, enabled: boolean) {
		if (typeof model.id !== "number") return;
		const modelId = model.id;
		setDraftEnabledModelIds((current) => {
			const next = new Set(current);
			if (enabled) {
				next.add(modelId);
			} else {
				next.delete(modelId);
			}
			return next;
		});
	}

	function handleBulkToggle(models: SelectableModel[], enabled: boolean) {
		const modelIds = models
			.map((model) => model.id)
			.filter((id): id is number => typeof id === "number");
		if (modelIds.length === 0) return;
		setDraftEnabledModelIds((current) => {
			const next = new Set(current);
			for (const id of modelIds) {
				if (enabled) {
					next.add(id);
				} else {
					next.delete(id);
				}
			}
			return next;
		});
	}

	return (
		<Dialog open={isOpen} onOpenChange={handleOpenChange}>
			<DialogTrigger asChild>
				<Button
					variant="ghost"
					size="icon"
					className="text-muted-foreground hover:text-accent-foreground"
					aria-label={`Configure ${providerLabel}`}
				>
					<Settings className="h-4 w-4" />
				</Button>
			</DialogTrigger>
			<DialogContent className="flex max-h-[90vh] max-w-3xl flex-col overflow-hidden bg-popover p-0 text-popover-foreground">
				<DialogHeader className="shrink-0 border-b px-6 py-5">
					<div className="flex items-center gap-3">
						{providerIcon(connection.provider, "size-5")}
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
							<Input
								value={baseUrlDraft}
								onChange={(event) => setBaseUrlDraft(event.target.value)}
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

						<Separator className="bg-muted-foreground/20" />

						<ModelsSelectionPanel
							models={draftModels}
							isRefreshing={discoverModels.isPending}
							isUpdatingModel={isSavingConnectionSettings}
							isBulkUpdating={isSavingConnectionSettings || bulkUpdateModels.isPending}
							refreshLabel={`Refresh ${providerLabel} models`}
							onRefresh={() => discoverModels.mutate(connection.id)}
							onToggleModel={handleToggleModel}
							onBulkToggle={handleBulkToggle}
						/>
					</div>
				</div>

				<DialogFooter className="shrink-0 border-t bg-popover px-6 py-4">
					<Button
						onClick={saveConnectionSettings}
						disabled={isSavingConnectionSettings || !canUpdate}
						className="relative min-w-[96px]"
					>
						<span className={isSavingConnectionSettings ? "opacity-0" : ""}>Update</span>
						{isSavingConnectionSettings ? <Spinner size="sm" className="absolute" /> : null}
					</Button>
				</DialogFooter>
			</DialogContent>
		</Dialog>
	);
}
