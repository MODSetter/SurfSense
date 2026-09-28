/** A globe, for the Web Crawl plugin. */
export function WebCrawlLogo(props: React.SVGProps<SVGSVGElement>) {
	return (
		<svg viewBox="0 0 48 48" aria-hidden="true" {...props}>
			<g fill="none" strokeWidth="3">
				<path fill="#8fbffa" d="M3 24a21 21 0 1 0 42 0a21 21 0 1 0-42 0" />
				<path stroke="#2859c5" strokeLinejoin="round" d="M3 24a21 21 0 1 0 42 0a21 21 0 1 0-42 0" />
				<path stroke="#2859c5" strokeLinejoin="round" d="M15 24a9 21 0 1 1 18 0a9 21 0 1 1-18 0" />
				<path
					stroke="#2859c5"
					strokeLinecap="round"
					strokeLinejoin="round"
					d="M4.5 31h39m-39-14h39"
				/>
			</g>
		</svg>
	);
}
