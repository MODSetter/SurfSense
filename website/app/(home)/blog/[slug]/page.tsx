import { loader } from "fumadocs-core/source";
import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";
import { notFound } from "next/navigation";
import { blog } from "@/.source/server";
import { HomeBadge } from "@/components/homepage/home/home-badge";
import { sectionSpacing } from "@/components/homepage/home/home-section-spacing";
import { ArticleJsonLd, FAQJsonLd } from "@/components/seo/json-ld";
import { siteText } from "@/components/site/site-text";
import { ArrowRightIcon, DotIcon } from "@/components/ui/icons";
import { extractFaqFromBlogPost } from "@/lib/blog-faq";
import { cn, formatDate } from "@/lib/utils";
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
	// Populated by Fumadocs when `lastModifiedTime: "git"` is set in source.config.ts.
	lastModified?: Date;
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
	const page = (source.getPages() as BlogPageItem[]).find((p) => p.slugs.join("/") === slug);

	if (!page) return {};

	return {
		title: `${page.data.title} | SurfSense Blog`,
		description: page.data.description,
		alternates: {
			canonical: `https://www.surfsense.com/blog/${slug}`,
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

export default async function BlogPostPage(props: { params: Promise<{ slug: string }> }) {
	const { slug } = await props.params;
	const page = (source.getPages() as BlogPageItem[]).find((p) => p.slugs.join("/") === slug);

	if (!page) notFound();

	const MDX = page.data.body;
	const date = new Date(page.data.date);
	const dateModified = page.data.lastModified
		? new Date(page.data.lastModified).toISOString()
		: undefined;
	const faqEntries = await extractFaqFromBlogPost(slug);

	const author = page.data.author ?? "SurfSense Team";

	return (
		<article className={sectionSpacing.foot}>
			<ArticleJsonLd
				title={page.data.title}
				description={page.data.description}
				url={`https://www.surfsense.com/blog/${slug}`}
				datePublished={page.data.date}
				dateModified={dateModified}
				author={author}
				image={page.data.image ? `https://www.surfsense.com${page.data.image}` : undefined}
			/>
			{faqEntries.length > 0 && <FAQJsonLd questions={faqEntries} />}

			{/* Centred like every homepage section head. */}
			<header className="mx-auto max-w-3xl pt-16 text-center md:pt-24">
				<Link
					href="/blog"
					className="inline-flex items-center gap-1.5 text-sm font-medium text-muted-foreground hover:text-foreground focus-visible:rounded-xs focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
				>
					<ArrowRightIcon aria-hidden="true" className="size-4 rotate-180" />
					All posts
				</Link>
				<h1 className={cn(siteText.h2, "mt-6 md:text-5xl")}>{page.data.title}</h1>
				{page.data.description && (
					<p className={cn(siteText.lede, "mx-auto mt-5 max-w-2xl")}>{page.data.description}</p>
				)}
				<p className="mt-6 flex items-center justify-center gap-3 text-sm text-muted-foreground">
					{page.data.authorAvatar && (
						<Image
							src={page.data.authorAvatar}
							alt=""
							width={28}
							height={28}
							className="size-7 rounded-full object-cover"
						/>
					)}
					<span className="font-medium text-foreground">{author}</span>
					<DotIcon aria-hidden="true" className="size-4" />
					<time dateTime={page.data.date}>{formatDate(date)}</time>
				</p>
				{page.data.tags && page.data.tags.length > 0 && (
					<ul className="m-0 mt-6 flex list-none flex-wrap justify-center gap-2 p-0">
						{page.data.tags.map((tag: string) => (
							<li key={tag}>
								<HomeBadge>{tag}</HomeBadge>
							</li>
						))}
					</ul>
				)}
			</header>

			{page.data.image && (
				<div className="mx-auto mt-10 max-w-5xl rounded-3xl bg-muted p-2 lg:mt-14">
					<div className="relative aspect-2/1 overflow-hidden rounded-2xl">
						<Image
							src={page.data.image}
							alt={page.data.title}
							fill
							className="object-cover"
							priority
							sizes="(max-width: 1024px) 100vw, 1024px"
						/>
					</div>
				</div>
			)}

			<div className="prose mx-auto mt-12 max-w-3xl prose-headings:scroll-mt-24 prose-headings:font-semibold prose-headings:tracking-tight prose-headings:text-balance prose-p:text-pretty prose-a:no-underline prose-img:rounded-2xl prose-img:border prose-img:border-border prose-img:shadow-none lg:mt-16">
				<MDX components={getMDXComponents()} />
			</div>
		</article>
	);
}
