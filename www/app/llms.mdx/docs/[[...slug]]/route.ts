import { notFound } from "next/navigation";
import { renderPageMarkdown } from "@/features/docs/docs-llms";
import { source } from "@/features/docs/source";

export const revalidate = false;

export async function GET(_req: Request, { params }: RouteContext<"/llms.mdx/docs/[[...slug]]">) {
	const { slug } = await params;
	const page = source.getPage(slug);
	if (!page) notFound();

	return new Response(await renderPageMarkdown(page), {
		headers: { "Content-Type": "text/markdown; charset=utf-8" },
	});
}

export function generateStaticParams() {
	return source.generateParams();
}
