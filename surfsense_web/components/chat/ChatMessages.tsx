"use client";

import {
	ChatMessage as LlamaIndexChatMessage,
	ChatMessages as LlamaIndexChatMessages,
	type Message,
	useChatUI,
} from "@llamaindex/chat-ui";
import { Loader2 } from "lucide-react";
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
		<LlamaIndexChatMessage message={message} isLast={isLast} className="flex flex-col items-start">
			{message.role === "assistant" ? (
				<div className="flex-1 flex flex-col space-y-4 items-start w-full">
					<TerminalDisplay message={message} />
					<LlamaIndexChatMessage.Content className="flex-1 text-left prose prose-sm max-w-none custom-markdown">
						<LlamaIndexChatMessage.Content.Markdown
							citationComponent={CitationDisplay}
							languageRenderers={languageRenderers}
						/>
						{isStreaming && (
							<span className="inline-flex items-center gap-1.5 ml-1">
								<Loader2 className="h-4 w-4 animate-spin text-blue-400" />
								<span className="text-xs text-blue-400">Generating answer...</span>
							</span>
						)}
					</LlamaIndexChatMessage.Content>
					<div ref={bottomRef} />
					{/* Main action bar with all buttons grouped together */}
					<div className="flex flex-wrap gap-2 items-center justify-between w-full">
						{/* Left side - Sources and view options */}
						<div className="flex items-center gap-2">
							<ChatSourcesDisplay message={message} />
						</div>
						{/* Right side - Copy and Regenerate actions */}
						<div className="flex items-center gap-2">
							<LlamaIndexChatMessage.Actions className="flex flex-row items-center gap-2" />
						</div>
					</div>
					{/* Suggested questions below action bar */}
					{isLast && <ChatFurtherQuestions message={message} />}
				</div>
			) : (
				<LlamaIndexChatMessage.Content className="flex-1 text-left">
					<LlamaIndexChatMessage.Content.Markdown languageRenderers={languageRenderers} />
				</LlamaIndexChatMessage.Content>
			)}
		</LlamaIndexChatMessage>
	);
}
