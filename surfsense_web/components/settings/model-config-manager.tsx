"use client";

import { useAtomValue } from "jotai";
import {
	AlertCircle,
	Edit3,
	FileText,
	MessageSquareQuote,
	Plus,
	RefreshCw,
	Info,
	Trash2,
	Wand2,
} from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import Image from "next/image";
import { useCallback, useMemo, useState } from "react";
import { membersAtom } from "@/atoms/members/members-query.atoms";
import {
	createNewLLMConfigMutationAtom,
	deleteNewLLMConfigMutationAtom,
	updateNewLLMConfigMutationAtom,
} from "@/atoms/new-llm-config/new-llm-config-mutation.atoms";
import {
	globalNewLLMConfigsAtom,
	newLLMConfigsAtom,
} from "@/atoms/new-llm-config/new-llm-config-query.atoms";
import { LLMConfigForm, type LLMConfigFormData } from "@/components/shared/llm-config-form";
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
import { Card, CardContent } from "@/components/ui/card";
import {
	Dialog,
	DialogContent,
	DialogDescription,
	DialogHeader,
	DialogTitle,
} from "@/components/ui/dialog";
import { Spinner } from "@/components/ui/spinner";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import type { NewLLMConfig } from "@/contracts/types/new-llm-config.types";
import { cn } from "@/lib/utils";

interface ModelConfigManagerProps {
	searchSpaceId: number;
}

