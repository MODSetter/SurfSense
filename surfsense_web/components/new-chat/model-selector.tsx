"use client";

import { useAtomValue } from "jotai";
import { Bot, Check, ChevronDown, Edit3, Eye, ImageIcon, Plus, Search, Zap } from "lucide-react";
import { type UIEvent, useCallback, useEffect, useMemo, useState } from "react";
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
import {
	globalVisionLLMConfigsAtom,
	visionLLMConfigsAtom,
} from "@/atoms/vision-llm-config/vision-llm-config-query.atoms";
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
	GlobalVisionLLMConfig,
	ImageGenerationConfig,
	NewLLMConfigPublic,
	VisionLLMConfig,
} from "@/contracts/types/new-llm-config.types";
import { getProviderIcon } from "@/lib/provider-icons";
import { cn } from "@/lib/utils";

interface ModelSelectorProps {
	onEditLLM?: (config: NewLLMConfigPublic | GlobalNewLLMConfig, isGlobal: boolean) => void;
	onAddNewLLM?: () => void;
	onEditImage?: (config: ImageGenerationConfig | GlobalImageGenConfig, isGlobal: boolean) => void;
	onAddNewImage?: () => void;
	onEditVision?: (config: VisionLLMConfig | GlobalVisionLLMConfig, isGlobal: boolean) => void;
	onAddNewVision?: () => void;
	className?: string;
}

