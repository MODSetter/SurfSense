import type { MetadataRoute } from "next";

// Returns a date rounded to the current hour (updates only once per hour)
function getHourlyDate(): Date {
	const now = new Date();
	now.setMinutes(0, 0, 0);
	return now;
}

export default function sitemap(): MetadataRoute.Sitemap {
	const lastModified = getHourlyDate();

	return [
		{
			url: "https://www.surfsense.com/",
			lastModified,
			changeFrequency: "yearly",
			priority: 1,
		},
		{
			url: "https://www.surfsense.com/contact",
			lastModified,
			changeFrequency: "yearly",
			priority: 1,
		},
		{
			url: "https://www.surfsense.com/pricing",
			lastModified,
			changeFrequency: "yearly",
			priority: 0.9,
		},
		{
			url: "https://www.surfsense.com/privacy",
			lastModified,
			changeFrequency: "monthly",
			priority: 0.9,
		},
		{
			url: "https://www.surfsense.com/terms",
			lastModified,
			changeFrequency: "monthly",
			priority: 0.9,
		},
		// Documentation pages
		{
			url: "https://www.surfsense.com/docs",
			lastModified,
			changeFrequency: "weekly",
			priority: 0.9,
		},
		{
			url: "https://www.surfsense.com/docs/installation",
			lastModified,
			changeFrequency: "weekly",
			priority: 0.9,
		},
		{
			url: "https://www.surfsense.com/docs/docker-installation",
			lastModified,
			changeFrequency: "weekly",
			priority: 0.9,
		},
		{
			url: "https://www.surfsense.com/docs/manual-installation",
			lastModified,
			changeFrequency: "weekly",
			priority: 0.9,
		},
		// Connector documentation
		{
			url: "https://www.surfsense.com/docs/connectors/airtable",
			lastModified,
			changeFrequency: "weekly",
			priority: 0.8,
		},
		{
			url: "https://www.surfsense.com/docs/connectors/bookstack",
			lastModified,
			changeFrequency: "weekly",
			priority: 0.8,
		},
		{
			url: "https://www.surfsense.com/docs/connectors/circleback",
			lastModified,
			changeFrequency: "weekly",
			priority: 0.8,
		},
		{
			url: "https://www.surfsense.com/docs/connectors/clickup",
			lastModified,
			changeFrequency: "weekly",
			priority: 0.8,
		},
		{
			url: "https://www.surfsense.com/docs/connectors/confluence",
			lastModified,
			changeFrequency: "weekly",
			priority: 0.8,
		},
		{
			url: "https://www.surfsense.com/docs/connectors/discord",
			lastModified,
			changeFrequency: "weekly",
			priority: 0.8,
		},
		{
			url: "https://www.surfsense.com/docs/connectors/elasticsearch",
			lastModified,
			changeFrequency: "weekly",
			priority: 0.8,
		},
		{
			url: "https://www.surfsense.com/docs/connectors/github",
			lastModified,
			changeFrequency: "weekly",
			priority: 0.8,
		},
		{
			url: "https://www.surfsense.com/docs/connectors/gmail",
			lastModified,
			changeFrequency: "weekly",
			priority: 0.8,
		},
		{
			url: "https://www.surfsense.com/docs/connectors/google-calendar",
			lastModified,
			changeFrequency: "weekly",
			priority: 0.8,
		},
		{
			url: "https://www.surfsense.com/docs/connectors/google-drive",
			lastModified,
			changeFrequency: "weekly",
			priority: 0.8,
		},
		{
			url: "https://www.surfsense.com/docs/connectors/jira",
			lastModified,
			changeFrequency: "weekly",
			priority: 0.8,
		},
		{
			url: "https://www.surfsense.com/docs/connectors/linear",
			lastModified,
			changeFrequency: "weekly",
			priority: 0.8,
		},
		{
			url: "https://www.surfsense.com/docs/connectors/luma",
			lastModified,
			changeFrequency: "weekly",
			priority: 0.8,
		},
		{
			url: "https://www.surfsense.com/docs/connectors/notion",
			lastModified,
			changeFrequency: "weekly",
			priority: 0.8,
		},
		{
			url: "https://www.surfsense.com/docs/connectors/slack",
			lastModified,
			changeFrequency: "weekly",
			priority: 0.8,
		},
		{
			url: "https://www.surfsense.com/docs/connectors/web-crawler",
			lastModified,
			changeFrequency: "weekly",
			priority: 0.8,
		},
	];
}
