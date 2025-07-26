"use client";

import { ChatInput } from "@llamaindex/chat-ui";
import { FolderOpen, Check, Zap, Brain } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
	Dialog,
	DialogContent,
	DialogDescription,
	DialogTitle,
	DialogTrigger,
	DialogFooter,
} from "@/components/ui/dialog";
import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { Suspense, useState, useCallback } from "react";
import { useParams } from "next/navigation";
import { useDocuments, Document } from "@/hooks/use-documents";
import { DocumentsDataTable } from "@/components/chat/DocumentsDataTable";
import { useSearchSourceConnectors } from "@/hooks/useSearchSourceConnectors";
import {
	getConnectorIcon,
	ConnectorButton as ConnectorButtonComponent,
} from "@/components/chat/ConnectorComponents";
import { ResearchMode } from "@/components/chat";
import { useLLMConfigs, useLLMPreferences } from "@/hooks/use-llm-configs";
import React from "react";

const DocumentSelector = React.memo(
	({
		onSelectionChange,
		selectedDocuments = [],
	}: {
		onSelectionChange?: (documents: Document[]) => void;
		selectedDocuments?: Document[];
	}) => {
		const { search_space_id } = useParams();
		const [isOpen, setIsOpen] = useState(false);

		const { documents, loading, isLoaded, fetchDocuments } = useDocuments(
			Number(search_space_id),
			true,
		);

		const handleOpenChange = useCallback(
			(open: boolean) => {
				setIsOpen(open);
				if (open && !isLoaded) {
					fetchDocuments();
				}
			},
			[fetchDocuments, isLoaded],
		);

		const handleSelectionChange = useCallback(
			(documents: Document[]) => {
				onSelectionChange?.(documents);
			},
			[onSelectionChange],
		);

		const handleDone = useCallback(() => {
			setIsOpen(false);
		}, []);

		const selectedCount = React.useMemo(
			() => selectedDocuments.length,
			[selectedDocuments.length],
		);

		return (
			<Dialog open={isOpen} onOpenChange={handleOpenChange}>
				<DialogTrigger asChild>
					<Button variant="outline" className="relative">
						<FolderOpen className="w-4 h-4" />
						{selectedCount > 0 && (
							<span className="absolute -top-2 -right-2 h-5 w-5 rounded-full bg-primary text-primary-foreground text-xs flex items-center justify-center">
								{selectedCount}
							</span>
						)}
					</Button>
				</DialogTrigger>

				<DialogContent className="max-w-[95vw] md:max-w-5xl h-[90vh] md:h-[85vh] p-0 flex flex-col">
					<div className="flex flex-col h-full">
						<div className="px-4 md:px-6 py-4 border-b flex-shrink-0">
							<DialogTitle className="text-lg md:text-xl">
								Select Documents
							</DialogTitle>
							<DialogDescription className="mt-1 text-sm">
								Choose documents to include in your research context
							</DialogDescription>
						</div>

						<div className="flex-1 min-h-0 p-4 md:p-6">
							{loading ? (
								<div className="flex items-center justify-center h-full">
									<div className="text-center space-y-2">
										<div className="animate-spin h-8 w-8 border-2 border-primary border-t-transparent rounded-full mx-auto" />
										<p className="text-sm text-muted-foreground">
											Loading documents...
										</p>
									</div>
								</div>
							) : isLoaded ? (
								<DocumentsDataTable
									documents={documents}
									onSelectionChange={handleSelectionChange}
									onDone={handleDone}
									initialSelectedDocuments={selectedDocuments}
								/>
							) : null}
						</div>
					</div>
				</DialogContent>
			</Dialog>
		);
	},
);

DocumentSelector.displayName = "DocumentSelector";

