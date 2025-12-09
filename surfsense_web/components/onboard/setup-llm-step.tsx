"use client";

import {
	AlertCircle,
	Bot,
	Brain,
	Check,
	CheckCircle,
	ChevronDown,
	ChevronsUpDown,
	ChevronUp,
	Plus,
	Trash2,
	Zap,
} from "lucide-react";
import { motion } from "motion/react";
import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Alert, AlertDescription } from "@/components/ui/alert";
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
import { LANGUAGES } from "@/contracts/enums/languages";
import { getModelsByProvider } from "@/contracts/enums/llm-models";
import { LLM_PROVIDERS } from "@/contracts/enums/llm-providers";
import {
	type CreateLLMConfig,
	useGlobalLLMConfigs,
	useLLMConfigs,
	useLLMPreferences,
} from "@/hooks/use-llm-configs";
import { cn } from "@/lib/utils";

import InferenceParamsEditor from "../inference-params-editor";
import { useAtomValue } from "jotai";
import { createLLMConfigMutationAtom } from "@/atoms/llm-config/llm-config-mutation.atoms";
import { CreateLLMConfigRequest } from "@/contracts/types/llm-config.types";

interface SetupLLMStepProps {
	searchSpaceId: number;
	onConfigCreated?: () => void;
	onConfigDeleted?: () => void;
	onPreferencesUpdated?: () => Promise<void>;
}

const ROLE_DESCRIPTIONS = {
	long_context: {
		icon: Brain,
		key: "long_context_llm_id" as const,
		titleKey: "long_context_llm_title",
		descKey: "long_context_llm_desc",
		examplesKey: "long_context_llm_examples",
		color:
			"bg-blue-100 text-blue-800 border-blue-200 dark:bg-blue-950 dark:text-blue-200 dark:border-blue-800",
	},
	fast: {
		icon: Zap,
		key: "fast_llm_id" as const,
		titleKey: "fast_llm_title",
		descKey: "fast_llm_desc",
		examplesKey: "fast_llm_examples",
		color:
			"bg-green-100 text-green-800 border-green-200 dark:bg-green-950 dark:text-green-200 dark:border-green-800",
	},
	strategic: {
		icon: Bot,
		key: "strategic_llm_id" as const,
		titleKey: "strategic_llm_title",
		descKey: "strategic_llm_desc",
		examplesKey: "strategic_llm_examples",
		color:
			"bg-purple-100 text-purple-800 border-purple-200 dark:bg-purple-950 dark:text-purple-200 dark:border-purple-800",
	},
};

