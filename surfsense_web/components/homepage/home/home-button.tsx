import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import type * as React from "react";

import { cn } from "@/lib/utils";

/**
 * Homepage button.
 *
 * Ported from the desktop app's button (`surfsense_local/frontend/src/components/ui/button.tsx`)
 * so the marketing site and the product press the same way: the same size
 * ladder, the same `translate-y-px` press, the same focus ring, the same
 * `--radius` corners.
 *
 * One deliberate difference from the desktop original: `transition-all` is
 * replaced by an explicit property list. Blanket transitions also animate size
 * and radius changes, which makes a button visibly stretch when a variant or
 * breakpoint changes it.
 *
 * Colours come from the canonical palette via semantic tokens only. There is no
 * marketing-accent variant: the accent on this page marks text, not actions.
 */
const homeButtonVariants = cva(
	[
		"group/button inline-flex shrink-0 cursor-pointer items-center justify-center",
		"rounded-lg border border-transparent bg-clip-padding",
		"text-sm font-medium whitespace-nowrap select-none outline-none",
		"transition-[color,background-color,border-color,box-shadow,opacity,translate]",
		"duration-150 ease-out",
		"focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50",
		"active:not-aria-[haspopup]:translate-y-px",
		"disabled:pointer-events-none disabled:opacity-50",
		"[&_svg]:pointer-events-none [&_svg]:shrink-0 [&_svg:not([class*='size-'])]:size-4",
	].join(" "),
	{
		variants: {
			variant: {
				default: "bg-primary text-primary-foreground hover:bg-primary/80",
				outline: "border-border bg-transparent hover:bg-accent hover:text-accent-foreground",
				secondary: "bg-secondary text-secondary-foreground hover:bg-secondary/80",
				ghost: "hover:bg-accent hover:text-accent-foreground",
				link: "ss-home-forward underline-offset-4 hover:underline",
			},
			size: {
				default: "h-8 gap-1.5 px-2.5",
				sm: "h-7 gap-1 px-2.5 text-[0.8rem]",
				lg: "h-9 gap-1.5 px-3",
				xl: "h-10 gap-2 px-4 text-base",
				"2xl": "h-11 gap-2 px-5 text-lg",
				icon: "size-8",
			},
		},
		defaultVariants: {
			variant: "default",
			size: "default",
		},
	}
);

function HomeButton({
	className,
	variant,
	size,
	asChild = false,
	...props
}: React.ComponentProps<"button"> &
	VariantProps<typeof homeButtonVariants> & {
		asChild?: boolean;
	}) {
	const Comp = asChild ? Slot : "button";

	return (
		<Comp
			data-slot="button"
			className={cn(homeButtonVariants({ variant, size, className }))}
			{...props}
		/>
	);
}

export { HomeButton, homeButtonVariants };
