import { llms } from "fumadocs-core/source/llms";
import { source } from "@/features/docs/source";

type DocsPage = NonNullable<ReturnType<typeof source.getPage>>;

/**
 * A docs page as Markdown, led by the title and description the MDX body leaves out.
 * The URL tells apart pages that share a title across 2.0 and Legacy in `/llms-full.txt`.
 */
export async function renderPageMarkdown(page: DocsPage): Promise<string> {
	const body = await page.data.getText("processed");
	return `# ${page.data.title} (${page.url})\n\n${page.data.description ?? ""}\n\n${body}`;
}

export const docsLLMs = llms(source, { renderPage: renderPageMarkdown });

/** Where a page's Markdown is served; `next.config.mts` rewrites it to `app/llms.mdx`. */
export function markdownUrlOf(page: DocsPage): string {
	return `${page.url}.mdx`;
}
