"use client";

import { SuggestedQuestions } from "@llamaindex/chat-ui/widgets";
import { getAnnotationData, Message, useChatUI } from "@llamaindex/chat-ui";
import {
	Accordion,
	AccordionContent,
	AccordionItem,
	AccordionTrigger,
} from "@/components/ui/accordion";

export const ChatFurtherQuestions: React.FC<{ message: Message }> = ({
	message,
}) => {
	const annotations: string[][] = getAnnotationData(
		message,
		"FURTHER_QUESTIONS",
	);
	const { append, requestData } = useChatUI();

	if (annotations.length !== 1 || annotations[0].length === 0) {
		return <></>;
	}

	return (
		<Accordion
			type="single"
			collapsible
			className="w-full px-2 border-2 rounded-lg shadow-lg"
		>
			<AccordionItem value="suggested-questions">
				<AccordionTrigger className="text-sm font-semibold">
					Suggested Questions
				</AccordionTrigger>
				<AccordionContent>
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
