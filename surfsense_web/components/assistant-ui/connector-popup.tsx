"use client";

import { useAtomValue } from "jotai";
import { AlertTriangle, Cable, Settings } from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import type { FC } from "react";
import {
	globalNewLLMConfigsAtom,
	llmPreferencesAtom,
} from "@/atoms/new-llm-config/new-llm-config-query.atoms";
import { activeSearchSpaceIdAtom } from "@/atoms/search-spaces/search-space-query.atoms";
import { currentUserAtom } from "@/atoms/user/user-query.atoms";
import { TooltipIconButton } from "@/components/assistant-ui/tooltip-icon-button";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { Spinner } from "@/components/ui/spinner";
import { Tabs, TabsContent } from "@/components/ui/tabs";
import type { SearchSourceConnector } from "@/contracts/types/connector.types";
import { useConnectorsElectric } from "@/hooks/use-connectors-electric";
import { useDocumentsElectric } from "@/hooks/use-documents-electric";
import { useInbox } from "@/hooks/use-inbox";
import { cn } from "@/lib/utils";
import { ConnectorDialogHeader } from "./connector-popup/components/connector-dialog-header";
import { ConnectorConnectView } from "./connector-popup/connector-configs/views/connector-connect-view";
import { ConnectorEditView } from "./connector-popup/connector-configs/views/connector-edit-view";
import { IndexingConfigurationView } from "./connector-popup/connector-configs/views/indexing-configuration-view";
import {
	COMPOSIO_CONNECTORS,
	OAUTH_CONNECTORS,
} from "./connector-popup/constants/connector-constants";
import { useConnectorDialog } from "./connector-popup/hooks/use-connector-dialog";
import { useIndexingConnectors } from "./connector-popup/hooks/use-indexing-connectors";
import { ActiveConnectorsTab } from "./connector-popup/tabs/active-connectors-tab";
import { AllConnectorsTab } from "./connector-popup/tabs/all-connectors-tab";
import { ConnectorAccountsListView } from "./connector-popup/views/connector-accounts-list-view";
import { YouTubeCrawlerView } from "./connector-popup/views/youtube-crawler-view";

