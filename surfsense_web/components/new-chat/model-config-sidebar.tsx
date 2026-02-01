"use client";

import { useAtomValue } from "jotai";
import { AlertCircle, Bot, ChevronRight, Globe, Shuffle, User, X, Zap } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useCallback, useEffect, useState } from "react";
import { createPortal } from "react-dom";
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
import type {
	GlobalNewLLMConfig,
	NewLLMConfigPublic,
} from "@/contracts/types/new-llm-config.types";
import { cn } from "@/lib/utils";

interface ModelConfigSidebarProps {
	open: boolean;
	onOpenChange: (open: boolean) => void;
	config: NewLLMConfigPublic | GlobalNewLLMConfig | null;
	isGlobal: boolean;
	searchSpaceId: number;
	mode: "create" | "edit" | "view";
}

export function ModelConfigSidebar({
	open,
	onOpenChange,
	config,
	isGlobal,
	searchSpaceId,
	mode,
}: ModelConfigSidebarProps) {
	const [isSubmitting, setIsSubmitting] = useState(false);
	const [mounted, setMounted] = useState(false);

	// Handle SSR - only render portal on client
	useEffect(() => {
		setMounted(true);
	}, []);

	// Mutations - use mutateAsync from the atom value
	const { mutateAsync: createConfig } = useAtomValue(createNewLLMConfigMutationAtom);
	const { mutateAsync: updateConfig } = useAtomValue(updateNewLLMConfigMutationAtom);
	const { mutateAsync: updatePreferences } = useAtomValue(updateLLMPreferencesMutationAtom);

	// Handle escape key
	useEffect(() => {
		const handleEscape = (e: KeyboardEvent) => {
			if (e.key === "Escape" && open) {
				onOpenChange(false);
			}
		};
		window.addEventListener("keydown", handleEscape);
		return () => window.removeEventListener("keydown", handleEscape);
	}, [open, onOpenChange]);

	// Check if this is Auto mode
	const isAutoMode = config && "is_auto_mode" in config && config.is_auto_mode;

	// Get title based on mode
	const getTitle = () => {
		if (mode === "create") return "Add New Configuration";
		if (isAutoMode) return "Auto Mode (Load Balanced)";
		if (isGlobal) return "View Global Configuration";
		return "Edit Configuration";
	};

	// Handle form submit
	const handleSubmit = useCallback(
		async (data: LLMConfigFormData) => {
			setIsSubmitting(true);
			try {
				if (mode === "create") {
					// Create new config
					const result = await createConfig({
						...data,
						search_space_id: searchSpaceId,
					});

					// Assign the new config to the agent role
					if (result?.id) {
						await updatePreferences({
							search_space_id: searchSpaceId,
							data: {
								agent_llm_id: result.id,
							},
						});
					}

					toast.success("Configuration created and assigned!");
					onOpenChange(false);
				} else if (!isGlobal && config) {
					// Update existing user config
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
					toast.success("Configuration updated!");
					onOpenChange(false);
				}
			} catch (error) {
				console.error("Failed to save configuration:", error);
				toast.error("Failed to save configuration");
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

	// Handle "Use this model" for global configs
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
			toast.error("Failed to set model");
		} finally {
			setIsSubmitting(false);
		}
	}, [config, isGlobal, searchSpaceId, updatePreferences, onOpenChange]);

	if (!mounted) return null;

	const sidebarContent = (
		<AnimatePresence>
			{open && (
				<>
					{/* Backdrop */}
					<motion.div
						initial={{ opacity: 0 }}
						animate={{ opacity: 1 }}
						exit={{ opacity: 0 }}
						transition={{ duration: 0.2 }}
						className="fixed inset-0 z-[24] bg-black/20 backdrop-blur-sm"
						onClick={() => onOpenChange(false)}
					/>

					{/* Sidebar Panel */}
					<motion.div
						initial={{ x: "100%", opacity: 0 }}
						animate={{ x: 0, opacity: 1 }}
						exit={{ x: "100%", opacity: 0 }}
						transition={{
							type: "spring",
							damping: 30,
							stiffness: 300,
						}}
						className={cn(
							"fixed right-0 top-0 z-[25] h-full w-full sm:w-[480px] lg:w-[540px]",
							"bg-background border-l border-border/50 shadow-2xl",
							"flex flex-col"
						)}
					>
						{/* Header */}
						<div
							className={cn(
								"flex items-center justify-between px-6 py-4 border-b border-border/50",
								isAutoMode ? "bg-gradient-to-r from-violet-500/10 to-purple-500/10" : "bg-muted/20"
							)}
						>
							<div className="flex items-center gap-3">
								<div
									className={cn(
										"flex items-center justify-center size-10 rounded-xl",
										isAutoMode ? "bg-gradient-to-br from-violet-500 to-purple-600" : "bg-primary/10"
									)}
								>
									{isAutoMode ? (
										<Shuffle className="size-5 text-white" />
									) : (
										<Bot className="size-5 text-primary" />
									)}
								</div>
								<div>
									<h2 className="text-base sm:text-lg font-semibold">{getTitle()}</h2>
									<div className="flex items-center gap-2 mt-0.5">
										{isAutoMode ? (
											<Badge
												variant="secondary"
												className="gap-1 text-xs bg-violet-100 text-violet-700 dark:bg-violet-900/30 dark:text-violet-300"
											>
												<Zap className="size-3" />
												Recommended
											</Badge>
										) : isGlobal ? (
											<Badge variant="secondary" className="gap-1 text-xs">
												<Globe className="size-3" />
												Global
											</Badge>
										) : mode !== "create" ? (
											<Badge variant="outline" className="gap-1 text-xs">
												<User className="size-3" />
												Custom
											</Badge>
										) : null}
										{config && !isAutoMode && (
											<span className="text-xs text-muted-foreground">{config.model_name}</span>
										)}
									</div>
								</div>
							</div>
							<Button
								variant="ghost"
								size="icon"
								onClick={() => onOpenChange(false)}
								className="h-8 w-8 rounded-full"
							>
								<X className="h-4 w-4" />
								<span className="sr-only">Close</span>
							</Button>
						</div>

						{/* Content - use overflow-y-auto instead of ScrollArea for better compatibility */}
						<div className="flex-1 overflow-y-auto">
							<div className="p-6">
								{/* Auto mode info banner */}
								{isAutoMode && (
									<Alert className="mb-6 border-violet-500/30 bg-violet-500/5">
										<Shuffle className="size-4 text-violet-500" />
										<AlertDescription className="text-sm text-violet-700 dark:text-violet-400">
											Auto mode automatically distributes requests across all available LLM
											providers to optimize performance and avoid rate limits.
										</AlertDescription>
									</Alert>
								)}

								{/* Global config notice */}
								{isGlobal && !isAutoMode && mode !== "create" && (
									<Alert className="mb-6 border-amber-500/30 bg-amber-500/5">
										<AlertCircle className="size-4 text-amber-500" />
										<AlertDescription className="text-sm text-amber-700 dark:text-amber-400">
											Global configurations are read-only. To customize settings, create a new
											configuration based on this template.
										</AlertDescription>
									</Alert>
								)}

								{/* Form */}
								{mode === "create" ? (
									<LLMConfigForm
										searchSpaceId={searchSpaceId}
										onSubmit={handleSubmit}
										onCancel={() => onOpenChange(false)}
										isSubmitting={isSubmitting}
										mode="create"
										submitLabel="Create & Use"
									/>
								) : isAutoMode && config ? (
									// Special view for Auto mode
									<div className="space-y-6">
										{/* Auto Mode Features */}
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
																Automatic Load Balancing
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

										{/* Action Buttons */}
										<div className="flex gap-3 pt-4 border-t border-border/50">
											<Button
												variant="outline"
												className="flex-1"
												onClick={() => onOpenChange(false)}
											>
												Close
											</Button>
											<Button
												className="flex-1 gap-2 bg-gradient-to-r from-violet-500 to-purple-600 hover:from-violet-600 hover:to-purple-700"
												onClick={handleUseGlobalConfig}
												disabled={isSubmitting}
											>
												{isSubmitting ? (
													<>Loading...</>
												) : (
													<>
														<ChevronRight className="size-4" />
														Use Auto Mode
													</>
												)}
											</Button>
										</div>
									</div>
								) : isGlobal && config ? (
									// Read-only view for global configs
									<div className="space-y-6">
										{/* Config Details */}
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

										{/* Action Buttons */}
										<div className="flex gap-3 pt-4 border-t border-border/50">
											<Button
												variant="outline"
												className="flex-1"
												onClick={() => onOpenChange(false)}
											>
												Close
											</Button>
											<Button
												className="flex-1 gap-2"
												onClick={handleUseGlobalConfig}
												disabled={isSubmitting}
											>
												{isSubmitting ? (
													<>Loading...</>
												) : (
													<>
														<ChevronRight className="size-4" />
														Use This Model
													</>
												)}
											</Button>
										</div>
									</div>
								) : config ? (
									// Edit form for user configs
									<LLMConfigForm
										searchSpaceId={searchSpaceId}
										initialData={{
											name: config.name,
											description: config.description,
											provider: config.provider,
											custom_provider: config.custom_provider,
											model_name: config.model_name,
											api_key: config.api_key,
											api_base: config.api_base,
											litellm_params: config.litellm_params,
											system_instructions: config.system_instructions,
											use_default_system_instructions: config.use_default_system_instructions,
											citations_enabled: config.citations_enabled,
											search_space_id: searchSpaceId,
										}}
										onSubmit={handleSubmit}
										onCancel={() => onOpenChange(false)}
										isSubmitting={isSubmitting}
										mode="edit"
										submitLabel="Save Changes"
									/>
								) : null}
							</div>
						</div>
					</motion.div>
				</>
			)}
		</AnimatePresence>
	);

	return typeof document !== "undefined" ? createPortal(sidebarContent, document.body) : null;
}
