"use client";

import { AlertCircle, Pencil, Podcast, RefreshCw } from "lucide-react";
import { useCallback, useContext, useTransition } from "react";
import { cn } from "@/lib/utils";
import { chatInterfaceContext } from "../ChatInterface";
import { getPodcastStalenessMessage, isPodcastStale } from "../PodcastUtils";
import type { GeneratePodcastRequest } from "./ChatPanelContainer";
import { ConfigModal } from "./ConfigModal";

interface ChatPanelViewProps {
	generatePodcast: (request: GeneratePodcastRequest) => Promise<void>;
}

export function ChatPanelView(props: ChatPanelViewProps) {
	const context = useContext(chatInterfaceContext);
	if (!context) {
		throw new Error("chatInterfaceContext must be used within a ChatProvider");
	}

	const { isChatPannelOpen, setIsChatPannelOpen, chatDetails, podcast } = context;
	const { generatePodcast } = props;

	// Check if podcast is stale
	const podcastIsStale =
		podcast && chatDetails && isPodcastStale(chatDetails.state_version, podcast.chat_state_version);

	const handleGeneratePost = useCallback(async () => {
		if (!chatDetails) return;
		await generatePodcast({
			type: "CHAT",
			ids: [chatDetails.id],
			search_space_id: chatDetails.search_space_id,
			podcast_title: chatDetails.title,
		});
	}, [chatDetails, generatePodcast]);

	return (
		<div className="w-full">
			<div
				className={cn(
					"w-full cursor-pointer h-full p-4 border-b",
					!isChatPannelOpen && "flex items-center justify-center"
				)}
				title={podcastIsStale ? "Regenerate Podcast" : "Generate Podcast"}
			>
				{isChatPannelOpen ? (
					<div className="space-y-3">
						{/* Show stale podcast warning if applicable */}
						{podcastIsStale && (
							<div className="rounded-lg p-3 bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-800">
								<div className="flex gap-2 items-start">
									<AlertCircle className="h-4 w-4 text-amber-600 dark:text-amber-500 mt-0.5 flex-shrink-0" />
									<div className="text-sm text-amber-800 dark:text-amber-200">
										<p className="font-medium">Podcast is outdated</p>
										<p className="text-xs mt-1 opacity-90">
											{getPodcastStalenessMessage(
												chatDetails?.state_version || 0,
												podcast?.chat_state_version
											)}
										</p>
									</div>
								</div>
							</div>
						)}

						<div
							role="button"
							tabIndex={0}
							onClick={handleGeneratePost}
							onKeyDown={(e) => {
								if (e.key === "Enter" || e.key === " ") {
									e.preventDefault();
									handleGeneratePost();
								}
							}}
							className={cn(
								"w-full space-y-3 rounded-xl p-3 transition-colors",
								podcastIsStale
									? "bg-gradient-to-r from-amber-400/50 to-orange-300/50 dark:from-amber-500/30 dark:to-orange-600/30 hover:from-amber-400/60 hover:to-orange-300/60"
									: "bg-gradient-to-r from-slate-400/50 to-slate-200/50 dark:from-slate-400/30 dark:to-slate-800/60 hover:from-slate-400/60 hover:to-slate-200/60"
							)}
						>
							<div className="w-full flex items-center justify-between">
								{podcastIsStale ? (
									<RefreshCw strokeWidth={1} className="h-5 w-5" />
								) : (
									<Podcast strokeWidth={1} className="h-5 w-5" />
								)}
								<ConfigModal generatePodcast={generatePodcast} />
							</div>
							<p className="text-sm font-medium text-left">
								{podcastIsStale ? "Regenerate Podcast" : "Generate Podcast"}
							</p>
						</div>
					</div>
				) : (
					<button
						title={podcastIsStale ? "Regenerate Podcast" : "Generate Podcast"}
						type="button"
						onClick={() => setIsChatPannelOpen(!isChatPannelOpen)}
						className={cn(
							"p-2 rounded-full hover:bg-muted transition-colors",
							podcastIsStale && "text-amber-600 dark:text-amber-500"
						)}
					>
						{podcastIsStale ? (
							<RefreshCw strokeWidth={1} className="h-5 w-5" />
						) : (
							<Podcast strokeWidth={1} className="h-5 w-5" />
						)}
					</button>
				)}
			</div>
		</div>
	);
}
