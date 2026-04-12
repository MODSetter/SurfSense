import { loader } from "fumadocs-core/source";
import type { Metadata } from "next";
import Image from "next/image";
import { notFound } from "next/navigation";
import { blog } from "@/.source/server";
import { BreadcrumbNav } from "@/components/seo/breadcrumb-nav";
import { ArticleJsonLd } from "@/components/seo/json-ld";
import { formatDate } from "@/lib/utils";
import { getMDXComponents } from "@/mdx-components";

const source = loader({
	baseUrl: "/blog",
	source: blog.toFumadocsSource(),
});

interface BlogData {
	title: string;
	description: string;
	date: string;
	image?: string;
	author?: string;
	authorAvatar?: string;
	tags?: string[];
	body: React.ComponentType<{
		components?: Record<string, React.ComponentType>;
	}>;
}

interface BlogPageItem {
	url: string;
	slugs: string[];
	data: BlogData;
}

export async function generateStaticParams() {
	return source.getPages().map((page) => ({
		slug: (page as BlogPageItem).slugs.join("/"),
	}));
}

export async function generateMetadata(props: {
	params: Promise<{ slug: string }>;
}): Promise<Metadata> {
	const { slug } = await props.params;
	const page = (source.getPages() as BlogPageItem[]).find(
		(p) => p.slugs.join("/") === slug,
	);

	if (!page) return {};

	return {
		title: `${page.data.title} | SurfSense Blog`,
		description: page.data.description,
		alternates: {
			canonical: `https://surfsense.com/blog/${slug}`,
		},
		openGraph: {
			title: page.data.title,
			description: page.data.description,
			type: "article",
			publishedTime: page.data.date,
			authors: [page.data.author ?? "SurfSense Team"],
			tags: page.data.tags,
			images: page.data.image ? [{ url: page.data.image }] : [{ url: "/og-image.png" }],
		},
		twitter: {
			card: "summary_large_image",
			title: page.data.title,
			description: page.data.description,
			images: page.data.image ? [page.data.image] : ["/og-image.png"],
		},
	};
}

export default async function BlogPostPage(props: {
	params: Promise<{ slug: string }>;
}) {
	const { slug } = await props.params;
	const page = (source.getPages() as BlogPageItem[]).find(
		(p) => p.slugs.join("/") === slug,
	);

	if (!page) notFound();

	const MDX = page.data.body;
	const date = new Date(page.data.date);

	return (
		<div className="min-h-screen relative pt-20">
			<ArticleJsonLd
				title={page.data.title}
				description={page.data.description}
				url={`https://surfsense.com/blog/${slug}`}
				datePublished={page.data.date}
				author={page.data.author ?? "SurfSense Team"}
				image={page.data.image ? `https://surfsense.com${page.data.image}` : undefined}
			/>
			<div className="max-w-3xl mx-auto px-6 lg:px-10 pt-10 pb-20">
				<BreadcrumbNav
					items={[
						{ name: "Home", href: "/" },
						{ name: "Blog", href: "/blog" },
						{ name: page.data.title, href: `/blog/${slug}` },
					]}
					className="mb-8"
				/>

				{page.data.image && (
					<div className="relative aspect-2/1 overflow-hidden rounded-2xl mb-8">
						<Image
							src={page.data.image}
							alt={page.data.title}
							fill
							className="object-cover"
							priority
							sizes="(max-width: 768px) 100vw, 768px"
						/>
					</div>
				)}

				<div className="space-y-4 mb-10">
					<h1 className="text-3xl md:text-4xl font-bold tracking-tight text-balance">
						{page.data.title}
					</h1>

					{page.data.tags && page.data.tags.length > 0 && (
						<div className="flex flex-wrap gap-2">
							{page.data.tags.map((tag: string) => (
								<span
									key={tag}
									className="h-6 w-fit px-2.5 text-xs font-medium bg-muted text-muted-foreground rounded-full border flex items-center justify-center"
								>
									{tag}
								</span>
							))}
						</div>
					)}

					<div className="flex items-center gap-3 text-sm text-muted-foreground">
						{page.data.authorAvatar && (
							<Image
								src={page.data.authorAvatar}
								alt={page.data.author ?? "SurfSense Team"}
								width={32}
								height={32}
								className="h-8 w-8 rounded-full object-cover"
							/>
						)}
						<span className="font-medium text-foreground">
							{page.data.author ?? "SurfSense Team"}
						</span>
						<span>·</span>
						<time dateTime={page.data.date}>{formatDate(date)}</time>
					</div>
				</div>

				<div className="prose dark:prose-invert max-w-none prose-headings:scroll-mt-8 prose-headings:font-semibold prose-a:no-underline prose-headings:tracking-tight prose-headings:text-balance prose-p:tracking-tight prose-p:text-balance prose-img:rounded-xl prose-img:shadow-lg">
					<MDX components={getMDXComponents()} />
				</div>
			</div>
		</div>
	);
}
