import { ArrowUpRight } from "lucide-react";
import Image from "next/image";
import type { ReactNode } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

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
		<section className={cn("py-32", className)}>
			<div className="container">
				<div className="mx-auto max-w-3xl">
					<h1 className="mb-4 text-3xl font-bold tracking-tight md:text-5xl">{title}</h1>
					<p className="mb-6 text-base text-muted-foreground md:text-lg">{description}</p>
				</div>
				{entries.length > 0 ? (
					<div className="mx-auto mt-16 flex max-w-3xl flex-col gap-16 md:mt-24 md:gap-24">
						{entries.map((entry) => (
							<div
								key={`${entry.version}-${entry.date}`}
								className="relative flex flex-col gap-4 md:flex-row md:gap-16"
							>
								<div className="top-8 flex h-min w-64 shrink-0 items-center gap-4 md:sticky">
									<Badge variant="secondary" className="text-xs">
										{entry.version}
									</Badge>
									<time className="text-xs font-medium text-muted-foreground">{entry.date}</time>
								</div>
								<div className="flex flex-col">
									<h2 className="mb-3 text-lg leading-tight font-bold text-foreground/90 md:text-2xl">
										{entry.title}
									</h2>
									<p className="text-sm text-muted-foreground md:text-base">{entry.description}</p>
									{entry.items && entry.items.length > 0 ? (
										<ul className="mt-4 ml-4 flex list-disc flex-col gap-1.5 text-sm text-muted-foreground md:text-base">
											{entry.items.map((item) => (
												<li key={item}>{item}</li>
											))}
										</ul>
									) : null}
									{entry.content ? (
										<div className="prose prose-neutral mt-8 max-w-none dark:prose-invert prose-headings:scroll-mt-8 prose-headings:font-semibold prose-headings:tracking-tight prose-headings:text-balance prose-p:tracking-tight prose-p:text-balance prose-a:no-underline prose-img:rounded-xl prose-img:shadow-lg">
											{entry.content}
										</div>
									) : null}
									{entry.image ? (
										<div className="relative mt-8 aspect-video overflow-hidden rounded-lg">
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
										<Button variant="link" className="mt-4 self-end" asChild>
											<a href={entry.button.url} target="_blank" rel="noreferrer">
												{entry.button.text} <ArrowUpRight data-icon="inline-end" />
											</a>
										</Button>
									) : null}
								</div>
							</div>
						))}
					</div>
				) : (
					<p className="mx-auto mt-16 max-w-3xl rounded-lg border border-dashed p-8 text-center text-muted-foreground">
						No changelog entries yet.
					</p>
				)}
			</div>
		</section>
	);
};
