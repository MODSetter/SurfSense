"use client";

import { format } from "date-fns";
import FuzzySearch from "fuzzy-search";
import Link from "next/link";
import { useMemo, useState } from "react";
import type { BlogEntry } from "./page";

/**
 * The blog index.
 *
 * Built from the same `ss-home-*` primitives as the homepage, pricing, contact
 * and plugins pages, with one addition: `.ss-home-post-card` in
 * `app/(home)/home.css`, because this is the one page on the site with
 * photographs on it. Cards get their own hairline border and a normal grid
 * gap instead of the shared-background flush grid the rest of the site uses,
 * since the archive's length is unbounded — there is no item count to make an
 * even row out of.
 *
 * A plain list, not a magazine layout: every post gets the same card, in the
 * order the server sorted them in (see `page.tsx`).
 *
 * Only the shell changed here, not the posts: titles, descriptions, images and
 * authors all come from the same `BlogEntry` data as before.
 */

function truncate(text: string, length: number) {
	return text.length > length ? `${text.slice(0, length)}…` : text;
}

function SearchIcon({ className }: { className?: string }) {
	return (
		<svg
			className={className}
			xmlns="http://www.w3.org/2000/svg"
			width="20"
			height="20"
			viewBox="0 0 24 24"
			fill="none"
			stroke="currentColor"
			strokeWidth="2"
			strokeLinecap="round"
			strokeLinejoin="round"
			aria-hidden="true"
			role="img"
		>
			<title>Search</title>
			<circle cx="11" cy="11" r="8" />
			<path d="m21 21-4.3-4.3" />
		</svg>
	);
}

export function BlogWithSearchMagazine({ blogs }: { blogs: BlogEntry[] }) {
	if (blogs.length === 0) {
		return (
			<section className="ss-home-hero ss-home-pad">
				<h1 className="ss-home-display">Blog</h1>
				<p className="ss-home-body mt-8">No blog posts yet.</p>
			</section>
		);
	}

	return (
		<>
			<section className="ss-home-hero ss-home-pad pb-8">
				<h1 className="ss-home-display">Blog</h1>
			</section>

			<section className="ss-home-pad pb-14">
				<PostSearchGrid blogs={blogs} />
			</section>
		</>
	);
}

function PostSearchGrid({ blogs: allBlogs }: { blogs: BlogEntry[] }) {
	const [search, setSearch] = useState("");

	const searcher = useMemo(
		() =>
			new FuzzySearch(allBlogs, ["title", "description"], {
				caseSensitive: false,
			}),
		[allBlogs]
	);

	const gridItems = useMemo(
		() => (search.trim() ? searcher.search(search) : allBlogs),
		[search, searcher, allBlogs]
	);

	return (
		<section aria-labelledby="archive-heading">
			<div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
				<div>
					<p className="ss-home-eyebrow">Archive</p>
					<h2 id="archive-heading" className="ss-home-h2 mt-2">
						All posts
					</h2>
				</div>
				<label className="relative w-full sm:max-w-md">
					<span className="sr-only">Search articles</span>
					<SearchIcon className="pointer-events-none absolute top-1/2 left-3.5 -translate-y-1/2 text-muted-foreground" />
					<input
						type="search"
						value={search}
						onChange={(e) => setSearch(e.target.value)}
						placeholder="Search blogs"
						className="w-full rounded-(--radius) border border-border bg-background py-2.5 pr-4 pl-11 text-sm text-foreground outline-none placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
					/>
				</label>
			</div>

			{gridItems.length === 0 ? (
				<p className="ss-home-body mt-8 border border-dashed border-border py-16 text-center">
					No articles match that search.
				</p>
			) : (
				<ul className="mt-8 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
					{gridItems.map((blog) => (
						<li key={blog.slug}>
							<PostCard blog={blog} />
						</li>
					))}
				</ul>
			)}
		</section>
	);
}

function PostCard({ blog }: { blog: BlogEntry }) {
	return (
		<Link href={blog.url} className="ss-home-post-card group/card">
			<div className="ss-home-post-card-media">
				{blog.image ? (
					<img src={blog.image} alt={blog.title} />
				) : (
					<div className="flex h-full items-center justify-center text-muted-foreground">
						No image
					</div>
				)}
			</div>
			<div className="ss-home-post-card-body">
				<time className="text-xs font-medium text-muted-foreground" dateTime={blog.date}>
					{format(new Date(blog.date), "MMM d, yyyy")}
				</time>
				<h3 className="ss-home-h3 mt-2">{blog.title}</h3>
				<p className="ss-home-body mt-2 flex-1 text-sm">{truncate(blog.description, 110)}</p>
				<div className="mt-4 flex items-center gap-2 pt-4">
					<img
						src={blog.authorAvatar}
						alt={blog.author}
						width={24}
						height={24}
						className="h-6 w-6 rounded-full object-cover"
					/>
					<span className="text-xs text-muted-foreground">{blog.author}</span>
				</div>
			</div>
		</Link>
	);
}
