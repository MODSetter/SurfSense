"use client";

import type { FC } from "react";
import { Badge } from "@/components/ui/badge";
import type { SearchSourceConnector } from "@/contracts/types/connector.types";
import { cn } from "@/lib/utils";

interface ComposioConfigProps {
	connector: SearchSourceConnector;
	onConfigChange?: (config: Record<string, unknown>) => void;
	onNameChange?: (name: string) => void;
}

export const ComposioConfig: FC<ComposioConfigProps> = ({ connector }) => {
	const toolkitId = connector.config?.toolkit_id as string;
	const isIndexable = connector.config?.is_indexable as boolean;
	const composioAccountId = connector.config?.composio_connected_account_id as string;

	return (
		<div className="space-y-6">
			{/* Connection Details */}
			<div className="space-y-3">
				<h4 className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
					Connection Details
				</h4>
				<div className="space-y-2">
					<div className="flex items-center justify-between py-2 px-3 rounded-lg bg-muted/50">
						<span className="text-xs text-muted-foreground">Toolkit</span>
						<span className="text-xs font-medium">{toolkitId}</span>
					</div>
					<div className="flex items-center justify-between py-2 px-3 rounded-lg bg-muted/50">
						<span className="text-xs text-muted-foreground">Indexing Supported</span>
						<Badge
							variant={isIndexable ? "default" : "secondary"}
							className={cn(
								"text-[10px] px-1.5 py-0 h-5",
								isIndexable
									? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20"
									: "bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/20"
							)}
						>
							{isIndexable ? "Yes" : "Coming Soon"}
						</Badge>
					</div>
					{composioAccountId && (
						<div className="flex items-center justify-between py-2 px-3 rounded-lg bg-muted/50">
							<span className="text-xs text-muted-foreground">Account ID</span>
							<span className="text-xs font-mono text-muted-foreground truncate max-w-[150px]">
								{composioAccountId}
							</span>
						</div>
					)}
				</div>
			</div>
		</div>
	);
};
