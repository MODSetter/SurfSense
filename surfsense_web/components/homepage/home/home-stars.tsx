"use client";

import { IconBrandGithub } from "@tabler/icons-react";
import { useQuery } from "@tanstack/react-query";
import { cacheKeys } from "@/lib/query-client/cache-keys";

/**
 * GitHub star count for the homepage navigation.
 *
 * Fetched with TanStack Query under the same `cacheKeys.github.repoStars` key
 * the site's other star badge uses, so the two share one cache entry and the
 * count is fetched once per session rather than once per component.
 *
 * Deliberately still. The site's other badge animates the number in on a spring
 * with per-digit rolling wheels; that is unattended motion in a bar that is
 * visible for the whole visit, and this page has none of it anywhere else.
 *
 * Failure is quiet by design. The unauthenticated GitHub API allows 60 requests
 * an hour per IP, so a rate-limited visitor is a normal case, not an error
 * worth showing. When the count is unavailable the control stays a working link
 * to the repository with no number attached.
 */

const OWNER = "MODSetter";
const REPO = "SurfSense";
const REPO_HREF = `https://github.com/${OWNER}/${REPO}`;

/** `12345` renders as `12.3k`: the exact figure is noise at this size, and a
 *  compact string keeps the control's width stable as the repo grows.
 *
 *  Lowercased because `Intl` emits `12.3K` while GitHub itself writes `12.3k`,
 *  and this sits next to a GitHub mark. */
const compactFormatter = new Intl.NumberFormat("en-US", {
	notation: "compact",
	maximumFractionDigits: 1,
});

const compact = (value: number) => compactFormatter.format(value).toLowerCase();

export function HomeStars() {
	const { data: stars } = useQuery({
		queryKey: cacheKeys.github.repoStars(OWNER, REPO),
		queryFn: async ({ signal }) => {
			const response = await fetch(`https://api.github.com/repos/${OWNER}/${REPO}`, { signal });
			// Throwing rather than returning 0 keeps a rate-limited response from
			// rendering as a repository with no stars.
			if (!response.ok) {
				throw new Error(`GitHub responded ${response.status}`);
			}
			const data = await response.json();
			if (typeof data?.stargazers_count !== "number") {
				throw new Error("GitHub response had no stargazers_count");
			}
			return data.stargazers_count as number;
		},
		staleTime: 5 * 60 * 1000,
		retry: false,
	});

	return (
		<a
			href={REPO_HREF}
			target="_blank"
			rel="noreferrer noopener"
			className="ss-home-nav-stars"
			// The visible number is decorative next to this; the label is what a
			// screen reader announces, and it says what the link does either way.
			aria-label={
				typeof stars === "number"
					? `SurfSense on GitHub, ${stars.toLocaleString("en-US")} stars`
					: "SurfSense on GitHub"
			}
		>
			<IconBrandGithub aria-hidden="true" className="size-4 shrink-0" />
			{/* Rendered even while empty so the bar does not reflow when the count
			    arrives. */}
			<span aria-hidden="true" className="ss-home-nav-stars-count">
				{typeof stars === "number" ? compact(stars) : ""}
			</span>
		</a>
	);
}
