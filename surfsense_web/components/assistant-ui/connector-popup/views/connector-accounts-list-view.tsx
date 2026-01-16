"use client";

import { differenceInDays, differenceInMinutes, format, isToday, isYesterday } from "date-fns";
import { ArrowLeft, Loader2, Plus } from "lucide-react";
import type { FC } from "react";
import { Button } from "@/components/ui/button";
import { getConnectorIcon } from "@/contracts/enums/connectorIcons";
import type { SearchSourceConnector } from "@/contracts/types/connector.types";
import type { LogActiveTask, LogSummary } from "@/contracts/types/log.types";
import { cn } from "@/lib/utils";
import { useConnectorStatus } from "../hooks/use-connector-status";
import { getConnectorDisplayName } from "../tabs/all-connectors-tab";

interface ConnectorAccountsListViewProps {
	connectorType: string;
	connectorTitle: string;
	connectors: SearchSourceConnector[];
	indexingConnectorIds: Set<number>;
	logsSummary: LogSummary | undefined;
	onBack: () => void;
	onManage: (connector: SearchSourceConnector) => void;
	onAddAccount: () => void;
	isConnecting?: boolean;
}

/**
 * Format last indexed date with contextual messages
 */
function formatLastIndexedDate(dateString: string): string {
	const date = new Date(dateString);
	const now = new Date();
	const minutesAgo = differenceInMinutes(now, date);
	const daysAgo = differenceInDays(now, date);

	if (minutesAgo < 1) {
		return "Just now";
	}

	if (minutesAgo < 60) {
		return `${minutesAgo} ${minutesAgo === 1 ? "minute" : "minutes"} ago`;
	}

	if (isToday(date)) {
		return `Today at ${format(date, "h:mm a")}`;
	}

	if (isYesterday(date)) {
		return `Yesterday at ${format(date, "h:mm a")}`;
	}

	if (daysAgo < 7) {
		return `${daysAgo} ${daysAgo === 1 ? "day" : "days"} ago`;
	}

	return format(date, "MMM d, yyyy");
}

export const ConnectorAccountsListView: FC<ConnectorAccountsListViewProps> = ({
	connectorType,
	connectorTitle,
	connectors,
	indexingConnectorIds,
	logsSummary,
	onBack,
	onManage,
	onAddAccount,
	isConnecting = false,
}) => {
	// Get connector status
	const { isConnectorEnabled, getConnectorStatusMessage } = useConnectorStatus();

	const isEnabled = isConnectorEnabled(connectorType);
	const statusMessage = getConnectorStatusMessage(connectorType);

	// Filter connectors to only show those of this type
	const typeConnectors = connectors.filter((c) => c.connector_type === connectorType);

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
							"flex items-center gap-1.5 sm:gap-2 px-2 sm:px-3 py-1.5 sm:py-2 rounded-lg border-2 border-dashed text-left transition-all duration-200 shrink-0 self-center sm:self-auto sm:w-auto",
							!isEnabled
								? "border-border/30 opacity-50 cursor-not-allowed"
								: "border-primary/50 hover:bg-primary/5",
							isConnecting && "opacity-50 cursor-not-allowed"
						)}
					>
						<div className="flex h-5 w-5 sm:h-6 sm:w-6 items-center justify-center rounded-md bg-primary/10 shrink-0">
							{isConnecting ? (
								<Loader2 className="size-3 sm:size-3.5 animate-spin text-primary" />
							) : (
								<Plus className="size-3 sm:size-3.5 text-primary" />
							)}
						</div>
						<span className="text-[11px] sm:text-[12px] font-medium">
							{isConnecting ? "Connecting..." : "Add Account"}
						</span>
					</button>
				</div>
			</div>

			{/* Content */}
			<div className="flex-1 overflow-y-auto px-6 sm:px-12 pt-0 sm:pt-6 pb-6 sm:pb-8">
				{/* Connected Accounts Grid */}
				<div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
					{typeConnectors.map((connector) => {
						const isIndexing = indexingConnectorIds.has(connector.id);
						const activeTask = logsSummary?.active_tasks?.find(
							(task: LogActiveTask) => task.connector_id === connector.id
						);

						return (
							<div
								key={connector.id}
								className={cn(
									"flex items-center gap-4 p-4 rounded-xl border border-border transition-all",
									isIndexing
										? "bg-primary/5 border-primary/20"
										: "bg-slate-400/5 dark:bg-white/5 hover:bg-slate-400/10 dark:hover:bg-white/10"
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
										{getConnectorDisplayName(connector.name)}
									</p>
									{isIndexing ? (
										<p className="text-[11px] text-primary mt-1 flex items-center gap-1.5">
											<Loader2 className="size-3 animate-spin" />
											Indexing...
											{activeTask?.message && (
												<span className="text-muted-foreground truncate max-w-[100px]">
													• {activeTask.message}
												</span>
											)}
										</p>
									) : (
										<p className="text-[10px] text-muted-foreground mt-1 whitespace-nowrap truncate">
											{connector.last_indexed_at
												? `Last indexed: ${formatLastIndexedDate(connector.last_indexed_at)}`
												: "Never indexed"}
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
			</div>
		</div>
	);
};
