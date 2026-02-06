"use client";

import { useAtomValue } from "jotai";
import {
	AlertCircle,
	Check,
	ChevronsUpDown,
	Globe,
	ImageIcon,
	Key,
	Shuffle,
	X,
	Zap,
} from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { createPortal } from "react-dom";
import { toast } from "sonner";
import {
	createImageGenConfigMutationAtom,
	updateImageGenConfigMutationAtom,
} from "@/atoms/image-gen-config/image-gen-config-mutation.atoms";
import { updateLLMPreferencesMutationAtom } from "@/atoms/new-llm-config/new-llm-config-mutation.atoms";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
	Command,
	CommandEmpty,
	CommandGroup,
	CommandInput,
	CommandItem,
	CommandList,
} from "@/components/ui/command";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";
import { Separator } from "@/components/ui/separator";
import { Spinner } from "@/components/ui/spinner";
import { IMAGE_GEN_MODELS, IMAGE_GEN_PROVIDERS } from "@/contracts/enums/image-gen-providers";
import type {
	GlobalImageGenConfig,
	ImageGenerationConfig,
} from "@/contracts/types/new-llm-config.types";
import { cn } from "@/lib/utils";

interface ImageConfigSidebarProps {
	open: boolean;
	onOpenChange: (open: boolean) => void;
	config: ImageGenerationConfig | GlobalImageGenConfig | null;
	isGlobal: boolean;
	searchSpaceId: number;
	mode: "create" | "edit" | "view";
}

const INITIAL_FORM = {
	name: "",
	description: "",
	provider: "",
	model_name: "",
	api_key: "",
	api_base: "",
	api_version: "",
};

