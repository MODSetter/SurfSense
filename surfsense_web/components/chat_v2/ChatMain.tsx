"use client";

import { ChatSection, ChatHandler } from "@llamaindex/chat-ui";

interface ChatMainProps {
    handler: ChatHandler;
}

export default function ChatMain({ handler }: ChatMainProps) {
    return <ChatSection handler={handler} className="flex h-full" />;
}
