"use client";

import { ArrowLeft, Check, Info, Loader2 } from "lucide-react";
import { type FC, useState, useCallback, useRef, useEffect, useMemo } from "react";
import { Button } from "@/components/ui/button";
import type { SearchSourceConnector } from "@/contracts/types/connector.types";
import { cn } from "@/lib/utils";
import type { IndexingConfigState } from "../../constants/connector-constants";
import { DateRangeSelector } from "../../components/date-range-selector";
import { PeriodicSyncConfig } from "../../components/periodic-sync-config";
import { getConnectorConfigComponent } from "../index";

interface IndexingConfigurationViewProps {
	config: IndexingConfigState;
	connector?: SearchSourceConnector;
	startDate: Date | undefined;
	endDate: Date | undefined;
	periodicEnabled: boolean;
	frequencyMinutes: string;
	isStartingIndexing: boolean;
	onStartDateChange: (date: Date | undefined) => void;
	onEndDateChange: (date: Date | undefined) => void;
	onPeriodicEnabledChange: (enabled: boolean) => void;
	onFrequencyChange: (frequency: string) => void;
	onConfigChange?: (config: Record<string, unknown>) => void;
	onStartIndexing: () => void;
	onSkip: () => void;
}

export const IndexingConfigurationView: FC<IndexingConfigurationViewProps> = ({
	config,
	connector,
	startDate,
	endDate,
	periodicEnabled,
	frequencyMinutes,
	isStartingIndexing,
	onStartDateChange,
	onEndDateChange,
	onPeriodicEnabledChange,
	onFrequencyChange,
	onConfigChange,
	onStartIndexing,
	onSkip,
}) => {
	// Get connector-specific config component
	const ConnectorConfigComponent = useMemo(
		() => connector ? getConnectorConfigComponent(connector.connector_type) : null,
		[connector]
	);
	const [isScrolled, setIsScrolled] = useState(false);
	const [hasMoreContent, setHasMoreContent] = useState(false);
	const scrollContainerRef = useRef<HTMLDivElement>(null);

	const checkScrollState = useCallback(() => {
		if (!scrollContainerRef.current) return;
		
		const target = scrollContainerRef.current;
		const scrolled = target.scrollTop > 0;
		const hasMore = target.scrollHeight > target.clientHeight && 
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

	return (
		<div className="flex-1 flex flex-col min-h-0 overflow-hidden">
			{/* Fixed Header */}
			<div className={cn(
				"flex-shrink-0 px-6 sm:px-12 pt-8 sm:pt-10 transition-shadow duration-200 relative z-10",
				isScrolled && "shadow-sm"
			)}>
				{/* Back button */}
				<button
					type="button"
					onClick={onSkip}
					className="flex items-center gap-2 text-xs sm:text-sm text-muted-foreground hover:text-foreground mb-6 w-fit"
				>
					<ArrowLeft className="size-4" />
					Back to connectors
				</button>

				{/* Success header */}
				<div className="flex items-center gap-4 mb-6">
					<div className="flex h-14 w-14 items-center justify-center rounded-xl bg-green-500/10 border border-green-500/20">
						<Check className="size-7 text-green-500" />
					</div>
					<div>
						<h2 className="text-xl sm:text-2xl font-semibold tracking-tight">
							{config.connectorTitle} Connected!
						</h2>
						<p className="text-xs sm:text-base text-muted-foreground mt-1">
							Configure when to start syncing your data
						</p>
					</div>
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
						{ConnectorConfigComponent && connector && (
							<ConnectorConfigComponent
								connector={connector}
								onConfigChange={onConfigChange}
							/>
						)}

						{/* Date range selector and periodic sync - only shown for indexable connectors */}
						{connector?.is_indexable && (
							<>
								{/* Date range selector - not shown for Google Drive (uses folder selection) or Webcrawler (uses config) */}
								{config.connectorType !== "GOOGLE_DRIVE_CONNECTOR" && config.connectorType !== "WEBCRAWLER_CONNECTOR" && (
									<DateRangeSelector
										startDate={startDate}
										endDate={endDate}
										onStartDateChange={onStartDateChange}
										onEndDateChange={onEndDateChange}
									/>
								)}

								<PeriodicSyncConfig
									enabled={periodicEnabled}
									frequencyMinutes={frequencyMinutes}
									onEnabledChange={onPeriodicEnabledChange}
									onFrequencyChange={onFrequencyChange}
								/>
							</>
						)}

						{/* Info box - only shown for indexable connectors */}
						{connector?.is_indexable && (
							<div className="rounded-xl border border-border bg-primary/5 p-4 flex items-start gap-3">
								<div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/10 shrink-0 mt-0.5">
									<Info className="size-4" />
								</div>
								<div className="text-xs sm:text-sm">
									<p className="font-medium text-xs sm:text-sm">Indexing runs in the background</p>
									<p className="text-muted-foreground mt-1 text-[10px] sm:text-sm">
										You can continue using SurfSense while we sync your data. Check the Active tab to see progress.
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
			<div className="flex-shrink-0 flex items-center justify-between px-6 sm:px-12 py-6 bg-muted">
				<Button variant="ghost" onClick={onSkip} disabled={isStartingIndexing} className="text-xs sm:text-sm">
					Skip for now
				</Button>
				<Button onClick={onStartIndexing} disabled={isStartingIndexing} className="text-xs sm:text-sm">
					{isStartingIndexing ? (
						<>
							<Loader2 className="mr-2 h-4 w-4 animate-spin" />
							Starting...
						</>
					) : (
						"Start Indexing"
					)}
				</Button>
			</div>
		</div>
	);
};

