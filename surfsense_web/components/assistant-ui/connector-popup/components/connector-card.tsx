"use client";

import { IconBrandYoutube } from "@tabler/icons-react";
import { FileText, Loader2 } from "lucide-react";
import { type FC } from "react";
import { Button } from "@/components/ui/button";
import { getConnectorIcon } from "@/contracts/enums/connectorIcons";
import type { LogActiveTask } from "@/contracts/types/log.types";
import { cn } from "@/lib/utils";

interface ConnectorCardProps {
	id: string;
	title: string;
	description: string;
	connectorType?: string;
	isConnected?: boolean;
	isConnecting?: boolean;
	documentCount?: number;
	isIndexing?: boolean;
	activeTask?: LogActiveTask;
	onConnect?: () => void;
	onManage?: () => void;
}

/**
 * Extract a number from the active task message for display
 * Looks for patterns like "45 indexed", "Processing 123", etc.
 */
function extractIndexedCount(message: string | undefined): number | null {
	if (!message) return null;
	// Try to find a number in the message
	const match = message.match(/(\d+)/);
	return match ? parseInt(match[1], 10) : null;
}

export const ConnectorCard: FC<ConnectorCardProps> = ({
	id,
	title,
	description,
	connectorType,
	isConnected = false,
	isConnecting = false,
	documentCount,
	isIndexing = false,
	activeTask,
	onConnect,
	onManage,
}) => {
	// Extract count from active task message during indexing
	const indexingCount = extractIndexedCount(activeTask?.message);

	// Determine the status content to display
	const getStatusContent = () => {
		if (isIndexing) {
			return (
				<div className="flex items-center gap-2 w-full max-w-[200px]">
					<span className="text-[11px] text-primary font-medium whitespace-nowrap">
						{indexingCount !== null ? (
							<>{indexingCount.toLocaleString()} indexed</>
						) : (
							"Syncing..."
						)}
					</span>
					{/* Indeterminate progress bar with animation */}
					<div className="relative flex-1 h-1 overflow-hidden rounded-full bg-primary/20">
						<div className="absolute h-full bg-primary rounded-full animate-progress-indeterminate" />
					</div>
				</div>
			);
		}

		if (isConnected) {
			if (documentCount !== undefined && documentCount > 0) {
				return (
					<span className="inline-flex items-center gap-1.5">
						<FileText className="size-3 flex-shrink-0" />
						<span className="whitespace-nowrap">
							{documentCount.toLocaleString()} document{documentCount !== 1 ? "s" : ""}
						</span>
					</span>
				);
			}
			// Fallback for connected but no documents yet
			return <span className="whitespace-nowrap">No documents indexed</span>;
		}

		return description;
	};

	return (
		<div className="group relative flex items-center gap-4 p-4 rounded-xl text-left transition-all duration-200 w-full border border-border bg-slate-400/5 dark:bg-white/5 hover:bg-slate-400/10 dark:hover:bg-white/10">
			<div className="flex h-12 w-12 items-center justify-center rounded-lg transition-colors flex-shrink-0 bg-slate-400/5 dark:bg-white/5 border border-slate-400/5 dark:border-white/5">
				{connectorType ? (
					getConnectorIcon(connectorType, "size-6")
				) : id === "youtube-crawler" ? (
					<IconBrandYoutube className="size-6" />
				) : (
					<FileText className="size-6" />
				)}
			</div>
			<div className="flex-1 min-w-0">
				<div className="flex items-center gap-2">
					<span className="text-[14px] font-semibold leading-tight">{title}</span>
				</div>
				<div className="text-[11px] text-muted-foreground mt-1">
					{getStatusContent()}
				</div>
			</div>
			<Button
				size="sm"
				variant={isConnected ? "outline" : "default"}
				className={cn(
					"h-8 text-[11px] px-3 rounded-lg flex-shrink-0 font-medium",
					isConnected && "border-0"
				)}
				onClick={isConnected ? onManage : onConnect}
				disabled={isConnecting || isIndexing}
			>
				{isConnecting ? (
					<Loader2 className="size-3 animate-spin" />
				) : isIndexing ? (
					"Syncing..."
				) : isConnected ? (
					"Manage"
				) : connectorType ? (
					"Connect"
				) : (
					"Add"
				)}
			</Button>
		</div>
	);
};

