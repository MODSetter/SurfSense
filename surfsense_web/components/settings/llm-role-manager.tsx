"use client";

import {
	AlertCircle,
	Bot,
	Brain,
	CheckCircle,
	Loader2,
	RefreshCw,
	RotateCcw,
	Save,
	Settings2,
	Zap,
} from "lucide-react";
import { motion } from "motion/react";
import { useEffect, useState } from "react";
import { toast } from "sonner";
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
import { useLLMConfigs, useLLMPreferences } from "@/hooks/use-llm-configs";

const ROLE_DESCRIPTIONS = {
	long_context: {
		icon: Brain,
		title: "Long Context LLM",
		description: "Handles complex tasks requiring extensive context understanding and reasoning",
		color: "bg-blue-100 text-blue-800 border-blue-200",
		examples: "Document analysis, research synthesis, complex Q&A",
		characteristics: ["Large context window", "Deep reasoning", "Complex analysis"],
	},
	fast: {
		icon: Zap,
		title: "Fast LLM",
		description: "Optimized for quick responses and real-time interactions",
		color: "bg-green-100 text-green-800 border-green-200",
		examples: "Quick searches, simple questions, instant responses",
		characteristics: ["Low latency", "Quick responses", "Real-time chat"],
	},
	strategic: {
		icon: Bot,
		title: "Strategic LLM",
		description: "Advanced reasoning for planning and strategic decision making",
		color: "bg-purple-100 text-purple-800 border-purple-200",
		examples: "Planning workflows, strategic analysis, complex problem solving",
		characteristics: ["Strategic thinking", "Long-term planning", "Complex reasoning"],
	},
};

interface LLMRoleManagerProps {
	searchSpaceId: number;
}

