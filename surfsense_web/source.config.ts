import { defineConfig, defineDocs, frontmatterSchema } from "fumadocs-mdx/config";
import lastModified from "fumadocs-mdx/plugins/last-modified";
import { z } from "zod";

export const docs = defineDocs({
	dir: "content/docs",
});

export const changelog = defineDocs({
	dir: "changelog/content",
	docs: {
		schema: frontmatterSchema.extend({
			date: z.string(),
			version: z.string().optional(),
		}),
	},
});

export const blog = defineDocs({
	dir: "blog/content",
	docs: {
		schema: frontmatterSchema.extend({
			date: z.string(),
			image: z.string().optional(),
			author: z.string().default("SurfSense Team"),
			authorAvatar: z.string().optional(),
			tags: z.array(z.string()).optional(),
			// Pin this post into the featured section above the archive grid.
			// Multiple posts can be featured at once; ordering within the
			// featured section follows `featured_order` ascending and falls
			// back to `date` descending.
			featured: z.boolean().optional().default(false),
			featured_order: z.number().optional(),
		}),
	},
});

export default defineConfig({
	plugins: [lastModified()],
	mdxOptions: {
		providerImportSource: "@/mdx-components",
	},
});
