"use client";

import { useAtomValue } from "jotai";
import {
	AlertCircle,
	Bot,
	CheckCircle,
	FileText,
	Loader2,
	RefreshCw,
	RotateCcw,
	Save,
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
		description: "Handles document summarization, long context analysis, and query reformulation",
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
		refetch: refreshPreferences,
	} = useAtomValue(llmPreferencesAtom);

	const { mutateAsync: updatePreferences } = useAtomValue(updateLLMPreferencesMutationAtom);

	const [assignments, setAssignments] = useState({
		agent_llm_id: preferences.agent_llm_id || "",
		document_summary_llm_id: preferences.document_summary_llm_id || "",
	});

	const [hasChanges, setHasChanges] = useState(false);
	const [isSaving, setIsSaving] = useState(false);

	useEffect(() => {
		const newAssignments = {
			agent_llm_id: preferences.agent_llm_id || "",
			document_summary_llm_id: preferences.document_summary_llm_id || "",
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
			agent_llm_id: preferences.agent_llm_id || "",
			document_summary_llm_id: preferences.document_summary_llm_id || "",
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
			agent_llm_id: preferences.agent_llm_id || "",
			document_summary_llm_id: preferences.document_summary_llm_id || "",
		});
		setHasChanges(false);
	};

	const isAssignmentComplete = assignments.agent_llm_id && assignments.document_summary_llm_id;

	// Combine global and custom configs (new system)
	const allConfigs = [
		...globalConfigs.map((config) => ({ ...config, is_global: true })),
		...newLLMConfigs.filter((config) => config.id && config.id.toString().trim() !== ""),
	];

	const availableConfigs = allConfigs;

	const isLoading = configsLoading || preferencesLoading || globalConfigsLoading;
	const hasError = configsError || preferencesError || globalConfigsError;

	return (
		<div className="space-y-6">
			{/* Header */}
			<div className="flex flex-col space-y-4 lg:flex-row lg:items-center lg:justify-between lg:space-y-0">
				<div className="flex flex-wrap gap-2">
					<Button
						variant="outline"
						size="sm"
						onClick={() => refreshConfigs()}
						disabled={isLoading}
						className="flex items-center gap-2"
					>
						<RefreshCw className={`h-4 w-4 ${configsLoading ? "animate-spin" : ""}`} />
						<span className="hidden sm:inline">Refresh Configs</span>
						<span className="sm:hidden">Configs</span>
					</Button>
					<Button
						variant="outline"
						size="sm"
						onClick={() => refreshPreferences()}
						disabled={isLoading}
						className="flex items-center gap-2"
					>
						<RefreshCw className={`h-4 w-4 ${preferencesLoading ? "animate-spin" : ""}`} />
						<span className="hidden sm:inline">Refresh Preferences</span>
						<span className="sm:hidden">Prefs</span>
					</Button>
				</div>
			</div>

			{/* Error Alert */}
			{hasError && (
				<Alert variant="destructive">
					<AlertCircle className="h-4 w-4" />
					<AlertDescription>
						{(configsError?.message ?? "Failed to load LLM configurations") ||
							(preferencesError?.message ?? "Failed to load preferences") ||
							(globalConfigsError?.message ?? "Failed to load global configurations")}
					</AlertDescription>
				</Alert>
			)}

			{/* Loading State */}
			{isLoading && (
				<Card>
					<CardContent className="flex items-center justify-center py-12">
						<div className="flex items-center gap-2 text-muted-foreground">
							<Loader2 className="w-5 h-5 animate-spin" />
							<span>
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
				<div className="space-y-6">
					{availableConfigs.length === 0 ? (
						<Alert variant="destructive">
							<AlertCircle className="h-4 w-4" />
							<AlertDescription>
								No LLM configurations found. Please add at least one LLM provider in the Agent
								Configs tab before assigning roles.
							</AlertDescription>
						</Alert>
					) : !isAssignmentComplete ? (
						<Alert>
							<AlertCircle className="h-4 w-4" />
							<AlertDescription>
								Complete all role assignments to enable full functionality. Each role serves
								different purposes in your workflow.
							</AlertDescription>
						</Alert>
					) : (
						<Alert>
							<CheckCircle className="h-4 w-4" />
							<AlertDescription>
								All roles are assigned and ready to use! Your LLM configuration is complete.
							</AlertDescription>
						</Alert>
					)}

					{/* Role Assignment Cards */}
					{availableConfigs.length > 0 && (
						<div className="grid gap-6">
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
											<CardHeader className="pb-3">
												<div className="flex items-center justify-between">
													<div className="flex items-center gap-3">
														<div className={`p-2 rounded-lg ${role.color}`}>
															<IconComponent className="w-5 h-5" />
														</div>
														<div>
															<CardTitle className="text-lg">{role.title}</CardTitle>
															<CardDescription className="mt-1">{role.description}</CardDescription>
														</div>
													</div>
													{currentAssignment && <CheckCircle className="w-5 h-5 text-green-500" />}
												</div>
											</CardHeader>
											<CardContent className="space-y-4">
												<div className="space-y-2">
													<Label className="text-sm font-medium">Assign LLM Configuration:</Label>
													<Select
														value={currentAssignment?.toString() || "unassigned"}
														onValueChange={(value) => handleRoleAssignment(`${key}_llm_id`, value)}
													>
														<SelectTrigger>
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
																	{globalConfigs.map((config) => (
																		<SelectItem key={config.id} value={config.id.toString()}>
																			<div className="flex items-center gap-2">
																				<Badge variant="outline" className="text-xs">
																					{config.provider}
																				</Badge>
																				<span>{config.name}</span>
																				<span className="text-muted-foreground">
																					({config.model_name})
																				</span>
																				<Badge variant="secondary" className="text-xs">
																					🌐 Global
																				</Badge>
																			</div>
																		</SelectItem>
																	))}
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
													<div className="mt-3 p-3 bg-muted/50 rounded-lg">
														<div className="flex items-center gap-2 text-sm flex-wrap">
															<Bot className="w-4 h-4" />
															<span className="font-medium">Assigned:</span>
															<Badge variant="secondary">{assignedConfig.provider}</Badge>
															<span>{assignedConfig.name}</span>
															{"is_global" in assignedConfig && assignedConfig.is_global && (
																<Badge variant="outline" className="text-xs">
																	🌐 Global
																</Badge>
															)}
														</div>
														<div className="text-xs text-muted-foreground mt-1">
															Model: {assignedConfig.model_name}
														</div>
														{assignedConfig.api_base && (
															<div className="text-xs text-muted-foreground">
																Base: {assignedConfig.api_base}
															</div>
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
						<div className="flex justify-center gap-3 pt-4">
							<Button onClick={handleSave} disabled={isSaving} className="flex items-center gap-2">
								<Save className="w-4 h-4" />
								{isSaving ? "Saving..." : "Save Changes"}
							</Button>
							<Button
								variant="outline"
								onClick={handleReset}
								disabled={isSaving}
								className="flex items-center gap-2"
							>
								<RotateCcw className="w-4 h-4" />
								Reset
							</Button>
						</div>
					)}
				</div>
			)}
		</div>
	);
}