export function LLMRoleManager({ searchSpaceId }: LLMRoleManagerProps) {
	const {
		llmConfigs,
		loading: configsLoading,
		error: configsError,
		refreshConfigs,
	} = useLLMConfigs(searchSpaceId);
	const {
		preferences,
		loading: preferencesLoading,
		error: preferencesError,
		updatePreferences,
		refreshPreferences,
	} = useLLMPreferences(searchSpaceId);

	const [assignments, setAssignments] = useState({
		long_context_llm_id: preferences.long_context_llm_id || "",
		fast_llm_id: preferences.fast_llm_id || "",
		strategic_llm_id: preferences.strategic_llm_id || "",
	});

	const [hasChanges, setHasChanges] = useState(false);
	const [isSaving, setIsSaving] = useState(false);

	useEffect(() => {
		const newAssignments = {
			long_context_llm_id: preferences.long_context_llm_id || "",
			fast_llm_id: preferences.fast_llm_id || "",
			strategic_llm_id: preferences.strategic_llm_id || "",
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
			long_context_llm_id: preferences.long_context_llm_id || "",
			fast_llm_id: preferences.fast_llm_id || "",
			strategic_llm_id: preferences.strategic_llm_id || "",
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
			long_context_llm_id:
				typeof assignments.long_context_llm_id === "string"
					? assignments.long_context_llm_id
						? parseInt(assignments.long_context_llm_id)
						: undefined
					: assignments.long_context_llm_id,
			fast_llm_id:
				typeof assignments.fast_llm_id === "string"
					? assignments.fast_llm_id
						? parseInt(assignments.fast_llm_id)
						: undefined
					: assignments.fast_llm_id,
			strategic_llm_id:
				typeof assignments.strategic_llm_id === "string"
					? assignments.strategic_llm_id
						? parseInt(assignments.strategic_llm_id)
						: undefined
					: assignments.strategic_llm_id,
		};

		const success = await updatePreferences(numericAssignments);

		if (success) {
			setHasChanges(false);
			toast.success("LLM role assignments saved successfully!");
		}

		setIsSaving(false);
	};

	const handleReset = () => {
		setAssignments({
			long_context_llm_id: preferences.long_context_llm_id || "",
			fast_llm_id: preferences.fast_llm_id || "",
			strategic_llm_id: preferences.strategic_llm_id || "",
		});
		setHasChanges(false);
	};

	const isAssignmentComplete =
		assignments.long_context_llm_id && assignments.fast_llm_id && assignments.strategic_llm_id;
	const assignedConfigIds = Object.values(assignments).filter((id) => id !== "");
	const availableConfigs = llmConfigs.filter(
		(config) => config.id && config.id.toString().trim() !== ""
	);

	const isLoading = configsLoading || preferencesLoading;
	const hasError = configsError || preferencesError;

	return (
		<div className="space-y-6">
			{/* Header */}
			<div className="flex flex-col space-y-4 lg:flex-row lg:items-center lg:justify-between lg:space-y-0">
				<div className="space-y-1">
					<div className="flex items-center space-x-3">
						<div className="flex h-10 w-10 items-center justify-center rounded-lg bg-purple-500/10">
							<Settings2 className="h-5 w-5 text-purple-600" />
						</div>
						<div>
							<h2 className="text-2xl font-bold tracking-tight">LLM Role Management</h2>
							<p className="text-muted-foreground">
								Assign your LLM configurations to specific roles for different purposes.
							</p>
						</div>
					</div>
				</div>
				<div className="flex flex-wrap gap-2">
					<Button
						variant="outline"
						size="sm"
						onClick={refreshConfigs}
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
						onClick={refreshPreferences}
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
					<AlertDescription>{configsError || preferencesError}</AlertDescription>
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

			{/* Stats Overview */}
			{!isLoading && !hasError && (
				<div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
					<Card className="border-l-4 border-l-blue-500">
						<CardContent className="p-6">
							<div className="flex items-center justify-between space-x-4">
								<div className="space-y-1">
									<p className="text-3xl font-bold tracking-tight">{availableConfigs.length}</p>
									<p className="text-sm font-medium text-muted-foreground">Available Models</p>
								</div>
								<div className="flex h-12 w-12 items-center justify-center rounded-lg bg-blue-500/10">
									<Bot className="h-6 w-6 text-blue-600" />
								</div>
							</div>
						</CardContent>
					</Card>

					<Card className="border-l-4 border-l-purple-500">
						<CardContent className="p-6">
							<div className="flex items-center justify-between space-x-4">
								<div className="space-y-1">
									<p className="text-3xl font-bold tracking-tight">{assignedConfigIds.length}</p>
									<p className="text-sm font-medium text-muted-foreground">Assigned Roles</p>
								</div>
								<div className="flex h-12 w-12 items-center justify-center rounded-lg bg-purple-500/10">
									<CheckCircle className="h-6 w-6 text-purple-600" />
								</div>
							</div>
						</CardContent>
					</Card>

					<Card
						className={`border-l-4 ${
							isAssignmentComplete ? "border-l-green-500" : "border-l-yellow-500"
						}`}
					>
						<CardContent className="p-6">
							<div className="flex items-center justify-between space-x-4">
								<div className="space-y-1">
									<p className="text-3xl font-bold tracking-tight">
										{Math.round((assignedConfigIds.length / 3) * 100)}%
									</p>
									<p className="text-sm font-medium text-muted-foreground">Completion</p>
								</div>
								<div
									className={`flex h-12 w-12 items-center justify-center rounded-lg ${
										isAssignmentComplete ? "bg-green-500/10" : "bg-yellow-500/10"
									}`}
								>
									{isAssignmentComplete ? (
										<CheckCircle className="h-6 w-6 text-green-600" />
									) : (
										<AlertCircle className="h-6 w-6 text-yellow-600" />
									)}
								</div>
							</div>
						</CardContent>
					</Card>

					<Card
						className={`border-l-4 ${
							isAssignmentComplete ? "border-l-emerald-500" : "border-l-orange-500"
						}`}
					>
						<CardContent className="p-6">
							<div className="flex items-center justify-between space-x-4">
								<div className="space-y-1">
									<p
										className={`text-3xl font-bold tracking-tight ${
											isAssignmentComplete ? "text-emerald-600" : "text-orange-600"
										}`}
									>
										{isAssignmentComplete ? "Ready" : "Setup"}
									</p>
									<p className="text-sm font-medium text-muted-foreground">Status</p>
								</div>
								<div
									className={`flex h-12 w-12 items-center justify-center rounded-lg ${
										isAssignmentComplete ? "bg-emerald-500/10" : "bg-orange-500/10"
									}`}
								>
									{isAssignmentComplete ? (
										<CheckCircle className="h-6 w-6 text-emerald-600" />
									) : (
										<RefreshCw className="h-6 w-6 text-orange-600" />
									)}
								</div>
							</div>
						</CardContent>
					</Card>
				</div>
			)}

			{/* Info Alert */}
			{!isLoading && !hasError && (
				<div className="space-y-6">
					{availableConfigs.length === 0 ? (
						<Alert variant="destructive">
							<AlertCircle className="h-4 w-4" />
							<AlertDescription>
								No LLM configurations found. Please add at least one LLM provider in the Model
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
													<div className="text-sm text-muted-foreground">
														<strong>Use cases:</strong> {role.examples}
													</div>
													<div className="flex flex-wrap gap-1">
														{role.characteristics.map((char, idx) => (
															<Badge key={idx} variant="outline" className="text-xs">
																{char}
															</Badge>
														))}
													</div>
												</div>

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
															{availableConfigs.map((config) => (
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
														</SelectContent>
													</Select>
												</div>

												{assignedConfig && (
													<div className="mt-3 p-3 bg-muted/50 rounded-lg">
														<div className="flex items-center gap-2 text-sm">
															<Bot className="w-4 h-4" />
															<span className="font-medium">Assigned:</span>
															<Badge variant="secondary">{assignedConfig.provider}</Badge>
															<span>{assignedConfig.name}</span>
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

					{/* Status Indicator */}
					{isAssignmentComplete && !hasChanges && (
						<div className="flex justify-center pt-4">
							<div className="flex items-center gap-2 px-4 py-2 bg-green-50 text-green-700 rounded-lg border border-green-200">
								<CheckCircle className="w-4 h-4" />
								<span className="text-sm font-medium">All roles assigned and saved!</span>
							</div>
						</div>
					)}

					{/* Progress Indicator */}
					<div className="flex justify-center">
						<div className="flex items-center gap-2 text-sm text-muted-foreground">
							<span>Progress:</span>
							<div className="flex gap-1">
								{Object.keys(ROLE_DESCRIPTIONS).map((key) => (
									<div
										key={key}
										className={`w-2 h-2 rounded-full ${
											assignments[`${key}_llm_id` as keyof typeof assignments]
												? "bg-primary"
												: "bg-muted"
										}`}
									/>
								))}
							</div>
							<span>
								{assignedConfigIds.length} of {Object.keys(ROLE_DESCRIPTIONS).length} roles assigned
							</span>
						</div>
					</div>
				</div>
			)}
		</div>
	);
}
