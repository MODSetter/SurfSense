import { useAtomValue } from "jotai";
import { Eye, EyeOff, Settings } from "lucide-react";
import { useState } from "react";
import {
	addManualModelMutationAtom,
	bulkUpdateModelsMutationAtom,
	discoverConnectionModelsMutationAtom,
	updateModelConnectionMutationAtom,
	updateModelMutationAtom,
	verifyModelConnectionMutationAtom,
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
import type {
	ConnectionRead,
	ConnectionUpdateRequest,
} from "@/contracts/types/model-connections.types";
import type { SelectableModel } from "./model-utils";
import { ModelsSelectionPanel } from "./models-selection-panel";
import { providerIcon } from "./provider-metadata";

interface ConnectionSettingsDialogProps {
	connection: ConnectionRead;
	providerLabel: string;
}

export function ConnectionSettingsDialog({
	connection,
	providerLabel,
}: ConnectionSettingsDialogProps) {
	const verifyConnection = useAtomValue(verifyModelConnectionMutationAtom);
	const discoverModels = useAtomValue(discoverConnectionModelsMutationAtom);
	const updateConnection = useAtomValue(updateModelConnectionMutationAtom);
	const addManualModel = useAtomValue(addManualModelMutationAtom);
	const updateModel = useAtomValue(updateModelMutationAtom);
	const bulkUpdateModels = useAtomValue(bulkUpdateModelsMutationAtom);

	const allowlist = Array.isArray(connection.extra?.model_ids)
		? (connection.extra.model_ids as string[])
		: [];
	const [isOpen, setIsOpen] = useState(false);
	const [baseUrlDraft, setBaseUrlDraft] = useState(connection.base_url ?? "");
	const [apiKeyDraft, setApiKeyDraft] = useState("");
	const [showApiKey, setShowApiKey] = useState(false);
	const [allowlistText, setAllowlistText] = useState(allowlist.join(", "));

	const isLocal =
		connection.provider === "ollama_chat" ||
		connection.provider === "lm_studio" ||
		!connection.base_url?.startsWith("https");
	const hasConnectionChanges =
		baseUrlDraft.trim() !== (connection.base_url ?? "") ||
		apiKeyDraft.trim() !== (connection.api_key ?? "");

	function handleOpenChange(open: boolean) {
		setIsOpen(open);
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

	function handleToggleModel(model: SelectableModel, enabled: boolean) {
		if (typeof model.id !== "number") return;
		updateModel.mutate({
			id: model.id,
			data: { enabled },
		});
	}

	function handleBulkToggle(models: SelectableModel[], enabled: boolean) {
		const modelIds = models
			.map((model) => model.id)
			.filter((id): id is number => typeof id === "number");
		if (modelIds.length === 0) return;
		bulkUpdateModels.mutate({
			connectionId: connection.id,
			data: { model_ids: modelIds, enabled },
		});
	}

	return (
		<Dialog open={isOpen} onOpenChange={handleOpenChange}>
			<DialogTrigger asChild>
				<Button variant="ghost" size="icon" aria-label={`Configure ${providerLabel}`}>
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

						{!isLocal ? (
							<div className="space-y-2">
								<Label className="text-xs">Model IDs filter (optional)</Label>
								<div className="flex gap-2">
									<Input
										value={allowlistText}
										onChange={(event) => setAllowlistText(event.target.value)}
										placeholder="Comma-separated, e.g. anthropic/claude-sonnet-4-5, google/gemini-2.5-pro"
									/>
									<Button size="sm" onClick={saveAllowlist} disabled={updateConnection.isPending}>
										Save filter
									</Button>
								</div>
								<p className="text-xs text-muted-foreground">
									Leave empty to discover all models. Recommended for providers with large catalogs.
								</p>
							</div>
						) : null}

						<Separator className="bg-muted-foreground/20" />

						<ModelsSelectionPanel
							models={connection.models}
							isRefreshing={discoverModels.isPending}
							isAddingManual={addManualModel.isPending}
							isUpdatingModel={updateModel.isPending}
							isBulkUpdating={bulkUpdateModels.isPending}
							refreshLabel={`Refresh ${providerLabel} models`}
							onRefresh={() => discoverModels.mutate(connection.id)}
							onAddManual={(modelId) =>
								addManualModel.mutate({
									connectionId: connection.id,
									data: { model_id: modelId },
								})
							}
							onToggleModel={handleToggleModel}
							onBulkToggle={handleBulkToggle}
						/>

						{connection.last_status && connection.last_status !== "OK" ? (
							<p className="rounded-lg bg-amber-500/10 px-3 py-2 text-sm text-amber-600 dark:text-amber-500">
								{connection.last_error || "Could not list models."} Chat may still work; add model
								IDs manually if discovery is unavailable.
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
	);
}
