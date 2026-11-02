import {
	DocsBody,
	DocsDescription,
	DocsPage,
	DocsTitle,
	MarkdownCopyButton,
	PageLastUpdate,
	ViewOptionsPopover,
} from "fumadocs-ui/layouts/spacious/page";
import { notFound } from "next/navigation";
import { cache } from "react";
import { markdownUrlOf } from "@/features/docs/docs-llms";
import { source } from "@/features/docs/source";
import { getMDXComponents } from "@/mdx-components";

const getDocPage = cache((slug?: string[]) => {
	return source.getPage(slug);
});

export default async function Page(props: { params: Promise<{ slug?: string[] }> }) {
	const params = await props.params;
	const page = getDocPage(params.slug);
	if (!page) notFound();

	const MDX = page.data.body;
	const markdownUrl = markdownUrlOf(page);

	return (
		<DocsPage toc={page.data.toc} full={page.data.full}>
			<DocsTitle>{page.data.title}</DocsTitle>
			<DocsDescription className="mb-0">{page.data.description}</DocsDescription>
			<div className="flex flex-row items-center gap-2 border-b pb-6">
				<MarkdownCopyButton markdownUrl={markdownUrl} />
				<ViewOptionsPopover
					markdownUrl={markdownUrl}
					githubUrl={`https://github.com/MODSetter/SurfSense/blob/main/www/content/docs/${page.path}`}
					pageUrl={`https://www.surfsense.com${page.url}`}
				/>
			</div>
			<DocsBody>
				<MDX components={getMDXComponents()} />
			</DocsBody>
			{page.data.lastModified && <PageLastUpdate date={page.data.lastModified} />}
		</DocsPage>
	);
}

export async function generateStaticParams() {
	return source.generateParams();
}

export async function generateMetadata(props: { params: Promise<{ slug?: string[] }> }) {
	const params = await props.params;
	const page = getDocPage(params.slug);
	if (!page) notFound();

	const slugPath = params.slug ? params.slug.join("/") : "";
	return {
		title: `${page.data.title} | SurfSense Docs`,
		description: page.data.description,
		alternates: {
			canonical: `https://www.surfsense.com/docs${slugPath ? `/${slugPath}` : ""}`,
		},
		openGraph: {
			title: `${page.data.title} | SurfSense Docs`,
			description: page.data.description,
			type: "article",
			images: [{ url: "/og-image.png", width: 1200, height: 630, alt: "SurfSense docs" }],
		},
	};
}
