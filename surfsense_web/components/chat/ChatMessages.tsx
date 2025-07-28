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
			<LlamaIndexChatMessages.List className="p-4">
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

	useEffect(() => {
		if (isLast && bottomRef.current) {
			bottomRef.current.scrollIntoView({ behavior: "smooth" });
		}
	}, [isLast]);

	return (
		<LlamaIndexChatMessage message={message} isLast={isLast} className="flex flex-col ">
			{message.role === "assistant" ? (
				<div className="flex-1 flex flex-col space-y-4">
					<TerminalDisplay message={message} open={isLast} />
					<ChatSourcesDisplay message={message} />
					<LlamaIndexChatMessage.Content className="flex-1">
						<LlamaIndexChatMessage.Content.Markdown
							citationComponent={CitationDisplay}
							languageRenderers={languageRenderers}
						/>
					</LlamaIndexChatMessage.Content>
					<div ref={bottomRef} />
					<div className="flex flex-row justify-end gap-2">
						{isLast && <ChatFurtherQuestions message={message} />}
						<LlamaIndexChatMessage.Actions className="flex-1 flex-col" />
					</div>
				</div>
			) : (
				<LlamaIndexChatMessage.Content className="flex-1">
					<LlamaIndexChatMessage.Content.Markdown languageRenderers={languageRenderers} />
				</LlamaIndexChatMessage.Content>
			)}
		</LlamaIndexChatMessage>
	);
}
