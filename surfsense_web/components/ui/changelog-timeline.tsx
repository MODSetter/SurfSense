import { ArrowUpRight } from "lucide-react";
import Image from "next/image";
import type { ReactNode } from "react";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

/**
 * Styled for the site design (`app/(home)/home.css`): rendered only from
 * `app/(home)/changelog/page.tsx`, which is listed in `SITE_DESIGN_ROUTES` in
 * `components/site/site-shell.tsx`.
 */

export type ChangelogTimelineEntry = {
	version: string;
	date: string;
	title: string;
	description: string;
	items?: string[];
	image?: string;
	content?: ReactNode;
	button?: {
		url: string;
		text: string;
	};
};

export interface ChangelogTimelineProps {
	title?: string;
	description?: string;
	entries?: ChangelogTimelineEntry[];
	className?: string;
}

const EMPTY_CHANGELOG_ENTRIES: ChangelogTimelineEntry[] = [];

export const ChangelogTimeline = ({
	title = "Changelog",
	description = "Get the latest updates and improvements to our platform.",
	entries = EMPTY_CHANGELOG_ENTRIES,
	className,
}: ChangelogTimelineProps) => {
	return (
		<>
			<section className="ss-home-hero ss-home-pad">
				<div className="mx-auto max-w-2xl text-center">
					<h1 className="ss-home-display">{title}</h1>
					<p className="ss-home-lede mx-auto mt-6 max-w-xl">{description}</p>
				</div>
			</section>

			<section className={cn("ss-home-rule ss-home-rule-plain", className)}>
				{entries.length > 0 ? (
					entries.map((entry, index) => (
						<article
							key={`${entry.version}-${entry.date}`}
							className={cn(
								"ss-home-pad grid gap-6 py-10 md:grid-cols-[12rem_1fr] md:gap-10 md:py-12",
								index > 0 && "ss-home-rule"
							)}
						>
							<div className="flex h-min flex-col items-start gap-3 md:sticky md:top-24">
								<time className="ss-home-eyebrow">{entry.date}</time>
								<Badge variant="secondary">{entry.version}</Badge>
							</div>
							<div className="flex min-w-0 max-w-2xl flex-1 flex-col">
								<h2 className="ss-home-h3 mb-3 text-xl md:text-2xl">{entry.title}</h2>
								<p className="ss-home-body">{entry.description}</p>
								{entry.items && entry.items.length > 0 ? (
									<ul className="ss-home-body mt-4 ml-4 flex list-disc flex-col gap-1.5">
										{entry.items.map((item) => (
											<li key={item}>{item}</li>
										))}
									</ul>
								) : null}
								{entry.content ? (
									<div className="prose prose-invert mt-8 max-w-none prose-headings:scroll-mt-8 prose-headings:font-semibold prose-headings:tracking-tight prose-headings:text-balance prose-p:tracking-tight prose-p:text-balance prose-a:text-(--home-accent) prose-a:no-underline prose-img:rounded-none prose-img:border prose-img:border-border">
										{entry.content}
									</div>
								) : null}
								{entry.image ? (
									<div className="relative mt-8 aspect-video overflow-hidden border border-border">
										<Image
											src={entry.image}
											alt={`${entry.version} visual`}
											fill
											sizes="(max-width: 768px) 100vw, 768px"
											className="object-cover"
										/>
									</div>
								) : null}
								{entry.button ? (
									<a
										href={entry.button.url}
										target="_blank"
										rel="noreferrer"
										className="ss-home-forward mt-4 self-start"
									>
										{entry.button.text} <ArrowUpRight className="size-3.5" />
									</a>
								) : null}
							</div>
						</article>
					))
				) : (
					<p className="ss-home-pad ss-home-body py-16 text-center">No changelog entries yet.</p>
				)}
			</section>
		</>
	);
};
