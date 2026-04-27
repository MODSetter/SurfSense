"use client";

import { useAtomValue } from "jotai";
import {
	AlertCircle,
	Dot,
	FileText,
	Info,
	Pencil,
	RefreshCw,
	Trash2,
} from "lucide-react";
import { useMemo, useState } from "react";
import { membersAtom, myAccessAtom } from "@/atoms/members/members-query.atoms";
import { deleteNewLLMConfigMutationAtom } from "@/atoms/new-llm-config/new-llm-config-mutation.atoms";
import {
	globalNewLLMConfigsAtom,
	newLLMConfigsAtom,
} from "@/atoms/new-llm-config/new-llm-config-query.atoms";
import { ModelConfigDialog } from "@/components/shared/model-config-dialog";
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
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Spinner } from "@/components/ui/spinner";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import type { NewLLMConfig } from "@/contracts/types/new-llm-config.types";
import { useMediaQuery } from "@/hooks/use-media-query";
import { getProviderIcon } from "@/lib/provider-icons";
import { cn } from "@/lib/utils";

interface AgentModelManagerProps {
	searchSpaceId: number;
}

function getInitials(name: string): string {
	const parts = name.trim().split(/\s+/);
	if (parts.length >= 2) {
		return (parts[0][0] + parts[1][0]).toUpperCase();
	}
	return name.slice(0, 2).toUpperCase();
}

