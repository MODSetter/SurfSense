"use client";

import { useAtomValue } from "jotai";
import {
	AlertCircle,
	Check,
	ChevronsUpDown,
	Clock,
	Edit3,
	ImageIcon,
	Key,
	Plus,
	RefreshCw,
	Shuffle,
	Sparkles,
	Trash2,
	Wand2,
} from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import {
	createImageGenConfigMutationAtom,
	deleteImageGenConfigMutationAtom,
	updateImageGenConfigMutationAtom,
} from "@/atoms/image-gen-config/image-gen-config-mutation.atoms";
import {
	globalImageGenConfigsAtom,
	imageGenConfigsAtom,
} from "@/atoms/image-gen-config/image-gen-config-query.atoms";
import { updateLLMPreferencesMutationAtom } from "@/atoms/new-llm-config/new-llm-config-mutation.atoms";
import { llmPreferencesAtom } from "@/atoms/new-llm-config/new-llm-config-query.atoms";
import { Alert, AlertDescription } from "@/components/ui/alert";
import {
	AlertDialog,
	AlertDialogAction,
	AlertDialogCancel,
	AlertDialogContent,
	AlertDialogDescription,
	AlertDialogFooter,
	AlertDialogHeader,
	AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
	Command,
	CommandEmpty,
	CommandGroup,
	CommandInput,
	CommandItem,
	CommandList,
} from "@/components/ui/command";
import {
	Dialog,
	DialogContent,
	DialogDescription,
	DialogHeader,
	DialogTitle,
} from "@/components/ui/dialog";
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
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import {
	IMAGE_GEN_PROVIDERS,
	getImageGenModelsByProvider,
} from "@/contracts/enums/image-gen-providers";
import type { ImageGenerationConfig } from "@/contracts/types/new-llm-config.types";
import { cn } from "@/lib/utils";

interface ImageModelManagerProps {
	searchSpaceId: number;
}

const container = {
	hidden: { opacity: 0 },
	show: { opacity: 1, transition: { staggerChildren: 0.05 } },
};

const item = {
	hidden: { opacity: 0, y: 20 },
	show: { opacity: 1, y: 0 },
};