export function ImageConfigSidebar({
	open,
	onOpenChange,
	config,
	isGlobal,
	searchSpaceId,
	mode,
}: ImageConfigSidebarProps) {
	const [isSubmitting, setIsSubmitting] = useState(false);
	const [mounted, setMounted] = useState(false);
	const [formData, setFormData] = useState(INITIAL_FORM);
	const [modelComboboxOpen, setModelComboboxOpen] = useState(false);

	useEffect(() => {
		setMounted(true);
	}, []);

	// Reset form when opening
	useEffect(() => {
		if (open) {
			if (mode === "edit" && config && !isGlobal) {
				setFormData({
					name: config.name || "",
					description: config.description || "",
					provider: config.provider || "",
					model_name: config.model_name || "",
					api_key: (config as ImageGenerationConfig).api_key || "",
					api_base: config.api_base || "",
					api_version: config.api_version || "",
				});
			} else if (mode === "create") {
				setFormData(INITIAL_FORM);
			}
		}
	}, [open, mode, config, isGlobal]);

	// Mutations
	const { mutateAsync: createConfig } = useAtomValue(createImageGenConfigMutationAtom);
	const { mutateAsync: updateConfig } = useAtomValue(updateImageGenConfigMutationAtom);
	const { mutateAsync: updatePreferences } = useAtomValue(updateLLMPreferencesMutationAtom);

	// Escape key
	useEffect(() => {
		const handleEscape = (e: KeyboardEvent) => {
			if (e.key === "Escape" && open) onOpenChange(false);
		};
		window.addEventListener("keydown", handleEscape);
		return () => window.removeEventListener("keydown", handleEscape);
	}, [open, onOpenChange]);

	const isAutoMode = config && "is_auto_mode" in config && config.is_auto_mode;

	const suggestedModels = useMemo(() => {
		if (!formData.provider) return [];
		return IMAGE_GEN_MODELS.filter((m) => m.provider === formData.provider);
	}, [formData.provider]);

	const getTitle = () => {
		if (mode === "create") return "Add Image Model";
		if (isAutoMode) return "Auto Mode (Load Balanced)";
		if (isGlobal) return "View Global Image Model";
		return "Edit Image Model";
	};

	const handleSubmit = useCallback(async () => {
		setIsSubmitting(true);
		try {
			if (mode === "create") {
				const result = await createConfig({
					name: formData.name,
					provider: formData.provider,
					model_name: formData.model_name,
					api_key: formData.api_key,
					api_base: formData.api_base || undefined,
					api_version: formData.api_version || undefined,
					description: formData.description || undefined,
					search_space_id: searchSpaceId,
				});
				// Set as active image model
				if (result?.id) {
					await updatePreferences({
						search_space_id: searchSpaceId,
						data: { image_generation_config_id: result.id },
					});
				}
				toast.success("Image model created and assigned!");
				onOpenChange(false);
			} else if (!isGlobal && config) {
				await updateConfig({
					id: config.id,
					data: {
						name: formData.name,
						description: formData.description || undefined,
						provider: formData.provider,
						model_name: formData.model_name,
						api_key: formData.api_key,
						api_base: formData.api_base || undefined,
						api_version: formData.api_version || undefined,
					},
				});
				toast.success("Image model updated!");
				onOpenChange(false);
			}
		} catch (error) {
			console.error("Failed to save image config:", error);
			toast.error("Failed to save image model");
		} finally {
			setIsSubmitting(false);
		}
	}, [mode, isGlobal, config, formData, searchSpaceId, createConfig, updateConfig, updatePreferences, onOpenChange]);

	const handleUseGlobalConfig = useCallback(async () => {
		if (!config || !isGlobal) return;
		setIsSubmitting(true);
		try {
			await updatePreferences({
				search_space_id: searchSpaceId,
				data: { image_generation_config_id: config.id },
			});
			toast.success(`Now using ${config.name}`);
			onOpenChange(false);
		} catch (error) {
			console.error("Failed to set image model:", error);
			toast.error("Failed to set image model");
		} finally {
			setIsSubmitting(false);
		}
	}, [config, isGlobal, searchSpaceId, updatePreferences, onOpenChange]);

	const isFormValid = formData.name && formData.provider && formData.model_name && formData.api_key;
	const selectedProvider = IMAGE_GEN_PROVIDERS.find((p) => p.value === formData.provider);

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
						className="fixed inset-0 z-50 bg-black/20 backdrop-blur-sm"
						onClick={() => onOpenChange(false)}
					/>

					{/* Sidebar */}
					<motion.div
						initial={{ x: "100%", opacity: 0 }}
						animate={{ x: 0, opacity: 1 }}
						exit={{ x: "100%", opacity: 0 }}
						transition={{ type: "spring", damping: 30, stiffness: 300 }}
						className={cn(
							"fixed right-0 top-0 z-50 h-full w-full sm:w-[480px] lg:w-[540px]",
							"bg-background border-l border-border/50 shadow-2xl",
							"flex flex-col"
						)}
					>
						{/* Header */}
						<div
							className={cn(
								"flex items-center justify-between px-6 py-4 border-b border-border/50",
								isAutoMode
									? "bg-gradient-to-r from-violet-500/10 to-purple-500/10"
									: "bg-gradient-to-r from-teal-500/10 to-cyan-500/10"
							)}
						>
							<div className="flex items-center gap-3">
								<div
									className={cn(
										"flex items-center justify-center size-10 rounded-xl",
										isAutoMode
											? "bg-gradient-to-br from-violet-500 to-purple-600"
											: "bg-gradient-to-br from-teal-500 to-cyan-600"
									)}
								>
									{isAutoMode ? (
										<Shuffle className="size-5 text-white" />
									) : (
										<ImageIcon className="size-5 text-white" />
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

						{/* Content */}
						<div className="flex-1 overflow-y-auto">
							<div className="p-6">
								{/* Auto mode */}
								{isAutoMode && (
									<>
										<Alert className="mb-6 border-violet-500/30 bg-violet-500/5">
											<Shuffle className="size-4 text-violet-500" />
											<AlertDescription className="text-sm text-violet-700 dark:text-violet-400">
												Auto mode distributes image generation requests across all configured providers for optimal performance and rate limit protection.
											</AlertDescription>
										</Alert>
										<div className="flex gap-3 pt-4 border-t border-border/50">
											<Button variant="outline" className="flex-1" onClick={() => onOpenChange(false)}>
												Close
											</Button>
											<Button
												className="flex-1 gap-2 bg-gradient-to-r from-violet-500 to-purple-600 hover:from-violet-600 hover:to-purple-700"
												onClick={handleUseGlobalConfig}
												disabled={isSubmitting}
											>
												{isSubmitting ? "Loading..." : "Use Auto Mode"}
											</Button>
										</div>
									</>
								)}

								{/* Global config (read-only) */}
								{isGlobal && !isAutoMode && config && (
									<>
										<Alert className="mb-6 border-amber-500/30 bg-amber-500/5">
											<AlertCircle className="size-4 text-amber-500" />
											<AlertDescription className="text-sm text-amber-700 dark:text-amber-400">
												Global configurations are read-only. To customize, create a new model.
											</AlertDescription>
										</Alert>
										<div className="space-y-4">
											<div className="grid gap-4 sm:grid-cols-2">
												<div className="space-y-1.5">
													<div className="text-xs font-medium text-muted-foreground uppercase tracking-wider">Name</div>
													<p className="text-sm font-medium">{config.name}</p>
												</div>
												{config.description && (
													<div className="space-y-1.5">
														<div className="text-xs font-medium text-muted-foreground uppercase tracking-wider">Description</div>
														<p className="text-sm text-muted-foreground">{config.description}</p>
													</div>
												)}
											</div>
											<Separator />
											<div className="grid gap-4 sm:grid-cols-2">
												<div className="space-y-1.5">
													<div className="text-xs font-medium text-muted-foreground uppercase tracking-wider">Provider</div>
													<p className="text-sm font-medium">{config.provider}</p>
												</div>
												<div className="space-y-1.5">
													<div className="text-xs font-medium text-muted-foreground uppercase tracking-wider">Model</div>
													<p className="text-sm font-medium font-mono">{config.model_name}</p>
												</div>
											</div>
										</div>
										<div className="flex gap-3 pt-6 border-t border-border/50 mt-6">
											<Button variant="outline" className="flex-1" onClick={() => onOpenChange(false)}>
												Close
											</Button>
											<Button className="flex-1 gap-2" onClick={handleUseGlobalConfig} disabled={isSubmitting}>
												{isSubmitting ? "Loading..." : "Use This Model"}
											</Button>
										</div>
									</>
								)}

								{/* Create / Edit form */}
								{(mode === "create" || (mode === "edit" && !isGlobal)) && (
									<div className="space-y-4">
										{/* Name */}
										<div className="space-y-2">
											<Label className="text-sm font-medium">Name *</Label>
											<Input
												placeholder="e.g., My DALL-E 3"
												value={formData.name}
												onChange={(e) => setFormData((p) => ({ ...p, name: e.target.value }))}
											/>
										</div>

										{/* Description */}
										<div className="space-y-2">
											<Label className="text-sm font-medium">Description</Label>
											<Input
												placeholder="Optional description"
												value={formData.description}
												onChange={(e) => setFormData((p) => ({ ...p, description: e.target.value }))}
											/>
										</div>

										<Separator />

										{/* Provider */}
										<div className="space-y-2">
											<Label className="text-sm font-medium">Provider *</Label>
											<Select
												value={formData.provider}
												onValueChange={(val) => setFormData((p) => ({ ...p, provider: val, model_name: "" }))}
											>
												<SelectTrigger>
													<SelectValue placeholder="Select a provider" />
												</SelectTrigger>
												<SelectContent>
													{IMAGE_GEN_PROVIDERS.map((p) => (
														<SelectItem key={p.value} value={p.value}>
															<div className="flex flex-col">
																<span className="font-medium">{p.label}</span>
																<span className="text-xs text-muted-foreground">{p.example}</span>
															</div>
														</SelectItem>
													))}
												</SelectContent>
											</Select>
										</div>

										{/* Model Name */}
										<div className="space-y-2">
											<Label className="text-sm font-medium">Model Name *</Label>
											{suggestedModels.length > 0 ? (
												<Popover open={modelComboboxOpen} onOpenChange={setModelComboboxOpen}>
													<PopoverTrigger asChild>
														<Button variant="outline" role="combobox" className="w-full justify-between font-normal">
															{formData.model_name || "Select or type a model..."}
															<ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
														</Button>
													</PopoverTrigger>
													<PopoverContent className="w-full p-0" align="start">
														<Command>
															<CommandInput
																placeholder="Search or type model..."
																value={formData.model_name}
																onValueChange={(val) => setFormData((p) => ({ ...p, model_name: val }))}
															/>
															<CommandList>
																<CommandEmpty>
																	<span className="text-xs text-muted-foreground">Type a custom model name</span>
																</CommandEmpty>
																<CommandGroup>
																	{suggestedModels.map((m) => (
																		<CommandItem
																			key={m.value}
																			value={m.value}
																			onSelect={() => {
																				setFormData((p) => ({ ...p, model_name: m.value }));
																				setModelComboboxOpen(false);
																			}}
																		>
																			<Check className={cn("mr-2 h-4 w-4", formData.model_name === m.value ? "opacity-100" : "opacity-0")} />
																			<span className="font-mono text-sm">{m.value}</span>
																			<span className="ml-2 text-xs text-muted-foreground">{m.label}</span>
																		</CommandItem>
																	))}
																</CommandGroup>
															</CommandList>
														</Command>
													</PopoverContent>
												</Popover>
											) : (
												<Input
													placeholder="e.g., dall-e-3"
													value={formData.model_name}
													onChange={(e) => setFormData((p) => ({ ...p, model_name: e.target.value }))}
												/>
											)}
										</div>

										{/* API Key */}
										<div className="space-y-2">
											<Label className="text-sm font-medium flex items-center gap-1.5">
												<Key className="h-3.5 w-3.5" /> API Key *
											</Label>
											<Input
												type="password"
												placeholder="sk-..."
												value={formData.api_key}
												onChange={(e) => setFormData((p) => ({ ...p, api_key: e.target.value }))}
											/>
										</div>

										{/* API Base */}
										<div className="space-y-2">
											<Label className="text-sm font-medium">API Base URL</Label>
											<Input
												placeholder={selectedProvider?.apiBase || "Optional"}
												value={formData.api_base}
												onChange={(e) => setFormData((p) => ({ ...p, api_base: e.target.value }))}
											/>
										</div>

										{/* Azure API Version */}
										{formData.provider === "AZURE_OPENAI" && (
											<div className="space-y-2">
												<Label className="text-sm font-medium">API Version (Azure)</Label>
												<Input
													placeholder="2024-02-15-preview"
													value={formData.api_version}
													onChange={(e) => setFormData((p) => ({ ...p, api_version: e.target.value }))}
												/>
											</div>
										)}

										{/* Actions */}
										<div className="flex gap-3 pt-4 border-t">
											<Button variant="outline" className="flex-1" onClick={() => onOpenChange(false)}>
												Cancel
											</Button>
											<Button
												className="flex-1 gap-2 bg-gradient-to-r from-teal-500 to-cyan-600 hover:from-teal-600 hover:to-cyan-700"
												onClick={handleSubmit}
												disabled={isSubmitting || !isFormValid}
											>
												{isSubmitting ? <Spinner size="sm" className="mr-2" /> : null}
												{mode === "edit" ? "Save Changes" : "Create & Use"}
											</Button>
										</div>
									</div>
								)}
							</div>
						</div>
					</motion.div>
				</>
			)}
		</AnimatePresence>
	);

	return typeof document !== "undefined" ? createPortal(sidebarContent, document.body) : null;
}