const ConnectorSelector = React.memo(
	({
		onSelectionChange,
		selectedConnectors = [],
	}: {
		onSelectionChange?: (connectorTypes: string[]) => void;
		selectedConnectors?: string[];
	}) => {
		const [isOpen, setIsOpen] = useState(false);

		const { connectorSourceItems, isLoading, isLoaded, fetchConnectors } =
			useSearchSourceConnectors(true);

		const handleOpenChange = useCallback(
			(open: boolean) => {
				setIsOpen(open);
				if (open && !isLoaded) {
					fetchConnectors();
				}
			},
			[fetchConnectors, isLoaded],
		);

		const handleConnectorToggle = useCallback(
			(connectorType: string) => {
				const isSelected = selectedConnectors.includes(connectorType);
				const newSelection = isSelected
					? selectedConnectors.filter((type) => type !== connectorType)
					: [...selectedConnectors, connectorType];
				onSelectionChange?.(newSelection);
			},
			[selectedConnectors, onSelectionChange],
		);

		const handleSelectAll = useCallback(() => {
			onSelectionChange?.(connectorSourceItems.map((c) => c.type));
		}, [connectorSourceItems, onSelectionChange]);

		const handleClearAll = useCallback(() => {
			onSelectionChange?.([]);
		}, [onSelectionChange]);

		return (
			<Dialog open={isOpen} onOpenChange={handleOpenChange}>
				<DialogTrigger asChild>
					<ConnectorButtonComponent
						selectedConnectors={selectedConnectors}
						onClick={() => setIsOpen(true)}
						connectorSources={connectorSourceItems}
					/>
				</DialogTrigger>

				<DialogContent className="sm:max-w-md">
					<DialogTitle>Select Connectors</DialogTitle>
					<DialogDescription>
						Choose which data sources to include in your research
					</DialogDescription>

					{/* Connector selection grid */}
					<div className="grid grid-cols-2 gap-4 py-4">
						{isLoading ? (
							<div className="col-span-2 flex justify-center py-4">
								<div className="animate-spin h-6 w-6 border-2 border-primary border-t-transparent rounded-full" />
							</div>
						) : (
							connectorSourceItems.map((connector) => {
								const isSelected = selectedConnectors.includes(connector.type);

								return (
									<div
										key={connector.id}
										className={`flex items-center gap-2 p-2 rounded-md border cursor-pointer transition-colors ${
											isSelected
												? "border-primary bg-primary/10"
												: "border-border hover:border-primary/50 hover:bg-muted"
										}`}
										onClick={() => handleConnectorToggle(connector.type)}
										role="checkbox"
										aria-checked={isSelected}
										tabIndex={0}
									>
										<div className="flex-shrink-0 w-6 h-6 flex items-center justify-center rounded-full bg-muted">
											{getConnectorIcon(connector.type)}
										</div>
										<span className="flex-1 text-sm font-medium">
											{connector.name}
										</span>
										{isSelected && <Check className="h-4 w-4 text-primary" />}
									</div>
								);
							})
						)}
					</div>

					<DialogFooter className="flex justify-between items-center">
						<div className="flex gap-2">
							<Button variant="outline" onClick={handleClearAll}>
								Clear All
							</Button>
							<Button onClick={handleSelectAll}>Select All</Button>
						</div>
					</DialogFooter>
				</DialogContent>
			</Dialog>
		);
	},
);

ConnectorSelector.displayName = "ConnectorSelector";

