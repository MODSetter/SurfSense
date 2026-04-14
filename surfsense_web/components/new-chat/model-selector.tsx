"use client";

import type React from "react";
import { useAtomValue } from "jotai";
import {
	Bot,
	Check,
	ChevronDown,
	ChevronLeft,
	ChevronRight,
	ChevronUp,
	Edit3,
	ImageIcon,
	ScanEye,
	Layers,
	Plus,
	Search,
	Zap,
} from "lucide-react";
import { Fragment, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";
import {
	globalImageGenConfigsAtom,
	imageGenConfigsAtom,
} from "@/atoms/image-gen-config/image-gen-config-query.atoms";
import { updateLLMPreferencesMutationAtom } from "@/atoms/new-llm-config/new-llm-config-mutation.atoms";
import {
	globalNewLLMConfigsAtom,
	llmPreferencesAtom,
	newLLMConfigsAtom,
} from "@/atoms/new-llm-config/new-llm-config-query.atoms";
import { activeSearchSpaceIdAtom } from "@/atoms/search-spaces/search-space-query.atoms";
import {
	globalVisionLLMConfigsAtom,
	visionLLMConfigsAtom,
} from "@/atoms/vision-llm-config/vision-llm-config-query.atoms";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
	Drawer,
	DrawerContent,
	DrawerHandle,
	DrawerHeader,
	DrawerTitle,
	DrawerTrigger,
} from "@/components/ui/drawer";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Spinner } from "@/components/ui/spinner";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import type {
	GlobalImageGenConfig,
	GlobalNewLLMConfig,
	GlobalVisionLLMConfig,
	ImageGenerationConfig,
	NewLLMConfigPublic,
	VisionLLMConfig,
} from "@/contracts/types/new-llm-config.types";
import { useIsMobile } from "@/hooks/use-mobile";
import { getProviderIcon } from "@/lib/provider-icons";
import { cn } from "@/lib/utils";

// ─── Helpers ────────────────────────────────────────────────────────

const PROVIDER_NAMES: Record<string, string> = {
	OPENAI: "OpenAI",
	ANTHROPIC: "Anthropic",
	GOOGLE: "Google",
	AZURE: "Azure",
	AZURE_OPENAI: "Azure OpenAI",
	AWS_BEDROCK: "AWS Bedrock",
	BEDROCK: "Bedrock",
	DEEPSEEK: "DeepSeek",
	MISTRAL: "Mistral",
	COHERE: "Cohere",
	GITHUB_MODELS: "GitHub Models",
	GROQ: "Groq",
	OLLAMA: "Ollama",
	TOGETHER_AI: "Together AI",
	FIREWORKS_AI: "Fireworks AI",
	REPLICATE: "Replicate",
	HUGGINGFACE: "HuggingFace",
	PERPLEXITY: "Perplexity",
	XAI: "xAI",
	OPENROUTER: "OpenRouter",
	CEREBRAS: "Cerebras",
	SAMBANOVA: "SambaNova",
	VERTEX_AI: "Vertex AI",
	MINIMAX: "MiniMax",
	MOONSHOT: "Moonshot",
	ZHIPU: "Zhipu",
	DEEPINFRA: "DeepInfra",
	CLOUDFLARE: "Cloudflare",
	DATABRICKS: "Databricks",
	NSCALE: "NScale",
	RECRAFT: "Recraft",
	XINFERENCE: "XInference",
	CUSTOM: "Custom",
	AI21: "AI21",
	ALIBABA_QWEN: "Qwen",
	ANYSCALE: "Anyscale",
	COMETAPI: "CometAPI",
};

// Provider keys valid per model type, matching backend enums
// (LiteLLMProvider, ImageGenProvider, VisionProvider in db.py)
const LLM_PROVIDER_KEYS: string[] = [
	"OPENAI",
	"ANTHROPIC",
	"GOOGLE",
	"AZURE_OPENAI",
	"BEDROCK",
	"VERTEX_AI",
	"GROQ",
	"DEEPSEEK",
	"XAI",
	"MISTRAL",
	"COHERE",
	"OPENROUTER",
	"TOGETHER_AI",
	"FIREWORKS_AI",
	"REPLICATE",
	"PERPLEXITY",
	"OLLAMA",
	"CEREBRAS",
	"SAMBANOVA",
	"DEEPINFRA",
	"AI21",
	"ALIBABA_QWEN",
	"MOONSHOT",
	"ZHIPU",
	"MINIMAX",
	"HUGGINGFACE",
	"CLOUDFLARE",
	"DATABRICKS",
	"ANYSCALE",
	"COMETAPI",
	"GITHUB_MODELS",
	"CUSTOM",
];

const IMAGE_PROVIDER_KEYS: string[] = [
	"OPENAI",
	"AZURE_OPENAI",
	"GOOGLE",
	"VERTEX_AI",
	"BEDROCK",
	"RECRAFT",
	"OPENROUTER",
	"XINFERENCE",
	"NSCALE",
];

const VISION_PROVIDER_KEYS: string[] = [
	"OPENAI",
	"ANTHROPIC",
	"GOOGLE",
	"AZURE_OPENAI",
	"VERTEX_AI",
	"BEDROCK",
	"XAI",
	"OPENROUTER",
	"OLLAMA",
	"GROQ",
	"TOGETHER_AI",
	"FIREWORKS_AI",
	"DEEPSEEK",
	"MISTRAL",
	"CUSTOM",
];

