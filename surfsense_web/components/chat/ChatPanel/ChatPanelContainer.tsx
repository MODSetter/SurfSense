"use client";
import { useAtom, useAtomValue } from "jotai";
import { LoaderIcon, PanelRight, TriangleAlert } from "lucide-react";
import { toast } from "sonner";
import { activeChatAtom, activeChatIdAtom } from "@/atoms/chats/chat-querie.atoms";
import { activeChathatUIAtom } from "@/atoms/chats/ui.atoms";
import type { GeneratePodcastRequest } from "@/contracts/types/podcast.types";
import { podcastsApiService } from "@/lib/apis/podcasts-api.service";
import { cn } from "@/lib/utils";
import { ChatPanelView } from "./ChatPanelView";

export function ChatPanelContainer() {
	const {
		data: activeChatState,
		isLoading: isChatLoading,
		error: chatError,
	} = useAtomValue(activeChatAtom);
	const activeChatIdState = useAtomValue(activeChatIdAtom);
	const authToken = localStorage.getItem("surfsense_bearer_token");
	const { isChatPannelOpen } = useAtomValue(activeChathatUIAtom);

	const handleGeneratePodcast = async (request: GeneratePodcastRequest) => {
		try {
			if (!authToken) {
				throw new Error("Authentication error. Please log in again.");
			}
			await podcastsApiService.generatePodcast(request);
			toast.success(`Podcast generation started!`);
		} catch (error) {
			toast.error("Error generating podcast. Please try again later.");
			console.error("Error generating podcast:", JSON.stringify(error));
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
						<div title="Failed to load chat" className="flex items-center justify-center h-full">
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
