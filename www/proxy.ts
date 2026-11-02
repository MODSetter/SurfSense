import { isMarkdownPreferred, rewritePath } from "fumadocs-core/negotiation";
import { type NextRequest, NextResponse } from "next/server";

const docsToMarkdown = rewritePath("/docs{/*path}", "/llms.mdx/docs{/*path}");

/** An agent that asks for Markdown gets a docs page's Markdown at the page's own URL. */
export function proxy(request: NextRequest) {
	if (isMarkdownPreferred(request)) {
		const markdownPath = docsToMarkdown.rewrite(request.nextUrl.pathname);
		if (markdownPath) return NextResponse.rewrite(new URL(markdownPath, request.nextUrl));
	}
	return NextResponse.next();
}

export const config = {
	matcher: "/docs/:path*",
};
