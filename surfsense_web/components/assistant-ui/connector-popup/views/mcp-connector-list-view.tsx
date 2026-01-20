"use client";

import { Plus, Server, XCircle } from "lucide-react";
import type { FC } from "react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { EnumConnectorName } from "@/contracts/enums/connector";
import { getConnectorIcon } from "@/contracts/enums/connectorIcons";
import type { SearchSourceConnector } from "@/contracts/types/connector.types";
import { cn } from "@/lib/utils";

interface MCPConnectorListViewProps {
	mcpConnectors: SearchSourceConnector[];
	onAddNew: () => void;
	onManageConnector: (connector: SearchSourceConnector) => void;
	onBack: () => void;
}

export const MCPConnectorListView: FC<MCPConnectorListViewProps> = ({
	mcpConnectors,
	onAddNew,
	onManageConnector,
	onBack,
}) => {
	// Validate that all connectors are MCP connectors
	const invalidConnectors = mcpConnectors.filter(
		(c) => c.connector_type !== EnumConnectorName.MCP_CONNECTOR
	);

	if (invalidConnectors.length > 0) {
		console.error(
			"MCPConnectorListView received non-MCP connectors:",
			invalidConnectors.map((c) => c.connector_type)
		);
		return (
			<Alert className="border-red-500/50 bg-red-500/10">
				<XCircle className="h-4 w-4 text-red-600" />
				<AlertTitle>Invalid Connector Type</AlertTitle>
				<AlertDescription>
					This view can only display MCP connectors. Found {invalidConnectors.length} invalid
					connector(s).
				</AlertDescription>
			</Alert>
		);
	}
	return (
		<div className="flex flex-col h-full">
			{/* Header */}
			<div className="flex items-center justify-between mb-6 shrink-0">
				<div className="flex items-center gap-3">
					<Button variant="ghost" size="icon" onClick={onBack} className="h-8 w-8">
						<svg
							xmlns="http://www.w3.org/2000/svg"
							width="16"
							height="16"
							viewBox="0 0 24 24"
							fill="none"
							stroke="currentColor"
							strokeWidth="2"
							strokeLinecap="round"
							strokeLinejoin="round"
						>
							<path d="m15 18-6-6 6-6" />
						</svg>
					</Button>
					<div>
						<h2 className="text-lg sm:text-xl font-semibold">MCP Connectors</h2>
						<p className="text-xs sm:text-sm text-muted-foreground">
							Manage your Model Context Protocol servers
						</p>
					</div>
				</div>
			</div>

			{/* Add New Button */}
			<div className="mb-4 shrink-0">
				<Button onClick={onAddNew} className="w-full" variant="outline">
					<Plus className="h-4 w-4 mr-2" />
					Add New MCP Server
				</Button>
			</div>

			{/* MCP Connectors List */}
			<div className="space-y-3 flex-1 overflow-y-auto">
				{mcpConnectors.length === 0 ? (
					<div className="flex flex-col items-center justify-center py-12 text-center">
						<div className="h-16 w-16 rounded-full bg-slate-400/5 dark:bg-white/5 flex items-center justify-center mb-4">
							<Server className="h-8 w-8 text-muted-foreground" />
						</div>
						<h3 className="text-sm font-medium mb-1">No MCP Servers</h3>
						<p className="text-xs text-muted-foreground max-w-[280px]">
							Get started by adding your first Model Context Protocol server
						</p>
					</div>
				) : (
					mcpConnectors.map((connector) => {
						// Extract server name from config
						const serverName = connector.config?.server_config?.name || connector.name;

						return (
							<div
								key={connector.id}
								className={cn(
									"flex items-center gap-4 p-4 rounded-xl border border-border transition-all",
									"bg-slate-400/5 dark:bg-white/5 hover:bg-slate-400/10 dark:hover:bg-white/10"
								)}
							>
								<div
									className={cn(
										"flex h-12 w-12 items-center justify-center rounded-lg border shrink-0",
										"bg-slate-400/5 dark:bg-white/5 border-slate-400/5 dark:border-white/5"
									)}
								>
									{getConnectorIcon("MCP_CONNECTOR", "size-6")}
								</div>
								<div className="flex-1 min-w-0">
									<p className="text-[14px] font-semibold leading-tight truncate">{serverName}</p>
								</div>
								<Button
									variant="secondary"
									size="sm"
									className="h-8 text-[11px] px-3 rounded-lg font-medium bg-white text-slate-700 hover:bg-slate-50 border-0 shadow-xs dark:bg-secondary dark:text-secondary-foreground dark:hover:bg-secondary/80 shrink-0"
									onClick={() => onManageConnector(connector)}
								>
									Manage
								</Button>
							</div>
						);
					})
				)}
			</div>
		</div>
	);
};