export function ModelSelector({
	onEditLLM,
	onAddNewLLM,
	onEditImage,
	onAddNewImage,
	onEditVision,
	onAddNewVision,
	className,
}: ModelSelectorProps) {
	const [open, setOpen] = useState(false);
	const [activeTab, setActiveTab] = useState<"llm" | "image" | "vision">("llm");
	const [llmSearchQuery, setLlmSearchQuery] = useState("");
	const [imageSearchQuery, setImageSearchQuery] = useState("");
	const [visionSearchQuery, setVisionSearchQuery] = useState("");
	const [llmScrollPos, setLlmScrollPos] = useState<"top" | "middle" | "bottom">("top");
	const [imageScrollPos, setImageScrollPos] = useState<"top" | "middle" | "bottom">("top");
	const [visionScrollPos, setVisionScrollPos] = useState<"top" | "middle" | "bottom">("top");
	const handleListScroll = useCallback(
		(setter: typeof setLlmScrollPos) => (e: UIEvent<HTMLDivElement>) => {
			const el = e.currentTarget;
			const atTop = el.scrollTop <= 2;
			const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight <= 2;
			setter(atTop ? "top" : atBottom ? "bottom" : "middle");
		},
		[]
	);

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

	// Vision data
	const { data: visionGlobalConfigs, isLoading: visionGlobalLoading } = useAtomValue(
		globalVisionLLMConfigsAtom
	);
	const { data: visionUserConfigs, isLoading: visionUserLoading } =
		useAtomValue(visionLLMConfigsAtom);

	const isLoading =
		llmUserLoading ||
		llmGlobalLoading ||
		prefsLoading ||
		imageGlobalLoading ||
		imageUserLoading ||
		visionGlobalLoading ||
		visionUserLoading;

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

	const isLLMAutoMode =
		currentLLMConfig && "is_auto_mode" in currentLLMConfig && currentLLMConfig.is_auto_mode;

	// ─── Image current config ───
	const currentImageConfig = useMemo(() => {
		if (!preferences) return null;
		const id = preferences.image_generation_config_id;
		if (id === null || id === undefined) return null;
		const globalMatch = imageGlobalConfigs?.find((c) => c.id === id);
		if (globalMatch) return globalMatch;
		return imageUserConfigs?.find((c) => c.id === id) ?? null;
	}, [preferences, imageGlobalConfigs, imageUserConfigs]);

	const isImageAutoMode =
		currentImageConfig && "is_auto_mode" in currentImageConfig && currentImageConfig.is_auto_mode;

	// ─── Vision current config ───
	const currentVisionConfig = useMemo(() => {
		if (!preferences) return null;
		const id = preferences.vision_llm_config_id;
		if (id === null || id === undefined) return null;
		const globalMatch = visionGlobalConfigs?.find((c) => c.id === id);
		if (globalMatch) return globalMatch;
		return visionUserConfigs?.find((c) => c.id === id) ?? null;
	}, [preferences, visionGlobalConfigs, visionUserConfigs]);

	const isVisionAutoMode = useMemo(() => {
		return (
			currentVisionConfig &&
			"is_auto_mode" in currentVisionConfig &&
			currentVisionConfig.is_auto_mode
		);
	}, [currentVisionConfig]);

	// ─── Auto-reset stale config selections ───
	// When configs finish loading and a saved preference points to a deleted config,
	// silently clear the stale ID so the UI shows "Select a model" instead of erroring.
	useEffect(() => {
		if (!preferences || !searchSpaceId || llmUserLoading || llmGlobalLoading || prefsLoading)
			return;
		const agentLlmId = preferences.agent_llm_id;
		if (agentLlmId === null || agentLlmId === undefined) return;
		const existsInUser = llmUserConfigs?.some((c) => c.id === agentLlmId);
		const existsInGlobal = llmGlobalConfigs?.some((c) => c.id === agentLlmId);
		if (!existsInUser && !existsInGlobal) {
			updatePreferences({ search_space_id: Number(searchSpaceId), data: { agent_llm_id: null } });
		}
	}, [
		preferences,
		llmUserConfigs,
		llmGlobalConfigs,
		llmUserLoading,
		llmGlobalLoading,
		prefsLoading,
		searchSpaceId,
		updatePreferences,
	]);

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

	// ─── Vision filtering ───
	const filteredVisionGlobal = useMemo(() => {
		if (!visionGlobalConfigs) return [];
		if (!visionSearchQuery) return visionGlobalConfigs;
		const q = visionSearchQuery.toLowerCase();
		return visionGlobalConfigs.filter(
			(c) =>
				c.name.toLowerCase().includes(q) ||
				c.model_name.toLowerCase().includes(q) ||
				c.provider.toLowerCase().includes(q)
		);
	}, [visionGlobalConfigs, visionSearchQuery]);

	const filteredVisionUser = useMemo(() => {
		if (!visionUserConfigs) return [];
		if (!visionSearchQuery) return visionUserConfigs;
		const q = visionSearchQuery.toLowerCase();
		return visionUserConfigs.filter(
			(c) =>
				c.name.toLowerCase().includes(q) ||
				c.model_name.toLowerCase().includes(q) ||
				c.provider.toLowerCase().includes(q)
		);
	}, [visionUserConfigs, visionSearchQuery]);

	const totalVisionModels = (visionGlobalConfigs?.length ?? 0) + (visionUserConfigs?.length ?? 0);

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

	const handleSelectVision = useCallback(
		async (configId: number) => {
			if (currentVisionConfig?.id === configId) {
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
					data: { vision_llm_config_id: configId },
				});
				toast.success("Vision model updated");
				setOpen(false);
			} catch {
				toast.error("Failed to switch vision model");
			}
		},
		[currentVisionConfig, searchSpaceId, updatePreferences]
	);

	return (
		<Popover open={open} onOpenChange={setOpen}>
			<PopoverTrigger asChild>
				<Button
					variant="ghost"
					size="sm"
					role="combobox"
					aria-expanded={open}
					className={cn(
						"h-8 gap-2 px-3 text-sm bg-main-panel hover:bg-accent/50 dark:hover:bg-white/[0.06] border border-border/40 select-none",
						className
					)}
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
							<div className="h-4 w-px bg-border/60 dark:bg-white/10 mx-0.5" />

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

							{/* Divider */}
							<div className="h-4 w-px bg-border/60 dark:bg-white/10 mx-0.5" />

							{/* Vision section */}
							{currentVisionConfig ? (
								<>
									{getProviderIcon(currentVisionConfig.provider, {
										isAutoMode: isVisionAutoMode ?? false,
									})}
									<span className="max-w-[80px] md:max-w-[100px] truncate hidden md:inline">
										{currentVisionConfig.name}
									</span>
								</>
							) : (
								<Eye className="size-4 text-muted-foreground" />
							)}
						</>
					)}
					<ChevronDown className="h-3.5 w-3.5 text-muted-foreground ml-1 shrink-0" />
				</Button>
			</PopoverTrigger>

			<PopoverContent
				className="w-[280px] md:w-[360px] p-0 rounded-lg shadow-lg bg-white border-border/60 dark:bg-neutral-900 dark:border dark:border-white/5 select-none"
				align="start"
				sideOffset={8}
			>
				<Tabs
					value={activeTab}
					onValueChange={(v) => setActiveTab(v as "llm" | "image" | "vision")}
					className="w-full"
				>
					<div className="border-b border-border/80 dark:border-neutral-800">
						<TabsList className="w-full grid grid-cols-3 rounded-none rounded-t-lg bg-transparent h-11 p-0 gap-0">
							<TabsTrigger
								value="llm"
								className="gap-1.5 text-sm font-medium rounded-none text-muted-foreground transition-all duration-200 h-full bg-transparent data-[state=active]:bg-transparent shadow-none data-[state=active]:shadow-none border-b-[1.5px] border-transparent data-[state=active]:border-foreground dark:data-[state=active]:border-white data-[state=active]:text-foreground"
							>
								<Zap className="size-3.5" />
								LLM
							</TabsTrigger>
							<TabsTrigger
								value="image"
								className="gap-1.5 text-sm font-medium rounded-none text-muted-foreground transition-all duration-200 h-full bg-transparent data-[state=active]:bg-transparent shadow-none data-[state=active]:shadow-none border-b-[1.5px] border-transparent data-[state=active]:border-foreground dark:data-[state=active]:border-white data-[state=active]:text-foreground"
							>
								<ImageIcon className="size-3.5" />
								Image
							</TabsTrigger>
							<TabsTrigger
								value="vision"
								className="gap-1.5 text-sm font-medium rounded-none text-muted-foreground transition-all duration-200 h-full bg-transparent data-[state=active]:bg-transparent shadow-none data-[state=active]:shadow-none border-b-[1.5px] border-transparent data-[state=active]:border-foreground dark:data-[state=active]:border-white data-[state=active]:text-foreground"
							>
								<Eye className="size-3.5" />
								Vision
							</TabsTrigger>
						</TabsList>
					</div>

					{/* ─── LLM Tab ─── */}
					<TabsContent value="llm" className="mt-0">
						<Command
							shouldFilter={false}
							className="rounded-none rounded-b-lg relative dark:bg-neutral-900 [&_[data-slot=command-input-wrapper]]:border-0 [&_[data-slot=command-input-wrapper]]:px-0 [&_[data-slot=command-input-wrapper]]:gap-2"
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

							<CommandList
								className="max-h-[300px] md:max-h-[400px] overflow-y-auto"
								onScroll={handleListScroll(setLlmScrollPos)}
								style={{
									maskImage: `linear-gradient(to bottom, ${llmScrollPos === "top" ? "black" : "transparent"}, black 16px, black calc(100% - 16px), ${llmScrollPos === "bottom" ? "black" : "transparent"})`,
									WebkitMaskImage: `linear-gradient(to bottom, ${llmScrollPos === "top" ? "black" : "transparent"}, black 16px, black calc(100% - 16px), ${llmScrollPos === "bottom" ? "black" : "transparent"})`,
								}}
							>
								<CommandEmpty className="py-8 text-center">
									<div className="flex flex-col items-center gap-2">
										<Search className="size-8 text-muted-foreground" />
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
														"hover:bg-accent/50 dark:hover:bg-white/[0.06]",
														isSelected && "bg-accent/80 dark:bg-white/[0.06]",
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
														{!isAutoMode && onEditLLM && (
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
														"hover:bg-accent/50 dark:hover:bg-white/[0.06]",
														isSelected && "bg-accent/80 dark:bg-white/[0.06]"
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
														{onEditLLM && (
															<Button
																variant="ghost"
																size="icon"
																className="size-7 shrink-0 rounded-md hover:bg-muted opacity-0 group-hover:opacity-100 transition-opacity"
																onClick={(e) => handleEditLLMConfig(e, config, false)}
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

								{/* Add New LLM Config — admin only */}
								{onAddNewLLM && (
									<div className="p-2 bg-muted/20 dark:bg-neutral-900">
										<Button
											variant="ghost"
											size="sm"
											className="w-full justify-start gap-2 h-9 rounded-lg hover:bg-accent/50 dark:hover:bg-white/[0.06]"
											onClick={() => {
												setOpen(false);
												onAddNewLLM();
											}}
										>
											<Plus className="size-4 text-primary" />
											<span className="text-sm font-medium">Add Model</span>
										</Button>
									</div>
								)}
							</CommandList>
						</Command>
					</TabsContent>

					{/* ─── Image Tab ─── */}
					<TabsContent value="image" className="mt-0">
						<Command
							shouldFilter={false}
							className="rounded-none rounded-b-lg dark:bg-neutral-900 [&_[data-slot=command-input-wrapper]]:border-0 [&_[data-slot=command-input-wrapper]]:px-0 [&_[data-slot=command-input-wrapper]]:gap-2"
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
							<CommandList
								className="max-h-[300px] md:max-h-[400px] overflow-y-auto"
								onScroll={handleListScroll(setImageScrollPos)}
								style={{
									maskImage: `linear-gradient(to bottom, ${imageScrollPos === "top" ? "black" : "transparent"}, black 16px, black calc(100% - 16px), ${imageScrollPos === "bottom" ? "black" : "transparent"})`,
									WebkitMaskImage: `linear-gradient(to bottom, ${imageScrollPos === "top" ? "black" : "transparent"}, black 16px, black calc(100% - 16px), ${imageScrollPos === "bottom" ? "black" : "transparent"})`,
								}}
							>
								<CommandEmpty className="py-8 text-center">
									<div className="flex flex-col items-center gap-2">
										<Search className="size-8 text-muted-foreground" />
										<p className="text-sm text-muted-foreground">No image models found</p>
										<p className="text-xs text-muted-foreground/60">Try a different search term</p>
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
														"mx-2 rounded-lg mb-1 cursor-pointer group transition-all hover:bg-accent/50 dark:hover:bg-white/[0.06]",
														isSelected && "bg-accent/80 dark:bg-white/[0.06]",
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
															"mx-2 rounded-lg mb-1 cursor-pointer group transition-all hover:bg-accent/50 dark:hover:bg-white/[0.06]",
															isSelected && "bg-accent/80 dark:bg-white/[0.06]"
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
									<div className="p-2 bg-muted/20 dark:bg-neutral-900">
										<Button
											variant="ghost"
											size="sm"
											className="w-full justify-start gap-2 h-9 rounded-lg hover:bg-accent/50 dark:hover:bg-white/[0.06]"
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

					{/* ─── Vision Tab ─── */}
					<TabsContent value="vision" className="mt-0">
						<Command
							shouldFilter={false}
							className="rounded-none rounded-b-lg dark:bg-neutral-900 [&_[data-slot=command-input-wrapper]]:border-0 [&_[data-slot=command-input-wrapper]]:px-0 [&_[data-slot=command-input-wrapper]]:gap-2"
						>
							{totalVisionModels > 3 && (
								<div className="px-2 md:px-3 py-1.5 md:py-2">
									<CommandInput
										placeholder="Search vision models"
										value={visionSearchQuery}
										onValueChange={setVisionSearchQuery}
										className="h-7 md:h-8 w-full text-xs md:text-sm border-0 bg-transparent focus:ring-0 placeholder:text-muted-foreground/60"
									/>
								</div>
							)}
							<CommandList
								className="max-h-[300px] md:max-h-[400px] overflow-y-auto"
								onScroll={handleListScroll(setVisionScrollPos)}
								style={{
									maskImage: `linear-gradient(to bottom, ${visionScrollPos === "top" ? "black" : "transparent"}, black 16px, black calc(100% - 16px), ${visionScrollPos === "bottom" ? "black" : "transparent"})`,
									WebkitMaskImage: `linear-gradient(to bottom, ${visionScrollPos === "top" ? "black" : "transparent"}, black 16px, black calc(100% - 16px), ${visionScrollPos === "bottom" ? "black" : "transparent"})`,
								}}
							>
								<CommandEmpty className="py-8 text-center">
									<div className="flex flex-col items-center gap-2">
										<Search className="size-8 text-muted-foreground" />
										<p className="text-sm text-muted-foreground">No vision models found</p>
										<p className="text-xs text-muted-foreground/60">Try a different search term</p>
									</div>
								</CommandEmpty>

								{filteredVisionGlobal.length > 0 && (
									<CommandGroup>
										<div className="flex items-center gap-2 px-3 py-2 text-xs font-semibold text-muted-foreground tracking-wider">
											Global Vision Models
										</div>
										{filteredVisionGlobal.map((config) => {
											const isSelected = currentVisionConfig?.id === config.id;
											const isAuto = "is_auto_mode" in config && config.is_auto_mode;
											return (
												<CommandItem
													key={`vis-g-${config.id}`}
													value={`vis-g-${config.id}`}
													onSelect={() => handleSelectVision(config.id)}
													className={cn(
														"mx-2 rounded-lg mb-1 cursor-pointer group transition-all hover:bg-accent/50 dark:hover:bg-white/[0.06]",
														isSelected && "bg-accent/80 dark:bg-white/[0.06]"
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
														{onEditVision && !isAuto && (
															<Button
																variant="ghost"
																size="icon"
																className="size-7 shrink-0 rounded-md hover:bg-muted opacity-0 group-hover:opacity-100 transition-opacity"
																onClick={(e) => {
																	e.stopPropagation();
																	setOpen(false);
																	onEditVision(config as VisionLLMConfig, true);
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

								{filteredVisionUser.length > 0 && (
									<>
										{filteredVisionGlobal.length > 0 && (
											<CommandSeparator className="my-1 mx-4 bg-border/60" />
										)}
										<CommandGroup>
											<div className="flex items-center gap-2 px-3 py-2 text-xs font-semibold text-muted-foreground tracking-wider">
												Your Vision Models
											</div>
											{filteredVisionUser.map((config) => {
												const isSelected = currentVisionConfig?.id === config.id;
												return (
													<CommandItem
														key={`vis-u-${config.id}`}
														value={`vis-u-${config.id}`}
														onSelect={() => handleSelectVision(config.id)}
														className={cn(
															"mx-2 rounded-lg mb-1 cursor-pointer group transition-all hover:bg-accent/50 dark:hover:bg-white/[0.06]",
															isSelected && "bg-accent/80 dark:bg-white/[0.06]"
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
															{onEditVision && (
																<Button
																	variant="ghost"
																	size="icon"
																	className="h-7 w-7 shrink-0 opacity-0 group-hover:opacity-100 transition-opacity"
																	onClick={(e) => {
																		e.stopPropagation();
																		setOpen(false);
																		onEditVision(config, false);
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

								{onAddNewVision && (
									<div className="p-2 bg-muted/20 dark:bg-neutral-900">
										<Button
											variant="ghost"
											size="sm"
											className="w-full justify-start gap-2 h-9 rounded-lg hover:bg-accent/50 dark:hover:bg-white/[0.06]"
											onClick={() => {
												setOpen(false);
												onAddNewVision();
											}}
										>
											<Plus className="size-4 text-primary" />
											<span className="text-sm font-medium">Add Vision Model</span>
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
