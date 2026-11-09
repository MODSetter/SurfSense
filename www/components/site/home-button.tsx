import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import type * as React from "react";

import { siteText } from "@/components/site/site-text";
import { cn } from "@/components/ui/cn";

// Colours ease out in 150ms. Scale presses in the same way but returns over
// 250ms on a no-overshoot spring curve: the held state's timing applies while
// pressed, the resting one on release.
const TRANSITION =
	"transition-[color,background-color,border-color,box-shadow,opacity,scale] duration-[150ms,150ms,150ms,150ms,150ms,250ms] ease-[ease-out,ease-out,ease-out,ease-out,ease-out,cubic-bezier(0.2,0,0,1)] active:duration-150 active:ease-out";

/**
 * Homepage button.
 *
 * Ported from the desktop app's button (`surfsense_local/frontend/src/components/ui/button.tsx`)
 * so the marketing site and the product press the same way: the same size
 * ladder, the same scale press, the same focus ring, the same `--radius` corners.
 *
 * Colours come from the canonical palette via semantic tokens only. There is no
 * marketing-accent variant: the accent on this page marks text, not actions.
 */
const homeButtonVariants = cva(
	[
		"group/button inline-flex shrink-0 cursor-pointer items-center justify-center",
		"rounded-lg border border-transparent bg-clip-padding",
		"text-sm font-medium whitespace-nowrap select-none outline-none",
		TRANSITION,
		"focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50",
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
				link: cn(siteText.forward, "underline-offset-4 hover:underline"),
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

type Variant = NonNullable<VariantProps<typeof homeButtonVariants>["variant"]>;

// 0.95 is the polish guide's floor: deeper reads as exaggerated.
const PRESS_SCALE = "active:not-disabled:scale-[0.95] motion-reduce:active:scale-100";

// A static button presses by colour instead, one step past its hover.
const PRESSED_FILL: Record<Variant | "bare", string> = {
	default: "active:bg-primary/70",
	outline: "active:bg-[color-mix(in_oklch,var(--accent),var(--foreground)_8%)]",
	secondary: "active:bg-secondary/70",
	ghost: "active:bg-[color-mix(in_oklch,var(--accent),var(--foreground)_8%)]",
	link: "",
	bare: "",
};

// Behaviour without looks, for a pill, tile or link that brings its own layout,
// colours and focus outline. A static bare element brings its own pressed fill.
const BARE = `${TRANSITION} cursor-pointer disabled:pointer-events-none disabled:opacity-50`;

function HomeButton({
	className,
	variant = "default",
	size,
	asChild = false,
	static: isStatic = false,
	...props
}: React.ComponentProps<"button"> &
	Omit<VariantProps<typeof homeButtonVariants>, "variant"> & {
		variant?: Variant | "bare";
		asChild?: boolean;
		/** No press scale, for wide buttons where 5% is a visible jump. */
		static?: boolean;
	}) {
	const Comp = asChild ? Slot : "button";

	return (
		<Comp
			data-slot="button"
			className={cn(
				variant === "bare" ? BARE : homeButtonVariants({ variant, size }),
				isStatic ? PRESSED_FILL[variant] : PRESS_SCALE,
				className
			)}
			{...props}
		/>
	);
}

export { HomeButton, homeButtonVariants };
