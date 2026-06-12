import { RefreshCw } from "lucide-react";
import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import {
	capability,
	capabilityLabels,
	MODEL_CAPABILITY_FILTERS,
	type ModelCapabilityFilter,
	modelLabel,
	type SelectableModel,
} from "./model-utils";

interface ModelsSelectionPanelProps {
	models: SelectableModel[];
	description?: string;
	emptyMessage?: string;
	manualInputPlaceholder?: string;
	refreshLabel?: string;
	isRefreshing?: boolean;
	isAddingManual?: boolean;
	isUpdatingModel?: boolean;
	isBulkUpdating?: boolean;
	onRefresh?: () => void;
	onAddManual?: (modelId: string) => void;
	onToggleModel?: (model: SelectableModel, enabled: boolean) => void;
	onBulkToggle?: (models: SelectableModel[], enabled: boolean) => void;
}

export function ModelsSelectionPanel({
	models,
	description = "Select models to make available for this provider.",
	emptyMessage = "No models available.",
	manualInputPlaceholder = "Add a model ID manually",
	refreshLabel = "Refresh models",
	isRefreshing = false,
	isAddingManual = false,
	isUpdatingModel = false,
	isBulkUpdating = false,
	onRefresh,
	onAddManual,
	onToggleModel,
	onBulkToggle,
}: ModelsSelectionPanelProps) {
	const [manualModelId, setManualModelId] = useState("");
	const [modelFilter, setModelFilter] = useState<ModelCapabilityFilter | null>(null);

	const filteredModels = modelFilter
		? models.filter((model) => capability(model, modelFilter))
		: models;
	const allFilteredModelsEnabled =
		filteredModels.length > 0 && filteredModels.every((model) => model.enabled);

	function addModel() {
		const modelId = manualModelId.trim();
		if (!modelId || !onAddManual) return;
		onAddManual(modelId);
		setManualModelId("");
	}

	function toggleFilteredModels() {
		const nextEnabled = !allFilteredModelsEnabled;
		const changedModels = filteredModels.filter((model) => model.enabled !== nextEnabled);
		if (changedModels.length === 0) return;
		onBulkToggle?.(changedModels, nextEnabled);
	}

	return (
		<div className="space-y-3">
			<div className="flex flex-wrap items-start justify-between gap-3">
				<div>
					<div className="font-semibold">Models</div>
					<p className="text-sm text-muted-foreground">{description}</p>
				</div>
				<div className="flex flex-wrap items-center gap-2">
					<Button
						variant="ghost"
						size="sm"
						type="button"
						onClick={toggleFilteredModels}
						disabled={!onBulkToggle || isBulkUpdating || filteredModels.length === 0}
					>
						{allFilteredModelsEnabled ? "Deselect All" : "Select All"}
					</Button>
					{onRefresh ? (
						<Button
							variant="ghost"
							size="icon"
							type="button"
							onClick={onRefresh}
							disabled={isRefreshing}
							aria-label={refreshLabel}
						>
							<RefreshCw className={`h-4 w-4 ${isRefreshing ? "animate-spin" : ""}`} />
						</Button>
					) : null}
				</div>
			</div>

			{onAddManual ? (
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
						placeholder={manualInputPlaceholder}
					/>
					<Button
						size="sm"
						type="button"
						onClick={addModel}
						disabled={isAddingManual || !manualModelId.trim()}
					>
						Add model
					</Button>
				</div>
			) : null}

			{models.length > 0 ? (
				<div className="flex flex-wrap items-center gap-2">
					<span className="text-xs font-medium text-muted-foreground">Filter models</span>
					{MODEL_CAPABILITY_FILTERS.map((filter) => {
						const count = models.filter((model) => capability(model, filter.key)).length;
						const isActive = modelFilter === filter.key;

						return (
							<Button
								key={filter.key}
								type="button"
								variant="secondary"
								size="sm"
								className={`h-7 rounded-full px-3 text-xs ${isActive ? "" : "opacity-80"}`}
								onClick={() => setModelFilter(isActive ? null : filter.key)}
							>
								{filter.label}
								<span className="ml-1 text-muted-foreground">{count}</span>
							</Button>
						);
					})}
				</div>
			) : null}

			<div className="h-80 overflow-y-auto rounded-xl border bg-muted/20 p-2">
				{models.length === 0 ? (
					<div className="rounded-lg px-3 py-6 text-center text-sm text-muted-foreground">
						{emptyMessage}
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
							key={model.id ?? model.model_id}
							className="flex items-center gap-3 rounded-lg px-3 py-2 transition-colors hover:bg-background"
						>
							<Checkbox
								checked={model.enabled}
								onCheckedChange={(checked) => onToggleModel?.(model, checked === true)}
								disabled={!onToggleModel || isUpdatingModel}
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
									{capabilityLabels(model) || "No discovered capabilities"}
								</div>
							</div>
						</div>
					))}
				</div>
			</div>
		</div>
	);
}
