"use client";

import { SuggestedQuestions } from "@llamaindex/chat-ui/widgets";
import { getAnnotationData, Message, useChatUI } from "@llamaindex/chat-ui";

export const ChatFurtherQuestions: React.FC<{message: Message}> = ({message}) => {
    const annotations: string[][] = getAnnotationData(message, "FURTHER_QUESTIONS");
    const { append, requestData } = useChatUI();

    console.log('🔥 annotations', annotations);
    

    if (annotations.length !== 1 || annotations[0].length === 0) {
        return <></>;
    }
    
    return <SuggestedQuestions questions={annotations[0]} append={append} requestData={requestData} />;
};