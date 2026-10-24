/**
 * The marketing site's text styles, as Tailwind class strings.
 *
 * One place to change a style that appears on every page. Strings rather than
 * components so they apply to whatever element the markup needs; combine with
 * `cn()` to add spacing or a size.
 */
export const siteText = {
	display:
		"text-4xl leading-none font-semibold tracking-tight text-balance md:text-5xl lg:text-6xl",
	h2: "text-3xl leading-tight font-semibold tracking-tight text-balance md:text-4xl",
	h3: "text-lg leading-snug font-semibold tracking-tight",
	lede: "text-base leading-relaxed text-pretty text-muted-foreground md:text-lg lg:text-xl",
	body: "leading-relaxed text-pretty text-muted-foreground",
	eyebrow: "text-xs font-medium tracking-widest text-muted-foreground uppercase",
	/** An inline link inside running text. */
	link: "text-primary underline decoration-primary/40 underline-offset-4 transition-[color,text-decoration-color] duration-150 ease-out hover:decoration-current focus-visible:rounded-xs focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring",
	/** A standalone "go somewhere" link, usually followed by an arrow. */
	forward:
		"inline-flex items-center gap-1.5 text-sm font-medium text-primary transition-colors duration-100 ease-out hover:text-foreground focus-visible:rounded-xs focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring",
} as const;
