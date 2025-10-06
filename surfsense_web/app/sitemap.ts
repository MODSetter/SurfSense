import type { MetadataRoute } from "next";

export default function sitemap(): MetadataRoute.Sitemap {
	return [
		{
			url: "https://www.surfsense.com/",
			lastModified: new Date(),
			changeFrequency: "yearly",
			priority: 1,
		},
		{
			url: "https://www.surfsense.com/contact",
			lastModified: new Date(),
			changeFrequency: "yearly",
			priority: 1,
		},
		{
			url: "https://www.surfsense.com/pricing",
			lastModified: new Date(),
			changeFrequency: "yearly",
			priority: 0.9,
		},
		{
			url: "https://www.surfsense.com/privacy",
			lastModified: new Date(),
			changeFrequency: "monthly",
			priority: 0.9,
		},
		{
			url: "https://www.surfsense.com/terms",
			lastModified: new Date(),
			changeFrequency: "monthly",
			priority: 0.9,
		},
		{
			url: "https://www.surfsense.com/docs",
			lastModified: new Date(),
			changeFrequency: "weekly",
			priority: 0.9,
		},
		{
			url: "https://www.surfsense.com/docs/installation",
			lastModified: new Date(),
			changeFrequency: "weekly",
			priority: 0.9,
		},
		{
			url: "https://www.surfsense.com/docs/docker-installation",
			lastModified: new Date(),
			changeFrequency: "weekly",
			priority: 0.9,
		},
		{
			url: "https://www.surfsense.com/docs/manual-installation",
			lastModified: new Date(),
			changeFrequency: "weekly",
			priority: 0.9,
		},
	];
}