const PROVIDER_KEYS_BY_TAB: Record<string, string[]> = {
	llm: LLM_PROVIDER_KEYS,
	image: IMAGE_PROVIDER_KEYS,
	vision: VISION_PROVIDER_KEYS,
};

function formatProviderName(provider: string): string {
	const key = provider.toUpperCase();
	return (
		PROVIDER_NAMES[key] ??
		provider.charAt(0).toUpperCase() +
			provider.slice(1).toLowerCase().replace(/_/g, " ")
	);
}

function normalizeText(input: string): string {
	return input
		.normalize("NFD")
		.replace(/\p{Diacritic}/gu, "")
		.toLowerCase()
		.replace(/[^a-z0-9]+/g, " ")
		.trim();
}

interface ConfigBase {
	id: number;
	name: string;
	model_name: string;
	provider: string;
}

function filterAndScore<T extends ConfigBase>(
	configs: T[],
	selectedProvider: string,
	searchQuery: string,
): T[] {
	let result = configs;

	if (selectedProvider !== "all") {
		result = result.filter(
			(c) => c.provider.toUpperCase() === selectedProvider,
		);
	}

	if (!searchQuery.trim()) return result;

	const normalized = normalizeText(searchQuery);
	const tokens = normalized.split(/\s+/).filter(Boolean);

	const scored = result.map((c) => {
		const aggregate = normalizeText(
			[c.name, c.model_name, c.provider].join(" "),
		);
		let score = 0;
		if (aggregate.includes(normalized)) score += 5;
		for (const token of tokens) {
			if (aggregate.includes(token)) score += 1;
		}
		return { config: c, score };
	});

	return scored
		.filter((s) => s.score > 0)
		.sort((a, b) => b.score - a.score)
		.map((s) => s.config);
}

interface DisplayItem {
	config: ConfigBase & Record<string, unknown>;
	isGlobal: boolean;
	isAutoMode: boolean;
}

// ─── Component ──────────────────────────────────────────────────────

interface ModelSelectorProps {
	onEditLLM: (
		config: NewLLMConfigPublic | GlobalNewLLMConfig,
		isGlobal: boolean,
	) => void;
	onAddNewLLM: (provider?: string) => void;
	onEditImage?: (
		config: ImageGenerationConfig | GlobalImageGenConfig,
		isGlobal: boolean,
	) => void;
	onAddNewImage?: (provider?: string) => void;
	onEditVision?: (
		config: VisionLLMConfig | GlobalVisionLLMConfig,
		isGlobal: boolean,
	) => void;
	onAddNewVision?: (provider?: string) => void;
	className?: string;
}

