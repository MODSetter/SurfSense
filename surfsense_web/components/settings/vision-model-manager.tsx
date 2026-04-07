"use client";

import { useAtomValue } from "jotai";
import { AlertCircle, Dot, Edit3, Info, RefreshCw, Trash2 } from "lucide-react";
import { useMemo, useState } from "react";
import { membersAtom, myAccessAtom } from "@/atoms/members/members-query.atoms";
import { deleteVisionLLMConfigMutationAtom } from "@/atoms/vision-llm-config/vision-llm-config-mutation.atoms";
import {
	globalVisionLLMConfigsAtom,
	visionLLMConfigsAtom,
} from "@/atoms/vision-llm-config/vision-llm-config-query.atoms";
import { VisionConfigDialog } from "@/components/shared/vision-config-dialog";
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
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Spinner } from "@/components/ui/spinner";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import type { VisionLLMConfig } from "@/contracts/types/new-llm-config.types";
import { useMediaQuery } from "@/hooks/use-media-query";
import { getProviderIcon } from "@/lib/provider-icons";
import { cn } from "@/lib/utils";

interface VisionModelManagerProps {
	searchSpaceId: number;
}

function getInitials(name: string): string {
	const parts = name.trim().split(/\s+/);
	if (parts.length >= 2) {
		return (parts[0][0] + parts[1][0]).toUpperCase();
	}
	return name.slice(0, 2).toUpperCase();
}

