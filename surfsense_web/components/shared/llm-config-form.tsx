"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useAtomValue } from "jotai";
import {
	Bot,
	Check,
	ChevronDown,
	ChevronsUpDown,
	Key,
	MessageSquareQuote,
	Rocket,
	Sparkles,
} from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { defaultSystemInstructionsAtom } from "@/atoms/new-llm-config/new-llm-config-query.atoms";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import {
	Command,
	CommandEmpty,
	CommandGroup,
	CommandInput,
	CommandItem,
	CommandList,
} from "@/components/ui/command";
import {
	Form,
	FormControl,
	FormDescription,
	FormField,
	FormItem,
	FormLabel,
	FormMessage,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";
import { Separator } from "@/components/ui/separator";
import { Spinner } from "@/components/ui/spinner";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { getModelsByProvider } from "@/contracts/enums/llm-models";
import { LLM_PROVIDERS } from "@/contracts/enums/llm-providers";
import type { CreateNewLLMConfigRequest } from "@/contracts/types/new-llm-config.types";
import { cn } from "@/lib/utils";
import InferenceParamsEditor from "../inference-params-editor";

// Form schema with zod
const formSchema = z.object({
	name: z.string().min(1, "Name is required").max(100),
	description: z.string().max(500).optional().nullable(),
	provider: z.string().min(1, "Provider is required"),
	custom_provider: z.string().max(100).optional().nullable(),
	model_name: z.string().min(1, "Model name is required").max(100),
	api_key: z.string().min(1, "API key is required"),
	api_base: z.string().max(500).optional().nullable(),
	litellm_params: z.record(z.string(), z.any()).optional().nullable(),
	system_instructions: z.string().optional().default(""),
	use_default_system_instructions: z.boolean().default(true),
	citations_enabled: z.boolean().default(true),
	search_space_id: z.number(),
});

type FormValues = z.infer<typeof formSchema>;

export interface LLMConfigFormData extends CreateNewLLMConfigRequest {}

interface LLMConfigFormProps {
	initialData?: Partial<LLMConfigFormData>;
	searchSpaceId: number;
	onSubmit: (data: LLMConfigFormData) => Promise<void>;
	onCancel?: () => void;
	isSubmitting?: boolean;
	mode?: "create" | "edit";
	submitLabel?: string;
	showAdvanced?: boolean;
	compact?: boolean;
}

export function LLMConfigForm({
	initialData,
	searchSpaceId,
	onSubmit,
	onCancel,
	isSubmitting = false,
	mode = "create",
	submitLabel,
	showAdvanced = true,
	compact = false,
}: LLMConfigFormProps) {
	const { data: defaultInstructions, isSuccess: defaultInstructionsLoaded } = useAtomValue(
		defaultSystemInstructionsAtom
	);
	const [modelComboboxOpen, setModelComboboxOpen] = useState(false);
	const [advancedOpen, setAdvancedOpen] = useState(false);
	const [systemInstructionsOpen, setSystemInstructionsOpen] = useState(false);

	const form = useForm<FormValues>({
		resolver: zodResolver(formSchema),
		defaultValues: {
			name: initialData?.name ?? "",
			description: initialData?.description ?? "",
			provider: initialData?.provider ?? "",
			custom_provider: initialData?.custom_provider ?? "",
			model_name: initialData?.model_name ?? "",
			api_key: initialData?.api_key ?? "",
			api_base: initialData?.api_base ?? "",
			litellm_params: initialData?.litellm_params ?? {},
			system_instructions: initialData?.system_instructions ?? "",
			use_default_system_instructions: initialData?.use_default_system_instructions ?? true,
			citations_enabled: initialData?.citations_enabled ?? true,
			search_space_id: searchSpaceId,
		},
	});

	// Load default instructions when available (only for new configs)
	useEffect(() => {
		if (
			mode === "create" &&
			defaultInstructionsLoaded &&
			defaultInstructions?.default_system_instructions &&
			!form.getValues("system_instructions")
		) {
			form.setValue("system_instructions", defaultInstructions.default_system_instructions);
		}
	}, [defaultInstructionsLoaded, defaultInstructions, mode, form]);

	const watchProvider = form.watch("provider");
	const selectedProvider = LLM_PROVIDERS.find((p) => p.value === watchProvider);
	const availableModels = watchProvider ? getModelsByProvider(watchProvider) : [];

	const handleProviderChange = (value: string) => {
		form.setValue("provider", value);
		form.setValue("model_name", "");

		// Auto-fill API base for certain providers
		const provider = LLM_PROVIDERS.find((p) => p.value === value);
		if (provider?.apiBase) {
			form.setValue("api_base", provider.apiBase);
		}
	};

	const handleFormSubmit = async (values: FormValues) => {
		await onSubmit(values as LLMConfigFormData);
	};

	return (
		<Form {...form}>
			<form onSubmit={form.handleSubmit(handleFormSubmit)} className="space-y-6">
				{/* Model Configuration Section */}
				<div className="space-y-4">
					<div className="flex items-center gap-2 text-xs sm:text-sm font-medium text-muted-foreground">
						<Bot className="h-3.5 w-3.5 sm:h-4 sm:w-4" />
						Model Configuration
					</div>

					{/* Name & Description */}
					<div className="grid gap-4 sm:grid-cols-2">
						<FormField
							control={form.control}
							name="name"
							render={({ field }) => (
								<FormItem>
									<FormLabel className="flex items-center gap-2 text-xs sm:text-sm">
										<Sparkles className="h-3.5 w-3.5 text-violet-500" />
										Configuration Name
									</FormLabel>
									<FormControl>
										<Input
											placeholder="e.g., My GPT-4 Agent"
											className="transition-all focus-visible:ring-violet-500/50"
											{...field}
										/>
									</FormControl>
									<FormMessage />
								</FormItem>
							)}
						/>

						<FormField
							control={form.control}
							name="description"
							render={({ field }) => (
								<FormItem>
									<FormLabel className="text-muted-foreground text-xs sm:text-sm">
										Description
										<Badge variant="outline" className="ml-2 text-[10px]">
											Optional
										</Badge>
									</FormLabel>
									<FormControl>
										<Input placeholder="Brief description" {...field} value={field.value ?? ""} />
									</FormControl>
									<FormMessage />
								</FormItem>
							)}
						/>
					</div>

					{/* Provider Selection */}
					<FormField
						control={form.control}
						name="provider"
						render={({ field }) => (
							<FormItem>
								<FormLabel className="text-xs sm:text-sm">LLM Provider</FormLabel>
								<Select value={field.value} onValueChange={handleProviderChange}>
									<FormControl>
										<SelectTrigger className="transition-all focus:ring-violet-500/50">
											<SelectValue placeholder="Select a provider" />
										</SelectTrigger>
									</FormControl>
									<SelectContent className="max-h-[300px]">
										{LLM_PROVIDERS.map((provider) => (
											<SelectItem key={provider.value} value={provider.value}>
												<div className="flex flex-col py-0.5">
													<span className="font-medium">{provider.label}</span>
													<span className="text-xs text-muted-foreground">
														{provider.description}
													</span>
												</div>
											</SelectItem>
										))}
									</SelectContent>
								</Select>
								<FormMessage />
							</FormItem>
						)}
					/>

					{/* Custom Provider (conditional) */}
					<AnimatePresence>
						{watchProvider === "CUSTOM" && (
							<motion.div
								initial={{ opacity: 0, height: 0 }}
								animate={{ opacity: 1, height: "auto" }}
								exit={{ opacity: 0, height: 0 }}
							>
								<FormField
									control={form.control}
									name="custom_provider"
									render={({ field }) => (
										<FormItem>
											<FormLabel className="text-xs sm:text-sm">Custom Provider Name</FormLabel>
											<FormControl>
												<Input
													placeholder="my-custom-provider"
													{...field}
													value={field.value ?? ""}
												/>
											</FormControl>
											<FormMessage />
										</FormItem>
									)}
								/>
							</motion.div>
						)}
					</AnimatePresence>

					{/* Model Name with Combobox */}
					<FormField
						control={form.control}
						name="model_name"
						render={({ field }) => (
							<FormItem className="flex flex-col">
								<FormLabel className="text-xs sm:text-sm">Model Name</FormLabel>
								<Popover open={modelComboboxOpen} onOpenChange={setModelComboboxOpen}>
									<PopoverTrigger asChild>
										<FormControl>
											<Button
												variant="outline"
												role="combobox"
												aria-expanded={modelComboboxOpen}
												className={cn(
													"w-full justify-between font-normal",
													!field.value && "text-muted-foreground"
												)}
											>
												{field.value || "Select or type model name"}
												<ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
											</Button>
										</FormControl>
									</PopoverTrigger>
									<PopoverContent className="w-full p-0" align="start">
										<Command shouldFilter={false}>
											<CommandInput
												placeholder={selectedProvider?.example || "Type model name..."}
												value={field.value}
												onValueChange={field.onChange}
											/>
											<CommandList>
												<CommandEmpty>
													<div className="py-3 text-center text-sm text-muted-foreground">
														{field.value ? `Using: "${field.value}"` : "Type your model name"}
													</div>
												</CommandEmpty>
												{availableModels.length > 0 && (
													<CommandGroup heading="Suggested Models">
														{availableModels
															.filter(
																(model) =>
																	!field.value ||
																	model.value.toLowerCase().includes(field.value.toLowerCase())
															)
															.slice(0, 8)
															.map((model) => (
																<CommandItem
																	key={model.value}
																	value={model.value}
																	onSelect={(value) => {
																		field.onChange(value);
																		setModelComboboxOpen(false);
																	}}
																	className="py-2"
																>
																	<Check
																		className={cn(
																			"mr-2 h-4 w-4",
																			field.value === model.value ? "opacity-100" : "opacity-0"
																		)}
																	/>
																	<div>
																		<div className="font-medium">{model.label}</div>
																		{model.contextWindow && (
																			<div className="text-xs text-muted-foreground">
																				Context: {model.contextWindow}
																			</div>
																		)}
																	</div>
																</CommandItem>
															))}
													</CommandGroup>
												)}
											</CommandList>
										</Command>
									</PopoverContent>
								</Popover>
								{selectedProvider?.example && (
									<FormDescription className="text-[10px] sm:text-xs">
										Example: {selectedProvider.example}
									</FormDescription>
								)}
								<FormMessage />
							</FormItem>
						)}
					/>

					{/* API Credentials */}
					<div className="grid gap-4 sm:grid-cols-2">
						<FormField
							control={form.control}
							name="api_key"
							render={({ field }) => (
								<FormItem>
									<FormLabel className="flex items-center gap-2 text-xs sm:text-sm">
										<Key className="h-3.5 w-3.5 text-amber-500" />
										API Key
									</FormLabel>
									<FormControl>
										<Input
											type="password"
											placeholder={watchProvider === "OLLAMA" ? "Any value" : "sk-..."}
											{...field}
										/>
									</FormControl>
									{watchProvider === "OLLAMA" && (
										<FormDescription className="text-[10px] sm:text-xs">
											Ollama doesn't require auth — enter any value
										</FormDescription>
									)}
									<FormMessage />
								</FormItem>
							)}
						/>

						<FormField
							control={form.control}
							name="api_base"
							render={({ field }) => (
								<FormItem>
									<FormLabel className="flex items-center gap-2 text-xs sm:text-sm">
										API Base URL
										{selectedProvider?.apiBase && (
											<Badge variant="secondary" className="text-[10px]">
												Auto-filled
											</Badge>
										)}
									</FormLabel>
									<FormControl>
										<Input
											placeholder={selectedProvider?.apiBase || "https://api.example.com/v1"}
											{...field}
											value={field.value ?? ""}
										/>
									</FormControl>
									<FormMessage />
								</FormItem>
							)}
						/>
					</div>

					{/* Ollama Quick Actions */}
					<AnimatePresence>
						{watchProvider === "OLLAMA" && (
							<motion.div
								initial={{ opacity: 0, height: 0 }}
								animate={{ opacity: 1, height: "auto" }}
								exit={{ opacity: 0, height: 0 }}
								className="flex flex-wrap gap-2"
							>
								<Button
									type="button"
									variant="outline"
									size="sm"
									className="h-7 text-xs"
									onClick={() => form.setValue("api_base", "http://localhost:11434")}
								>
									localhost:11434
								</Button>
								<Button
									type="button"
									variant="outline"
									size="sm"
									className="h-7 text-xs"
									onClick={() => form.setValue("api_base", "http://host.docker.internal:11434")}
								>
									Docker
								</Button>
							</motion.div>
						)}
					</AnimatePresence>
				</div>

				{/* Advanced Parameters */}
				{showAdvanced && (
					<>
						<Separator />
						<Collapsible open={advancedOpen} onOpenChange={setAdvancedOpen}>
							<CollapsibleTrigger asChild>
								<button
									type="button"
									className="flex w-full items-center justify-between py-2 text-xs sm:text-sm font-medium text-muted-foreground hover:text-foreground transition-colors"
								>
									<div className="flex items-center gap-2">
										<Sparkles className="h-3.5 w-3.5 sm:h-4 sm:w-4" />
										Advanced Parameters
									</div>
									<ChevronDown
										className={cn(
											"h-4 w-4 transition-transform duration-200",
											advancedOpen && "rotate-180"
										)}
									/>
								</button>
							</CollapsibleTrigger>
							<CollapsibleContent className="space-y-4 pt-2">
								<FormField
									control={form.control}
									name="litellm_params"
									render={({ field }) => (
										<FormItem>
											<FormControl>
												<InferenceParamsEditor
													params={field.value || {}}
													setParams={field.onChange}
												/>
											</FormControl>
											<FormMessage />
										</FormItem>
									)}
								/>
							</CollapsibleContent>
						</Collapsible>
					</>
				)}

				{/* System Instructions & Citations Section */}
				<Separator />
				<Collapsible open={systemInstructionsOpen} onOpenChange={setSystemInstructionsOpen}>
					<CollapsibleTrigger asChild>
						<button
							type="button"
							className="flex w-full items-center justify-between py-2 text-xs sm:text-sm font-medium text-muted-foreground hover:text-foreground transition-colors"
						>
							<div className="flex items-center gap-2">
								<MessageSquareQuote className="h-3.5 w-3.5 sm:h-4 sm:w-4" />
								System Instructions
							</div>
							<ChevronDown
								className={cn(
									"h-4 w-4 transition-transform duration-200",
									systemInstructionsOpen && "rotate-180"
								)}
							/>
						</button>
					</CollapsibleTrigger>
					<CollapsibleContent className="space-y-4 pt-2">
						{/* System Instructions */}
						<FormField
							control={form.control}
							name="system_instructions"
							render={({ field }) => (
								<FormItem>
									<div className="flex items-center justify-between">
										<FormLabel className="text-xs sm:text-sm">Instructions for the AI</FormLabel>
										{defaultInstructions && (
											<Button
												type="button"
												variant="ghost"
												size="sm"
												onClick={() =>
													field.onChange(defaultInstructions.default_system_instructions)
												}
												className="h-7 text-[10px] sm:text-xs text-muted-foreground hover:text-foreground"
											>
												Reset to Default
											</Button>
										)}
									</div>
									<FormControl>
										<Textarea
											placeholder="Enter system instructions for the AI..."
											rows={6}
											className="font-mono text-[11px] sm:text-xs resize-none"
											{...field}
										/>
									</FormControl>
									<FormDescription className="text-[10px] sm:text-xs">
										Use {"{resolved_today}"} to include today's date dynamically
									</FormDescription>
									<FormMessage />
								</FormItem>
							)}
						/>

						{/* Citations Toggle */}
						<FormField
							control={form.control}
							name="citations_enabled"
							render={({ field }) => (
								<FormItem className="flex items-center justify-between rounded-lg border p-3 bg-muted/30">
									<div className="space-y-0.5">
										<FormLabel className="text-xs sm:text-sm font-medium">
											Enable Citations
										</FormLabel>
										<FormDescription className="text-[10px] sm:text-xs">
											Include [citation:id] references to source documents
										</FormDescription>
									</div>
									<FormControl>
										<Switch checked={field.value} onCheckedChange={field.onChange} />
									</FormControl>
								</FormItem>
							)}
						/>
					</CollapsibleContent>
				</Collapsible>

				{/* Action Buttons */}
				<div
					className={cn(
						"flex gap-3 pt-4",
						compact ? "justify-end" : "justify-center sm:justify-end"
					)}
				>
					{onCancel && (
						<Button
							type="button"
							variant="outline"
							onClick={onCancel}
							disabled={isSubmitting}
							className="text-xs sm:text-sm h-9 sm:h-10"
						>
							Cancel
						</Button>
					)}
					<Button
						type="submit"
						disabled={isSubmitting}
						className="gap-2 min-w-[140px] sm:min-w-[160px] text-xs sm:text-sm h-9 sm:h-10"
					>
						{isSubmitting ? (
							<>
								<Spinner size="sm" />
								{mode === "edit" ? "Updating..." : "Creating"}
							</>
						) : (
							<>
								{!compact && <Rocket className="h-3.5 w-3.5 sm:h-4 sm:w-4" />}
								{submitLabel ?? (mode === "edit" ? "Update Configuration" : "Create Configuration")}
							</>
						)}
					</Button>
				</div>
			</form>
		</Form>
	);
}
