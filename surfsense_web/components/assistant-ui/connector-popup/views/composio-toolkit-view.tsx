"use client";

import {
	ArrowLeft,
	Calendar,
	Check,
	ExternalLink,
	FileText,
	Github,
	HardDrive,
	Loader2,
	Mail,
	MessageSquare,
	Zap,
} from "lucide-react";
import Image from "next/image";
import type { FC } from "react";
import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface ComposioToolkit {
	id: string;
	name: string;
	description: string;
	isIndexable: boolean;
}

interface ComposioToolkitViewProps {
	searchSpaceId: string;
	connectedToolkits: string[];
	onBack: () => void;
	onConnectToolkit: (toolkitId: string) => void;
	isConnecting: boolean;
	connectingToolkitId: string | null;
}

// Available Composio toolkits
const COMPOSIO_TOOLKITS: ComposioToolkit[] = [
	{
		id: "googledrive",
		name: "Google Drive",
		description: "Search your Drive files and documents",
		isIndexable: true,
	},
	{
		id: "gmail",
		name: "Gmail",
		description: "Search through your emails",
		isIndexable: true,
	},
	{
		id: "googlecalendar",
		name: "Google Calendar",
		description: "Search through your events",
		isIndexable: true,
	},
	{
		id: "slack",
		name: "Slack",
		description: "Search Slack messages",
		isIndexable: false,
	},
	{
		id: "notion",
		name: "Notion",
		description: "Search Notion pages",
		isIndexable: false,
	},
	{
		id: "github",
		name: "GitHub",
		description: "Search repositories and code",
		isIndexable: false,
	},
];

// Get icon for toolkit
const getToolkitIcon = (toolkitId: string, className?: string) => {
	const iconClass = className || "size-5";

	switch (toolkitId) {
		case "googledrive":
			return (
				<Image
					src="/connectors/google-drive.svg"
					alt="Google Drive"
					width={20}
					height={20}
					className={iconClass}
				/>
			);
		case "gmail":
			return (
				<Image
					src="/connectors/google-gmail.svg"
					alt="Gmail"
					width={20}
					height={20}
					className={iconClass}
				/>
			);
		case "googlecalendar":
			return (
				<Image
					src="/connectors/google-calendar.svg"
					alt="Google Calendar"
					width={20}
					height={20}
					className={iconClass}
				/>
			);
		case "slack":
			return (
				<Image
					src="/connectors/slack.svg"
					alt="Slack"
					width={20}
					height={20}
					className={iconClass}
				/>
			);
		case "notion":
			return (
				<Image
					src="/connectors/notion.svg"
					alt="Notion"
					width={20}
					height={20}
					className={iconClass}
				/>
			);
		case "github":
			return (
				<Image
					src="/connectors/github.svg"
					alt="GitHub"
					width={20}
					height={20}
					className={iconClass}
				/>
			);
		default:
			return <Zap className={iconClass} />;
	}
};

