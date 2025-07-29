"use client";

import { AnimatePresence, motion } from "framer-motion";
import {
	AlertCircle,
	Bot,
	CheckCircle,
	Clock,
	Edit3,
	Eye,
	EyeOff,
	Loader2,
	Plus,
	RefreshCw,
	Settings2,
	Trash2,
} from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Alert, AlertDescription } from "@/components/ui/alert";
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
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";
import { type CreateLLMConfig, type LLMConfig, useLLMConfigs } from "@/hooks/use-llm-configs";

const LLM_PROVIDERS = [
	{
		value: "OPENAI",
		label: "OpenAI",
		example: "gpt-4o, gpt-4, gpt-3.5-turbo",
		description: "Most popular and versatile AI models",
	},
	{
		value: "ANTHROPIC",
		label: "Anthropic",
		example: "claude-3-5-sonnet-20241022, claude-3-opus-20240229",
		description: "Constitutional AI with strong reasoning",
	},
	{
		value: "GROQ",
		label: "Groq",
		example: "llama3-70b-8192, mixtral-8x7b-32768",
		description: "Ultra-fast inference speeds",
	},
	{
		value: "COHERE",
		label: "Cohere",
		example: "command-r-plus, command-r",
		description: "Enterprise-focused language models",
	},
	{
		value: "HUGGINGFACE",
		label: "HuggingFace",
		example: "microsoft/DialoGPT-medium",
		description: "Open source model hub",
	},
	{
		value: "AZURE_OPENAI",
		label: "Azure OpenAI",
		example: "gpt-4, gpt-35-turbo",
		description: "Enterprise OpenAI through Azure",
	},
	{
		value: "GOOGLE",
		label: "Google",
		example: "gemini-pro, gemini-pro-vision",
		description: "Google's Gemini AI models",
	},
	{
		value: "AWS_BEDROCK",
		label: "AWS Bedrock",
		example: "anthropic.claude-v2",
		description: "AWS managed AI service",
	},
	{
		value: "OLLAMA",
		label: "Ollama",
		example: "llama2, codellama",
		description: "Run models locally",
	},
	{
		value: "MISTRAL",
		label: "Mistral",
		example: "mistral-large-latest, mistral-medium",
		description: "European AI excellence",
	},
	{
		value: "TOGETHER_AI",
		label: "Together AI",
		example: "togethercomputer/llama-2-70b-chat",
		description: "Decentralized AI platform",
	},
	{
		value: "REPLICATE",
		label: "Replicate",
		example: "meta/llama-2-70b-chat",
		description: "Run models via API",
	},
	{
		value: "CUSTOM",
		label: "Custom Provider",
		example: "your-custom-model",
		description: "Your own model endpoint",
	},
];

