"use client";

import { useAtomValue } from "jotai";
import {
	Check,
	ChevronDown,
	ChevronRight,
	Edit3,
	Globe,
	ImageIcon,
	Plus,
	Shuffle,
	User,
} from "lucide-react";
import { useCallback, useMemo, useState } from "react";
import { toast } from "sonner";
import {
	createImageGenConfigMutationAtom,
	updateImageGenConfigMutationAtom,
} from "@/atoms/image-gen-config/image-gen-config-mutation.atoms";
import {
	globalImageGenConfigsAtom,
	imageGenConfigsAtom,
} from "@/atoms/image-gen-config/image-gen-config-query.atoms";
import { updateLLMPreferencesMutationAtom } from "@/atoms/new-llm-config/new-llm-config-mutation.atoms";
import { llmPreferencesAtom } from "@/atoms/new-llm-config/new-llm-config-query.atoms";
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
	GlobalImageGenConfig,
	ImageGenerationConfig,
} from "@/contracts/types/new-llm-config.types";
import { cn } from "@/lib/utils";

interface ImageModelSelectorProps {
	className?: string;
	onAddNew?: () => void;
	onEdit?: (config: ImageGenerationConfig | GlobalImageGenConfig, isGlobal: boolean) => void;
}

export function ImageModelSelector({ className, onAddNew, onEdit }: ImageModelSelectorProps) {
	const [open, setOpen] = useState(false);
	const [searchQuery, setSearchQuery] = useState("");

	const { data: globalConfigs, isLoading: globalLoading } =
		useAtomValue(globalImageGenConfigsAtom);
	const { data: userConfigs, isLoading: userLoading } = useAtomValue(imageGenConfigsAtom);
	const { data: preferences, isLoading: prefsLoading } = useAtomValue(llmPreferencesAtom);
	const searchSpaceId = useAtomValue(activeSearchSpaceIdAtom);
	const { mutateAsync: updatePreferences } = useAtomValue(updateLLMPreferencesMutationAtom);

	const isLoading = globalLoading || userLoading || prefsLoading;

	const currentConfig = useMemo(() => {
		if (!preferences) return null;
		const id = preferences.image_generation_config_id;
		if (id === null || id === undefined) return null;
		const globalMatch = globalConfigs?.find((c) => c.id === id);
		if (globalMatch) return globalMatch;
		return userConfigs?.find((c) => c.id === id) ?? null;
	}, [preferences, globalConfigs, userConfigs]);

	const isCurrentAutoMode = useMemo(() => {
		return currentConfig && "is_auto_mode" in currentConfig && currentConfig.is_auto_mode;
	}, [currentConfig]);

	const filteredGlobal = useMemo(() => {
		if (!globalConfigs) return [];
		if (!searchQuery) return globalConfigs;
		const q = searchQuery.toLowerCase();
		return globalConfigs.filter(
			(c) =>
				c.name.toLowerCase().includes(q) ||
				c.model_name.toLowerCase().includes(q) ||
				c.provider.toLowerCase().includes(q)
		);
	}, [globalConfigs, searchQuery]);

	const filteredUser = useMemo(() => {
		if (!userConfigs) return [];
		if (!searchQuery) return userConfigs;
		const q = searchQuery.toLowerCase();
		return userConfigs.filter(
			(c) =>
				c.name.toLowerCase().includes(q) ||
				c.model_name.toLowerCase().includes(q) ||
				c.provider.toLowerCase().includes(q)
		);
	}, [userConfigs, searchQuery]);

	const totalModels = (globalConfigs?.length ?? 0) + (userConfigs?.length ?? 0);

	const handleSelect = useCallback(
		async (configId: number) => {
			if (currentConfig?.id === configId) {
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
		[currentConfig, searchSpaceId, updatePreferences]
	);

	// Don't render if no configs at all
	if (!isLoading && totalModels === 0) {
		return (
			<Button
				variant="outline"
				size="sm"
				onClick={onAddNew}
				className={cn("h-8 gap-2 px-3 text-sm border-border/60", className)}
			>
				<Plus className="size-4 text-teal-600" />
				<span className="hidden md:inline">Add Image Model</span>
			</Button>
		);
	}

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
						<Spinner size="sm" className="text-muted-foreground" />
					) : currentConfig ? (
						<>
							{isCurrentAutoMode ? (
								<Shuffle className="size-4 text-violet-500" />
							) : (
								<ImageIcon className="size-4 text-teal-500" />
							)}
							<span className="max-w-[100px] md:max-w-[120px] truncate hidden md:inline">
								{currentConfig.name}
							</span>
							{isCurrentAutoMode ? (
								<Badge
									variant="secondary"
									className="ml-1 text-[10px] px-1.5 py-0 h-4 bg-violet-100 text-violet-700 dark:bg-violet-900/30 dark:text-violet-300"
								>
									Auto
								</Badge>
							) : (
								<Badge
									variant="secondary"
									className="ml-1 text-[10px] px-1.5 py-0 h-4 bg-teal-50 text-teal-700 dark:bg-teal-900/30 dark:text-teal-300"
								>
									Image
								</Badge>
							)}
						</>
					) : (
						<>
							<ImageIcon className="h-4 w-4 text-muted-foreground" />
							<span className="text-muted-foreground hidden md:inline">Image Model</span>
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
				<Command shouldFilter={false} className="rounded-lg">
					{totalModels > 3 && (
						<div className="flex items-center gap-1 md:gap-2 px-2 md:px-3 py-1.5 md:py-2">
							<CommandInput
								placeholder="Search image models..."
								value={searchQuery}
								onValueChange={setSearchQuery}
								className="h-7 md:h-8 text-xs md:text-sm border-0 bg-transparent focus:ring-0 placeholder:text-muted-foreground/60"
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

						{/* Global Image Gen Configs */}
						{filteredGlobal.length > 0 && (
							<CommandGroup>
								<div className="flex items-center gap-2 px-3 py-2 text-xs font-semibold text-muted-foreground tracking-wider">
									<Globe className="size-3.5" />
									Global Image Models
								</div>
							{filteredGlobal.map((config) => {
								const isSelected = currentConfig?.id === config.id;
								const isAuto = "is_auto_mode" in config && config.is_auto_mode;
								return (
									<CommandItem
										key={`g-${config.id}`}
										value={`g-${config.id}`}
										onSelect={() => handleSelect(config.id)}
										className={cn(
											"mx-2 rounded-lg mb-1 cursor-pointer group transition-all hover:bg-accent/50",
											isSelected && "bg-accent/80",
											isAuto && "border border-violet-200 dark:border-violet-800/50"
										)}
									>
										<div className="flex items-center gap-3 min-w-0 flex-1">
											<div className="shrink-0">
												{isAuto ? (
													<Shuffle className="size-4 text-violet-500" />
												) : (
													<ImageIcon className="size-4 text-teal-500" />
												)}
											</div>
											<div className="min-w-0 flex-1">
												<div className="flex items-center gap-2">
													<span className="font-medium truncate">{config.name}</span>
													{isAuto && (
														<Badge
															variant="secondary"
															className="text-[9px] px-1 py-0 h-3.5 bg-violet-100 text-violet-700 dark:bg-violet-900/30 dark:text-violet-300 border-0"
														>
															Recommended
														</Badge>
													)}
													{isSelected && <Check className="size-3.5 text-primary shrink-0" />}
												</div>
												<span className="text-xs text-muted-foreground truncate block">
													{isAuto ? "Auto load balancing" : config.model_name}
												</span>
											</div>
											{onEdit && (
												<ChevronRight
													className="size-3.5 text-muted-foreground shrink-0 opacity-0 group-hover:opacity-100 transition-opacity cursor-pointer"
													onClick={(e) => {
														e.stopPropagation();
														setOpen(false);
														onEdit(config, true);
													}}
												/>
											)}
										</div>
									</CommandItem>
								);
							})}
							</CommandGroup>
						)}

						{/* User Image Gen Configs */}
						{filteredUser.length > 0 && (
							<>
								{filteredGlobal.length > 0 && <CommandSeparator className="my-1 bg-border/30" />}
								<CommandGroup>
									<div className="flex items-center gap-2 px-3 py-2 text-xs font-semibold text-muted-foreground tracking-wider">
										<User className="size-3.5" />
										Your Image Models
									</div>
								{filteredUser.map((config) => {
									const isSelected = currentConfig?.id === config.id;
									return (
										<CommandItem
											key={`u-${config.id}`}
											value={`u-${config.id}`}
											onSelect={() => handleSelect(config.id)}
											className={cn(
												"mx-2 rounded-lg mb-1 cursor-pointer group transition-all hover:bg-accent/50",
												isSelected && "bg-accent/80"
											)}
										>
											<div className="flex items-center gap-3 min-w-0 flex-1">
												<div className="shrink-0">
													<ImageIcon className="size-4 text-teal-500" />
												</div>
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
												{onEdit && (
													<Button
														variant="ghost"
														size="icon"
														className="h-7 w-7 shrink-0 opacity-0 group-hover:opacity-100 transition-opacity"
														onClick={(e) => {
															e.stopPropagation();
															setOpen(false);
															onEdit(config, false);
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

						{/* Add New */}
						{onAddNew && (
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
									<Plus className="size-4 text-teal-600" />
									<span className="text-sm font-medium">Add Image Model</span>
								</Button>
							</div>
						)}
					</CommandList>
				</Command>
			</PopoverContent>
		</Popover>
	);
}