const SearchModeSelector = React.memo(
	({
		searchMode,
		onSearchModeChange,
	}: {
		searchMode?: "DOCUMENTS" | "CHUNKS";
		onSearchModeChange?: (mode: "DOCUMENTS" | "CHUNKS") => void;
	}) => {
		const handleDocumentsClick = React.useCallback(() => {
			onSearchModeChange?.("DOCUMENTS");
		}, [onSearchModeChange]);

		const handleChunksClick = React.useCallback(() => {
			onSearchModeChange?.("CHUNKS");
		}, [onSearchModeChange]);

		return (
			<div className="flex items-center gap-1 sm:gap-2">
				<span className="text-xs text-muted-foreground hidden sm:block">
					Scope:
				</span>
				<div className="flex rounded-md border border-border overflow-hidden">
					<Button
						variant={searchMode === "DOCUMENTS" ? "default" : "ghost"}
						size="sm"
						className="rounded-none border-r h-8 px-2 sm:px-3 text-xs transition-all duration-200 hover:bg-muted/80"
						onClick={handleDocumentsClick}
					>
						<span className="hidden sm:inline">Documents</span>
						<span className="sm:hidden">Docs</span>
					</Button>
					<Button
						variant={searchMode === "CHUNKS" ? "default" : "ghost"}
						size="sm"
						className="rounded-none h-8 px-2 sm:px-3 text-xs transition-all duration-200 hover:bg-muted/80"
						onClick={handleChunksClick}
					>
						Chunks
					</Button>
				</div>
			</div>
		);
	},
);

SearchModeSelector.displayName = "SearchModeSelector";

const ResearchModeSelector = React.memo(
	({
		researchMode,
		onResearchModeChange,
	}: {
		researchMode?: ResearchMode;
		onResearchModeChange?: (mode: ResearchMode) => void;
	}) => {
		const handleValueChange = React.useCallback(
			(value: string) => {
				onResearchModeChange?.(value as ResearchMode);
			},
			[onResearchModeChange],
		);

		// Memoize mode options to prevent recreation
		const modeOptions = React.useMemo(
			() => [
				{ value: "QNA", label: "Q&A", shortLabel: "Q&A" },
				{
					value: "REPORT_GENERAL",
					label: "General Report",
					shortLabel: "General",
				},
				{
					value: "REPORT_DEEP",
					label: "Deep Report",
					shortLabel: "Deep",
				},
				{
					value: "REPORT_DEEPER",
					label: "Deeper Report",
					shortLabel: "Deeper",
				},
			],
			[],
		);

		return (
			<div className="flex items-center gap-1 sm:gap-2">
				<span className="text-xs text-muted-foreground hidden sm:block">
					Mode:
				</span>
				<Select value={researchMode} onValueChange={handleValueChange}>
					<SelectTrigger className="w-auto min-w-[80px] sm:min-w-[120px] h-8 text-xs border-border bg-background hover:bg-muted/50 transition-colors duration-200 focus:ring-2 focus:ring-primary/20">
						<SelectValue placeholder="Mode" className="text-xs" />
					</SelectTrigger>
					<SelectContent align="end" className="min-w-[140px]">
						<div className="px-2 py-1.5 text-xs font-medium text-muted-foreground border-b bg-muted/30">
							Research Mode
						</div>
						{modeOptions.map((option) => (
							<SelectItem
								key={option.value}
								value={option.value}
								className="px-3 py-2 cursor-pointer hover:bg-accent/50 focus:bg-accent"
							>
								<span className="hidden sm:inline">{option.label}</span>
								<span className="sm:hidden">{option.shortLabel}</span>
							</SelectItem>
						))}
					</SelectContent>
				</Select>
			</div>
		);
	},
);

ResearchModeSelector.displayName = "ResearchModeSelector";

