"use client";

import {
	AlertCircle,
	Bot,
	Check,
	CheckCircle,
	ChevronsUpDown,
	Clock,
	Edit3,
	Loader2,
	Plus,
	RefreshCw,
	Settings2,
	Trash2,
} from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useEffect, useState } from "react";
import { toast } from "sonner";
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
import { LANGUAGES } from "@/contracts/enums/languages";
import { getModelsByProvider } from "@/contracts/enums/llm-models";
import { LLM_PROVIDERS } from "@/contracts/enums/llm-providers";
import {
	useGlobalLLMConfigs,
} from "@/hooks/use-llm-configs";
import { cn } from "@/lib/utils";
import InferenceParamsEditor from "../inference-params-editor";
import { useAtomValue } from "jotai";
import { createLLMConfigMutationAtom, deleteLLMConfigMutationAtom, updateLLMConfigMutationAtom } from "@/atoms/llm-config/llm-config-mutation.atoms";
import { CreateLLMConfigRequest, CreateLLMConfigResponse, LLMConfig, UpdateLLMConfigResponse } from "@/contracts/types/llm-config.types";
import { globalLLMConfigsAtom, llmConfigsAtom } from "@/atoms/llm-config/llm-config-query.atoms";

interface ModelConfigManagerProps {
	searchSpaceId: number;
}

