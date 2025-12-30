"use client";

import { useRouter } from "next/navigation";
import { type FC } from "react";
import { OAUTH_CONNECTORS, OTHER_CONNECTORS } from "./connector-constants";
import { ConnectorCard } from "./connector-card";

interface AllConnectorsTabProps {
	searchQuery: string;
	searchSpaceId: string;
	connectedTypes: Set<string>;
	connectingId: string | null;
	onConnectOAuth: (connector: (typeof OAUTH_CONNECTORS)[0]) => void;
}

export const AllConnectorsTab: FC<AllConnectorsTabProps> = ({
	searchQuery,
	searchSpaceId,
	connectedTypes,
	connectingId,
	onConnectOAuth,
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
									onManage={() =>
										router.push(
											`/dashboard/${searchSpaceId}/connectors/add/${connector.id}`
										)
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
						<h3 className="text-sm font-semibold text-muted-foreground">
							More Integrations
						</h3>
					</div>
					<div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
						{filteredOther.map((connector) => {
							const isConnected = connectedTypes.has(connector.connectorType);

							return (
								<ConnectorCard
									key={connector.id}
									id={connector.id}
									title={connector.title}
									description={connector.description}
									connectorType={connector.connectorType}
									isConnected={isConnected}
									onConnect={() =>
										router.push(
											`/dashboard/${searchSpaceId}/connectors/add/${connector.id}`
										)
									}
									onManage={() =>
										router.push(
											`/dashboard/${searchSpaceId}/connectors/add/${connector.id}`
										)
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

