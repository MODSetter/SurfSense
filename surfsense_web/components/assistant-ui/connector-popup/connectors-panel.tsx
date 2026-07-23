"use client";

import { useAtomValue } from "jotai";
import { ChevronRight, LayoutGrid, Search, TriangleAlert, X } from "lucide-react";
import { type ReactNode, useMemo, useState } from "react";
import { activeWorkspaceIdAtom } from "@/atoms/workspaces/workspace-query.atoms";
import { Button } from "@/components/ui/button";
import {
	Drawer,
	DrawerContent,
	DrawerHandle,
	DrawerTitle,
	DrawerTrigger,
} from "@/components/ui/drawer";
import { Input } from "@/components/ui/input";
import { Separator } from "@/components/ui/separator";
import { Spinner } from "@/components/ui/spinner";
import { EnumConnectorName } from "@/contracts/enums/connector";
import { getConnectorIcon } from "@/contracts/enums/connectorIcons";
import type { SearchSourceConnector } from "@/contracts/types/connector.types";
import { useConnectorsSync } from "@/hooks/use-connectors-sync";
import { useZeroDocumentTypeCounts } from "@/hooks/use-zero-document-type-counts";
import { cn } from "@/lib/utils";
import { ConnectorConnectView } from "./connector-configs/views/connector-connect-view";
import { ConnectorEditView } from "./connector-configs/views/connector-edit-view";
import { IndexingConfigurationView } from "./connector-configs/views/indexing-configuration-view";
import {
	COMPOSIO_CONNECTORS,
	getConnectorTitle,
	OAUTH_CONNECTORS,
} from "./constants/connector-constants";
import { type ConnectorRow, useConnectorRows } from "./hooks/use-connector-rows";
import { useConnectorDialog } from "./hooks/use-connector-dialog";
import { AllConnectorsTab } from "./tabs/all-connectors-tab";
import { ConnectorAccountsListView } from "./views/connector-accounts-list-view";
import { YouTubeCrawlerView } from "./views/youtube-crawler-view";

/**
 * Connector management surface (single `/connectors` route) rendered inside the
 * workspace panel. Stateful master–detail:
 *  - sub-rail: Overview + a flat "Your connectors" list (only what's connected,
 *    each with a live status glyph) + an "Add MCP server" action;
 *  - detail pane: the flat catalog (search + cards) OR one of the existing flow
 *    views (connect / edit / indexing / accounts / YouTube), reused verbatim
 *    from the former dialog.
 *
 * Unconnected connectors are one click from the catalog cards, so they never
 * clutter the rail. The hook's internal `isOpen`/`connectorDialogOpenAtom` is
 * inert on a route and ignored.
 */
