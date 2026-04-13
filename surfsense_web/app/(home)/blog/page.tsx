import { loader } from "fumadocs-core/source";
import type { Metadata } from "next";
import { blog } from "@/.source/server";
import { BlogWithSearchMagazine } from "./blog-magazine";

export const metadata: Metadata = {
	title: "Blog | SurfSense - AI Search & Knowledge Management",
	description:
		"Product updates, tutorials, and tips from the SurfSense team.",
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
		}))
		.sort(
			(a, b) => new Date(b.date).getTime() - new Date(a.date).getTime(),
		);

	return <BlogWithSearchMagazine blogs={blogs} />;
}
