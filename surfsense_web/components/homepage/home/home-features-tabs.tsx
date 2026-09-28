"use client";

import Link from "next/link";
import { useRef } from "react";
import { PROOF_POINTS, STORIES } from "@/components/homepage/home/home-content";
import { ArrowRightIcon, CheckIcon, ChevronDownIcon } from "@/components/ui/icons";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

// Matches the max-width of the accordion block in home.css.
const ACCORDION_QUERY = "(max-width: 767px)";

/**
 * H2 #5, #6, #7 as a tabbed switcher rather than three stacked rows.
 *
 * All three panels stay mounted (`forceMount`) so all three real H2s are in
 * the markup regardless of which tab is open — the heading sequence this
 * section owes the SEO brief does not depend on the active tab. They are
 * stacked in one grid cell so the section's height is always the tallest
 * panel's height: switching tabs never changes it, so nothing below the
 * section moves.
 *
 * Below 768px the same tabs lay out as an accordion: the `order` pairs each
 * panel with its trigger once CSS flattens the list. One component rather than
 * a second accordion, so the three H2s appear once.
 */
export function HomeFeaturesTabs() {
	const triggers = useRef(new Map<string, HTMLButtonElement>());

	// Closing the panel above the tapped row pulls that row up, possibly off screen.
	const keepOpenedRowInView = (value: string) => {
		if (!window.matchMedia(ACCORDION_QUERY).matches) return;
		requestAnimationFrame(() => triggers.current.get(value)?.scrollIntoView({ block: "nearest" }));
	};

	return (
		<Tabs
			defaultValue={STORIES[0].key}
			onValueChange={keepOpenedRowInView}
			className="ss-home-features"
		>
			<TabsList className="ss-home-features-tablist ss-home-grid ss-home-grid-3">
				{STORIES.map((story, index) => (
					<TabsTrigger
						key={story.key}
						value={story.key}
						ref={(node) => {
							if (node) triggers.current.set(story.key, node);
							else triggers.current.delete(story.key);
						}}
						style={{ order: index * 2 }}
						className="ss-home-features-tab"
					>
						<span className="ss-home-features-tab-num">{String(index + 1).padStart(2, "0")}</span>
						<span className="ss-home-features-tab-title">{story.heading}</span>
						<ChevronDownIcon aria-hidden="true" className="ss-home-features-tab-chevron size-4" />
					</TabsTrigger>
				))}
			</TabsList>

			<div className="ss-home-features-panels">
				{STORIES.map((story, index) => (
					<TabsContent
						key={story.key}
						value={story.key}
						forceMount
						style={{ order: index * 2 + 1 }}
						className="ss-home-split"
					>
						<div className="ss-home-statement">
							<h2 className="ss-home-h2 ss-home-features-heading">{story.heading}</h2>
							<div className="ss-home-body mt-5 flex flex-col gap-4">
								{story.body.map((paragraph) => (
									<p key={paragraph}>{paragraph}</p>
								))}
							</div>
							<p className="mt-6">
								{story.action.external ? (
									<a
										className="ss-home-forward"
										href={story.action.href}
										target="_blank"
										rel="noreferrer noopener"
									>
										{story.action.label} <ArrowRightIcon aria-hidden="true" className="size-4" />
									</a>
								) : (
									<Link className="ss-home-forward" href={story.action.href}>
										{story.action.label} <ArrowRightIcon aria-hidden="true" className="size-4" />
									</Link>
								)}
							</p>
						</div>

						<ul className="ss-home-grid m-0 list-none p-0">
							{PROOF_POINTS[story.key].map((point) => (
								<li key={point} className="flex items-center gap-3 px-(--home-gutter) py-3.5">
									<CheckIcon
										aria-hidden="true"
										className="size-3.5 shrink-0 text-(--home-accent)"
									/>
									<span className="ss-home-body text-sm">{point}</span>
								</li>
							))}
						</ul>
					</TabsContent>
				))}
			</div>
		</Tabs>
	);
}
