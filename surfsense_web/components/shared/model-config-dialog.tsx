"use client";

import { useAtomValue } from "jotai";
import { AlertCircle, Zap } from "lucide-react";
import { useCallback, useRef, useState } from "react";
import { toast } from "sonner";
import {
	createNewLLMConfigMutationAtom,
	updateLLMPreferencesMutationAtom,
	updateNewLLMConfigMutationAtom,
} from "@/atoms/new-llm-config/new-llm-config-mutation.atoms";
import { LLMConfigForm, type LLMConfigFormData } from "@/components/shared/llm-config-form";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { Spinner } from "@/components/ui/spinner";
import type {
	GlobalNewLLMConfig,
	LiteLLMProvider,
	NewLLMConfigPublic,
} from "@/contracts/types/new-llm-config.types";

interface ModelConfigDialogProps {
	open: boolean;
	onOpenChange: (open: boolean) => void;
	config: NewLLMConfigPublic | GlobalNewLLMConfig | null;
	isGlobal: boolean;
	searchSpaceId: number;
	mode: "create" | "edit" | "view";
}

export function ModelConfigDialog({
	open,
	onOpenChange,
	config,
	isGlobal,
	searchSpaceId,
	mode,
}: ModelConfigDialogProps) {
	const [isSubmitting, setIsSubmitting] = useState(false);
	const [scrollPos, setScrollPos] = useState<"top" | "middle" | "bottom">("top");
	const scrollRef = useRef<HTMLDivElement>(null);

	const handleScroll = useCallback((e: React.UIEvent<HTMLDivElement>) => {
		const el = e.currentTarget;
		const atTop = el.scrollTop <= 2;
		const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight <= 2;
		setScrollPos(atTop ? "top" : atBottom ? "bottom" : "middle");
	}, []);

	const { mutateAsync: createConfig } = useAtomValue(createNewLLMConfigMutationAtom);
	const { mutateAsync: updateConfig } = useAtomValue(updateNewLLMConfigMutationAtom);
	const { mutateAsync: updatePreferences } = useAtomValue(updateLLMPreferencesMutationAtom);

	const isAutoMode = config && "is_auto_mode" in config && config.is_auto_mode;

	const getTitle = () => {
		if (mode === "create") return "Add New Configuration";
		if (isAutoMode) return "Auto Mode (Fastest)";
		if (isGlobal) return "View Global Configuration";
		return "Edit Configuration";
	};

	const getSubtitle = () => {
		if (mode === "create") return "Set up a new LLM provider for this search space";
		if (isAutoMode) return "Automatically routes requests across providers";
		if (isGlobal) return "Read-only global configuration";
		return "Update your configuration settings";
	};

	const handleSubmit = useCallback(
		async (data: LLMConfigFormData) => {
			setIsSubmitting(true);
			try {
				if (mode === "create") {
					const result = await createConfig({
						...data,
						search_space_id: searchSpaceId,
					});

					if (result?.id) {
						await updatePreferences({
							search_space_id: searchSpaceId,
							data: {
								agent_llm_id: result.id,
							},
						});
					}

					onOpenChange(false);
				} else if (!isGlobal && config) {
					await updateConfig({
						id: config.id,
						data: {
							name: data.name,
							description: data.description,
							provider: data.provider,
							custom_provider: data.custom_provider,
							model_name: data.model_name,
							api_key: data.api_key,
							api_base: data.api_base,
							litellm_params: data.litellm_params,
							system_instructions: data.system_instructions,
							use_default_system_instructions: data.use_default_system_instructions,
							citations_enabled: data.citations_enabled,
						},
					});
					onOpenChange(false);
				}
			} catch (error) {
				console.error("Failed to save configuration:", error);
			} finally {
				setIsSubmitting(false);
			}
		},
		[
			mode,
			isGlobal,
			config,
			searchSpaceId,
			createConfig,
			updateConfig,
			updatePreferences,
			onOpenChange,
		]
	);

	const handleUseGlobalConfig = useCallback(async () => {
		if (!config || !isGlobal) return;
		setIsSubmitting(true);
		try {
			await updatePreferences({
				search_space_id: searchSpaceId,
				data: {
					agent_llm_id: config.id,
				},
			});
			toast.success(`Now using ${config.name}`);
			onOpenChange(false);
		} catch (error) {
			console.error("Failed to set model:", error);
		} finally {
			setIsSubmitting(false);
		}
	}, [config, isGlobal, searchSpaceId, updatePreferences, onOpenChange]);

	return (
		<Dialog open={open} onOpenChange={onOpenChange}>
			<DialogContent
				className="max-w-lg h-[85vh] flex flex-col p-0 gap-0 overflow-hidden"
				onOpenAutoFocus={(e) => e.preventDefault()}
			>
				<DialogTitle className="sr-only">{getTitle()}</DialogTitle>

				{/* Header */}
				<div className="flex items-start justify-between px-6 pt-6 pb-4 pr-14">
					<div className="space-y-1">
						<div className="flex items-center gap-2">
							<h2 className="text-lg font-semibold tracking-tight">{getTitle()}</h2>
							{isAutoMode && (
								<Badge variant="secondary" className="text-[10px]">
									Recommended
								</Badge>
							)}
							{isGlobal && !isAutoMode && mode !== "create" && (
								<Badge variant="secondary" className="text-[10px]">
									Global
								</Badge>
							)}
							{!isGlobal && mode !== "create" && !isAutoMode && (
								<Badge variant="outline" className="text-[10px]">
									Custom
								</Badge>
							)}
						</div>
						<p className="text-sm text-muted-foreground">{getSubtitle()}</p>
						{config && !isAutoMode && mode !== "create" && (
							<p className="text-xs font-mono text-muted-foreground/70">
								{config.model_name}
							</p>
						)}
					</div>
				</div>

				{/* Scrollable content */}
				<div
					ref={scrollRef}
					onScroll={handleScroll}
					className="flex-1 overflow-y-auto px-6 py-5"
					style={{
						maskImage: `linear-gradient(to bottom, ${scrollPos === "top" ? "black" : "transparent"}, black 16px, black calc(100% - 16px), ${scrollPos === "bottom" ? "black" : "transparent"})`,
						WebkitMaskImage: `linear-gradient(to bottom, ${scrollPos === "top" ? "black" : "transparent"}, black 16px, black calc(100% - 16px), ${scrollPos === "bottom" ? "black" : "transparent"})`,
					}}
				>
					{isAutoMode && (
						<Alert className="mb-5 border-violet-500/30 bg-violet-500/5">
							<AlertDescription className="text-sm text-violet-700 dark:text-violet-400">
								Auto mode automatically distributes requests across all available LLM
								providers to optimize performance and avoid rate limits.
							</AlertDescription>
						</Alert>
					)}

					{isGlobal && !isAutoMode && mode !== "create" && (
						<Alert className="mb-5 border-amber-500/30 bg-amber-500/5">
							<AlertCircle className="size-4 text-amber-500" />
							<AlertDescription className="text-sm text-amber-700 dark:text-amber-400">
								Global configurations are read-only. To customize settings, create a new
								configuration based on this template.
							</AlertDescription>
						</Alert>
					)}

					{mode === "create" ? (
						<LLMConfigForm
							searchSpaceId={searchSpaceId}
							onSubmit={handleSubmit}
							isSubmitting={isSubmitting}
							mode="create"
							formId="model-config-form"
							hideActions
						/>
					) : isAutoMode && config ? (
						<div className="space-y-6">
							<div className="space-y-4">
								<div className="space-y-1.5">
									<div className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
										How It Works
									</div>
									<p className="text-sm text-muted-foreground">{config.description}</p>
								</div>

								<div className="h-px bg-border/50" />

								<div className="space-y-3">
									<div className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
										Key Benefits
									</div>
									<div className="space-y-2">
										<div className="flex items-start gap-3 p-3 rounded-lg bg-violet-50 dark:bg-violet-900/20 border border-violet-200 dark:border-violet-800/50">
											<Zap className="size-4 text-violet-600 dark:text-violet-400 mt-0.5 shrink-0" />
											<div>
												<p className="text-sm font-medium text-violet-900 dark:text-violet-100">
													Automatic (Fastest)
												</p>
												<p className="text-xs text-violet-700 dark:text-violet-300">
													Distributes requests across all configured LLM providers
												</p>
											</div>
										</div>
										<div className="flex items-start gap-3 p-3 rounded-lg bg-violet-50 dark:bg-violet-900/20 border border-violet-200 dark:border-violet-800/50">
											<Zap className="size-4 text-violet-600 dark:text-violet-400 mt-0.5 shrink-0" />
											<div>
												<p className="text-sm font-medium text-violet-900 dark:text-violet-100">
													Rate Limit Protection
												</p>
												<p className="text-xs text-violet-700 dark:text-violet-300">
													Automatically handles rate limits with cooldowns and retries
												</p>
											</div>
										</div>
										<div className="flex items-start gap-3 p-3 rounded-lg bg-violet-50 dark:bg-violet-900/20 border border-violet-200 dark:border-violet-800/50">
											<Zap className="size-4 text-violet-600 dark:text-violet-400 mt-0.5 shrink-0" />
											<div>
												<p className="text-sm font-medium text-violet-900 dark:text-violet-100">
													Automatic Failover
												</p>
												<p className="text-xs text-violet-700 dark:text-violet-300">
													Falls back to other providers if one becomes unavailable
												</p>
											</div>
										</div>
									</div>
								</div>
							</div>
						</div>
					) : isGlobal && config ? (
						<div className="space-y-6">
							<div className="space-y-4">
								<div className="grid gap-4 sm:grid-cols-2">
									<div className="space-y-1.5">
										<div className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
											Configuration Name
										</div>
										<p className="text-sm font-medium">{config.name}</p>
									</div>
									{config.description && (
										<div className="space-y-1.5">
											<div className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
												Description
											</div>
											<p className="text-sm text-muted-foreground">{config.description}</p>
										</div>
									)}
								</div>

								<div className="h-px bg-border/50" />

								<div className="grid gap-4 sm:grid-cols-2">
									<div className="space-y-1.5">
										<div className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
											Provider
										</div>
										<p className="text-sm font-medium">{config.provider}</p>
									</div>
									<div className="space-y-1.5">
										<div className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
											Model
										</div>
										<p className="text-sm font-medium font-mono">{config.model_name}</p>
									</div>
								</div>

								<div className="h-px bg-border/50" />

								<div className="grid gap-4 sm:grid-cols-2">
									<div className="space-y-2">
										<div className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
											Citations
										</div>
										<Badge
											variant={config.citations_enabled ? "default" : "secondary"}
											className="w-fit"
										>
											{config.citations_enabled ? "Enabled" : "Disabled"}
										</Badge>
									</div>
								</div>

								{config.system_instructions && (
									<>
										<div className="h-px bg-border/50" />
										<div className="space-y-1.5">
											<div className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
												System Instructions
											</div>
											<div className="p-3 rounded-lg bg-muted/50 border border-border/50">
												<p className="text-xs font-mono text-muted-foreground whitespace-pre-wrap line-clamp-10">
													{config.system_instructions}
												</p>
											</div>
										</div>
									</>
								)}
							</div>
						</div>
					) : config ? (
						<LLMConfigForm
							searchSpaceId={searchSpaceId}
							initialData={{
								name: config.name,
								description: config.description,
								provider: config.provider as LiteLLMProvider,
								custom_provider: config.custom_provider,
								model_name: config.model_name,
								api_key: "api_key" in config ? (config.api_key as string) : "",
								api_base: config.api_base,
								litellm_params: config.litellm_params,
								system_instructions: config.system_instructions,
								use_default_system_instructions: config.use_default_system_instructions,
								citations_enabled: config.citations_enabled,
								search_space_id: searchSpaceId,
							}}
							onSubmit={handleSubmit}
							isSubmitting={isSubmitting}
							mode="edit"
							formId="model-config-form"
							hideActions
						/>
					) : null}
				</div>

				{/* Fixed footer */}
				<div className="shrink-0 px-6 py-4 flex items-center justify-end gap-3">
					<Button
						type="button"
						variant="secondary"
						onClick={() => onOpenChange(false)}
						disabled={isSubmitting}
						className="text-sm h-9"
					>
						Cancel
					</Button>
					{mode === "create" || (!isGlobal && !isAutoMode && config) ? (
						<Button
							type="submit"
							form="model-config-form"
							disabled={isSubmitting}
							className="text-sm h-9 min-w-[120px]"
						>
							{isSubmitting ? (
								<>
									<Spinner size="sm" />
									{mode === "edit" ? "Saving" : "Creating"}
								</>
							) : mode === "edit" ? (
								"Save Changes"
							) : (
								"Create & Use"
							)}
						</Button>
					) : isAutoMode ? (
						<Button
							className="text-sm h-9 gap-2 bg-gradient-to-r from-violet-500 to-purple-600 hover:from-violet-600 hover:to-purple-700"
							onClick={handleUseGlobalConfig}
							disabled={isSubmitting}
						>
							{isSubmitting ? "Loading..." : "Use Auto Mode"}
						</Button>
					) : isGlobal && config ? (
						<Button
							className="text-sm h-9 gap-2"
							onClick={handleUseGlobalConfig}
							disabled={isSubmitting}
						>
							{isSubmitting ? "Loading..." : "Use This Model"}
						</Button>
					) : null}
				</div>
			</DialogContent>
		</Dialog>
	);
}
