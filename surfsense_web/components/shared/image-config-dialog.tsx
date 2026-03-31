"use client";

import { useAtomValue } from "jotai";
import { AlertCircle, Check, ChevronsUpDown } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";
import {
	createImageGenConfigMutationAtom,
	updateImageGenConfigMutationAtom,
} from "@/atoms/image-gen-config/image-gen-config-mutation.atoms";
import { updateLLMPreferencesMutationAtom } from "@/atoms/new-llm-config/new-llm-config-mutation.atoms";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
	Command,
	CommandEmpty,
	CommandGroup,
	CommandInput,
	CommandItem,
	CommandList,
} from "@/components/ui/command";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
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
import { Spinner } from "@/components/ui/spinner";
import { IMAGE_GEN_MODELS, IMAGE_GEN_PROVIDERS } from "@/contracts/enums/image-gen-providers";
import type {
	GlobalImageGenConfig,
	ImageGenerationConfig,
	ImageGenProvider,
} from "@/contracts/types/new-llm-config.types";
import { cn } from "@/lib/utils";

interface ImageConfigDialogProps {
	open: boolean;
	onOpenChange: (open: boolean) => void;
	config: ImageGenerationConfig | GlobalImageGenConfig | null;
	isGlobal: boolean;
	searchSpaceId: number;
	mode: "create" | "edit" | "view";
}

const INITIAL_FORM = {
	name: "",
	description: "",
	provider: "",
	model_name: "",
	api_key: "",
	api_base: "",
	api_version: "",
};

