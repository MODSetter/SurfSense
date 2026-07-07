import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

/**
 * Shared marketing-page section container. Mirrors the navbar/hero grid exactly
 * (max-w-7xl with px-2 md:px-8 xl:px-0 gutters) so every section edge aligns
 * across the homepage, connector pages, and the connectors hub.
 */
export function MarketingSection({
	children,
	className,
}: {
	children: ReactNode;
	className?: string;
}) {
	return (
		<section className={cn("py-12 sm:py-16", className)}>
			<div className="mx-auto w-full max-w-7xl px-2 md:px-8 xl:px-0">{children}</div>
		</section>
	);
}
