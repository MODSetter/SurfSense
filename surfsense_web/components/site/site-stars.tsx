import { GithubLogo } from "@/components/homepage/icons/github-logo";
import { cn } from "@/lib/utils";

/**
 * GitHub star count in the site navigation.
 *
 * A presentational component: the number is fetched and cached on the server
 * (`github-stars.ts`) and handed down as a prop, so there is no query, no
 * loading state and nothing to shift when data arrives.
 *
 * `null` means the count was unavailable. The control stays a working link to
 * the repository with no number attached, and the count keeps its reserved
 * width so the bar looks the same either way.
 */

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

export function SiteStars({
	count,
	href,
	className,
}: {
	count: number | null;
	href: string;
	className?: string;
}) {
	return (
		<a
			href={href}
			target="_blank"
			rel="noreferrer noopener"
			className={cn(
				"inline-flex items-center gap-1.5 rounded-lg px-2 py-1.5 text-sm font-medium text-muted-foreground tabular-nums transition-colors duration-100 hover:text-foreground focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-ring",
				className
			)}
			// The visible number is decorative next to this; the label is what a
			// screen reader announces, and it says what the link does either way.
			aria-label={
				count === null
					? "SurfSense on GitHub"
					: `SurfSense on GitHub, ${count.toLocaleString("en-US")} stars`
			}
		>
			<GithubLogo aria-hidden="true" className="size-4 shrink-0" />
			<span aria-hidden="true" className="min-w-8">
				{count === null ? "" : compact(count)}
			</span>
		</a>
	);
}
