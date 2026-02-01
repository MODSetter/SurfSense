"use client";

import { useAtomValue } from "jotai";
import {
	Bot,
	Check,
	ChevronDown,
	Cloud,
	Edit3,
	Globe,
	Plus,
	Settings2,
	Shuffle,
	Sparkles,
	User,
	Zap,
} from "lucide-react";
import { useCallback, useMemo, useState } from "react";
import { toast } from "sonner";
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
import type {
	GlobalNewLLMConfig,
	NewLLMConfigPublic,
} from "@/contracts/types/new-llm-config.types";
import { cn } from "@/lib/utils";

// Provider icons mapping
const getProviderIcon = (provider: string, isAutoMode?: boolean) => {
	const iconClass = "size-4";

	// Special icon for Auto mode
	if (isAutoMode || provider?.toUpperCase() === "AUTO") {
		return <Shuffle className={cn(iconClass, "text-violet-500")} />;
	}

	switch (provider?.toUpperCase()) {
		case "OPENAI":
			return <Sparkles className={cn(iconClass, "text-emerald-500")} />;
		case "ANTHROPIC":
			return <Bot className={cn(iconClass, "text-amber-600")} />;
		case "GOOGLE":
			return <Cloud className={cn(iconClass, "text-blue-500")} />;
		case "GROQ":
			return <Zap className={cn(iconClass, "text-orange-500")} />;
		case "OLLAMA":
			return <Settings2 className={cn(iconClass, "text-gray-500")} />;
		case "XAI":
			return <Bot className={cn(iconClass, "text-violet-500")} />;
		default:
			return <Bot className={cn(iconClass, "text-muted-foreground")} />;
	}
};

interface ModelSelectorProps {
	onEdit: (config: NewLLMConfigPublic | GlobalNewLLMConfig, isGlobal: boolean) => void;
	onAddNew: () => void;
	className?: string;
}

