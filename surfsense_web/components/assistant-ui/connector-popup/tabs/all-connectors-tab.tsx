"use client";

import { useRouter } from "next/navigation";
import { type FC } from "react";
import type { SearchSourceConnector } from "@/contracts/types/connector.types";
import { OAUTH_CONNECTORS, OTHER_CONNECTORS } from "../constants/connector-constants";
import { ConnectorCard } from "../components/connector-card";

interface AllConnectorsTabProps {
	searchQuery: string;
	searchSpaceId: string;
	connectedTypes: Set<string>;
	connectingId: string | null;
	allConnectors: SearchSourceConnector[] | undefined;
	onConnectOAuth: (connector: (typeof OAUTH_CONNECTORS)[0]) => void;
	onConnectNonOAuth?: (connectorType: string) => void;
	onCreateWebcrawler?: () => void;
	onCreateYouTube?: () => void;
	onManage?: (connector: SearchSourceConnector) => void;
}

export const AllConnectorsTab: FC<AllConnectorsTabProps> = ({
	searchQuery,
	searchSpaceId,
	connectedTypes,
	connectingId,
	allConnectors,
	onConnectOAuth,
	onConnectNonOAuth,
	onCreateWebcrawler,
	onCreateYouTube,
	onManage,
}) => {
	const router = useRouter();

	// Filter connectors based on search
	const filteredOAuth = OAUTH_CONNECTORS.filter(
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

							return (
								<ConnectorCard
									key={connector.id}
									id={connector.id}
									title={connector.title}
									description={connector.description}
									connectorType={connector.connectorType}
									isConnected={isConnected}
									isConnecting={isConnecting}
									onConnect={() => onConnectOAuth(connector)}
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
							const isConnected = connectedTypes.has(connector.connectorType);
							const isConnecting = connectingId === connector.id;
							// Find the actual connector object if connected
							const actualConnector = isConnected && allConnectors
								? allConnectors.find((c: SearchSourceConnector) => c.connector_type === connector.connectorType)
								: undefined;

							// Special handling for connectors that can be created in popup
							const isWebcrawler = connector.id === "webcrawler-connector";
							const isYouTube = connector.id === "youtube-connector";
							const isTavily = connector.id === "tavily-api";
							const handleConnect = isWebcrawler && onCreateWebcrawler
								? onCreateWebcrawler
								: isYouTube && onCreateYouTube
								? onCreateYouTube
								: isTavily && onConnectNonOAuth
								? () => onConnectNonOAuth(connector.connectorType)
								: () => router.push(`/dashboard/${searchSpaceId}/connectors/add/${connector.id}`);

							return (
								<ConnectorCard
									key={connector.id}
									id={connector.id}
									title={connector.title}
									description={connector.description}
									connectorType={connector.connectorType}
									isConnected={isConnected}
									isConnecting={isConnecting}
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

