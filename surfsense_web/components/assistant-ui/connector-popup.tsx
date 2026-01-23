"use client";

import { useAtomValue } from "jotai";
import { Cable, Loader2 } from "lucide-react";
import { useSearchParams } from "next/navigation";
import type { FC } from "react";
import { activeSearchSpaceIdAtom } from "@/atoms/search-spaces/search-space-query.atoms";
import { TooltipIconButton } from "@/components/assistant-ui/tooltip-icon-button";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Tabs, TabsContent } from "@/components/ui/tabs";
import type { SearchSourceConnector } from "@/contracts/types/connector.types";
import { useConnectorsElectric } from "@/hooks/use-connectors-electric";
import { useDocumentsElectric } from "@/hooks/use-documents-electric";
import { cn } from "@/lib/utils";
import { ConnectorDialogHeader } from "./connector-popup/components/connector-dialog-header";
import { ConnectorConnectView } from "./connector-popup/connector-configs/views/connector-connect-view";
import { ConnectorEditView } from "./connector-popup/connector-configs/views/connector-edit-view";
import { IndexingConfigurationView } from "./connector-popup/connector-configs/views/indexing-configuration-view";
import { OAUTH_CONNECTORS } from "./connector-popup/constants/connector-constants";
import { useConnectorDialog } from "./connector-popup/hooks/use-connector-dialog";
import { useIndexingConnectors } from "./connector-popup/hooks/use-indexing-connectors";
import { ActiveConnectorsTab } from "./connector-popup/tabs/active-connectors-tab";
import { AllConnectorsTab } from "./connector-popup/tabs/all-connectors-tab";
import { ComposioToolkitView } from "./connector-popup/views/composio-toolkit-view";
import { ConnectorAccountsListView } from "./connector-popup/views/connector-accounts-list-view";
import { YouTubeCrawlerView } from "./connector-popup/views/youtube-crawler-view";

export const ConnectorIndicator: FC = () => {
	const searchSpaceId = useAtomValue(activeSearchSpaceIdAtom);
	const searchParams = useSearchParams();

	// Fetch document type counts using Electric SQL + PGlite for real-time updates
	const { documentTypeCounts, loading: documentTypesLoading } = useDocumentsElectric(searchSpaceId);

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
		// Composio
		viewingComposio,
		connectingComposioToolkit,
		handleOpenComposio,
		handleBackFromComposio,
		handleConnectComposioToolkit,
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
	const { indexingConnectorIds, startIndexing } = useIndexingConnectors(
		connectors as SearchSourceConnector[]
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
	const connectedTypes = new Set(
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
					<Loader2 className="size-4 animate-spin" />
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

			<DialogContent className="max-w-3xl w-[95vw] sm:w-full h-[75vh] sm:h-[85vh] flex flex-col p-0 gap-0 overflow-hidden border border-border bg-muted text-foreground [&>button]:right-4 sm:[&>button]:right-12 [&>button]:top-6 sm:[&>button]:top-10 [&>button]:opacity-80 hover:[&>button]:opacity-100 [&>button_svg]:size-5">
				{/* YouTube Crawler View - shown when adding YouTube videos */}
				{isYouTubeView && searchSpaceId ? (
					<YouTubeCrawlerView searchSpaceId={searchSpaceId} onBack={handleBackFromYouTube} />
				) : viewingComposio && searchSpaceId ? (
					<ComposioToolkitView
						searchSpaceId={searchSpaceId}
						connectedToolkits={(connectors || [])
							.filter((c: SearchSourceConnector) => c.connector_type === "COMPOSIO_CONNECTOR")
							.map((c: SearchSourceConnector) => c.config?.toolkit_id as string)
							.filter(Boolean)}
						onBack={handleBackFromComposio}
						onConnectToolkit={handleConnectComposioToolkit}
						isConnecting={connectingComposioToolkit !== null}
						connectingToolkitId={connectingComposioToolkit}
					/>
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
							const oauthConnector = OAUTH_CONNECTORS.find(
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
										handleQuickIndexConnector(editingConnector.id, editingConnector.connector_type);
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
									<TabsContent value="all" className="m-0">
										<AllConnectorsTab
											searchQuery={searchQuery}
											searchSpaceId={searchSpaceId}
											connectedTypes={connectedTypes}
											connectingId={connectingId}
											allConnectors={connectors}
											documentTypeCounts={documentTypeCounts}
											indexingConnectorIds={indexingConnectorIds}
											onConnectOAuth={handleConnectOAuth}
											onConnectNonOAuth={handleConnectNonOAuth}
											onCreateWebcrawler={handleCreateWebcrawler}
											onCreateYouTubeCrawler={handleCreateYouTubeCrawler}
											onManage={handleStartEdit}
											onViewAccountsList={handleViewAccountsList}
											onOpenComposio={handleOpenComposio}
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
