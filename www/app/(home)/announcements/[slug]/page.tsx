import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";
import { notFound } from "next/navigation";
import { HomeBadge } from "@/components/site/home-badge";
import { HomeButton } from "@/components/site/home-button";
import { sectionSpacing } from "@/components/site/home-section-spacing";
import { ArticleJsonLd } from "@/components/site/json-ld";
import { siteText } from "@/components/site/site-text";
import { cn } from "@/components/ui/cn";
import { ArrowRightIcon, LinkSquare02Icon } from "@/components/ui/icons";
import {
	getPublishedAnnouncementPost,
	getPublishedAnnouncementPosts,
} from "@/features/announcements/announcements-source";
import { announcementPath } from "@/features/announcements/announcements-utils";
import { getMDXComponents } from "@/mdx-components";
import { categoryLabel } from "../category-label";
import { formatAnnouncementDate } from "../format-announcement-date";

/**
 * One announcement, laid out like a blog post. The header and image come from
 * `features/announcements/announcements-data.ts`, the text from its MDX body.
 * Site design via the `/announcements/` prefix in `components/site/site-shell.tsx`.
 */

const BASE_URL = "https://www.surfsense.com";

// Hourly, so a scheduled announcement's page opens without a redeploy.
export const revalidate = 3600;

export function generateStaticParams() {
	return getPublishedAnnouncementPosts().map((post) => ({ slug: post.id }));
}

export async function generateMetadata(props: {
	params: Promise<{ slug: string }>;
}): Promise<Metadata> {
	const { slug } = await props.params;
	const post = getPublishedAnnouncementPost(slug);

	if (!post) return {};

	const url = `${BASE_URL}${announcementPath(post.id)}`;
	// The 1200x630 preview when there is one: link previews crop anything else.
	const image = post.image?.og ?? post.image?.src ?? "/og-image.png";

	return {
		title: `${post.title} | SurfSense`,
		description: post.description,
		alternates: {
			canonical: url,
		},
		openGraph: {
			title: post.title,
			description: post.description,
			url,
			siteName: "SurfSense",
			locale: "en_US",
			type: "article",
			publishedTime: post.date,
			images: [{ url: image, alt: post.image?.alt }],
		},
		twitter: {
			card: "summary_large_image",
			title: post.title,
			description: post.description,
			creator: "@SurfSenseAI",
			site: "@SurfSenseAI",
			images: [image],
		},
	};
}

export default async function AnnouncementPage(props: { params: Promise<{ slug: string }> }) {
	const { slug } = await props.params;
	const post = getPublishedAnnouncementPost(slug);

	if (!post) notFound();

	const MDX = post.body;
	const isExternalLink = post.link?.url.startsWith("http") ?? false;

	return (
		<article className={sectionSpacing.foot}>
			<ArticleJsonLd
				title={post.title}
				description={post.description}
				url={`${BASE_URL}${announcementPath(post.id)}`}
				datePublished={post.date}
				author="SurfSense Team"
				image={post.image ? new URL(post.image.src, BASE_URL).toString() : undefined}
			/>

			<header className="mx-auto max-w-3xl pt-16 text-center md:pt-24">
				<Link
					href="/announcements"
					className="inline-flex items-center gap-1.5 text-sm font-medium text-muted-foreground hover:text-foreground focus-visible:rounded-xs focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
				>
					<ArrowRightIcon aria-hidden="true" className="size-4 rotate-180" />
					All announcements
				</Link>
				<p className="mt-6 flex flex-wrap items-center justify-center gap-3 text-sm text-muted-foreground">
					<span className="rounded-full bg-foreground px-3 py-1 text-xs font-medium text-background">
						{categoryLabel[post.category]}
					</span>
					{post.isImportant && <HomeBadge>Important</HomeBadge>}
					<time dateTime={post.date}>{formatAnnouncementDate(post.date, "long")}</time>
				</p>
				<h1 className={cn(siteText.h2, "mt-6 md:text-5xl")}>{post.title}</h1>
				<p className={cn(siteText.lede, "mx-auto mt-5 max-w-2xl")}>{post.description}</p>
			</header>

			{post.image && (
				<div className="mx-auto mt-10 max-w-5xl rounded-3xl bg-muted p-2 lg:mt-14">
					<div className="relative aspect-video overflow-hidden rounded-2xl">
						<Image
							src={post.image.src}
							alt={post.image.alt}
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

			{post.link && (
				<div className="mx-auto mt-12 flex max-w-3xl justify-center">
					<HomeButton asChild size="xl">
						<Link
							href={post.link.url}
							target={isExternalLink ? "_blank" : undefined}
							rel={isExternalLink ? "noopener noreferrer" : undefined}
						>
							{post.link.label}
							{isExternalLink ? (
								<LinkSquare02Icon aria-hidden="true" />
							) : (
								<ArrowRightIcon aria-hidden="true" />
							)}
						</Link>
					</HomeButton>
				</div>
			)}
		</article>
	);
}
