"use client";

import { useAtomValue } from "jotai";
import {
	Cable,
	ChevronRight,
	Loader2,
	Search,
} from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { type FC, useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { getDocumentTypeLabel } from "@/app/dashboard/[search_space_id]/documents/(manage)/components/DocumentTypeIcon";
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
import { EnumConnectorName } from "@/contracts/enums/connector";
import { getConnectorIcon } from "@/contracts/enums/connectorIcons";
import type { SearchSourceConnector } from "@/contracts/types/connector.types";
import { useSearchSourceConnectors } from "@/hooks/use-search-source-connectors";
import { authenticatedFetch } from "@/lib/auth-utils";
import { TooltipIconButton } from "@/components/assistant-ui/tooltip-icon-button";
import { cn } from "@/lib/utils";

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
	const searchSpaceId = useAtomValue(activeSearchSpaceIdAtom);
	const { connectors, isLoading: connectorsLoading } = useSearchSourceConnectors(
		false,
		searchSpaceId ? Number(searchSpaceId) : undefined
	);
	const { data: documentTypeCounts, isLoading: documentTypesLoading } =
		useAtomValue(documentTypeCountsAtom);
	const { data: allConnectors } = useAtomValue(connectorsAtom);
	const pathname = usePathname();
	const [isOpen, setIsOpen] = useState(false);
	const [activeTab, setActiveTab] = useState("all");
	const [connectingId, setConnectingId] = useState<string | null>(null);
	const [isScrolled, setIsScrolled] = useState(false);
	const [searchQuery, setSearchQuery] = useState("");

	const isLoading = connectorsLoading || documentTypesLoading;

	// Synchronize state with URL path
	useEffect(() => {
		const pathParts = window.location.pathname.split("/");
		const connectorsIdx = pathParts.indexOf("connectors");
		
		if (connectorsIdx !== -1) {
			if (!isOpen) setIsOpen(true);
			
			// Detect tab from URL: .../connectors/active or .../connectors/all
			const tabFromUrl = pathParts[connectorsIdx + 1];
			if (tabFromUrl === "active" || tabFromUrl === "all") {
				if (activeTab !== tabFromUrl) setActiveTab(tabFromUrl);
			}
		} else {
			if (isOpen) setIsOpen(false);
		}
	}, [pathname, isOpen, activeTab]);

	// Get document types that have documents in the search space
	const activeDocumentTypes = documentTypeCounts
		? Object.entries(documentTypeCounts).filter(([_, count]) => count > 0)
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

			const currentPath = window.location.pathname;
			const basePath = currentPath.split("/connectors")[0].replace(/\/$/, "");
			
			if (open) {
				// Base state is /connectors/all
				const newUrl = `${basePath}/connectors/${activeTab}`;
				window.history.pushState({ modal: true }, "", newUrl);
			} else {
				// Return to base chat path
				window.history.pushState({ modal: false }, "", basePath || "/");
				setIsScrolled(false);
				setSearchQuery("");
			}
		},
		[activeTab]
	);

	const handleTabChange = useCallback(
		(value: string) => {
			setActiveTab(value);
			const currentPath = window.location.pathname;
			const basePath = currentPath.split("/connectors")[0].replace(/\/$/, "");
			
			// Update URL to reflect the new tab state
			const newUrl = `${basePath}/connectors/${value}`;
			window.history.replaceState({ modal: true }, "", newUrl);
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

						<div className="flex flex-col-reverse sm:flex-row sm:items-end justify-between gap-6 sm:gap-8 mt-6 sm:mt-8 border-b border-black/5 dark:border-white/5">
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
										className="w-full bg-black/5 dark:bg-white/5 hover:bg-black/10 dark:hover:bg-white/10 focus:bg-black/10 dark:focus:bg-white/10 border border-border rounded-xl pl-9 pr-4 py-2 text-sm transition-all outline-none placeholder:text-muted-foreground/50"
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
														className="group relative flex items-center gap-4 p-4 rounded-xl text-left transition-all duration-200 w-full border border-border bg-black/5 dark:bg-white/5 hover:bg-black/10 dark:hover:bg-white/10"
													>
														<div className="flex h-12 w-12 items-center justify-center rounded-lg transition-colors flex-shrink-0 bg-black/5 dark:bg-white/5 border border-black/5 dark:border-white/5">
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
														className="group flex items-center gap-4 p-4 rounded-xl transition-all duration-150 border border-border bg-black/5 dark:bg-white/5 hover:bg-black/10 dark:hover:bg-white/10"
													>
														<div className="flex h-12 w-12 items-center justify-center rounded-lg transition-colors bg-black/5 dark:bg-white/5 border border-black/5 dark:border-white/5">
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
													className="flex items-center gap-4 p-4 rounded-xl bg-black/5 dark:bg-white/5 hover:bg-black/10 dark:hover:bg-white/10 border border-border transition-all"
												>
													<div className="flex h-12 w-12 items-center justify-center rounded-lg bg-black/5 dark:bg-white/5 border border-black/5 dark:border-white/5">
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
											{connectors.map((connector) => (
												<div
													key={`connector-${connector.id}`}
													className="flex items-center gap-4 p-4 rounded-xl bg-black/5 dark:bg-white/5 hover:bg-black/10 dark:hover:bg-white/10 border border-border transition-all"
												>
													<div className="flex h-12 w-12 items-center justify-center rounded-lg bg-black/5 dark:bg-white/5 border border-black/5 dark:border-white/5">
														{getConnectorIcon(connector.connector_type, "size-6")}
													</div>
													<div className="flex-1 min-w-0">
														<p className="text-[14px] font-semibold leading-tight truncate">
															{connector.name}
														</p>
														<p className="text-[11px] text-muted-foreground mt-1">Status: Active</p>
													</div>
													<Button variant="ghost" size="sm" className="h-8 text-[11px]" onClick={() => router.push(`/dashboard/${searchSpaceId}/connectors/add/${connector.id}`)}>
														Manage
													</Button>
												</div>
											))}
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
			</DialogContent>
		</Dialog>
	);
};
