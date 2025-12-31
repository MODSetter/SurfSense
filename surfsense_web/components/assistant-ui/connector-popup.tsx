"use client";

import { useAtomValue } from "jotai";
import { Cable, Loader2 } from "lucide-react";
import { type FC, useMemo } from "react";
import { documentTypeCountsAtom } from "@/atoms/documents/document-query.atoms";
import { useLogsSummary } from "@/hooks/use-logs";
import { useSearchSourceConnectors } from "@/hooks/use-search-source-connectors";
import { activeSearchSpaceIdAtom } from "@/atoms/search-spaces/search-space-query.atoms";
import {
	Dialog,
	DialogContent,
} from "@/components/ui/dialog";
import {
	Tabs,
	TabsContent,
} from "@/components/ui/tabs";
import { TooltipIconButton } from "@/components/assistant-ui/tooltip-icon-button";
import { cn } from "@/lib/utils";
import { AllConnectorsTab } from "./connector-popup/tabs/all-connectors-tab";
import { ActiveConnectorsTab } from "./connector-popup/tabs/active-connectors-tab";
import { ConnectorDialogHeader } from "./connector-popup/components/connector-dialog-header";
import { ConnectorEditView } from "./connector-popup/connector-configs/views/connector-edit-view";
import { IndexingConfigurationView } from "./connector-popup/connector-configs/views/indexing-configuration-view";
import { useConnectorDialog } from "./connector-popup/hooks/use-connector-dialog";
import type { SearchSourceConnector } from "@/contracts/types/connector.types";

