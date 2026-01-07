import defaultMdxComponents from "fumadocs-ui/mdx";
import type { MDXComponents } from "mdx/types";
import {
	Accordion,
	AccordionContent,
	AccordionItem,
	AccordionTrigger,
} from "@/components/ui/accordion";
import { cn } from "@/lib/utils";
import Image, { type ImageProps } from "next/image";

export function getMDXComponents(components?: MDXComponents): MDXComponents {
	return {
		...defaultMdxComponents,
		img: ({ className, alt, ...props }: React.ComponentProps<"img">) => (
			<Image
				className={cn("rounded-md border", className)}
				alt={alt ?? ""}
				{...(props as ImageProps)}
			/>
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
