"use client";

import { useAtomValue } from "jotai";
import { Bot, Check, ChevronDown, Edit3, ImageIcon, Plus, Zap } from "lucide-react";
import { useCallback, useMemo, useState } from "react";
import { toast } from "sonner";
import {
	globalImageGenConfigsAtom,
	imageGenConfigsAtom,
} from "@/atoms/image-gen-config/image-gen-config-query.atoms";
import { updateLLMPreferencesMutationAtom } from "@/atoms/new-llm-config/new-llm-config-mutation.atoms";
import {
	globalNewLLMConfigsAtom,
	llmPreferencesAtom,
	newLLMConfigsAtom,
} from "@/atoms/new-llm-config/new-llm-config-query.atoms";
import { activeSearchSpaceIdAtom } from "@/atoms/search-spaces/search-space-query.atoms";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
	Command,
	CommandEmpty,
	CommandGroup,
	CommandInput,
	CommandItem,
	CommandList,
	CommandSeparator,
} from "@/components/ui/command";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Spinner } from "@/components/ui/spinner";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import type {
	GlobalImageGenConfig,
	GlobalNewLLMConfig,
	ImageGenerationConfig,
	NewLLMConfigPublic,
} from "@/contracts/types/new-llm-config.types";
import { getProviderIcon } from "@/lib/provider-icons";
import { cn } from "@/lib/utils";

interface ModelSelectorProps {
	onEditLLM: (config: NewLLMConfigPublic | GlobalNewLLMConfig, isGlobal: boolean) => void;
	onAddNewLLM: () => void;
	onEditImage?: (config: ImageGenerationConfig | GlobalImageGenConfig, isGlobal: boolean) => void;
	onAddNewImage?: () => void;
	className?: string;
}