export const ConnectorIndicator: FC = () => {
	const searchSpaceId = useAtomValue(activeSearchSpaceIdAtom);
	const searchParams = useSearchParams();
	const { data: currentUser } = useAtomValue(currentUserAtom);
	const { data: preferences = {}, isFetching: preferencesLoading } =
		useAtomValue(llmPreferencesAtom);
	const { data: globalConfigs = [], isFetching: globalConfigsLoading } =
		useAtomValue(globalNewLLMConfigsAtom);

	// Check if document summary LLM is properly configured
	// - If ID is 0 (Auto mode), we need global configs to be available
	// - If ID is positive (user config) or negative (specific global config), it's configured
	// - If ID is null/undefined, it's not configured
	const docSummaryLlmId = preferences.document_summary_llm_id;
	const isAutoMode = docSummaryLlmId === 0;
	const hasGlobalConfigs = globalConfigs.length > 0;

	const hasDocumentSummaryLLM =
		docSummaryLlmId !== null &&
		docSummaryLlmId !== undefined &&
		// If it's Auto mode, we need global configs to actually be available
		(!isAutoMode || hasGlobalConfigs);

	const llmConfigLoading = preferencesLoading || globalConfigsLoading;

	// Fetch document type counts using Electric SQL + PGlite for real-time updates
	const { documentTypeCounts, loading: documentTypesLoading } = useDocumentsElectric(searchSpaceId);

	// Fetch notifications to detect indexing failures
	const { inboxItems = [] } = useInbox(
		currentUser?.id ?? null,
		searchSpaceId ? Number(searchSpaceId) : null,
		"connector_indexing"
	);

	// Check if YouTube view is active
	const isYouTubeView = searchParams.get("view") === "youtube";

	// Use the custom hook for dialog state management
	const {
		isOpen,
		activeTab,
		connectingId,
		isScrolled,
		searchQuery,
		indexingConfig,
		indexingConnector,
		indexingConnectorConfig,
		editingConnector,
		connectingConnectorType,
		isCreatingConnector,
		startDate,
		endDate,
		isStartingIndexing,
		isSaving,
		isDisconnecting,
		periodicEnabled,
		frequencyMinutes,
		allConnectors,
		viewingAccountsType,
		viewingMCPList,
		setSearchQuery,
		setStartDate,
		setEndDate,
		setPeriodicEnabled,
		setFrequencyMinutes,
		handleOpenChange,
		handleTabChange,
		handleScroll,
		handleConnectOAuth,
		handleConnectNonOAuth,
		handleCreateWebcrawler,
		handleCreateYouTubeCrawler,
		handleSubmitConnectForm,
		handleStartIndexing,
		handleSkipIndexing,
		handleStartEdit,
		handleSaveConnector,
		handleDisconnectConnector,
		handleBackFromEdit,
		handleBackFromConnect,
		handleBackFromYouTube,
		handleViewAccountsList,
		handleBackFromAccountsList,
		handleBackFromMCPList,
		handleAddNewMCPFromList,
		handleQuickIndexConnector,
		connectorConfig,
		setConnectorConfig,
		setIndexingConnectorConfig,
		setConnectorName,
	} = useConnectorDialog();

	// Fetch connectors using Electric SQL + PGlite for real-time updates
	// This provides instant updates when connectors change, without polling
	const {
		connectors: connectorsFromElectric = [],
		loading: connectorsLoading,
		error: connectorsError,
		refreshConnectors: refreshConnectorsElectric,
	} = useConnectorsElectric(searchSpaceId);

	// Fallback to API if Electric is not available or fails
	// Use Electric data if: 1) we have data, or 2) still loading without error
	// Use API data if: Electric failed (has error) or finished loading with no data
	const useElectricData =
		connectorsFromElectric.length > 0 || (connectorsLoading && !connectorsError);
	const connectors = useElectricData ? connectorsFromElectric : allConnectors || [];

	// Manual refresh function that works with both Electric and API
	const refreshConnectors = async () => {
		if (useElectricData) {
			await refreshConnectorsElectric();
		} else {
			// Fallback: use allConnectors from useConnectorDialog (which uses connectorsAtom)
			// The connectorsAtom will handle refetching if needed
		}
	};

	// Track indexing state locally - clears automatically when Electric SQL detects last_indexed_at changed
	// Also clears when failed notifications are detected
	const { indexingConnectorIds, startIndexing, stopIndexing } = useIndexingConnectors(
		connectors as SearchSourceConnector[],
		inboxItems
	);

	const isLoading = connectorsLoading || documentTypesLoading;

	// Get document types that have documents in the search space
	const activeDocumentTypes = documentTypeCounts
		? Object.entries(documentTypeCounts).filter(([, count]) => count > 0)
		: [];

	const hasConnectors = connectors.length > 0;
	const hasSources = hasConnectors || activeDocumentTypes.length > 0;
	const totalSourceCount = connectors.length + activeDocumentTypes.length;

	const activeConnectorsCount = connectors.length;

	// Check which connectors are already connected
	// Using Electric SQL + PGlite for real-time connector updates
	const connectedTypes = new Set<string>(
		(connectors || []).map((c: SearchSourceConnector) => c.connector_type)
	);

	if (!searchSpaceId) return null;

	return (
		<Dialog open={isOpen} onOpenChange={handleOpenChange}>
			<TooltipIconButton
				data-joyride="connector-icon"
				tooltip={hasConnectors ? `Manage ${activeConnectorsCount} connectors` : "Connect your data"}
				side="bottom"
				className={cn(
					"size-[34px] rounded-full p-1 flex items-center justify-center transition-colors relative",
					"hover:bg-muted-foreground/15 dark:hover:bg-muted-foreground/30",
					"outline-none focus:outline-none focus-visible:outline-none font-semibold text-xs",
					"border-0 ring-0 focus:ring-0 shadow-none focus:shadow-none"
				)}
				aria-label={
					hasConnectors ? `View ${activeConnectorsCount} connectors` : "Add your first connector"
				}
				onClick={() => handleOpenChange(true)}
			>
				{isLoading ? (
					<Spinner size="sm" />
				) : (
					<>
						<Cable className="size-4 stroke-[1.5px]" />
						{activeConnectorsCount > 0 && (
							<span className="absolute -top-0.5 right-0 flex items-center justify-center min-w-[16px] h-4 px-1 text-[10px] font-medium rounded-full bg-primary text-primary-foreground shadow-sm">
								{activeConnectorsCount > 99 ? "99+" : activeConnectorsCount}
							</span>
						)}
					</>
				)}
			</TooltipIconButton>

			<DialogContent className="max-w-3xl w-[95vw] sm:w-full h-[75vh] sm:h-[85vh] flex flex-col p-0 gap-0 overflow-hidden border border-border bg-muted text-foreground focus:outline-none focus:ring-0 focus-visible:outline-none focus-visible:ring-0 [&>button]:right-4 sm:[&>button]:right-12 [&>button]:top-6 sm:[&>button]:top-10 [&>button]:opacity-80 hover:[&>button]:opacity-100 [&>button_svg]:size-5">
				<DialogTitle className="sr-only">Manage Connectors</DialogTitle>
				{/* YouTube Crawler View - shown when adding YouTube videos */}
				{isYouTubeView && searchSpaceId ? (
					<YouTubeCrawlerView searchSpaceId={searchSpaceId} onBack={handleBackFromYouTube} />
				) : viewingMCPList ? (
					<ConnectorAccountsListView
						connectorType="MCP_CONNECTOR"
						connectorTitle="MCP Connectors"
						connectors={(allConnectors || []) as SearchSourceConnector[]}
						indexingConnectorIds={indexingConnectorIds}
						onBack={handleBackFromMCPList}
						onManage={handleStartEdit}
						onAddAccount={handleAddNewMCPFromList}
						addButtonText="Add New MCP Server"
					/>
				) : viewingAccountsType ? (
					<ConnectorAccountsListView
						connectorType={viewingAccountsType.connectorType}
						connectorTitle={viewingAccountsType.connectorTitle}
						connectors={(connectors || []) as SearchSourceConnector[]} // Using Electric SQL + PGlite for real-time connector updates (all connector types)
						indexingConnectorIds={indexingConnectorIds}
						onBack={handleBackFromAccountsList}
						onManage={handleStartEdit}
						onAddAccount={() => {
							// Check both OAUTH_CONNECTORS and COMPOSIO_CONNECTORS
							const oauthConnector =
								OAUTH_CONNECTORS.find(
									(c) => c.connectorType === viewingAccountsType.connectorType
								) ||
								COMPOSIO_CONNECTORS.find(
									(c) => c.connectorType === viewingAccountsType.connectorType
								);
							if (oauthConnector) {
								handleConnectOAuth(oauthConnector);
							}
						}}
						isConnecting={connectingId !== null}
					/>
				) : connectingConnectorType ? (
					<ConnectorConnectView
						connectorType={connectingConnectorType}
						onSubmit={(formData) => handleSubmitConnectForm(formData, startIndexing)}
						onBack={handleBackFromConnect}
						isSubmitting={isCreatingConnector}
					/>
				) : editingConnector ? (
					<ConnectorEditView
						connector={{
							...editingConnector,
							config: connectorConfig || editingConnector.config,
							name: editingConnector.name,
							// Sync last_indexed_at with live data from Electric SQL for real-time updates
							last_indexed_at:
								(connectors as SearchSourceConnector[]).find((c) => c.id === editingConnector.id)
									?.last_indexed_at ?? editingConnector.last_indexed_at,
						}}
						startDate={startDate}
						endDate={endDate}
						periodicEnabled={periodicEnabled}
						frequencyMinutes={frequencyMinutes}
						isSaving={isSaving}
						isDisconnecting={isDisconnecting}
						isIndexing={indexingConnectorIds.has(editingConnector.id)}
						searchSpaceId={searchSpaceId?.toString()}
						onStartDateChange={setStartDate}
						onEndDateChange={setEndDate}
						onPeriodicEnabledChange={setPeriodicEnabled}
						onFrequencyChange={setFrequencyMinutes}
						onSave={() => {
							startIndexing(editingConnector.id);
							handleSaveConnector(() => refreshConnectors());
						}}
						onDisconnect={() => handleDisconnectConnector(() => refreshConnectors())}
						onBack={handleBackFromEdit}
						onQuickIndex={
							editingConnector.connector_type !== "GOOGLE_DRIVE_CONNECTOR"
								? () => {
										startIndexing(editingConnector.id);
										handleQuickIndexConnector(
											editingConnector.id,
											editingConnector.connector_type,
											stopIndexing,
											startDate,
											endDate
										);
									}
								: undefined
						}
						onConfigChange={setConnectorConfig}
						onNameChange={setConnectorName}
					/>
				) : indexingConfig ? (
					<IndexingConfigurationView
						config={indexingConfig}
						connector={
							indexingConnector
								? {
										...indexingConnector,
										config: indexingConnectorConfig || indexingConnector.config,
									}
								: undefined
						}
						startDate={startDate}
						endDate={endDate}
						periodicEnabled={periodicEnabled}
						frequencyMinutes={frequencyMinutes}
						isStartingIndexing={isStartingIndexing}
						onStartDateChange={setStartDate}
						onEndDateChange={setEndDate}
						onPeriodicEnabledChange={setPeriodicEnabled}
						onFrequencyChange={setFrequencyMinutes}
						onConfigChange={setIndexingConnectorConfig}
						onStartIndexing={() => {
							if (indexingConfig.connectorId) {
								startIndexing(indexingConfig.connectorId);
							}
							handleStartIndexing(() => refreshConnectors());
						}}
						onSkip={handleSkipIndexing}
					/>
				) : (
					<Tabs
						value={activeTab}
						onValueChange={handleTabChange}
						className="flex-1 flex flex-col min-h-0"
					>
						{/* Header */}
						<ConnectorDialogHeader
							activeTab={activeTab}
							totalSourceCount={activeConnectorsCount}
							searchQuery={searchQuery}
							onTabChange={handleTabChange}
							onSearchChange={setSearchQuery}
							isScrolled={isScrolled}
						/>

						{/* Content */}
						<div className="flex-1 min-h-0 relative overflow-hidden">
							<div className="h-full overflow-y-auto" onScroll={handleScroll}>
								<div className="px-4 sm:px-12 py-4 sm:py-8 pb-12 sm:pb-16">
									{/* LLM Configuration Warning */}
									{!llmConfigLoading && !hasDocumentSummaryLLM && (
										<Alert variant="destructive" className="mb-6">
											<AlertTriangle className="h-4 w-4" />
											<AlertTitle>LLM Configuration Required</AlertTitle>
											<AlertDescription className="mt-2">
												<p className="mb-3">
													{isAutoMode && !hasGlobalConfigs
														? "Auto mode is selected but no global LLM configurations are available. Please configure a custom LLM in Settings to process and summarize documents from your connected sources."
														: "You need to configure a Document Summary LLM before adding connectors. This LLM is used to process and summarize documents from your connected sources."}
												</p>
												<Button asChild size="sm" variant="outline">
													<Link href={`/dashboard/${searchSpaceId}/settings`}>
														<Settings className="mr-2 h-4 w-4" />
														Go to Settings
													</Link>
												</Button>
											</AlertDescription>
										</Alert>
									)}

									<TabsContent value="all" className="m-0">
										<AllConnectorsTab
											searchQuery={searchQuery}
											searchSpaceId={searchSpaceId}
											connectedTypes={connectedTypes}
											connectingId={connectingId}
											allConnectors={connectors}
											documentTypeCounts={documentTypeCounts}
											indexingConnectorIds={indexingConnectorIds}
											onConnectOAuth={hasDocumentSummaryLLM ? handleConnectOAuth : () => {}}
											onConnectNonOAuth={hasDocumentSummaryLLM ? handleConnectNonOAuth : () => {}}
											onCreateWebcrawler={hasDocumentSummaryLLM ? handleCreateWebcrawler : () => {}}
											onCreateYouTubeCrawler={
												hasDocumentSummaryLLM ? handleCreateYouTubeCrawler : () => {}
											}
											onManage={handleStartEdit}
											onViewAccountsList={handleViewAccountsList}
										/>
									</TabsContent>

									<ActiveConnectorsTab
										searchQuery={searchQuery}
										hasSources={hasSources}
										totalSourceCount={totalSourceCount}
										activeDocumentTypes={activeDocumentTypes}
										connectors={connectors as SearchSourceConnector[]}
										indexingConnectorIds={indexingConnectorIds}
										searchSpaceId={searchSpaceId}
										onTabChange={handleTabChange}
										onManage={handleStartEdit}
										onViewAccountsList={handleViewAccountsList}
									/>
								</div>
							</div>
							{/* Bottom fade shadow */}
							<div className="absolute bottom-0 left-0 right-0 h-7 bg-gradient-to-t from-muted via-muted/80 to-transparent pointer-events-none z-10" />
						</div>
					</Tabs>
				)}
			</DialogContent>
		</Dialog>
	);
};
