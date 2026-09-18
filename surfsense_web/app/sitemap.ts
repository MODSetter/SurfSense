import { loader } from "fumadocs-core/source";
import type { MetadataRoute } from "next";
import { blog, changelog } from "@/.source/server";
import { getAllConnectorSlugs } from "@/lib/connectors-marketing";
import { FREE_MODELS } from "@/lib/free-models";
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

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
	const now = new Date();
	now.setMinutes(0, 0, 0);
	const lastModified = now;

	const staticPages: MetadataRoute.Sitemap = [
		{ url: `${BASE_URL}/`, lastModified, changeFrequency: "daily", priority: 1 },
		{ url: `${BASE_URL}/free`, lastModified, changeFrequency: "daily", priority: 0.95 },
		// "How do I install it" is transactional intent this niche can actually
		// win — Jan's `/download` ranks 7th on its own volume — so the page needs
		// to be in here (`plans/community-local/seo/02-page-briefs.md`).
		{ url: `${BASE_URL}/downloads`, lastModified, changeFrequency: "weekly", priority: 0.95 },
		{
			url: `${BASE_URL}/private-ai-for-business`,
			lastModified,
			changeFrequency: "weekly",
			priority: 0.9,
		},
		{ url: `${BASE_URL}/plugins`, lastModified, changeFrequency: "weekly", priority: 0.9 },
		{ url: `${BASE_URL}/mcp-server`, lastModified, changeFrequency: "weekly", priority: 0.85 },
		{
			url: `${BASE_URL}/external-mcp-connectors`,
			lastModified,
			changeFrequency: "weekly",
			priority: 0.85,
		},
		{ url: `${BASE_URL}/pricing`, lastModified, changeFrequency: "weekly", priority: 0.9 },
		{ url: `${BASE_URL}/contact`, lastModified, changeFrequency: "monthly", priority: 0.7 },
		{ url: `${BASE_URL}/blog`, lastModified, changeFrequency: "daily", priority: 0.9 },
		{ url: `${BASE_URL}/changelog`, lastModified, changeFrequency: "weekly", priority: 0.7 },
		{ url: `${BASE_URL}/announcements`, lastModified, changeFrequency: "weekly", priority: 0.6 },
		// /docs itself redirects to the current version section, so the version
		// roots come from `docsPages` below instead of being listed here.
		// The one indexable page under /license: the other two are noindex, one
		// being a form keyed on an email address and the other serving a license
		// file. This one is a help document, and the license emails link it.
		{
			url: `${BASE_URL}/license/activate`,
			lastModified,
			changeFrequency: "monthly",
			priority: 0.4,
		},
		{ url: `${BASE_URL}/privacy`, lastModified, changeFrequency: "monthly", priority: 0.3 },
		{ url: `${BASE_URL}/terms`, lastModified, changeFrequency: "monthly", priority: 0.3 },
		{ url: `${BASE_URL}/login`, lastModified, changeFrequency: "monthly", priority: 0.5 },
		{ url: `${BASE_URL}/register`, lastModified, changeFrequency: "monthly", priority: 0.5 },
	];

	// The static catalog rather than the hosted anon-chat endpoint, which is
	// closed. The slugs the old service published are not listed here — there is
	// no list left to read them from — but `/free/[model_slug]` still answers for
	// them, so the ones Google already holds keep working.
	const freeModelPages: MetadataRoute.Sitemap = FREE_MODELS.map((model) => ({
		url: `${BASE_URL}/free/${model.slug}`,
		lastModified,
		changeFrequency: "weekly" as const,
		priority: 0.9,
	}));

	const connectorPages: MetadataRoute.Sitemap = getAllConnectorSlugs().map((slug) => ({
		url: `${BASE_URL}/${slug}`,
		lastModified,
		changeFrequency: "weekly" as const,
		priority: 0.85,
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

	return [
		...staticPages,
		...connectorPages,
		...freeModelPages,
		...docsPages,
		...blogPages,
		...changelogPages,
	];
}