export function ImageModelManager({ searchSpaceId }: ImageModelManagerProps) {
	// Image gen config atoms
	const { mutateAsync: createConfig, isPending: isCreating, error: createError } =
		useAtomValue(createImageGenConfigMutationAtom);
	const { mutateAsync: updateConfig, isPending: isUpdating, error: updateError } =
		useAtomValue(updateImageGenConfigMutationAtom);
	const { mutateAsync: deleteConfig, isPending: isDeleting, error: deleteError } =
		useAtomValue(deleteImageGenConfigMutationAtom);
	const { mutateAsync: updatePreferences } = useAtomValue(updateLLMPreferencesMutationAtom);

	const { data: userConfigs, isFetching: configsLoading, error: fetchError, refetch: refreshConfigs } =
		useAtomValue(imageGenConfigsAtom);
	const { data: globalConfigs = [], isFetching: globalLoading } =
		useAtomValue(globalImageGenConfigsAtom);
	const { data: preferences = {}, isFetching: prefsLoading } = useAtomValue(llmPreferencesAtom);

	// Local state
	const [isDialogOpen, setIsDialogOpen] = useState(false);
	const [editingConfig, setEditingConfig] = useState<ImageGenerationConfig | null>(null);
	const [configToDelete, setConfigToDelete] = useState<ImageGenerationConfig | null>(null);

	// Preference state
	const [selectedPrefId, setSelectedPrefId] = useState<string | number>(
		preferences.image_generation_config_id ?? ""
	);
	const [hasPrefChanges, setHasPrefChanges] = useState(false);
	const [isSavingPref, setIsSavingPref] = useState(false);

	useEffect(() => {
		setSelectedPrefId(preferences.image_generation_config_id ?? "");
		setHasPrefChanges(false);
	}, [preferences]);

	const isSubmitting = isCreating || isUpdating;
	const isLoading = configsLoading || globalLoading || prefsLoading;
	const errors = [createError, updateError, deleteError, fetchError].filter(Boolean) as Error[];

	// Form state for create/edit dialog
	const [formData, setFormData] = useState({
		name: "",
		description: "",
		provider: "",
		custom_provider: "",
		model_name: "",
		api_key: "",
		api_base: "",
		api_version: "",
	});
	const [modelComboboxOpen, setModelComboboxOpen] = useState(false);

	const resetForm = () => {
		setFormData({
			name: "",
			description: "",
			provider: "",
			custom_provider: "",
			model_name: "",
			api_key: "",
			api_base: "",
			api_version: "",
		});
	};

	const handleFormSubmit = useCallback(async () => {
		if (!formData.name || !formData.provider || !formData.model_name || !formData.api_key) {
			toast.error("Please fill in all required fields");
			return;
		}
		try {
			if (editingConfig) {
				await updateConfig({
					id: editingConfig.id,
					data: {
						name: formData.name,
						description: formData.description || undefined,
						provider: formData.provider as any,
						custom_provider: formData.custom_provider || undefined,
						model_name: formData.model_name,
						api_key: formData.api_key,
						api_base: formData.api_base || undefined,
						api_version: formData.api_version || undefined,
					},
				});
			} else {
				const result = await createConfig({
					name: formData.name,
					description: formData.description || undefined,
					provider: formData.provider as any,
					custom_provider: formData.custom_provider || undefined,
					model_name: formData.model_name,
					api_key: formData.api_key,
					api_base: formData.api_base || undefined,
					api_version: formData.api_version || undefined,
					search_space_id: searchSpaceId,
				});
				// Auto-assign newly created config
				if (result?.id) {
					await updatePreferences({
						search_space_id: searchSpaceId,
						data: { image_generation_config_id: result.id },
					});
				}
			}
			setIsDialogOpen(false);
			setEditingConfig(null);
			resetForm();
		} catch {
			// Error handled by mutation
		}
	}, [editingConfig, formData, searchSpaceId, createConfig, updateConfig, updatePreferences]);

	const handleDelete = async () => {
		if (!configToDelete) return;
		try {
			await deleteConfig(configToDelete.id);
			setConfigToDelete(null);
		} catch {
			// Error handled by mutation
		}
	};

	const openEditDialog = (config: ImageGenerationConfig) => {
		setEditingConfig(config);
		setFormData({
			name: config.name,
			description: config.description || "",
			provider: config.provider,
			custom_provider: config.custom_provider || "",
			model_name: config.model_name,
			api_key: config.api_key,
			api_base: config.api_base || "",
			api_version: config.api_version || "",
		});
		setIsDialogOpen(true);
	};

	const openNewDialog = () => {
		setEditingConfig(null);
		resetForm();
		setIsDialogOpen(true);
	};

	const handlePrefChange = (value: string) => {
		const newVal = value === "unassigned" ? "" : parseInt(value);
		setSelectedPrefId(newVal);
		setHasPrefChanges(newVal !== (preferences.image_generation_config_id ?? ""));
	};

	const handleSavePref = async () => {
		setIsSavingPref(true);
		try {
			await updatePreferences({
				search_space_id: searchSpaceId,
				data: {
					image_generation_config_id:
						typeof selectedPrefId === "string"
							? selectedPrefId ? parseInt(selectedPrefId) : undefined
							: selectedPrefId,
				},
			});
			setHasPrefChanges(false);
			toast.success("Image generation model preference saved!");
		} catch {
			toast.error("Failed to save preference");
		} finally {
			setIsSavingPref(false);
		}
	};

	const allConfigs = [
		...globalConfigs.map((c) => ({ ...c, _source: "global" as const })),
		...(userConfigs ?? []).map((c) => ({ ...c, _source: "user" as const })),
	];

	const selectedProvider = IMAGE_GEN_PROVIDERS.find((p) => p.value === formData.provider);
	const suggestedModels = getImageGenModelsByProvider(formData.provider);

	return (
		<div className="space-y-4 md:space-y-6">
			{/* Header */}
			<div className="flex flex-col space-y-4 sm:flex-row sm:items-center sm:justify-between sm:space-y-0">
				<Button
					variant="outline"
					size="sm"
					onClick={() => refreshConfigs()}
					disabled={isLoading}
					className="flex items-center gap-2 text-xs md:text-sm h-8 md:h-9"
				>
					<RefreshCw className={cn("h-3 w-3 md:h-4 md:w-4", configsLoading && "animate-spin")} />
					Refresh
				</Button>
			</div>

			{/* Errors */}
			<AnimatePresence>
				{errors.map((err) => (
					<motion.div key={err?.message} initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -10 }}>
						<Alert variant="destructive" className="py-3">
							<AlertCircle className="h-3 w-3 md:h-4 md:w-4 shrink-0" />
							<AlertDescription className="text-xs md:text-sm">{err?.message}</AlertDescription>
						</Alert>
					</motion.div>
				))}
			</AnimatePresence>

			{/* Global info */}
			{globalConfigs.filter((g) => !("is_auto_mode" in g && g.is_auto_mode)).length > 0 && (
				<Alert className="border-teal-500/30 bg-teal-500/5 py-3">
					<Sparkles className="h-3 w-3 md:h-4 md:w-4 text-teal-600 dark:text-teal-400 shrink-0" />
					<AlertDescription className="text-teal-800 dark:text-teal-200 text-xs md:text-sm">
						<span className="font-medium">
							{globalConfigs.filter((g) => !("is_auto_mode" in g && g.is_auto_mode)).length} global image model(s)
						</span>{" "}
						available from your administrator.
					</AlertDescription>
				</Alert>
			)}

			{/* Active Preference Card */}
			{!isLoading && allConfigs.length > 0 && (
				<motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}>
					<Card className="border-l-4 border-l-teal-500">
						<CardHeader className="pb-2 px-3 md:px-6 pt-3 md:pt-6">
							<div className="flex items-center gap-2 md:gap-3">
								<div className="p-1.5 md:p-2 rounded-lg bg-teal-100 text-teal-800">
									<ImageIcon className="w-4 h-4 md:w-5 md:h-5" />
								</div>
								<div>
									<CardTitle className="text-base md:text-lg">Active Image Model</CardTitle>
									<CardDescription className="text-xs md:text-sm">
										Select which model to use for image generation
									</CardDescription>
								</div>
							</div>
						</CardHeader>
						<CardContent className="space-y-3 px-3 md:px-6 pb-3 md:pb-6">
							<Select
								value={selectedPrefId?.toString() || "unassigned"}
								onValueChange={handlePrefChange}
							>
								<SelectTrigger className="h-9 md:h-10 text-xs md:text-sm">
									<SelectValue placeholder="Select an image model" />
								</SelectTrigger>
								<SelectContent>
									<SelectItem value="unassigned">
										<span className="text-muted-foreground">Unassigned</span>
									</SelectItem>
									{globalConfigs.length > 0 && (
										<>
											<div className="px-2 py-1.5 text-xs font-semibold text-muted-foreground">Global</div>
											{globalConfigs.map((c) => {
												const isAuto = "is_auto_mode" in c && c.is_auto_mode;
												return (
													<SelectItem key={`g-${c.id}`} value={c.id.toString()}>
														<div className="flex items-center gap-2">
															{isAuto ? (
																<Badge variant="outline" className="text-xs bg-violet-100 text-violet-700 dark:bg-violet-900/30 dark:text-violet-300 border-violet-200">
																	<Shuffle className="size-3 mr-1" />AUTO
																</Badge>
															) : (
																<Badge variant="outline" className="text-xs bg-teal-50 text-teal-700 dark:bg-teal-900/30 dark:text-teal-300 border-teal-200">
																	{c.provider}
																</Badge>
															)}
															<span>{c.name}</span>
														</div>
													</SelectItem>
												);
											})}
										</>
									)}
									{(userConfigs?.length ?? 0) > 0 && (
										<>
											<div className="px-2 py-1.5 text-xs font-semibold text-muted-foreground">Your Models</div>
											{userConfigs?.map((c) => (
												<SelectItem key={`u-${c.id}`} value={c.id.toString()}>
													<div className="flex items-center gap-2">
														<Badge variant="outline" className="text-xs">{c.provider}</Badge>
														<span>{c.name}</span>
														<span className="text-muted-foreground">({c.model_name})</span>
													</div>
												</SelectItem>
											))}
										</>
									)}
								</SelectContent>
							</Select>
							{hasPrefChanges && (
								<div className="flex gap-2 pt-1">
									<Button size="sm" onClick={handleSavePref} disabled={isSavingPref} className="text-xs h-8">
										{isSavingPref ? "Saving..." : "Save"}
									</Button>
									<Button size="sm" variant="outline" onClick={() => { setSelectedPrefId(preferences.image_generation_config_id ?? ""); setHasPrefChanges(false); }} className="text-xs h-8">
										Reset
									</Button>
								</div>
							)}
						</CardContent>
					</Card>
				</motion.div>
			)}

			{/* Loading */}
			{isLoading && (
				<Card>
					<CardContent className="flex items-center justify-center py-10">
						<Spinner size="md" className="text-muted-foreground" />
					</CardContent>
				</Card>
			)}

			{/* User Configs */}
			{!isLoading && (
				<div className="space-y-4 md:space-y-6">
					<div className="flex flex-col space-y-4 sm:flex-row sm:items-center sm:justify-between sm:space-y-0">
						<h3 className="text-lg md:text-xl font-semibold tracking-tight">Your Image Models</h3>
						<Button onClick={openNewDialog} className="flex items-center gap-2 text-xs md:text-sm h-8 md:h-9">
							<Plus className="h-3 w-3 md:h-4 md:w-4" />
							Add Image Model
						</Button>
					</div>

					{(userConfigs?.length ?? 0) === 0 ? (
						<Card className="border-dashed border-2 border-muted-foreground/25">
							<CardContent className="flex flex-col items-center justify-center py-10 md:py-16 text-center">
								<div className="rounded-full bg-gradient-to-br from-teal-500/10 to-cyan-500/10 p-4 md:p-6 mb-4">
									<Wand2 className="h-8 w-8 md:h-12 md:w-12 text-teal-600 dark:text-teal-400" />
								</div>
								<h3 className="text-lg font-semibold mb-2">No Image Models Yet</h3>
								<p className="text-xs md:text-sm text-muted-foreground max-w-sm mb-4">
									Add your own image generation model (DALL-E 3, GPT Image 1, etc.)
								</p>
								<Button onClick={openNewDialog} size="lg" className="gap-2 text-xs md:text-sm">
									<Plus className="h-3 w-3 md:h-4 md:w-4" />
									Add First Image Model
								</Button>
							</CardContent>
						</Card>
					) : (
						<motion.div variants={container} initial="hidden" animate="show" className="grid gap-4">
							<AnimatePresence mode="popLayout">
								{userConfigs?.map((config) => (
									<motion.div key={config.id} variants={item} layout exit={{ opacity: 0, scale: 0.95 }}>
										<Card className="group overflow-hidden hover:shadow-lg transition-all duration-300 border-muted-foreground/10 hover:border-teal-500/30">
											<CardContent className="p-0">
												<div className="flex">
													<div className="w-1 md:w-1.5 bg-gradient-to-b from-teal-500/50 to-cyan-500/50 group-hover:from-teal-500 group-hover:to-cyan-500 transition-colors" />
													<div className="flex-1 p-3 md:p-5">
														<div className="flex items-start justify-between gap-2">
															<div className="flex items-start gap-2 md:gap-4 flex-1 min-w-0">
																<div className="flex h-10 w-10 md:h-12 md:w-12 items-center justify-center rounded-lg md:rounded-xl bg-gradient-to-br from-teal-500/10 to-cyan-500/10 shrink-0">
																	<ImageIcon className="h-5 w-5 md:h-6 md:w-6 text-teal-600 dark:text-teal-400" />
																</div>
																<div className="flex-1 min-w-0 space-y-2">
																	<div className="flex items-center gap-1.5 flex-wrap">
																		<h4 className="text-sm md:text-base font-semibold truncate">{config.name}</h4>
																		<Badge variant="secondary" className="text-[9px] md:text-[10px] px-1.5 py-0.5 bg-teal-500/10 text-teal-700 dark:text-teal-300 border-teal-500/20">
																			{config.provider}
																		</Badge>
																	</div>
																	<code className="text-[10px] md:text-xs font-mono text-muted-foreground bg-muted/50 px-1.5 py-0.5 rounded-md inline-block">
																		{config.model_name}
																	</code>
																	{config.description && (
																		<p className="text-[10px] md:text-xs text-muted-foreground line-clamp-1">{config.description}</p>
																	)}
																	<div className="flex items-center gap-1 text-[10px] md:text-xs text-muted-foreground pt-1">
																		<Clock className="h-2.5 w-2.5 md:h-3 md:w-3" />
																		{new Date(config.created_at).toLocaleDateString()}
																	</div>
																</div>
															</div>
															<div className="flex items-center gap-0.5 shrink-0 opacity-0 group-hover:opacity-100 transition-opacity">
																<TooltipProvider>
																	<Tooltip>
																		<TooltipTrigger asChild>
																			<Button variant="ghost" size="sm" onClick={() => openEditDialog(config)} className="h-7 w-7 p-0 text-muted-foreground hover:text-foreground">
																				<Edit3 className="h-3.5 w-3.5" />
																			</Button>
																		</TooltipTrigger>
																		<TooltipContent>Edit</TooltipContent>
																	</Tooltip>
																</TooltipProvider>
																<TooltipProvider>
																	<Tooltip>
																		<TooltipTrigger asChild>
																			<Button variant="ghost" size="sm" onClick={() => setConfigToDelete(config)} className="h-7 w-7 p-0 text-muted-foreground hover:text-destructive">
																				<Trash2 className="h-3.5 w-3.5" />
																			</Button>
																		</TooltipTrigger>
																		<TooltipContent>Delete</TooltipContent>
																	</Tooltip>
																</TooltipProvider>
															</div>
														</div>
													</div>
												</div>
											</CardContent>
										</Card>
									</motion.div>
								))}
							</AnimatePresence>
						</motion.div>
					)}
				</div>
			)}

			{/* Create/Edit Dialog */}
			<Dialog open={isDialogOpen} onOpenChange={(open) => { if (!open) { setIsDialogOpen(false); setEditingConfig(null); resetForm(); } }}>
				<DialogContent className="max-w-lg max-h-[90vh] overflow-y-auto">
					<DialogHeader>
						<DialogTitle className="flex items-center gap-2">
							{editingConfig ? <Edit3 className="w-5 h-5 text-teal-600" /> : <Plus className="w-5 h-5 text-teal-600" />}
							{editingConfig ? "Edit Image Model" : "Add Image Model"}
						</DialogTitle>
						<DialogDescription>
							{editingConfig ? "Update your image generation model" : "Configure a new image generation model (DALL-E 3, GPT Image 1, etc.)"}
						</DialogDescription>
					</DialogHeader>

					<div className="space-y-4 pt-2">
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
												placeholder="Search or type model name..."
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

						{/* API Base (optional) */}
						<div className="space-y-2">
							<Label className="text-sm font-medium">API Base URL</Label>
							<Input
								placeholder={selectedProvider?.apiBase || "Optional"}
								value={formData.api_base}
								onChange={(e) => setFormData((p) => ({ ...p, api_base: e.target.value }))}
							/>
						</div>

						{/* API Version (Azure) */}
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
							<Button
								variant="outline"
								className="flex-1"
								onClick={() => { setIsDialogOpen(false); setEditingConfig(null); resetForm(); }}
							>
								Cancel
							</Button>
							<Button
								className="flex-1"
								onClick={handleFormSubmit}
								disabled={isSubmitting || !formData.name || !formData.provider || !formData.model_name || !formData.api_key}
							>
								{isSubmitting ? <Spinner size="sm" className="mr-2" /> : null}
								{editingConfig ? "Save Changes" : "Create & Use"}
							</Button>
						</div>
					</div>
				</DialogContent>
			</Dialog>

			{/* Delete Confirmation */}
			<AlertDialog open={!!configToDelete} onOpenChange={(open) => !open && setConfigToDelete(null)}>
				<AlertDialogContent>
					<AlertDialogHeader>
						<AlertDialogTitle className="flex items-center gap-2">
							<Trash2 className="h-5 w-5 text-destructive" />
							Delete Image Model
						</AlertDialogTitle>
						<AlertDialogDescription>
							Are you sure you want to delete <span className="font-semibold text-foreground">{configToDelete?.name}</span>?
						</AlertDialogDescription>
					</AlertDialogHeader>
					<AlertDialogFooter>
						<AlertDialogCancel disabled={isDeleting}>Cancel</AlertDialogCancel>
						<AlertDialogAction onClick={handleDelete} disabled={isDeleting} className="bg-destructive text-destructive-foreground hover:bg-destructive/90">
							{isDeleting ? <><Spinner size="sm" className="mr-2" />Deleting</> : <><Trash2 className="mr-2 h-4 w-4" />Delete</>}
						</AlertDialogAction>
					</AlertDialogFooter>
				</AlertDialogContent>
			</AlertDialog>
		</div>
	);
}
