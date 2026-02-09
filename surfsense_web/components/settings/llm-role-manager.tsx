"use client";

import { useAtomValue } from "jotai";
import {
	AlertCircle,
	Bot,
	CheckCircle,
	CircleDashed,
	FileText,
	RefreshCw,
	RotateCcw,
	Save,
	Shuffle,
} from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { updateLLMPreferencesMutationAtom } from "@/atoms/new-llm-config/new-llm-config-mutation.atoms";
import {
	globalNewLLMConfigsAtom,
	llmPreferencesAtom,
	newLLMConfigsAtom,
} from "@/atoms/new-llm-config/new-llm-config-query.atoms";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import {
	Select,
	SelectContent,
	SelectGroup,
	SelectItem,
	SelectLabel,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

const ROLE_DESCRIPTIONS = {
	agent: {
		icon: Bot,
		title: "Agent LLM",
		description: "Primary LLM for chat interactions and agent operations",
		color: "text-blue-600 dark:text-blue-400",
		bgColor: "bg-blue-500/10",
	},
	document_summary: {
		icon: FileText,
		title: "Document Summary LLM",
		description: "Handles document summarization and research synthesis",
		color: "text-purple-600 dark:text-purple-400",
		bgColor: "bg-purple-500/10",
	},
};

interface LLMRoleManagerProps {
	searchSpaceId: number;
}

export function LLMRoleManager({ searchSpaceId }: LLMRoleManagerProps) {
	const {
		data: newLLMConfigs = [],
		isFetching: configsLoading,
		error: configsError,
		refetch: refreshConfigs,
	} = useAtomValue(newLLMConfigsAtom);
	const {
		data: globalConfigs = [],
		isFetching: globalConfigsLoading,
		error: globalConfigsError,
	} = useAtomValue(globalNewLLMConfigsAtom);
	const {
		data: preferences = {},
		isFetching: preferencesLoading,
		error: preferencesError,
	} = useAtomValue(llmPreferencesAtom);

	const { mutateAsync: updatePreferences } = useAtomValue(updateLLMPreferencesMutationAtom);

	const [assignments, setAssignments] = useState({
		agent_llm_id: preferences.agent_llm_id ?? "",
		document_summary_llm_id: preferences.document_summary_llm_id ?? "",
	});

	const [hasChanges, setHasChanges] = useState(false);
	const [isSaving, setIsSaving] = useState(false);

	useEffect(() => {
		const newAssignments = {
			agent_llm_id: preferences.agent_llm_id ?? "",
			document_summary_llm_id: preferences.document_summary_llm_id ?? "",
		};
		setAssignments(newAssignments);
		setHasChanges(false);
	}, [preferences]);

	const handleRoleAssignment = (role: string, configId: string) => {
		const newAssignments = {
			...assignments,
			[role]: configId === "unassigned" ? "" : parseInt(configId),
		};

		setAssignments(newAssignments);

		const currentPrefs = {
			agent_llm_id: preferences.agent_llm_id ?? "",
			document_summary_llm_id: preferences.document_summary_llm_id ?? "",
		};

		const hasChangesNow = Object.keys(newAssignments).some(
			(key) =>
				newAssignments[key as keyof typeof newAssignments] !==
				currentPrefs[key as keyof typeof currentPrefs]
		);

		setHasChanges(hasChangesNow);
	};

	const handleSave = async () => {
		setIsSaving(true);

		const numericAssignments = {
			agent_llm_id:
				typeof assignments.agent_llm_id === "string"
					? assignments.agent_llm_id
						? parseInt(assignments.agent_llm_id)
						: undefined
					: assignments.agent_llm_id,
			document_summary_llm_id:
				typeof assignments.document_summary_llm_id === "string"
					? assignments.document_summary_llm_id
						? parseInt(assignments.document_summary_llm_id)
						: undefined
					: assignments.document_summary_llm_id,
		};

		await updatePreferences({
			search_space_id: searchSpaceId,
			data: numericAssignments,
		});

		setHasChanges(false);
		toast.success("LLM role assignments saved successfully!");

		setIsSaving(false);
	};

	const handleReset = () => {
		setAssignments({
			agent_llm_id: preferences.agent_llm_id ?? "",
			document_summary_llm_id: preferences.document_summary_llm_id ?? "",
		});
		setHasChanges(false);
	};

	const isAssignmentComplete =
		assignments.agent_llm_id !== "" &&
		assignments.agent_llm_id !== null &&
		assignments.agent_llm_id !== undefined &&
		assignments.document_summary_llm_id !== "" &&
		assignments.document_summary_llm_id !== null &&
		assignments.document_summary_llm_id !== undefined;

	// Combine global and custom configs
	const allConfigs = [
		...globalConfigs.map((config) => ({ ...config, is_global: true })),
		...newLLMConfigs.filter((config) => config.id && config.id.toString().trim() !== ""),
	];

	const isLoading = configsLoading || preferencesLoading || globalConfigsLoading;
	const hasError = configsError || preferencesError || globalConfigsError;

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
					<RefreshCw className="h-3 w-3 md:h-4 md:w-4" />
					Refresh
				</Button>
				{isAssignmentComplete && !isLoading && !hasError && (
					<Badge
						variant="outline"
						className="text-xs gap-1.5 border-emerald-500/30 text-emerald-700 dark:text-emerald-300 bg-emerald-500/5"
					>
						<CheckCircle className="h-3 w-3" />
						All roles assigned
					</Badge>
				)}
			</div>

			{/* Error Alert */}
			<AnimatePresence>
				{hasError && (
					<motion.div
						key="error-alert"
						initial={{ opacity: 0, y: -10 }}
						animate={{ opacity: 1, y: 0 }}
						exit={{ opacity: 0, y: -10 }}
					>
						<Alert variant="destructive" className="py-3 md:py-4">
							<AlertCircle className="h-3 w-3 md:h-4 md:w-4 shrink-0" />
							<AlertDescription className="text-xs md:text-sm">
								{(configsError?.message ?? "Failed to load LLM configurations") ||
									(preferencesError?.message ?? "Failed to load preferences") ||
									(globalConfigsError?.message ??
										"Failed to load global configurations")}
							</AlertDescription>
						</Alert>
					</motion.div>
				)}
			</AnimatePresence>

			{/* Loading Skeleton */}
			{isLoading && (
				<div className="grid gap-4 grid-cols-1 lg:grid-cols-2">
					{["skeleton-a", "skeleton-b"].map((key) => (
						<Card key={key} className="border-border/60">
							<CardContent className="p-4 md:p-5 space-y-4">
								{/* Header: icon + title + status */}
								<div className="flex items-start justify-between gap-3">
									<div className="flex items-center gap-3 min-w-0">
										<Skeleton className="h-9 w-9 rounded-lg shrink-0" />
										<div className="space-y-1.5 flex-1">
											<Skeleton className="h-4 w-24 md:w-28" />
											<Skeleton className="h-3 w-40 md:w-52" />
										</div>
									</div>
									<Skeleton className="h-4 w-4 rounded-full shrink-0" />
								</div>
								{/* Label */}
								<div className="space-y-1.5">
									<Skeleton className="h-3 w-20" />
									<Skeleton className="h-9 md:h-10 w-full rounded-md" />
								</div>
								{/* Summary block */}
								<div className="rounded-lg border border-border/50 p-3 space-y-2">
									<div className="flex items-center gap-2">
										<Skeleton className="h-3.5 w-3.5 rounded shrink-0" />
										<Skeleton className="h-3.5 w-28" />
									</div>
									<div className="flex items-center gap-1.5">
										<Skeleton className="h-4 w-14 rounded-full" />
										<Skeleton className="h-3 w-24" />
									</div>
								</div>
							</CardContent>
						</Card>
					))}
				</div>
			)}

			{/* No configs warning */}
			{!isLoading && !hasError && allConfigs.length === 0 && (
				<Alert variant="destructive" className="py-3 md:py-4">
					<AlertCircle className="h-3 w-3 md:h-4 md:w-4 shrink-0" />
					<AlertDescription className="text-xs md:text-sm">
						No LLM configurations found. Please add at least one LLM provider in the
						Agent Configs tab before assigning roles.
					</AlertDescription>
				</Alert>
			)}

			{/* Role Assignment Cards */}
			{!isLoading && !hasError && allConfigs.length > 0 && (
				<motion.div
					initial={{ opacity: 0 }}
					animate={{ opacity: 1 }}
					transition={{ duration: 0.3 }}
					className="grid gap-4 grid-cols-1 lg:grid-cols-2"
				>
					{Object.entries(ROLE_DESCRIPTIONS).map(([key, role], index) => {
						const IconComponent = role.icon;
						const currentAssignment =
							assignments[`${key}_llm_id` as keyof typeof assignments];
						const assignedConfig = allConfigs.find(
							(config) => config.id === currentAssignment
						);
						const isAssigned =
							currentAssignment !== "" &&
							currentAssignment !== null &&
							currentAssignment !== undefined;
						const isAutoMode =
							assignedConfig &&
							"is_auto_mode" in assignedConfig &&
							assignedConfig.is_auto_mode;

						return (
							<motion.div
								key={key}
								initial={{ opacity: 0, y: 15 }}
								animate={{ opacity: 1, y: 0 }}
								transition={{ delay: index * 0.08, duration: 0.3 }}
							>
								<Card className="group relative overflow-hidden transition-all duration-200 border-border/60 hover:shadow-md h-full">
									<CardContent className="p-4 md:p-5 space-y-4">
										{/* Role Header */}
										<div className="flex items-start justify-between gap-3">
											<div className="flex items-center gap-3 min-w-0">
												<div
													className={cn(
														"flex items-center justify-center w-9 h-9 rounded-lg shrink-0",
														role.bgColor
													)}
												>
													<IconComponent
														className={cn("w-4 h-4", role.color)}
													/>
												</div>
												<div className="min-w-0">
													<h4 className="text-sm font-semibold tracking-tight">
														{role.title}
													</h4>
													<p className="text-[11px] text-muted-foreground/70 mt-0.5">
														{role.description}
													</p>
												</div>
											</div>
											{isAssigned ? (
												<CheckCircle className="w-4 h-4 text-emerald-500 shrink-0 mt-0.5" />
											) : (
												<CircleDashed className="w-4 h-4 text-muted-foreground/40 shrink-0 mt-0.5" />
											)}
										</div>

										{/* Selector */}
										<div className="space-y-1.5">
											<Label className="text-xs font-medium text-muted-foreground">
												Configuration
											</Label>
											<Select
												value={currentAssignment?.toString() || "unassigned"}
												onValueChange={(value) =>
													handleRoleAssignment(`${key}_llm_id`, value)
												}
											>
												<SelectTrigger className="h-9 md:h-10 text-xs md:text-sm">
													<SelectValue placeholder="Select a configuration" />
												</SelectTrigger>
												<SelectContent>
													<SelectItem value="unassigned">
														<span className="text-muted-foreground">
															Unassigned
														</span>
													</SelectItem>

													{/* Global Configurations */}
													{globalConfigs.length > 0 && (
														<SelectGroup>
															<SelectLabel className="text-xs font-semibold text-muted-foreground">
																Global Configurations
															</SelectLabel>
															{globalConfigs.map((config) => {
																const isAuto =
																	"is_auto_mode" in config &&
																	config.is_auto_mode;
																return (
																	<SelectItem
																		key={config.id}
																		value={config.id.toString()}
																	>
																		<div className="flex items-center gap-2">
																			{isAuto ? (
																				<Badge
																					variant="outline"
																					className="text-[10px] bg-violet-100 text-violet-700 dark:bg-violet-900/30 dark:text-violet-300 border-violet-200 dark:border-violet-700"
																				>
																					<Shuffle className="size-2.5 mr-0.5" />
																					AUTO
																				</Badge>
																			) : (
																				<Badge
																					variant="outline"
																					className="text-[10px]"
																				>
																					{config.provider}
																				</Badge>
																			)}
																			<span>
																				{config.name}
																			</span>
																			{!isAuto && (
																				<span className="text-muted-foreground text-[11px]">
																					(
																					{
																						config.model_name
																					}
																					)
																				</span>
																			)}
																			{isAuto && (
																				<Badge
																					variant="secondary"
																					className="text-[9px] bg-violet-100 text-violet-700 dark:bg-violet-900/30 dark:text-violet-300"
																				>
																					Recommended
																				</Badge>
																			)}
																		</div>
																	</SelectItem>
																);
															})}
														</SelectGroup>
													)}

													{/* Custom Configurations */}
													{newLLMConfigs.length > 0 && (
														<SelectGroup>
															<SelectLabel className="text-xs font-semibold text-muted-foreground">
																Your Configurations
															</SelectLabel>
															{newLLMConfigs
																.filter(
																	(config) =>
																		config.id &&
																		config.id
																			.toString()
																			.trim() !== ""
																)
																.map((config) => (
																	<SelectItem
																		key={config.id}
																		value={config.id.toString()}
																	>
																		<div className="flex items-center gap-2">
																			<Badge
																				variant="outline"
																				className="text-[10px]"
																			>
																				{config.provider}
																			</Badge>
																			<span>
																				{config.name}
																			</span>
																			<span className="text-muted-foreground text-[11px]">
																				(
																				{
																					config.model_name
																				}
																				)
																			</span>
																		</div>
																	</SelectItem>
																))}
														</SelectGroup>
													)}
												</SelectContent>
											</Select>
										</div>

									{/* Assigned Config Summary */}
									{assignedConfig && (
										<div
											className={cn(
												"rounded-lg p-3 border",
												isAutoMode
													? "bg-violet-50 dark:bg-violet-900/10 border-violet-200/50 dark:border-violet-800/30"
													: "bg-muted/40 border-border/50"
											)}
										>
												{isAutoMode ? (
													<div className="flex items-center gap-2">
														<Shuffle
															className={cn(
																"w-3.5 h-3.5 shrink-0 text-violet-600 dark:text-violet-400"
															)}
														/>
														<div className="min-w-0">
															<p className="text-xs font-medium text-violet-700 dark:text-violet-300">
																Auto Load Balanced
															</p>
															<p className="text-[10px] text-violet-600/70 dark:text-violet-400/70 mt-0.5">
																Routes across all available providers
															</p>
														</div>
													</div>
												) : (
													<div className="flex items-start gap-2">
														<Bot className="w-3.5 h-3.5 shrink-0 mt-0.5 text-muted-foreground" />
														<div className="min-w-0 flex-1">
															<div className="flex items-center gap-1.5 flex-wrap">
																<span className="text-xs font-medium">
																	{assignedConfig.name}
																</span>
																{"is_global" in assignedConfig &&
																	assignedConfig.is_global && (
																		<Badge
																			variant="secondary"
																			className="text-[9px] px-1.5 py-0"
																		>
																			🌐 Global
																		</Badge>
																	)}
															</div>
															<div className="flex items-center gap-1.5 mt-1">
																<Badge
																	variant="outline"
																	className="text-[9px] px-1.5 py-0 font-mono"
																>
																	{assignedConfig.provider}
																</Badge>
																<code className="text-[10px] text-muted-foreground font-mono truncate">
																	{assignedConfig.model_name}
																</code>
															</div>
															{assignedConfig.api_base && (
																<p className="text-[10px] text-muted-foreground/60 mt-1 truncate">
																	{assignedConfig.api_base}
																</p>
															)}
														</div>
													</div>
												)}
										</div>
									)}
								</CardContent>
								</Card>
							</motion.div>
						);
					})}
				</motion.div>
			)}

			{/* Save / Reset Bar */}
			<AnimatePresence>
				{hasChanges && (
					<motion.div
						initial={{ opacity: 0, y: 10 }}
						animate={{ opacity: 1, y: 0 }}
						exit={{ opacity: 0, y: 10 }}
						transition={{ duration: 0.2 }}
						className="flex items-center justify-between gap-3 rounded-lg border border-border bg-muted/50 p-3 md:p-4"
					>
						<p className="text-xs md:text-sm text-muted-foreground">
							You have unsaved changes
						</p>
						<div className="flex items-center gap-2">
							<Button
								variant="outline"
								size="sm"
								onClick={handleReset}
								disabled={isSaving}
								className="h-8 text-xs gap-1.5"
							>
								<RotateCcw className="w-3 h-3" />
								Reset
							</Button>
							<Button
								size="sm"
								onClick={handleSave}
								disabled={isSaving}
								className="h-8 text-xs gap-1.5"
							>
								<Save className="w-3 h-3" />
								{isSaving ? "Saving…" : "Save Changes"}
							</Button>
						</div>
					</motion.div>
				)}
			</AnimatePresence>
		</div>
	);
}
