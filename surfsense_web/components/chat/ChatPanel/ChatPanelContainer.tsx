import { PanelRight } from "lucide-react";
import { useActionState, useContext, useTransition } from "react";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import { chatInterfaceContext } from "../ChatInterface";
import type { GeneratePodcastRequest } from "./actions";
import { ChatPanelView } from "./ChatPanelView";

export function ChatPanelContainer() {
	const context = useContext(chatInterfaceContext);

	if (!context) {
		throw new Error("chatInterfaceContext must be used within a ChatProvider");
	}

	const { isChatPannelOpen, setIsChatPannelOpen, chat_id: chatId, setPodcast } = context;

	const generatePodcast = async (request: GeneratePodcastRequest) => {
		try {
			const { podcast_title = "SurfSense Podcast" } = request;

			const response = await fetch(
				`${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/podcasts/generate/`,
				{
					method: "POST",
					headers: {
						Authorization: `Bearer ${localStorage.getItem("surfsense_bearer_token")}`,
						"Content-Type": "application/json",
					},
					body: JSON.stringify({ ...request, podcast_title }),
				}
			);

			if (!response.ok) {
				const errorData = await response.json().catch(() => ({}));
				throw new Error(errorData.detail || "Failed to generate podcast");
			}

			const result = await response.json();

			setPodcast(result);

			toast.success(`Podcast generation started!`);
		} catch (error) {
			console.error("Error generating podcast:", error);
			console.log(error);
		} finally {
		}
	};

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
				<ChatPanelView generatePodcast={generatePodcast} />
			</div>
		</div>
	) : null;
}
