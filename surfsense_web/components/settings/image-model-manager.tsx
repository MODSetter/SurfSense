"use client";

import { useAtomValue } from "jotai";
import {
	AlertCircle,
	Check,
	ChevronsUpDown,
	Edit3,
	Info,
	Key,
	Plus,
	RefreshCw,
	Trash2,
	Wand2,
} from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import Image from "next/image";
import { useCallback, useMemo, useState } from "react";
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
import { membersAtom, myAccessAtom } from "@/atoms/members/members-query.atoms";
import { updateLLMPreferencesMutationAtom } from "@/atoms/new-llm-config/new-llm-config-mutation.atoms";
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
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
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
import { Skeleton } from "@/components/ui/skeleton";
import { Spinner } from "@/components/ui/spinner";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import {
	getImageGenModelsByProvider,
	IMAGE_GEN_PROVIDERS,
} from "@/contracts/enums/image-gen-providers";
import type { ImageGenerationConfig } from "@/contracts/types/new-llm-config.types";
import { getProviderIcon } from "@/lib/provider-icons";
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

function getInitials(name: string): string {
	const parts = name.trim().split(/\s+/);
	if (parts.length >= 2) {
		return (parts[0][0] + parts[1][0]).toUpperCase();
	}
	return name.slice(0, 2).toUpperCase();
}