export function ModelConfigManager() {
	const {
		llmConfigs,
		loading,
		error,
		createLLMConfig,
		updateLLMConfig,
		deleteLLMConfig,
		refreshConfigs,
	} = useLLMConfigs();
	const [isAddingNew, setIsAddingNew] = useState(false);
	const [editingConfig, setEditingConfig] = useState<LLMConfig | null>(null);
	const [showApiKey, setShowApiKey] = useState<Record<number, boolean>>({});
	const [formData, setFormData] = useState<CreateLLMConfig>({
		name: "",
		provider: "",
		custom_provider: "",
		model_name: "",
		api_key: "",
		api_base: "",
		litellm_params: {},
	});
	const [isSubmitting, setIsSubmitting] = useState(false);

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
				litellm_params: editingConfig.litellm_params || {},
			});
		}
	}, [editingConfig]);

	const handleInputChange = (field: keyof CreateLLMConfig, value: string) => {
		setFormData((prev) => ({ ...prev, [field]: value }));
	};

	const handleSubmit = async (e: React.FormEvent) => {
		e.preventDefault();
		if (!formData.name || !formData.provider || !formData.model_name || !formData.api_key) {
			toast.error("Please fill in all required fields");
			return;
		}

		setIsSubmitting(true);

		let result: LLMConfig | null = null;
		if (editingConfig) {
			// Update existing config
			result = await updateLLMConfig(editingConfig.id, formData);
		} else {
			// Create new config
			result = await createLLMConfig(formData);
		}

		setIsSubmitting(false);

		if (result) {
			setFormData({
				name: "",
				provider: "",
				custom_provider: "",
				model_name: "",
				api_key: "",
				api_base: "",
				litellm_params: {},
			});
			setIsAddingNew(false);
			setEditingConfig(null);
		}
	};

	const handleDelete = async (id: number) => {
		if (
			confirm("Are you sure you want to delete this configuration? This action cannot be undone.")
		) {
			await deleteLLMConfig(id);
		}
	};

	const toggleApiKeyVisibility = (configId: number) => {
		setShowApiKey((prev) => ({
			...prev,
			[configId]: !prev[configId],
		}));
	};

	const selectedProvider = LLM_PROVIDERS.find((p) => p.value === formData.provider);

	const getProviderInfo = (providerValue: string) => {
		return LLM_PROVIDERS.find((p) => p.value === providerValue);
	};

	const maskApiKey = (apiKey: string) => {
		if (apiKey.length <= 8) return "*".repeat(apiKey.length);
		return (
			apiKey.substring(0, 4) + "*".repeat(apiKey.length - 8) + apiKey.substring(apiKey.length - 4)
		);
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
						onClick={refreshConfigs}
						disabled={loading}
						className="flex items-center gap-2"
					>
						<RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
						Refresh
					</Button>
				</div>
			</div>

			{/* Error Alert */}
			{error && (
				<Alert variant="destructive">
					<AlertCircle className="h-4 w-4" />
					<AlertDescription>{error}</AlertDescription>
				</Alert>
			)}

			{/* Loading State */}
			{loading && (
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
			{!loading && !error && (
				<div className="grid gap-4 md:grid-cols-3">
					<Card className="border-l-4 border-l-blue-500">
						<CardContent className="p-6">
							<div className="flex items-center justify-between space-x-4">
								<div className="space-y-1">
									<p className="text-3xl font-bold tracking-tight">{llmConfigs.length}</p>
									<p className="text-sm font-medium text-muted-foreground">Total Configurations</p>
								</div>
								<div className="flex h-12 w-12 items-center justify-center rounded-lg bg-blue-500/10">
									<Bot className="h-6 w-6 text-blue-600" />
								</div>
							</div>
						</CardContent>
					</Card>

					<Card className="border-l-4 border-l-green-500">
						<CardContent className="p-6">
							<div className="flex items-center justify-between space-x-4">
								<div className="space-y-1">
									<p className="text-3xl font-bold tracking-tight">
										{new Set(llmConfigs.map((c) => c.provider)).size}
									</p>
									<p className="text-sm font-medium text-muted-foreground">Unique Providers</p>
								</div>
								<div className="flex h-12 w-12 items-center justify-center rounded-lg bg-green-500/10">
									<CheckCircle className="h-6 w-6 text-green-600" />
								</div>
							</div>
						</CardContent>
					</Card>

					<Card className="border-l-4 border-l-emerald-500">
						<CardContent className="p-6">
							<div className="flex items-center justify-between space-x-4">
								<div className="space-y-1">
									<p className="text-3xl font-bold tracking-tight text-emerald-600">Active</p>
									<p className="text-sm font-medium text-muted-foreground">System Status</p>
								</div>
								<div className="flex h-12 w-12 items-center justify-center rounded-lg bg-emerald-500/10">
									<CheckCircle className="h-6 w-6 text-emerald-600" />
								</div>
							</div>
						</CardContent>
					</Card>
				</div>
			)}

			{/* Configuration Management */}
			{!loading && !error && (
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

					{llmConfigs.length === 0 ? (
						<Card className="border-dashed border-2 border-muted-foreground/25">
							<CardContent className="flex flex-col items-center justify-center py-16 text-center">
								<div className="rounded-full bg-muted p-4 mb-6">
									<Bot className="h-10 w-10 text-muted-foreground" />
								</div>
								<div className="space-y-2 mb-6">
									<h3 className="text-xl font-semibold">No Configurations Yet</h3>
									<p className="text-muted-foreground max-w-sm">
										Get started by adding your first LLM provider configuration to begin using the
										system.
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
								{llmConfigs.map((config) => {
									const providerInfo = getProviderInfo(config.provider);
									return (
										<motion.div
											key={config.id}
											initial={{ opacity: 0, y: 10 }}
											animate={{ opacity: 1, y: 0 }}
											exit={{ opacity: 0, y: -10 }}
											transition={{ duration: 0.2 }}
										>
											<Card className="group border-l-4 border-l-primary/50 hover:border-l-primary hover:shadow-md transition-all duration-200">
												<CardContent className="p-6">
													<div className="flex items-start justify-between">
														<div className="flex-1 space-y-4">
															{/* Header */}
															<div className="flex items-start gap-4">
																<div className="flex h-12 w-12 items-center justify-center rounded-lg bg-primary/10 group-hover:bg-primary/20 transition-colors">
																	<Bot className="h-6 w-6 text-primary" />
																</div>
																<div className="flex-1 space-y-2">
																	<div className="flex items-center gap-3">
																		<h4 className="text-lg font-semibold tracking-tight">
																			{config.name}
																		</h4>
																		<Badge variant="secondary" className="text-xs font-medium">
																			{config.provider}
																		</Badge>
																	</div>
																	<p className="text-sm text-muted-foreground font-mono">
																		{config.model_name}
																	</p>
																</div>
															</div>

															{/* Provider Description */}
															{providerInfo && (
																<p className="text-sm text-muted-foreground">
																	{providerInfo.description}
																</p>
															)}

															{/* Configuration Details */}
															<div className="grid gap-4 sm:grid-cols-2">
																<div className="space-y-2">
																	<Label className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
																		API Key
																	</Label>
																	<div className="flex items-center space-x-2">
																		<code className="flex-1 rounded-md bg-muted px-3 py-2 text-xs font-mono">
																			{showApiKey[config.id]
																				? config.api_key
																				: maskApiKey(config.api_key)}
																		</code>
																		<Button
																			variant="ghost"
																			size="sm"
																			onClick={() => toggleApiKeyVisibility(config.id)}
																			className="h-8 w-8 p-0"
																		>
																			{showApiKey[config.id] ? (
																				<EyeOff className="h-3 w-3" />
																			) : (
																				<Eye className="h-3 w-3" />
																			)}
																		</Button>
																	</div>
																</div>

																{config.api_base && (
																	<div className="space-y-2">
																		<Label className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
																			API Base URL
																		</Label>
																		<code className="block rounded-md bg-muted px-3 py-2 text-xs font-mono break-all">
																			{config.api_base}
																		</code>
																	</div>
																)}
															</div>

															{/* Metadata */}
															<div className="flex flex-wrap items-center gap-4 pt-4 border-t border-border/50">
																<div className="flex items-center gap-2 text-xs text-muted-foreground">
																	<Clock className="h-3 w-3" />
																	<span>
																		Created {new Date(config.created_at).toLocaleDateString()}
																	</span>
																</div>
																<div className="flex items-center gap-2 text-xs">
																	<div className="h-2 w-2 rounded-full bg-green-500"></div>
																	<span className="text-green-600 font-medium">Active</span>
																</div>
															</div>
														</div>

														{/* Actions */}
														<div className="flex flex-col gap-2 ml-6">
															<Button
																variant="outline"
																size="sm"
																onClick={() => setEditingConfig(config)}
																className="h-8 w-8 p-0"
															>
																<Edit3 className="h-4 w-4" />
															</Button>
															<Button
																variant="outline"
																size="sm"
																onClick={() => handleDelete(config.id)}
																className="h-8 w-8 p-0 border-destructive/20 text-destructive hover:bg-destructive hover:text-destructive-foreground"
															>
																<Trash2 className="h-4 w-4" />
															</Button>
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
							provider: "",
							custom_provider: "",
							model_name: "",
							api_key: "",
							api_base: "",
							litellm_params: {},
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
								<Select
									value={formData.provider}
									onValueChange={(value) => handleInputChange("provider", value)}
								>
									<SelectTrigger className="h-auto min-h-[2.5rem] py-2">
										<SelectValue placeholder="Select a provider">
											{formData.provider && (
												<div className="flex items-center space-x-2 py-1">
													<div className="font-medium">
														{LLM_PROVIDERS.find((p) => p.value === formData.provider)?.label}
													</div>
													<div className="text-xs text-muted-foreground">•</div>
													<div className="text-xs text-muted-foreground">
														{LLM_PROVIDERS.find((p) => p.value === formData.provider)?.description}
													</div>
												</div>
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
									value={formData.custom_provider}
									onChange={(e) => handleInputChange("custom_provider", e.target.value)}
									required
								/>
							</div>
						)}

						<div className="space-y-2">
							<Label htmlFor="model_name">Model Name *</Label>
							<Input
								id="model_name"
								placeholder={selectedProvider?.example || "e.g., gpt-4"}
								value={formData.model_name}
								onChange={(e) => handleInputChange("model_name", e.target.value)}
								required
							/>
							{selectedProvider && (
								<p className="text-xs text-muted-foreground">
									Examples: {selectedProvider.example}
								</p>
							)}
						</div>

						<div className="space-y-2">
							<Label htmlFor="api_key">API Key *</Label>
							<Input
								id="api_key"
								type="password"
								placeholder="Your API key"
								value={formData.api_key}
								onChange={(e) => handleInputChange("api_key", e.target.value)}
								required
							/>
						</div>

						<div className="space-y-2">
							<Label htmlFor="api_base">API Base URL (Optional)</Label>
							<Input
								id="api_base"
								placeholder="e.g., https://api.openai.com/v1"
								value={formData.api_base}
								onChange={(e) => handleInputChange("api_base", e.target.value)}
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
										provider: "",
										custom_provider: "",
										model_name: "",
										api_key: "",
										api_base: "",
										litellm_params: {},
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
		</div>
	);
}
