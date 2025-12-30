"use client";

import { format, subDays, subYears } from "date-fns";
import { useAtomValue } from "jotai";
import {
	ArrowLeft,
	Cable,
	Calendar as CalendarIcon,
	Check,
	ChevronRight,
	Loader2,
	Search,
} from "lucide-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { type FC, useCallback, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { getDocumentTypeLabel } from "@/app/dashboard/[search_space_id]/documents/(manage)/components/DocumentTypeIcon";
import { indexConnectorMutationAtom, updateConnectorMutationAtom } from "@/atoms/connectors/connector-mutation.atoms";
import { connectorsAtom } from "@/atoms/connectors/connector-query.atoms";
import { documentTypeCountsAtom } from "@/atoms/documents/document-query.atoms";
import { activeSearchSpaceIdAtom } from "@/atoms/search-spaces/search-space-query.atoms";
import {
	Dialog,
	DialogContent,
	DialogDescription,
	DialogHeader,
	DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Calendar } from "@/components/ui/calendar";
import { Label } from "@/components/ui/label";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Switch } from "@/components/ui/switch";
import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";
import { EnumConnectorName } from "@/contracts/enums/connector";
import { getConnectorIcon } from "@/contracts/enums/connectorIcons";
import type { SearchSourceConnector } from "@/contracts/types/connector.types";
import { useLogsSummary } from "@/hooks/use-logs";
import { useSearchSourceConnectors } from "@/hooks/use-search-source-connectors";
import { authenticatedFetch } from "@/lib/auth-utils";
import { queryClient } from "@/lib/query-client/client";
import { cacheKeys } from "@/lib/query-client/cache-keys";
import { TooltipIconButton } from "@/components/assistant-ui/tooltip-icon-button";
import { cn } from "@/lib/utils";

// Type for the indexing configuration state
interface IndexingConfigState {
	connectorType: string;
	connectorId: number;
	connectorTitle: string;
}

// OAuth Connectors (Quick Connect)
const OAUTH_CONNECTORS = [
	{
		id: "google-gmail-connector",
		title: "Gmail",
		description: "Search through your emails",
		connectorType: EnumConnectorName.GOOGLE_GMAIL_CONNECTOR,
		authEndpoint: "/api/v1/auth/google/gmail/connector/add/",
	},
	{
		id: "google-calendar-connector",
		title: "Google Calendar",
		description: "Search through your events",
		connectorType: EnumConnectorName.GOOGLE_CALENDAR_CONNECTOR,
		authEndpoint: "/api/v1/auth/google/calendar/connector/add/",
	},
	{
		id: "airtable-connector",
		title: "Airtable",
		description: "Search your Airtable bases",
		connectorType: EnumConnectorName.AIRTABLE_CONNECTOR,
		authEndpoint: "/api/v1/auth/airtable/connector/add/",
	},
];

// Non-OAuth Connectors
const OTHER_CONNECTORS = [
	{
		id: "slack-connector",
		title: "Slack",
		description: "Search Slack messages",
		connectorType: EnumConnectorName.SLACK_CONNECTOR,
	},
	{
		id: "discord-connector",
		title: "Discord",
		description: "Search Discord messages",
		connectorType: EnumConnectorName.DISCORD_CONNECTOR,
	},
	{
		id: "notion-connector",
		title: "Notion",
		description: "Search Notion pages",
		connectorType: EnumConnectorName.NOTION_CONNECTOR,
	},
	{
		id: "confluence-connector",
		title: "Confluence",
		description: "Search documentation",
		connectorType: EnumConnectorName.CONFLUENCE_CONNECTOR,
	},
	{
		id: "bookstack-connector",
		title: "BookStack",
		description: "Search BookStack docs",
		connectorType: EnumConnectorName.BOOKSTACK_CONNECTOR,
	},
	{
		id: "github-connector",
		title: "GitHub",
		description: "Search repositories",
		connectorType: EnumConnectorName.GITHUB_CONNECTOR,
	},
	{
		id: "linear-connector",
		title: "Linear",
		description: "Search issues & projects",
		connectorType: EnumConnectorName.LINEAR_CONNECTOR,
	},
	{
		id: "jira-connector",
		title: "Jira",
		description: "Search Jira issues",
		connectorType: EnumConnectorName.JIRA_CONNECTOR,
	},
	{
		id: "clickup-connector",
		title: "ClickUp",
		description: "Search ClickUp tasks",
		connectorType: EnumConnectorName.CLICKUP_CONNECTOR,
	},
	{
		id: "luma-connector",
		title: "Luma",
		description: "Search Luma events",
		connectorType: EnumConnectorName.LUMA_CONNECTOR,
	},
	{
		id: "elasticsearch-connector",
		title: "Elasticsearch",
		description: "Search ES indexes",
		connectorType: EnumConnectorName.ELASTICSEARCH_CONNECTOR,
	},
	{
		id: "webcrawler-connector",
		title: "Web Pages",
		description: "Crawl web content",
		connectorType: EnumConnectorName.WEBCRAWLER_CONNECTOR,
	},
	{
		id: "tavily-api",
		title: "Tavily AI",
		description: "Search with Tavily",
		connectorType: EnumConnectorName.TAVILY_API,
	},
	{
		id: "searxng",
		title: "SearxNG",
		description: "Search with SearxNG",
		connectorType: EnumConnectorName.SEARXNG_API,
	},
	{
		id: "linkup-api",
		title: "Linkup API",
		description: "Search with Linkup",
		connectorType: EnumConnectorName.LINKUP_API,
	},
	{
		id: "baidu-search-api",
		title: "Baidu Search",
		description: "Search with Baidu",
		connectorType: EnumConnectorName.BAIDU_SEARCH_API,
	},
];

