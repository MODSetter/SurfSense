"use client";

import { Search } from "lucide-react";
import type { FC } from "react";
import { EnumConnectorName } from "@/contracts/enums/connector";
import type { SearchSourceConnector } from "@/contracts/types/connector.types";
import { usePlatform } from "@/hooks/use-platform";
import { isSelfHosted } from "@/lib/env-config";
import { ConnectorCard } from "../components/connector-card";
import {
	COMPOSIO_CONNECTORS,
	CRAWLERS,
	OAUTH_CONNECTORS,
	OTHER_CONNECTORS,
} from "../constants/connector-constants";
import { getDocumentCountForConnector } from "../utils/connector-document-mapping";

type OAuthConnector = (typeof OAUTH_CONNECTORS)[number];
type ComposioConnector = (typeof COMPOSIO_CONNECTORS)[number];
type OtherConnector = (typeof OTHER_CONNECTORS)[number];
type CrawlerConnector = (typeof CRAWLERS)[number];

const DOCUMENT_FILE_CONNECTOR_TYPES = new Set<string>([
	EnumConnectorName.GOOGLE_DRIVE_CONNECTOR,
	EnumConnectorName.COMPOSIO_GOOGLE_DRIVE_CONNECTOR,
	EnumConnectorName.ONEDRIVE_CONNECTOR,
	EnumConnectorName.DROPBOX_CONNECTOR,
]);

const OTHER_DOCUMENT_CONNECTOR_TYPES = new Set<string>([
	EnumConnectorName.YOUTUBE_CONNECTOR,
	EnumConnectorName.NOTION_CONNECTOR,
	EnumConnectorName.AIRTABLE_CONNECTOR,
]);

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
	const selfHosted = isSelfHosted();
	const { isDesktop } = usePlatform();

	const matchesSearch = (title: string, description: string) =>
		title.toLowerCase().includes(searchQuery.toLowerCase()) ||
		description.toLowerCase().includes(searchQuery.toLowerCase());

	const passesDeploymentFilter = (c: { selfHostedOnly?: boolean; desktopOnly?: boolean }) =>
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

	const nativeGoogleDriveConnectors = filteredOAuth.filter(
		(c) => c.connectorType === EnumConnectorName.GOOGLE_DRIVE_CONNECTOR
	);
	const composioGoogleDriveConnectors = filteredComposio.filter(
		(c) => c.connectorType === EnumConnectorName.COMPOSIO_GOOGLE_DRIVE_CONNECTOR
	);
	const fileStorageConnectors = filteredOAuth.filter(
		(c) =>
			c.connectorType === EnumConnectorName.ONEDRIVE_CONNECTOR ||
			c.connectorType === EnumConnectorName.DROPBOX_CONNECTOR
	);

	const otherDocumentYouTubeConnectors = filteredCrawlers.filter(
		(c) => c.connectorType === EnumConnectorName.YOUTUBE_CONNECTOR
	);
	const otherDocumentNotionConnectors = filteredOAuth.filter(
		(c) => c.connectorType === EnumConnectorName.NOTION_CONNECTOR
	);
	const otherDocumentAirtableConnectors = filteredOAuth.filter(
		(c) => c.connectorType === EnumConnectorName.AIRTABLE_CONNECTOR
	);

	const moreIntegrationsComposio = filteredComposio.filter(
		(c) =>
			!DOCUMENT_FILE_CONNECTOR_TYPES.has(c.connectorType) &&
			!OTHER_DOCUMENT_CONNECTOR_TYPES.has(c.connectorType)
	);
	const moreIntegrationsOAuth = filteredOAuth.filter(
		(c) =>
			!DOCUMENT_FILE_CONNECTOR_TYPES.has(c.connectorType) &&
			!OTHER_DOCUMENT_CONNECTOR_TYPES.has(c.connectorType)
	);
	const moreIntegrationsOther = filteredOther;
	const moreIntegrationsCrawlers = filteredCrawlers.filter(
		(c) =>
			!c.connectorType ||
			(!DOCUMENT_FILE_CONNECTOR_TYPES.has(c.connectorType) &&
				!OTHER_DOCUMENT_CONNECTOR_TYPES.has(c.connectorType))
	);

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

	const hasDocumentFileConnectors =
		nativeGoogleDriveConnectors.length > 0 ||
		composioGoogleDriveConnectors.length > 0 ||
		fileStorageConnectors.length > 0;
	const hasMoreIntegrations =
		otherDocumentYouTubeConnectors.length > 0 ||
		otherDocumentNotionConnectors.length > 0 ||
		otherDocumentAirtableConnectors.length > 0 ||
		moreIntegrationsComposio.length > 0 ||
		moreIntegrationsOAuth.length > 0 ||
		moreIntegrationsOther.length > 0 ||
		moreIntegrationsCrawlers.length > 0;

	const hasAnyResults = hasDocumentFileConnectors || hasMoreIntegrations;

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
			{/* File Storage Integrations */}
			{hasDocumentFileConnectors && (
				<section>
					<div className="flex items-center gap-2 mb-4">
						<h3 className="text-sm font-semibold text-muted-foreground">
							File Storage Integrations
						</h3>
					</div>
					<div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
						{nativeGoogleDriveConnectors.map(renderOAuthCard)}
						{composioGoogleDriveConnectors.map(renderOAuthCard)}
						{fileStorageConnectors.map(renderOAuthCard)}
					</div>
				</section>
			)}

			{/* More Integrations */}
			{hasMoreIntegrations && (
				<section>
					<div className="flex items-center gap-2 mb-4">
						<h3 className="text-sm font-semibold text-muted-foreground">More Integrations</h3>
					</div>
					<div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
						{otherDocumentYouTubeConnectors.map(renderCrawlerCard)}
						{otherDocumentNotionConnectors.map(renderOAuthCard)}
						{otherDocumentAirtableConnectors.map(renderOAuthCard)}
						{moreIntegrationsComposio.map(renderOAuthCard)}
						{moreIntegrationsOAuth.map(renderOAuthCard)}
						{moreIntegrationsOther.map(renderOtherCard)}
						{moreIntegrationsCrawlers.map(renderCrawlerCard)}
					</div>
				</section>
			)}
		</div>
	);
};
