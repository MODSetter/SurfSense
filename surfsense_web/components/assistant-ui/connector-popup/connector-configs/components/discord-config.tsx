"use client";

import { AlertCircle, CheckCircle2, Hash, Info, Megaphone, RefreshCw } from "lucide-react";
import { type FC, useCallback, useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { connectorsApiService, type DiscordChannel } from "@/lib/apis/connectors-api.service";
import { cn } from "@/lib/utils";
import type { ConnectorConfigProps } from "../index";

export interface DiscordConfigProps extends ConnectorConfigProps {
	onNameChange?: (name: string) => void;
}

export const DiscordConfig: FC<DiscordConfigProps> = ({ connector }) => {
	const [channels, setChannels] = useState<DiscordChannel[]>([]);
	const [isLoading, setIsLoading] = useState(false);
	const [error, setError] = useState<string | null>(null);
	const [lastFetched, setLastFetched] = useState<Date | null>(null);

	const fetchChannels = useCallback(async () => {
		if (!connector?.id) return;

		setIsLoading(true);
		setError(null);

		try {
			const data = await connectorsApiService.getDiscordChannels(connector.id);
			setChannels(data);
			setLastFetched(new Date());
		} catch (err) {
			console.error("Failed to fetch Discord channels:", err);
			setError(err instanceof Error ? err.message : "Failed to fetch channels");
		} finally {
			setIsLoading(false);
		}
	}, [connector?.id]);

	// Fetch channels on mount
	useEffect(() => {
		fetchChannels();
	}, [fetchChannels]);

	// Auto-refresh when user returns to tab
	useEffect(() => {
		const handleVisibilityChange = () => {
			if (document.visibilityState === "visible" && connector?.id) {
				fetchChannels();
			}
		};

		document.addEventListener("visibilitychange", handleVisibilityChange);
		return () => document.removeEventListener("visibilitychange", handleVisibilityChange);
	}, [connector?.id, fetchChannels]);

	// Separate channels by indexing capability
	const readyToIndex = channels.filter((ch) => ch.can_index);
	const needsPermissions = channels.filter((ch) => !ch.can_index);

	// Format last fetched time
	const formatLastFetched = () => {
		if (!lastFetched) return null;
		const now = new Date();
		const diffMs = now.getTime() - lastFetched.getTime();
		const diffSecs = Math.floor(diffMs / 1000);
		const diffMins = Math.floor(diffSecs / 60);

		if (diffSecs < 60) return "just now";
		if (diffMins === 1) return "1 minute ago";
		if (diffMins < 60) return `${diffMins} minutes ago`;
		return lastFetched.toLocaleTimeString();
	};

	return (
		<div className="space-y-6">
			{/* Info box */}
			<div className="rounded-xl border border-border bg-primary/5 p-4 flex items-start gap-3">
				<div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/10 shrink-0 mt-0.5">
					<Info className="size-4" />
				</div>
				<div className="text-xs sm:text-sm">
					<p className="text-muted-foreground mt-1 text-[10px] sm:text-sm">
						The bot needs &quot;Read Message History&quot; permission to index channels. Ask a
						server admin to grant this permission for channels shown below.
					</p>
				</div>
			</div>

			{/* Channels Section */}
			<div className="space-y-3">
				<div className="flex items-center justify-between">
					<div className="flex items-center gap-3">
						<h3 className="text-sm font-semibold">Channel Access</h3>
					</div>
					<div className="flex items-center gap-2">
						{lastFetched && (
							<span className="text-[10px] text-muted-foreground">{formatLastFetched()}</span>
						)}
						<Button
							variant="secondary"
							size="sm"
							onClick={fetchChannels}
							disabled={isLoading}
							className="h-7 px-2.5 text-[11px] bg-slate-400/10 dark:bg-white/10 hover:bg-slate-400/20 dark:hover:bg-white/20 border-slate-400/20 dark:border-white/20"
						>
							<RefreshCw className={cn("mr-1.5 size-3", isLoading && "animate-spin")} />
							Refresh
						</Button>
					</div>
				</div>

				{error && (
					<div className="rounded-lg border border-destructive/50 bg-destructive/10 p-3 text-xs text-destructive">
						{error}
					</div>
				)}

				{isLoading && channels.length === 0 ? (
					<div className="flex items-center justify-center py-8">
						<Spinner size="sm" />
						<span className="ml-2 text-sm text-muted-foreground">Loading channels</span>
					</div>
				) : channels.length === 0 && !error ? (
					<div className="text-center py-8 text-sm text-muted-foreground">
						No channels found. Make sure the bot has been added to your Discord server with proper
						permissions.
					</div>
				) : (
					<div className="rounded-xl bg-slate-400/5 dark:bg-white/5 overflow-hidden">
						{/* Ready to index */}
						{readyToIndex.length > 0 && (
							<div className={cn("p-3", needsPermissions.length > 0 && "border-b border-border")}>
								<div className="flex items-center gap-2 mb-2">
									<CheckCircle2 className="size-3.5 text-emerald-500" />
									<span className="text-[11px] font-medium">Ready to index</span>
									<span className="text-[10px] text-muted-foreground">
										{readyToIndex.length} {readyToIndex.length === 1 ? "channel" : "channels"}
									</span>
								</div>
								<div className="flex flex-wrap gap-1.5">
									{readyToIndex.map((channel) => (
										<ChannelPill key={channel.id} channel={channel} />
									))}
								</div>
							</div>
						)}

						{/* Needs permissions */}
						{needsPermissions.length > 0 && (
							<div className="p-3">
								<div className="flex items-center gap-2 mb-2">
									<AlertCircle className="size-3.5 text-amber-500" />
									<span className="text-[11px] font-medium">Grant permissions to index</span>
									<span className="text-[10px] text-muted-foreground">
										{needsPermissions.length}{" "}
										{needsPermissions.length === 1 ? "channel" : "channels"}
									</span>
								</div>
								<div className="flex flex-wrap gap-1.5">
									{needsPermissions.map((channel) => (
										<ChannelPill key={channel.id} channel={channel} />
									))}
								</div>
							</div>
						)}
					</div>
				)}
			</div>
		</div>
	);
};

interface ChannelPillProps {
	channel: DiscordChannel;
}

const ChannelPill: FC<ChannelPillProps> = ({ channel }) => {
	return (
		<div className="inline-flex items-center gap-1 px-2 py-1 rounded-md text-[11px] font-medium bg-slate-400/10 dark:bg-white/10 hover:bg-slate-400/20 dark:hover:bg-white/20 transition-colors">
			{channel.type === "announcement" ? (
				<Megaphone className="size-2.5 text-muted-foreground" />
			) : (
				<Hash className="size-2.5 text-muted-foreground" />
			)}
			<span>{channel.name}</span>
		</div>
	);
};
