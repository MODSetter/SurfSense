import Link from "next/link";
import type { ReactNode } from "react";
import type { PILLARS } from "@/components/homepage/home/home-content";
import { siteText } from "@/components/site/site-text";
import { ArrowRightIcon } from "@/components/ui/icons";
import { cn } from "@/lib/utils";

/**
 * One claim as a card: a still preview of it on a stage, then its heading,
 * which is a real H2 (the brief's #2–#4). The link sits at the bottom so the
 * three line up however long each body runs.
 */
export function PillarCard({
	pillar,
	preview,
}: {
	pillar: (typeof PILLARS)[number];
	preview: ReactNode;
}) {
	const label = (
		<>
			{pillar.action.label} <ArrowRightIcon aria-hidden="true" className="size-4" />
		</>
	);
	return (
		<article className="flex flex-col overflow-hidden rounded-2xl border border-border bg-card shadow-xs transition-[translate,box-shadow] duration-200 ease-out hover:-translate-y-0.5 hover:shadow-[0_16px_32px_-16px_rgb(0_0_0/0.2)] motion-reduce:transition-none motion-reduce:hover:translate-y-0">
			<div className="flex min-h-52 items-center justify-center bg-secondary p-6">{preview}</div>
			<div className="flex flex-1 flex-col border-t border-border px-6 py-5">
				<h2 className={siteText.h3}>{pillar.title}</h2>
				<p className={cn(siteText.body, "mt-2 text-sm")}>{pillar.body}</p>
				<p className="mt-auto pt-5">
					{pillar.action.external ? (
						<a
							className={siteText.forward}
							href={pillar.action.href}
							target="_blank"
							rel="noreferrer noopener"
						>
							{label}
						</a>
					) : (
						<Link className={siteText.forward} href={pillar.action.href}>
							{label}
						</Link>
					)}
				</p>
			</div>
		</article>
	);
}
