"use client";

import { getAnnotationData, type Message, useChatUI } from "@llamaindex/chat-ui";
import { SuggestedQuestions } from "@llamaindex/chat-ui/widgets";
import {
	Accordion,
	AccordionContent,
	AccordionItem,
	AccordionTrigger,
} from "@/components/ui/accordion";

export const ChatFurtherQuestions: React.FC<{ message: Message }> = ({ message }) => {
	const annotations: string[][] = getAnnotationData(message, "FURTHER_QUESTIONS");
	const { append, requestData } = useChatUI();

	if (annotations.length !== 1 || annotations[0].length === 0) {
		return null;
	}

	return (
		<Accordion type="single" collapsible className="w-full border rounded-md bg-card shadow-sm">
			<AccordionItem value="suggested-questions" className="border-0">
				<AccordionTrigger className="px-4 py-3 text-sm font-medium text-foreground transition-colors">
					Further Suggested Questions
				</AccordionTrigger>
				<AccordionContent className="px-4 pb-4 pt-0">
					<SuggestedQuestions
						questions={annotations[0]}
						append={append}
						requestData={requestData}
					/>
				</AccordionContent>
			</AccordionItem>
		</Accordion>
	);
};
