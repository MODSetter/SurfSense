"use client";

import { ExternalLink, Info, Zap } from "lucide-react";
import Image from "next/image";
import type { FC } from "react";
import { Badge } from "@/components/ui/badge";
import type { SearchSourceConnector } from "@/contracts/types/connector.types";
import { cn } from "@/lib/utils";

interface ComposioConfigProps {
	connector: SearchSourceConnector;
	onConfigChange?: (config: Record<string, unknown>) => void;
	onNameChange?: (name: string) => void;
}

// Get toolkit display info
const getToolkitInfo = (toolkitId: string): { name: string; icon: string; description: string } => {
	switch (toolkitId) {
		case "googledrive":
			return {
				name: "Google Drive",
				icon: "/connectors/google-drive.svg",
				description: "Files and documents from Google Drive",
			};
		case "gmail":
			return {
				name: "Gmail",
				icon: "/connectors/google-gmail.svg",
				description: "Emails from Gmail",
			};
		case "googlecalendar":
			return {
				name: "Google Calendar",
				icon: "/connectors/google-calendar.svg",
				description: "Events from Google Calendar",
			};
		case "slack":
			return {
				name: "Slack",
				icon: "/connectors/slack.svg",
				description: "Messages from Slack",
			};
		case "notion":
			return {
				name: "Notion",
				icon: "/connectors/notion.svg",
				description: "Pages from Notion",
			};
		case "github":
			return {
				name: "GitHub",
				icon: "/connectors/github.svg",
				description: "Repositories from GitHub",
			};
		default:
			return {
				name: toolkitId,
				icon: "/connectors/composio.svg",
				description: "Connected via Composio",
			};
	}
};

export const ComposioConfig: FC<ComposioConfigProps> = ({ connector }) => {
	const toolkitId = connector.config?.toolkit_id as string;
	const toolkitName = connector.config?.toolkit_name as string;
	const isIndexable = connector.config?.is_indexable as boolean;
	const composioAccountId = connector.config?.composio_connected_account_id as string;

	const toolkitInfo = getToolkitInfo(toolkitId);

	return (
		<div className="space-y-6">
			{/* Toolkit Info Card */}
			<div className="rounded-xl border border-violet-500/20 bg-gradient-to-br from-violet-500/5 to-purple-500/5 p-4">
				<div className="flex items-start gap-4">
					<div className="flex h-12 w-12 items-center justify-center rounded-lg bg-gradient-to-br from-violet-500/10 to-purple-500/10 border border-violet-500/20 shrink-0">
						<Image
							src={toolkitInfo.icon}
							alt={toolkitInfo.name}
							width={24}
							height={24}
							className="size-6"
						/>
					</div>
					<div className="flex-1 min-w-0">
						<div className="flex items-center gap-2 mb-1">
							<h3 className="text-sm font-semibold">{toolkitName || toolkitInfo.name}</h3>
							<Badge
								variant="secondary"
								className="text-[10px] px-1.5 py-0 h-5 bg-violet-500/10 text-violet-600 dark:text-violet-400 border-violet-500/20"
							>
								<Zap className="size-3 mr-0.5" />
								Composio
							</Badge>
						</div>
						<p className="text-xs text-muted-foreground">{toolkitInfo.description}</p>
					</div>
				</div>
			</div>

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

			{/* Info Banner */}
			<div className="rounded-lg border border-border/50 bg-muted/30 p-3">
				<div className="flex items-start gap-2.5">
					<Info className="size-4 text-muted-foreground shrink-0 mt-0.5" />
					<div className="space-y-1">
						<p className="text-xs text-muted-foreground leading-relaxed">
							This connection uses Composio&apos;s managed OAuth, which means you don&apos;t need to
							wait for app verification. Your data is securely accessed through Composio.
						</p>
						<a
							href="https://composio.dev"
							target="_blank"
							rel="noopener noreferrer"
							className="inline-flex items-center gap-1 text-xs text-violet-600 dark:text-violet-400 hover:underline"
						>
							Learn more about Composio
							<ExternalLink className="size-3" />
						</a>
					</div>
				</div>
			</div>
		</div>
	);
};