export function ConnectorsSection() {
	const workspaceId = useAtomValue(activeWorkspaceIdAtom);
	const documentTypeCounts = useZeroDocumentTypeCounts(workspaceId);
	const [drawerOpen, setDrawerOpen] = useState(false);

	const {
		connectingId,
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
		enableVisionLlm,
		allConnectors,
		viewingAccountsType,
		viewingMCPList,
		isYouTubeView,
		isFromOAuth,
		setSearchQuery,
		setStartDate,
		setEndDate,
		setPeriodicEnabled,
		setFrequencyMinutes,
		setEnableVisionLlm,
		handleOpenChange,
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
		handleViewMCPList,
		handleBackFromMCPList,
		handleAddNewMCPFromList,
		handleQuickIndexConnector,
		connectorConfig,
		setConnectorConfig,
		setIndexingConnectorConfig,
		setConnectorName,
	} = useConnectorDialog();

	const {
		connectors: connectorsFromSync = [],
		loading: connectorsLoading,
		error: connectorsError,
		refreshConnectors: refreshConnectorsSync,
	} = useConnectorsSync(workspaceId);

	const useSyncData = connectorsFromSync.length > 0 || (connectorsLoading && !connectorsError);
	const connectors = (useSyncData ? connectorsFromSync : allConnectors || []) as SearchSourceConnector[];

	const refreshConnectors = async () => {
		if (useSyncData) {
			await refreshConnectorsSync();
		}
	};

	// "Your connectors" rows with live indexing health, plus the shared indexing
	// controls the flow views reuse (single source of truth via useConnectorRows).
	const {
		rows: connectedRows,
		indexingConnectorIds,
		startIndexing,
		stopIndexing,
	} = useConnectorRows(connectors);

	const connectedTypes = useMemo(
		() => new Set<string>(connectors.map((c) => c.connector_type)),
		[connectors]
	);

	if (!workspaceId) return null;

	const activeConnectorType = editingConnector
		? editingConnector.connector_type
		: connectingConnectorType ||
			viewingAccountsType?.connectorType ||
			(viewingMCPList ? EnumConnectorName.MCP_CONNECTOR : null);

	const flowView = ((): ReactNode => {
		if (isYouTubeView) {
			return <YouTubeCrawlerView workspaceId={workspaceId} onBack={handleBackFromYouTube} />;
		}
		if (viewingMCPList) {
			return (
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
			);
		}
		if (viewingAccountsType) {
			return (
				<ConnectorAccountsListView
					connectorType={viewingAccountsType.connectorType}
					connectorTitle={viewingAccountsType.connectorTitle}
					connectors={connectors}
					indexingConnectorIds={indexingConnectorIds}
					onBack={handleBackFromAccountsList}
					onManage={handleStartEdit}
					onAddAccount={() => {
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
			);
		}
		if (connectingConnectorType) {
			return (
				<ConnectorConnectView
					connectorType={connectingConnectorType}
					onSubmit={(formData) => handleSubmitConnectForm(formData, startIndexing)}
					onBack={handleBackFromConnect}
					isSubmitting={isCreatingConnector}
				/>
			);
		}
		if (editingConnector) {
			return (
				<ConnectorEditView
					connector={{
						...editingConnector,
						config: connectorConfig || editingConnector.config,
						name: editingConnector.name,
						last_indexed_at:
							connectors.find((c) => c.id === editingConnector.id)?.last_indexed_at ??
							editingConnector.last_indexed_at,
					}}
					startDate={startDate}
					endDate={endDate}
					periodicEnabled={periodicEnabled}
					frequencyMinutes={frequencyMinutes}
					enableVisionLlm={enableVisionLlm}
					isSaving={isSaving}
					isDisconnecting={isDisconnecting}
					isIndexing={indexingConnectorIds.has(editingConnector.id)}
					workspaceId={workspaceId?.toString()}
					onStartDateChange={setStartDate}
					onEndDateChange={setEndDate}
					onPeriodicEnabledChange={setPeriodicEnabled}
					onFrequencyChange={setFrequencyMinutes}
					onEnableVisionLlmChange={setEnableVisionLlm}
					onSave={() => {
						startIndexing(editingConnector.id);
						handleSaveConnector(() => refreshConnectors());
					}}
					onDisconnect={() => handleDisconnectConnector(() => refreshConnectors())}
					onBack={handleBackFromEdit}
					onQuickIndex={(() => {
						const cfg = connectorConfig || editingConnector.config;
						const isDriveOrOneDrive =
							editingConnector.connector_type === "GOOGLE_DRIVE_CONNECTOR" ||
							editingConnector.connector_type === "COMPOSIO_GOOGLE_DRIVE_CONNECTOR" ||
							editingConnector.connector_type === "ONEDRIVE_CONNECTOR" ||
							editingConnector.connector_type === "DROPBOX_CONNECTOR";
						const hasDriveItems = isDriveOrOneDrive
							? ((cfg?.selected_folders as unknown[]) ?? []).length > 0 ||
								((cfg?.selected_files as unknown[]) ?? []).length > 0
							: true;
						if (!hasDriveItems) return undefined;
						return () => {
							startIndexing(editingConnector.id);
							handleQuickIndexConnector(
								editingConnector.id,
								editingConnector.connector_type,
								stopIndexing,
								startDate,
								endDate
							);
						};
					})()}
					onConfigChange={setConnectorConfig}
					onNameChange={setConnectorName}
				/>
			);
		}
		if (indexingConfig) {
			return (
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
					enableVisionLlm={enableVisionLlm}
					isStartingIndexing={isStartingIndexing}
					isFromOAuth={isFromOAuth}
					onStartDateChange={setStartDate}
					onEndDateChange={setEndDate}
					onPeriodicEnabledChange={setPeriodicEnabled}
					onFrequencyChange={setFrequencyMinutes}
					onEnableVisionLlmChange={setEnableVisionLlm}
					onConfigChange={setIndexingConnectorConfig}
					onStartIndexing={() => {
						if (indexingConfig.connectorId) {
							startIndexing(indexingConfig.connectorId);
						}
						handleStartIndexing(() => refreshConnectors());
					}}
					onSkip={handleSkipIndexing}
				/>
			);
		}
		return null;
	})();

	const isFlowActive = flowView !== null;

	const detailTitle =
		isFlowActive && activeConnectorType ? getConnectorTitle(activeConnectorType) : "Overview";

	const hasConnected = connectedRows.length > 0;

	// Rail navigation: clear any open flow first (handleOpenChange(false) is the
	// hook's full reset), then apply the target management action.
	const resetFlow = () => handleOpenChange(false);
	const goOverview = () => {
		setDrawerOpen(false);
		resetFlow();
	};
	const manageRow = (row: ConnectorRow) => {
		setDrawerOpen(false);
		resetFlow();
		if (row.type === EnumConnectorName.MCP_CONNECTOR) {
			handleViewMCPList();
			return;
		}
		if (row.accountCount > 1) {
			handleViewAccountsList(row.type, row.title);
			return;
		}
		handleStartEdit(row.connectors[0]);
	};
	const addMcpServer = () => {
		setDrawerOpen(false);
		resetFlow();
		handleConnectNonOAuth?.(EnumConnectorName.MCP_CONNECTOR);
	};

	const navBtnClass = (active: boolean) =>
		cn(
			"inline-flex w-full items-center justify-start gap-3 rounded-md px-3 py-2.5 text-left text-sm font-medium transition-colors duration-150 focus:outline-none",
			active
				? "bg-accent text-accent-foreground"
				: "text-muted-foreground hover:bg-accent hover:text-accent-foreground"
		);

	const railLabel = (text: string) => (
		<p className="px-3 pb-1 pt-1 text-xs font-semibold text-muted-foreground">{text}</p>
	);

	const renderNav = () => (
		<>
			<button type="button" onClick={goOverview} className={navBtnClass(!isFlowActive)}>
				<LayoutGrid className="h-4 w-4" />
				<span className="min-w-0 truncate">Overview</span>
			</button>

			{hasConnected && (
				<>
					<Separator className="my-3 bg-border" />
					{railLabel("Your connectors")}
					<div className="flex flex-col gap-0.5">
						{connectedRows.map((row) => {
							const isActive = isFlowActive && activeConnectorType === row.type;
							return (
								<button
									key={row.type}
									type="button"
									onClick={() => manageRow(row)}
									className={cn(
										"inline-flex w-full items-center justify-start gap-3 rounded-md px-3 py-2 text-left text-sm transition-colors duration-150 focus:outline-none",
										isActive
											? "bg-accent text-accent-foreground"
											: "text-muted-foreground hover:bg-accent hover:text-accent-foreground"
									)}
								>
									<span className="flex size-4 shrink-0 items-center justify-center">
										{getConnectorIcon(row.type, "size-4")}
									</span>
									<span className="min-w-0 truncate">{row.title}</span>
									{row.health === "syncing" ? (
										<Spinner size="xs" className="ml-auto shrink-0" />
									) : row.health === "failed" ? (
										<TriangleAlert
											className="ml-auto h-3.5 w-3.5 shrink-0 text-destructive"
											aria-label={row.errorMessage ?? "Indexing failed"}
										/>
									) : row.accountCount > 1 ? (
										<span className="ml-auto shrink-0 text-[11px] tabular-nums text-muted-foreground">
											{row.accountCount}
										</span>
									) : null}
								</button>
							);
						})}
					</div>
				</>
			)}

			<Separator className="my-3 bg-border" />
			<button type="button" onClick={addMcpServer} className={navBtnClass(false)}>
				{getConnectorIcon(EnumConnectorName.MCP_CONNECTOR, "h-4 w-4")}
				<span className="min-w-0 truncate">Add MCP server</span>
			</button>
		</>
	);

	const catalog = (
		<div className="flex flex-col gap-8">
			<div className="w-full">
				<div className="relative">
					<Search className="absolute left-3.5 top-1/2 -translate-y-1/2 h-4.5 w-4.5 text-muted-foreground" />
					<Input
						type="text"
						autoComplete="off"
						placeholder="Search connectors"
						className="h-10 border-0 bg-muted pl-10 pr-9 text-base shadow-none"
						value={searchQuery}
						onChange={(e) => setSearchQuery(e.target.value)}
					/>
					{searchQuery && (
						<Button
							variant="ghost"
							size="icon"
							type="button"
							onClick={() => setSearchQuery("")}
							className="absolute right-2 top-1/2 h-7 w-7 -translate-y-1/2 rounded-sm text-muted-foreground transition-colors hover:bg-accent hover:text-accent-foreground"
							aria-label="Clear search"
						>
							<X className="h-4.5 w-4.5" />
						</Button>
					)}
				</div>
			</div>

			<AllConnectorsTab
				searchQuery={searchQuery}
				workspaceId={workspaceId}
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
			/>
		</div>
	);

	return (
		<section className="flex h-full min-h-[min(680px,calc(100vh-5rem))] w-full select-none flex-col gap-6 md:flex-row">
			<div className="md:w-[220px] md:shrink-0">
				<h1 className="mb-4 px-1 text-xl font-semibold tracking-tight text-foreground md:text-2xl">
					Connectors
				</h1>
				<nav className="hidden flex-col gap-0.5 md:flex">{renderNav()}</nav>
				<Drawer open={drawerOpen} onOpenChange={setDrawerOpen} shouldScaleBackground={false}>
					<DrawerTrigger asChild>
						<Button
							type="button"
							variant="outline"
							className="flex h-10 w-full justify-between bg-transparent px-3 hover:bg-accent md:hidden"
						>
							<span className="truncate">{detailTitle}</span>
							<ChevronRight className="h-4 w-4 rotate-90 text-muted-foreground" />
						</Button>
					</DrawerTrigger>
					<DrawerContent className="h-[88vh] overflow-hidden rounded-t-2xl border bg-popover text-popover-foreground">
						<DrawerHandle className="mt-3 h-1.5 w-10" />
						<DrawerTitle className="sr-only">Connectors navigation</DrawerTitle>
						<nav className="flex min-h-0 flex-1 flex-col gap-0.5 overflow-y-auto p-4">
							{renderNav()}
						</nav>
					</DrawerContent>
				</Drawer>
			</div>

			<div className="min-w-0 flex-1">
				<div className="hidden md:block">
					<h2 className="text-lg font-semibold">{detailTitle}</h2>
					<Separator className="mt-4 bg-border" />
				</div>
				<div className="min-w-0 pt-4 md:max-w-5xl">{isFlowActive ? flowView : catalog}</div>
			</div>
		</section>
	);
}
