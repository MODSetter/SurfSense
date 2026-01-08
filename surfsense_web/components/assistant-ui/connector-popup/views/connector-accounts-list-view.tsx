"use client";

import { differenceInDays, differenceInMinutes, format, isToday, isYesterday } from "date-fns";
import { ArrowLeft, Loader2, Plus } from "lucide-react";
import type { FC } from "react";
import { Button } from "@/components/ui/button";
import { getConnectorIcon } from "@/contracts/enums/connectorIcons";
import type { SearchSourceConnector } from "@/contracts/types/connector.types";
import type { LogActiveTask, LogSummary } from "@/contracts/types/log.types";
import { cn } from "@/lib/utils";
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
	// Filter connectors to only show those of this type
	const typeConnectors = connectors.filter((c) => c.connector_type === connectorType);

	return (
		<div className="flex flex-col h-full">
			{/* Header */}
			<div className="px-4 sm:px-12 pt-6 sm:pt-10 pb-4 border-b border-border/50 bg-muted">
				<div className="flex items-center justify-between gap-4 sm:pr-4">
					<div className="flex items-center gap-4">
						<Button
							variant="ghost"
							size="icon"
							className="size-8 rounded-full shrink-0"
							onClick={onBack}
						>
							<ArrowLeft className="size-4" />
						</Button>
						<div className="flex items-center gap-3">
							<div className="flex h-10 w-10 items-center justify-center rounded-lg bg-slate-400/5 dark:bg-white/5 border border-slate-400/5 dark:border-white/5">
								{getConnectorIcon(connectorType, "size-5")}
							</div>
							<div>
								<h2 className="text-lg font-semibold">{connectorTitle} Accounts</h2>
								<p className="text-xs text-muted-foreground">
									{typeConnectors.length} connected account{typeConnectors.length !== 1 ? "s" : ""}
								</p>
							</div>
						</div>
					</div>
					{/* Add Account Button with dashed border */}
					<button
						type="button"
						onClick={onAddAccount}
						disabled={isConnecting}
						className={cn(
							"flex items-center gap-2 px-3 py-2 rounded-lg mr-4 border-2 border-dashed border-border/70 text-left transition-all duration-200",
							"border-primary/50 hover:bg-primary/5",
							isConnecting && "opacity-50 cursor-not-allowed"
						)}
					>
						<div className="flex h-6 w-6 items-center justify-center rounded-md bg-primary/10 shrink-0">
							{isConnecting ? (
								<Loader2 className="size-3.5 animate-spin text-primary" />
							) : (
								<Plus className="size-3.5 text-primary" />
							)}
						</div>
						<span className="text-[12px] font-medium">
							{isConnecting ? "Connecting..." : "Add Account"}
						</span>
					</button>
				</div>
			</div>

			{/* Content */}
			<div className="flex-1 overflow-y-auto px-4 sm:px-12 py-6 sm:py-8">
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