export const ConnectorIndicator: FC = () => {
	const searchSpaceId = useAtomValue(activeSearchSpaceIdAtom);
	const { connectors, isLoading: connectorsLoading, refreshConnectors } = useSearchSourceConnectors(
		false,
		searchSpaceId ? Number(searchSpaceId) : undefined
	);
	const { data: documentTypeCounts, isLoading: documentTypesLoading } =
		useAtomValue(documentTypeCountsAtom);

	// Track active indexing tasks
	const { summary: logsSummary } = useLogsSummary(
		searchSpaceId ? Number(searchSpaceId) : 0,
		24,
		{
			enablePolling: true,
			refetchInterval: 5000,
		}
	);

	// Get connector IDs that are currently being indexed
	const indexingConnectorIds = useMemo(() => {
		if (!logsSummary?.active_tasks) return new Set<number>();
		return new Set(
			logsSummary.active_tasks
				.filter((task) => task.source?.includes("connector_indexing"))
				.map((task) => {
					const match = task.source?.match(/connector[_-]?(\d+)/i);
					return match ? parseInt(match[1], 10) : null;
				})
				.filter((id): id is number => id !== null)
		);
	}, [logsSummary?.active_tasks]);

	const isLoading = connectorsLoading || documentTypesLoading;

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
		startDate,
		endDate,
		isStartingIndexing,
		isSaving,
		isDisconnecting,
		periodicEnabled,
		frequencyMinutes,
		allConnectors,
		setSearchQuery,
		setStartDate,
		setEndDate,
		setPeriodicEnabled,
		setFrequencyMinutes,
		handleOpenChange,
		handleTabChange,
		handleScroll,
		handleConnectOAuth,
		handleCreateWebcrawler,
		handleCreateYouTube,
		handleStartIndexing,
		handleSkipIndexing,
		handleStartEdit,
		handleSaveConnector,
		handleDisconnectConnector,
		handleBackFromEdit,
		connectorConfig,
		setConnectorConfig,
		setIndexingConnectorConfig,
	} = useConnectorDialog();

	// Get document types that have documents in the search space
	const activeDocumentTypes = documentTypeCounts
		? Object.entries(documentTypeCounts).filter(([, count]) => count > 0)
		: [];

	const hasConnectors = connectors.length > 0;
	const hasSources = hasConnectors || activeDocumentTypes.length > 0;
	const totalSourceCount = connectors.length + activeDocumentTypes.length;

	// Check which connectors are already connected
	const connectedTypes = new Set(
		(allConnectors || []).map((c: SearchSourceConnector) => c.connector_type)
	);

	if (!searchSpaceId) return null;

	return (
		<Dialog open={isOpen} onOpenChange={handleOpenChange}>
			<TooltipIconButton
				tooltip={hasSources ? `Manage ${totalSourceCount} sources` : "Connect your data"}
				side="bottom"
				className={cn(
					"size-[34px] rounded-full p-1 flex items-center justify-center transition-colors relative",
					"hover:bg-muted-foreground/15 dark:hover:bg-muted-foreground/30",
					"outline-none focus:outline-none focus-visible:outline-none font-semibold text-xs",
					"border-0 ring-0 focus:ring-0 shadow-none focus:shadow-none"
				)}
				aria-label={
					hasSources ? `View ${totalSourceCount} connected sources` : "Add your first connector"
				}
				onClick={() => handleOpenChange(true)}
			>
				{isLoading ? (
					<Loader2 className="size-4 animate-spin" />
				) : (
					<>
						<Cable className="size-4 stroke-[1.5px]" />
						{totalSourceCount > 0 && (
							<span className="absolute -top-0.5 right-0 flex items-center justify-center min-w-[16px] h-4 px-1 text-[10px] font-medium rounded-full bg-primary text-primary-foreground shadow-sm">
								{totalSourceCount > 99 ? "99+" : totalSourceCount}
							</span>
						)}
					</>
				)}
			</TooltipIconButton>

			<DialogContent className="max-w-3xl w-[95vw] sm:w-full h-[90vh] sm:h-[85vh] flex flex-col p-0 gap-0 overflow-hidden border border-border bg-muted text-foreground [&>button]:right-6 sm:[&>button]:right-12 [&>button]:top-8 sm:[&>button]:top-10 [&>button]:opacity-80 hover:[&>button]:opacity-100 [&>button_svg]:size-5">
				{/* Connector Edit View - shown when editing existing connector */}
				{editingConnector ? (
					<ConnectorEditView
						connector={{
							...editingConnector,
							config: connectorConfig || editingConnector.config,
						}}
						startDate={startDate}
						endDate={endDate}
						periodicEnabled={periodicEnabled}
						frequencyMinutes={frequencyMinutes}
						isSaving={isSaving}
						isDisconnecting={isDisconnecting}
						onStartDateChange={setStartDate}
						onEndDateChange={setEndDate}
						onPeriodicEnabledChange={setPeriodicEnabled}
						onFrequencyChange={setFrequencyMinutes}
						onSave={() => handleSaveConnector(refreshConnectors)}
						onDisconnect={() => handleDisconnectConnector(refreshConnectors)}
						onBack={handleBackFromEdit}
						onConfigChange={setConnectorConfig}
					/>
				) : indexingConfig ? (
					<IndexingConfigurationView
						config={indexingConfig}
						connector={indexingConnector ? {
							...indexingConnector,
							config: indexingConnectorConfig || indexingConnector.config,
						} : undefined}
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
						onStartIndexing={() => handleStartIndexing(refreshConnectors)}
						onSkip={handleSkipIndexing}
					/>
				) : (
					<Tabs value={activeTab} onValueChange={handleTabChange} className="flex-1 flex flex-col min-h-0">
						{/* Header */}
						<ConnectorDialogHeader
							activeTab={activeTab}
							totalSourceCount={totalSourceCount}
							searchQuery={searchQuery}
							onTabChange={handleTabChange}
							onSearchChange={setSearchQuery}
							isScrolled={isScrolled}
						/>

						{/* Content */}
						<div className="flex-1 min-h-0 relative overflow-hidden">
							<div className="h-full overflow-y-auto" onScroll={handleScroll}>
								<div className="px-6 sm:px-12 py-6 sm:py-8 pb-16 sm:pb-16">
									<TabsContent value="all" className="m-0">
										<AllConnectorsTab
											searchQuery={searchQuery}
											searchSpaceId={searchSpaceId}
											connectedTypes={connectedTypes}
											connectingId={connectingId}
											allConnectors={allConnectors}
											onConnectOAuth={handleConnectOAuth}
											onCreateWebcrawler={handleCreateWebcrawler}
											onCreateYouTube={handleCreateYouTube}
											onManage={handleStartEdit}
										/>
									</TabsContent>

									<ActiveConnectorsTab
										hasSources={hasSources}
										totalSourceCount={totalSourceCount}
										activeDocumentTypes={activeDocumentTypes}
										connectors={connectors as SearchSourceConnector[]}
										indexingConnectorIds={indexingConnectorIds}
										logsSummary={logsSummary}
										searchSpaceId={searchSpaceId}
										onTabChange={handleTabChange}
										onManage={handleStartEdit}
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
