import Link from "next/link";
import type { ReactNode } from "react";
import type { FEATURES } from "@/components/homepage/home/home-content";
import { siteText } from "@/components/site/site-text";
import { ArrowRightIcon, CheckIcon } from "@/components/ui/icons";
import { cn } from "@/lib/utils";

/**
 * One claim beside its picture. The claim's heading is a real H2 (the brief's
 * #5–#7). `flip` puts the picture on the right, so the rows alternate.
 */
export function FeatureRow({
	feature,
	visual,
	flip = false,
}: {
	feature: (typeof FEATURES)[number];
	visual: ReactNode;
	flip?: boolean;
}) {
	return (
		<div
			className={cn(
				"flex flex-col overflow-hidden rounded-3xl bg-muted p-2 md:flex-row",
				flip && "md:flex-row-reverse"
			)}
		>
			<div className="shrink-0 md:w-1/2">{visual}</div>

			<div className="flex flex-1 flex-col justify-center gap-7 p-6 md:p-10">
				<div className="flex flex-col gap-3">
					<h2 className="text-2xl leading-snug font-medium tracking-tight text-foreground">
						{feature.heading}
					</h2>
					<p className={siteText.body}>{feature.body}</p>
				</div>
				<ul className="m-0 flex list-none flex-col gap-3 p-0">
					{feature.points.map((point) => (
						<li key={point.title} className="flex items-start gap-3">
							<span
								aria-hidden="true"
								className="mt-0.5 grid size-5 shrink-0 place-items-center rounded-full bg-foreground text-background"
							>
								<CheckIcon className="size-3" />
							</span>
							<p className={siteText.body}>
								<span className="font-medium text-foreground">{point.title}: </span>
								{point.body}
							</p>
						</li>
					))}
				</ul>
				<p>
					<Link className={siteText.forward} href={feature.action.href}>
						{feature.action.label} <ArrowRightIcon aria-hidden="true" className="size-4" />
					</Link>
				</p>
			</div>
		</div>
	);
}
