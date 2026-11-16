/** A magnifier, for the web search built into the app; drawn like the Web Crawl globe. */
export function WebSearchLogo(props: React.SVGProps<SVGSVGElement>) {
	return (
		<svg viewBox="0 0 48 48" aria-hidden="true" {...props}>
			<g fill="none" strokeWidth="3">
				<path fill="#8fbffa" d="M5 21a16 16 0 1 0 32 0a16 16 0 1 0-32 0" />
				<path stroke="#2859c5" strokeLinejoin="round" d="M5 21a16 16 0 1 0 32 0a16 16 0 1 0-32 0" />
				<path stroke="#2859c5" strokeLinecap="round" d="M32.5 32.5L43 43" />
			</g>
		</svg>
	);
}
