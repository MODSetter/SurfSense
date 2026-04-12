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

const BASE_URL = "https://surfsense.com";

export default function sitemap(): MetadataRoute.Sitemap {
	const now = new Date();
	now.setMinutes(0, 0, 0);
	const lastModified = now;

	const staticPages: MetadataRoute.Sitemap = [
		{ url: `${BASE_URL}/`, lastModified, changeFrequency: "daily", priority: 1 },
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

	return [...staticPages, ...docsPages, ...blogPages, ...changelogPages];
}