export function ImageModelManager({ searchSpaceId }: ImageModelManagerProps) {
	// Image gen config atoms
	const {
		mutateAsync: createConfig,
		isPending: isCreating,
		error: createError,
	} = useAtomValue(createImageGenConfigMutationAtom);
	const {
		mutateAsync: updateConfig,
		isPending: isUpdating,
		error: updateError,
	} = useAtomValue(updateImageGenConfigMutationAtom);
	const {
		mutateAsync: deleteConfig,
		isPending: isDeleting,
		error: deleteError,
	} = useAtomValue(deleteImageGenConfigMutationAtom);
	const { mutateAsync: updatePreferences } = useAtomValue(updateLLMPreferencesMutationAtom);

	const {
		data: userConfigs,
		isFetching: configsLoading,
		error: fetchError,
		refetch: refreshConfigs,
	} = useAtomValue(imageGenConfigsAtom);
	const { data: globalConfigs = [], isFetching: globalLoading } =
		useAtomValue(globalImageGenConfigsAtom);

	// Members for user resolution
	const { data: members } = useAtomValue(membersAtom);
	const memberMap = useMemo(() => {
		const map = new Map<string, { name: string; email?: string; avatarUrl?: string }>();
		if (members) {
			for (const m of members) {
				map.set(m.user_id, {
					name: m.user_display_name || m.user_email || "Unknown",
					email: m.user_email || undefined,
					avatarUrl: m.user_avatar_url || undefined,
				});
			}
		}
		return map;
	}, [members]);

	// Permissions
	const { data: access } = useAtomValue(myAccessAtom);
	const canCreate = useMemo(() => {
		if (!access) return false;
		if (access.is_owner) return true;
		return access.permissions?.includes("image_generations:create") ?? false;
	}, [access]);
	const canDelete = useMemo(() => {
		if (!access) return false;
		if (access.is_owner) return true;
		return access.permissions?.includes("image_generations:delete") ?? false;
	}, [access]);
	// Backend uses image_generations:create for update as well
	const canUpdate = canCreate;
	const isReadOnly = !canCreate && !canDelete;

	// Local state
	const [isDialogOpen, setIsDialogOpen] = useState(false);
	const [editingConfig, setEditingConfig] = useState<ImageGenerationConfig | null>(null);
	const [configToDelete, setConfigToDelete] = useState<ImageGenerationConfig | null>(null);

	const isSubmitting = isCreating || isUpdating;
	const isLoading = configsLoading || globalLoading;
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
				{canCreate && (
					<Button
						onClick={openNewDialog}
						className="flex items-center gap-2 text-xs md:text-sm h-8 md:h-9"
					>
						Add Image Model
					</Button>
				)}
			</div>

			{/* Errors */}
			<AnimatePresence>
				{errors.map((err) => (
					<motion.div
						key={err?.message}
						initial={{ opacity: 0, y: -10 }}
						animate={{ opacity: 1, y: 0 }}
						exit={{ opacity: 0, y: -10 }}
					>
						<Alert variant="destructive" className="py-3">
							<AlertCircle className="h-3 w-3 md:h-4 md:w-4 shrink-0" />
							<AlertDescription className="text-xs md:text-sm">{err?.message}</AlertDescription>
						</Alert>
					</motion.div>
				))}
			</AnimatePresence>

			{/* Read-only / Limited permissions notice */}
			{access && !isLoading && isReadOnly && (
				<motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }}>
					<Alert className="bg-muted/50 py-3 md:py-4">
						<Info className="h-3 w-3 md:h-4 md:w-4 shrink-0" />
						<AlertDescription className="text-xs md:text-sm">
							You have <span className="font-medium">read-only</span> access to image generation
							configurations. Contact a space owner to request additional permissions.
						</AlertDescription>
					</Alert>
				</motion.div>
			)}
			{access && !isLoading && !isReadOnly && (!canCreate || !canDelete) && (
				<motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }}>
					<Alert className="bg-muted/50 py-3 md:py-4">
						<Info className="h-3 w-3 md:h-4 md:w-4 shrink-0" />
						<AlertDescription className="text-xs md:text-sm">
							You can{" "}
							{[canCreate && "create and edit", canDelete && "delete"]
								.filter(Boolean)
								.join(" and ")}{" "}
							image model configurations
							{!canDelete && ", but cannot delete them"}.
						</AlertDescription>
					</Alert>
				</motion.div>
			)}

			{/* Global info */}
			{globalConfigs.filter((g) => !("is_auto_mode" in g && g.is_auto_mode)).length > 0 && (
				<Alert className="flex flex-row items-center gap-2 bg-muted/50 py-3 [&>svg]:static [&>svg+div]:translate-y-0 [&>svg~*]:pl-0">
					<Info className="h-3 w-3 md:h-4 md:w-4 shrink-0" />
					<AlertDescription className="text-xs md:text-sm">
						<span className="font-medium">
							{globalConfigs.filter((g) => !("is_auto_mode" in g && g.is_auto_mode)).length} global
							image model(s)
						</span>{" "}
						available from your administrator.
					</AlertDescription>
				</Alert>
			)}

			{/* Loading Skeleton */}
			{isLoading && (
				<div className="space-y-4 md:space-y-6">
					{/* Your Image Models Section Skeleton */}
					<div className="space-y-4">
						<div className="flex items-center justify-between">
							<Skeleton className="h-6 md:h-7 w-40 md:w-48" />
							<Skeleton className="h-8 md:h-9 w-32 md:w-36 rounded-md" />
						</div>

						{/* Cards Grid Skeleton */}
						<div className="grid gap-3 grid-cols-1 sm:grid-cols-2 xl:grid-cols-3">
							{["skeleton-a", "skeleton-b", "skeleton-c"].map((key) => (
								<Card key={key} className="border-border/60">
									<CardContent className="p-4 flex flex-col gap-3">
										{/* Header */}
										<div className="flex items-start justify-between gap-2">
											<div className="space-y-1.5 flex-1 min-w-0">
												<Skeleton className="h-4 w-28 md:w-32" />
												<Skeleton className="h-3 w-40 md:w-48" />
											</div>
										</div>
										{/* Provider + Model */}
										<div className="flex items-center gap-2">
											<Skeleton className="h-5 w-16 rounded-full" />
											<Skeleton className="h-5 w-24 rounded-md" />
										</div>
										{/* Footer */}
										<div className="flex items-center gap-2 pt-2 border-t border-border/40">
											<Skeleton className="h-3 w-20" />
											<Skeleton className="h-4 w-4 rounded-full" />
											<Skeleton className="h-3 w-16" />
										</div>
									</CardContent>
								</Card>
							))}
						</div>
					</div>
				</div>
			)}

			{/* User Configs */}
			{!isLoading && (
				<div className="space-y-4 md:space-y-6">
					{(userConfigs?.length ?? 0) === 0 ? (
						<Card className="border-dashed border-2 border-muted-foreground/25">
							<CardContent className="flex flex-col items-center justify-center py-10 md:py-16 text-center">
								<div className="rounded-full bg-gradient-to-br from-teal-500/10 to-cyan-500/10 p-4 md:p-6 mb-4">
									<Wand2 className="h-8 w-8 md:h-12 md:w-12 text-teal-600 dark:text-teal-400" />
								</div>
								<h3 className="text-lg font-semibold mb-2">No Image Models Yet</h3>
								<p className="text-xs md:text-sm text-muted-foreground max-w-sm mb-4">
									{canCreate
										? "Add your own image generation model (DALL-E 3, GPT Image 1, etc.)"
										: "No image models have been added to this space yet. Contact a space owner to add one."}
								</p>
								{canCreate && (
									<Button
										onClick={openNewDialog}
										size="lg"
										className="gap-2 text-xs md:text-sm h-9 md:h-10"
									>
										<Plus className="h-3 w-3 md:h-4 md:w-4" />
										Add First Image Model
									</Button>
								)}
							</CardContent>
						</Card>
					) : (
						<motion.div
							variants={container}
							initial="hidden"
							animate="show"
							className="grid gap-3 grid-cols-1 sm:grid-cols-2 xl:grid-cols-3"
						>
							<AnimatePresence mode="popLayout">
								{userConfigs?.map((config) => {
									const member = config.user_id ? memberMap.get(config.user_id) : null;

									return (
										<motion.div
											key={config.id}
											variants={item}
											layout
											exit={{ opacity: 0, scale: 0.95 }}
										>
											<Card className="group relative overflow-hidden transition-all duration-200 border-border/60 hover:shadow-md h-full">
												<CardContent className="p-4 flex flex-col gap-3 h-full">
													{/* Header: Name + Actions */}
													<div className="flex items-start justify-between gap-2">
														<div className="min-w-0 flex-1">
															<h4 className="text-sm font-semibold tracking-tight truncate">
																{config.name}
															</h4>
															{config.description && (
																<p className="text-[11px] text-muted-foreground/70 truncate mt-0.5">
																	{config.description}
																</p>
															)}
														</div>
														{(canUpdate || canDelete) && (
															<div className="flex items-center gap-0.5 shrink-0 sm:opacity-0 sm:group-hover:opacity-100 transition-opacity duration-150">
																{canUpdate && (
																	<TooltipProvider>
																		<Tooltip>
																			<TooltipTrigger asChild>
																				<Button
																					variant="ghost"
																					size="icon"
																					onClick={() => openEditDialog(config)}
																					className="h-7 w-7 text-muted-foreground hover:text-foreground"
																				>
																					<Edit3 className="h-3 w-3" />
																				</Button>
																			</TooltipTrigger>
																			<TooltipContent>Edit</TooltipContent>
																		</Tooltip>
																	</TooltipProvider>
																)}
																{canDelete && (
																	<TooltipProvider>
																		<Tooltip>
																			<TooltipTrigger asChild>
																				<Button
																					variant="ghost"
																					size="icon"
																					onClick={() => setConfigToDelete(config)}
																					className="h-7 w-7 text-muted-foreground hover:text-destructive"
																				>
																					<Trash2 className="h-3 w-3" />
																				</Button>
																			</TooltipTrigger>
																			<TooltipContent>Delete</TooltipContent>
																		</Tooltip>
																	</TooltipProvider>
																)}
															</div>
														)}
													</div>

													{/* Provider + Model */}
													<div className="flex items-center gap-2 flex-wrap">
														{getProviderIcon(config.provider, { className: "size-3.5 shrink-0" })}
														<code className="text-[11px] font-mono text-muted-foreground bg-muted/60 px-2 py-0.5 rounded-md truncate max-w-[160px]">
															{config.model_name}
														</code>
													</div>

													{/* Footer: Date + Creator */}
													<div className="flex items-center gap-2 pt-2 border-t border-border/40 mt-auto">
														<span className="text-[11px] text-muted-foreground/60">
															{new Date(config.created_at).toLocaleDateString(undefined, {
																year: "numeric",
																month: "short",
																day: "numeric",
															})}
														</span>
														{member && (
															<>
																<span className="text-muted-foreground/30">·</span>
																<TooltipProvider>
																	<Tooltip>
																		<TooltipTrigger asChild>
																			<div className="flex items-center gap-1.5 cursor-default">
																				{member.avatarUrl ? (
																					<Image
																						src={member.avatarUrl}
																						alt={member.name}
																						width={18}
																						height={18}
																						className="h-4.5 w-4.5 rounded-full object-cover shrink-0"
																					/>
																				) : (
																					<div className="flex h-4.5 w-4.5 items-center justify-center rounded-full bg-gradient-to-br from-primary/20 to-primary/5 shrink-0">
																						<span className="text-[9px] font-semibold text-primary">
																							{getInitials(member.name)}
																						</span>
																					</div>
																				)}
																				<span className="text-[11px] text-muted-foreground/60 truncate max-w-[120px]">
																					{member.name}
																				</span>
																			</div>
																		</TooltipTrigger>
																		<TooltipContent side="bottom">
																			{member.email || member.name}
																		</TooltipContent>
																	</Tooltip>
																</TooltipProvider>
															</>
														)}
													</div>
												</CardContent>
											</Card>
										</motion.div>
									);
								})}
							</AnimatePresence>
						</motion.div>
					)}
				</div>
			)}

			{/* Create/Edit Dialog */}
			<Dialog
				open={isDialogOpen}
				onOpenChange={(open) => {
					if (!open) {
						setIsDialogOpen(false);
						setEditingConfig(null);
						resetForm();
					}
				}}
			>
				<DialogContent
					className="max-w-lg max-h-[90vh] overflow-y-auto"
					onOpenAutoFocus={(e) => e.preventDefault()}
				>
					<DialogHeader>
						<DialogTitle>{editingConfig ? "Edit Image Model" : "Add Image Model"}</DialogTitle>
						<DialogDescription>
							{editingConfig
								? "Update your image generation model"
								: "Configure a new image generation model (DALL-E 3, GPT Image 1, etc.)"}
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
								onValueChange={(val) =>
									setFormData((p) => ({ ...p, provider: val, model_name: "" }))
								}
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
										<Button
											variant="outline"
											role="combobox"
											className="w-full justify-between font-normal"
										>
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
													<span className="text-xs text-muted-foreground">
														Type a custom model name
													</span>
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
															<Check
																className={cn(
																	"mr-2 h-4 w-4",
																	formData.model_name === m.value ? "opacity-100" : "opacity-0"
																)}
															/>
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
								onClick={() => {
									setIsDialogOpen(false);
									setEditingConfig(null);
									resetForm();
								}}
							>
								Cancel
							</Button>
							<Button
								className="flex-1"
								onClick={handleFormSubmit}
								disabled={
									isSubmitting ||
									!formData.name ||
									!formData.provider ||
									!formData.model_name ||
									!formData.api_key
								}
							>
								{isSubmitting ? <Spinner size="sm" className="mr-2" /> : null}
								{editingConfig ? "Save Changes" : "Create & Use"}
							</Button>
						</div>
					</div>
				</DialogContent>
			</Dialog>

			{/* Delete Confirmation */}
			<AlertDialog
				open={!!configToDelete}
				onOpenChange={(open) => !open && setConfigToDelete(null)}
			>
				<AlertDialogContent>
					<AlertDialogHeader>
						<AlertDialogTitle className="flex items-center gap-2">
							<Trash2 className="h-5 w-5 text-destructive" />
							Delete Image Model
						</AlertDialogTitle>
						<AlertDialogDescription>
							Are you sure you want to delete{" "}
							<span className="font-semibold text-foreground">{configToDelete?.name}</span>?
						</AlertDialogDescription>
					</AlertDialogHeader>
					<AlertDialogFooter>
						<AlertDialogCancel disabled={isDeleting}>Cancel</AlertDialogCancel>
						<AlertDialogAction
							onClick={handleDelete}
							disabled={isDeleting}
							className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
						>
							{isDeleting ? (
								<>
									<Spinner size="sm" className="mr-2" />
									Deleting
								</>
							) : (
								<>
									<Trash2 className="mr-2 h-4 w-4" />
									Delete
								</>
							)}
						</AlertDialogAction>
					</AlertDialogFooter>
				</AlertDialogContent>
			</AlertDialog>
		</div>
	);
}