export function ModelConfigManager({ searchSpaceId }: ModelConfigManagerProps) {
	const { mutateAsync : createLLMConfig, isPending : isCreatingLLMConfig, error : createLLMConfigError, } = useAtomValue(createLLMConfigMutationAtom)
	const { mutateAsync : updateLLMConfig, isPending : isUpdatingLLMConfig, error : updateLLMConfigError,} = useAtomValue(updateLLMConfigMutationAtom)
	const { mutateAsync : deleteLLMConfig, isPending : isDeletingLLMConfig, error : deleteLLMConfigError, } = useAtomValue(deleteLLMConfigMutationAtom)
	const { data : llmConfigs, isFetching : isFetchingLLMConfigs, error : LLMConfigsFetchError, refetch : refreshConfigs} = useAtomValue(llmConfigsAtom)
	const { data : globalConfigs = [] } = useAtomValue(globalLLMConfigsAtom);
	const [isAddingNew, setIsAddingNew] = useState(false);
	const [editingConfig, setEditingConfig] = useState<LLMConfig | null>(null);
	const [formData, setFormData] = useState<CreateLLMConfigRequest>({
		name: "",
		provider: "" as CreateLLMConfigRequest["provider"], // Allow it as Default,
		custom_provider: "",
		model_name: "",
		api_key: "",
		api_base: "",
		language: "English",
		litellm_params: {},
		search_space_id: searchSpaceId,
	});
	const isSubmitting = isCreatingLLMConfig || isUpdatingLLMConfig
	const errors = [createLLMConfigError, updateLLMConfigError, deleteLLMConfigError, LLMConfigsFetchError] as Error[]
	const isError = Boolean(errors.filter(Boolean).length)
	const [modelComboboxOpen, setModelComboboxOpen] = useState(false);
	const [configToDelete, setConfigToDelete] = useState<LLMConfig | null>(null);
	const [isDeleting, setIsDeleting] = useState(false);

	// Populate form when editing
	useEffect(() => {
		if (editingConfig) {
			setFormData({
				name: editingConfig.name,
				provider: editingConfig.provider,
				custom_provider: editingConfig.custom_provider || "",
				model_name: editingConfig.model_name,
				api_key: editingConfig.api_key,
				api_base: editingConfig.api_base || "",
				language: editingConfig.language || "English",
				litellm_params: editingConfig.litellm_params || {},
				search_space_id: searchSpaceId,
			});
		}
	}, [editingConfig, searchSpaceId]);

	const handleInputChange = (field: keyof CreateLLMConfigRequest, value: string) => {
		setFormData((prev) => ({ ...prev, [field]: value }));
	};

	// Handle provider change with auto-fill API Base URL and reset model / 处理 Provider 变更并自动填充 API Base URL 并重置模型
	const handleProviderChange = (providerValue : CreateLLMConfigRequest["provider"]) => {
		const provider = LLM_PROVIDERS.find((p) => p.value === providerValue);
		setFormData((prev) => ({
			...prev,
			provider: providerValue,
			model_name: "", // Reset model when provider changes
			// Auto-fill API Base URL if provider has a default / 如果提供商有默认值则自动填充
			api_base: provider?.apiBase || prev.api_base,
		}));
	};

	

	const handleSubmit = async (e: React.FormEvent) => {
		e.preventDefault();
		if (!formData.name || !formData.provider || !formData.model_name || !formData.api_key) {
			toast.error("Please fill in all required fields");
			return;
		}

		let result: CreateLLMConfigResponse | UpdateLLMConfigResponse | null = null;
		if (editingConfig) {
			// Update existing config
			result = await updateLLMConfig({id : editingConfig.id, data : formData});
		} else {
			// Create new config
			result = await createLLMConfig(formData);
		}

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
			setEditingConfig(null);
		}
	};

	const handleDeleteClick = (config: LLMConfig) => {
		setConfigToDelete(config);
	};

	const handleConfirmDelete = async () => {
		if (!configToDelete) return;
		try {
			await deleteLLMConfig({id : configToDelete.id});
		} catch (error) {
			toast.error("Failed to delete configuration");
		} finally {
			setConfigToDelete(null);
		}
	};

	const selectedProvider = LLM_PROVIDERS.find((p) => p.value === formData.provider);
	const availableModels = formData.provider ? getModelsByProvider(formData.provider) : [];

	const getProviderInfo = (providerValue: string) => {
		return LLM_PROVIDERS.find((p) => p.value === providerValue);
	};

	return (
		<div className="space-y-6">
			{/* Header */}
			<div className="flex flex-col space-y-4 sm:flex-row sm:items-center sm:justify-between sm:space-y-0">
				<div className="space-y-1">
					<div className="flex items-center space-x-3">
						<div className="flex h-10 w-10 items-center justify-center rounded-lg bg-blue-500/10">
							<Settings2 className="h-5 w-5 text-blue-600" />
						</div>
						<div>
							<h2 className="text-2xl font-bold tracking-tight">Model Configurations</h2>
							<p className="text-muted-foreground">
								Manage your LLM provider configurations and API settings.
							</p>
						</div>
					</div>
				</div>
				<div className="flex items-center space-x-2">
					<Button
						variant="outline"
						size="sm"
						onClick={() => refreshConfigs()}
						disabled={isFetchingLLMConfigs}
						className="flex items-center gap-2"
					>
						<RefreshCw className={`h-4 w-4 ${isFetchingLLMConfigs ? "animate-spin" : ""}`} />
						Refresh
					</Button>
				</div>
			</div>

			{/* Error Alert */}
			{isError && errors.filter(Boolean).map(err => {
				return (
				<Alert variant="destructive">
					<AlertCircle className="h-4 w-4" />
					<AlertDescription>{err?.message ?? "Something went wrong"}</AlertDescription>
				</Alert>
			)
			}) }

			{/* Global Configs Info Alert */}
			{!isFetchingLLMConfigs && !isError && globalConfigs.length > 0 && (
				<Alert>
					<CheckCircle className="h-4 w-4" />
					<AlertDescription>
						<strong>
							{globalConfigs.length} global configuration{globalConfigs.length > 1 ? "s" : ""}
						</strong>{" "}
						available for use. You can assign them in the LLM Roles tab without adding your own API
						keys.
					</AlertDescription>
				</Alert>
			)}

			{/* Loading State */}
			{isFetchingLLMConfigs && (
				<Card>
					<CardContent className="flex items-center justify-center py-12">
						<div className="flex items-center gap-2 text-muted-foreground">
							<Loader2 className="w-5 h-5 animate-spin" />
							<span>Loading configurations...</span>
						</div>
					</CardContent>
				</Card>
			)}

			{/* Stats Overview */}
			{!isFetchingLLMConfigs && !isError&& (
				<div className="grid gap-3 grid-cols-3">
					<Card className="overflow-hidden">
						<div className="h-1 bg-blue-500" />
						<CardContent className="p-4">
							<div className="flex items-start justify-between gap-2">
								<div className="space-y-1 min-w-0">
									<p className="text-2xl font-bold tracking-tight">{llmConfigs?.length}</p>
									<p className="text-xs font-medium text-muted-foreground">Total Configs</p>
								</div>
								<div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-blue-500/10">
									<Bot className="h-4 w-4 text-blue-600" />
								</div>
							</div>
						</CardContent>
					</Card>

					<Card className="overflow-hidden">
						<div className="h-1 bg-green-500" />
						<CardContent className="p-4">
							<div className="flex items-start justify-between gap-2">
								<div className="space-y-1 min-w-0">
									<p className="text-2xl font-bold tracking-tight">
										{new Set(llmConfigs?.map((c) => c.provider)).size}
									</p>
									<p className="text-xs font-medium text-muted-foreground">Providers</p>
								</div>
								<div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-green-500/10">
									<CheckCircle className="h-4 w-4 text-green-600" />
								</div>
							</div>
						</CardContent>
					</Card>

					<Card className="overflow-hidden">
						<div className="h-1 bg-emerald-500" />
						<CardContent className="p-4">
							<div className="flex items-start justify-between gap-2">
								<div className="space-y-1 min-w-0">
									<p className="text-2xl font-bold tracking-tight text-emerald-600">Active</p>
									<p className="text-xs font-medium text-muted-foreground">Status</p>
								</div>
								<div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-emerald-500/10">
									<CheckCircle className="h-4 w-4 text-emerald-600" />
								</div>
							</div>
						</CardContent>
					</Card>
				</div>
			)}

			{/* Configuration Management */}
			{!isFetchingLLMConfigs && !isError && (
				<div className="space-y-6">
					<div className="flex flex-col space-y-4 sm:flex-row sm:items-center sm:justify-between sm:space-y-0">
						<div>
							<h3 className="text-xl font-semibold tracking-tight">Your Configurations</h3>
							<p className="text-sm text-muted-foreground">
								Manage and configure your LLM providers
							</p>
						</div>
						<Button onClick={() => setIsAddingNew(true)} className="flex items-center gap-2">
							<Plus className="h-4 w-4" />
							Add Configuration
						</Button>
					</div>

					{llmConfigs?.length === 0 ? (
						<Card className="border-dashed border-2 border-muted-foreground/25">
							<CardContent className="flex flex-col items-center justify-center py-16 text-center">
								<div className="rounded-full bg-muted p-4 mb-6">
									<Bot className="h-10 w-10 text-muted-foreground" />
								</div>
								<div className="space-y-2 mb-6">
									<h3 className="text-xl font-semibold">No Configurations Yet</h3>
									<p className="text-muted-foreground max-w-sm">
										Add your own LLM provider configurations.
									</p>
								</div>
								<Button onClick={() => setIsAddingNew(true)} size="lg">
									<Plus className="h-4 w-4 mr-2" />
									Add First Configuration
								</Button>
							</CardContent>
						</Card>
					) : (
						<div className="grid gap-4">
							<AnimatePresence>
								{llmConfigs?.map((config) => {
									const providerInfo = getProviderInfo(config.provider);
									return (
										<motion.div
											key={config.id}
											initial={{ opacity: 0, y: 10 }}
											animate={{ opacity: 1, y: 0 }}
											exit={{ opacity: 0, y: -10 }}
											transition={{ duration: 0.2 }}
										>
											<Card className="group overflow-hidden hover:shadow-md transition-all duration-200">
												<CardContent className="p-0">
													<div className="flex">
														{/* Left accent bar */}
														<div className="w-1 bg-primary/50 group-hover:bg-primary transition-colors" />

														<div className="flex-1 p-5">
															<div className="flex items-start justify-between gap-4">
																{/* Main content */}
																<div className="flex items-start gap-4 flex-1 min-w-0">
																	<div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-primary/10 group-hover:bg-primary/15 transition-colors">
																		<Bot className="h-5 w-5 text-primary" />
																	</div>
																	<div className="flex-1 min-w-0 space-y-3">
																		{/* Title row */}
																		<div className="flex items-center gap-2 flex-wrap">
																			<h4 className="text-base font-semibold tracking-tight truncate">
																				{config.name}
																			</h4>
																			<div className="flex items-center gap-1.5">
																				<Badge
																					variant="secondary"
																					className="text-[10px] font-medium px-1.5 py-0"
																				>
																					{config.provider}
																				</Badge>
																				{config.language && (
																					<Badge
																						variant="outline"
																						className="text-[10px] px-1.5 py-0 text-muted-foreground"
																					>
																						{config.language}
																					</Badge>
																				)}
																			</div>
																		</div>

																		{/* Model name */}
																		<div className="flex items-center gap-2">
																			<code className="text-xs font-mono text-muted-foreground bg-muted/50 px-2 py-0.5 rounded">
																				{config.model_name}
																			</code>
																		</div>

																		{/* Footer row */}
																		<div className="flex items-center gap-3 pt-2">
																			{config.created_at && (
																				<div className="flex items-center gap-1.5 text-xs text-muted-foreground">
																					<Clock className="h-3 w-3" />
																					<span>
																						{new Date(config.created_at).toLocaleDateString()}
																					</span>
																				</div>
																			)}
																			<div className="flex items-center gap-1.5 text-xs">
																				<div className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
																				<span className="text-emerald-600 dark:text-emerald-400 font-medium">
																					Active
																				</span>
																			</div>
																		</div>
																	</div>
																</div>

																{/* Actions */}
																<div className="flex items-center gap-1 shrink-0">
																	<Button
																		variant="ghost"
																		size="sm"
																		onClick={() => setEditingConfig(config)}
																		className="h-8 w-8 p-0 text-muted-foreground hover:text-foreground"
																	>
																		<Edit3 className="h-4 w-4" />
																	</Button>
																	<Button
																		variant="ghost"
																		size="sm"
																		onClick={() => handleDeleteClick(config)}
																		className="h-8 w-8 p-0 text-muted-foreground hover:text-destructive hover:bg-destructive/10"
																	>
																		<Trash2 className="h-4 w-4" />
																	</Button>
																</div>
															</div>
														</div>
													</div>
												</CardContent>
											</Card>
										</motion.div>
									);
								})}
							</AnimatePresence>
						</div>
					)}
				</div>
			)}

			{/* Add/Edit Configuration Dialog */}
			<Dialog
				open={isAddingNew || !!editingConfig}
				onOpenChange={(open) => {
					if (!open) {
						setIsAddingNew(false);
						setEditingConfig(null);
						setFormData({
							name: "",
							provider: "" as LLMConfig["provider"],
							custom_provider: "",
							model_name: "",
							api_key: "",
							api_base: "",
							language: "",
							litellm_params: {},
							search_space_id: searchSpaceId,
						});
					}
				}}
			>
				<DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
					<DialogHeader>
						<DialogTitle className="flex items-center gap-2">
							{editingConfig ? <Edit3 className="w-5 h-5" /> : <Plus className="w-5 h-5" />}
							{editingConfig ? "Edit LLM Configuration" : "Add New LLM Configuration"}
						</DialogTitle>
						<DialogDescription>
							{editingConfig
								? "Update your language model provider configuration"
								: "Configure a new language model provider for your AI assistant"}
						</DialogDescription>
					</DialogHeader>

					<form onSubmit={handleSubmit} className="space-y-4">
						<div className="grid grid-cols-1 md:grid-cols-2 gap-4">
							<div className="space-y-2">
								<Label htmlFor="name">Configuration Name *</Label>
								<Input
									id="name"
									placeholder="e.g., My OpenAI GPT-4"
									value={formData.name}
									onChange={(e) => handleInputChange("name", e.target.value)}
									required
								/>
							</div>

							<div className="space-y-2">
								<Label htmlFor="provider">Provider *</Label>
								<Select value={formData.provider} onValueChange={handleProviderChange}>
									<SelectTrigger>
										<SelectValue placeholder="Select a provider">
											{formData.provider && (
												<span className="font-medium">
													{LLM_PROVIDERS.find((p) => p.value === formData.provider)?.label}
												</span>
											)}
										</SelectValue>
									</SelectTrigger>
									<SelectContent>
										{LLM_PROVIDERS.map((provider) => (
											<SelectItem key={provider.value} value={provider.value}>
												<div className="space-y-1 py-1">
													<div className="font-medium">{provider.label}</div>
													<div className="text-xs text-muted-foreground">
														{provider.description}
													</div>
												</div>
											</SelectItem>
										))}
									</SelectContent>
								</Select>
							</div>
						</div>

						{formData.provider === "CUSTOM" && (
							<div className="space-y-2">
								<Label htmlFor="custom_provider">Custom Provider Name *</Label>
								<Input
									id="custom_provider"
									placeholder="e.g., my-custom-provider"
									value={formData.custom_provider ?? ""}
									onChange={(e) => handleInputChange("custom_provider", e.target.value)}
									required
								/>
							</div>
						)}

						<div className="space-y-2">
							<Label htmlFor="model_name">Model Name *</Label>
							<Popover open={modelComboboxOpen} onOpenChange={setModelComboboxOpen}>
								<PopoverTrigger asChild>
									<Button
										variant="outline"
										aria-expanded={modelComboboxOpen}
										className="w-full justify-between font-normal"
									>
										<span className={cn(!formData.model_name && "text-muted-foreground")}>
											{formData.model_name || "Select or type model name..."}
										</span>
										<ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
									</Button>
								</PopoverTrigger>
								<PopoverContent className="w-full p-0" align="start" side="bottom">
									<Command shouldFilter={false}>
										<CommandInput
											placeholder={selectedProvider?.example || "Type model name..."}
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
										? `Examples: ${selectedProvider.example}`
										: "Type your model name freely"}
							</p>
						</div>

						<div className="space-y-2">
							<Label htmlFor="language">Language (Optional)</Label>
							<Select
								value={formData.language || "English"}
								onValueChange={(value) => handleInputChange("language", value)}
							>
								<SelectTrigger>
									<SelectValue placeholder="Select language" />
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

						<div className="space-y-2">
							<Label htmlFor="api_key">API Key *</Label>
							<Input
								id="api_key"
								type="password"
								placeholder={
									formData.provider === "OLLAMA" ? "Any value (e.g., ollama)" : "Your API key"
								}
								value={formData.api_key}
								onChange={(e) => handleInputChange("api_key", e.target.value)}
								required
							/>
							{formData.provider === "OLLAMA" && (
								<p className="text-xs text-muted-foreground">
									💡 Ollama doesn't require authentication — enter any value (e.g., "ollama")
								</p>
							)}
						</div>

						<div className="space-y-2">
							<Label htmlFor="api_base">
								API Base URL
								{selectedProvider?.apiBase && (
									<span className="text-xs font-normal text-muted-foreground ml-2">
										(Auto-filled for {selectedProvider.label})
									</span>
								)}
							</Label>
							<Input
								id="api_base"
								placeholder={selectedProvider?.apiBase || "e.g., https://api.openai.com/v1"}
								value={formData.api_base ?? ""}
								onChange={(e) => handleInputChange("api_base", e.target.value)}
							/>
							{selectedProvider?.apiBase && formData.api_base === selectedProvider.apiBase && (
								<p className="text-xs text-green-600 flex items-center gap-1">
									<CheckCircle className="h-3 w-3" />
									Using recommended API endpoint for {selectedProvider.label}
								</p>
							)}
							{selectedProvider?.apiBase && !formData.api_base && (
								<p className="text-xs text-amber-600 flex items-center gap-1">
									<AlertCircle className="h-3 w-3" />
									⚠️ API Base URL is required for {selectedProvider.label}. Click to auto-fill:
									<button
										type="button"
										className="underline font-medium"
										onClick={() => handleInputChange("api_base", selectedProvider.apiBase || "")}
									>
										{selectedProvider.apiBase}
									</button>
								</p>
							)}
							{/* Ollama-specific help */}
							{formData.provider === "OLLAMA" && (
								<div className="mt-2 p-3 bg-muted/50 rounded-lg border border-muted">
									<p className="text-xs font-medium mb-2">💡 Ollama API Base URL Examples:</p>
									<div className="space-y-1.5">
										<button
											type="button"
											className="flex items-center gap-2 text-xs text-muted-foreground hover:text-foreground transition-colors"
											onClick={() => handleInputChange("api_base", "http://localhost:11434")}
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

						{/* Optional Inference Parameters */}
						<div className="pt-4">
							<InferenceParamsEditor
								params={formData.litellm_params || {}}
								setParams={(newParams) =>
									setFormData((prev) => ({ ...prev, litellm_params: newParams }))
								}
							/>
						</div>

						<div className="flex gap-2 pt-4">
							<Button type="submit" disabled={isSubmitting}>
								{isSubmitting
									? editingConfig
										? "Updating..."
										: "Adding..."
									: editingConfig
										? "Update Configuration"
										: "Add Configuration"}
							</Button>
							<Button
								type="button"
								variant="outline"
								onClick={() => {
									setIsAddingNew(false);
									setEditingConfig(null);
									setFormData({
										name: "",
										provider: "" as LLMConfig["provider"],
										custom_provider: "",
										model_name: "",
										api_key: "",
										api_base: "",
										language: "",
										litellm_params: {},
										search_space_id: searchSpaceId,
									});
								}}
								disabled={isSubmitting}
							>
								Cancel
							</Button>
						</div>
					</form>
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
							action cannot be undone and will permanently remove this model configuration.
						</AlertDialogDescription>
					</AlertDialogHeader>
					<AlertDialogFooter>
						<AlertDialogCancel disabled={isDeleting}>Cancel</AlertDialogCancel>
						<AlertDialogAction
							onClick={handleConfirmDelete}
							disabled={isDeleting}
							className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
						>
							{isDeleting ? (
								<>
									<Loader2 className="mr-2 h-4 w-4 animate-spin" />
									Deleting...
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
