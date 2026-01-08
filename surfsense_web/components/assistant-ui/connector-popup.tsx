"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useAtomValue } from "jotai";
import { Cable, Loader2 } from "lucide-react";
import { useSearchParams } from "next/navigation";
import { type FC, useEffect, useMemo } from "react";
import { documentTypeCountsAtom } from "@/atoms/documents/document-query.atoms";
import { activeSearchSpaceIdAtom } from "@/atoms/search-spaces/search-space-query.atoms";
import { TooltipIconButton } from "@/components/assistant-ui/tooltip-icon-button";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Tabs, TabsContent } from "@/components/ui/tabs";
import type { SearchSourceConnector } from "@/contracts/types/connector.types";
import { useLogsSummary } from "@/hooks/use-logs";
import { connectorsApiService } from "@/lib/apis/connectors-api.service";
import { cacheKeys } from "@/lib/query-client/cache-keys";
import { cn } from "@/lib/utils";
import { ConnectorDialogHeader } from "./connector-popup/components/connector-dialog-header";
import { ConnectorConnectView } from "./connector-popup/connector-configs/views/connector-connect-view";
import { ConnectorEditView } from "./connector-popup/connector-configs/views/connector-edit-view";
import { IndexingConfigurationView } from "./connector-popup/connector-configs/views/indexing-configuration-view";
import { OAUTH_CONNECTORS } from "./connector-popup/constants/connector-constants";
import { useConnectorDialog } from "./connector-popup/hooks/use-connector-dialog";
import { ActiveConnectorsTab } from "./connector-popup/tabs/active-connectors-tab";
import { AllConnectorsTab } from "./connector-popup/tabs/all-connectors-tab";
import { ConnectorAccountsListView } from "./connector-popup/views/connector-accounts-list-view";
import { YouTubeCrawlerView } from "./connector-popup/views/youtube-crawler-view";

export const ConnectorIndicator: FC = () => {
	const searchSpaceId = useAtomValue(activeSearchSpaceIdAtom);
	const searchParams = useSearchParams();
	const { data: documentTypeCounts, isLoading: documentTypesLoading } =
		useAtomValue(documentTypeCountsAtom);

	// Check if YouTube view is active
	const isYouTubeView = searchParams.get("view") === "youtube";

	// Track active indexing tasks
	const { summary: logsSummary } = useLogsSummary(searchSpaceId ? Number(searchSpaceId) : 0, 24, {
		enablePolling: true,
		refetchInterval: 5000,
	});

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
		handleQuickIndexConnector,
		connectorConfig,
		setConnectorConfig,
		setIndexingConnectorConfig,
		setConnectorName,
	} = useConnectorDialog();

	// Fetch connectors using React Query with conditional refetchInterval
	// This automatically refetches when mutations invalidate the cache (event-driven)
	// and also polls when dialog is open to catch external changes
	const {
		data: connectors = [],
		isLoading: connectorsLoading,
		refetch: refreshConnectors,
	} = useQuery({
		queryKey: cacheKeys.connectors.all(searchSpaceId || ""),
		queryFn: () =>
			connectorsApiService.getConnectors({
				queryParams: {
					search_space_id: searchSpaceId ? Number(searchSpaceId) : undefined,
				},
			}),
		enabled: !!searchSpaceId,
		staleTime: 5 * 60 * 1000, // 5 minutes (same as connectorsAtom)
		// Poll when dialog is open to catch external changes
		refetchInterval: isOpen ? 5000 : false, // 5 seconds when open, no polling when closed
	});

	const queryClient = useQueryClient();

	// Also refresh document type counts when dialog is open
	useEffect(() => {
		if (!isOpen || !searchSpaceId) return;

		const POLL_INTERVAL = 5000; // 5 seconds, same as connectors

		const intervalId = setInterval(() => {
			// Invalidate document type counts to refresh active document types
			queryClient.invalidateQueries({
				queryKey: cacheKeys.documents.typeCounts(searchSpaceId),
			});
		}, POLL_INTERVAL);

		// Cleanup interval on unmount or when dialog closes
		return () => {
			clearInterval(intervalId);
		};
	}, [isOpen, searchSpaceId, queryClient]);

	// Get connector IDs that are currently being indexed
	const indexingConnectorIds = useMemo(() => {
		if (!logsSummary?.active_tasks) return new Set<number>();
		return new Set(
			logsSummary.active_tasks
				.filter((task) => task.source?.includes("connector_indexing") && task.connector_id != null)
				.map((task) => task.connector_id as number)
		);
	}, [logsSummary?.active_tasks]);

	const isLoading = connectorsLoading || documentTypesLoading;

	// Get document types that have documents in the search space
	const activeDocumentTypes = documentTypeCounts
		? Object.entries(documentTypeCounts).filter(([, count]) => count > 0)
		: [];

	const hasConnectors = connectors.length > 0;
	const hasSources = hasConnectors || activeDocumentTypes.length > 0;
	const totalSourceCount = connectors.length + activeDocumentTypes.length;
	const activeConnectorsCount = connectors.length; // Only actual connectors, not document types

	// Check which connectors are already connected
	const connectedTypes = new Set(
		(allConnectors || []).map((c: SearchSourceConnector) => c.connector_type)
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
				) : viewingAccountsType ? (
					<ConnectorAccountsListView
						connectorType={viewingAccountsType.connectorType}
						connectorTitle={viewingAccountsType.connectorTitle}
						connectors={(allConnectors || []) as SearchSourceConnector[]}
						indexingConnectorIds={indexingConnectorIds}
						logsSummary={logsSummary}
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
						onSubmit={handleSubmitConnectForm}
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
						onStartDateChange={setStartDate}
						onEndDateChange={setEndDate}
						onPeriodicEnabledChange={setPeriodicEnabled}
						onFrequencyChange={setFrequencyMinutes}
						onSave={() => handleSaveConnector(() => refreshConnectors())}
						onDisconnect={() => handleDisconnectConnector(() => refreshConnectors())}
						onBack={handleBackFromEdit}
						onQuickIndex={
							editingConnector.connector_type !== "GOOGLE_DRIVE_CONNECTOR"
								? () =>
										handleQuickIndexConnector(editingConnector.id, editingConnector.connector_type)
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
						onStartIndexing={() => handleStartIndexing(() => refreshConnectors())}
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
											allConnectors={allConnectors}
											documentTypeCounts={documentTypeCounts}
											indexingConnectorIds={indexingConnectorIds}
											logsSummary={logsSummary}
											onConnectOAuth={handleConnectOAuth}
											onConnectNonOAuth={handleConnectNonOAuth}
											onCreateWebcrawler={handleCreateWebcrawler}
											onCreateYouTubeCrawler={handleCreateYouTubeCrawler}
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
										logsSummary={logsSummary}
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
