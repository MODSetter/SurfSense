"use client";

import type { FC } from "react";
import type { SearchSourceConnector } from "@/contracts/types/connector.types";
import type { LogActiveTask, LogSummary } from "@/contracts/types/log.types";
import { OAUTH_CONNECTORS, CRAWLERS, OTHER_CONNECTORS } from "../constants/connector-constants";
import { ConnectorCard } from "../components/connector-card";
import { getDocumentCountForConnector } from "../utils/connector-document-mapping";

interface AllConnectorsTabProps {
	searchQuery: string;
	searchSpaceId: string;
	connectedTypes: Set<string>;
	connectingId: string | null;
	allConnectors: SearchSourceConnector[] | undefined;
	documentTypeCounts?: Record<string, number>;
	indexingConnectorIds?: Set<number>;
	logsSummary?: LogSummary;
	onConnectOAuth: (connector: (typeof OAUTH_CONNECTORS)[number]) => void;
	onConnectNonOAuth?: (connectorType: string) => void;
	onCreateWebcrawler?: () => void;
	onCreateYouTubeCrawler?: () => void;
	onManage?: (connector: SearchSourceConnector) => void;
}

export const AllConnectorsTab: FC<AllConnectorsTabProps> = ({
	searchQuery,
	searchSpaceId,
	connectedTypes,
	connectingId,
	allConnectors,
	documentTypeCounts,
	indexingConnectorIds,
	logsSummary,
	onConnectOAuth,
	onConnectNonOAuth,
	onCreateWebcrawler,
	onCreateYouTubeCrawler,
	onManage,
}) => {
	// Helper to find active task for a connector
	const getActiveTaskForConnector = (connectorId: number): LogActiveTask | undefined => {
		if (!logsSummary?.active_tasks) return undefined;
		return logsSummary.active_tasks.find(
			(task: LogActiveTask) => task.connector_id === connectorId
		);
	};

	// Filter connectors based on search
	const filteredOAuth = OAUTH_CONNECTORS.filter(
		(c) =>
			c.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
			c.description.toLowerCase().includes(searchQuery.toLowerCase())
	);

	const filteredCrawlers = CRAWLERS.filter(
		(c) =>
			c.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
			c.description.toLowerCase().includes(searchQuery.toLowerCase())
	);

	const filteredOther = OTHER_CONNECTORS.filter(
		(c) =>
			c.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
			c.description.toLowerCase().includes(searchQuery.toLowerCase())
	);

	return (
		<div className="space-y-8">
			{/* Quick Connect */}
			{filteredOAuth.length > 0 && (
				<section>
					<div className="flex items-center gap-2 mb-4">
						<h3 className="text-sm font-semibold text-muted-foreground">
							Quick Connect
						</h3>
					</div>
					<div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
					{filteredOAuth.map((connector) => {
						const isConnected = connectedTypes.has(connector.connectorType);
						const isConnecting = connectingId === connector.id;
						// Find the actual connector object if connected
						const actualConnector = isConnected && allConnectors
							? allConnectors.find((c: SearchSourceConnector) => c.connector_type === connector.connectorType)
							: undefined;
						
						const documentCount = getDocumentCountForConnector(connector.connectorType, documentTypeCounts);
						const isIndexing = actualConnector && indexingConnectorIds?.has(actualConnector.id);
						const activeTask = actualConnector ? getActiveTaskForConnector(actualConnector.id) : undefined;

						return (
							<ConnectorCard
								key={connector.id}
								id={connector.id}
								title={connector.title}
								description={connector.description}
								connectorType={connector.connectorType}
								isConnected={isConnected}
								isConnecting={isConnecting}
								documentCount={documentCount}
								lastIndexedAt={actualConnector?.last_indexed_at}
								isIndexing={isIndexing}
								activeTask={activeTask}
								onConnect={() => onConnectOAuth(connector)}
								onManage={actualConnector && onManage ? () => onManage(actualConnector) : undefined}
							/>
						);
					})}
					</div>
				</section>
			)}

			{/* Content Sources */}
			{filteredCrawlers.length > 0 && (
				<section>
					<div className="flex items-center gap-2 mb-4">
						<h3 className="text-sm font-semibold text-muted-foreground">
							Content Sources
						</h3>
					</div>
					<div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
						{filteredCrawlers.map((crawler) => {
							const isYouTube = crawler.id === "youtube-crawler";
							const isWebcrawler = crawler.id === "webcrawler-connector";
							
							// For crawlers that are actual connectors, check connection status
							const isConnected = crawler.connectorType 
								? connectedTypes.has(crawler.connectorType)
								: false;
							const isConnecting = connectingId === crawler.id;
							
							// Find the actual connector object if connected
							const actualConnector = isConnected && crawler.connectorType && allConnectors
								? allConnectors.find((c: SearchSourceConnector) => c.connector_type === crawler.connectorType)
								: undefined;

							const documentCount = crawler.connectorType 
								? getDocumentCountForConnector(crawler.connectorType, documentTypeCounts)
								: undefined;
							const isIndexing = actualConnector && indexingConnectorIds?.has(actualConnector.id);
							const activeTask = actualConnector ? getActiveTaskForConnector(actualConnector.id) : undefined;

							const handleConnect = isYouTube && onCreateYouTubeCrawler
								? onCreateYouTubeCrawler
								: isWebcrawler && onCreateWebcrawler
								? onCreateWebcrawler
								: crawler.connectorType && onConnectNonOAuth
								? () => {
									if (crawler.connectorType) {
										onConnectNonOAuth(crawler.connectorType);
									}
								}
								: () => {}; // Fallback for non-connector crawlers

							return (
								<ConnectorCard
									key={crawler.id}
									id={crawler.id}
									title={crawler.title}
									description={crawler.description}
									connectorType={crawler.connectorType || undefined}
									isConnected={isConnected}
									isConnecting={isConnecting}
									documentCount={documentCount}
									lastIndexedAt={actualConnector?.last_indexed_at}
									isIndexing={isIndexing}
									activeTask={activeTask}
									onConnect={handleConnect}
									onManage={actualConnector && onManage ? () => onManage(actualConnector) : undefined}
								/>
							);
						})}
					</div>
				</section>
			)}

			{/* More Integrations */}
			{filteredOther.length > 0 && (
				<section>
					<div className="flex items-center gap-2 mb-4">
						<h3 className="text-sm font-semibold text-muted-foreground">
							More Integrations
						</h3>
					</div>
					<div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
						{filteredOther.map((connector) => {
						// Special handling for connectors that can be created in popup
						const isTavily = connector.id === "tavily-api";
						const isSearxng = connector.id === "searxng";
						const isLinkup = connector.id === "linkup-api";
						const isBaidu = connector.id === "baidu-search-api";
						const isLinear = connector.id === "linear-connector";
						const isElasticsearch = connector.id === "elasticsearch-connector";
						const isSlack = connector.id === "slack-connector";
						const isDiscord = connector.id === "discord-connector";
						const isNotion = connector.id === "notion-connector";
						const isConfluence = connector.id === "confluence-connector";
						const isBookStack = connector.id === "bookstack-connector";
						const isGithub = connector.id === "github-connector";
						const isJira = connector.id === "jira-connector";
						const isClickUp = connector.id === "clickup-connector";
						const isLuma = connector.id === "luma-connector";
						const isCircleback = connector.id === "circleback-connector";
							
						const isConnected = connectedTypes.has(connector.connectorType);
						const isConnecting = connectingId === connector.id;
						
						// Find the actual connector object if connected
						const actualConnector = isConnected && allConnectors
							? allConnectors.find((c: SearchSourceConnector) => c.connector_type === connector.connectorType)
							: undefined;

						const documentCount = getDocumentCountForConnector(connector.connectorType, documentTypeCounts);
						const isIndexing = actualConnector && indexingConnectorIds?.has(actualConnector.id);
						const activeTask = actualConnector ? getActiveTaskForConnector(actualConnector.id) : undefined;

						const handleConnect = (isTavily || isSearxng || isLinkup || isBaidu || isLinear || isElasticsearch || isSlack || isDiscord || isNotion || isConfluence || isBookStack || isGithub || isJira || isClickUp || isLuma || isCircleback) && onConnectNonOAuth
							? () => onConnectNonOAuth(connector.connectorType)
							: () => {}; // Fallback - connector popup should handle all connector types

						return (
							<ConnectorCard
								key={connector.id}
								id={connector.id}
								title={connector.title}
								description={connector.description}
								connectorType={connector.connectorType}
								isConnected={isConnected}
								isConnecting={isConnecting}
								documentCount={documentCount}
								lastIndexedAt={actualConnector?.last_indexed_at}
								isIndexing={isIndexing}
								activeTask={activeTask}
								onConnect={handleConnect}
								onManage={actualConnector && onManage ? () => onManage(actualConnector) : undefined}
							/>
						);
					})}
					</div>
				</section>
			)}
		</div>
	);
};

