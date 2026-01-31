"use client";

import { ArrowLeft, Plus, Server } from "lucide-react";
import type { FC } from "react";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { EnumConnectorName } from "@/contracts/enums/connector";
import { getConnectorIcon } from "@/contracts/enums/connectorIcons";
import type { SearchSourceConnector } from "@/contracts/types/connector.types";
import { formatRelativeDate } from "@/lib/format-date";
import { cn } from "@/lib/utils";
import { useConnectorStatus } from "../hooks/use-connector-status";
import { getConnectorDisplayName } from "../tabs/all-connectors-tab";

interface ConnectorAccountsListViewProps {
	connectorType: string;
	connectorTitle: string;
	connectors: SearchSourceConnector[];
	indexingConnectorIds: Set<number>;
	onBack: () => void;
	onManage: (connector: SearchSourceConnector) => void;
	onAddAccount: () => void;
	isConnecting?: boolean;
	addButtonText?: string;
}

/**
 * Check if a connector type is indexable
 */
function isIndexableConnector(connectorType: string): boolean {
	const nonIndexableTypes = ["MCP_CONNECTOR"];
	return !nonIndexableTypes.includes(connectorType);
}

export const ConnectorAccountsListView: FC<ConnectorAccountsListViewProps> = ({
	connectorType,
	connectorTitle,
	connectors,
	indexingConnectorIds,
	onBack,
	onManage,
	onAddAccount,
	isConnecting = false,
	addButtonText,
}) => {
	// Get connector status
	const { isConnectorEnabled, getConnectorStatusMessage } = useConnectorStatus();

	const isEnabled = isConnectorEnabled(connectorType);
	const statusMessage = getConnectorStatusMessage(connectorType);

	// Filter connectors to only show those of this type
	const typeConnectors = connectors.filter((c) => c.connector_type === connectorType);

	// Determine button text - default to "Add Account" unless specified
	const buttonText =
		addButtonText ||
		(connectorType === EnumConnectorName.MCP_CONNECTOR ? "Add New MCP Server" : "Add Account");
	const isMCP = connectorType === EnumConnectorName.MCP_CONNECTOR;

	// Helper to get display name for connector (handles MCP server name extraction)
	const getDisplayName = (connector: SearchSourceConnector): string => {
		if (isMCP) {
			// For MCP, extract server name from config if available
			const serverName = connector.config?.server_config?.name || connector.name;
			return serverName;
		}
		return getConnectorDisplayName(connector.name);
	};

	return (
		<div className="flex flex-col h-full">
			{/* Header */}
			<div className="px-6 sm:px-12 pt-8 sm:pt-10 pb-1 sm:pb-4 border-b border-border/50 bg-muted">
				{/* Back button */}
				<button
					type="button"
					onClick={onBack}
					className="flex items-center gap-2 text-xs sm:text-sm text-muted-foreground hover:text-foreground mb-6 w-fit"
				>
					<ArrowLeft className="size-4" />
					Back to connectors
				</button>

				{/* Connector header */}
				<div className="flex flex-col sm:flex-row items-start sm:items-center gap-4 mb-6">
					<div className="flex gap-4 flex-1 w-full sm:w-auto">
						<div className="flex h-14 w-14 items-center justify-center rounded-xl bg-primary/10 border border-primary/20 shrink-0">
							{getConnectorIcon(connectorType, "size-7")}
						</div>
						<div className="flex-1 min-w-0">
							<h2 className="text-xl sm:text-2xl font-semibold tracking-tight text-wrap whitespace-normal">
								{connectorTitle}
							</h2>
							<p className="text-xs sm:text-base text-muted-foreground mt-1">
								{statusMessage || "Manage your connector settings and sync configuration"}
							</p>
						</div>
					</div>
					{/* Add Account Button with dashed border */}
					<button
						type="button"
						onClick={onAddAccount}
						disabled={isConnecting || !isEnabled}
						className={cn(
							"flex items-center justify-center gap-1.5 h-8 px-3 rounded-md border-2 border-dashed text-xs sm:text-sm transition-all duration-200 shrink-0 w-full sm:w-auto",
							!isEnabled
								? "border-border/30 opacity-50 cursor-not-allowed"
								: "border-slate-400/20 dark:border-white/20 hover:bg-primary/5",
							isConnecting && "opacity-50 cursor-not-allowed"
						)}
					>
						<div className="flex h-5 w-5 items-center justify-center rounded-md bg-primary/10 shrink-0">
							{isConnecting ? (
								<Spinner size="xs" className="text-primary" />
							) : (
								<Plus className="size-3 text-primary" />
							)}
						</div>
						<span className="text-xs sm:text-sm font-medium">
							{isConnecting ? "Connecting" : buttonText}
						</span>
					</button>
				</div>
			</div>

			{/* Content */}
			<div className="flex-1 overflow-y-auto px-6 sm:px-12 pt-0 sm:pt-6 pb-6 sm:pb-8">
				{/* Connected Accounts Grid */}
				{typeConnectors.length === 0 ? (
					<div className="flex flex-col items-center justify-center py-12 text-center">
						<div className="h-16 w-16 rounded-full bg-slate-400/5 dark:bg-white/5 flex items-center justify-center mb-4">
							{isMCP ? (
								<Server className="h-8 w-8 text-muted-foreground" />
							) : (
								getConnectorIcon(connectorType, "size-8")
							)}
						</div>
						<h3 className="text-sm font-medium mb-1">
							{isMCP ? "No MCP Servers" : `No ${connectorTitle} Accounts`}
						</h3>
						<p className="text-xs text-muted-foreground max-w-[280px]">
							{isMCP
								? "Get started by adding your first Model Context Protocol server"
								: `Get started by connecting your first ${connectorTitle} account`}
						</p>
					</div>
				) : (
					<div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
						{typeConnectors.map((connector) => {
							const isIndexing = indexingConnectorIds.has(connector.id);

							return (
								<div
									key={connector.id}
									className={cn(
										"flex items-center gap-4 p-4 rounded-xl transition-all",
										isIndexing
											? "bg-primary/5 border-0"
											: "bg-slate-400/5 dark:bg-white/5 hover:bg-slate-400/10 dark:hover:bg-white/10 border border-border"
									)}
								>
									<div
										className={cn(
											"flex h-12 w-12 items-center justify-center rounded-lg border shrink-0",
											isIndexing
												? "bg-primary/10 border-primary/20"
												: "bg-slate-400/5 dark:bg-white/5 border-slate-400/5 dark:border-white/5"
										)}
									>
										{getConnectorIcon(connector.connector_type, "size-6")}
									</div>
									<div className="flex-1 min-w-0">
										<p className="text-[14px] font-semibold leading-tight truncate">
											{getDisplayName(connector)}
										</p>
										{isIndexing ? (
											<p className="text-[11px] text-primary mt-1 flex items-center gap-1.5">
												<Spinner size="xs" />
												Syncing
											</p>
										) : (
											<p className="text-[10px] text-muted-foreground mt-1 whitespace-nowrap truncate">
												{isIndexableConnector(connector.connector_type)
													? connector.last_indexed_at
														? `Last indexed: ${formatRelativeDate(connector.last_indexed_at)}`
														: "Never indexed"
													: "Active"}
											</p>
										)}
									</div>
									<Button
										variant="secondary"
										size="sm"
										className="h-8 text-[11px] px-3 rounded-lg font-medium bg-white text-slate-700 hover:bg-slate-50 border-0 shadow-xs dark:bg-secondary dark:text-secondary-foreground dark:hover:bg-secondary/80 shrink-0"
										onClick={() => onManage(connector)}
									>
										Manage
									</Button>
								</div>
							);
						})}
					</div>
				)}
			</div>
		</div>
	);
};
