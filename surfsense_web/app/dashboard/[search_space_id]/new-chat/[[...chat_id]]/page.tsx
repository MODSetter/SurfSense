"use client";

import { AssistantRuntimeProvider } from "@assistant-ui/react";
import { useChatRuntime } from "@assistant-ui/react-ai-sdk";
import { Thread } from "@/components/assistant-ui/thread";

export default function NewChatPage() {
	// Using the official assistant-ui pattern - useChatRuntime with NO parameters
	// It defaults to /api/chat endpoint
	const runtime = useChatRuntime();

	return (
		<AssistantRuntimeProvider runtime={runtime}>
			<div className="h-full">
				<Thread />
			</div>
		</AssistantRuntimeProvider>
	);
}