const LLMSelector = React.memo(() => {
	const { llmConfigs, loading: llmLoading, error } = useLLMConfigs();
	const {
		preferences,
		updatePreferences,
		loading: preferencesLoading,
	} = useLLMPreferences();

	const isLoading = llmLoading || preferencesLoading;

	// Memoize the selected config to avoid repeated lookups
	const selectedConfig = React.useMemo(() => {
		if (!preferences.fast_llm_id || !llmConfigs.length) return null;
		return (
			llmConfigs.find((config) => config.id === preferences.fast_llm_id) || null
		);
	}, [preferences.fast_llm_id, llmConfigs]);

	// Memoize the display value for the trigger
	const displayValue = React.useMemo(() => {
		if (!selectedConfig) return null;
		return (
			<div className="flex items-center gap-1">
				<span className="font-medium text-xs">{selectedConfig.provider}</span>
				<span className="text-muted-foreground">•</span>
				<span className="hidden sm:inline text-muted-foreground text-xs truncate max-w-[60px]">
					{selectedConfig.name}
				</span>
			</div>
		);
	}, [selectedConfig]);

	const handleValueChange = React.useCallback(
		(value: string) => {
			const llmId = value ? parseInt(value, 10) : undefined;
			updatePreferences({ fast_llm_id: llmId });
		},
		[updatePreferences],
	);

	// Loading skeleton
	if (isLoading) {
		return (
			<div className="h-8 min-w-[100px] sm:min-w-[120px]">
				<div className="h-8 rounded-md bg-muted animate-pulse flex items-center px-3">
					<div className="w-3 h-3 rounded bg-muted-foreground/20 mr-2" />
					<div className="h-3 w-16 rounded bg-muted-foreground/20" />
				</div>
			</div>
		);
	}

	// Error state
	if (error) {
		return (
			<div className="h-8 min-w-[100px] sm:min-w-[120px]">
				<Button
					variant="outline"
					size="sm"
					className="h-8 px-3 text-xs text-destructive border-destructive/50 hover:bg-destructive/10"
					disabled
				>
					<span className="text-xs">Error</span>
				</Button>
			</div>
		);
	}

	return (
		<div className="h-8 min-w-0">
			<Select
				value={preferences.fast_llm_id?.toString() || ""}
				onValueChange={handleValueChange}
				disabled={isLoading}
			>
				<SelectTrigger className="h-8 w-auto min-w-[100px] sm:min-w-[120px] px-3 text-xs border-border bg-background hover:bg-muted/50 transition-colors duration-200 focus:ring-2 focus:ring-primary/20">
					<div className="flex items-center gap-2 min-w-0">
						<Zap className="h-3 w-3 text-primary flex-shrink-0" />
						<SelectValue placeholder="Fast LLM" className="text-xs">
							{displayValue || (
								<span className="text-muted-foreground">Select LLM</span>
							)}
						</SelectValue>
					</div>
				</SelectTrigger>

				<SelectContent align="end" className="w-[300px] max-h-[400px]">
					<div className="px-3 py-2 text-xs font-medium text-muted-foreground border-b bg-muted/30">
						<div className="flex items-center gap-2">
							<Zap className="h-3 w-3" />
							Fast LLM Selection
						</div>
					</div>

					{llmConfigs.length === 0 ? (
						<div className="px-4 py-6 text-center">
							<div className="mx-auto w-12 h-12 rounded-full bg-muted flex items-center justify-center mb-3">
								<Brain className="h-5 w-5 text-muted-foreground" />
							</div>
							<h4 className="text-sm font-medium mb-1">
								No LLM configurations
							</h4>
							<p className="text-xs text-muted-foreground mb-3">
								Configure AI models to get started
							</p>
							<Button
								variant="outline"
								size="sm"
								className="text-xs"
								onClick={() => window.open("/settings", "_blank")}
							>
								Open Settings
							</Button>
						</div>
					) : (
						<div className="py-1">
							{llmConfigs.map((config) => (
								<SelectItem
									key={config.id}
									value={config.id.toString()}
									className="px-3 py-2 cursor-pointer hover:bg-accent/50 focus:bg-accent"
								>
									<div className="flex items-center justify-between w-full min-w-0">
										<div className="flex items-center gap-3 min-w-0 flex-1">
											<div className="flex h-8 w-8 items-center justify-center rounded-md bg-primary/10 flex-shrink-0">
												<Brain className="h-4 w-4 text-primary" />
											</div>
											<div className="min-w-0 flex-1">
												<div className="flex items-center gap-2 mb-1">
													<span className="font-medium text-sm truncate">
														{config.name}
													</span>
													<Badge
														variant="outline"
														className="text-xs px-1.5 py-0.5 flex-shrink-0"
													>
														{config.provider}
													</Badge>
												</div>
												<p className="text-xs text-muted-foreground font-mono truncate">
													{config.model_name}
												</p>
											</div>
										</div>
										{preferences.fast_llm_id === config.id && (
											<div className="flex h-5 w-5 items-center justify-center rounded-full bg-primary ml-2 flex-shrink-0">
												<Check className="h-3 w-3 text-primary-foreground" />
											</div>
										)}
									</div>
								</SelectItem>
							))}
						</div>
					)}
				</SelectContent>
			</Select>
		</div>
	);
});