export function AgentModelManager({ searchSpaceId }: AgentModelManagerProps) {
	const isDesktop = useMediaQuery("(min-width: 768px)");
	// Mutations
	const { mutateAsync: deleteConfig, isPending: isDeleting } = useAtomValue(
		deleteNewLLMConfigMutationAtom
	);

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

	// Permissions
	const { data: access } = useAtomValue(myAccessAtom);
	const canCreate =
		!!access && (access.is_owner || (access.permissions?.includes("llm_configs:create") ?? false));
	const canUpdate =
		!!access && (access.is_owner || (access.permissions?.includes("llm_configs:update") ?? false));
	const canDelete =
		!!access && (access.is_owner || (access.permissions?.includes("llm_configs:delete") ?? false));
	const isReadOnly = !canCreate && !canUpdate && !canDelete;

	// Local state
	const [isDialogOpen, setIsDialogOpen] = useState(false);
	const [editingConfig, setEditingConfig] = useState<NewLLMConfig | null>(null);
	const [configToDelete, setConfigToDelete] = useState<NewLLMConfig | null>(null);

	const handleDelete = async () => {
		if (!configToDelete) return;
		try {
			await deleteConfig({ id: configToDelete.id, name: configToDelete.name });
			setConfigToDelete(null);
		} catch {
			// Error handled by mutation state
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

	return (
		<div className="space-y-5 md:space-y-6">
			{/* Header actions */}
			<div className="flex items-center justify-between">
				<Button
					variant="secondary"
					size="sm"
					onClick={() => refreshConfigs()}
					disabled={isLoading}
					className="gap-2"
				>
					<RefreshCw className={cn("h-3.5 w-3.5", isLoading && "animate-spin")} />
					Refresh
				</Button>
				{canCreate && (
					<Button
						variant="outline"
						onClick={openNewDialog}
						className="gap-2 bg-white text-black hover:bg-neutral-100 dark:bg-white dark:text-black dark:hover:bg-neutral-200"
					>
						Add Model
					</Button>
				)}
			</div>

			{/* Fetch Error Alert */}
			{fetchError && (
				<div>
					<Alert variant="destructive" className="py-3 md:py-4">
						<AlertCircle className="h-3 w-3 md:h-4 md:w-4 shrink-0" />
						<AlertDescription className="text-xs md:text-sm">
							{fetchError?.message ?? "Failed to load configurations"}
						</AlertDescription>
					</Alert>
				</div>
			)}

			{/* Read-only / Limited permissions notice */}
			{access && !isLoading && isReadOnly && (
				<div>
					<Alert className="bg-muted/50 py-3 md:py-4">
						<Info className="h-3 w-3 md:h-4 md:w-4 shrink-0" />
						<AlertDescription className="text-xs md:text-sm">
							You have <span className="font-medium">read-only</span> access to LLM configurations.
							Contact a space owner to request additional permissions.
						</AlertDescription>
					</Alert>
				</div>
			)}
			{access && !isLoading && !isReadOnly && (!canCreate || !canUpdate || !canDelete) && (
				<div>
					<Alert className="bg-muted/50 py-3 md:py-4">
						<Info className="h-3 w-3 md:h-4 md:w-4 shrink-0" />
						<AlertDescription className="text-xs md:text-sm">
							You can{" "}
							{[canCreate && "create", canUpdate && "edit", canDelete && "delete"]
								.filter(Boolean)
								.join(" and ")}{" "}
							configurations
							{!canDelete && ", but cannot delete them"}.
						</AlertDescription>
					</Alert>
				</div>
			)}

			{/* Global Configs Info */}
			{globalConfigs.length > 0 && (
				<Alert className="bg-muted/50 py-3">
					<Info className="h-3 w-3 md:h-4 md:w-4 shrink-0" />
					<AlertDescription className="text-xs md:text-sm">
						<p>
							<span className="font-medium">
								{globalConfigs.length} global {globalConfigs.length === 1 ? "model" : "models"}
							</span>{" "}
							available from your administrator.
						</p>
					</AlertDescription>
				</Alert>
			)}

			{/* Loading Skeleton */}
			{isLoading && (
				<div className="grid gap-3 grid-cols-1 sm:grid-cols-2 xl:grid-cols-3">
					{["skeleton-a", "skeleton-b", "skeleton-c"].map((key) => (
						<Card key={key} className="border-border/60">
							<CardContent className="p-4 flex flex-col gap-3">
								{/* Header: Icon + Name */}
								<div className="flex items-start gap-2.5">
									<Skeleton className="size-4 rounded-full shrink-0 mt-0.5" />
									<div className="space-y-1.5 flex-1 min-w-0">
										<Skeleton className="h-4 w-28 md:w-32" />
										<Skeleton className="h-3 w-40 md:w-48" />
									</div>
								</div>
								{/* Feature badges */}
								<div className="flex items-center gap-1.5">
									<Skeleton className="h-5 w-20 rounded-full" />
								</div>
								{/* Footer */}
								<div className="flex items-center pt-2 border-t border-border/40">
									<Skeleton className="h-3 w-20 flex-1" />
									<Skeleton className="h-3 w-3 rounded-full shrink-0 mx-1" />
									<div className="flex-1 flex items-center justify-end gap-1.5">
										<Skeleton className="h-4 w-4 rounded-full" />
										<Skeleton className="h-3 w-16" />
									</div>
								</div>
							</CardContent>
						</Card>
					))}
				</div>
			)}

			{/* Configurations List */}
			{!isLoading && (
				<div className="space-y-4">
					{configs?.length === 0 ? (
						<div>
							<Card className="border-0 bg-transparent shadow-none">
								<CardContent className="flex flex-col items-center justify-center py-10 md:py-16 text-center">
									<h3 className="text-sm md:text-base font-semibold mb-2">No Models Yet</h3>
									<p className="text-[11px] md:text-xs text-muted-foreground max-w-sm mb-4">
										{canCreate
											? "Add your first model to power document summarization, chat, and other agent capabilities"
											: "No models have been added to this space yet. Contact a space owner to add one"}
									</p>
								</CardContent>
							</Card>
						</div>
					) : (
						<div className="grid gap-3 grid-cols-1 sm:grid-cols-2 xl:grid-cols-3">
							{configs?.map((config) => {
								const member = config.user_id ? memberMap.get(config.user_id) : null;

								return (
									<div key={config.id}>
										<Card className="group relative overflow-hidden transition-all duration-200 border-border/60 hover:shadow-md h-full">
											<CardContent className="p-4 flex flex-col gap-3 h-full">
												{/* Header: Icon + Name + Actions */}
												<div className="flex items-center justify-between gap-2">
													<div className="flex items-center gap-2.5 min-w-0 flex-1">
														<div className="shrink-0">
															{getProviderIcon(config.provider, { className: "size-4" })}
														</div>
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
													</div>
													{(canUpdate || canDelete) && (
														<div className="flex items-center gap-1 shrink-0 sm:w-0 sm:overflow-hidden sm:group-hover:w-auto sm:opacity-0 sm:group-hover:opacity-100 transition-all duration-150">
															{canUpdate && (
																<TooltipProvider>
																	<Tooltip open={isDesktop ? undefined : false}>
																		<TooltipTrigger asChild>
																			<Button
																				variant="ghost"
																				size="icon"
																				onClick={() => openEditDialog(config)}
																				className="h-7 w-7 rounded-lg text-muted-foreground hover:text-foreground"
																			>
																				<Pencil className="h-3 w-3" />
																			</Button>
																		</TooltipTrigger>
																		<TooltipContent>Edit</TooltipContent>
																	</Tooltip>
																</TooltipProvider>
															)}
															{canDelete && (
																<TooltipProvider>
																	<Tooltip open={isDesktop ? undefined : false}>
																		<TooltipTrigger asChild>
																			<Button
																				variant="ghost"
																				size="icon"
																				onClick={() => setConfigToDelete(config)}
																				className="h-7 w-7 rounded-lg text-muted-foreground hover:text-destructive"
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

												{/* Feature badges */}
												<div className="flex items-center gap-1.5 flex-wrap">
													{config.citations_enabled && (
														<Badge
															variant="secondary"
															className="text-[10px] px-1.5 py-0.5 border-0 text-muted-foreground bg-muted"
														>
															Citations
														</Badge>
													)}
													{!config.use_default_system_instructions &&
														config.system_instructions && (
															<Badge
																variant="secondary"
																className="text-[10px] px-1.5 py-0.5 border-0 text-muted-foreground bg-muted"
															>
																<FileText className="h-2.5 w-2.5 mr-1" />
																Custom
															</Badge>
														)}
												</div>

												{/* Footer: Date + Creator */}
												<div className="flex items-center pt-2 border-t border-border/40 mt-auto">
													<span className="shrink-0 text-[11px] text-muted-foreground/60 whitespace-nowrap">
														{new Date(config.created_at).toLocaleDateString(undefined, {
															year: "numeric",
															month: "short",
															day: "numeric",
														})}
													</span>
													{member && (
														<>
															<Dot className="h-4 w-4 text-muted-foreground/30 shrink-0" />
															<TooltipProvider>
																<Tooltip open={isDesktop ? undefined : false}>
																	<TooltipTrigger asChild>
																		<div className="min-w-0 flex items-center gap-1.5 cursor-default">
																			<Avatar className="size-4.5 shrink-0">
																				{member.avatarUrl && (
																					<AvatarImage src={member.avatarUrl} alt={member.name} />
																				)}
																				<AvatarFallback className="text-[9px]">
																					{getInitials(member.name)}
																				</AvatarFallback>
																			</Avatar>
																			<span className="text-[11px] text-muted-foreground/60 truncate">
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
									</div>
								);
							})}
						</div>
					)}
				</div>
			)}

			{/* Add/Edit Configuration Dialog */}
			<ModelConfigDialog
				open={isDialogOpen}
				onOpenChange={(open) => {
					setIsDialogOpen(open);
					if (!open) setEditingConfig(null);
				}}
				config={editingConfig}
				isGlobal={false}
				searchSpaceId={searchSpaceId}
				mode={editingConfig ? "edit" : "create"}
			/>

			{/* Delete Confirmation Dialog */}
			<AlertDialog
				open={!!configToDelete}
				onOpenChange={(open) => !open && setConfigToDelete(null)}
			>
				<AlertDialogContent className="select-none">
					<AlertDialogHeader>
						<AlertDialogTitle>Delete Model</AlertDialogTitle>
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
								"Delete"
							)}
						</AlertDialogAction>
					</AlertDialogFooter>
				</AlertDialogContent>
			</AlertDialog>
		</div>
	);
}
