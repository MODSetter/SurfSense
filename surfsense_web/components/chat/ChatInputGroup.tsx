"use client";

import { ChatInput } from "@llamaindex/chat-ui";
import { Brain, Check, FolderOpen, Minus, Plus, Zap } from "lucide-react";
import { useParams } from "next/navigation";
import React, { Suspense, useCallback, useState } from "react";
import { DocumentsDataTable } from "@/components/chat/DocumentsDataTable";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
	Dialog,
	DialogContent,
	DialogDescription,
	DialogFooter,
	DialogTitle,
	DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { getConnectorIcon } from "@/contracts/enums/connectorIcons";
import { useDocumentTypes } from "@/hooks/use-document-types";
import type { Document } from "@/hooks/use-documents";
import { useLLMConfigs, useLLMPreferences } from "@/hooks/use-llm-configs";
import { useSearchSourceConnectors } from "@/hooks/use-search-source-connectors";

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

		const handleOpenChange = useCallback((open: boolean) => {
			setIsOpen(open);
		}, []);

		const handleSelectionChange = useCallback(
			(documents: Document[]) => {
				onSelectionChange?.(documents);
			},
			[onSelectionChange]
		);

		const handleDone = useCallback(() => {
			setIsOpen(false);
		}, []);

		const selectedCount = React.useMemo(() => selectedDocuments.length, [selectedDocuments.length]);

		return (
			<Dialog open={isOpen} onOpenChange={handleOpenChange}>
				<DialogTrigger asChild>
					<Button
						variant="outline"
						size="sm"
						className="h-9 gap-2 px-3 border-dashed hover:border-solid hover:bg-accent/50 transition-all"
					>
						<FolderOpen className="h-4 w-4 text-muted-foreground" />
						<span className="text-xs font-medium">
							{selectedCount > 0 ? `Selected` : "Documents"}
						</span>
						{selectedCount > 0 && (
							<Badge variant="secondary" className="h-5 px-1.5 text-xs font-medium">
								{selectedCount}
							</Badge>
						)}
					</Button>
				</DialogTrigger>

				<DialogContent className="max-w-[95vw] md:max-w-5xl h-[90vh] md:h-[85vh] p-0 flex flex-col">
					<div className="flex flex-col h-full">
						<div className="px-4 md:px-6 py-4 border-b flex-shrink-0 bg-muted/30">
							<DialogTitle className="text-lg md:text-xl font-semibold">
								Select Documents
							</DialogTitle>
							<DialogDescription className="mt-1.5 text-sm">
								Choose specific documents to include in your research context
							</DialogDescription>
						</div>

						<div className="flex-1 min-h-0 p-4 md:p-6">
							<DocumentsDataTable
								searchSpaceId={Number(search_space_id)}
								onSelectionChange={handleSelectionChange}
								onDone={handleDone}
								initialSelectedDocuments={selectedDocuments}
							/>
						</div>
					</div>
				</DialogContent>
			</Dialog>
		);
	}
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
		const { search_space_id } = useParams();
		const [isOpen, setIsOpen] = useState(false);

		// Fetch immediately (not lazy) so the button can show the correct count
		const { documentTypes, isLoading, isLoaded, fetchDocumentTypes } = useDocumentTypes(
			Number(search_space_id),
			false
		);

		// Fetch live search connectors immediately (non-indexable)
		const {
			connectors: searchConnectors,
			isLoading: connectorsLoading,
			isLoaded: connectorsLoaded,
			fetchConnectors,
		} = useSearchSourceConnectors(false, Number(search_space_id));

		// Filter for non-indexable connectors (live search)
		const liveSearchConnectors = React.useMemo(
			() => searchConnectors.filter((connector) => !connector.is_indexable),
			[searchConnectors]
		);

		const handleOpenChange = useCallback((open: boolean) => {
			setIsOpen(open);
			// Data is already loaded on mount, no need to fetch again
		}, []);

		const handleConnectorToggle = useCallback(
			(connectorType: string) => {
				const isSelected = selectedConnectors.includes(connectorType);
				const newSelection = isSelected
					? selectedConnectors.filter((type) => type !== connectorType)
					: [...selectedConnectors, connectorType];
				onSelectionChange?.(newSelection);
			},
			[selectedConnectors, onSelectionChange]
		);

		const handleSelectAll = useCallback(() => {
			const allTypes = [
				...documentTypes.map((dt) => dt.type),
				...liveSearchConnectors.map((c) => c.connector_type),
			];
			onSelectionChange?.(allTypes);
		}, [documentTypes, liveSearchConnectors, onSelectionChange]);

		const handleClearAll = useCallback(() => {
			onSelectionChange?.([]);
		}, [onSelectionChange]);

		// Get display name for connector type
		const getDisplayName = (type: string) => {
			return type
				.split("_")
				.map((word) => word.charAt(0) + word.slice(1).toLowerCase())
				.join(" ");
		};

		// Get selected document types with their counts
		const selectedDocTypes = documentTypes.filter((dt) => selectedConnectors.includes(dt.type));
		const selectedLiveConnectors = liveSearchConnectors.filter((c) =>
			selectedConnectors.includes(c.connector_type)
		);

		// Total selected count
		const totalSelectedCount = selectedDocTypes.length + selectedLiveConnectors.length;
		const totalAvailableCount = documentTypes.length + liveSearchConnectors.length;

		return (
			<Dialog open={isOpen} onOpenChange={handleOpenChange}>
				<DialogTrigger asChild>
					<Button
						variant="outline"
						size="sm"
						className="relative h-9 gap-2 px-3 border-dashed hover:border-solid hover:bg-accent/50 transition-all"
					>
						<div className="flex items-center gap-1.5">
							{totalSelectedCount > 0 ? (
								<>
									<div className="flex items-center -space-x-2">
										{selectedDocTypes.slice(0, 2).map((docType) => (
											<div
												key={docType.type}
												className="flex h-6 w-6 items-center justify-center rounded-full border-2 border-background bg-muted"
											>
												{getConnectorIcon(docType.type, "h-3 w-3")}
											</div>
										))}
										{selectedLiveConnectors
											.slice(0, 3 - selectedDocTypes.slice(0, 2).length)
											.map((connector) => (
												<div
													key={connector.id}
													className="flex h-6 w-6 items-center justify-center rounded-full border-2 border-background bg-muted"
												>
													{getConnectorIcon(connector.connector_type, "h-3 w-3")}
												</div>
											))}
									</div>
									<span className="text-xs font-medium">
										{totalSelectedCount} {totalSelectedCount === 1 ? "source" : "sources"}
									</span>
								</>
							) : (
								<>
									<Brain className="h-4 w-4 text-muted-foreground" />
									<span className="text-xs font-medium">Sources</span>
								</>
							)}
						</div>
					</Button>
				</DialogTrigger>

				<DialogContent className="sm:max-w-2xl max-h-[85vh] flex flex-col">
					<div className="space-y-4 flex-1 overflow-y-auto pr-2">
						<div>
							<DialogTitle className="text-xl">Select Sources</DialogTitle>
							<DialogDescription className="mt-1.5">
								Choose indexed document types and live search connectors to include in your search
							</DialogDescription>
						</div>

						{isLoading || connectorsLoading ? (
							<div className="flex justify-center py-8">
								<div className="animate-spin h-8 w-8 border-3 border-primary border-t-transparent rounded-full" />
							</div>
						) : totalAvailableCount === 0 ? (
							<div className="flex flex-col items-center justify-center py-12 text-center">
								<div className="rounded-full bg-muted p-4 mb-4">
									<Brain className="h-8 w-8 text-muted-foreground" />
								</div>
								<h4 className="text-sm font-medium mb-1">No sources found</h4>
								<p className="text-xs text-muted-foreground max-w-xs">
									Add documents or configure search connectors for this search space
								</p>
							</div>
						) : (
							<>
								{/* Live Search Connectors Section */}
								{liveSearchConnectors.length > 0 && (
									<div className="space-y-2">
										<div className="flex items-center gap-2 pb-2">
											<Zap className="h-4 w-4 text-primary" />
											<h3 className="text-sm font-semibold">Live Search Connectors</h3>
											<Badge variant="outline" className="text-xs">
												Real-time
											</Badge>
										</div>
										<div className="grid grid-cols-2 gap-3">
											{liveSearchConnectors.map((connector) => {
												const isSelected = selectedConnectors.includes(connector.connector_type);

												return (
													<button
														key={connector.id}
														onClick={() => handleConnectorToggle(connector.connector_type)}
														type="button"
														className={`group relative flex items-center gap-3 p-3 rounded-lg border-2 transition-all ${
															isSelected
																? "border-primary bg-primary/5 shadow-sm"
																: "border-border hover:border-primary/50 hover:bg-accent/50"
														}`}
													>
														<div
															className={`flex h-10 w-10 items-center justify-center rounded-md transition-colors ${
																isSelected ? "bg-primary/10" : "bg-muted group-hover:bg-primary/5"
															}`}
														>
															{getConnectorIcon(
																connector.connector_type,
																`h-5 w-5 ${isSelected ? "text-primary" : "text-muted-foreground group-hover:text-primary"}`
															)}
														</div>
														<div className="flex-1 text-left min-w-0">
															<div className="flex items-center gap-2">
																<p className="text-sm font-medium truncate">{connector.name}</p>
																{isSelected && (
																	<div className="flex h-5 w-5 items-center justify-center rounded-full bg-primary">
																		<Check className="h-3 w-3 text-primary-foreground" />
																	</div>
																)}
															</div>
															<p className="text-xs text-muted-foreground mt-0.5 truncate">
																{getDisplayName(connector.connector_type)}
															</p>
														</div>
													</button>
												);
											})}
										</div>
									</div>
								)}

								{/* Document Types Section */}
								{documentTypes.length > 0 && (
									<div className="space-y-2">
										<div className="flex items-center gap-2 pb-2">
											<FolderOpen className="h-4 w-4 text-primary" />
											<h3 className="text-sm font-semibold">Indexed Document Types</h3>
											<Badge variant="outline" className="text-xs">
												Stored
											</Badge>
										</div>
										<div className="grid grid-cols-2 gap-3">
											{documentTypes.map((docType) => {
												const isSelected = selectedConnectors.includes(docType.type);

												return (
													<button
														key={docType.type}
														onClick={() => handleConnectorToggle(docType.type)}
														type="button"
														className={`group relative flex items-center gap-3 p-3 rounded-lg border-2 transition-all ${
															isSelected
																? "border-primary bg-primary/5 shadow-sm"
																: "border-border hover:border-primary/50 hover:bg-accent/50"
														}`}
													>
														<div
															className={`flex h-10 w-10 items-center justify-center rounded-md transition-colors ${
																isSelected ? "bg-primary/10" : "bg-muted group-hover:bg-primary/5"
															}`}
														>
															{getConnectorIcon(
																docType.type,
																`h-5 w-5 ${isSelected ? "text-primary" : "text-muted-foreground group-hover:text-primary"}`
															)}
														</div>
														<div className="flex-1 text-left min-w-0">
															<div className="flex items-center gap-2">
																<p className="text-sm font-medium truncate">
																	{getDisplayName(docType.type)}
																</p>
																{isSelected && (
																	<div className="flex h-5 w-5 items-center justify-center rounded-full bg-primary">
																		<Check className="h-3 w-3 text-primary-foreground" />
																	</div>
																)}
															</div>
															<p className="text-xs text-muted-foreground mt-0.5">
																{docType.count} {docType.count === 1 ? "document" : "documents"}
															</p>
														</div>
													</button>
												);
											})}
										</div>
									</div>
								)}
							</>
						)}
					</div>

					{totalAvailableCount > 0 && (
						<DialogFooter className="flex flex-row justify-between items-center gap-2 pt-4 border-t">
							<Button
								variant="ghost"
								size="sm"
								onClick={handleClearAll}
								disabled={selectedConnectors.length === 0}
								className="text-xs"
							>
								Clear All
							</Button>
							<Button
								size="sm"
								onClick={handleSelectAll}
								disabled={selectedConnectors.length === totalAvailableCount}
								className="text-xs"
							>
								Select All ({totalAvailableCount})
							</Button>
						</DialogFooter>
					)}
				</DialogContent>
			</Dialog>
		);
	}
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
			<div className="flex items-center gap-2">
				<div className="inline-flex h-9 items-center justify-center rounded-lg bg-muted p-1 text-muted-foreground">
					<button
						type="button"
						onClick={handleDocumentsClick}
						className={`inline-flex items-center justify-center whitespace-nowrap rounded-md px-3 py-1.5 text-xs font-medium transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 ${
							searchMode === "DOCUMENTS"
								? "bg-background text-foreground shadow-sm"
								: "hover:bg-background/50 hover:text-foreground"
						}`}
					>
						<FolderOpen className="h-3.5 w-3.5 mr-1.5" />
						<span className="hidden sm:inline">Documents</span>
						<span className="sm:hidden">Docs</span>
					</button>
					<button
						type="button"
						onClick={handleChunksClick}
						className={`inline-flex items-center justify-center whitespace-nowrap rounded-md px-3 py-1.5 text-xs font-medium transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 ${
							searchMode === "CHUNKS"
								? "bg-background text-foreground shadow-sm"
								: "hover:bg-background/50 hover:text-foreground"
						}`}
					>
						<Zap className="h-3.5 w-3.5 mr-1.5" />
						Chunks
					</button>
				</div>
			</div>
		);
	}
);

