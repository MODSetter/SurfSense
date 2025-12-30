"use client";

import { format } from "date-fns";
import { Cable, Loader2 } from "lucide-react";
import { useRouter } from "next/navigation";
import type { FC } from "react";
import { Button } from "@/components/ui/button";
import { getDocumentTypeLabel } from "@/app/dashboard/[search_space_id]/documents/(manage)/components/DocumentTypeIcon";
import { getConnectorIcon } from "@/contracts/enums/connectorIcons";
import type { SearchSourceConnector } from "@/contracts/types/connector.types";
import type { LogSummary, LogActiveTask } from "@/contracts/types/log.types";
import { cn } from "@/lib/utils";
import {
	TabsContent,
	TabsTrigger,
} from "@/components/ui/tabs";

interface ActiveConnectorsTabProps {
	hasSources: boolean;
	totalSourceCount: number;
	activeDocumentTypes: Array<[string, number]>;
	connectors: SearchSourceConnector[];
	indexingConnectorIds: Set<number>;
	logsSummary: LogSummary | undefined;
	searchSpaceId: string;
	onTabChange: (value: string) => void;
}

export const ActiveConnectorsTab: FC<ActiveConnectorsTabProps> = ({
	hasSources,
	activeDocumentTypes,
	connectors,
	indexingConnectorIds,
	logsSummary,
	searchSpaceId,
	onTabChange,
}) => {
	const router = useRouter();

	return (
		<TabsContent value="active" className="m-0">
			{hasSources ? (
				<div className="space-y-6">
					<div className="flex items-center gap-2 mb-4">
						<h3 className="text-sm font-semibold text-muted-foreground">
							Currently Active
						</h3>
					</div>
					<div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
						{activeDocumentTypes.map(([docType, count]) => (
							<div
								key={docType}
								className="flex items-center gap-4 p-4 rounded-xl bg-slate-400/5 dark:bg-white/5 hover:bg-slate-400/10 dark:hover:bg-white/10 border border-border transition-all"
							>
								<div className="flex h-12 w-12 items-center justify-center rounded-lg bg-slate-400/5 dark:bg-white/5 border border-slate-400/5 dark:border-white/5">
									{getConnectorIcon(docType, "size-6")}
								</div>
								<div>
									<p className="text-[14px] font-semibold leading-tight">
										{getDocumentTypeLabel(docType)}
									</p>
									<p className="text-[11px] text-muted-foreground mt-1">
										{count as number} documents indexed
									</p>
								</div>
							</div>
						))}
						{connectors.map((connector) => {
							const isIndexing = indexingConnectorIds.has(connector.id);
							const activeTask = logsSummary?.active_tasks?.find(
								(task: LogActiveTask) =>
									task.source?.includes(`connector_${connector.id}`) ||
									task.source?.includes(`connector-${connector.id}`)
							);

							return (
								<div
									key={`connector-${connector.id}`}
									className={cn(
										"flex items-center gap-4 p-4 rounded-xl border border-border transition-all",
										isIndexing
											? "bg-primary/5 border-primary/20"
											: "bg-slate-400/5 dark:bg-white/5 hover:bg-slate-400/10 dark:hover:bg-white/10"
									)}
								>
									<div
										className={cn(
											"flex h-12 w-12 items-center justify-center rounded-lg border",
											isIndexing
												? "bg-primary/10 border-primary/20"
												: "bg-slate-400/5 dark:bg-white/5 border-slate-400/5 dark:border-white/5"
										)}
									>
										{getConnectorIcon(connector.connector_type, "size-6")}
									</div>
									<div className="flex-1 min-w-0">
										<p className="text-[14px] font-semibold leading-tight truncate">
											{connector.name}
										</p>
										{isIndexing ? (
											<p className="text-[11px] text-primary mt-1 flex items-center gap-1.5">
												<Loader2 className="size-3 animate-spin" />
												Indexing...
												{activeTask?.message && (
													<span className="text-muted-foreground truncate max-w-[150px]">
														• {activeTask.message}
													</span>
												)}
											</p>
										) : (
											<p className="text-[11px] text-muted-foreground mt-1">
												{connector.last_indexed_at
													? `Last indexed: ${format(new Date(connector.last_indexed_at), "MMM d, yyyy")}`
													: "Never indexed"}
											</p>
										)}
									</div>
									<Button
										variant="outline"
										size="sm"
										className="h-8 text-[11px] px-3 rounded-lg font-medium"
										onClick={() =>
											router.push(
												`/dashboard/${searchSpaceId}/connectors/add/${connector.id}`
											)
										}
										disabled={isIndexing}
									>
										{isIndexing ? "Syncing..." : "Manage"}
									</Button>
								</div>
							);
						})}
					</div>
				</div>
			) : (
				<div className="flex flex-col items-center justify-center py-20 text-center">
					<div className="flex h-16 w-16 items-center justify-center rounded-full bg-muted mb-4">
						<Cable className="size-8 text-muted-foreground/50" />
					</div>
					<h4 className="text-lg font-semibold">No active sources</h4>
					<p className="text-sm text-muted-foreground mt-1 max-w-[280px]">
						Connect your first service to start searching across all your data.
					</p>
					<TabsTrigger value="all" className="mt-6 text-primary hover:underline" onClick={() => onTabChange("all")}>
						Browse available connectors
					</TabsTrigger>
				</div>
			)}
		</TabsContent>
	);
};

