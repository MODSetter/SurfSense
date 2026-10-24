import type { ReactNode } from "react";
import type { Format } from "@/components/homepage/home/home-content";
import { siteText } from "@/components/site/site-text";
import { cn } from "@/lib/utils";

/**
 * One artifact as a card: a miniature of the output on a stage, then its
 * name. `wash` sets the stage in the hero's sky, kept for the headline formats
 * so the scenery carries into the middle of the page.
 */
export function FormatCard({
	format,
	group,
	preview,
	wash = false,
	className,
}: {
	format: Format;
	group: string;
	preview: ReactNode;
	wash?: boolean;
	className?: string;
}) {
	return (
		<article
			className={cn(
				"flex flex-col overflow-hidden rounded-2xl border border-border bg-card shadow-xs transition-[translate,box-shadow] duration-200 ease-out hover:-translate-y-0.5 hover:shadow-[0_16px_32px_-16px_rgb(0_0_0/0.2)] motion-reduce:transition-none motion-reduce:hover:translate-y-0",
				className
			)}
		>
			<div
				aria-hidden="true"
				className={cn(
					"flex min-h-44 flex-1 items-center justify-center p-6",
					wash ? "bg-linear-to-b from-(--home-sky) to-(--home-sky-soft)" : "bg-secondary"
				)}
			>
				{preview}
			</div>
			<div className="border-t border-border px-5 py-4">
				<p className={siteText.eyebrow}>{group}</p>
				<p className={cn(siteText.h3, "mt-1.5")}>{format.label}</p>
				<p className={cn(siteText.body, "mt-1 text-sm")}>{format.body}</p>
			</div>
		</article>
	);
}
