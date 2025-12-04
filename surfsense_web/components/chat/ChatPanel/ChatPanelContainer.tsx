"use client";
import { useAtomValue } from "jotai";
import { LoaderIcon, TriangleAlert } from "lucide-react";
import { logger } from "@/lib/logger";
import { toast } from "sonner";
import { activeChatAtom } from "@/atoms/chats/chat-query.atoms";
import { activeChathatUIAtom, activeChatIdAtom } from "@/atoms/chats/ui.atoms";
import { generatePodcastMutationAtom } from "@/atoms/podcasts/podcast-mutation.atoms";
import type { GeneratePodcastRequest } from "@/contracts/types/podcast.types";
import { cn } from "@/lib/utils";
import { ChatPanelView } from "./ChatPanelView";

export function ChatPanelContainer() {
	const {
		data: activeChatState,
		isLoading: isChatLoading,
		error: chatError,
	} = useAtomValue(activeChatAtom);
	const activeChatIdState = useAtomValue(activeChatIdAtom);
	const { isChatPannelOpen } = useAtomValue(activeChathatUIAtom);
	const { mutateAsync: generatePodcast, error: generatePodcastError } = useAtomValue(
		generatePodcastMutationAtom
	);

	const handleGeneratePodcast = async (request: GeneratePodcastRequest) => {
		try {
			generatePodcast(request);
			toast.success(`Podcast generation started!`);
		} catch (error) {
			toast.error("Error generating podcast. Please try again later.");
			logger.error("Error generating podcast:", JSON.stringify(generatePodcastError));
		}
	};

	return activeChatIdState ? (
		<div
			className={cn(
				"shrink-0 bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60 flex flex-col h-full transition-all",
				isChatPannelOpen ? "w-96" : "w-0"
			)}
		>
			{isChatLoading || chatError ? (
				<div className="border-b p-2">
					{isChatLoading ? (
						<div title="Loading chat" className="flex items-center justify-center h-full">
							<LoaderIcon strokeWidth={1.5} className="h-5 w-5 animate-spin" />
						</div>
					) : chatError ? (
						<div title="Failed  to load chat" className="flex items-center justify-center h-full">
							<TriangleAlert strokeWidth={1.5} className="h-5 w-5 text-red-600" />
						</div>
					) : null}
				</div>
			) : null}

			{!isChatLoading && !chatError && activeChatState?.chatDetails && (
				<ChatPanelView generatePodcast={handleGeneratePodcast} />
			)}
		</div>
	) : null;
}
