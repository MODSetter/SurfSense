"use client";

import { Search } from "lucide-react";
import type { FC } from "react";
import { useIsSelfHosted } from "@/components/providers/runtime-config";
import { EnumConnectorName } from "@/contracts/enums/connector";
import type { SearchSourceConnector } from "@/contracts/types/connector.types";
import { usePlatform } from "@/hooks/use-platform";
import { ConnectorCard } from "../components/connector-card";
import {
	COMPOSIO_CONNECTORS,
	CRAWLERS,
	DEPRECATED_CONNECTOR_TYPES,
	OAUTH_CONNECTORS,
	OTHER_CONNECTORS,
} from "../constants/connector-constants";
import { getDocumentCountForConnector } from "../utils/connector-document-mapping";

type OAuthConnector = (typeof OAUTH_CONNECTORS)[number];
type ComposioConnector = (typeof COMPOSIO_CONNECTORS)[number];
type OtherConnector = (typeof OTHER_CONNECTORS)[number];
type CrawlerConnector = (typeof CRAWLERS)[number];
type DeploymentFilterableConnector = {
	readonly id: string;
	readonly selfHostedOnly?: boolean;
	readonly desktopOnly?: boolean;
};

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
	workspaceId: string;
	connectedTypes: Set<string>;
	connectingId: string | null;
	allConnectors: SearchSourceConnector[] | undefined;
	documentTypeCounts?: Record<string, number>;
	indexingConnectorIds?: Set<number>;
	onConnectOAuth: (connector: OAuthConnector | ComposioConnector) => void;
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
	const selfHosted = useIsSelfHosted();
	const { isDesktop } = usePlatform();

	const matchesSearch = (title: string, description: string) =>
		title.toLowerCase().includes(searchQuery.toLowerCase()) ||
		description.toLowerCase().includes(searchQuery.toLowerCase());

	const passesDeploymentFilter = (c: DeploymentFilterableConnector) =>
		(!c.selfHostedOnly || selfHosted) && (!c.desktopOnly || isDesktop);

	// Filter connectors based on search and deployment mode
	const filteredOAuth = OAUTH_CONNECTORS.filter(
		(c) => matchesSearch(c.title, c.description) && passesDeploymentFilter(c)
	);

	const filteredCrawlers = CRAWLERS.filter(
		(c) => matchesSearch(c.title, c.description) && passesDeploymentFilter(c)
	);

	const filteredOther = OTHER_CONNECTORS.filter(
		(c) => matchesSearch(c.title, c.description) && passesDeploymentFilter(c)
	);

	// Filter Composio connectors
	const filteredComposio = COMPOSIO_CONNECTORS.filter(
		(c) =>
			c.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
			c.description.toLowerCase().includes(searchQuery.toLowerCase())
	);

	// One flat grid, no separate "Deprecated" section. A deprecated connector is
	// shown only if the user already connected it (before deprecation), so it
	// stays manageable/disconnectable; never-connected deprecated connectors are
	// hidden entirely. See DEPRECATED_CONNECTOR_TYPES for the full list.
	const isVisible = <T extends { connectorType?: string }>(c: T) =>
		!c.connectorType ||
		!DEPRECATED_CONNECTOR_TYPES.has(c.connectorType) ||
		connectedTypes.has(c.connectorType);
	const available = {
		oauth: filteredOAuth.filter(isVisible),
		composio: filteredComposio.filter(isVisible),
		other: filteredOther.filter(isVisible),
		crawlers: filteredCrawlers.filter(isVisible),
	};

	const renderOAuthCard = (connector: OAuthConnector | ComposioConnector) => {
		const isConnected = connectedTypes.has(connector.connectorType);
		const isConnecting = connectingId === connector.id;

		const typeConnectors =
			isConnected && allConnectors
				? allConnectors.filter(
						(c: SearchSourceConnector) => c.connector_type === connector.connectorType
					)
				: [];

		const accountCount = typeConnectors.length;
		const documentCount = getDocumentCountForConnector(connector.connectorType, documentTypeCounts);
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
	};

	const renderOtherCard = (connector: OtherConnector) => {
		const isConnected = connectedTypes.has(connector.connectorType);
		const isConnecting = connectingId === connector.id;

		const actualConnector =
			isConnected && allConnectors
				? allConnectors.find(
						(c: SearchSourceConnector) => c.connector_type === connector.connectorType
					)
				: undefined;

		const documentCount = getDocumentCountForConnector(connector.connectorType, documentTypeCounts);
		const isIndexing = actualConnector && indexingConnectorIds?.has(actualConnector.id);

		const isMCP = connector.connectorType === EnumConnectorName.MCP_CONNECTOR;
		const mcpConnectorCount =
			isMCP && allConnectors
				? allConnectors.filter(
						(c: SearchSourceConnector) => c.connector_type === EnumConnectorName.MCP_CONNECTOR
					).length
				: undefined;

		const handleConnect = onConnectNonOAuth
			? () => onConnectNonOAuth(connector.connectorType)
			: () => {};

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
				onManage={actualConnector && onManage ? () => onManage(actualConnector) : undefined}
			/>
		);
	};

	const renderCrawlerCard = (crawler: CrawlerConnector) => {
		const isYouTube = crawler.id === "youtube-crawler";
		const isWebcrawler = crawler.id === "webcrawler-connector";
		const isConnected = crawler.connectorType ? connectedTypes.has(crawler.connectorType) : false;
		const isConnecting = connectingId === crawler.id;

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
						: () => {};

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
				onManage={actualConnector && onManage ? () => onManage(actualConnector) : undefined}
			/>
		);
	};

	const hasAnyResults =
		available.oauth.length > 0 ||
		available.composio.length > 0 ||
		available.other.length > 0 ||
		available.crawlers.length > 0;

	if (!hasAnyResults && searchQuery) {
		return (
			<div className="flex flex-col items-center justify-center py-20 text-center">
				<Search className="size-8 text-muted-foreground mb-3" />
				<p className="text-sm text-muted-foreground">No connectors found</p>
				<p className="text-xs text-muted-foreground/60 mt-1">Try a different search term</p>
			</div>
		);
	}

	return (
		<div className="space-y-8">
			<div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
				{available.oauth.map(renderOAuthCard)}
				{available.composio.map(renderOAuthCard)}
				{available.crawlers.map(renderCrawlerCard)}
				{available.other.map(renderOtherCard)}
			</div>
		</div>
	);
};
