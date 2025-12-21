"use client";

import { AssistantRuntimeProvider, useLocalRuntime } from "@assistant-ui/react";
import { useParams } from "next/navigation";
import { useMemo } from "react";
import { Thread } from "@/components/assistant-ui/thread";
import { createNewChatAdapter } from "@/lib/chat/new-chat-transport";

export default function NewChatPage() {
	const params = useParams();

	// Extract search_space_id and chat_id from URL params
	const searchSpaceId = useMemo(() => {
		const id = params.search_space_id;
		const parsed = typeof id === "string" ? Number.parseInt(id, 10) : 0;
		return Number.isNaN(parsed) ? 0 : parsed;
	}, [params.search_space_id]);

	const chatId = useMemo(() => {
		const id = params.chat_id;
		let parsed = 0;
		if (Array.isArray(id) && id.length > 0) {
			parsed = Number.parseInt(id[0], 10);
		} else if (typeof id === "string") {
			parsed = Number.parseInt(id, 10);
		}
		return Number.isNaN(parsed) ? 0 : parsed;
	}, [params.chat_id]);

	// Create the adapter with the extracted params
	const adapter = useMemo(
		() => createNewChatAdapter({ searchSpaceId, chatId }),
		[searchSpaceId, chatId]
	);

	// Use LocalRuntime with our custom adapter
	const runtime = useLocalRuntime(adapter);

	return (
		<AssistantRuntimeProvider runtime={runtime}>
			<div className="h-[calc(100vh-64px)] max-h-[calc(100vh-64px)] overflow-hidden">
				<Thread />
			</div>
		</AssistantRuntimeProvider>
	);
}