export function ModelSelector({ onEdit, onAddNew, className }: ModelSelectorProps) {
	const [open, setOpen] = useState(false);
	const [searchQuery, setSearchQuery] = useState("");

	// Fetch configs
	const { data: userConfigs, isLoading: userConfigsLoading } = useAtomValue(newLLMConfigsAtom);
	const { data: globalConfigs, isLoading: globalConfigsLoading } =
		useAtomValue(globalNewLLMConfigsAtom);
	const { data: preferences, isLoading: preferencesLoading } = useAtomValue(llmPreferencesAtom);
	const searchSpaceId = useAtomValue(activeSearchSpaceIdAtom);
	const { mutateAsync: updatePreferences } = useAtomValue(updateLLMPreferencesMutationAtom);

	const isLoading = userConfigsLoading || globalConfigsLoading || preferencesLoading;

	// Get current agent LLM config
	const currentConfig = useMemo(() => {
		if (!preferences) return null;

		const agentLlmId = preferences.agent_llm_id;
		if (agentLlmId === null || agentLlmId === undefined) return null;

		// Check if it's Auto mode (ID 0) or global config (negative ID)
		if (agentLlmId <= 0) {
			return globalConfigs?.find((c) => c.id === agentLlmId) ?? null;
		}
		// Otherwise, check user configs
		return userConfigs?.find((c) => c.id === agentLlmId) ?? null;
	}, [preferences, globalConfigs, userConfigs]);

	// Check if current config is Auto mode
	const isCurrentAutoMode = useMemo(() => {
		return currentConfig && "is_auto_mode" in currentConfig && currentConfig.is_auto_mode;
	}, [currentConfig]);

	// Filter configs based on search
	const filteredGlobalConfigs = useMemo(() => {
		if (!globalConfigs) return [];
		if (!searchQuery) return globalConfigs;
		const query = searchQuery.toLowerCase();
		return globalConfigs.filter(
			(c) =>
				c.name.toLowerCase().includes(query) ||
				c.model_name.toLowerCase().includes(query) ||
				c.provider.toLowerCase().includes(query)
		);
	}, [globalConfigs, searchQuery]);

	const filteredUserConfigs = useMemo(() => {
		if (!userConfigs) return [];
		if (!searchQuery) return userConfigs;
		const query = searchQuery.toLowerCase();
		return userConfigs.filter(
			(c) =>
				c.name.toLowerCase().includes(query) ||
				c.model_name.toLowerCase().includes(query) ||
				c.provider.toLowerCase().includes(query)
		);
	}, [userConfigs, searchQuery]);

	// Total model count for conditional search display
	const totalModels = useMemo(() => {
		return (globalConfigs?.length ?? 0) + (userConfigs?.length ?? 0);
	}, [globalConfigs, userConfigs]);

	const handleSelectConfig = useCallback(
		async (config: NewLLMConfigPublic | GlobalNewLLMConfig) => {
			// If already selected, just close
			if (currentConfig?.id === config.id) {
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
					data: {
						agent_llm_id: config.id,
					},
				});
				toast.success(`Switched to ${config.name}`);
				setOpen(false);
			} catch (error) {
				console.error("Failed to switch model:", error);
				toast.error("Failed to switch model");
			}
		},
		[currentConfig, searchSpaceId, updatePreferences]
	);

	const handleEditConfig = useCallback(
		(e: React.MouseEvent, config: NewLLMConfigPublic | GlobalNewLLMConfig, isGlobal: boolean) => {
			e.stopPropagation();
			onEdit(config, isGlobal);
			setOpen(false);
		},
		[onEdit]
	);

	return (
		<Popover open={open} onOpenChange={setOpen}>
			<PopoverTrigger asChild>
				<Button
					variant="outline"
					size="sm"
					role="combobox"
					aria-expanded={open}
					className={cn("h-8 gap-2 px-3 text-sm border-border/60", className)}
				>
					{isLoading ? (
						<>
							<Spinner size="sm" className="text-muted-foreground" />
							<span className="text-muted-foreground hidden md:inline">Loading</span>
						</>
					) : currentConfig ? (
						<>
							{getProviderIcon(currentConfig.provider, isCurrentAutoMode ?? false)}
							<span className="max-w-[100px] md:max-w-[150px] truncate hidden md:inline">
								{currentConfig.name}
							</span>
							{isCurrentAutoMode ? (
								<Badge
									variant="secondary"
									className="ml-1 text-[10px] px-1.5 py-0 h-4 bg-violet-100 text-violet-700 dark:bg-violet-900/30 dark:text-violet-300"
								>
									Balanced
								</Badge>
							) : (
								<Badge variant="secondary" className="ml-1 text-[10px] px-1.5 py-0 h-4 bg-muted/80">
									{currentConfig.model_name.split("/").pop()?.slice(0, 10) ||
										currentConfig.model_name.slice(0, 10)}
								</Badge>
							)}
						</>
					) : (
						<>
							<Bot className="h-4 w-4 text-muted-foreground" />
							<span className="text-muted-foreground hidden md:inline">Select Model</span>
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
				className="w-[280px] md:w-[360px] p-0 rounded-lg shadow-lg border-border/60"
				align="start"
				sideOffset={8}
			>
				<Command
					shouldFilter={false}
					className="rounded-lg relative [&_[data-slot=command-input-wrapper]]:border-0 [&_[data-slot=command-input-wrapper]]:px-0 [&_[data-slot=command-input-wrapper]]:gap-2"
				>
					{totalModels > 3 && (
						<div className="flex items-center gap-1 md:gap-2 px-2 md:px-3 py-1.5 md:py-2">
							<CommandInput
								placeholder="Search models"
								value={searchQuery}
								onValueChange={setSearchQuery}
								className="h-7 md:h-8 text-xs md:text-sm border-0 bg-transparent focus:ring-0 placeholder:text-muted-foreground/60"
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

						{/* Global Configs Section */}
						{filteredGlobalConfigs.length > 0 && (
							<CommandGroup>
								<div className="flex items-center gap-2 px-3 py-2 text-xs font-semibold text-muted-foreground tracking-wider">
									<Globe className="size-3.5" />
									Global Models
								</div>
								{filteredGlobalConfigs.map((config) => {
									const isSelected = currentConfig?.id === config.id;
									const isAutoMode = "is_auto_mode" in config && config.is_auto_mode;
									return (
										<CommandItem
											key={`global-${config.id}`}
											value={`global-${config.id}`}
											onSelect={() => handleSelectConfig(config)}
											className={cn(
												"mx-2 rounded-lg mb-1 cursor-pointer group transition-all",
												"hover:bg-accent/50",
												isSelected && "bg-accent/80",
												isAutoMode && "border border-violet-200 dark:border-violet-800/50"
											)}
										>
											<div className="flex items-center justify-between w-full gap-2">
												<div className="flex items-center gap-3 min-w-0 flex-1">
													<div className="shrink-0">
														{getProviderIcon(config.provider, isAutoMode)}
													</div>
													<div className="min-w-0 flex-1">
														<div className="flex items-center gap-2">
															<span className="font-medium truncate">{config.name}</span>
															{isAutoMode && (
																<Badge
																	variant="secondary"
																	className="text-[9px] px-1 py-0 h-3.5 bg-violet-100 text-violet-700 dark:bg-violet-900/30 dark:text-violet-300 border-0"
																>
																	Recommended
																</Badge>
															)}
															{isSelected && <Check className="size-3.5 text-primary shrink-0" />}
														</div>
														<div className="flex items-center gap-1.5 mt-0.5">
															<span className="text-xs text-muted-foreground truncate">
																{isAutoMode ? "Auto load balancing" : config.model_name}
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
														onClick={(e) => handleEditConfig(e, config, true)}
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

						{filteredGlobalConfigs.length > 0 && filteredUserConfigs.length > 0 && (
							<CommandSeparator className="my-1 bg-border/30" />
						)}

						{/* User Configs Section */}
						{filteredUserConfigs.length > 0 && (
							<CommandGroup>
								<div className="flex items-center gap-2 px-3 py-2 text-xs font-semibold text-muted-foreground tracking-wider">
									<User className="size-3.5" />
									Your Configurations
								</div>
								{filteredUserConfigs.map((config) => {
									const isSelected = currentConfig?.id === config.id;
									return (
										<CommandItem
											key={`user-${config.id}`}
											value={`user-${config.id}`}
											onSelect={() => handleSelectConfig(config)}
											className={cn(
												"mx-2 rounded-lg mb-1 cursor-pointer group transition-all",
												"hover:bg-accent/50",
												isSelected && "bg-accent/80"
											)}
										>
											<div className="flex items-center justify-between w-full gap-2">
												<div className="flex items-center gap-3 min-w-0 flex-1">
													<div className="shrink-0">{getProviderIcon(config.provider)}</div>
													<div className="min-w-0 flex-1">
														<div className="flex items-center gap-2">
															<span className="font-medium truncate">{config.name}</span>
															{isSelected && <Check className="size-3.5 text-primary shrink-0" />}
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
													onClick={(e) => handleEditConfig(e, config, false)}
												>
													<Edit3 className="size-3.5 text-muted-foreground" />
												</Button>
											</div>
										</CommandItem>
									);
								})}
							</CommandGroup>
						)}

						{/* Add New Config Button */}
						<div className="p-2 bg-muted/20">
							<Button
								variant="ghost"
								size="sm"
								className="w-full justify-start gap-2 h-9 rounded-lg hover:bg-accent/50"
								onClick={() => {
									setOpen(false);
									onAddNew();
								}}
							>
								<Plus className="size-4 text-primary" />
								<span className="text-sm font-medium">Add New Configuration</span>
							</Button>
						</div>
					</CommandList>
				</Command>
			</PopoverContent>
		</Popover>
	);
}
