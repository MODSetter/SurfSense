"use client";

import { ChevronRight } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { type FC } from "react";
import { getConnectorIcon } from "@/contracts/enums/connectorIcons";
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
											<span className="text-[14px] font-semibold leading-tight">
												{connector.title}
											</span>
											{isConnected && (
												<span
													className="size-1.5 rounded-full bg-green-500 shadow-[0_0_8px_rgba(34,197,94,0.6)]"
													title="Connected"
												/>
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
		</div>
	);
};

