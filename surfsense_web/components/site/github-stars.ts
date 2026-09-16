import "server-only";

import { REPO_URL } from "@/components/site/site-content";

/**
 * The repository's star count, fetched on the server and cached.
 *
 * This used to run in the visitor's browser on every page load. Moving it here
 * buys three things at once:
 *
 *   - the number is in the HTML on first paint, so the navigation cannot shift
 *     when it arrives;
 *   - visitors make no request to github.com, which matters on a site whose
 *     argument is that nothing leaves your machine;
 *   - GitHub allows 60 unauthenticated requests an hour per IP. Per-visitor
 *     that is a burst away from being rate-limited, at which point the count
 *     silently disappeared for everyone behind that address. Per-hour it is not
 *     a limit that can realistically be reached.
 *
 * Cached through Next's Data Cache. On a managed platform that cache is shared,
 * so this is one request an hour for the whole deployment; self-hosted it is one
 * an hour per container, which is still four orders of magnitude fewer than one
 * per visitor.
 */

const OWNER = "MODSetter";
const REPO = "SurfSense";
const ONE_HOUR = 3600;

export const STARS_HREF = REPO_URL;

export async function getStarCount(): Promise<number | null> {
	try {
		const response = await fetch(`https://api.github.com/repos/${OWNER}/${REPO}`, {
			next: { revalidate: ONE_HOUR },
		});

		if (!response.ok) {
			return null;
		}

		const data = await response.json();
		return typeof data?.stargazers_count === "number" ? data.stargazers_count : null;
	} catch {
		// Never throw. An unreachable GitHub at build time would otherwise fail the
		// whole build, and at runtime it would take down every page under this
		// layout — to hide one number in the corner of the navigation.
		return null;
	}
}
