"use client";

import type { FC } from "react";
import { EnumConnectorName } from "@/contracts/enums/connector";
import type { SearchSourceConnector } from "@/contracts/types/connector.types";
import { isSelfHosted } from "@/lib/env-config";
import { ConnectorCard } from "../components/connector-card";
import {
	COMPOSIO_CONNECTORS,
	CRAWLERS,
	OAUTH_CONNECTORS,
	OTHER_CONNECTORS,
} from "../constants/connector-constants";
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
	onConnectOAuth: (
		connector: (typeof OAUTH_CONNECTORS)[number] | (typeof COMPOSIO_CONNECTORS)[number]
	) => void;
	onConnectNonOAuth?: (connectorType: string) => void;
	onCreateWebcrawler?: () => void;
	onCreateYouTubeCrawler?: () => void;
	onManage?: (connector: SearchSourceConnector) => void;
	onViewAccountsList?: (connectorType: string, connectorTitle: string) => void;
}

export const AllConnectorsTab: FC<AllConnectorsTabProps> = ({
	searchQuery,
	connectedTypes,
	connectingId,
	allConnectors,
	documentTypeCounts,
	indexingConnectorIds,
	onConnectOAuth,
	onConnectNonOAuth,
	onCreateWebcrawler,
	onCreateYouTubeCrawler,
	onManage,
	onViewAccountsList,
}) => {
	// Check if self-hosted mode (for showing self-hosted only connectors)
	const selfHosted = isSelfHosted();

	// Filter connectors based on search and deployment mode
	const filteredOAuth = OAUTH_CONNECTORS.filter(
		(c) =>
			// Filter by search query
			(c.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
				c.description.toLowerCase().includes(searchQuery.toLowerCase())) &&
			// Filter self-hosted only connectors in cloud mode
			(!("selfHostedOnly" in c) || !c.selfHostedOnly || selfHosted)
	);

	const filteredCrawlers = CRAWLERS.filter(
		(c) =>
			(c.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
				c.description.toLowerCase().includes(searchQuery.toLowerCase())) &&
			(!("selfHostedOnly" in c) || !c.selfHostedOnly || selfHosted)
	);

	const filteredOther = OTHER_CONNECTORS.filter(
		(c) =>
			(c.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
				c.description.toLowerCase().includes(searchQuery.toLowerCase())) &&
			(!("selfHostedOnly" in c) || !c.selfHostedOnly || selfHosted)
	);

	// Filter Composio connectors
	const filteredComposio = COMPOSIO_CONNECTORS.filter(
		(c) =>
			c.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
			c.description.toLowerCase().includes(searchQuery.toLowerCase())
	);

	return (
		<div className="space-y-8">
			{/* Managed OAuth (Composio Integrations) */}
			{filteredComposio.length > 0 && (
				<section>
					<div className="flex items-center gap-2 mb-4">
						<h3 className="text-sm font-semibold text-muted-foreground">
							Managed OAuth (Composio)
						</h3>
					</div>
					<div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
						{filteredComposio.map((connector) => {
							const isConnected = connectedTypes.has(connector.connectorType);
							const isConnecting = connectingId === connector.id;

							// Find all connectors of this type
							const typeConnectors =
								isConnected && allConnectors
									? allConnectors.filter(
											(c: SearchSourceConnector) => c.connector_type === connector.connectorType
										)
									: [];

							const accountCount = typeConnectors.length;

							const documentCount = getDocumentCountForConnector(
								connector.connectorType,
								documentTypeCounts
							);

							// Check if any account is currently indexing
							const isIndexing = typeConnectors.some((c) => indexingConnectorIds?.has(c.id));

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
									accountCount={accountCount}
									isIndexing={isIndexing}
									onConnect={() => onConnectOAuth(connector)}
									onManage={
										isConnected && onViewAccountsList
											? () => onViewAccountsList(connector.connectorType, connector.title)
											: undefined
									}
								/>
							);
						})}
					</div>
				</section>
			)}

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

							// Find all connectors of this type
							const typeConnectors =
								isConnected && allConnectors
									? allConnectors.filter(
											(c: SearchSourceConnector) => c.connector_type === connector.connectorType
										)
									: [];

							const accountCount = typeConnectors.length;

							const documentCount = getDocumentCountForConnector(
								connector.connectorType,
								documentTypeCounts
							);

							// Check if any account is currently indexing
							const isIndexing = typeConnectors.some((c) => indexingConnectorIds?.has(c.id));

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
									accountCount={accountCount}
									isIndexing={isIndexing}
									onConnect={() => onConnectOAuth(connector)}
									onManage={
										isConnected && onViewAccountsList
											? () => onViewAccountsList(connector.connectorType, connector.title)
											: undefined
									}
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

							// For MCP connectors, count total MCP connectors instead of document count
							const isMCP = connector.connectorType === EnumConnectorName.MCP_CONNECTOR;
							const mcpConnectorCount =
								isMCP && allConnectors
									? allConnectors.filter(
											(c: SearchSourceConnector) =>
												c.connector_type === EnumConnectorName.MCP_CONNECTOR
										).length
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
									connectorCount={mcpConnectorCount}
									isIndexing={isIndexing}
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
									isIndexing={isIndexing}
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
