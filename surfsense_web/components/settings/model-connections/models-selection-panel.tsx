import { RefreshCw } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Spinner } from "@/components/ui/spinner";
import {
	capability,
	capabilityLabels,
	MODEL_CAPABILITY_FILTERS,
	type ModelCapabilityFilter,
	modelLabel,
	reportedContextLength,
	type SelectableModel,
} from "./model-utils";

interface ModelsSelectionPanelProps {
	models: SelectableModel[];
	description?: string;
	emptyMessage?: string;
	refreshLabel?: string;
	isRefreshing?: boolean;
	isRefreshDisabled?: boolean;
	isUpdatingModel?: boolean;
	isBulkUpdating?: boolean;
	onRefresh?: () => void;
	onToggleModel?: (model: SelectableModel, enabled: boolean) => void;
	onBulkToggle?: (models: SelectableModel[], enabled: boolean) => void;
	onMaxInputTokensChange?: (model: SelectableModel, value: number | null) => void;
}

export function ModelsSelectionPanel({
	models,
	description = "Select models to make available for this provider.",
	emptyMessage = "No models available.",
	refreshLabel = "Refresh models",
	isRefreshing = false,
	isRefreshDisabled = false,
	isUpdatingModel = false,
	isBulkUpdating = false,
	onRefresh,
	onToggleModel,
	onBulkToggle,
	onMaxInputTokensChange,
}: ModelsSelectionPanelProps) {
	const [modelFilter, setModelFilter] = useState<ModelCapabilityFilter | null>(null);

	const filteredModels = modelFilter
		? models.filter((model) => capability(model, modelFilter))
		: models;
	const allFilteredModelsEnabled =
		filteredModels.length > 0 && filteredModels.every((model) => model.enabled);

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
							disabled={isRefreshing || isRefreshDisabled}
							aria-label={refreshLabel}
						>
							<RefreshCw className={`h-4 w-4 ${isRefreshing ? "animate-spin" : ""}`} />
						</Button>
					) : null}
				</div>
			</div>

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
								className={`h-7 rounded-full px-3 text-xs ${
									isActive ? "bg-brand text-white hover:bg-brand/90" : "opacity-80"
								}`}
								onClick={() => setModelFilter(isActive ? null : filter.key)}
							>
								{filter.label}
								<span className={`ml-1 ${isActive ? "text-white/80" : "text-muted-foreground"}`}>
									{count}
								</span>
							</Button>
						);
					})}
				</div>
			) : null}

			<div
				className={`overflow-y-auto rounded-xl border bg-muted/20 p-2 ${
					models.length === 0 ? "h-auto border-dashed border-border/100" : "h-80"
				}`}
			>
				{models.length === 0 ? (
					<div className="flex flex-col items-center gap-3 rounded-lg px-3 py-6 text-center text-sm text-muted-foreground">
						{emptyMessage}
						{onRefresh ? (
							<Button
								variant="secondary"
								size="sm"
								type="button"
								onClick={onRefresh}
								disabled={isRefreshing || isRefreshDisabled}
								className="relative"
							>
								<span className={isRefreshing ? "opacity-0" : ""}>Reload models</span>
								{isRefreshing ? <Spinner size="sm" className="absolute" /> : null}
							</Button>
						) : null}
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
					{filteredModels.map((model) => {
						const reportedContext = reportedContextLength(model);

						return (
							<div
								key={model.id ?? model.model_id}
								className="flex flex-col gap-2 rounded-lg px-3 py-2 transition-colors hover:bg-popover sm:flex-row sm:items-center sm:gap-3"
							>
								<div className="flex min-w-0 flex-1 items-center gap-3">
									<Checkbox
										checked={model.enabled}
										onCheckedChange={(checked) => onToggleModel?.(model, checked === true)}
										disabled={!onToggleModel || isUpdatingModel}
										className="border-muted-foreground/20"
									/>
									<div className="min-w-0 flex-1">
										<div className="truncate text-sm font-medium" title={modelLabel(model)}>
											{modelLabel(model)}
										</div>
										<div className="text-xs text-muted-foreground">
											{capabilityLabels(model) || "No discovered capabilities"}
										</div>
									</div>
								</div>
								{onMaxInputTokensChange ? (
									// Stacked below sm, so indent by the checkbox column to stay
									// aligned under the model name.
									<div className="flex shrink-0 items-center gap-2 pl-7 sm:pl-0">
										<Label
											htmlFor={`model-context-${model.id ?? model.model_id}`}
											className="sr-only"
										>
											Max input tokens for {modelLabel(model)}
										</Label>
										<Input
											id={`model-context-${model.id ?? model.model_id}`}
											type="number"
											inputMode="numeric"
											min={1}
											step={1024}
											placeholder="Auto"
											value={model.max_input_tokens ?? ""}
											onChange={(event) => {
												const value = event.target.valueAsNumber;
												onMaxInputTokensChange(
													model,
													Number.isFinite(value) && value > 0 ? value : null
												);
											}}
											className="h-9 w-24 text-right text-xs tabular-nums sm:h-8 sm:w-28"
											aria-describedby={`model-context-unit-${model.id ?? model.model_id}`}
										/>
										<span
											id={`model-context-unit-${model.id ?? model.model_id}`}
											className="text-xs text-muted-foreground sm:w-32"
										>
											{reportedContext ? `of ${reportedContext.toLocaleString()} tokens` : "tokens"}
										</span>
									</div>
								) : null}
							</div>
						);
					})}
				</div>
			</div>
		</div>
	);
}