SearchModeSelector.displayName = "SearchModeSelector";

const TopKSelector = React.memo(
	({ topK = 10, onTopKChange }: { topK?: number; onTopKChange?: (topK: number) => void }) => {
		const MIN_VALUE = 1;
		const MAX_VALUE = 100;

		const handleIncrement = React.useCallback(() => {
			if (topK < MAX_VALUE) {
				onTopKChange?.(topK + 1);
			}
		}, [topK, onTopKChange]);

		const handleDecrement = React.useCallback(() => {
			if (topK > MIN_VALUE) {
				onTopKChange?.(topK - 1);
			}
		}, [topK, onTopKChange]);

		const handleInputChange = React.useCallback(
			(e: React.ChangeEvent<HTMLInputElement>) => {
				const value = e.target.value;
				// Allow empty input for editing
				if (value === "") {
					return;
				}
				const numValue = parseInt(value, 10);
				if (!isNaN(numValue) && numValue >= MIN_VALUE && numValue <= MAX_VALUE) {
					onTopKChange?.(numValue);
				}
			},
			[onTopKChange]
		);

		const handleInputBlur = React.useCallback(
			(e: React.FocusEvent<HTMLInputElement>) => {
				const value = e.target.value;
				if (value === "") {
					// Reset to default if empty
					onTopKChange?.(10);
					return;
				}
				const numValue = parseInt(value, 10);
				if (isNaN(numValue) || numValue < MIN_VALUE) {
					onTopKChange?.(MIN_VALUE);
				} else if (numValue > MAX_VALUE) {
					onTopKChange?.(MAX_VALUE);
				}
			},
			[onTopKChange]
		);

		return (
			<TooltipProvider>
				<Tooltip delayDuration={200}>
					<TooltipTrigger asChild>
						<div className="flex items-center h-8 border rounded-md bg-background hover:bg-accent/50 transition-colors">
							<Button
								type="button"
								variant="ghost"
								size="icon"
								className="h-full w-7 rounded-l-md rounded-r-none hover:bg-accent border-r"
								onClick={handleDecrement}
								disabled={topK <= MIN_VALUE}
							>
								<Minus className="h-3.5 w-3.5" />
							</Button>
							<div className="flex flex-col items-center justify-center px-2 min-w-[60px]">
								<Input
									type="number"
									value={topK}
									onChange={handleInputChange}
									onBlur={handleInputBlur}
									min={MIN_VALUE}
									max={MAX_VALUE}
									className="h-5 w-full px-1 text-center text-sm font-semibold border-0 bg-transparent focus-visible:ring-0 focus-visible:ring-offset-0 [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none"
								/>
								<span className="text-[10px] text-muted-foreground leading-none">Results</span>
							</div>
							<Button
								type="button"
								variant="ghost"
								size="icon"
								className="h-full w-7 rounded-r-md rounded-l-none hover:bg-accent border-l"
								onClick={handleIncrement}
								disabled={topK >= MAX_VALUE}
							>
								<Plus className="h-3.5 w-3.5" />
							</Button>
						</div>
					</TooltipTrigger>
					<TooltipContent side="top" className="max-w-xs">
						<div className="space-y-2">
							<p className="text-sm font-semibold">Results per Source</p>
							<p className="text-xs text-muted-foreground leading-relaxed">
								Control how many results to fetch from each data source. Set a higher number to get
								more information, or a lower number for faster, more focused results.
							</p>
							<div className="flex items-center gap-2 text-xs text-muted-foreground pt-1 border-t">
								<span>Recommended: 5-20</span>
								<span>•</span>
								<span>
									Range: {MIN_VALUE}-{MAX_VALUE}
								</span>
							</div>
						</div>
					</TooltipContent>
				</Tooltip>
			</TooltipProvider>
		);
	}
);

