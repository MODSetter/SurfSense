import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

/**
 * Marketing-page section. No side padding: `.ss-home-page` already holds the
 * column to the text edge, so content and rules share one edge.
 */
export function MarketingSection({
	children,
	className,
}: {
	children: ReactNode;
	className?: string;
}) {
	return <section className={cn("py-12 sm:py-16", className)}>{children}</section>;
}