import {
	Tabs,
	TabsContent,
	TabsList,
	TabsTrigger,
} from "@/components/ui/tabs";

export const ConnectorIndicator: FC = () => {
	const router = useRouter();
	const searchParams = useSearchParams();
	const searchSpaceId = useAtomValue(activeSearchSpaceIdAtom);
	const { connectors, isLoading: connectorsLoading, refreshConnectors } = useSearchSourceConnectors(
		false,
		searchSpaceId ? Number(searchSpaceId) : undefined
	);
	const { data: documentTypeCounts, isLoading: documentTypesLoading } =
		useAtomValue(documentTypeCountsAtom);
	const { data: allConnectors, refetch: refetchAllConnectors } = useAtomValue(connectorsAtom);
	const { mutateAsync: indexConnector } = useAtomValue(indexConnectorMutationAtom);
	const { mutateAsync: updateConnector } = useAtomValue(updateConnectorMutationAtom);
	const [isOpen, setIsOpen] = useState(false);
	const [activeTab, setActiveTab] = useState("all");
	const [connectingId, setConnectingId] = useState<string | null>(null);
	const [isScrolled, setIsScrolled] = useState(false);
	const [searchQuery, setSearchQuery] = useState("");
	
	// Indexing configuration state (shown after OAuth success)
	const [indexingConfig, setIndexingConfig] = useState<IndexingConfigState | null>(null);
	const [startDate, setStartDate] = useState<Date | undefined>(undefined);
	const [endDate, setEndDate] = useState<Date | undefined>(undefined);
	const [isStartingIndexing, setIsStartingIndexing] = useState(false);
	
	// Periodic indexing state
	const [periodicEnabled, setPeriodicEnabled] = useState(false);
	const [frequencyMinutes, setFrequencyMinutes] = useState("1440"); // Default: daily

	// Helper function to get frequency label
	const getFrequencyLabel = useCallback((minutes: string): string => {
		switch (minutes) {
			case "15": return "15 minutes";
			case "60": return "hour";
			case "360": return "6 hours";
			case "720": return "12 hours";
			case "1440": return "day";
			case "10080": return "week";
			default: return `${minutes} minutes`;
		}
	}, []);

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
					// Extract connector ID from task metadata or source
					const match = task.source?.match(/connector[_-]?(\d+)/i);
					return match ? parseInt(match[1], 10) : null;
				})
				.filter((id): id is number => id !== null)
		);
	}, [logsSummary?.active_tasks]);

	const isLoading = connectorsLoading || documentTypesLoading;

	// Synchronize state with URL query params
	useEffect(() => {
		const modalParam = searchParams.get("modal");
		const tabParam = searchParams.get("tab");
		const viewParam = searchParams.get("view");
		const connectorParam = searchParams.get("connector");
		
		if (modalParam === "connectors") {
			if (!isOpen) setIsOpen(true);
			
			// Detect tab from URL query param
			if (tabParam === "active" || tabParam === "all") {
				if (activeTab !== tabParam) setActiveTab(tabParam);
			}
			
			// Restore indexing config view from URL if present (e.g., on page refresh)
			if (viewParam === "configure" && connectorParam && !indexingConfig) {
				const oauthConnector = OAUTH_CONNECTORS.find(c => c.id === connectorParam);
				if (oauthConnector && allConnectors) {
					const existingConnector = allConnectors.find(
						(c: SearchSourceConnector) => c.connector_type === oauthConnector.connectorType
					);
					if (existingConnector) {
						setIndexingConfig({
							connectorType: oauthConnector.connectorType,
							connectorId: existingConnector.id,
							connectorTitle: oauthConnector.title,
						});
					}
				}
			}
		} else {
			if (isOpen) setIsOpen(false);
		}
	}, [searchParams, isOpen, activeTab, indexingConfig, allConnectors]);

	// Detect OAuth success and transition to config view
	useEffect(() => {
		const success = searchParams.get("success");
		const connectorParam = searchParams.get("connector");
		const modalParam = searchParams.get("modal");
		
		if (success === "true" && connectorParam && searchSpaceId && modalParam === "connectors") {
			// Find the OAuth connector info
			const oauthConnector = OAUTH_CONNECTORS.find(c => c.id === connectorParam);
			if (oauthConnector) {
				// Refetch connectors to get the newly created connector
				refetchAllConnectors().then((result) => {
					const newConnector = result.data?.find(
						(c: SearchSourceConnector) => c.connector_type === oauthConnector.connectorType
					);
					if (newConnector) {
						setIndexingConfig({
							connectorType: oauthConnector.connectorType,
							connectorId: newConnector.id,
							connectorTitle: oauthConnector.title,
						});
						setIsOpen(true);
						// Update URL to reflect config view (replace success with view=configure)
						const url = new URL(window.location.href);
						url.searchParams.delete("success");
						url.searchParams.set("view", "configure");
						// Keep connector param for URL restoration
						window.history.replaceState({}, "", url.toString());
					}
				});
			}
		}
	}, [searchParams, searchSpaceId, refetchAllConnectors]);

	// Handle starting indexing
	const handleStartIndexing = useCallback(async () => {
		if (!indexingConfig || !searchSpaceId) return;

		setIsStartingIndexing(true);
		try {
			const startDateStr = startDate ? format(startDate, "yyyy-MM-dd") : undefined;
			const endDateStr = endDate ? format(endDate, "yyyy-MM-dd") : undefined;

			// Update periodic indexing settings if enabled
			if (periodicEnabled) {
				const frequency = parseInt(frequencyMinutes, 10);
				await updateConnector({
					id: indexingConfig.connectorId,
					data: {
						periodic_indexing_enabled: true,
						indexing_frequency_minutes: frequency,
					},
				});
			}

			await indexConnector({
				connector_id: indexingConfig.connectorId,
				queryParams: {
					search_space_id: searchSpaceId,
					start_date: startDateStr,
					end_date: endDateStr,
				},
			});

			toast.success(`${indexingConfig.connectorTitle} indexing started`, {
				description: periodicEnabled 
					? `Periodic sync enabled every ${getFrequencyLabel(frequencyMinutes)}.`
					: "You can continue working while we sync your data.",
			});

			// Close the config view and reset state
			setIndexingConfig(null);
			setStartDate(undefined);
			setEndDate(undefined);
			setPeriodicEnabled(false);
			setFrequencyMinutes("1440");
			
			// Clear config-related URL params and switch to active tab
			const url = new URL(window.location.href);
			url.searchParams.delete("view");
			url.searchParams.delete("connector");
			url.searchParams.set("tab", "active");
			window.history.replaceState({}, "", url.toString());
			setActiveTab("active");
			
			// Refresh connectors list
			refreshConnectors();
			queryClient.invalidateQueries({
				queryKey: cacheKeys.logs.summary(Number(searchSpaceId)),
			});
		} catch (error) {
			console.error("Error starting indexing:", error);
			toast.error("Failed to start indexing");
		} finally {
			setIsStartingIndexing(false);
		}
	}, [indexingConfig, searchSpaceId, startDate, endDate, indexConnector, updateConnector, periodicEnabled, frequencyMinutes, refreshConnectors, getFrequencyLabel]);

	// Handle skipping indexing for now
	const handleSkipIndexing = useCallback(() => {
		setIndexingConfig(null);
		setStartDate(undefined);
		setEndDate(undefined);
		setPeriodicEnabled(false);
		setFrequencyMinutes("1440");
		
		// Clear config-related URL params
		const url = new URL(window.location.href);
		url.searchParams.delete("view");
		url.searchParams.delete("connector");
		window.history.replaceState({}, "", url.toString());
	}, []);

	// Quick date range handlers
	const handleLast30Days = useCallback(() => {
		const today = new Date();
		setStartDate(subDays(today, 30));
		setEndDate(today);
	}, []);

	const handleLastYear = useCallback(() => {
		const today = new Date();
		setStartDate(subYears(today, 1));
		setEndDate(today);
	}, []);

	const handleClearDates = useCallback(() => {
		setStartDate(undefined);
		setEndDate(undefined);
	}, []);

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

	// Filter connectors based on search
	const filteredOAuth = OAUTH_CONNECTORS.filter(c => 
		c.title.toLowerCase().includes(searchQuery.toLowerCase()) || 
		c.description.toLowerCase().includes(searchQuery.toLowerCase())
	);

	const filteredOther = OTHER_CONNECTORS.filter(c => 
		c.title.toLowerCase().includes(searchQuery.toLowerCase()) || 
		c.description.toLowerCase().includes(searchQuery.toLowerCase())
	);

	// Handle OAuth connection
	const handleConnectOAuth = useCallback(
		async (connector: (typeof OAUTH_CONNECTORS)[0]) => {
			if (!searchSpaceId || !connector.authEndpoint) return;

			try {
				setConnectingId(connector.id);
				const response = await authenticatedFetch(
					`${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}${connector.authEndpoint}?space_id=${searchSpaceId}`,
					{ method: "GET" }
				);

				if (!response.ok) {
					throw new Error(`Failed to initiate ${connector.title} OAuth`);
				}

				const data = await response.json();
				window.location.href = data.auth_url;
			} catch (error) {
				console.error(`Error connecting to ${connector.title}:`, error);
				toast.error(`Failed to connect to ${connector.title}`);
			} finally {
				setConnectingId(null);
			}
		},
		[searchSpaceId]
	);

	const handleOpenChange = useCallback(
		(open: boolean) => {
			setIsOpen(open);

			if (open) {
				// Add modal query params to current URL
				const url = new URL(window.location.href);
				url.searchParams.set("modal", "connectors");
				url.searchParams.set("tab", activeTab);
				window.history.pushState({ modal: true }, "", url.toString());
			} else {
				// Remove modal query params from URL
				const url = new URL(window.location.href);
				url.searchParams.delete("modal");
				url.searchParams.delete("tab");
				url.searchParams.delete("success");
				url.searchParams.delete("connector");
				url.searchParams.delete("view");
				window.history.pushState({ modal: false }, "", url.toString());
				setIsScrolled(false);
				setSearchQuery("");
				// Reset indexing config when closing
				if (!isStartingIndexing) {
					setIndexingConfig(null);
					setStartDate(undefined);
					setEndDate(undefined);
					setPeriodicEnabled(false);
					setFrequencyMinutes("1440");
				}
			}
		},
		[activeTab, isStartingIndexing]
	);

	const handleTabChange = useCallback(
		(value: string) => {
			setActiveTab(value);
			// Update tab query param
			const url = new URL(window.location.href);
			url.searchParams.set("tab", value);
			window.history.replaceState({ modal: true }, "", url.toString());
		},
		[]
	);

	const handleScroll = useCallback((e: React.UIEvent<HTMLDivElement>) => {
		setIsScrolled(e.currentTarget.scrollTop > 0);
	}, []);

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
			{/* Indexing Configuration View - shown after OAuth success */}
			{indexingConfig ? (
				<div className="flex-1 flex flex-col min-h-0 overflow-hidden">
					{/* Fixed Header */}
					<div className="flex-shrink-0 px-6 sm:px-12 pt-8 sm:pt-10">
						{/* Back button */}
						<button
							type="button"
							onClick={handleSkipIndexing}
							className="flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground mb-6 w-fit"
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
								<h2 className="text-2xl font-semibold tracking-tight">
									{indexingConfig.connectorTitle} Connected!
								</h2>
								<p className="text-muted-foreground mt-1">
									Configure when to start syncing your data
								</p>
							</div>
						</div>
					</div>

					{/* Scrollable Content */}
					<div className="flex-1 min-h-0 overflow-y-auto px-6 sm:px-12">
						<div className="space-y-6 pb-6">
						<div className="rounded-xl border border-border bg-slate-400/5 dark:bg-white/5 p-6">
							<h3 className="font-medium mb-4">Select Date Range</h3>
							<p className="text-sm text-muted-foreground mb-6">
								Choose how far back you want to sync your data. You can always re-index later with different dates.
							</p>

							<div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
								{/* Start Date */}
								<div className="space-y-2">
									<Label htmlFor="start-date">Start Date</Label>
									<Popover>
										<PopoverTrigger asChild>
											<Button
												id="start-date"
												variant="outline"
												className={cn(
													"w-full justify-start text-left font-normal bg-slate-400/5 dark:bg-slate-400/5 border-slate-400/20",
													!startDate && "text-muted-foreground"
												)}
											>
												<CalendarIcon className="mr-2 h-4 w-4" />
												{startDate ? format(startDate, "PPP") : "Default (1 year ago)"}
											</Button>
										</PopoverTrigger>
										<PopoverContent className="w-auto p-0 z-[100]" align="start">
											<Calendar
												mode="single"
												selected={startDate}
												onSelect={setStartDate}
												disabled={(date) => date > new Date()}
											/>
										</PopoverContent>
									</Popover>
								</div>

								{/* End Date */}
								<div className="space-y-2">
									<Label htmlFor="end-date">End Date</Label>
									<Popover>
										<PopoverTrigger asChild>
											<Button
												id="end-date"
												variant="outline"
												className={cn(
													"w-full justify-start text-left font-normal bg-slate-400/5 dark:bg-slate-400/5 border-slate-400/20",
													!endDate && "text-muted-foreground"
												)}
											>
												<CalendarIcon className="mr-2 h-4 w-4" />
												{endDate ? format(endDate, "PPP") : "Default (Today)"}
											</Button>
										</PopoverTrigger>
										<PopoverContent className="w-auto p-0 z-[100]" align="start">
											<Calendar
												mode="single"
												selected={endDate}
												onSelect={setEndDate}
												disabled={(date) => date > new Date() || (startDate ? date < startDate : false)}
											/>
										</PopoverContent>
									</Popover>
								</div>
							</div>

							{/* Quick date range buttons */}
							<div className="flex flex-wrap gap-2 mt-4">
								<Button
									type="button"
									variant="outline"
									size="sm"
									onClick={handleClearDates}
									className="text-xs bg-slate-400/5 dark:bg-slate-400/5 border-slate-400/20 hover:bg-slate-400/10 dark:hover:bg-slate-400/10"
								>
									Clear Dates
								</Button>
								<Button
									type="button"
									variant="outline"
									size="sm"
									onClick={handleLast30Days}
									className="text-xs bg-slate-400/5 dark:bg-slate-400/5 border-slate-400/20 hover:bg-slate-400/10 dark:hover:bg-slate-400/10"
								>
									Last 30 Days
								</Button>
								<Button
									type="button"
									variant="outline"
									size="sm"
									onClick={handleLastYear}
									className="text-xs bg-slate-400/5 dark:bg-slate-400/5 border-slate-400/20 hover:bg-slate-400/10 dark:hover:bg-slate-400/10"
								>
									Last Year
								</Button>
							</div>
						</div>

						{/* Periodic Indexing Configuration */}
						<div className="rounded-xl border border-border bg-slate-400/5 dark:bg-white/5 p-6">
							<div className="flex items-center justify-between">
								<div className="space-y-1">
									<h3 className="font-medium">Enable Periodic Sync</h3>
									<p className="text-sm text-muted-foreground">
										Automatically re-index at regular intervals
									</p>
								</div>
								<Switch
									checked={periodicEnabled}
									onCheckedChange={setPeriodicEnabled}
								/>
							</div>

							{periodicEnabled && (
								<div className="mt-4 pt-4 border-t border-border/100 space-y-3">
									<div className="space-y-2">
										<Label htmlFor="frequency">Sync Frequency</Label>
										<Select value={frequencyMinutes} onValueChange={setFrequencyMinutes}>
											<SelectTrigger id="frequency" className="w-full bg-slate-400/5 dark:bg-slate-400/5 border-slate-400/20">
												<SelectValue placeholder="Select frequency" />
											</SelectTrigger>
											<SelectContent className="z-[100]">
												<SelectItem value="15">Every 15 minutes</SelectItem>
												<SelectItem value="60">Every hour</SelectItem>
												<SelectItem value="360">Every 6 hours</SelectItem>
												<SelectItem value="720">Every 12 hours</SelectItem>
												<SelectItem value="1440">Daily</SelectItem>
												<SelectItem value="10080">Weekly</SelectItem>
											</SelectContent>
										</Select>
									</div>
								</div>
							)}
						</div>

						{/* Info box */}
						<div className="rounded-xl border border-border bg-primary/5 p-4 flex items-start gap-3">
							<div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/10 shrink-0 mt-0.5">
								{getConnectorIcon(indexingConfig.connectorType, "size-4")}
							</div>
							<div className="text-sm">
								<p className="font-medium">Indexing runs in the background</p>
								<p className="text-muted-foreground mt-1">
									You can continue using SurfSense while we sync your data. Check the Active tab to see progress.
								</p>
							</div>
						</div>
						</div>
					</div>

					{/* Fixed Footer - Action buttons */}
					<div className="flex-shrink-0 flex items-center justify-between px-6 sm:px-12 py-6 border-t border-border bg-muted">
						<Button
							variant="ghost"
							onClick={handleSkipIndexing}
							disabled={isStartingIndexing}
						>
							Skip for now
						</Button>
						<Button
							onClick={handleStartIndexing}
							disabled={isStartingIndexing}
						>
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
			) : (
			<Tabs value={activeTab} onValueChange={handleTabChange} className="flex-1 flex flex-col min-h-0">
					{/* Header */}
					<div
						className={cn(
							"flex-shrink-0 px-6 sm:px-12 pt-8 sm:pt-10 transition-shadow duration-200 relative z-10",
							isScrolled && "shadow-xl bg-muted/50 backdrop-blur-md"
						)}
					>
						<DialogHeader>
							<DialogTitle className="text-2xl sm:text-3xl font-semibold tracking-tight">Connectors</DialogTitle>
							<DialogDescription className="text-sm sm:text-base text-muted-foreground/80 mt-1 sm:mt-1.5">
								Search across all your apps and data in one place.
							</DialogDescription>
						</DialogHeader>

						<div className="flex flex-col-reverse sm:flex-row sm:items-end justify-between gap-6 sm:gap-8 mt-6 sm:mt-8 border-b border-slate-400/5 dark:border-white/5">
							<TabsList className="bg-transparent p-0 gap-4 sm:gap-8 h-auto w-full sm:w-auto justify-center sm:justify-start">
								<TabsTrigger 
									value="all" 
									className="px-0 pb-3 bg-transparent data-[state=active]:bg-transparent shadow-none data-[state=active]:shadow-none rounded-none border-b-[1.5px] border-transparent data-[state=active]:border-foreground dark:data-[state=active]:border-white transition-all text-base font-medium text-muted-foreground data-[state=active]:text-foreground"
								>
									All Connectors
								</TabsTrigger>
								<TabsTrigger 
									value="active" 
									className="group px-0 pb-3 bg-transparent data-[state=active]:bg-transparent shadow-none data-[state=active]:shadow-none rounded-none border-b-[1.5px] border-transparent transition-all text-base font-medium flex items-center gap-2 text-muted-foreground data-[state=active]:text-foreground relative"
								>
									<span className="relative">
										Active
										<span className="absolute bottom-[-13.5px] left-1/2 -translate-x-1/2 w-12 h-[1.5px] bg-foreground dark:bg-white opacity-0 group-data-[state=active]:opacity-100 transition-all duration-200" />
									</span>
									{totalSourceCount > 0 && (
										<span className="px-1.5 py-0.5 rounded-full bg-muted-foreground/15 text-[10px] font-bold">
											{totalSourceCount}
										</span>
									)}
								</TabsTrigger>
							</TabsList>

							<div className="w-full sm:w-72 sm:pb-1">
								<div className="relative">
									<Search className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-muted-foreground/60" />
									<input 
										type="text"
										placeholder="Search"
										className="w-full bg-slate-400/5 dark:bg-white/5 hover:bg-slate-400/10 dark:hover:bg-white/10 focus:bg-slate-400/10 dark:focus:bg-white/10 border border-border rounded-xl pl-9 pr-4 py-2 text-sm transition-all outline-none placeholder:text-muted-foreground/50"
										value={searchQuery}
										onChange={(e) => setSearchQuery(e.target.value)}
									/>
								</div>
							</div>
						</div>
					</div>

					{/* Content */}
					<div className="flex-1 min-h-0 relative overflow-hidden">
						<div className="h-full overflow-y-auto" onScroll={handleScroll}>
							<div className="px-6 sm:px-12 py-6 sm:py-8 pb-16 sm:pb-16">
							<TabsContent value="all" className="m-0 space-y-8">
								{/* Quick Connect */}
								{filteredOAuth.length > 0 && (
									<section>
										<div className="flex items-center gap-2 mb-4">
											<h3 className="text-sm font-semibold text-muted-foreground">Quick Connect</h3>
										</div>
										<div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
											{filteredOAuth.map((connector) => {
												const isConnected = connectedTypes.has(connector.connectorType);
												const isConnecting = connectingId === connector.id;

												return (
													<div
														key={connector.id}
														className="group relative flex items-center gap-4 p-4 rounded-xl text-left transition-all duration-200 w-full border border-border bg-slate-400/5 dark:bg-white/5 hover:bg-slate-400/10 dark:hover:bg-white/10"
													>
														<div className="flex h-12 w-12 items-center justify-center rounded-lg transition-colors flex-shrink-0 bg-slate-400/5 dark:bg-white/5 border border-slate-400/5 dark:border-white/5">
															{getConnectorIcon(connector.connectorType, "size-6")}
														</div>
														<div className="flex-1 min-w-0">
															<div className="flex items-center gap-2">
																<span className="text-[14px] font-semibold leading-tight">{connector.title}</span>
																{isConnected && (
																	<span className="size-1.5 rounded-full bg-green-500 shadow-[0_0_8px_rgba(34,197,94,0.6)]" title="Connected" />
																)}
															</div>
															<p className="text-[11px] text-muted-foreground truncate mt-1">
																{isConnected ? "Connected" : connector.description}
															</p>
														</div>
														<Button
															size="sm"
															variant={isConnected ? "outline" : "default"}
															className="h-8 text-[11px] px-3 rounded-lg flex-shrink-0 font-medium"
															onClick={() =>
																isConnected
																	? router.push(
																			`/dashboard/${searchSpaceId}/connectors/add/${connector.id}`
																		)
																	: handleConnectOAuth(connector)
															}
															disabled={isConnecting}
														>
															{isConnecting ? (
																<Loader2 className="size-3 animate-spin" />
															) : isConnected ? (
																"Manage"
															) : (
																"Connect"
															)}
														</Button>
													</div>
												);
											})}
										</div>
									</section>
								)}

								{/* More Integrations */}
								{filteredOther.length > 0 && (
									<section>
										<div className="flex items-center gap-2 mb-4">
											<h3 className="text-sm font-semibold text-muted-foreground">More Integrations</h3>
										</div>
										<div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
											{filteredOther.map((connector) => {
												const isConnected = connectedTypes.has(connector.connectorType);

												return (
													<Link
														key={connector.id}
														href={`/dashboard/${searchSpaceId}/connectors/add/${connector.id}`}
														className="group flex items-center gap-4 p-4 rounded-xl transition-all duration-150 border border-border bg-slate-400/5 dark:bg-white/5 hover:bg-slate-400/10 dark:hover:bg-white/10"
													>
														<div className="flex h-12 w-12 items-center justify-center rounded-lg transition-colors bg-slate-400/5 dark:bg-white/5 border border-slate-400/5 dark:border-white/5">
															{getConnectorIcon(connector.connectorType, "size-6")}
														</div>
														<div className="flex-1 min-w-0">
															<div className="flex items-center gap-2">
																<span className="text-[14px] font-semibold leading-tight">{connector.title}</span>
																{isConnected && (
																	<span className="size-1.5 rounded-full bg-green-500 shadow-[0_0_8px_rgba(34,197,94,0.6)]" title="Connected" />
																)}
															</div>
															<p className="text-[11px] text-muted-foreground truncate mt-1">
																{connector.description}
															</p>
														</div>
														<ChevronRight className="size-4 text-muted-foreground/50 group-hover:text-foreground transition-colors flex-shrink-0" />
													</Link>
												);
											})}
										</div>
									</section>
								)}
							</TabsContent>

							<TabsContent value="active" className="m-0">
								{hasSources ? (
									<div className="space-y-6">
										<div className="flex items-center gap-2 mb-4">
											<h3 className="text-sm font-semibold text-muted-foreground">Currently Active</h3>
										</div>
										<div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
											{activeDocumentTypes.map(([docType, count]) => (
												<div
													key={docType}
													className="flex items-center gap-4 p-4 rounded-xl bg-slate-400/5 dark:bg-white/5 hover:bg-slate-400/10 dark:hover:bg-white/10 border border-border transition-all"
												>
													<div className="flex h-12 w-12 items-center justify-center rounded-lg bg-slate-400/5 dark:bg-white/5 border border-slate-400/5 dark:border-white/5">
														{getConnectorIcon(docType, "size-6")}
													</div>
													<div>
														<p className="text-[14px] font-semibold leading-tight">
															{getDocumentTypeLabel(docType)}
														</p>
														<p className="text-[11px] text-muted-foreground mt-1">
															{count as number} documents indexed
														</p>
													</div>
												</div>
											))}
											{connectors.map((connector) => {
												const isIndexing = indexingConnectorIds.has(connector.id);
												const activeTask = logsSummary?.active_tasks?.find(
													(task) => task.source?.includes(`connector_${connector.id}`) || task.source?.includes(`connector-${connector.id}`)
												);

												return (
													<div
														key={`connector-${connector.id}`}
														className={cn(
															"flex items-center gap-4 p-4 rounded-xl border border-border transition-all",
															isIndexing
																? "bg-primary/5 border-primary/20"
																: "bg-slate-400/5 dark:bg-white/5 hover:bg-slate-400/10 dark:hover:bg-white/10"
														)}
													>
														<div className={cn(
															"flex h-12 w-12 items-center justify-center rounded-lg border",
															isIndexing
																? "bg-primary/10 border-primary/20"
																: "bg-slate-400/5 dark:bg-white/5 border-slate-400/5 dark:border-white/5"
														)}>
															{getConnectorIcon(connector.connector_type, "size-6")}
														</div>
														<div className="flex-1 min-w-0">
															<p className="text-[14px] font-semibold leading-tight truncate">
																{connector.name}
															</p>
															{isIndexing ? (
																<p className="text-[11px] text-primary mt-1 flex items-center gap-1.5">
																	<Loader2 className="size-3 animate-spin" />
																	Indexing...
																	{activeTask?.message && (
																		<span className="text-muted-foreground truncate max-w-[150px]">
																			• {activeTask.message}
																		</span>
																	)}
																</p>
															) : (
																<p className="text-[11px] text-muted-foreground mt-1">
																	{connector.last_indexed_at
																		? `Last indexed: ${format(new Date(connector.last_indexed_at), "MMM d, yyyy")}`
																		: "Never indexed"}
																</p>
															)}
														</div>
														<Button 
															variant="ghost" 
															size="sm" 
															className="h-8 text-[11px]" 
															onClick={() => router.push(`/dashboard/${searchSpaceId}/connectors/add/${connector.id}`)}
															disabled={isIndexing}
														>
															{isIndexing ? "Syncing..." : "Manage"}
														</Button>
													</div>
												);
											})}
										</div>
									</div>
								) : (
									<div className="flex flex-col items-center justify-center py-20 text-center">
										<div className="flex h-16 w-16 items-center justify-center rounded-full bg-muted mb-4">
											<Cable className="size-8 text-muted-foreground/50" />
										</div>
										<h4 className="text-lg font-semibold">No active sources</h4>
										<p className="text-sm text-muted-foreground mt-1 max-w-[280px]">
											Connect your first service to start searching across all your data.
										</p>
										<TabsTrigger value="all" className="mt-6 text-primary hover:underline">
											Browse available connectors
										</TabsTrigger>
									</div>
								)}
								</TabsContent>
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