TopKSelector.displayName = "TopKSelector";

const LLMSelector = React.memo(() => {
	const { search_space_id } = useParams();
	const searchSpaceId = Number(search_space_id);

	const { llmConfigs, loading: llmLoading, error } = useLLMConfigs(searchSpaceId);
	const {
		preferences,
		updatePreferences,
		loading: preferencesLoading,
	} = useLLMPreferences(searchSpaceId);

	const isLoading = llmLoading || preferencesLoading;

	// Memoize the selected config to avoid repeated lookups
	const selectedConfig = React.useMemo(() => {
		if (!preferences.fast_llm_id || !llmConfigs.length) return null;
		return llmConfigs.find((config) => config.id === preferences.fast_llm_id) || null;
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
		[updatePreferences]
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
							{displayValue || <span className="text-muted-foreground">Select LLM</span>}
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
							<h4 className="text-sm font-medium mb-1">No LLM configurations</h4>
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
													<span className="font-medium text-sm truncate">{config.name}</span>
													<Badge variant="outline" className="text-xs px-1.5 py-0.5 flex-shrink-0">
														{config.provider}
													</Badge>
												</div>
												<p className="text-xs text-muted-foreground font-mono truncate">
													{config.model_name}
												</p>
											</div>
										</div>
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
		topK,
		onTopKChange,
	}: {
		onDocumentSelectionChange?: (documents: Document[]) => void;
		selectedDocuments?: Document[];
		onConnectorSelectionChange?: (connectorTypes: string[]) => void;
		selectedConnectors?: string[];
		searchMode?: "DOCUMENTS" | "CHUNKS";
		onSearchModeChange?: (mode: "DOCUMENTS" | "CHUNKS") => void;
		topK?: number;
		onTopKChange?: (topK: number) => void;
	}) => {
		// Memoize the loading fallback to prevent recreation
		const loadingFallback = React.useMemo(
			() => <div className="h-9 w-24 animate-pulse bg-muted/50 rounded-md" />,
			[]
		);

		return (
			<div className="flex flex-wrap gap-2 items-center">
				<div className="flex items-center gap-2">
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
				</div>
				<div className="h-4 w-px bg-border hidden sm:block" />
				<SearchModeSelector searchMode={searchMode} onSearchModeChange={onSearchModeChange} />
				<div className="h-4 w-px bg-border hidden sm:block" />
				<TopKSelector topK={topK} onTopKChange={onTopKChange} />
				<div className="h-4 w-px bg-border hidden sm:block" />
				<LLMSelector />
			</div>
		);
	}
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
		topK,
		onTopKChange,
	}: {
		onDocumentSelectionChange?: (documents: Document[]) => void;
		selectedDocuments?: Document[];
		onConnectorSelectionChange?: (connectorTypes: string[]) => void;
		selectedConnectors?: string[];
		searchMode?: "DOCUMENTS" | "CHUNKS";
		onSearchModeChange?: (mode: "DOCUMENTS" | "CHUNKS") => void;
		topK?: number;
		onTopKChange?: (topK: number) => void;
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
					topK={topK}
					onTopKChange={onTopKChange}
				/>
			</ChatInput>
		);
	}
);

ChatInputUI.displayName = "ChatInputUI";
