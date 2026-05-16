import { promises as fs } from "node:fs";
import path from "node:path";

export interface FaqEntry {
	question: string;
	answer: string;
}

/**
 * Extracts FAQ items from a blog post MDX file by parsing the `## FAQ` section.
 *
 * The FAQ section is bounded by `## FAQ` and the next H2 heading. Each H3 inside
 * is treated as a question, with the body until the next H3 (or the end of the
 * FAQ section) as its answer. Common Markdown decorations (links, bold, inline
 * code) are stripped so the JSON-LD output contains plain text suitable for
 * Google's FAQ rich-result eligibility checks.
 *
 * Returns an empty array when the post has no FAQ section, or when the file
 * cannot be read (e.g. for posts that do not yet exist on disk).
 */
export async function extractFaqFromBlogPost(slug: string): Promise<FaqEntry[]> {
	try {
		const filepath = path.join(process.cwd(), "blog", "content", `${slug}.mdx`);
		const content = await fs.readFile(filepath, "utf-8");
		return extractFaqFromContent(content);
	} catch {
		return [];
	}
}

export function extractFaqFromContent(content: string): FaqEntry[] {
	const faqHeading = content.match(/^##\s+FAQ\s*$/m);
	if (!faqHeading || faqHeading.index === undefined) return [];

	const afterFaq = content.slice(faqHeading.index + faqHeading[0].length);
	const nextH2 = afterFaq.match(/^##\s+/m);
	const faqBody = nextH2 ? afterFaq.slice(0, nextH2.index) : afterFaq;

	const blocks = faqBody.split(/^###\s+/m).slice(1);

	return blocks
		.map((block) => {
			const newlineIdx = block.indexOf("\n");
			const question = (newlineIdx === -1 ? block : block.slice(0, newlineIdx)).trim();
			const answer = (newlineIdx === -1 ? "" : block.slice(newlineIdx + 1))
				.trim()
				.replace(/\[([^\]]+)\]\([^)]+\)/g, "$1")
				.replace(/\*\*([^*]+)\*\*/g, "$1")
				.replace(/`([^`]+)`/g, "$1")
				.replace(/\s+/g, " ");
			return { question, answer };
		})
		.filter((item) => item.question.length > 0 && item.answer.length > 0);
}
