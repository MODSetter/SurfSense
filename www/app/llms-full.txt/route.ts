import { docsLLMs } from "@/features/docs/docs-llms";

export const revalidate = false;

export async function GET() {
	return new Response(await docsLLMs.full(), {
		headers: { "Content-Type": "text/markdown; charset=utf-8" },
	});
}
