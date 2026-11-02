import { isMarkdownPreferred } from "fumadocs-core/negotiation";
import { type NextRequest, NextResponse } from "next/server";
import { docsMarkdownPath } from "@/features/docs/docs-markdown-path.mts";

/** An agent that asks for Markdown gets a docs page's Markdown at the page's own URL. */
export function proxy(request: NextRequest) {
	if (isMarkdownPreferred(request)) {
		const markdownPath = docsMarkdownPath(request.nextUrl.pathname);
		if (markdownPath) return NextResponse.rewrite(new URL(markdownPath, request.nextUrl));
	}
	return NextResponse.next();
}

export const config = {
	matcher: "/docs/:path*",
};
