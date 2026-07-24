"use client";

import {
	Accordion,
	AccordionContent,
	AccordionItem,
	AccordionTrigger,
} from "@/components/ui/accordion";
import type { FaqItem } from "@/lib/connectors-marketing/types";

export function ConnectorFaq({ items }: { items: FaqItem[] }) {
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