LLMSelector.displayName = "LLMSelector";

const CustomChatInputOptions = React.memo(
	({
		onDocumentSelectionChange,
		selectedDocuments,
		onConnectorSelectionChange,
		selectedConnectors,
		searchMode,
		onSearchModeChange,
		researchMode,
		onResearchModeChange,
	}: {
		onDocumentSelectionChange?: (documents: Document[]) => void;
		selectedDocuments?: Document[];
		onConnectorSelectionChange?: (connectorTypes: string[]) => void;
		selectedConnectors?: string[];
		searchMode?: "DOCUMENTS" | "CHUNKS";
		onSearchModeChange?: (mode: "DOCUMENTS" | "CHUNKS") => void;
		researchMode?: ResearchMode;
		onResearchModeChange?: (mode: ResearchMode) => void;
	}) => {
		// Memoize the loading fallback to prevent recreation
		const loadingFallback = React.useMemo(
			() => (
				<div className="h-8 min-w-[100px] animate-pulse bg-muted rounded-md" />
			),
			[],
		);

		return (
			<div className="flex flex-wrap gap-2 sm:gap-3 items-center justify-start">
				<Suspense fallback={loadingFallback}>
					<DocumentSelector
						onSelectionChange={onDocumentSelectionChange}
						selectedDocuments={selectedDocuments}
					/>
				</Suspense>
				<Suspense fallback={loadingFallback}>
					<ConnectorSelector
						onSelectionChange={onConnectorSelectionChange}
						selectedConnectors={selectedConnectors}
					/>
				</Suspense>
				<SearchModeSelector
					searchMode={searchMode}
					onSearchModeChange={onSearchModeChange}
				/>
				<ResearchModeSelector
					researchMode={researchMode}
					onResearchModeChange={onResearchModeChange}
				/>
				<LLMSelector />
			</div>
		);
	},
);

CustomChatInputOptions.displayName = "CustomChatInputOptions";

export const ChatInputUI = React.memo(
	({
		onDocumentSelectionChange,
		selectedDocuments,
		onConnectorSelectionChange,
		selectedConnectors,
		searchMode,
		onSearchModeChange,
		researchMode,
		onResearchModeChange,
	}: {
		onDocumentSelectionChange?: (documents: Document[]) => void;
		selectedDocuments?: Document[];
		onConnectorSelectionChange?: (connectorTypes: string[]) => void;
		selectedConnectors?: string[];
		searchMode?: "DOCUMENTS" | "CHUNKS";
		onSearchModeChange?: (mode: "DOCUMENTS" | "CHUNKS") => void;
		researchMode?: ResearchMode;
		onResearchModeChange?: (mode: ResearchMode) => void;
	}) => {
		return (
			<ChatInput>
				<ChatInput.Form className="flex gap-2">
					<ChatInput.Field className="flex-1" />
					<ChatInput.Submit />
				</ChatInput.Form>
				<CustomChatInputOptions
					onDocumentSelectionChange={onDocumentSelectionChange}
					selectedDocuments={selectedDocuments}
					onConnectorSelectionChange={onConnectorSelectionChange}
					selectedConnectors={selectedConnectors}
					searchMode={searchMode}
					onSearchModeChange={onSearchModeChange}
					researchMode={researchMode}
					onResearchModeChange={onResearchModeChange}
				/>
			</ChatInput>
		);
	},
);

ChatInputUI.displayName = "ChatInputUI";