export function ModelSelector({
	onEditLLM,
	onAddNewLLM,
	onEditImage,
	onAddNewImage,
	className,
}: ModelSelectorProps) {
	const [open, setOpen] = useState(false);
	const [activeTab, setActiveTab] = useState<"llm" | "image">("llm");
	const [llmSearchQuery, setLlmSearchQuery] = useState("");
	const [imageSearchQuery, setImageSearchQuery] = useState("");

	// LLM data
	const { data: llmUserConfigs, isLoading: llmUserLoading } = useAtomValue(newLLMConfigsAtom);
	const { data: llmGlobalConfigs, isLoading: llmGlobalLoading } =
		useAtomValue(globalNewLLMConfigsAtom);
	const { data: preferences, isLoading: prefsLoading } = useAtomValue(llmPreferencesAtom);
	const searchSpaceId = useAtomValue(activeSearchSpaceIdAtom);
	const { mutateAsync: updatePreferences } = useAtomValue(updateLLMPreferencesMutationAtom);

	// Image data
	const { data: imageGlobalConfigs, isLoading: imageGlobalLoading } =
		useAtomValue(globalImageGenConfigsAtom);
	const { data: imageUserConfigs, isLoading: imageUserLoading } = useAtomValue(imageGenConfigsAtom);

	const isLoading =
		llmUserLoading || llmGlobalLoading || prefsLoading || imageGlobalLoading || imageUserLoading;

	// ─── LLM current config ───
	const currentLLMConfig = useMemo(() => {
		if (!preferences) return null;
		const agentLlmId = preferences.agent_llm_id;
		if (agentLlmId === null || agentLlmId === undefined) return null;
		if (agentLlmId <= 0) {
			return llmGlobalConfigs?.find((c) => c.id === agentLlmId) ?? null;
		}
		return llmUserConfigs?.find((c) => c.id === agentLlmId) ?? null;
	}, [preferences, llmGlobalConfigs, llmUserConfigs]);

	const isLLMAutoMode = useMemo(() => {
		return currentLLMConfig && "is_auto_mode" in currentLLMConfig && currentLLMConfig.is_auto_mode;
	}, [currentLLMConfig]);

	// ─── Image current config ───
	const currentImageConfig = useMemo(() => {
		if (!preferences) return null;
		const id = preferences.image_generation_config_id;
		if (id === null || id === undefined) return null;
		const globalMatch = imageGlobalConfigs?.find((c) => c.id === id);
		if (globalMatch) return globalMatch;
		return imageUserConfigs?.find((c) => c.id === id) ?? null;
	}, [preferences, imageGlobalConfigs, imageUserConfigs]);

	const isImageAutoMode = useMemo(() => {
		return (
			currentImageConfig && "is_auto_mode" in currentImageConfig && currentImageConfig.is_auto_mode
		);
	}, [currentImageConfig]);

	// ─── LLM filtering ───
	const filteredLLMGlobal = useMemo(() => {
		if (!llmGlobalConfigs) return [];
		if (!llmSearchQuery) return llmGlobalConfigs;
		const q = llmSearchQuery.toLowerCase();
		return llmGlobalConfigs.filter(
			(c) =>
				c.name.toLowerCase().includes(q) ||
				c.model_name.toLowerCase().includes(q) ||
				c.provider.toLowerCase().includes(q)
		);
	}, [llmGlobalConfigs, llmSearchQuery]);

	const filteredLLMUser = useMemo(() => {
		if (!llmUserConfigs) return [];
		if (!llmSearchQuery) return llmUserConfigs;
		const q = llmSearchQuery.toLowerCase();
		return llmUserConfigs.filter(
			(c) =>
				c.name.toLowerCase().includes(q) ||
				c.model_name.toLowerCase().includes(q) ||
				c.provider.toLowerCase().includes(q)
		);
	}, [llmUserConfigs, llmSearchQuery]);

	const totalLLMModels = (llmGlobalConfigs?.length ?? 0) + (llmUserConfigs?.length ?? 0);

	// ─── Image filtering ───
	const filteredImageGlobal = useMemo(() => {
		if (!imageGlobalConfigs) return [];
		if (!imageSearchQuery) return imageGlobalConfigs;
		const q = imageSearchQuery.toLowerCase();
		return imageGlobalConfigs.filter(
			(c) =>
				c.name.toLowerCase().includes(q) ||
				c.model_name.toLowerCase().includes(q) ||
				c.provider.toLowerCase().includes(q)
		);
	}, [imageGlobalConfigs, imageSearchQuery]);

	const filteredImageUser = useMemo(() => {
		if (!imageUserConfigs) return [];
		if (!imageSearchQuery) return imageUserConfigs;
		const q = imageSearchQuery.toLowerCase();
		return imageUserConfigs.filter(
			(c) =>
				c.name.toLowerCase().includes(q) ||
				c.model_name.toLowerCase().includes(q) ||
				c.provider.toLowerCase().includes(q)
		);
	}, [imageUserConfigs, imageSearchQuery]);

	const totalImageModels = (imageGlobalConfigs?.length ?? 0) + (imageUserConfigs?.length ?? 0);

	// ─── Handlers ───
	const handleSelectLLM = useCallback(
		async (config: NewLLMConfigPublic | GlobalNewLLMConfig) => {
			if (currentLLMConfig?.id === config.id) {
				setOpen(false);
				return;
			}
			if (!searchSpaceId) {
				toast.error("No search space selected");
				return;
			}
			try {
				await updatePreferences({
					search_space_id: Number(searchSpaceId),
					data: { agent_llm_id: config.id },
				});
				toast.success(`Switched to ${config.name}`);
				setOpen(false);
			} catch (error) {
				console.error("Failed to switch model:", error);
				toast.error("Failed to switch model");
			}
		},
		[currentLLMConfig, searchSpaceId, updatePreferences]
	);

	const handleEditLLMConfig = useCallback(
		(e: React.MouseEvent, config: NewLLMConfigPublic | GlobalNewLLMConfig, isGlobal: boolean) => {
			e.stopPropagation();
			onEditLLM(config, isGlobal);
			setOpen(false);
		},
		[onEditLLM]
	);

	const handleSelectImage = useCallback(
		async (configId: number) => {
			if (currentImageConfig?.id === configId) {
				setOpen(false);
				return;
			}
			if (!searchSpaceId) {
				toast.error("No search space selected");
				return;
			}
			try {
				await updatePreferences({
					search_space_id: Number(searchSpaceId),
					data: { image_generation_config_id: configId },
				});
				toast.success("Image model updated");
				setOpen(false);
			} catch {
				toast.error("Failed to switch image model");
			}
		},
		[currentImageConfig, searchSpaceId, updatePreferences]
	);

	return (
		<Popover open={open} onOpenChange={setOpen}>
			<PopoverTrigger asChild>
				<Button
					variant="outline"
					size="sm"
					role="combobox"
					aria-expanded={open}
					className={cn("h-8 gap-2 px-3 text-sm border-border/60 select-none", className)}
				>
					{isLoading ? (
						<>
							<Spinner size="sm" className="text-muted-foreground" />
							<span className="text-muted-foreground hidden md:inline">Loading</span>
						</>
					) : (
						<>
							{/* LLM section */}
							{currentLLMConfig ? (
								<>
									{getProviderIcon(currentLLMConfig.provider, {
										isAutoMode: isLLMAutoMode ?? false,
									})}
									<span className="max-w-[100px] md:max-w-[120px] truncate hidden md:inline">
										{currentLLMConfig.name}
									</span>
								</>
							) : (
								<>
									<Bot className="size-4 text-muted-foreground" />
									<span className="text-muted-foreground hidden md:inline">Select Model</span>
								</>
							)}

							{/* Divider */}
							<div className="h-4 w-px bg-border/60 mx-0.5" />

							{/* Image section */}
							{currentImageConfig ? (
								<>
									{getProviderIcon(currentImageConfig.provider, {
										isAutoMode: isImageAutoMode ?? false,
									})}
									<span className="max-w-[80px] md:max-w-[100px] truncate hidden md:inline">
										{currentImageConfig.name}
									</span>
								</>
							) : (
								<ImageIcon className="size-4 text-muted-foreground" />
							)}
						</>
					)}
					<ChevronDown
						className={cn(
							"h-3.5 w-3.5 text-muted-foreground ml-1 shrink-0 transition-transform duration-200",
							open && "rotate-180"
						)}
					/>
				</Button>
			</PopoverTrigger>

			<PopoverContent
				className="w-[280px] md:w-[360px] p-0 rounded-lg shadow-lg border-border/60 dark:bg-muted dark:border dark:border-neutral-700 select-none"
				align="start"
				sideOffset={8}
			>
				<Tabs
					value={activeTab}
					onValueChange={(v) => setActiveTab(v as "llm" | "image")}
					className="w-full"
				>
					<div className="border-b border-border/80 dark:border-white/5">
						<TabsList className="w-full grid grid-cols-2 rounded-none rounded-t-lg bg-transparent h-11 p-0 gap-0">
							<TabsTrigger
								value="llm"
								className="gap-2 text-sm font-medium rounded-none text-muted-foreground/60 transition-all duration-200 h-full bg-transparent data-[state=active]:bg-transparent shadow-none data-[state=active]:shadow-none border-b-[1.5px] border-transparent data-[state=active]:border-foreground dark:data-[state=active]:border-white data-[state=active]:text-foreground"
							>
								<Zap className="size-4" />
								LLM
							</TabsTrigger>
							<TabsTrigger
								value="image"
								className="gap-2 text-sm font-medium rounded-none text-muted-foreground/60 transition-all duration-200 h-full bg-transparent data-[state=active]:bg-transparent shadow-none data-[state=active]:shadow-none border-b-[1.5px] border-transparent data-[state=active]:border-foreground dark:data-[state=active]:border-white data-[state=active]:text-foreground"
							>
								<ImageIcon className="size-4" />
								Image
							</TabsTrigger>
						</TabsList>
					</div>

					{/* ─── LLM Tab ─── */}
					<TabsContent value="llm" className="mt-0">
						<Command
							shouldFilter={false}
							className="rounded-none rounded-b-lg relative dark:bg-muted [&_[data-slot=command-input-wrapper]]:border-0 [&_[data-slot=command-input-wrapper]]:px-0 [&_[data-slot=command-input-wrapper]]:gap-2"
						>
							{totalLLMModels > 3 && (
								<div className="px-2 md:px-3 py-1.5 md:py-2">
									<CommandInput
										placeholder="Search models"
										value={llmSearchQuery}
										onValueChange={setLlmSearchQuery}
										className="h-7 md:h-8 w-full text-xs md:text-sm border-0 bg-transparent focus:ring-0 placeholder:text-muted-foreground/60"
									/>
								</div>
							)}

							<CommandList className="max-h-[300px] md:max-h-[400px] overflow-y-auto">
								<CommandEmpty className="py-8 text-center">
									<div className="flex flex-col items-center gap-2">
										<Bot className="size-8 text-muted-foreground" />
										<p className="text-sm text-muted-foreground">No models found</p>
										<p className="text-xs text-muted-foreground/60">Try a different search term</p>
									</div>
								</CommandEmpty>

								{/* Global LLM Configs */}
								{filteredLLMGlobal.length > 0 && (
									<CommandGroup>
										<div className="flex items-center gap-2 px-3 py-2 text-xs font-semibold text-muted-foreground tracking-wider">
											Global Models
										</div>
										{filteredLLMGlobal.map((config) => {
											const isSelected = currentLLMConfig?.id === config.id;
											const isAutoMode = "is_auto_mode" in config && config.is_auto_mode;
											return (
												<CommandItem
													key={`llm-g-${config.id}`}
													value={`llm-g-${config.id}`}
													onSelect={() => handleSelectLLM(config)}
													className={cn(
														"mx-2 rounded-lg mb-1 cursor-pointer group transition-all",
														"hover:bg-accent/50 dark:hover:bg-white/10",
														isSelected && "bg-accent/80 dark:bg-white/10",
														isAutoMode && ""
													)}
												>
													<div className="flex items-center justify-between w-full gap-2">
														<div className="flex items-center gap-3 min-w-0 flex-1">
															<div className="shrink-0">
																{getProviderIcon(config.provider, { isAutoMode })}
															</div>
															<div className="min-w-0 flex-1">
																<div className="flex items-center gap-2">
																	<span className="font-medium truncate">{config.name}</span>
																	{isAutoMode && (
																		<Badge
																			variant="secondary"
																			className="text-[9px] px-1 py-0 h-3.5 bg-violet-800 text-white dark:bg-violet-800 dark:text-white border-0"
																		>
																			Recommended
																		</Badge>
																	)}
																	{isSelected && (
																		<Check className="size-3.5 text-primary shrink-0" />
																	)}
																</div>
																<div className="flex items-center gap-1.5 mt-0.5">
																	<span className="text-xs text-muted-foreground truncate">
																		{isAutoMode ? "Auto Mode" : config.model_name}
																	</span>
																	{!isAutoMode && config.citations_enabled && (
																		<Badge
																			variant="outline"
																			className="text-[9px] px-1 py-0 h-3.5 bg-primary/10 text-primary border-primary/20"
																		>
																			Citations
																		</Badge>
																	)}
																</div>
															</div>
														</div>
														{!isAutoMode && (
															<Button
																variant="ghost"
																size="icon"
																className="size-7 shrink-0 rounded-md hover:bg-muted opacity-0 group-hover:opacity-100 transition-opacity"
																onClick={(e) => handleEditLLMConfig(e, config, true)}
															>
																<Edit3 className="size-3.5 text-muted-foreground" />
															</Button>
														)}
													</div>
												</CommandItem>
											);
										})}
									</CommandGroup>
								)}

								{filteredLLMGlobal.length > 0 && filteredLLMUser.length > 0 && (
									<CommandSeparator className="my-1 mx-4 bg-border/60" />
								)}

								{/* User LLM Configs */}
								{filteredLLMUser.length > 0 && (
									<CommandGroup>
										<div className="flex items-center gap-2 px-3 py-2 text-xs font-semibold text-muted-foreground tracking-wider">
											Your Configurations
										</div>
										{filteredLLMUser.map((config) => {
											const isSelected = currentLLMConfig?.id === config.id;
											return (
												<CommandItem
													key={`llm-u-${config.id}`}
													value={`llm-u-${config.id}`}
													onSelect={() => handleSelectLLM(config)}
													className={cn(
														"mx-2 rounded-lg mb-1 cursor-pointer group transition-all",
														"hover:bg-accent/50 dark:hover:bg-white/10",
														isSelected && "bg-accent/80 dark:bg-white/10"
													)}
												>
													<div className="flex items-center justify-between w-full gap-2">
														<div className="flex items-center gap-3 min-w-0 flex-1">
															<div className="shrink-0">{getProviderIcon(config.provider)}</div>
															<div className="min-w-0 flex-1">
																<div className="flex items-center gap-2">
																	<span className="font-medium truncate">{config.name}</span>
																	{isSelected && (
																		<Check className="size-3.5 text-primary shrink-0" />
																	)}
																</div>
																<div className="flex items-center gap-1.5 mt-0.5">
																	<span className="text-xs text-muted-foreground truncate">
																		{config.model_name}
																	</span>
																	{config.citations_enabled && (
																		<Badge
																			variant="outline"
																			className="text-[9px] px-1 py-0 h-3.5 bg-primary/10 text-primary border-primary/20"
																		>
																			Citations
																		</Badge>
																	)}
																</div>
															</div>
														</div>
														<Button
															variant="ghost"
															size="icon"
															className="size-7 shrink-0 rounded-md hover:bg-muted opacity-0 group-hover:opacity-100 transition-opacity"
															onClick={(e) => handleEditLLMConfig(e, config, false)}
														>
															<Edit3 className="size-3.5 text-muted-foreground" />
														</Button>
													</div>
												</CommandItem>
											);
										})}
									</CommandGroup>
								)}

								{/* Add New LLM Config */}
								<div className="p-2 bg-muted/20 dark:bg-muted">
									<Button
										variant="ghost"
										size="sm"
										className="w-full justify-start gap-2 h-9 rounded-lg hover:bg-accent/50 dark:hover:bg-white/10"
										onClick={() => {
											setOpen(false);
											onAddNewLLM();
										}}
									>
										<Plus className="size-4 text-primary" />
										<span className="text-sm font-medium">Add New Configuration</span>
									</Button>
								</div>
							</CommandList>
						</Command>
					</TabsContent>

					{/* ─── Image Tab ─── */}
					<TabsContent value="image" className="mt-0">
						<Command
							shouldFilter={false}
							className="rounded-none rounded-b-lg dark:bg-muted [&_[data-slot=command-input-wrapper]]:border-0 [&_[data-slot=command-input-wrapper]]:px-0 [&_[data-slot=command-input-wrapper]]:gap-2"
						>
							{totalImageModels > 3 && (
								<div className="px-2 md:px-3 py-1.5 md:py-2">
									<CommandInput
										placeholder="Search models"
										value={imageSearchQuery}
										onValueChange={setImageSearchQuery}
										className="h-7 md:h-8 w-full text-xs md:text-sm border-0 bg-transparent focus:ring-0 placeholder:text-muted-foreground/60"
									/>
								</div>
							)}
							<CommandList className="max-h-[300px] md:max-h-[400px] overflow-y-auto">
								<CommandEmpty className="py-8 text-center">
									<div className="flex flex-col items-center gap-2">
										<ImageIcon className="size-8 text-muted-foreground" />
										<p className="text-sm text-muted-foreground">No image models found</p>
									</div>
								</CommandEmpty>

								{/* Global Image Configs */}
								{filteredImageGlobal.length > 0 && (
									<CommandGroup>
										<div className="flex items-center gap-2 px-3 py-2 text-xs font-semibold text-muted-foreground tracking-wider">
											Global Image Models
										</div>
										{filteredImageGlobal.map((config) => {
											const isSelected = currentImageConfig?.id === config.id;
											const isAuto = "is_auto_mode" in config && config.is_auto_mode;
											return (
												<CommandItem
													key={`img-g-${config.id}`}
													value={`img-g-${config.id}`}
													onSelect={() => handleSelectImage(config.id)}
													className={cn(
														"mx-2 rounded-lg mb-1 cursor-pointer group transition-all hover:bg-accent/50 dark:hover:bg-white/10",
														isSelected && "bg-accent/80 dark:bg-white/10",
														isAuto && ""
													)}
												>
													<div className="flex items-center gap-3 min-w-0 flex-1">
														<div className="shrink-0">
															{getProviderIcon(config.provider, { isAutoMode: isAuto })}
														</div>
														<div className="min-w-0 flex-1">
															<div className="flex items-center gap-2">
																<span className="font-medium truncate">{config.name}</span>
																{isAuto && (
																	<Badge
																		variant="secondary"
																		className="text-[9px] px-1 py-0 h-3.5 bg-violet-800 text-white dark:bg-violet-800 dark:text-white border-0"
																	>
																		Recommended
																	</Badge>
																)}
																{isSelected && <Check className="size-3.5 text-primary shrink-0" />}
															</div>
															<span className="text-xs text-muted-foreground truncate block">
																{isAuto ? "Auto Mode" : config.model_name}
															</span>
														</div>
														{onEditImage && !isAuto && (
															<Button
																variant="ghost"
																size="icon"
																className="size-7 shrink-0 rounded-md hover:bg-muted opacity-0 group-hover:opacity-100 transition-opacity"
																onClick={(e) => {
																	e.stopPropagation();
																	setOpen(false);
																	onEditImage(config, true);
																}}
															>
																<Edit3 className="size-3.5 text-muted-foreground" />
															</Button>
														)}
													</div>
												</CommandItem>
											);
										})}
									</CommandGroup>
								)}

								{/* User Image Configs */}
								{filteredImageUser.length > 0 && (
									<>
										{filteredImageGlobal.length > 0 && (
											<CommandSeparator className="my-1 mx-4 bg-border/60" />
										)}
										<CommandGroup>
											<div className="flex items-center gap-2 px-3 py-2 text-xs font-semibold text-muted-foreground tracking-wider">
												Your Image Models
											</div>
											{filteredImageUser.map((config) => {
												const isSelected = currentImageConfig?.id === config.id;
												return (
													<CommandItem
														key={`img-u-${config.id}`}
														value={`img-u-${config.id}`}
														onSelect={() => handleSelectImage(config.id)}
														className={cn(
															"mx-2 rounded-lg mb-1 cursor-pointer group transition-all hover:bg-accent/50 dark:hover:bg-white/10",
															isSelected && "bg-accent/80 dark:bg-white/10"
														)}
													>
														<div className="flex items-center gap-3 min-w-0 flex-1">
															<div className="shrink-0">{getProviderIcon(config.provider)}</div>
															<div className="min-w-0 flex-1">
																<div className="flex items-center gap-2">
																	<span className="font-medium truncate">{config.name}</span>
																	{isSelected && (
																		<Check className="size-3.5 text-primary shrink-0" />
																	)}
																</div>
																<span className="text-xs text-muted-foreground truncate block">
																	{config.model_name}
																</span>
															</div>
															{onEditImage && (
																<Button
																	variant="ghost"
																	size="icon"
																	className="h-7 w-7 shrink-0 opacity-0 group-hover:opacity-100 transition-opacity"
																	onClick={(e) => {
																		e.stopPropagation();
																		setOpen(false);
																		onEditImage(config, false);
																	}}
																>
																	<Edit3 className="size-3.5 text-muted-foreground" />
																</Button>
															)}
														</div>
													</CommandItem>
												);
											})}
										</CommandGroup>
									</>
								)}

								{/* Add New Image Config */}
								{onAddNewImage && (
									<div className="p-2 bg-muted/20 dark:bg-muted">
										<Button
											variant="ghost"
											size="sm"
											className="w-full justify-start gap-2 h-9 rounded-lg hover:bg-accent/50 dark:hover:bg-white/10"
											onClick={() => {
												setOpen(false);
												onAddNewImage();
											}}
										>
											<Plus className="size-4 text-primary" />
											<span className="text-sm font-medium">Add Image Model</span>
										</Button>
									</div>
								)}
							</CommandList>
						</Command>
					</TabsContent>
				</Tabs>
			</PopoverContent>
		</Popover>
	);
}
