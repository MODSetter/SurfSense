"use client";

import FuzzySearch from "fuzzy-search";
import { useMemo, useState } from "react";
import { HomeBadge } from "@/components/homepage/home/home-badge";
import { sectionSpacing } from "@/components/homepage/home/home-section-spacing";
import { siteText } from "@/components/site/site-text";
import { cn } from "@/lib/utils";
import { FeaturedPost } from "./featured-post";
import type { BlogEntry } from "./page";
import { PostCard } from "./post-card";

function SearchIcon({ className }: { className?: string }) {
	return (
		<svg
			className={className}
			xmlns="http://www.w3.org/2000/svg"
			width="18"
			height="18"
			viewBox="0 0 24 24"
			fill="none"
			stroke="currentColor"
			strokeWidth="2"
			strokeLinecap="round"
			strokeLinejoin="round"
			aria-hidden="true"
		>
			<circle cx="11" cy="11" r="8" />
			<path d="m21 21-4.3-4.3" />
		</svg>
	);
}

/**
 * The blog index, in the homepage's shapes: a centred badge and heading, the
 * lead post as a wide feature, the rest as rounded cards. A search shows every
 * match as a card, so the feature never hides a result.
 */
export function BlogWithSearchMagazine({ blogs }: { blogs: BlogEntry[] }) {
	const [search, setSearch] = useState("");

	const searcher = useMemo(
		() => new FuzzySearch(blogs, ["title", "description"], { caseSensitive: false }),
		[blogs]
	);
	const searching = search.trim() !== "";
	const matches = useMemo(
		() => (searching ? searcher.search(search) : blogs),
		[searching, search, searcher, blogs]
	);
	const [lead, ...rest] = blogs;
	const grid = searching ? matches : rest;

	return (
		<section className={sectionSpacing.foot}>
			<div className={cn("text-center", sectionSpacing.head)}>
				<HomeBadge>Blog</HomeBadge>
				<h1 className={cn(siteText.display, "mt-4")}>From the SurfSense team</h1>
				<p className={cn(siteText.lede, "mx-auto mt-6 max-w-2xl")}>
					Product updates, benchmarks and guides to keeping your AI private.
				</p>
				{blogs.length > 0 && (
					<label className="relative mx-auto mt-8 block w-full max-w-md">
						<span className="sr-only">Search posts</span>
						<SearchIcon className="pointer-events-none absolute top-1/2 left-4 -translate-y-1/2 text-muted-foreground" />
						<input
							type="search"
							value={search}
							onChange={(e) => setSearch(e.target.value)}
							placeholder="Search posts"
							className="h-11 w-full rounded-full border border-border bg-card pr-4 pl-11 text-sm text-foreground shadow-xs outline-none placeholder:text-muted-foreground focus-visible:ring-3 focus-visible:ring-ring/50"
						/>
					</label>
				)}
			</div>

			{blogs.length === 0 ? (
				<p className={cn(siteText.body, "mt-14 text-center")}>No posts yet.</p>
			) : (
				<div className="mt-10 flex flex-col gap-6 lg:mt-14">
					{!searching && lead && <FeaturedPost blog={lead} />}

					<h2 className="sr-only">{searching ? "Search results" : "More posts"}</h2>
					{searching && grid.length === 0 ? (
						<p
							className={cn(
								siteText.body,
								"rounded-2xl border border-dashed border-border py-16 text-center"
							)}
						>
							No posts match that search.
						</p>
					) : (
						<ul className="m-0 grid list-none gap-6 p-0 sm:grid-cols-2 lg:grid-cols-3">
							{grid.map((blog) => (
								<li key={blog.slug}>
									<PostCard blog={blog} />
								</li>
							))}
						</ul>
					)}
				</div>
			)}
		</section>
	);
}
