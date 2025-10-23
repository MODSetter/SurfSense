import { PanelRight } from "lucide-react";
import { useActionState, useContext } from "react";
import { cn } from "@/lib/utils";
import { chatInterfaceContext } from "../ChatInterface";
import { generatePodCastAction, getChatPodcastPromise } from "./actions";
import { ChatPanelView } from "./ChatPanelView";

export interface PodCastInterface {
	title: string;
	podcast_transcript: string;
	search_space_id: string;
}

export type PodcastGenerationState = Partial<{
	title: string;
	podcast_transcript: string;
	search_space_id: string;
	chat_id: string;
	prompt: string;
	error: unknown;
}>;

export function ChatPanelContainer() {
	const context = useContext(chatInterfaceContext);

	if (!context) {
		throw new Error("chatInterfaceContext must be used within a ChatProvider");
	}

	const { isChatPannelOpen, setIsChatPannelOpen, chat_id: chatId } = context;

	const [state, generatePodcastAction, isGeneratingPodcast] =
		useActionState<PodcastGenerationState>(generatePodCastAction, {
			chat_id: chatId,
			prompt: "Test",
		});

	return chatId && chatId !== "" ? (
		<div
			className={cn(
				"border rounded-2xl shrink-0 bg-sidebar flex flex-col h-full transition-all",
				isChatPannelOpen ? "w-72" : "w-14"
			)}
		>
			<div
				className={cn(
					"w-full border-b p-2 flex items-center transition-all ",
					isChatPannelOpen ? "justify-end" : " justify-center "
				)}
			>
				<button
					type="button"
					onClick={() => setIsChatPannelOpen(!isChatPannelOpen)}
					className={cn(" shrink-0 rounded-full p-2 w-fit hover:bg-muted")}
				>
					<PanelRight className="h-5 w-5" strokeWidth={1.5} />
				</button>
			</div>

			<div className="border-b rounded-lg grow-1">
				<ChatPanelView chat_id={chatId} />
			</div>
		</div>
	) : null;
}