export function SetupLLMStep({
	searchSpaceId,
	onConfigCreated,
	onConfigDeleted,
	onPreferencesUpdated,
}: SetupLLMStepProps) {
	const t = useTranslations("onboard");
	const { llmConfigs, deleteLLMConfig } = useLLMConfigs(searchSpaceId);
	const { mutateAsync : createLLMConfig, isPending : isCreatingLlmConfig } = useAtomValue(createLLMConfigMutationAtom)
	const { globalConfigs } = useGlobalLLMConfigs();
	const { preferences, updatePreferences } = useLLMPreferences(searchSpaceId);

	const [isAddingNew, setIsAddingNew] = useState(false);
	const [formData, setFormData] = useState<CreateLLMConfigRequest>({
		name: "",
		provider: "" as CreateLLMConfigRequest["provider"], // Allow it as Default
		custom_provider: "",
		model_name: "",
		api_key: "",
		api_base: "",
		language: "English",
		litellm_params: {},
		search_space_id: searchSpaceId,
	});
	const [modelComboboxOpen, setModelComboboxOpen] = useState(false);
	const [showProviderForm, setShowProviderForm] = useState(false);

	// Role assignments state
	const [assignments, setAssignments] = useState({
		long_context_llm_id: preferences.long_context_llm_id || "",
		fast_llm_id: preferences.fast_llm_id || "",
		strategic_llm_id: preferences.strategic_llm_id || "",
	});

	// Combine global and user-specific configs
	const allConfigs = [...globalConfigs, ...llmConfigs];

	useEffect(() => {
		setAssignments({
			long_context_llm_id: preferences.long_context_llm_id || "",
			fast_llm_id: preferences.fast_llm_id || "",
			strategic_llm_id: preferences.strategic_llm_id || "",
		});
	}, [preferences]);

	const handleInputChange = (field: keyof CreateLLMConfig, value: string) => {
		setFormData((prev) => ({ ...prev, [field]: value }));
	};

	const handleSubmit = async (e: React.FormEvent) => {
		e.preventDefault();
		if (!formData.name || !formData.provider || !formData.model_name || !formData.api_key) {
			toast.error("Please fill in all required fields");
			return;
		}

		const result = await createLLMConfig(formData);

		if (result) {
			setFormData({
				name: "",
				provider: "" as CreateLLMConfigRequest["provider"],
				custom_provider: "",
				model_name: "",
				api_key: "",
				api_base: "",
				language: "English",
				litellm_params: {},
				search_space_id: searchSpaceId,
			});
			setIsAddingNew(false);
			onConfigCreated?.();
		}
	};

	const handleRoleAssignment = async (role: string, configId: string) => {
		const newAssignments = {
			...assignments,
			[role]: configId === "" ? "" : parseInt(configId),
		};

		setAssignments(newAssignments);

		// Auto-save if this assignment completes all roles
		const hasAllAssignments =
			newAssignments.long_context_llm_id &&
			newAssignments.fast_llm_id &&
			newAssignments.strategic_llm_id;

		if (hasAllAssignments) {
			const numericAssignments = {
				long_context_llm_id:
					typeof newAssignments.long_context_llm_id === "string"
						? parseInt(newAssignments.long_context_llm_id)
						: newAssignments.long_context_llm_id,
				fast_llm_id:
					typeof newAssignments.fast_llm_id === "string"
						? parseInt(newAssignments.fast_llm_id)
						: newAssignments.fast_llm_id,
				strategic_llm_id:
					typeof newAssignments.strategic_llm_id === "string"
						? parseInt(newAssignments.strategic_llm_id)
						: newAssignments.strategic_llm_id,
			};

			const success = await updatePreferences(numericAssignments);

			if (success && onPreferencesUpdated) {
				await onPreferencesUpdated();
			}
		}
	};

	const selectedProvider = LLM_PROVIDERS.find((p) => p.value === formData.provider);
	const availableModels = formData.provider ? getModelsByProvider(formData.provider) : [];

	const handleParamsChange = (newParams: Record<string, number | string>) => {
		setFormData((prev) => ({ ...prev, litellm_params: newParams }));
	};

	const handleProviderChange = (value: string) => {
		handleInputChange("provider", value);
		setFormData((prev) => ({ ...prev, model_name: "" }));
	};

	const isAssignmentComplete =
		assignments.long_context_llm_id && assignments.fast_llm_id && assignments.strategic_llm_id;

	return (
		<div className="space-y-8">
			{/* Global Configs Notice - Prominent at top */}
			{globalConfigs.length > 0 && (
				<Alert className="bg-blue-50 border-blue-200 dark:bg-blue-950 dark:border-blue-800">
					<CheckCircle className="h-4 w-4 text-blue-600 dark:text-blue-400" />
					<AlertDescription className="text-blue-800 dark:text-blue-200">
						<div className="space-y-2">
							<p className="font-semibold text-base">
								{globalConfigs.length} global configuration(s) available!
							</p>
							<p className="text-sm">
								You can skip adding your own LLM provider and use our pre-configured models in the
								role assignment section below.
							</p>
							<p className="text-sm">
								Or expand "Add LLM Provider" to add your own custom configurations.
							</p>
						</div>
					</AlertDescription>
				</Alert>
			)}

			{/* Section 1: Add LLM Providers */}
			<div className="space-y-4">
				<div className="flex items-center justify-between">
					<div>
						<h3 className="text-xl font-semibold flex items-center gap-2">
							<Bot className="w-5 h-5" />
							{t("add_llm_provider")}
						</h3>
						<p className="text-sm text-muted-foreground mt-1">{t("configure_first_provider")}</p>
					</div>
					<Button
						variant="ghost"
						size="sm"
						onClick={() => setShowProviderForm(!showProviderForm)}
						className="gap-2"
					>
						{showProviderForm ? (
							<>
								<ChevronUp className="w-4 h-4" />
								Collapse
							</>
						) : (
							<>
								<ChevronDown className="w-4 h-4" />
								Expand
							</>
						)}
					</Button>
				</div>

				{showProviderForm && (
					<motion.div
						initial={{ opacity: 0, height: 0 }}
						animate={{ opacity: 1, height: "auto" }}
						exit={{ opacity: 0, height: 0 }}
						transition={{ duration: 0.3 }}
						className="space-y-4"
					>
						{/* Info Alert */}
						<Alert>
							<AlertCircle className="h-4 w-4" />
							<AlertDescription>{t("add_provider_instruction")}</AlertDescription>
						</Alert>

						{/* Existing Configurations */}
						{llmConfigs.length > 0 && (
							<div className="space-y-3">
								<h4 className="text-sm font-semibold text-muted-foreground">
									{t("your_llm_configs")}
								</h4>
								<div className="grid gap-3">
									{llmConfigs.map((config) => (
										<motion.div
											key={config.id}
											initial={{ opacity: 0, y: 10 }}
											animate={{ opacity: 1, y: 0 }}
											exit={{ opacity: 0, y: -10 }}
										>
											<Card className="border-l-4 border-l-primary">
												<CardContent className="pt-4">
													<div className="flex items-center justify-between">
														<div className="flex-1">
															<div className="flex items-center gap-2 mb-1">
																<Bot className="w-4 h-4" />
																<h4 className="font-medium">{config.name}</h4>
																<Badge variant="secondary" className="text-xs">
																	{config.provider}
																</Badge>
															</div>
															<p className="text-sm text-muted-foreground">
																{t("model")}: {config.model_name}
																{config.language && ` • ${t("language")}: ${config.language}`}
																{config.api_base && ` • ${t("base")}: ${config.api_base}`}
															</p>
														</div>
														<Button
															variant="ghost"
															size="sm"
															onClick={async () => {
																const success = await deleteLLMConfig(config.id);
																if (success) {
																	onConfigDeleted?.();
																}
															}}
															className="text-destructive hover:text-destructive"
														>
															<Trash2 className="w-4 h-4" />
														</Button>
													</div>
												</CardContent>
											</Card>
										</motion.div>
									))}
								</div>
							</div>
						)}

						{/* Add New Provider */}
						{!isAddingNew ? (
							<Card className="border-dashed border-2 hover:border-primary/50 transition-colors">
								<CardContent className="flex flex-col items-center justify-center py-8">
									<Plus className="w-8 h-8 text-muted-foreground mb-3" />
									<h4 className="font-semibold mb-1">{t("add_provider_title")}</h4>
									<p className="text-sm text-muted-foreground text-center mb-3">
										{t("add_provider_subtitle")}
									</p>
									<Button onClick={() => setIsAddingNew(true)} size="sm">
										<Plus className="w-4 h-4 mr-2" />
										{t("add_provider_button")}
									</Button>
								</CardContent>
							</Card>
						) : (
							<Card>
								<CardHeader>
									<CardTitle className="text-lg">{t("add_new_llm_provider")}</CardTitle>
									<CardDescription>{t("configure_new_provider")}</CardDescription>
								</CardHeader>
								<CardContent>
									<form onSubmit={handleSubmit} className="space-y-4">
										<div className="grid grid-cols-1 md:grid-cols-3 gap-4">
											<div className="space-y-2">
												<Label htmlFor="name">{t("config_name_required")}</Label>
												<Input
													id="name"
													placeholder={t("config_name_placeholder")}
													value={formData.name}
													onChange={(e) => handleInputChange("name", e.target.value)}
													required
												/>
											</div>

											<div className="space-y-2">
												<Label htmlFor="provider">{t("provider_required")}</Label>
												<Select value={formData.provider} onValueChange={handleProviderChange}>
													<SelectTrigger>
														<SelectValue placeholder={t("provider_placeholder")} />
													</SelectTrigger>
													<SelectContent className="max-h-[300px]">
														{LLM_PROVIDERS.map((provider) => (
															<SelectItem key={provider.value} value={provider.value}>
																{provider.label}
															</SelectItem>
														))}
													</SelectContent>
												</Select>
											</div>

											<div className="space-y-2">
												<Label htmlFor="language">{t("language_optional")}</Label>
												<Select
													value={formData.language || "English"}
													onValueChange={(value) => handleInputChange("language", value)}
												>
													<SelectTrigger>
														<SelectValue placeholder={t("language_placeholder")} />
													</SelectTrigger>
													<SelectContent>
														{LANGUAGES.map((language) => (
															<SelectItem key={language.value} value={language.value}>
																{language.label}
															</SelectItem>
														))}
													</SelectContent>
												</Select>
											</div>
										</div>

										{formData.provider === "CUSTOM" && (
											<div className="space-y-2">
												<Label htmlFor="custom_provider">{t("custom_provider_name")}</Label>
												<Input
													id="custom_provider"
													placeholder={t("custom_provider_placeholder")}
													value={formData.custom_provider ?? ""}
													onChange={(e) => handleInputChange("custom_provider", e.target.value)}
													required
												/>
											</div>
										)}

										<div className="space-y-2">
											<Label htmlFor="model_name">{t("model_name_required")}</Label>
											<Popover open={modelComboboxOpen} onOpenChange={setModelComboboxOpen}>
												<PopoverTrigger asChild>
													<Button
														variant="outline"
														aria-expanded={modelComboboxOpen}
														className="w-full justify-between font-normal"
													>
														<span className={cn(!formData.model_name && "text-muted-foreground")}>
															{formData.model_name || t("model_name_placeholder")}
														</span>
														<ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
													</Button>
												</PopoverTrigger>
												<PopoverContent className="w-full p-0" align="start" side="bottom">
													<Command shouldFilter={false}>
														<CommandInput
															placeholder={
																selectedProvider?.example ||
																t("model_name_placeholder") ||
																"Type model name..."
															}
															value={formData.model_name}
															onValueChange={(value) => handleInputChange("model_name", value)}
														/>
														<CommandList>
															<CommandEmpty>
																<div className="py-2 text-center text-sm text-muted-foreground">
																	{formData.model_name
																		? `Using custom model: "${formData.model_name}"`
																		: "Type your model name above"}
																</div>
															</CommandEmpty>
															{availableModels.length > 0 && (
																<CommandGroup heading="Suggested Models">
																	{availableModels
																		.filter(
																			(model) =>
																				!formData.model_name ||
																				model.value
																					.toLowerCase()
																					.includes(formData.model_name.toLowerCase()) ||
																				model.label
																					.toLowerCase()
																					.includes(formData.model_name.toLowerCase())
																		)
																		.map((model) => (
																			<CommandItem
																				key={model.value}
																				value={model.value}
																				onSelect={(currentValue) => {
																					handleInputChange("model_name", currentValue);
																					setModelComboboxOpen(false);
																				}}
																				className="flex flex-col items-start py-3"
																			>
																				<div className="flex w-full items-center">
																					<Check
																						className={cn(
																							"mr-2 h-4 w-4 shrink-0",
																							formData.model_name === model.value
																								? "opacity-100"
																								: "opacity-0"
																						)}
																					/>
																					<div className="flex-1">
																						<div className="font-medium">{model.label}</div>
																						{model.contextWindow && (
																							<div className="text-xs text-muted-foreground">
																								Context: {model.contextWindow}
																							</div>
																						)}
																					</div>
																				</div>
																			</CommandItem>
																		))}
																</CommandGroup>
															)}
														</CommandList>
													</Command>
												</PopoverContent>
											</Popover>
											<p className="text-xs text-muted-foreground">
												{availableModels.length > 0
													? `Type freely or select from ${availableModels.length} model suggestions`
													: selectedProvider?.example
														? `${t("examples")}: ${selectedProvider.example}`
														: "Type your model name freely"}
											</p>
										</div>

										<div className="space-y-2">
											<Label htmlFor="api_key">{t("api_key_required")}</Label>
											<Input
												id="api_key"
												type="password"
												placeholder={
													formData.provider === "OLLAMA"
														? "Any value (e.g., ollama)"
														: t("api_key_placeholder")
												}
												value={formData.api_key}
												onChange={(e) => handleInputChange("api_key", e.target.value)}
												required
											/>
											{formData.provider === "OLLAMA" && (
												<p className="text-xs text-muted-foreground">
													💡 Ollama doesn't require authentication — enter any value (e.g.,
													"ollama")
												</p>
											)}
										</div>

										<div className="space-y-2">
											<Label htmlFor="api_base">{t("api_base_optional")}</Label>
											<Input
												id="api_base"
												placeholder={selectedProvider?.apiBase || t("api_base_placeholder")}
												value={formData.api_base ?? ""}
												onChange={(e) => handleInputChange("api_base", e.target.value)}
											/>
											{/* Ollama-specific help */}
											{formData.provider === "OLLAMA" && (
												<div className="mt-2 p-3 bg-muted/50 rounded-lg border border-muted">
													<p className="text-xs font-medium mb-2">
														💡 Ollama API Base URL Examples:
													</p>
													<div className="space-y-1.5">
														<button
															type="button"
															className="flex items-center gap-2 text-xs text-muted-foreground hover:text-foreground transition-colors"
															onClick={() =>
																handleInputChange("api_base", "http://localhost:11434")
															}
														>
															<code className="px-1.5 py-0.5 bg-background rounded border">
																http://localhost:11434
															</code>
															<span>— Standard local installation</span>
														</button>
														<button
															type="button"
															className="flex items-center gap-2 text-xs text-muted-foreground hover:text-foreground transition-colors"
															onClick={() =>
																handleInputChange("api_base", "http://host.docker.internal:11434")
															}
														>
															<code className="px-1.5 py-0.5 bg-background rounded border">
																http://host.docker.internal:11434
															</code>
															<span>— If using SurfSense Docker image</span>
														</button>
													</div>
												</div>
											)}
										</div>

										<div className="pt-2">
											<InferenceParamsEditor
												params={formData.litellm_params || {}}
												setParams={handleParamsChange}
											/>
										</div>

										<div className="flex gap-2 pt-2">
											<Button type="submit" disabled={isCreatingLlmConfig} size="sm">
												{isCreatingLlmConfig ? t("adding") : t("add_provider")}
											</Button>
											<Button
												type="button"
												variant="outline"
												size="sm"
												onClick={() => setIsAddingNew(false)}
												disabled={isCreatingLlmConfig}
											>
												{t("cancel")}
											</Button>
										</div>
									</form>
								</CardContent>
							</Card>
						)}
					</motion.div>
				)}
			</div>

			<Separator className="my-8" />

			{/* Section 2: Assign Roles */}
			<div className="space-y-4">
				<div>
					<h3 className="text-xl font-semibold flex items-center gap-2">
						<Brain className="w-5 h-5" />
						{t("assign_llm_roles")}
					</h3>
					<p className="text-sm text-muted-foreground mt-1">{t("assign_specific_roles")}</p>
				</div>

				{allConfigs.length === 0 ? (
					<Alert>
						<AlertCircle className="h-4 w-4" />
						<AlertDescription>{t("add_provider_before_roles")}</AlertDescription>
					</Alert>
				) : (
					<div className="space-y-4">
						<Alert>
							<AlertCircle className="h-4 w-4" />
							<AlertDescription>{t("assign_roles_instruction")}</AlertDescription>
						</Alert>

						<div className="grid gap-4">
							{Object.entries(ROLE_DESCRIPTIONS).map(([roleKey, role]) => {
								const IconComponent = role.icon;
								const currentAssignment = assignments[role.key];
								const assignedConfig = allConfigs.find((config) => config.id === currentAssignment);

								return (
									<motion.div
										key={roleKey}
										initial={{ opacity: 0, y: 10 }}
										animate={{ opacity: 1, y: 0 }}
										transition={{ delay: Object.keys(ROLE_DESCRIPTIONS).indexOf(roleKey) * 0.1 }}
									>
										<Card
											className={`border-l-4 ${currentAssignment ? "border-l-primary" : "border-l-muted"}`}
										>
											<CardHeader className="pb-3">
												<div className="flex items-center justify-between">
													<div className="flex items-center gap-3">
														<div className={`p-2 rounded-lg ${role.color}`}>
															<IconComponent className="w-5 h-5" />
														</div>
														<div>
															<CardTitle className="text-base">{t(role.titleKey)}</CardTitle>
															<CardDescription className="mt-1 text-xs">
																{t(role.descKey)}
															</CardDescription>
														</div>
													</div>
													{currentAssignment && <CheckCircle className="w-5 h-5 text-green-500" />}
												</div>
											</CardHeader>
											<CardContent className="space-y-3">
												<div className="space-y-2">
													<Label className="text-sm font-medium">{t("assign_llm_config")}:</Label>
													<Select
														value={currentAssignment?.toString() || ""}
														onValueChange={(value) => handleRoleAssignment(role.key, value)}
													>
														<SelectTrigger>
															<SelectValue placeholder={t("select_llm_config")} />
														</SelectTrigger>
														<SelectContent>
															{globalConfigs.length > 0 && (
																<div className="px-2 py-1.5 text-xs font-semibold text-muted-foreground">
																	{t("global_configs") || "Global Configurations"}
																</div>
															)}
															{globalConfigs
																.filter((config) => config.id && config.id.toString().trim() !== "")
																.map((config) => (
																	<SelectItem key={config.id} value={config.id.toString()}>
																		<div className="flex items-center gap-2">
																			<Badge variant="secondary" className="text-xs">
																				🌐 Global
																			</Badge>
																			<Badge variant="outline" className="text-xs">
																				{config.provider}
																			</Badge>
																			<span className="text-sm">{config.name}</span>
																			<span className="text-xs text-muted-foreground">
																				({config.model_name})
																			</span>
																		</div>
																	</SelectItem>
																))}
															{llmConfigs.length > 0 && globalConfigs.length > 0 && (
																<div className="px-2 py-1.5 text-xs font-semibold text-muted-foreground border-t mt-1">
																	{t("your_configs") || "Your Configurations"}
																</div>
															)}
															{llmConfigs
																.filter((config) => config.id && config.id.toString().trim() !== "")
																.map((config) => (
																	<SelectItem key={config.id} value={config.id.toString()}>
																		<div className="flex items-center gap-2">
																			<Badge variant="outline" className="text-xs">
																				{config.provider}
																			</Badge>
																			<span className="text-sm">{config.name}</span>
																			<span className="text-xs text-muted-foreground">
																				({config.model_name})
																			</span>
																		</div>
																	</SelectItem>
																))}
														</SelectContent>
													</Select>
												</div>

												{assignedConfig && (
													<div className="mt-2 p-3 bg-muted/50 rounded-lg">
														<div className="flex items-center gap-2 text-sm">
															<Bot className="w-4 h-4" />
															<span className="font-medium">{t("assigned")}:</span>
															{assignedConfig.is_global && (
																<Badge variant="secondary" className="text-xs">
																	🌐 Global
																</Badge>
															)}
															<Badge variant="secondary" className="text-xs">
																{assignedConfig.provider}
															</Badge>
															<span className="text-sm">{assignedConfig.name}</span>
														</div>
														<div className="text-xs text-muted-foreground mt-1">
															{t("model")}: {assignedConfig.model_name}
														</div>
													</div>
												)}
											</CardContent>
										</Card>
									</motion.div>
								);
							})}
						</div>

						{/* Status Indicators */}
						<div className="flex flex-col sm:flex-row items-center justify-between gap-3 pt-2">
							<div className="flex items-center gap-2 text-sm text-muted-foreground">
								<span>{t("progress")}:</span>
								<div className="flex gap-1">
									{Object.keys(ROLE_DESCRIPTIONS).map((key) => {
										const roleKey = ROLE_DESCRIPTIONS[key as keyof typeof ROLE_DESCRIPTIONS].key;
										return (
											<div
												key={key}
												className={`w-2 h-2 rounded-full ${
													assignments[roleKey] ? "bg-primary" : "bg-muted"
												}`}
											/>
										);
									})}
								</div>
								<span>
									{t("roles_assigned", {
										assigned: Object.values(assignments).filter(Boolean).length,
										total: Object.keys(ROLE_DESCRIPTIONS).length,
									})}
								</span>
							</div>

							{isAssignmentComplete && (
								<div className="flex items-center gap-2 px-3 py-1.5 bg-green-50 text-green-700 dark:bg-green-950 dark:text-green-200 rounded-lg border border-green-200 dark:border-green-800">
									<CheckCircle className="w-4 h-4" />
									<span className="text-sm font-medium">{t("all_roles_assigned_saved")}</span>
								</div>
							)}
						</div>
					</div>
				)}
			</div>
		</div>
	);
}
