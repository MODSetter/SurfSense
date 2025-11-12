"use client";

import { useAtom, useAtomValue } from "jotai";
import { AlertCircle, Play, RefreshCw, Sparkles } from "lucide-react";
import { motion } from "motion/react";
import { useCallback } from "react";
import { cn } from "@/lib/utils";
import { activeChatAtom } from "@/atoms/chats/chat-queries.atom";
import { chatUIAtom } from "@/atoms/chats/chat-uis.atom";
import { getPodcastStalenessMessage, isPodcastStale } from "../PodcastUtils";
import type { GeneratePodcastRequest } from "./ChatPanelContainer";
import { ConfigModal } from "./ConfigModal";
import { PodcastPlayer } from "./PodcastPlayer";

interface ChatPanelViewProps {
	generatePodcast: (request: GeneratePodcastRequest) => Promise<void>;
}

export function ChatPanelView(props: ChatPanelViewProps) {
	const [chatUIState, setChatUIState] = useAtom(chatUIAtom);
	const { data: activeChatState } = useAtomValue(activeChatAtom);

	const { isChatPannelOpen } = chatUIState;
	const podcast = activeChatState?.podcast;
	const chatDetails = activeChatState?.chatDetails;

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
			<div className={cn("w-full p-4", !isChatPannelOpen && "flex items-center justify-center")}>
				{isChatPannelOpen ? (
					<div className="space-y-3">
						{/* Show stale podcast warning if applicable */}
						{podcastIsStale && (
							<motion.div
								initial={{ opacity: 0, y: -10 }}
								animate={{ opacity: 1, y: 0 }}
								className="rounded-xl p-3 bg-gradient-to-br from-amber-50 to-orange-50 dark:from-amber-950/30 dark:to-orange-950/20 border border-amber-200/50 dark:border-amber-800/50 shadow-sm"
							>
								<div className="flex gap-2 items-start">
									<motion.div
										animate={{ rotate: [0, 10, -10, 0] }}
										transition={{ duration: 0.5, repeat: Infinity, repeatDelay: 3 }}
									>
										<AlertCircle className="h-4 w-4 text-amber-600 dark:text-amber-400 mt-0.5 flex-shrink-0" />
									</motion.div>
									<div className="text-sm text-amber-900 dark:text-amber-100">
										<p className="font-semibold">Podcast Outdated</p>
										<p className="text-xs mt-1 opacity-80">
											{getPodcastStalenessMessage(
												chatDetails?.state_version || 0,
												podcast?.chat_state_version
											)}
										</p>
									</div>
								</div>
							</motion.div>
						)}

						<motion.div
							whileHover={{ scale: 1.02 }}
							whileTap={{ scale: 0.98 }}
							initial={{ opacity: 0 }}
							animate={{ opacity: 1 }}
							transition={{ duration: 0.3 }}
							className="relative"
						>
							<button
								type="button"
								onClick={handleGeneratePost}
								className={cn(
									"relative w-full rounded-2xl p-4 transition-all duration-300 cursor-pointer group overflow-hidden",
									"border-2",
									podcastIsStale
										? "bg-gradient-to-br from-amber-500/10 via-orange-500/10 to-amber-500/10 dark:from-amber-500/20 dark:via-orange-500/20 dark:to-amber-500/20 border-amber-400/50 hover:border-amber-400 hover:shadow-lg hover:shadow-amber-500/20"
										: "bg-gradient-to-br from-primary/10 via-primary/5 to-primary/10 border-primary/30 hover:border-primary/60 hover:shadow-lg hover:shadow-primary/20"
								)}
							>
								{/* Background gradient animation */}
								<motion.div
									className={cn(
										"absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity duration-500",
										podcastIsStale
											? "bg-gradient-to-r from-transparent via-amber-400/10 to-transparent"
											: "bg-gradient-to-r from-transparent via-primary/10 to-transparent"
									)}
									animate={{
										x: ["-100%", "100%"],
									}}
									transition={{
										duration: 3,
										repeat: Infinity,
										ease: "linear",
									}}
								/>

								<div className="relative z-10 space-y-3">
									<div className="flex items-center justify-between">
										<div className="flex items-center gap-3">
											<motion.div
												className={cn(
													"p-2.5 rounded-xl",
													podcastIsStale
														? "bg-amber-500/20 dark:bg-amber-500/30"
														: "bg-primary/20 dark:bg-primary/30"
												)}
												animate={{
													rotate: podcastIsStale ? [0, 360] : 0,
												}}
												transition={{
													duration: 2,
													repeat: podcastIsStale ? Infinity : 0,
													ease: "linear",
												}}
											>
												{podcastIsStale ? (
													<RefreshCw className="h-5 w-5 text-amber-600 dark:text-amber-400" />
												) : (
													<Sparkles className="h-5 w-5 text-primary" />
												)}
											</motion.div>
											<div>
												<p className="text-sm font-semibold">
													{podcastIsStale ? "Regenerate Podcast" : "Generate Podcast"}
												</p>
												<p className="text-xs text-muted-foreground">
													{podcastIsStale
														? "Update with latest changes"
														: "Create podcasts of your chat"}
												</p>
											</div>
										</div>
									</div>
								</div>
							</button>
							{/* ConfigModal positioned absolutely to avoid nesting buttons */}
							<div className="absolute top-4 right-4 z-20">
								<ConfigModal generatePodcast={generatePodcast} />
							</div>
						</motion.div>
					</div>
				) : (
					<motion.button
						title={podcastIsStale ? "Regenerate Podcast" : "Generate Podcast"}
						type="button"
						onClick={() =>
							setChatUIState((prev) => ({
								...prev,
								isChatPannelOpen: !isChatPannelOpen,
							}))
						}
						whileHover={{ scale: 1.1 }}
						whileTap={{ scale: 0.9 }}
						className={cn(
							"p-2.5 rounded-full transition-colors shadow-sm",
							podcastIsStale
								? "bg-amber-500/20 hover:bg-amber-500/30 text-amber-600 dark:text-amber-400"
								: "bg-primary/20 hover:bg-primary/30 text-primary"
						)}
					>
						{podcastIsStale ? <RefreshCw className="h-5 w-5" /> : <Sparkles className="h-5 w-5" />}
					</motion.button>
				)}
			</div>
			{podcast ? (
				<div
					className={cn(
						"w-full border-t",
						!isChatPannelOpen && "flex items-center justify-center p-4"
					)}
				>
					{isChatPannelOpen ? (
						<PodcastPlayer compact podcast={podcast} />
					) : podcast ? (
						<motion.button
							title="Play Podcast"
							type="button"
							onClick={() => setChatUIState((prev) => ({ ...prev, isChatPannelOpen: true }))}
							whileHover={{ scale: 1.1 }}
							whileTap={{ scale: 0.9 }}
							className="p-2.5 rounded-full bg-green-500/20 hover:bg-green-500/30 text-green-600 dark:text-green-400 transition-colors shadow-sm"
						>
							<Play className="h-5 w-5" />
						</motion.button>
					) : null}
				</div>
			) : null}
		</div>
	);
}
