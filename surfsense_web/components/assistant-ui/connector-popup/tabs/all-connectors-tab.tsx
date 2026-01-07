"use client";

import { Plus } from "lucide-react";
import type { FC } from "react";
import { Button } from "@/components/ui/button";
import type { SearchSourceConnector } from "@/contracts/types/connector.types";
import type { LogActiveTask, LogSummary } from "@/contracts/types/log.types";
import { ConnectorCard } from "../components/connector-card";
import { CRAWLERS, OAUTH_CONNECTORS, OTHER_CONNECTORS } from "../constants/connector-constants";
import { getDocumentCountForConnector } from "../utils/connector-document-mapping";

/**
 * Extract the display name from a full connector name.
 * Full names are in format "Base Name - identifier" (e.g., "Gmail - john@example.com").
 * Returns just the identifier (e.g : john@example.com).
 */
export function getConnectorDisplayName(fullName: string): string {
	const separatorIndex = fullName.indexOf(" - ");
	if (separatorIndex !== -1) {
		return fullName.substring(separatorIndex + 3);
	}
	return fullName;
}

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
			{/* Per-Type OAuth Connector Groups */}
			{filteredOAuth.map((connectorType) => {
				const userConnectors =
					allConnectors?.filter(
						(c: SearchSourceConnector) => c.connector_type === connectorType.connectorType
					) || [];
				const isConnecting = connectingId === connectorType.id;

				return (
					<section key={connectorType.id}>
						{/* Group Header */}
						<div className="flex items-center justify-between mb-4">
							<h3 className="text-sm font-semibold text-muted-foreground">
								{connectorType.title} Integrations
							</h3>
							{userConnectors.length > 0 && (
								<Button
									size="sm"
									variant="default"
									className="h-8 text-[11px] px-3 rounded-lg shrink-0 font-medium shadow-xs gap-1"
									onClick={() => onConnectOAuth(connectorType)}
									disabled={isConnecting}
								>
									<Plus className="size-3" />
									Add Account
								</Button>
							)}
						</div>

						<div className="grid grid-cols-1 sm:grid-cols-2 gap-1">
							{userConnectors.length === 0 ? (
								<ConnectorCard
									id={connectorType.id}
									title={connectorType.title}
									description={connectorType.description}
									connectorType={connectorType.connectorType}
									isConnected={false}
									isConnecting={isConnecting}
									onConnect={() => onConnectOAuth(connectorType)}
								/>
							) : (
								userConnectors.map((connector: SearchSourceConnector) => {
									const documentCount = getDocumentCountForConnector(
										connector.connector_type,
										documentTypeCounts
									);
									const isIndexing = indexingConnectorIds?.has(connector.id);
									const activeTask = getActiveTaskForConnector(connector.id);

									return (
										<ConnectorCard
											key={connector.id}
											id={String(connector.id)}
											title={getConnectorDisplayName(connector.name)}
											description={connectorType.description}
											connectorType={connector.connector_type}
											isConnected={true}
											isConnecting={false}
											documentCount={documentCount}
											lastIndexedAt={connector.last_indexed_at}
											isIndexing={isIndexing}
											activeTask={activeTask}
											onConnect={() => onConnectOAuth(connectorType)}
											onManage={onManage ? () => onManage(connector) : undefined}
										/>
									);
								})
							)}
						</div>
					</section>
				);
			})}

			{/* More Integrations */}
			{filteredOther.length > 0 && (
				<section>
					<div className="flex items-center gap-2 mb-4">
						<h3 className="text-sm font-semibold text-muted-foreground">More Integrations</h3>
					</div>
					<div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
						{filteredOther.map((connector) => {
							const isConnected = connectedTypes.has(connector.connectorType);
							const isConnecting = connectingId === connector.id;

							// Find the actual connector object if connected
							const actualConnector =
								isConnected && allConnectors
									? allConnectors.find(
											(c: SearchSourceConnector) => c.connector_type === connector.connectorType
										)
									: undefined;

							const documentCount = getDocumentCountForConnector(
								connector.connectorType,
								documentTypeCounts
							);
							const isIndexing = actualConnector && indexingConnectorIds?.has(actualConnector.id);
							const activeTask = actualConnector
								? getActiveTaskForConnector(actualConnector.id)
								: undefined;

							const handleConnect = onConnectNonOAuth
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
									onManage={
										actualConnector && onManage ? () => onManage(actualConnector) : undefined
									}
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
						<h3 className="text-sm font-semibold text-muted-foreground">Content Sources</h3>
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
							const actualConnector =
								isConnected && crawler.connectorType && allConnectors
									? allConnectors.find(
											(c: SearchSourceConnector) => c.connector_type === crawler.connectorType
										)
									: undefined;

							const documentCount = crawler.connectorType
								? getDocumentCountForConnector(crawler.connectorType, documentTypeCounts)
								: undefined;
							const isIndexing = actualConnector && indexingConnectorIds?.has(actualConnector.id);
							const activeTask = actualConnector
								? getActiveTaskForConnector(actualConnector.id)
								: undefined;

							const handleConnect =
								isYouTube && onCreateYouTubeCrawler
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
									onManage={
										actualConnector && onManage ? () => onManage(actualConnector) : undefined
									}
								/>
							);
						})}
					</div>
				</section>
			)}
		</div>
	);
};
