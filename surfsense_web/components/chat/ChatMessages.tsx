"use client";

import {
	ChatMessage as LlamaIndexChatMessage,
	ChatMessages as LlamaIndexChatMessages,
	type Message,
	useChatUI,
} from "@llamaindex/chat-ui";
import { useEffect, useRef } from "react";
import { AnimatedEmptyState } from "@/components/chat/AnimatedEmptyState";
import { CitationDisplay } from "@/components/chat/ChatCitation";
import { ChatFurtherQuestions } from "@/components/chat/ChatFurtherQuestions";
import ChatSourcesDisplay from "@/components/chat/ChatSources";
import TerminalDisplay from "@/components/chat/ChatTerminal";
import { languageRenderers } from "@/components/chat/CodeBlock";

export function ChatMessagesUI() {
	const { messages } = useChatUI();

	return (
		<LlamaIndexChatMessages className="flex-1">
			<LlamaIndexChatMessages.Empty>
				<AnimatedEmptyState />
			</LlamaIndexChatMessages.Empty>
			<LlamaIndexChatMessages.List className="p-2">
				{messages.map((message, index) => (
					<ChatMessageUI
						key={`Message-${index}`}
						message={message}
						isLast={index === messages.length - 1}
					/>
				))}
			</LlamaIndexChatMessages.List>
			<LlamaIndexChatMessages.Loading />
		</LlamaIndexChatMessages>
	);
}

function ChatMessageUI({ message, isLast }: { message: Message; isLast: boolean }) {
	const bottomRef = useRef<HTMLDivElement>(null);
	const { isLoading } = useChatUI();
	const isStreaming = isLast && message.role === "assistant" && isLoading;

	useEffect(() => {
		if (isLast && bottomRef.current) {
			bottomRef.current.scrollIntoView({ behavior: "smooth" });
		}
	}, [isLast]);

	return (
		<LlamaIndexChatMessage message={message} isLast={isLast} className="flex flex-col">
			{message.role === "assistant" ? (
				<div className="flex-1 flex flex-col space-y-4">
					<TerminalDisplay message={message} />
					<ChatSourcesDisplay message={message} />
					<LlamaIndexChatMessage.Content className="flex-1 text-left">
						<LlamaIndexChatMessage.Content.Markdown
							citationComponent={CitationDisplay}
							languageRenderers={languageRenderers}
						/>
						{isStreaming && (
							<svg
								className="inline-block w-4 h-4 ml-1 text-blue-400 animate-anchor-pulse"
								viewBox="0 0 24 24"
								fill="currentColor"
								aria-hidden="true"
							>
								<title>Generating response</title>
								<circle cx="12" cy="3" r="1.5" />
								<rect x="11" y="4" width="2" height="11" rx="0.5" />
								<ellipse cx="12" cy="11" rx="4" ry="1.5" />
								<path d="M 12 15 Q 8 16, 6 19 L 5 19.5 Q 4.5 20, 5 20.5 L 6 21 Q 7 21, 7.5 20 L 9 17.5 Q 10.5 15.5, 12 15 Z" />
								<path d="M 12 15 Q 16 16, 18 19 L 19 19.5 Q 19.5 20, 19 20.5 L 18 21 Q 17 21, 16.5 20 L 15 17.5 Q 13.5 15.5, 12 15 Z" />
							</svg>
						)}
					</LlamaIndexChatMessage.Content>
					<div ref={bottomRef} />
					<div className="flex flex-row justify-end gap-2">
						{isLast && <ChatFurtherQuestions message={message} />}
						<LlamaIndexChatMessage.Actions className="flex-1 flex-col" />
					</div>
				</div>
			) : (
				<LlamaIndexChatMessage.Content className="flex-1 text-left">
					<LlamaIndexChatMessage.Content.Markdown languageRenderers={languageRenderers} />
				</LlamaIndexChatMessage.Content>
			)}
		</LlamaIndexChatMessage>
	);
}
