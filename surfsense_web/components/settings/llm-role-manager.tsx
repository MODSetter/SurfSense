"use client";

import { useAtomValue } from "jotai";
import {
	AlertCircle,
	Bot,
	CheckCircle,
	FileText,
	RefreshCw,
	RotateCcw,
	Save,
	Shuffle,
} from "lucide-react";
import { motion } from "motion/react";
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
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";
import { Spinner } from "@/components/ui/spinner";
import { cn } from "@/lib/utils";

const ROLE_DESCRIPTIONS = {
	agent: {
		icon: Bot,
		title: "Agent LLM",
		description: "Primary LLM for chat interactions and agent operations",
		color: "bg-blue-100 text-blue-800 border-blue-200",
		examples: "Chat responses, agent tasks, real-time interactions",
		characteristics: ["Fast responses", "Conversational", "Agent operations"],
	},
	document_summary: {
		icon: FileText,
		title: "Document Summary LLM",
		description: "Handles document summarization",
		color: "bg-purple-100 text-purple-800 border-purple-200",
		examples: "Document analysis, podcasts, research synthesis",
		characteristics: ["Large context window", "Deep reasoning", "Summarization"],
	},
};

interface LLMRoleManagerProps {
	searchSpaceId: number;
}

export function LLMRoleManager({ searchSpaceId }: LLMRoleManagerProps) {
	// Use new LLM config system
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
		refetch: refreshGlobalConfigs,
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

		// Check if there are changes compared to current preferences
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

	// Combine global and custom configs (new system)
	const allConfigs = [
		...globalConfigs.map((config) => ({ ...config, is_global: true })),
		...newLLMConfigs.filter((config) => config.id && config.id.toString().trim() !== ""),
	];

	const availableConfigs = allConfigs;

	const isLoading = configsLoading || preferencesLoading || globalConfigsLoading;
	const hasError = configsError || preferencesError || globalConfigsError;

	return (
		<div className="space-y-4 md:space-y-6">
			{/* Header */}
			<div className="flex flex-col space-y-4 lg:flex-row lg:items-center lg:justify-between lg:space-y-0">
				<div className="flex flex-wrap gap-2">
					<Button
						variant="outline"
						size="sm"
						onClick={() => refreshConfigs()}
						disabled={isLoading}
						className="flex items-center gap-2 text-xs md:text-sm h-8 md:h-9"
					>
						<RefreshCw
							className={`h-3 w-3 md:h-4 md:w-4 ${configsLoading ? "animate-spin" : ""}`}
						/>
						<span className="hidden sm:inline">Refresh Configs</span>
						<span className="sm:hidden">Configs</span>
					</Button>
				</div>
			</div>

			{/* Error Alert */}
			{hasError && (
				<Alert variant="destructive" className="py-3 md:py-4">
					<AlertCircle className="h-3 w-3 md:h-4 md:w-4 shrink-0" />
					<AlertDescription className="text-xs md:text-sm">
						{(configsError?.message ?? "Failed to load LLM configurations") ||
							(preferencesError?.message ?? "Failed to load preferences") ||
							(globalConfigsError?.message ?? "Failed to load global configurations")}
					</AlertDescription>
				</Alert>
			)}

			{/* Loading State */}
			{isLoading && (
				<Card>
					<CardContent className="flex items-center justify-center py-8 md:py-12">
						<div className="flex items-center gap-2 text-muted-foreground">
							<Spinner size="sm" className="md:h-5 md:w-5" />
							<span className="text-xs md:text-sm">
								{configsLoading && preferencesLoading
									? "Loading configurations and preferences..."
									: configsLoading
										? "Loading configurations..."
										: "Loading preferences..."}
							</span>
						</div>
					</CardContent>
				</Card>
			)}

			{/* Info Alert */}
			{!isLoading && !hasError && (
				<div className="space-y-4 md:space-y-6">
					{availableConfigs.length === 0 ? (
						<Alert variant="destructive" className="py-3 md:py-4">
							<AlertCircle className="h-3 w-3 md:h-4 md:w-4 shrink-0" />
							<AlertDescription className="text-xs md:text-sm">
								No LLM configurations found. Please add at least one LLM provider in the Agent
								Configs tab before assigning roles.
							</AlertDescription>
						</Alert>
					) : !isAssignmentComplete ? (
						<Alert className="py-3 md:py-4">
							<AlertCircle className="h-3 w-3 md:h-4 md:w-4 shrink-0" />
							<AlertDescription className="text-xs md:text-sm">
								Complete all role assignments to enable full functionality. Each role serves
								different purposes in your workflow.
							</AlertDescription>
						</Alert>
					) : (
						<Alert className="py-3 md:py-4">
							<CheckCircle className="h-3 w-3 md:h-4 md:w-4 shrink-0" />
							<AlertDescription className="text-xs md:text-sm">
								All roles are assigned and ready to use! Your LLM configuration is complete.
							</AlertDescription>
						</Alert>
					)}

					{/* Role Assignment Cards */}
					{availableConfigs.length > 0 && (
						<div className="grid gap-4 md:gap-6">
							{Object.entries(ROLE_DESCRIPTIONS).map(([key, role]) => {
								const IconComponent = role.icon;
								const currentAssignment = assignments[`${key}_llm_id` as keyof typeof assignments];
								const assignedConfig = availableConfigs.find(
									(config) => config.id === currentAssignment
								);

								return (
									<motion.div
										key={key}
										initial={{ opacity: 0, y: 10 }}
										animate={{ opacity: 1, y: 0 }}
										transition={{ delay: Object.keys(ROLE_DESCRIPTIONS).indexOf(key) * 0.1 }}
									>
										<Card
											className={`border-l-4 ${currentAssignment ? "border-l-primary" : "border-l-muted"} hover:shadow-md transition-shadow`}
										>
											<CardHeader className="pb-2 md:pb-3 px-3 md:px-6 pt-3 md:pt-6">
												<div className="flex items-center justify-between">
													<div className="flex items-center gap-2 md:gap-3">
														<div className={`p-1.5 md:p-2 rounded-lg ${role.color}`}>
															<IconComponent className="w-4 h-4 md:w-5 md:h-5" />
														</div>
														<div>
															<CardTitle className="text-base md:text-lg">{role.title}</CardTitle>
															<CardDescription className="mt-0.5 md:mt-1 text-xs md:text-sm">
																{role.description}
															</CardDescription>
														</div>
													</div>
													{currentAssignment && (
														<CheckCircle className="w-4 h-4 md:w-5 md:h-5 text-green-500 shrink-0" />
													)}
												</div>
											</CardHeader>
											<CardContent className="space-y-3 md:space-y-4 px-3 md:px-6 pb-3 md:pb-6">
												<div className="space-y-1.5 md:space-y-2">
													<Label className="text-xs md:text-sm font-medium">
														Assign LLM Configuration:
													</Label>
													<Select
														value={currentAssignment?.toString() || "unassigned"}
														onValueChange={(value) => handleRoleAssignment(`${key}_llm_id`, value)}
													>
														<SelectTrigger className="h-9 md:h-10 text-xs md:text-sm">
															<SelectValue placeholder="Select an LLM configuration" />
														</SelectTrigger>
														<SelectContent>
															<SelectItem value="unassigned">
																<span className="text-muted-foreground">Unassigned</span>
															</SelectItem>

															{/* Global Configurations */}
															{globalConfigs.length > 0 && (
																<>
																	<div className="px-2 py-1.5 text-xs font-semibold text-muted-foreground">
																		Global Configurations
																	</div>
																	{globalConfigs.map((config) => {
																		const isAutoMode =
																			"is_auto_mode" in config && config.is_auto_mode;
																		return (
																			<SelectItem key={config.id} value={config.id.toString()}>
																				<div className="flex items-center gap-2">
																					{isAutoMode ? (
																						<Badge
																							variant="outline"
																							className="text-xs bg-violet-100 text-violet-700 dark:bg-violet-900/30 dark:text-violet-300 border-violet-200 dark:border-violet-700"
																						>
																							<Shuffle className="size-3 mr-1" />
																							AUTO
																						</Badge>
																					) : (
																						<Badge variant="outline" className="text-xs">
																							{config.provider}
																						</Badge>
																					)}
																					<span>{config.name}</span>
																					{!isAutoMode && (
																						<span className="text-muted-foreground">
																							({config.model_name})
																						</span>
																					)}
																					{isAutoMode ? (
																						<Badge
																							variant="secondary"
																							className="text-xs bg-violet-100 text-violet-700 dark:bg-violet-900/30 dark:text-violet-300"
																						>
																							Recommended
																						</Badge>
																					) : (
																						<Badge variant="secondary" className="text-xs">
																							🌐 Global
																						</Badge>
																					)}
																				</div>
																			</SelectItem>
																		);
																	})}
																</>
															)}

															{/* Custom Configurations */}
															{newLLMConfigs.length > 0 && (
																<>
																	<div className="px-2 py-1.5 text-xs font-semibold text-muted-foreground">
																		Your Configurations
																	</div>
																	{newLLMConfigs
																		.filter(
																			(config) => config.id && config.id.toString().trim() !== ""
																		)
																		.map((config) => (
																			<SelectItem key={config.id} value={config.id.toString()}>
																				<div className="flex items-center gap-2">
																					<Badge variant="outline" className="text-xs">
																						{config.provider}
																					</Badge>
																					<span>{config.name}</span>
																					<span className="text-muted-foreground">
																						({config.model_name})
																					</span>
																				</div>
																			</SelectItem>
																		))}
																</>
															)}
														</SelectContent>
													</Select>
												</div>

												{assignedConfig && (
													<div
														className={cn(
															"mt-2 md:mt-3 p-2 md:p-3 rounded-lg",
															"is_auto_mode" in assignedConfig && assignedConfig.is_auto_mode
																? "bg-violet-50 dark:bg-violet-900/20 border border-violet-200 dark:border-violet-800/50"
																: "bg-muted/50"
														)}
													>
														<div className="flex items-center gap-1.5 md:gap-2 text-xs md:text-sm flex-wrap">
															{"is_auto_mode" in assignedConfig && assignedConfig.is_auto_mode ? (
																<Shuffle className="w-3 h-3 md:w-4 md:h-4 shrink-0 text-violet-600 dark:text-violet-400" />
															) : (
																<Bot className="w-3 h-3 md:w-4 md:h-4 shrink-0" />
															)}
															<span className="font-medium">Assigned:</span>
															{"is_auto_mode" in assignedConfig && assignedConfig.is_auto_mode ? (
																<Badge
																	variant="secondary"
																	className="text-[10px] md:text-xs bg-violet-100 text-violet-700 dark:bg-violet-900/30 dark:text-violet-300"
																>
																	AUTO
																</Badge>
															) : (
																<Badge variant="secondary" className="text-[10px] md:text-xs">
																	{assignedConfig.provider}
																</Badge>
															)}
															<span>{assignedConfig.name}</span>
															{"is_auto_mode" in assignedConfig && assignedConfig.is_auto_mode ? (
																<Badge
																	variant="outline"
																	className="text-[9px] md:text-xs bg-violet-100 text-violet-700 dark:bg-violet-900/30 dark:text-violet-300 border-violet-200 dark:border-violet-700"
																>
																	Recommended
																</Badge>
															) : (
																"is_global" in assignedConfig &&
																assignedConfig.is_global && (
																	<Badge variant="outline" className="text-[9px] md:text-xs">
																		🌐 Global
																	</Badge>
																)
															)}
														</div>
														{"is_auto_mode" in assignedConfig && assignedConfig.is_auto_mode ? (
															<div className="text-[10px] md:text-xs text-violet-600 dark:text-violet-400 mt-0.5 md:mt-1">
																Automatically load balances across all available LLM providers
															</div>
														) : (
															<>
																<div className="text-[10px] md:text-xs text-muted-foreground mt-0.5 md:mt-1">
																	Model: {assignedConfig.model_name}
																</div>
																{assignedConfig.api_base && (
																	<div className="text-[10px] md:text-xs text-muted-foreground">
																		Base: {assignedConfig.api_base}
																	</div>
																)}
															</>
														)}
													</div>
												)}
											</CardContent>
										</Card>
									</motion.div>
								);
							})}
						</div>
					)}

					{/* Action Buttons */}
					{hasChanges && (
						<div className="flex justify-center gap-2 md:gap-3 pt-3 md:pt-4">
							<Button
								onClick={handleSave}
								disabled={isSaving}
								className="flex items-center gap-2 text-xs md:text-sm h-9 md:h-10"
							>
								<Save className="w-3.5 h-3.5 md:w-4 md:h-4" />
								{isSaving ? "Saving" : "Save Changes"}
							</Button>
							<Button
								variant="outline"
								onClick={handleReset}
								disabled={isSaving}
								className="flex items-center gap-2 text-xs md:text-sm h-9 md:h-10"
							>
								<RotateCcw className="w-3.5 h-3.5 md:w-4 md:h-4" />
								Reset
							</Button>
						</div>
					)}
				</div>
			)}
		</div>
	);
}
