/**
 * Where `proxy.ts` sends a docs request that prefers Markdown, or null to let it through.
 *
 * A `.mdx` URL is left alone: the proxy runs before `next.config.mts`'s rewrite,
 * which strips the extension, and a slug ending in `.mdx` finds no page.
 */
export function docsMarkdownPath(pathname: string): string | null {
	if (pathname !== "/docs" && !pathname.startsWith("/docs/")) return null;
	if (pathname.endsWith(".mdx")) return null;
	return `/llms.mdx${pathname}`;
}
