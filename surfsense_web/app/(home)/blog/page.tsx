import { loader } from "fumadocs-core/source";
import type { Metadata } from "next";
import { blog } from "@/.source/server";
import { BlogWithSearchMagazine } from "./blog-magazine";

export const metadata: Metadata = {
	title: "Blog | SurfSense - AI Search & Knowledge Management",
	description: "Product updates, tutorials, and tips from the SurfSense team.",
	alternates: {
		canonical: "https://surfsense.com/blog",
	},
};

const source = loader({
	baseUrl: "/blog",
	source: blog.toFumadocsSource(),
});

export interface BlogEntry {
	title: string;
	description: string;
	date: string;
	slug: string;
	url: string;
	image: string;
	author: string;
	authorAvatar: string;
	featured: boolean;
	featuredOrder?: number;
}

export default async function BlogPage() {
	const allPages = source.getPages() as Array<{
		url: string;
		slugs: string[];
		data: {
			title: string;
			description: string;
			date: string;
			image?: string;
			author?: string;
			authorAvatar?: string;
			featured?: boolean;
			featured_order?: number;
		};
	}>;

	const blogs: BlogEntry[] = allPages
		.map((page) => ({
			title: page.data.title,
			description: page.data.description ?? "",
			date: page.data.date,
			slug: page.slugs.join("/"),
			url: page.url,
			image: page.data.image ?? "/og-image.png",
			author: page.data.author ?? "SurfSense Team",
			authorAvatar: page.data.authorAvatar ?? "/logo.png",
			featured: page.data.featured ?? false,
			featuredOrder: page.data.featured_order,
		}))
		.sort((a, b) => {
			// Featured first; then by `featured_order` asc within featured;
			// then by `date` desc as the universal tie-breaker.
			if (a.featured !== b.featured) return a.featured ? -1 : 1;
			if (a.featured && b.featured) {
				const aOrder = a.featuredOrder ?? Number.POSITIVE_INFINITY;
				const bOrder = b.featuredOrder ?? Number.POSITIVE_INFINITY;
				if (aOrder !== bOrder) return aOrder - bOrder;
			}
			return new Date(b.date).getTime() - new Date(a.date).getTime();
		});

	return <BlogWithSearchMagazine blogs={blogs} />;
}
