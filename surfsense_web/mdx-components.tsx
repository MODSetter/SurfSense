import defaultMdxComponents from "fumadocs-ui/mdx";
import type { MDXComponents } from "mdx/types";
import {
	Accordion,
	AccordionContent,
	AccordionItem,
	AccordionTrigger,
} from "@/components/ui/accordion";
import { cn } from "@/lib/utils";

export function getMDXComponents(components?: MDXComponents): MDXComponents {
	return {
		...defaultMdxComponents,
		img: ({ className, ...props }: React.ComponentProps<"img">) => (
			<img className={cn("rounded-md border", className)} {...props} />
		),
		Video: ({ className, ...props }: React.ComponentProps<"video">) => (
			<video className={cn("rounded-md border", className)} controls loop {...props} />
		),
		Accordion,
		AccordionItem,
		AccordionTrigger,
		AccordionContent,
		...components,
	};
}

export const useMDXComponents = getMDXComponents;
