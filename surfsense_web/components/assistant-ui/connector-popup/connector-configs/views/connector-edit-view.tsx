"use client";

import { ArrowLeft, Info, RefreshCw, Trash2 } from "lucide-react";
import { type FC, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { getConnectorIcon } from "@/contracts/enums/connectorIcons";
import type { SearchSourceConnector } from "@/contracts/types/connector.types";
import { cn } from "@/lib/utils";
import { DateRangeSelector } from "../../components/date-range-selector";
import { PeriodicSyncConfig } from "../../components/periodic-sync-config";
import { getConnectorDisplayName } from "../../tabs/all-connectors-tab";
import { getConnectorConfigComponent } from "../index";

interface ConnectorEditViewProps {
	connector: SearchSourceConnector;
	startDate: Date | undefined;
	endDate: Date | undefined;
	periodicEnabled: boolean;
	frequencyMinutes: string;
	isSaving: boolean;
	isDisconnecting: boolean;
	isIndexing?: boolean;
	searchSpaceId?: string;
	onStartDateChange: (date: Date | undefined) => void;
	onEndDateChange: (date: Date | undefined) => void;
	onPeriodicEnabledChange: (enabled: boolean) => void;
	onFrequencyChange: (frequency: string) => void;
	onSave: () => void;
	onDisconnect: () => void;
	onBack: () => void;
	onQuickIndex?: () => void;
	onConfigChange?: (config: Record<string, unknown>) => void;
	onNameChange?: (name: string) => void;
}

export const ConnectorEditView: FC<ConnectorEditViewProps> = ({
	connector,
	startDate,
	endDate,
	periodicEnabled,
	frequencyMinutes,
	isSaving,
	isDisconnecting,
	isIndexing = false,
	searchSpaceId,
	onStartDateChange,
	onEndDateChange,
	onPeriodicEnabledChange,
	onFrequencyChange,
	onSave,
	onDisconnect,
	onBack,
	onQuickIndex,
	onConfigChange,
	onNameChange,
}) => {
	// Get connector-specific config component
	const ConnectorConfigComponent = useMemo(
		() => getConnectorConfigComponent(connector.connector_type),
		[connector.connector_type]
	);
	const [isScrolled, setIsScrolled] = useState(false);
	const [hasMoreContent, setHasMoreContent] = useState(false);
	const [showDisconnectConfirm, setShowDisconnectConfirm] = useState(false);
	const [isQuickIndexing, setIsQuickIndexing] = useState(false);
	const scrollContainerRef = useRef<HTMLDivElement>(null);

	const checkScrollState = useCallback(() => {
		if (!scrollContainerRef.current) return;

		const target = scrollContainerRef.current;
		const scrolled = target.scrollTop > 0;
		const hasMore =
			target.scrollHeight > target.clientHeight &&
			target.scrollTop + target.clientHeight < target.scrollHeight - 10;

		setIsScrolled(scrolled);
		setHasMoreContent(hasMore);
	}, []);

	const handleScroll = useCallback(() => {
		checkScrollState();
	}, [checkScrollState]);

	// Check initial scroll state and on resize
	useEffect(() => {
		checkScrollState();
		const resizeObserver = new ResizeObserver(() => {
			checkScrollState();
		});

		if (scrollContainerRef.current) {
			resizeObserver.observe(scrollContainerRef.current);
		}

		return () => {
			resizeObserver.disconnect();
		};
	}, [checkScrollState]);

	// Reset local quick indexing state when indexing completes or fails
	useEffect(() => {
		if (!isIndexing && isQuickIndexing) {
			// Small delay to ensure smooth transition
			const timer = setTimeout(() => {
				setIsQuickIndexing(false);
			}, 100);
			return () => clearTimeout(timer);
		}
	}, [isIndexing, isQuickIndexing]);

	const handleDisconnectClick = () => {
		setShowDisconnectConfirm(true);
	};

	const handleDisconnectConfirm = () => {
		setShowDisconnectConfirm(false);
		onDisconnect();
	};

	const handleDisconnectCancel = () => {
		setShowDisconnectConfirm(false);
	};

	const handleQuickIndex = useCallback(() => {
		if (onQuickIndex && !isQuickIndexing && !isIndexing) {
			setIsQuickIndexing(true);
			onQuickIndex();
		}
	}, [onQuickIndex, isQuickIndexing, isIndexing]);

	return (
		<div className="flex-1 flex flex-col min-h-0 overflow-hidden">
			{/* Fixed Header */}
			<div
				className={cn(
					"flex-shrink-0 px-6 sm:px-12 pt-8 sm:pt-10 transition-shadow duration-200 relative z-10",
					isScrolled && "shadow-sm"
				)}
			>
				{/* Back button */}
				<button
					type="button"
					onClick={onBack}
					className="flex items-center gap-2 text-xs sm:text-sm text-muted-foreground hover:text-foreground mb-6 w-fit"
				>
					<ArrowLeft className="size-4" />
					Back to connectors
				</button>

				{/* Connector header */}
				<div className="flex flex-col sm:flex-row items-start sm:items-center gap-4 mb-6">
					<div className="flex gap-4 flex-1 w-full sm:w-auto">
						<div className="flex h-14 w-14 items-center justify-center rounded-xl bg-primary/10 border border-primary/20 shrink-0">
							{getConnectorIcon(connector.connector_type, "size-7")}
						</div>
						<div className="flex-1 min-w-0">
							<h2 className="text-xl sm:text-2xl font-semibold tracking-tight text-wrap whitespace-normal wrap-break-word">
								{getConnectorDisplayName(connector.name)}
							</h2>
							<p className="text-xs sm:text-base text-muted-foreground mt-1">
								Manage your connector settings and sync configuration
							</p>
						</div>
					</div>
					{/* Quick Index Button - only show for indexable connectors, but not for Google Drive (requires folder selection) */}
					{connector.is_indexable &&
						onQuickIndex &&
						connector.connector_type !== "GOOGLE_DRIVE_CONNECTOR" && (
							<Button
								variant="secondary"
								size="sm"
								onClick={handleQuickIndex}
								disabled={isQuickIndexing || isIndexing || isSaving || isDisconnecting}
								className="text-xs sm:text-sm bg-slate-400/10 dark:bg-white/10 hover:bg-slate-400/20 dark:hover:bg-white/20 border-slate-400/20 dark:border-white/20 w-full sm:w-auto"
							>
								{isQuickIndexing || isIndexing ? (
									<>
										<RefreshCw className="mr-2 h-4 w-4 animate-spin" />
										Syncing
									</>
								) : (
									<>
										<RefreshCw className="mr-2 h-4 w-4" />
										Quick Index
									</>
								)}
							</Button>
						)}
				</div>
			</div>

			{/* Scrollable Content */}
			<div className="flex-1 min-h-0 relative overflow-hidden">
				<div
					ref={scrollContainerRef}
					className="h-full overflow-y-auto px-6 sm:px-12"
					onScroll={handleScroll}
				>
					<div className="space-y-6 pb-6 pt-2">
						{/* Connector-specific configuration */}
						{ConnectorConfigComponent && (
							<ConnectorConfigComponent
								connector={connector}
								onConfigChange={onConfigChange}
								onNameChange={onNameChange}
								searchSpaceId={searchSpaceId}
							/>
						)}

						{/* Date range selector and periodic sync - only shown for indexable connectors */}
						{connector.is_indexable && (
							<>
								{/* Date range selector - not shown for Google Drive (regular and Composio), Webcrawler, or GitHub (indexes full repo snapshots) */}
								{connector.connector_type !== "GOOGLE_DRIVE_CONNECTOR" &&
									connector.connector_type !== "COMPOSIO_GOOGLE_DRIVE_CONNECTOR" &&
									connector.connector_type !== "WEBCRAWLER_CONNECTOR" &&
									connector.connector_type !== "GITHUB_CONNECTOR" && (
										<DateRangeSelector
											startDate={startDate}
											endDate={endDate}
											onStartDateChange={onStartDateChange}
											onEndDateChange={onEndDateChange}
											allowFutureDates={
												connector.connector_type === "GOOGLE_CALENDAR_CONNECTOR" ||
												connector.connector_type === "COMPOSIO_GOOGLE_CALENDAR_CONNECTOR" ||
												connector.connector_type === "LUMA_CONNECTOR"
											}
											lastIndexedAt={connector.last_indexed_at}
										/>
									)}

								{/* Periodic sync - shown for all indexable connectors */}
								{(() => {
									// Check if Google Drive (regular or Composio) has folders/files selected
									const isGoogleDrive = connector.connector_type === "GOOGLE_DRIVE_CONNECTOR";
									const isComposioGoogleDrive =
										connector.connector_type === "COMPOSIO_GOOGLE_DRIVE_CONNECTOR";
									const requiresFolderSelection = isGoogleDrive || isComposioGoogleDrive;
									const selectedFolders =
										(connector.config?.selected_folders as
											| Array<{ id: string; name: string }>
											| undefined) || [];
									const selectedFiles =
										(connector.config?.selected_files as
											| Array<{ id: string; name: string }>
											| undefined) || [];
									const hasItemsSelected = selectedFolders.length > 0 || selectedFiles.length > 0;
									const isDisabled = requiresFolderSelection && !hasItemsSelected;

									return (
										<PeriodicSyncConfig
											enabled={periodicEnabled}
											frequencyMinutes={frequencyMinutes}
											onEnabledChange={onPeriodicEnabledChange}
											onFrequencyChange={onFrequencyChange}
											disabled={isDisabled}
											disabledMessage={
												isDisabled
													? "Select at least one folder or file above to enable periodic sync"
													: undefined
											}
										/>
									);
								})()}
							</>
						)}

						{/* Info box - only shown for indexable connectors */}
						{connector.is_indexable && (
							<div className="rounded-xl border border-border bg-primary/5 p-4 flex items-start gap-3">
								<div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/10 shrink-0 mt-0.5">
									<Info className="size-4" />
								</div>
								<div className="text-xs sm:text-sm">
									<p className="font-medium text-xs sm:text-sm">
										Re-indexing runs in the background
									</p>
									<p className="text-muted-foreground mt-1 text-[10px] sm:text-sm">
										You can continue using SurfSense while we sync your data. Check inbox for
										updates.
									</p>
								</div>
							</div>
						)}
					</div>
				</div>
				{/* Top fade shadow - appears when scrolled */}
				{isScrolled && (
					<div className="absolute top-0 left-0 right-0 h-6 bg-gradient-to-b from-muted/50 to-transparent pointer-events-none z-10" />
				)}
				{/* Bottom fade shadow - appears when there's more content */}
				{hasMoreContent && (
					<div className="absolute bottom-0 left-0 right-0 h-3 bg-gradient-to-t from-muted/50 to-transparent pointer-events-none z-10" />
				)}
			</div>

			{/* Fixed Footer - Action buttons */}
			<div className="flex-shrink-0 flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 sm:gap-0 px-6 sm:px-12 py-6 sm:py-6 bg-muted border-t border-border">
				{showDisconnectConfirm ? (
					<div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3 flex-1 sm:flex-initial">
						<span className="text-xs sm:text-sm text-muted-foreground sm:whitespace-nowrap">
							Are you sure?
						</span>
						<div className="flex items-center gap-2 sm:gap-3">
							<Button
								variant="destructive"
								size="sm"
								onClick={handleDisconnectConfirm}
								disabled={isDisconnecting}
								className="text-xs sm:text-sm flex-1 sm:flex-initial h-10 sm:h-auto py-2 sm:py-2"
							>
								{isDisconnecting ? (
									<>
										<Spinner size="sm" className="mr-2" />
										Disconnecting
									</>
								) : (
									"Confirm Disconnect"
								)}
							</Button>
							<Button
								variant="ghost"
								size="sm"
								onClick={handleDisconnectCancel}
								disabled={isDisconnecting}
								className="text-xs sm:text-sm flex-1 sm:flex-initial h-10 sm:h-auto py-2 sm:py-2"
							>
								Cancel
							</Button>
						</div>
					</div>
				) : (
					<Button
						variant="destructive"
						onClick={handleDisconnectClick}
						disabled={isSaving || isDisconnecting}
						className="text-xs sm:text-sm flex-1 sm:flex-initial h-12 sm:h-auto py-3 sm:py-2"
					>
						<Trash2 className="mr-2 h-4 w-4" />
						Disconnect
					</Button>
				)}
				<Button
					onClick={onSave}
					disabled={isSaving || isDisconnecting}
					className="text-xs sm:text-sm flex-1 sm:flex-initial h-12 sm:h-auto py-3 sm:py-2"
				>
					{isSaving ? (
						<>
							<Spinner size="sm" className="mr-2" />
							Saving
						</>
					) : (
						"Save Changes"
					)}
				</Button>
			</div>
		</div>
	);
};