export function ImageConfigDialog({
	open,
	onOpenChange,
	config,
	isGlobal,
	searchSpaceId,
	mode,
}: ImageConfigDialogProps) {
	const [isSubmitting, setIsSubmitting] = useState(false);
	const [formData, setFormData] = useState(INITIAL_FORM);
	const [modelComboboxOpen, setModelComboboxOpen] = useState(false);
	const [scrollPos, setScrollPos] = useState<"top" | "middle" | "bottom">("top");
	const scrollRef = useRef<HTMLDivElement>(null);

	useEffect(() => {
		if (open) {
			if (mode === "edit" && config && !isGlobal) {
				setFormData({
					name: config.name || "",
					description: config.description || "",
					provider: config.provider || "",
					model_name: config.model_name || "",
					api_key: (config as ImageGenerationConfig).api_key || "",
					api_base: config.api_base || "",
					api_version: config.api_version || "",
				});
			} else if (mode === "create") {
				setFormData(INITIAL_FORM);
			}
			setScrollPos("top");
		}
	}, [open, mode, config, isGlobal]);

	const { mutateAsync: createConfig } = useAtomValue(createImageGenConfigMutationAtom);
	const { mutateAsync: updateConfig } = useAtomValue(updateImageGenConfigMutationAtom);
	const { mutateAsync: updatePreferences } = useAtomValue(updateLLMPreferencesMutationAtom);

	const handleScroll = useCallback((e: React.UIEvent<HTMLDivElement>) => {
		const el = e.currentTarget;
		const atTop = el.scrollTop <= 2;
		const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight <= 2;
		setScrollPos(atTop ? "top" : atBottom ? "bottom" : "middle");
	}, []);

	const suggestedModels = useMemo(() => {
		if (!formData.provider) return [];
		return IMAGE_GEN_MODELS.filter((m) => m.provider === formData.provider);
	}, [formData.provider]);

	const getTitle = () => {
		if (mode === "create") return "Add Image Model";
		if (isGlobal) return "View Global Image Model";
		return "Edit Image Model";
	};

	const getSubtitle = () => {
		if (mode === "create") return "Set up a new image generation provider";
		if (isGlobal) return "Read-only global configuration";
		return "Update your image model settings";
	};

	const handleSubmit = useCallback(async () => {
		setIsSubmitting(true);
		try {
			if (mode === "create") {
				const result = await createConfig({
					name: formData.name,
					provider: formData.provider as ImageGenProvider,
					model_name: formData.model_name,
					api_key: formData.api_key,
					api_base: formData.api_base || undefined,
					api_version: formData.api_version || undefined,
					description: formData.description || undefined,
					search_space_id: searchSpaceId,
				});
				if (result?.id) {
					await updatePreferences({
						search_space_id: searchSpaceId,
						data: { image_generation_config_id: result.id },
					});
				}
				onOpenChange(false);
			} else if (!isGlobal && config) {
				await updateConfig({
					id: config.id,
					data: {
						name: formData.name,
						description: formData.description || undefined,
						provider: formData.provider as ImageGenProvider,
						model_name: formData.model_name,
						api_key: formData.api_key,
						api_base: formData.api_base || undefined,
						api_version: formData.api_version || undefined,
					},
				});
				onOpenChange(false);
			}
		} catch (error) {
			console.error("Failed to save image config:", error);
			toast.error("Failed to save image model");
		} finally {
			setIsSubmitting(false);
		}
	}, [
		mode,
		isGlobal,
		config,
		formData,
		searchSpaceId,
		createConfig,
		updateConfig,
		updatePreferences,
		onOpenChange,
	]);

	const handleUseGlobalConfig = useCallback(async () => {
		if (!config || !isGlobal) return;
		setIsSubmitting(true);
		try {
			await updatePreferences({
				search_space_id: searchSpaceId,
				data: { image_generation_config_id: config.id },
			});
			toast.success(`Now using ${config.name}`);
			onOpenChange(false);
		} catch (error) {
			console.error("Failed to set image model:", error);
			toast.error("Failed to set image model");
		} finally {
			setIsSubmitting(false);
		}
	}, [config, isGlobal, searchSpaceId, updatePreferences, onOpenChange]);

	const isFormValid = formData.name && formData.provider && formData.model_name && formData.api_key;
	const selectedProvider = IMAGE_GEN_PROVIDERS.find((p) => p.value === formData.provider);

	return (
		<Dialog open={open} onOpenChange={onOpenChange}>
			<DialogContent
				className="max-w-lg h-[85vh] flex flex-col p-0 gap-0 overflow-hidden"
				onOpenAutoFocus={(e) => e.preventDefault()}
			>
				<DialogTitle className="sr-only">{getTitle()}</DialogTitle>

				{/* Header */}
				<div className="flex items-start justify-between px-6 pt-6 pb-4 pr-14">
					<div className="space-y-1">
						<div className="flex items-center gap-2">
							<h2 className="text-lg font-semibold tracking-tight">{getTitle()}</h2>
							{isGlobal && mode !== "create" && (
								<Badge variant="secondary" className="text-[10px]">
									Global
								</Badge>
							)}
						</div>
						<p className="text-sm text-muted-foreground">{getSubtitle()}</p>
						{config && mode !== "create" && (
							<p className="text-xs font-mono text-muted-foreground/70">{config.model_name}</p>
						)}
					</div>
				</div>

				{/* Scrollable content */}
				<div
					ref={scrollRef}
					onScroll={handleScroll}
					className="flex-1 overflow-y-auto px-6 py-5"
					style={{
						maskImage: `linear-gradient(to bottom, ${scrollPos === "top" ? "black" : "transparent"}, black 16px, black calc(100% - 16px), ${scrollPos === "bottom" ? "black" : "transparent"})`,
						WebkitMaskImage: `linear-gradient(to bottom, ${scrollPos === "top" ? "black" : "transparent"}, black 16px, black calc(100% - 16px), ${scrollPos === "bottom" ? "black" : "transparent"})`,
					}}
				>
					{isGlobal && config && (
						<>
							<Alert className="mb-5 border-amber-500/30 bg-amber-500/5">
								<AlertCircle className="size-4 text-amber-500" />
								<AlertDescription className="text-sm text-amber-700 dark:text-amber-400">
									Global configurations are read-only. To customize, create a new model.
								</AlertDescription>
							</Alert>
							<div className="space-y-4">
								<div className="grid gap-4 sm:grid-cols-2">
									<div className="space-y-1.5">
										<div className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
											Name
										</div>
										<p className="text-sm font-medium">{config.name}</p>
									</div>
									{config.description && (
										<div className="space-y-1.5">
											<div className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
												Description
											</div>
											<p className="text-sm text-muted-foreground">{config.description}</p>
										</div>
									)}
								</div>
								<Separator />
								<div className="grid gap-4 sm:grid-cols-2">
									<div className="space-y-1.5">
										<div className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
											Provider
										</div>
										<p className="text-sm font-medium">{config.provider}</p>
									</div>
									<div className="space-y-1.5">
										<div className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
											Model
										</div>
										<p className="text-sm font-medium font-mono">{config.model_name}</p>
									</div>
								</div>
							</div>
						</>
					)}

					{(mode === "create" || (mode === "edit" && !isGlobal)) && (
						<div className="space-y-4">
							<div className="space-y-2">
								<Label className="text-sm font-medium">Name *</Label>
								<Input
									placeholder="e.g., My DALL-E 3"
									value={formData.name}
									onChange={(e) => setFormData((p) => ({ ...p, name: e.target.value }))}
								/>
							</div>

							<div className="space-y-2">
								<Label className="text-sm font-medium">Description</Label>
								<Input
									placeholder="Optional description"
									value={formData.description}
									onChange={(e) => setFormData((p) => ({ ...p, description: e.target.value }))}
								/>
							</div>

							<Separator />

							<div className="space-y-2">
								<Label className="text-sm font-medium">Provider *</Label>
								<Select
									value={formData.provider}
									onValueChange={(val) =>
										setFormData((p) => ({ ...p, provider: val, model_name: "" }))
									}
								>
									<SelectTrigger>
										<SelectValue placeholder="Select a provider" />
									</SelectTrigger>
									<SelectContent>
										{IMAGE_GEN_PROVIDERS.map((p) => (
											<SelectItem key={p.value} value={p.value} description={p.example}>
												{p.label}
											</SelectItem>
										))}
									</SelectContent>
								</Select>
							</div>

							<div className="space-y-2">
								<Label className="text-sm font-medium">Model Name *</Label>
								{suggestedModels.length > 0 ? (
									<Popover open={modelComboboxOpen} onOpenChange={setModelComboboxOpen}>
										<PopoverTrigger asChild>
											<Button
												variant="outline"
												role="combobox"
												className="w-full justify-between font-normal bg-transparent"
											>
												{formData.model_name || "Select or type a model..."}
												<ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
											</Button>
										</PopoverTrigger>
										<PopoverContent className="w-full p-0" align="start">
											<Command className="bg-transparent">
												<CommandInput
													placeholder="Search or type model..."
													value={formData.model_name}
													onValueChange={(val) => setFormData((p) => ({ ...p, model_name: val }))}
												/>
												<CommandList>
													<CommandEmpty>
														<span className="text-xs text-muted-foreground">
															Type a custom model name
														</span>
													</CommandEmpty>
													<CommandGroup>
														{suggestedModels.map((m) => (
															<CommandItem
																key={m.value}
																value={m.value}
																onSelect={() => {
																	setFormData((p) => ({ ...p, model_name: m.value }));
																	setModelComboboxOpen(false);
																}}
															>
																<Check
																	className={cn(
																		"mr-2 h-4 w-4",
																		formData.model_name === m.value ? "opacity-100" : "opacity-0"
																	)}
																/>
																<span className="font-mono text-sm">{m.value}</span>
																<span className="ml-2 text-xs text-muted-foreground">
																	{m.label}
																</span>
															</CommandItem>
														))}
													</CommandGroup>
												</CommandList>
											</Command>
										</PopoverContent>
									</Popover>
								) : (
									<Input
										placeholder="e.g., dall-e-3"
										value={formData.model_name}
										onChange={(e) => setFormData((p) => ({ ...p, model_name: e.target.value }))}
									/>
								)}
							</div>

							<div className="space-y-2">
								<Label className="text-sm font-medium">API Key *</Label>
								<Input
									type="password"
									placeholder="sk-..."
									value={formData.api_key}
									onChange={(e) => setFormData((p) => ({ ...p, api_key: e.target.value }))}
								/>
							</div>

							<div className="space-y-2">
								<Label className="text-sm font-medium">API Base URL</Label>
								<Input
									placeholder={selectedProvider?.apiBase || "Optional"}
									value={formData.api_base}
									onChange={(e) => setFormData((p) => ({ ...p, api_base: e.target.value }))}
								/>
							</div>

							{formData.provider === "AZURE_OPENAI" && (
								<div className="space-y-2">
									<Label className="text-sm font-medium">API Version (Azure)</Label>
									<Input
										placeholder="2024-02-15-preview"
										value={formData.api_version}
										onChange={(e) => setFormData((p) => ({ ...p, api_version: e.target.value }))}
									/>
								</div>
							)}
						</div>
					)}
				</div>

				{/* Fixed footer */}
				<div className="shrink-0 px-6 py-4 flex items-center justify-end gap-3">
					<Button
						type="button"
						variant="secondary"
						onClick={() => onOpenChange(false)}
						disabled={isSubmitting}
						className="text-sm h-9"
					>
						Cancel
					</Button>
					{mode === "create" || (mode === "edit" && !isGlobal) ? (
						<Button
							onClick={handleSubmit}
							disabled={isSubmitting || !isFormValid}
							className="relative text-sm h-9 min-w-[120px]"
						>
							<span className={isSubmitting ? "opacity-0" : ""}>
								{mode === "edit" ? "Save Changes" : "Create & Use"}
							</span>
							{isSubmitting && <Spinner size="sm" className="absolute" />}
						</Button>
					) : isGlobal && config ? (
						<Button
							className="relative text-sm h-9"
							onClick={handleUseGlobalConfig}
							disabled={isSubmitting}
						>
							<span className={isSubmitting ? "opacity-0" : ""}>Use This Model</span>
							{isSubmitting && <Spinner size="sm" className="absolute" />}
						</Button>
					) : null}
				</div>
			</DialogContent>
		</Dialog>
	);
}