const container = {
	hidden: { opacity: 0 },
	show: {
		opacity: 1,
		transition: {
			staggerChildren: 0.05,
		},
	},
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

export function ModelConfigManager({ searchSpaceId }: ModelConfigManagerProps) {
	// Mutations
	const {
		mutateAsync: createConfig,
		isPending: isCreating,
		error: createError,
	} = useAtomValue(createNewLLMConfigMutationAtom);
	const {
		mutateAsync: updateConfig,
		isPending: isUpdating,
		error: updateError,
	} = useAtomValue(updateNewLLMConfigMutationAtom);
	const {
		mutateAsync: deleteConfig,
		isPending: isDeleting,
		error: deleteError,
	} = useAtomValue(deleteNewLLMConfigMutationAtom);

	// Queries
	const {
		data: configs,
		isFetching: isLoading,
		error: fetchError,
		refetch: refreshConfigs,
	} = useAtomValue(newLLMConfigsAtom);
	const { data: globalConfigs = [] } = useAtomValue(globalNewLLMConfigsAtom);

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

	// Local state
	const [isDialogOpen, setIsDialogOpen] = useState(false);
	const [editingConfig, setEditingConfig] = useState<NewLLMConfig | null>(null);
	const [configToDelete, setConfigToDelete] = useState<NewLLMConfig | null>(null);

	const isSubmitting = isCreating || isUpdating;
	const errors = [createError, updateError, deleteError, fetchError].filter(Boolean) as Error[];

	const handleFormSubmit = useCallback(
		async (formData: LLMConfigFormData) => {
			try {
				if (editingConfig) {
					const { search_space_id, ...updateData } = formData;
					await updateConfig({
						id: editingConfig.id,
						data: updateData,
					});
				} else {
					await createConfig(formData);
				}
				setIsDialogOpen(false);
				setEditingConfig(null);
			} catch {
				// Error handled by mutation
			}
		},
		[editingConfig, createConfig, updateConfig]
	);

	const handleDelete = async () => {
		if (!configToDelete) return;
		try {
			await deleteConfig({ id: configToDelete.id });
			setConfigToDelete(null);
		} catch {
			// Error handled by mutation
		}
	};

	const openEditDialog = (config: NewLLMConfig) => {
		setEditingConfig(config);
		setIsDialogOpen(true);
	};

	const openNewDialog = () => {
		setEditingConfig(null);
		setIsDialogOpen(true);
	};

	const closeDialog = () => {
		setIsDialogOpen(false);
		setEditingConfig(null);
	};

	return (
		<div className="space-y-5 md:space-y-6">
			{/* Header actions */}
			<div className="flex items-center justify-between">
				<Button
					variant="outline"
					size="sm"
					onClick={() => refreshConfigs()}
					disabled={isLoading}
					className="flex items-center gap-2 text-xs md:text-sm h-8 md:h-9"
				>
					<RefreshCw className={cn("h-3 w-3 md:h-4 md:w-4", isLoading && "animate-spin")} />
					Refresh
				</Button>
				<Button
					onClick={openNewDialog}
					size="sm"
					className="flex items-center gap-2 text-xs md:text-sm h-8 md:h-9"
				>
					<Plus className="h-3 w-3 md:h-4 md:w-4" />
					Add Configuration
				</Button>
			</div>

			{/* Error Alerts */}
			<AnimatePresence>
				{errors.length > 0 &&
					errors.map((err) => (
						<motion.div
							key={err?.message ?? `error-${Date.now()}-${Math.random()}`}
							initial={{ opacity: 0, y: -10 }}
							animate={{ opacity: 1, y: 0 }}
							exit={{ opacity: 0, y: -10 }}
						>
							<Alert variant="destructive" className="py-3 md:py-4">
								<AlertCircle className="h-3 w-3 md:h-4 md:w-4 shrink-0" />
								<AlertDescription className="text-xs md:text-sm">
									{err?.message ?? "Something went wrong"}
								</AlertDescription>
							</Alert>
						</motion.div>
					))}
			</AnimatePresence>

			{/* Global Configs Info */}
			{globalConfigs.length > 0 && (
				<motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }}>
					<Alert className="bg-muted/50 py-3 md:py-4">
						<Info className="h-3 w-3 md:h-4 md:w-4 shrink-0" />
						<AlertDescription className="text-xs md:text-sm">
							<span className="font-medium">{globalConfigs.length} global configuration(s)</span>{" "}
							available from your administrator. These are pre-configured and ready to use.{" "}
							<span className="text-muted-foreground">
								Global configs: {globalConfigs.map((g) => g.name).join(", ")}
							</span>
						</AlertDescription>
					</Alert>
				</motion.div>
			)}

			{/* Loading State */}
			{isLoading && (
				<Card>
					<CardContent className="flex items-center justify-center py-10 md:py-16">
						<div className="flex flex-col items-center gap-2 md:gap-3">
							<Spinner size="md" className="md:h-8 md:w-8 text-muted-foreground" />
							<span className="text-xs md:text-sm text-muted-foreground">
								Loading configurations...
							</span>
						</div>
					</CardContent>
				</Card>
			)}

			{/* Configurations List */}
			{!isLoading && (
				<div className="space-y-4">
					{configs?.length === 0 ? (
						<motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}>
							<Card className="border-dashed border-2 border-muted-foreground/25">
								<CardContent className="flex flex-col items-center justify-center py-10 md:py-16 text-center">
									<div className="rounded-full bg-gradient-to-br from-violet-500/10 to-purple-500/10 p-4 md:p-6 mb-4 md:mb-6">
										<Wand2 className="h-8 w-8 md:h-12 md:w-12 text-violet-600 dark:text-violet-400" />
									</div>
									<div className="space-y-2 mb-4 md:mb-6">
										<h3 className="text-lg md:text-xl font-semibold">No Configurations Yet</h3>
										<p className="text-xs md:text-sm text-muted-foreground max-w-sm">
											Create your first AI configuration to customize how your agent responds
										</p>
									</div>
									<Button
										onClick={openNewDialog}
										size="lg"
										className="gap-2 text-xs md:text-sm h-9 md:h-10"
									>
										<Plus className="h-3 w-3 md:h-4 md:w-4" />
										Create First Configuration
									</Button>
								</CardContent>
							</Card>
						</motion.div>
					) : (
						<motion.div
							variants={container}
							initial="hidden"
							animate="show"
							className="grid gap-3 grid-cols-1 sm:grid-cols-2 xl:grid-cols-3"
						>
							<AnimatePresence mode="popLayout">
								{configs?.map((config) => {
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
														<div className="flex items-center gap-0.5 shrink-0 sm:opacity-0 sm:group-hover:opacity-100 transition-opacity duration-150">
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
														</div>
													</div>

													{/* Provider + Model */}
													<div className="flex items-center gap-2 flex-wrap">
														<Badge
															variant="secondary"
															className="text-[10px] font-medium px-2 py-0.5 bg-violet-500/10 text-violet-700 dark:text-violet-300 border-violet-500/20"
														>
															{config.provider}
														</Badge>
														<code className="text-[11px] font-mono text-muted-foreground bg-muted/60 px-2 py-0.5 rounded-md truncate max-w-[160px]">
															{config.model_name}
														</code>
													</div>

													{/* Feature badges */}
													<div className="flex items-center gap-1.5 flex-wrap">
														{config.citations_enabled && (
															<Badge
																variant="outline"
																className="text-[10px] px-1.5 py-0.5 border-emerald-500/30 text-emerald-700 dark:text-emerald-300 bg-emerald-500/5"
															>
																<MessageSquareQuote className="h-2.5 w-2.5 mr-1" />
																Citations
															</Badge>
														)}
														{!config.use_default_system_instructions &&
															config.system_instructions && (
																<Badge
																	variant="outline"
																	className="text-[10px] px-1.5 py-0.5 border-blue-500/30 text-blue-700 dark:text-blue-300 bg-blue-500/5"
																>
																	<FileText className="h-2.5 w-2.5 mr-1" />
																	Custom
																</Badge>
															)}
													</div>

													{/* Footer: Date + Creator */}
													<div className="flex items-center gap-2 pt-2 border-t border-border/40 mt-auto">
														<span className="text-[11px] text-muted-foreground/60">
															{new Date(config.created_at).toLocaleDateString(
																undefined,
																{
																	year: "numeric",
																	month: "short",
																	day: "numeric",
																}
															)}
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
																				<span className="text-[11px] text-muted-foreground/60 truncate max-w-[80px]">
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

			{/* Add/Edit Configuration Dialog */}
			<Dialog open={isDialogOpen} onOpenChange={(open) => !open && closeDialog()}>
				<DialogContent
					className="max-w-2xl max-h-[90vh] overflow-y-auto"
					onOpenAutoFocus={(e) => e.preventDefault()}
				>
					<DialogHeader>
						<DialogTitle className="flex items-center gap-2">
							{editingConfig ? (
								<Edit3 className="w-5 h-5 text-violet-600" />
							) : (
								<Plus className="w-5 h-5 text-violet-600" />
							)}
							{editingConfig ? "Edit Configuration" : "Create New Configuration"}
						</DialogTitle>
						<DialogDescription>
							{editingConfig
								? "Update your AI model and prompt configuration"
								: "Set up a new AI model with custom prompts and citation settings"}
						</DialogDescription>
					</DialogHeader>

					<LLMConfigForm
						key={editingConfig ? `edit-${editingConfig.id}` : "create"}
						searchSpaceId={searchSpaceId}
						initialData={
							editingConfig
								? {
										name: editingConfig.name,
										description: editingConfig.description || "",
										provider: editingConfig.provider,
										custom_provider: editingConfig.custom_provider || "",
										model_name: editingConfig.model_name,
										api_key: editingConfig.api_key,
										api_base: editingConfig.api_base || "",
										litellm_params: editingConfig.litellm_params || {},
										system_instructions: editingConfig.system_instructions || "",
										use_default_system_instructions: editingConfig.use_default_system_instructions,
										citations_enabled: editingConfig.citations_enabled,
									}
								: {
										citations_enabled: true,
										use_default_system_instructions: true,
									}
						}
						onSubmit={handleFormSubmit}
						onCancel={closeDialog}
						isSubmitting={isSubmitting}
						mode={editingConfig ? "edit" : "create"}
						showAdvanced={true}
						compact={true}
					/>
				</DialogContent>
			</Dialog>

			{/* Delete Confirmation Dialog */}
			<AlertDialog
				open={!!configToDelete}
				onOpenChange={(open) => !open && setConfigToDelete(null)}
			>
				<AlertDialogContent>
					<AlertDialogHeader>
						<AlertDialogTitle className="flex items-center gap-2">
							<Trash2 className="h-5 w-5 text-destructive" />
							Delete Configuration
						</AlertDialogTitle>
						<AlertDialogDescription>
							Are you sure you want to delete{" "}
							<span className="font-semibold text-foreground">{configToDelete?.name}</span>? This
							action cannot be undone.
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
