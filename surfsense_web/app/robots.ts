import type { MetadataRoute } from "next";

export default function robots(): MetadataRoute.Robots {
	return {
		rules: [
			{
				userAgent: "*",
				allow: "/",
				disallow: [
					"/dashboard/",
					"/desktop/",
					"/auth/",
					"/api/",
					"/invite/",
					"/public/",
					"/verify-token/",
				],
			},
		],
		sitemap: "https://surfsense.com/sitemap.xml",
	};
}
