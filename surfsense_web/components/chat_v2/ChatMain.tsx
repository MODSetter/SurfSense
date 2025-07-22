"use client";

import {
    ChatCanvas,
    ChatMessages,
    ChatSection,
    useChatUI,
    ChatHandler,
} from "@llamaindex/chat-ui";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import { Loader2 } from "lucide-react";
import { useEffect } from "react";

interface ChatMainProps {
    handler: ChatHandler;
    handleQuerySubmit: (input: string, handleSubmit: () => void) => void;
}

const ChatInput = (props: {
    handleQuerySubmit: (input: string, handleSubmit: () => void) => void;
}) => {
    const { input, setInput, handleSubmit } = useChatUI();
    const { handleQuerySubmit } = props;

    const handleFormSubmit = (e: React.FormEvent<HTMLFormElement>) => {
        e.preventDefault();
        if (!input.trim()) return;

        handleQuerySubmit(input, handleSubmit);
    };

    return (
        <form
            className="flex flex-row items-center justify-between gap-2"
            onSubmit={handleFormSubmit}
        >
            <Textarea
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="Type your message here..."
                rows={4}
                className="max-h-[150px] overflow-y-auto"
            />

            <Button type="submit">Send</Button>
        </form>
    );
};

export default function ChatMain({
    handler,
    handleQuerySubmit,
}: ChatMainProps) {
    return (
        <ChatSection handler={handler} className="flex h-full">
            <div className="flex flex-1 flex-col">
                <ChatMessages className="flex-1">
                    <ChatMessages.List className="p-4">
                        {/* Custom message rendering */}
                    </ChatMessages.List>
                    <ChatMessages.Loading>
                        <Loader2 className="animate-spin" />
                    </ChatMessages.Loading>
                </ChatMessages>

                <div className="border-t p-4">
                    <ChatInput handleQuerySubmit={handleQuerySubmit} />
                </div>
            </div>

            <ChatCanvas className="w-1/2 border-l" />
        </ChatSection>
    );
}
