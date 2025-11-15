"use client";

import { AlertCircle, Bot, Check, CheckCircle, ChevronsUpDown, Plus, Trash2 } from "lucide-react";
import { motion } from "motion/react";
import { useTranslations } from "next-intl";
import { useState } from "react";
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
import { LANGUAGES } from "@/contracts/enums/languages";
import { getModelsByProvider } from "@/contracts/enums/llm-models";
import { LLM_PROVIDERS } from "@/contracts/enums/llm-providers";
import { type CreateLLMConfig, useGlobalLLMConfigs, useLLMConfigs } from "@/hooks/use-llm-configs";
import { cn } from "@/lib/utils";

import InferenceParamsEditor from "../inference-params-editor";

interface AddProviderStepProps {
	searchSpaceId: number;
	onConfigCreated?: () => void;
	onConfigDeleted?: () => void;
}

export function AddProviderStep({
	searchSpaceId,
	onConfigCreated,
	onConfigDeleted,
}: AddProviderStepProps) {
	const t = useTranslations("onboard");
	const { llmConfigs, createLLMConfig, deleteLLMConfig } = useLLMConfigs(searchSpaceId);
	const { globalConfigs } = useGlobalLLMConfigs();
	const [isAddingNew, setIsAddingNew] = useState(false);
	const [formData, setFormData] = useState<CreateLLMConfig>({
		name: "",
		provider: "",
		custom_provider: "",
		model_name: "",
		api_key: "",
		api_base: "",
		language: "English",
		litellm_params: {},
		search_space_id: searchSpaceId,
	});
	const [isSubmitting, setIsSubmitting] = useState(false);
	const [modelComboboxOpen, setModelComboboxOpen] = useState(false);

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
		const result = await createLLMConfig(formData);
		setIsSubmitting(false);

		if (result) {
			setFormData({
				name: "",
				provider: "",
				custom_provider: "",
				model_name: "",
				api_key: "",
				api_base: "",
				language: "English",
				litellm_params: {},
				search_space_id: searchSpaceId,
			});
			setIsAddingNew(false);
			// Notify parent component that a config was created
			onConfigCreated?.();
		}
	};

	const selectedProvider = LLM_PROVIDERS.find((p) => p.value === formData.provider);
	const availableModels = formData.provider ? getModelsByProvider(formData.provider) : [];

	const handleParamsChange = (newParams: Record<string, number | string>) => {
		setFormData((prev) => ({ ...prev, litellm_params: newParams }));
	};

	// Reset model when provider changes
	const handleProviderChange = (value: string) => {
		handleInputChange("provider", value);
		setFormData((prev) => ({ ...prev, model_name: "" }));
	};

	return (
		<div className="space-y-6">
			{/* Info Alert */}
			<Alert>
				<AlertCircle className="h-4 w-4" />
				<AlertDescription>{t("add_provider_instruction")}</AlertDescription>
			</Alert>

			{/* Global Configs Notice */}
			{globalConfigs.length > 0 && (
				<Alert className="bg-blue-50 border-blue-200 dark:bg-blue-950 dark:border-blue-800">
					<CheckCircle className="h-4 w-4 text-blue-600" />
					<AlertDescription className="text-blue-800 dark:text-blue-200">
						<strong>{globalConfigs.length} global configuration(s) available!</strong>
						<br />
						You can skip adding your own LLM provider and use our pre-configured models in the next
						step. Or continue here to add your own custom configurations.
					</AlertDescription>
				</Alert>
			)}

			{/* Existing Configurations */}
			{llmConfigs.length > 0 && (
				<div className="space-y-4">
					<h3 className="text-lg font-semibold">{t("your_llm_configs")}</h3>
					<div className="grid gap-4">
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
												<div className="flex items-center gap-2 mb-2">
													<Bot className="w-4 h-4" />
													<h4 className="font-medium">{config.name}</h4>
													<Badge variant="secondary">{config.provider}</Badge>
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
					<CardContent className="flex flex-col items-center justify-center py-12">
						<Plus className="w-12 h-12 text-muted-foreground mb-4" />
						<h3 className="text-lg font-semibold mb-2">{t("add_provider_title")}</h3>
						<p className="text-muted-foreground text-center mb-4">{t("add_provider_subtitle")}</p>
						<Button onClick={() => setIsAddingNew(true)}>
							<Plus className="w-4 h-4 mr-2" />
							{t("add_provider_button")}
						</Button>
					</CardContent>
				</Card>
			) : (
				<Card>
					<CardHeader>
						<CardTitle>{t("add_new_llm_provider")}</CardTitle>
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

								{/* language */}
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
										value={formData.custom_provider}
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
									placeholder={t("api_key_placeholder")}
									value={formData.api_key}
									onChange={(e) => handleInputChange("api_key", e.target.value)}
									required
								/>
							</div>

							<div className="space-y-2">
								<Label htmlFor="api_base">{t("api_base_optional")}</Label>
								<Input
									id="api_base"
									placeholder={t("api_base_placeholder")}
									value={formData.api_base}
									onChange={(e) => handleInputChange("api_base", e.target.value)}
								/>
							</div>

							{/* Optional Inference Parameters */}
							<div className="pt-4">
								<InferenceParamsEditor
									params={formData.litellm_params || {}}
									setParams={handleParamsChange}
								/>
							</div>

							<div className="flex gap-2 pt-4">
								<Button type="submit" disabled={isSubmitting}>
									{isSubmitting ? t("adding") : t("add_provider")}
								</Button>
								<Button
									type="button"
									variant="outline"
									onClick={() => setIsAddingNew(false)}
									disabled={isSubmitting}
								>
									{t("cancel")}
								</Button>
							</div>
						</form>
					</CardContent>
				</Card>
			)}
		</div>
	);
}
