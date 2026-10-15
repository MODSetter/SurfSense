import Image from "next/image";
import type { ReactNode } from "react";
import { HomeBadge } from "@/components/homepage/home/home-badge";
import { sectionSpacing } from "@/components/homepage/home/home-section-spacing";
import { siteText } from "@/components/site/site-text";
import { ArrowUpRight01Icon } from "@/components/ui/icons";
import { cn } from "@/lib/utils";

/**
 * The changelog in the homepage's shapes: a centred badge head, then one
 * release per row, ruled off from the next, its date and version beside the
 * notes.
 * Rendered only from `app/(home)/changelog/page.tsx`.
 */

export type ChangelogTimelineEntry = {
	version: string;
	date: string;
	// Optional: the MDX releases carry their own headings in `content`.
	title?: string;
	description?: string;
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
		<section className={cn(sectionSpacing.foot, className)}>
			<div className={cn("text-center", sectionSpacing.head)}>
				<HomeBadge>Release notes</HomeBadge>
				<h1 className={cn(siteText.display, "mt-4")}>{title}</h1>
				<p className={cn(siteText.lede, "mx-auto mt-6 max-w-xl")}>{description}</p>
			</div>

			{entries.length > 0 ? (
				<ol className="m-0 mt-10 list-none divide-y divide-border border-y border-border p-0 lg:mt-14">
					{entries.map((entry) => (
						<li key={`${entry.version}-${entry.date}`}>
							<article className="grid gap-6 py-10 md:grid-cols-[11rem_1fr] md:gap-10 md:py-14">
								<div className="flex h-min flex-wrap items-center gap-2 md:sticky md:top-24 md:flex-col md:items-start md:gap-3">
									<span className="rounded-full bg-foreground px-3 py-1 text-xs font-medium text-background">
										{entry.version}
									</span>
									<time className="text-sm text-muted-foreground">{entry.date}</time>
								</div>
								<div className="flex min-w-0 max-w-3xl flex-col">
									{entry.title ? (
										<h2 className={cn(siteText.h3, "mb-3 text-xl md:text-2xl")}>{entry.title}</h2>
									) : null}
									{entry.description ? <p className={siteText.body}>{entry.description}</p> : null}
									{entry.items && entry.items.length > 0 ? (
										<ul className={cn(siteText.body, "mt-4 ml-4 flex list-disc flex-col gap-1.5")}>
											{entry.items.map((item) => (
												<li key={item}>{item}</li>
											))}
										</ul>
									) : null}
									{entry.content ? (
										<div className="prose max-w-none prose-headings:scroll-mt-24 prose-headings:font-semibold prose-headings:tracking-tight prose-headings:text-balance prose-p:text-pretty prose-a:text-primary prose-a:no-underline prose-img:rounded-2xl prose-img:border prose-img:border-border prose-img:shadow-none first:prose-headings:mt-0">
											{entry.content}
										</div>
									) : null}
									{entry.image ? (
										<div className="relative mt-8 aspect-video overflow-hidden rounded-2xl border border-border">
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
											className={cn(siteText.forward, "mt-4 self-start")}
										>
											{entry.button.text} <ArrowUpRight01Icon className="size-3.5" />
										</a>
									) : null}
								</div>
							</article>
						</li>
					))}
				</ol>
			) : (
				<p
					className={cn(
						siteText.body,
						"mt-10 rounded-3xl border border-dashed border-border py-16 text-center lg:mt-14"
					)}
				>
					No changelog entries yet.
				</p>
			)}
		</section>
	);
};
