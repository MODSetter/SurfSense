import { loader } from "fumadocs-core/source";
import type { MetadataRoute } from "next";
import { blog, changelog } from "@/.source/server";
import { source as docsSource } from "@/lib/source";

const blogSource = loader({
	baseUrl: "/blog",
	source: blog.toFumadocsSource(),
});

const changelogSource = loader({
	baseUrl: "/changelog",
	source: changelog.toFumadocsSource(),
});

const BASE_URL = "https://www.surfsense.com";
const BACKEND_URL = process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL || "http://localhost:8000";

async function getFreeModelSlugs(): Promise<string[]> {
	try {
		const res = await fetch(`${BACKEND_URL}/api/v1/public/anon-chat/models`, {
			next: { revalidate: 3600 },
		});
		if (!res.ok) return [];
		const models = await res.json();
		return models
			.filter((m: { seo_slug?: string }) => m.seo_slug)
			.map((m: { seo_slug: string }) => m.seo_slug);
	} catch {
		return [];
	}
}

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
	const now = new Date();
	now.setMinutes(0, 0, 0);
	const lastModified = now;

	const staticPages: MetadataRoute.Sitemap = [
		{ url: `${BASE_URL}/`, lastModified, changeFrequency: "daily", priority: 1 },
		{ url: `${BASE_URL}/free`, lastModified, changeFrequency: "daily", priority: 0.95 },
		{ url: `${BASE_URL}/pricing`, lastModified, changeFrequency: "weekly", priority: 0.9 },
		{ url: `${BASE_URL}/contact`, lastModified, changeFrequency: "monthly", priority: 0.7 },
		{ url: `${BASE_URL}/blog`, lastModified, changeFrequency: "daily", priority: 0.9 },
		{ url: `${BASE_URL}/changelog`, lastModified, changeFrequency: "weekly", priority: 0.7 },
		{ url: `${BASE_URL}/announcements`, lastModified, changeFrequency: "weekly", priority: 0.6 },
		{ url: `${BASE_URL}/docs`, lastModified, changeFrequency: "daily", priority: 1 },
		{ url: `${BASE_URL}/privacy`, lastModified, changeFrequency: "monthly", priority: 0.3 },
		{ url: `${BASE_URL}/terms`, lastModified, changeFrequency: "monthly", priority: 0.3 },
		{ url: `${BASE_URL}/login`, lastModified, changeFrequency: "monthly", priority: 0.5 },
		{ url: `${BASE_URL}/register`, lastModified, changeFrequency: "monthly", priority: 0.5 },
	];

	const slugs = await getFreeModelSlugs();
	const freeModelPages: MetadataRoute.Sitemap = slugs.map((slug) => ({
		url: `${BASE_URL}/free/${slug}`,
		lastModified,
		changeFrequency: "daily" as const,
		priority: 0.9,
	}));

	const docsPages: MetadataRoute.Sitemap = docsSource.getPages().map((page) => ({
		url: `${BASE_URL}${page.url}`,
		lastModified,
		changeFrequency: "weekly" as const,
		priority: 0.8,
	}));

	const blogPages: MetadataRoute.Sitemap = blogSource.getPages().map((page) => ({
		url: `${BASE_URL}${page.url}`,
		lastModified,
		changeFrequency: "weekly" as const,
		priority: 0.8,
	}));

	const changelogPages: MetadataRoute.Sitemap = changelogSource.getPages().map((page) => ({
		url: `${BASE_URL}${page.url}`,
		lastModified,
		changeFrequency: "monthly" as const,
		priority: 0.5,
	}));

	return [...staticPages, ...freeModelPages, ...docsPages, ...blogPages, ...changelogPages];
}
