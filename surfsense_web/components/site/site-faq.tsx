"use client";

import {
	Accordion,
	AccordionContent,
	AccordionItem,
	AccordionTrigger,
} from "@/components/ui/accordion";

export interface FaqItem {
	question: string;
	answer: string;
}

export function SiteFaq({ items }: { items: FaqItem[] }) {
	return (
		<Accordion type="single" collapsible className="w-full">
			{items.map((item, i) => (
				<AccordionItem key={item.question} value={`item-${i}`}>
					<AccordionTrigger className="text-base">{item.question}</AccordionTrigger>
					<AccordionContent className="text-muted-foreground leading-relaxed">
						{item.answer}
					</AccordionContent>
				</AccordionItem>
			))}
		</Accordion>
	);
}