export const ComposioToolkitView: FC<ComposioToolkitViewProps> = ({
	searchSpaceId,
	connectedToolkits,
	onBack,
	onConnectToolkit,
	isConnecting,
	connectingToolkitId,
}) => {
	const [hoveredToolkit, setHoveredToolkit] = useState<string | null>(null);

	// Separate indexable and non-indexable toolkits
	const indexableToolkits = COMPOSIO_TOOLKITS.filter((t) => t.isIndexable);
	const nonIndexableToolkits = COMPOSIO_TOOLKITS.filter((t) => !t.isIndexable);

	return (
		<div className="flex flex-col h-full">
			{/* Header */}
			<div className="px-6 sm:px-12 pt-8 sm:pt-10 pb-4 sm:pb-6 border-b border-border/50 bg-muted">
				{/* Back button */}
				<button
					type="button"
					onClick={onBack}
					className="flex items-center gap-2 text-xs sm:text-sm text-muted-foreground hover:text-foreground mb-6 w-fit transition-colors"
				>
					<ArrowLeft className="size-4" />
					Back to connectors
				</button>

				{/* Header content */}
				<div className="flex flex-col sm:flex-row items-start sm:items-center gap-4">
					<div className="flex gap-4 flex-1 w-full sm:w-auto">
						<div className="flex h-14 w-14 items-center justify-center rounded-xl bg-gradient-to-br from-violet-500/20 to-purple-500/20 border border-violet-500/30 shrink-0">
							<Image
								src="/connectors/composio.svg"
								alt="Composio"
								width={28}
								height={28}
								className="size-7"
							/>
						</div>
						<div className="flex-1 min-w-0">
							<h2 className="text-xl sm:text-2xl font-semibold tracking-tight">Composio</h2>
							<p className="text-xs sm:text-sm text-muted-foreground mt-1">
								Connect 100+ apps with managed OAuth - no verification needed
							</p>
						</div>
					</div>
					<a
						href="https://composio.dev"
						target="_blank"
						rel="noopener noreferrer"
						className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors"
					>
						<span>Powered by Composio</span>
						<ExternalLink className="size-3" />
					</a>
				</div>
			</div>

			{/* Content */}
			<div className="flex-1 overflow-y-auto px-6 sm:px-12 py-6 sm:py-8">
				{/* Indexable Toolkits (Google Services) */}
				<section className="mb-8">
					<div className="flex items-center gap-2 mb-4">
						<h3 className="text-sm font-semibold text-foreground">Google Services</h3>
						<Badge
							variant="secondary"
							className="text-[10px] px-1.5 py-0 h-5 bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20"
						>
							Indexable
						</Badge>
					</div>
					<p className="text-xs text-muted-foreground mb-4">
						Connect Google services via Composio&apos;s verified OAuth app. Your data will be
						indexed and searchable.
					</p>
					<div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
						{indexableToolkits.map((toolkit) => {
							const isConnected = connectedToolkits.includes(toolkit.id);
							const isThisConnecting = connectingToolkitId === toolkit.id;

							return (
								<div
									key={toolkit.id}
									onMouseEnter={() => setHoveredToolkit(toolkit.id)}
									onMouseLeave={() => setHoveredToolkit(null)}
									className={cn(
										"group relative flex flex-col p-4 rounded-xl border transition-all duration-200",
										isConnected
											? "border-emerald-500/30 bg-emerald-500/5"
											: "border-border bg-card hover:border-violet-500/30 hover:bg-violet-500/5"
									)}
								>
									<div className="flex items-start justify-between mb-3">
										<div
											className={cn(
												"flex h-10 w-10 items-center justify-center rounded-lg border transition-colors",
												isConnected
													? "bg-emerald-500/10 border-emerald-500/20"
													: "bg-muted border-border group-hover:border-violet-500/20 group-hover:bg-violet-500/10"
											)}
										>
											{getToolkitIcon(toolkit.id, "size-5")}
										</div>
										{isConnected && (
											<Badge
												variant="secondary"
												className="text-[10px] px-1.5 py-0 h-5 bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20"
											>
												<Check className="size-3 mr-0.5" />
												Connected
											</Badge>
										)}
									</div>
									<h4 className="text-sm font-medium mb-1">{toolkit.name}</h4>
									<p className="text-xs text-muted-foreground mb-4 flex-1">{toolkit.description}</p>
									<Button
										size="sm"
										variant={isConnected ? "secondary" : "default"}
										className={cn(
											"w-full h-8 text-xs font-medium",
											!isConnected && "bg-violet-600 hover:bg-violet-700 text-white"
										)}
										onClick={() => onConnectToolkit(toolkit.id)}
										disabled={isConnecting || isConnected}
									>
										{isThisConnecting ? (
											<>
												<Loader2 className="size-3 mr-1.5 animate-spin" />
												Connecting...
											</>
										) : isConnected ? (
											"Connected"
										) : (
											"Connect"
										)}
									</Button>
								</div>
							);
						})}
					</div>
				</section>

				{/* Non-Indexable Toolkits (Coming Soon) */}
				<section>
					<div className="flex items-center gap-2 mb-4">
						<h3 className="text-sm font-semibold text-foreground">More Integrations</h3>
						<Badge
							variant="secondary"
							className="text-[10px] px-1.5 py-0 h-5 bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/20"
						>
							Coming Soon
						</Badge>
					</div>
					<p className="text-xs text-muted-foreground mb-4">
						Connect these services for future indexing support. Currently available for connection
						only.
					</p>
					<div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 opacity-60">
						{nonIndexableToolkits.map((toolkit) => (
							<div
								key={toolkit.id}
								className="group relative flex flex-col p-4 rounded-xl border border-border bg-card/50"
							>
								<div className="flex items-start justify-between mb-3">
									<div className="flex h-10 w-10 items-center justify-center rounded-lg border bg-muted border-border">
										{getToolkitIcon(toolkit.id, "size-5")}
									</div>
									<Badge variant="outline" className="text-[10px] px-1.5 py-0 h-5">
										Soon
									</Badge>
								</div>
								<h4 className="text-sm font-medium mb-1">{toolkit.name}</h4>
								<p className="text-xs text-muted-foreground mb-4 flex-1">{toolkit.description}</p>
								<Button
									size="sm"
									variant="outline"
									className="w-full h-8 text-xs font-medium"
									disabled
								>
									Coming Soon
								</Button>
							</div>
						))}
					</div>
				</section>

				{/* Info footer */}
				<div className="mt-8 p-4 rounded-xl bg-muted/50 border border-border/50">
					<div className="flex items-start gap-3">
						<div className="flex h-8 w-8 items-center justify-center rounded-lg bg-violet-500/10 border border-violet-500/20 shrink-0">
							<Zap className="size-4 text-violet-500" />
						</div>
						<div>
							<h4 className="text-sm font-medium mb-1">Why use Composio?</h4>
							<p className="text-xs text-muted-foreground leading-relaxed">
								Composio provides pre-verified OAuth apps, so you don&apos;t need to wait for Google
								app verification. Your data is securely processed through Composio&apos;s managed
								authentication.
							</p>
						</div>
					</div>
				</div>
			</div>
		</div>
	);
};