export function VisionModelManager({ searchSpaceId }: VisionModelManagerProps) {
	const isDesktop = useMediaQuery("(min-width: 768px)");

	const {
		mutateAsync: deleteConfig,
		isPending: isDeleting,
		error: deleteError,
	} = useAtomValue(deleteVisionLLMConfigMutationAtom);

	const {
		data: userConfigs,
		isFetching: configsLoading,
		error: fetchError,
		refetch: refreshConfigs,
	} = useAtomValue(visionLLMConfigsAtom);
	const { data: globalConfigs = [], isFetching: globalLoading } = useAtomValue(
		globalVisionLLMConfigsAtom
	);

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

	const { data: access } = useAtomValue(myAccessAtom);
	const canCreate = useMemo(() => {
		if (!access) return false;
		if (access.is_owner) return true;
		return access.permissions?.includes("vision_configs:create") ?? false;
	}, [access]);
	const canDelete = useMemo(() => {
		if (!access) return false;
		if (access.is_owner) return true;
		return access.permissions?.includes("vision_configs:delete") ?? false;
	}, [access]);
	const canUpdate = canCreate;
	const isReadOnly = !canCreate && !canDelete;

	const [isDialogOpen, setIsDialogOpen] = useState(false);
	const [editingConfig, setEditingConfig] = useState<VisionLLMConfig | null>(null);
	const [configToDelete, setConfigToDelete] = useState<VisionLLMConfig | null>(null);

	const isLoading = configsLoading || globalLoading;
	const errors = [deleteError, fetchError].filter(Boolean) as Error[];

	const openEditDialog = (config: VisionLLMConfig) => {
		setEditingConfig(config);
		setIsDialogOpen(true);
	};

	const openNewDialog = () => {
		setEditingConfig(null);
		setIsDialogOpen(true);
	};

	const handleDelete = async () => {
		if (!configToDelete) return;
		try {
			await deleteConfig({ id: configToDelete.id, name: configToDelete.name });
			setConfigToDelete(null);
		} catch {
			// Error handled by mutation
		}
	};

	return (
		<div className="space-y-4 md:space-y-6">
			<div className="flex flex-col space-y-4 sm:flex-row sm:items-center sm:justify-between sm:space-y-0">
				<Button
					variant="secondary"
					size="sm"
					onClick={() => refreshConfigs()}
					disabled={isLoading}
					className="gap-2"
				>
					<RefreshCw className={cn("h-3.5 w-3.5", configsLoading && "animate-spin")} />
					Refresh
				</Button>
				{canCreate && (
					<Button
						variant="outline"
						onClick={openNewDialog}
						className="gap-2 bg-white text-black hover:bg-neutral-100 dark:bg-white dark:text-black dark:hover:bg-neutral-200"
					>
						Add Vision Model
					</Button>
				)}
			</div>

			{errors.map((err) => (
				<div key={err?.message}>
					<Alert variant="destructive" className="py-3">
						<AlertCircle className="h-3 w-3 md:h-4 md:w-4 shrink-0" />
						<AlertDescription className="text-xs md:text-sm">{err?.message}</AlertDescription>
					</Alert>
				</div>
			))}

			{access && !isLoading && isReadOnly && (
				<div>
					<Alert className="bg-muted/50 py-3 md:py-4">
						<Info className="h-3 w-3 md:h-4 md:w-4 shrink-0" />
						<AlertDescription className="text-xs md:text-sm">
							You have <span className="font-medium">read-only</span> access to vision model
							configurations. Contact a space owner to request additional permissions.
						</AlertDescription>
					</Alert>
				</div>
			)}
			{access && !isLoading && !isReadOnly && (!canCreate || !canDelete) && (
				<div>
					<Alert className="bg-muted/50 py-3 md:py-4">
						<Info className="h-3 w-3 md:h-4 md:w-4 shrink-0" />
						<AlertDescription className="text-xs md:text-sm">
							You can{" "}
							{[canCreate && "create and edit", canDelete && "delete"]
								.filter(Boolean)
								.join(" and ")}{" "}
							vision model configurations
							{!canDelete && ", but cannot delete them"}.
						</AlertDescription>
					</Alert>
				</div>
			)}

			{globalConfigs.filter((g) => !("is_auto_mode" in g && g.is_auto_mode)).length > 0 && (
				<Alert className="bg-muted/50 py-3">
					<Info className="h-3 w-3 md:h-4 md:w-4 shrink-0" />
					<AlertDescription className="text-xs md:text-sm">
						<p>
							<span className="font-medium">
								{globalConfigs.filter((g) => !("is_auto_mode" in g && g.is_auto_mode)).length}{" "}
								global vision{" "}
								{globalConfigs.filter((g) => !("is_auto_mode" in g && g.is_auto_mode)).length === 1
									? "model"
									: "models"}
							</span>{" "}
							available from your administrator. Use the model selector to view and select them.
						</p>
					</AlertDescription>
				</Alert>
			)}

			{isLoading && (
				<div className="space-y-4 md:space-y-6">
					<div className="space-y-4">
						<div className="flex items-center justify-between">
							<Skeleton className="h-6 md:h-7 w-40 md:w-48" />
							<Skeleton className="h-8 md:h-9 w-32 md:w-36 rounded-md" />
						</div>
						<div className="grid gap-3 grid-cols-1 sm:grid-cols-2 xl:grid-cols-3">
							{["skeleton-a", "skeleton-b", "skeleton-c"].map((key) => (
								<Card key={key} className="border-border/60">
									<CardContent className="p-4 flex flex-col gap-3">
										<div className="flex items-start justify-between gap-2">
											<div className="space-y-1.5 flex-1 min-w-0">
												<Skeleton className="h-4 w-28 md:w-32" />
												<Skeleton className="h-3 w-40 md:w-48" />
											</div>
										</div>
										<div className="flex items-center gap-2">
											<Skeleton className="h-5 w-16 rounded-full" />
											<Skeleton className="h-5 w-24 rounded-md" />
										</div>
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

			{!isLoading && (
				<div className="space-y-4 md:space-y-6">
					{(userConfigs?.length ?? 0) === 0 ? (
						<Card className="border-0 bg-transparent shadow-none">
							<CardContent className="flex flex-col items-center justify-center py-10 md:py-16 text-center">
								<h3 className="text-sm md:text-base font-semibold mb-2">No Vision Models Yet</h3>
								<p className="text-[11px] md:text-xs text-muted-foreground max-w-sm mb-4">
									{canCreate
										? "Add your own vision-capable model (GPT-4o, Claude, Gemini, etc.)"
										: "No vision models have been added to this space yet. Contact a space owner to add one."}
								</p>
							</CardContent>
						</Card>
					) : (
						<div className="grid gap-3 grid-cols-1 sm:grid-cols-2 xl:grid-cols-3">
							{userConfigs?.map((config) => {
								const member = config.user_id ? memberMap.get(config.user_id) : null;

								return (
									<div key={config.id}>
										<Card className="group relative overflow-hidden transition-all duration-200 border-border/60 hover:shadow-md h-full">
											<CardContent className="p-4 flex flex-col gap-3 h-full">
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
																	<Tooltip open={isDesktop ? undefined : false}>
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
																	<Tooltip open={isDesktop ? undefined : false}>
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

												<div className="flex items-center gap-2 flex-wrap">
													{getProviderIcon(config.provider, {
														className: "size-3.5 shrink-0",
													})}
													<code className="text-[11px] font-mono text-muted-foreground bg-muted/60 px-2 py-0.5 rounded-md truncate max-w-[160px]">
														{config.model_name}
													</code>
												</div>

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
															<Dot className="h-4 w-4 text-muted-foreground/30" />
															<TooltipProvider>
																<Tooltip open={isDesktop ? undefined : false}>
																	<TooltipTrigger asChild>
																		<div className="flex items-center gap-1.5 cursor-default">
																			<Avatar className="size-4.5 shrink-0">
																				{member.avatarUrl && (
																					<AvatarImage src={member.avatarUrl} alt={member.name} />
																				)}
																				<AvatarFallback className="text-[9px]">
																					{getInitials(member.name)}
																				</AvatarFallback>
																			</Avatar>
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
									</div>
								);
							})}
						</div>
					)}
				</div>
			)}

			<VisionConfigDialog
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

			<AlertDialog
				open={!!configToDelete}
				onOpenChange={(open) => !open && setConfigToDelete(null)}
			>
				<AlertDialogContent className="select-none">
					<AlertDialogHeader>
						<AlertDialogTitle>Delete Vision Model</AlertDialogTitle>
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
							className="relative bg-destructive text-destructive-foreground hover:bg-destructive/90"
						>
							<span className={isDeleting ? "opacity-0" : ""}>Delete</span>
							{isDeleting && <Spinner size="sm" className="absolute" />}
						</AlertDialogAction>
					</AlertDialogFooter>
				</AlertDialogContent>
			</AlertDialog>
		</div>
	);
}