export function ModelSelector({
	onEditLLM,
	onAddNewLLM,
	onEditImage,
	onAddNewImage,
	onEditVision,
	onAddNewVision,
	className,
}: ModelSelectorProps) {
	const [open, setOpen] = useState(false);
	const [activeTab, setActiveTab] = useState<"llm" | "image" | "vision">(
		"llm",
	);
	const [searchQuery, setSearchQuery] = useState("");
	const [selectedProvider, setSelectedProvider] = useState<string>("all");
	const [focusedIndex, setFocusedIndex] = useState(-1);
	const [modelScrollPos, setModelScrollPos] = useState<"top" | "middle" | "bottom">("top");
	const [sidebarScrollPos, setSidebarScrollPos] = useState<"top" | "middle" | "bottom">("top");
	const providerSidebarRef = useRef<HTMLDivElement>(null);
	const modelListRef = useRef<HTMLDivElement>(null);
	const searchInputRef = useRef<HTMLInputElement>(null);
	const isMobile = useIsMobile();

	const handleModelListScroll = useCallback((e: React.UIEvent<HTMLDivElement>) => {
		const el = e.currentTarget;
		const atTop = el.scrollTop <= 2;
		const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight <= 2;
		setModelScrollPos(atTop ? "top" : atBottom ? "bottom" : "middle");
	}, []);

	const handleSidebarScroll = useCallback((e: React.UIEvent<HTMLDivElement>) => {
		const el = e.currentTarget;
		if (isMobile) {
			const atStart = el.scrollLeft <= 2;
			const atEnd = el.scrollWidth - el.scrollLeft - el.clientWidth <= 2;
			setSidebarScrollPos(atStart ? "top" : atEnd ? "bottom" : "middle");
		} else {
			const atTop = el.scrollTop <= 2;
			const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight <= 2;
			setSidebarScrollPos(atTop ? "top" : atBottom ? "bottom" : "middle");
		}
	}, [isMobile]);

	// Reset search + provider when tab changes
	// biome-ignore lint/correctness/useExhaustiveDependencies: activeTab is intentionally used as a trigger
	useEffect(() => {
		setSelectedProvider("all");
		setSearchQuery("");
		setFocusedIndex(-1);
		setModelScrollPos("top");
	}, [activeTab]);

	// Reset on open
	useEffect(() => {
		if (open) {
			setSearchQuery("");
			setSelectedProvider("all");
		}
	}, [open]);

	// Cmd/Ctrl+M shortcut (desktop only)
	useEffect(() => {
		if (isMobile) return;
		const handler = (e: KeyboardEvent) => {
			if ((e.metaKey || e.ctrlKey) && e.key === "m") {
				e.preventDefault();
				setOpen((prev) => !prev);
			}
		};
		document.addEventListener("keydown", handler);
		return () => document.removeEventListener("keydown", handler);
	}, [isMobile]);

	// Focus search input on open
	// biome-ignore lint/correctness/useExhaustiveDependencies: activeTab is intentionally used as a trigger to re-focus on tab switch
	useEffect(() => {
		if (open && !isMobile) {
			requestAnimationFrame(() => searchInputRef.current?.focus());
		}
	}, [open, isMobile, activeTab]);

	// ─── Data ───
	const { data: llmUserConfigs, isLoading: llmUserLoading } =
		useAtomValue(newLLMConfigsAtom);
	const { data: llmGlobalConfigs, isLoading: llmGlobalLoading } =
		useAtomValue(globalNewLLMConfigsAtom);
	const { data: preferences, isLoading: prefsLoading } =
		useAtomValue(llmPreferencesAtom);
	const searchSpaceId = useAtomValue(activeSearchSpaceIdAtom);
	const { mutateAsync: updatePreferences } = useAtomValue(
		updateLLMPreferencesMutationAtom,
	);
	const { data: imageGlobalConfigs, isLoading: imageGlobalLoading } =
		useAtomValue(globalImageGenConfigsAtom);
	const { data: imageUserConfigs, isLoading: imageUserLoading } =
		useAtomValue(imageGenConfigsAtom);
	const { data: visionGlobalConfigs, isLoading: visionGlobalLoading } =
		useAtomValue(globalVisionLLMConfigsAtom);
	const { data: visionUserConfigs, isLoading: visionUserLoading } =
		useAtomValue(visionLLMConfigsAtom);

	const isLoading =
		llmUserLoading ||
		llmGlobalLoading ||
		prefsLoading ||
		imageGlobalLoading ||
		imageUserLoading ||
		visionGlobalLoading ||
		visionUserLoading;

	// ─── Current selected configs ───
	const currentLLMConfig = useMemo(() => {
		if (!preferences) return null;
		const id = preferences.agent_llm_id;
		if (id === null || id === undefined) return null;
		if (id <= 0) return llmGlobalConfigs?.find((c) => c.id === id) ?? null;
		return llmUserConfigs?.find((c) => c.id === id) ?? null;
	}, [preferences, llmGlobalConfigs, llmUserConfigs]);

	const isLLMAutoMode =
		currentLLMConfig &&
		"is_auto_mode" in currentLLMConfig &&
		currentLLMConfig.is_auto_mode;

	const currentImageConfig = useMemo(() => {
		if (!preferences) return null;
		const id = preferences.image_generation_config_id;
		if (id === null || id === undefined) return null;
		return (
			imageGlobalConfigs?.find((c) => c.id === id) ??
			imageUserConfigs?.find((c) => c.id === id) ??
			null
		);
	}, [preferences, imageGlobalConfigs, imageUserConfigs]);

	const isImageAutoMode =
		currentImageConfig &&
		"is_auto_mode" in currentImageConfig &&
		currentImageConfig.is_auto_mode;

	const currentVisionConfig = useMemo(() => {
		if (!preferences) return null;
		const id = preferences.vision_llm_config_id;
		if (id === null || id === undefined) return null;
		return (
			visionGlobalConfigs?.find((c) => c.id === id) ??
			visionUserConfigs?.find((c) => c.id === id) ??
			null
		);
	}, [preferences, visionGlobalConfigs, visionUserConfigs]);

	const isVisionAutoMode =
		currentVisionConfig &&
		"is_auto_mode" in currentVisionConfig &&
		currentVisionConfig.is_auto_mode;

	// ─── Filtered configs (separate global / user for section headers) ───
	const filteredLLMGlobal = useMemo(
		() =>
			filterAndScore(llmGlobalConfigs ?? [], selectedProvider, searchQuery),
		[llmGlobalConfigs, selectedProvider, searchQuery],
	);
	const filteredLLMUser = useMemo(
		() =>
			filterAndScore(llmUserConfigs ?? [], selectedProvider, searchQuery),
		[llmUserConfigs, selectedProvider, searchQuery],
	);
	const filteredImageGlobal = useMemo(
		() =>
			filterAndScore(
				imageGlobalConfigs ?? [],
				selectedProvider,
				searchQuery,
			),
		[imageGlobalConfigs, selectedProvider, searchQuery],
	);
	const filteredImageUser = useMemo(
		() =>
			filterAndScore(
				imageUserConfigs ?? [],
				selectedProvider,
				searchQuery,
			),
		[imageUserConfigs, selectedProvider, searchQuery],
	);
	const filteredVisionGlobal = useMemo(
		() =>
			filterAndScore(
				visionGlobalConfigs ?? [],
				selectedProvider,
				searchQuery,
			),
		[visionGlobalConfigs, selectedProvider, searchQuery],
	);
	const filteredVisionUser = useMemo(
		() =>
			filterAndScore(
				visionUserConfigs ?? [],
				selectedProvider,
				searchQuery,
			),
		[visionUserConfigs, selectedProvider, searchQuery],
	);

	// Combined display list for keyboard navigation
	const currentDisplayItems: DisplayItem[] = useMemo(() => {
		const toItems = (
			configs: ConfigBase[],
			isGlobal: boolean,
		): DisplayItem[] =>
			configs.map((c) => ({
				config: c as ConfigBase & Record<string, unknown>,
				isGlobal,
				isAutoMode:
					isGlobal &&
					"is_auto_mode" in c &&
					!!(c as Record<string, unknown>).is_auto_mode,
			}));

		switch (activeTab) {
			case "llm":
				return [
					...toItems(filteredLLMGlobal, true),
					...toItems(filteredLLMUser, false),
				];
			case "image":
				return [
					...toItems(filteredImageGlobal, true),
					...toItems(filteredImageUser, false),
				];
			case "vision":
				return [
					...toItems(filteredVisionGlobal, true),
					...toItems(filteredVisionUser, false),
				];
		}
	}, [
		activeTab,
		filteredLLMGlobal,
		filteredLLMUser,
		filteredImageGlobal,
		filteredImageUser,
		filteredVisionGlobal,
		filteredVisionUser,
	]);

	// ─── Provider sidebar data ───
	// Collect which providers actually have configured models for the active tab
	const configuredProviderSet = useMemo(() => {
		const configs =
			activeTab === "llm"
				? [
						...(llmGlobalConfigs ?? []),
						...(llmUserConfigs ?? []),
					]
				: activeTab === "image"
					? [
							...(imageGlobalConfigs ?? []),
							...(imageUserConfigs ?? []),
						]
					: [
							...(visionGlobalConfigs ?? []),
							...(visionUserConfigs ?? []),
						];
		const set = new Set<string>();
		for (const c of configs) {
			if (c.provider) set.add(c.provider.toUpperCase());
		}
		return set;
	}, [
		activeTab,
		llmGlobalConfigs,
		llmUserConfigs,
		imageGlobalConfigs,
		imageUserConfigs,
		visionGlobalConfigs,
		visionUserConfigs,
	]);

	// Show only providers valid for the active tab; configured ones first
	const activeProviders = useMemo(() => {
		const tabKeys = PROVIDER_KEYS_BY_TAB[activeTab] ?? LLM_PROVIDER_KEYS;
		const configured = tabKeys.filter((p) =>
			configuredProviderSet.has(p),
		);
		const unconfigured = tabKeys.filter(
			(p) => !configuredProviderSet.has(p),
		);
		return ["all", ...configured, ...unconfigured];
	}, [activeTab, configuredProviderSet]);

	const providerModelCounts = useMemo(() => {
		const allConfigs =
			activeTab === "llm"
				? [
						...(llmGlobalConfigs ?? []),
						...(llmUserConfigs ?? []),
					]
				: activeTab === "image"
					? [
							...(imageGlobalConfigs ?? []),
							...(imageUserConfigs ?? []),
						]
					: [
							...(visionGlobalConfigs ?? []),
							...(visionUserConfigs ?? []),
						];
		const counts: Record<string, number> = { all: allConfigs.length };
		for (const c of allConfigs) {
			const p = c.provider.toUpperCase();
			counts[p] = (counts[p] || 0) + 1;
		}
		return counts;
	}, [
		activeTab,
		llmGlobalConfigs,
		llmUserConfigs,
		imageGlobalConfigs,
		imageUserConfigs,
		visionGlobalConfigs,
		visionUserConfigs,
	]);

	// ─── Selection handlers ───
	const handleSelectLLM = useCallback(
		async (config: NewLLMConfigPublic | GlobalNewLLMConfig) => {
			if (currentLLMConfig?.id === config.id) {
				setOpen(false);
				return;
			}
			if (!searchSpaceId) {
				toast.error("No search space selected");
				return;
			}
			try {
				await updatePreferences({
					search_space_id: Number(searchSpaceId),
					data: { agent_llm_id: config.id },
				});
				toast.success(`Switched to ${config.name}`);
				setOpen(false);
			} catch {
				toast.error("Failed to switch model");
			}
		},
		[currentLLMConfig, searchSpaceId, updatePreferences],
	);

	const handleSelectImage = useCallback(
		async (configId: number) => {
			if (currentImageConfig?.id === configId) {
				setOpen(false);
				return;
			}
			if (!searchSpaceId) {
				toast.error("No search space selected");
				return;
			}
			try {
				await updatePreferences({
					search_space_id: Number(searchSpaceId),
					data: { image_generation_config_id: configId },
				});
				toast.success("Image model updated");
				setOpen(false);
			} catch {
				toast.error("Failed to switch image model");
			}
		},
		[currentImageConfig, searchSpaceId, updatePreferences],
	);

	const handleSelectVision = useCallback(
		async (configId: number) => {
			if (currentVisionConfig?.id === configId) {
				setOpen(false);
				return;
			}
			if (!searchSpaceId) {
				toast.error("No search space selected");
				return;
			}
			try {
				await updatePreferences({
					search_space_id: Number(searchSpaceId),
					data: { vision_llm_config_id: configId },
				});
				toast.success("Vision model updated");
				setOpen(false);
			} catch {
				toast.error("Failed to switch vision model");
			}
		},
		[currentVisionConfig, searchSpaceId, updatePreferences],
	);

	const handleSelectItem = useCallback(
		(item: DisplayItem) => {
			switch (activeTab) {
				case "llm":
					handleSelectLLM(
						item.config as NewLLMConfigPublic | GlobalNewLLMConfig,
					);
					break;
				case "image":
					handleSelectImage(item.config.id);
					break;
				case "vision":
					handleSelectVision(item.config.id);
					break;
			}
		},
		[activeTab, handleSelectLLM, handleSelectImage, handleSelectVision],
	);

	const handleEditItem = useCallback(
		(e: React.MouseEvent, item: DisplayItem) => {
			e.stopPropagation();
			setOpen(false);
			switch (activeTab) {
				case "llm":
					onEditLLM(
						item.config as NewLLMConfigPublic | GlobalNewLLMConfig,
						item.isGlobal,
					);
					break;
				case "image":
					onEditImage?.(
						item.config as ImageGenerationConfig | GlobalImageGenConfig,
						item.isGlobal,
					);
					break;
				case "vision":
					onEditVision?.(
						item.config as VisionLLMConfig | GlobalVisionLLMConfig,
						item.isGlobal,
					);
					break;
			}
		},
		[activeTab, onEditLLM, onEditImage, onEditVision],
	);

	// ─── Keyboard navigation ───
	// biome-ignore lint/correctness/useExhaustiveDependencies: searchQuery and selectedProvider are intentional triggers to reset focus
	useEffect(() => {
		setFocusedIndex(-1);
	}, [searchQuery, selectedProvider]);

	useEffect(() => {
		if (focusedIndex < 0 || !modelListRef.current) return;
		const items =
			modelListRef.current.querySelectorAll("[data-model-index]");
		items[focusedIndex]?.scrollIntoView({
			block: "nearest",
			behavior: "smooth",
		});
	}, [focusedIndex]);

	const handleKeyDown = useCallback(
		(e: React.KeyboardEvent<HTMLInputElement>) => {
			const count = currentDisplayItems.length;

			// Arrow Left/Right cycle provider filters
			if (e.key === "ArrowLeft" || e.key === "ArrowRight") {
				e.preventDefault();
				const providers = activeProviders;
				const idx = providers.indexOf(selectedProvider);
				let next: number;
				if (e.key === "ArrowLeft") {
					next = idx > 0 ? idx - 1 : providers.length - 1;
				} else {
					next =
						idx < providers.length - 1 ? idx + 1 : 0;
				}
				setSelectedProvider(providers[next]);
				if (providerSidebarRef.current) {
					const buttons =
						providerSidebarRef.current.querySelectorAll("button");
					buttons[next]?.scrollIntoView({
						block: "nearest",
						inline: "nearest",
						behavior: "smooth",
					});
				}
				return;
			}

			if (count === 0) return;

			switch (e.key) {
				case "ArrowDown":
					e.preventDefault();
					setFocusedIndex((prev) =>
						prev < count - 1 ? prev + 1 : 0,
					);
					break;
				case "ArrowUp":
					e.preventDefault();
					setFocusedIndex((prev) =>
						prev > 0 ? prev - 1 : count - 1,
					);
					break;
				case "Enter":
					e.preventDefault();
					if (focusedIndex >= 0 && focusedIndex < count) {
						handleSelectItem(currentDisplayItems[focusedIndex]);
					}
					break;
				case "Home":
					e.preventDefault();
					setFocusedIndex(0);
					break;
				case "End":
					e.preventDefault();
					setFocusedIndex(count - 1);
					break;
			}
		},
		[
			currentDisplayItems,
			focusedIndex,
			activeProviders,
			selectedProvider,
			handleSelectItem,
		],
	);

	// ─── Render: Provider sidebar ───
	const renderProviderSidebar = () => {
		const configuredCount = configuredProviderSet.size;

		return (
			<div
				className={cn(
					"shrink-0 border-border/50 flex",
					isMobile ? "flex-row items-center border-b border-border/40" : "flex-col w-10 border-r",
				)}
			>
				{!isMobile && sidebarScrollPos !== "top" && (
					<div className="flex items-center justify-center py-0.5 pointer-events-none">
						<ChevronUp className="size-3 text-muted-foreground" />
					</div>
				)}
				{isMobile && sidebarScrollPos !== "top" && (
					<div className="flex items-center justify-center px-0.5 shrink-0 pointer-events-none">
						<ChevronLeft className="size-3 text-muted-foreground" />
					</div>
				)}
				<div
					ref={providerSidebarRef}
					onScroll={handleSidebarScroll}
					className={cn(
						isMobile
							? "flex flex-row gap-0.5 px-1 py-1.5 overflow-x-auto [&::-webkit-scrollbar]:h-0 [&::-webkit-scrollbar-track]:bg-transparent"
							: "flex flex-col gap-0.5 p-1 overflow-y-auto flex-1 [&::-webkit-scrollbar]:w-0 [&::-webkit-scrollbar-track]:bg-transparent",
					)}
					style={isMobile ? {
						maskImage: `linear-gradient(to right, ${sidebarScrollPos === "top" ? "black" : "transparent"}, black 24px, black calc(100% - 24px), ${sidebarScrollPos === "bottom" ? "black" : "transparent"})`,
						WebkitMaskImage: `linear-gradient(to right, ${sidebarScrollPos === "top" ? "black" : "transparent"}, black 24px, black calc(100% - 24px), ${sidebarScrollPos === "bottom" ? "black" : "transparent"})`,
					} : {
						maskImage: `linear-gradient(to bottom, ${sidebarScrollPos === "top" ? "black" : "transparent"}, black 32px, black calc(100% - 32px), ${sidebarScrollPos === "bottom" ? "black" : "transparent"})`,
						WebkitMaskImage: `linear-gradient(to bottom, ${sidebarScrollPos === "top" ? "black" : "transparent"}, black 32px, black calc(100% - 32px), ${sidebarScrollPos === "bottom" ? "black" : "transparent"})`,
					}}
				>
					{activeProviders.map((provider, idx) => {
						const isAll = provider === "all";
						const isActive = selectedProvider === provider;
						const count = providerModelCounts[provider] || 0;
						const isConfigured =
							isAll || configuredProviderSet.has(provider);

						// Separator between configured and unconfigured providers
						// idx 0 is "all", configured run from 1..configuredCount, unconfigured start at configuredCount+1
						const showSeparator =
							!isAll &&
							idx === configuredCount + 1 &&
							configuredCount > 0;

						return (
							<Fragment key={provider}>
								{showSeparator &&
									(isMobile ? (
										<div className="w-px h-5 bg-border/60 shrink-0 self-center mx-0.5" />
									) : (
										<div className="h-px w-5 bg-border/60 mx-auto my-0.5" />
									))}
								<Tooltip>
									<TooltipTrigger asChild>
										<button
											type="button"
											onClick={() =>
												setSelectedProvider(provider)
											}
											tabIndex={-1}
											className={cn(
												"relative flex items-center justify-center rounded-md transition-all duration-150",
												isMobile
													? "p-2 shrink-0"
													: "p-1.5 w-full",
												isActive
													? "bg-primary/10 text-primary"
													: isConfigured
														? "hover:bg-accent/60 text-muted-foreground hover:text-foreground"
														: "opacity-50 hover:opacity-80 hover:bg-accent/40 text-muted-foreground",
											)}
										>
											{isAll ? (
												<Layers className="size-4" />
											) : (
												getProviderIcon(provider, {
													className: "size-4",
												})
											)}
										</button>
									</TooltipTrigger>
									<TooltipContent
										side={
											isMobile ? "bottom" : "right"
										}
									>
										{isAll
											? "All Models"
											: formatProviderName(
													provider,
												)}
										{isConfigured
											? ` (${count})`
											: " (not configured)"}
									</TooltipContent>
								</Tooltip>
							</Fragment>
						);
					})}
				</div>
				{!isMobile && sidebarScrollPos !== "bottom" && (
					<div className="flex items-center justify-center py-0.5 pointer-events-none">
						<ChevronDown className="size-3 text-muted-foreground" />
					</div>
				)}
				{isMobile && sidebarScrollPos !== "bottom" && (
					<div className="flex items-center justify-center px-0.5 shrink-0 pointer-events-none">
						<ChevronRight className="size-3 text-muted-foreground" />
					</div>
				)}
			</div>
		);
	};

	// ─── Render: Model card ───
	const getSelectedId = () => {
		switch (activeTab) {
			case "llm":
				return currentLLMConfig?.id;
			case "image":
				return currentImageConfig?.id;
			case "vision":
				return currentVisionConfig?.id;
		}
	};

	const renderModelCard = (item: DisplayItem, index: number) => {
		const { config, isAutoMode } = item;
		const isSelected = getSelectedId() === config.id;
		const isFocused = focusedIndex === index;
		const hasCitations =
			"citations_enabled" in config && !!config.citations_enabled;

		return (
			<div
				key={`${activeTab}-${item.isGlobal ? "g" : "u"}-${config.id}`}
				data-model-index={index}
				role="option"
				tabIndex={isMobile ? -1 : 0}
				aria-selected={isSelected}
				onClick={() => handleSelectItem(item)}
				onKeyDown={isMobile ? undefined : (e) => {
					if (e.key === "Enter" || e.key === " ") {
						e.preventDefault();
						handleSelectItem(item);
					}
				}}
				onMouseEnter={() => setFocusedIndex(index)}
				className={cn(
					"group flex items-center gap-2.5 px-3 py-2 rounded-xl cursor-pointer",
					"transition-all duration-150 mx-2",
					"hover:bg-accent/40",
					isSelected && "bg-primary/6 dark:bg-primary/8",
					isFocused && "bg-accent/50",
				)}
			>
				{/* Provider icon */}
				<div className="shrink-0">
					{getProviderIcon(config.provider as string, {
						isAutoMode,
						className: "size-5",
					})}
				</div>

				{/* Model info */}
				<div className="flex-1 min-w-0">
					<div className="flex items-center gap-1.5">
						<span className="font-medium text-sm truncate">
							{config.name}
						</span>
						{isAutoMode && (
							<Badge
								variant="secondary"
								className="text-[9px] px-1 py-0 h-3.5 bg-violet-800 text-white dark:bg-violet-800 dark:text-white border-0"
							>
								Recommended
							</Badge>
						)}
					</div>
					<div className="flex items-center gap-1.5 mt-0.5">
						<span className="text-xs text-muted-foreground truncate">
							{isAutoMode
								? "Auto Mode"
								: (config.model_name as string)}
						</span>
						{!isAutoMode && hasCitations && (
							<Badge
								variant="secondary"
								className="text-[10px] px-1.5 py-0.5 border-0 text-muted-foreground bg-muted"
							>
								Citations
							</Badge>
						)}
					</div>
				</div>

				{/* Actions */}
				<div className="flex items-center gap-1 shrink-0">
					{!isAutoMode && (
						<Button
							variant="ghost"
							size="icon"
							className="size-7 rounded-md hover:bg-muted opacity-0 group-hover:opacity-100 transition-opacity"
							onClick={(e) => handleEditItem(e, item)}
						>
							<Edit3 className="size-3.5 text-muted-foreground" />
						</Button>
					)}
					{isSelected && (
						<Check className="size-4 text-primary shrink-0" />
					)}
				</div>
			</div>
		);
	};

	// ─── Render: Full content ───
	const renderContent = () => {
		const globalItems = currentDisplayItems.filter((i) => i.isGlobal);
		const userItems = currentDisplayItems.filter((i) => !i.isGlobal);
		const globalStartIdx = 0;
		const userStartIdx = globalItems.length;

		const addHandler =
			activeTab === "llm"
				? onAddNewLLM
				: activeTab === "image"
					? onAddNewImage
					: onAddNewVision;
		const addLabel =
			activeTab === "llm"
				? "Add Model"
				: activeTab === "image"
					? "Add Image Model"
					: "Add Vision Model";

		return (
			<div className="flex flex-col w-full overflow-hidden">
				{/* Tab header */}
				<div className="border-b border-border/80 dark:border-neutral-800">
					<div className="w-full grid grid-cols-3 h-11">
						{(
							[
								{
									value: "llm" as const,
									icon: Zap,
									label: "LLM",
								},
								{
									value: "image" as const,
									icon: ImageIcon,
									label: "Image",
								},
								{
									value: "vision" as const,
									icon: ScanEye,
									label: "Vision",
								},
							] as const
						).map(({ value, icon: Icon, label }) => (
							<button
								key={value}
								type="button"
								onClick={() => setActiveTab(value)}
								className={cn(
									"flex items-center justify-center gap-1.5 text-sm font-medium transition-all duration-200 border-b-[1.5px]",
									activeTab === value
										? "border-foreground dark:border-white text-foreground"
										: "border-transparent text-muted-foreground hover:text-foreground/70",
								)}
							>
								<Icon className="size-3.5" />
								{label}
							</button>
						))}
					</div>
				</div>

				{/* Two-pane layout */}
				<div
					className={cn(
						"flex",
						isMobile
							? "flex-col h-[60vh]"
							: "flex-row h-[380px]",
					)}
				>
					{/* Provider sidebar */}
					{renderProviderSidebar()}

					{/* Main content */}
					<div className="flex flex-col min-w-0 min-h-0 flex-1 overflow-hidden">
						{/* Search */}
						<div className="relative">
							<Search className="absolute left-3 top-1/2 -translate-y-1/2 size-3.5 text-muted-foreground/100 pointer-events-none" />
							<input
								ref={searchInputRef}
								placeholder="Search models"
								value={searchQuery}
								onChange={(e) =>
									setSearchQuery(e.target.value)
								}
								onKeyDown={isMobile ? undefined : handleKeyDown}
								role="combobox"
								aria-expanded={true}
								aria-controls="model-selector-list"
								className={cn(
									"w-full pl-8 pr-3 py-2.5 text-sm bg-transparent",
									"focus:outline-none",
									"placeholder:text-muted-foreground",
								)}
							/>
						</div>

						{/* Provider header when filtered */}
						{selectedProvider !== "all" && (
							<div className="flex items-center gap-2 px-3 py-1.5">
								{getProviderIcon(selectedProvider, {
									className: "size-4",
								})}
								<span className="text-sm font-medium">
									{formatProviderName(selectedProvider)}
								</span>
								<span className="text-xs text-muted-foreground ml-auto">
									{configuredProviderSet.has(
										selectedProvider,
									)
										? `${providerModelCounts[selectedProvider] || 0} models`
										: "Not configured"}
								</span>
							</div>
						)}

						{/* Model list */}
						<div
							id="model-selector-list"
							ref={modelListRef}
							role="listbox"
							className="overflow-y-auto flex-1 py-1 space-y-1 flex flex-col"
							onScroll={handleModelListScroll}
							style={{
								maskImage: `linear-gradient(to bottom, ${modelScrollPos === "top" ? "black" : "transparent"}, black 16px, black calc(100% - 16px), ${modelScrollPos === "bottom" ? "black" : "transparent"})`,
								WebkitMaskImage: `linear-gradient(to bottom, ${modelScrollPos === "top" ? "black" : "transparent"}, black 16px, black calc(100% - 16px), ${modelScrollPos === "bottom" ? "black" : "transparent"})`,
							}}
						>
							{currentDisplayItems.length === 0 ? (
								<div className="flex-1 flex flex-col items-center justify-center gap-3 px-4">
									{selectedProvider !== "all" &&
									!configuredProviderSet.has(
										selectedProvider,
									) ? (
										<>
											<div className="opacity-40">
												{getProviderIcon(
													selectedProvider,
													{
														className:
															"size-10",
													},
												)}
											</div>
											<p className="text-sm font-medium text-muted-foreground">
												No{" "}
												{formatProviderName(
													selectedProvider,
												)}{" "}
												models configured
											</p>
											<p className="text-xs text-muted-foreground/60 text-center">
												Add a model with this
												provider to get started
											</p>
											{addHandler && (
												<Button
													variant="secondary"
													size="sm"
													className="mt-1"
													onClick={() => {
														setOpen(false);
														addHandler(selectedProvider !== "all" ? selectedProvider : undefined);
													}}
												>
													{addLabel}
												</Button>
											)}
										</>
									) : searchQuery ? (
										<>
											<Search className="size-8 text-muted-foreground" />
											<p className="text-sm text-muted-foreground">
												No models found
											</p>
											<p className="text-xs text-muted-foreground/60">
												Try a different search
												term
											</p>
										</>
									) : (
										<>
											<p className="text-sm font-medium text-muted-foreground">
												No models configured
											</p>
											<p className="text-xs text-muted-foreground/60 text-center">
												Configure models in your search space settings
											</p>
										</>
									)}
								</div>
							) : (
								<>
									{globalItems.length > 0 && (
										<>
											<div className="flex items-center gap-2 px-3 py-1.5 text-[12px] font-semibold text-muted-foreground tracking-wider">
												Global Models
											</div>
											{globalItems.map((item, i) =>
												renderModelCard(
													item,
													globalStartIdx + i,
												),
											)}
										</>
									)}
									{globalItems.length > 0 &&
										userItems.length > 0 && (
											<div className="my-1.5 mx-4 h-px bg-border/60" />
										)}
									{userItems.length > 0 && (
										<>
											<div className="flex items-center gap-2 px-3 py-1.5 text-[12px] font-semibold text-muted-foreground tracking-wider">
												Your Configurations
											</div>
											{userItems.map((item, i) =>
												renderModelCard(
													item,
													userStartIdx + i,
												),
											)}
										</>
									)}
								</>
							)}
						</div>

						{/* Add model button */}
						{addHandler && (
							<div className="p-2">
								<Button
									variant="ghost"
									size="sm"
									className="w-full justify-start gap-2 h-9 rounded-lg hover:bg-accent/50 dark:hover:bg-white/[0.06]"
									onClick={() => {
										setOpen(false);
										addHandler(selectedProvider !== "all" ? selectedProvider : undefined);
									}}
								>
									<Plus className="size-4 text-primary" />
									<span className="text-sm font-medium">
										{addLabel}
									</span>
								</Button>
							</div>
						)}
					</div>
				</div>
			</div>
		);
	};

	// ─── Trigger button ───
	const triggerButton = (
		<Button
			variant="ghost"
			size="sm"
			role="combobox"
			aria-expanded={open}
			className={cn(
				"h-8 gap-2 px-3 text-sm bg-main-panel hover:bg-accent/50 dark:hover:bg-white/[0.06] border border-border/40 select-none",
				className,
			)}
		>
			{isLoading ? (
				<>
					<Spinner
						size="sm"
						className="text-muted-foreground"
					/>
					<span className="text-muted-foreground hidden md:inline">
						Loading
					</span>
				</>
			) : (
				<>
					{/* LLM */}
					{currentLLMConfig ? (
						<>
							{getProviderIcon(currentLLMConfig.provider, {
								isAutoMode: isLLMAutoMode ?? false,
							})}
							<span className="max-w-[100px] md:max-w-[120px] truncate hidden md:inline">
								{currentLLMConfig.name}
							</span>
						</>
					) : (
						<>
							<Bot className="size-4 text-muted-foreground" />
							<span className="text-muted-foreground hidden md:inline">
								Select Model
							</span>
						</>
					)}
					<div className="h-4 w-px bg-border/60 dark:bg-white/10 mx-0.5" />
					{/* Image */}
					{currentImageConfig ? (
						<>
							{getProviderIcon(currentImageConfig.provider, {
								isAutoMode: isImageAutoMode ?? false,
							})}
							<span className="max-w-[80px] md:max-w-[100px] truncate hidden md:inline">
								{currentImageConfig.name}
							</span>
						</>
					) : (
						<ImageIcon className="size-4 text-muted-foreground" />
					)}
					<div className="h-4 w-px bg-border/60 dark:bg-white/10 mx-0.5" />
					{/* Vision */}
					{currentVisionConfig ? (
						<>
							{getProviderIcon(currentVisionConfig.provider, {
								isAutoMode: isVisionAutoMode ?? false,
							})}
							<span className="max-w-[80px] md:max-w-[100px] truncate hidden md:inline">
								{currentVisionConfig.name}
							</span>
						</>
					) : (
						<ScanEye className="size-4 text-muted-foreground" />
					)}
				</>
			)}
			<ChevronDown className="h-3.5 w-3.5 text-muted-foreground ml-1 shrink-0" />
		</Button>
	);

	// ─── Shell: Drawer on mobile, Popover on desktop ───
	if (isMobile) {
		return (
			<Drawer open={open} onOpenChange={setOpen}>
				<DrawerTrigger asChild>{triggerButton}</DrawerTrigger>
				<DrawerContent className="max-h-[85vh]">
					<DrawerHandle />
					<DrawerHeader className="pb-0">
						<DrawerTitle>Select Model</DrawerTitle>
					</DrawerHeader>
					<div className="flex-1 overflow-hidden">
						{renderContent()}
					</div>
				</DrawerContent>
			</Drawer>
		);
	}

	return (
		<Popover open={open} onOpenChange={setOpen}>
			<PopoverTrigger asChild>{triggerButton}</PopoverTrigger>
			<PopoverContent
				className="w-[300px] md:w-[380px] p-0 rounded-lg shadow-lg overflow-hidden bg-white border-border/60 dark:bg-neutral-900 dark:border dark:border-white/5 select-none"
				align="start"
				sideOffset={8}
				onCloseAutoFocus={(e) => e.preventDefault()}
			>
				{renderContent()}
			</PopoverContent>
		</Popover>
	);
}
