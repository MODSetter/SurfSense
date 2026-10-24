import { defineConfig, defineDocs, frontmatterSchema } from "fumadocs-mdx/config";
import lastModified from "fumadocs-mdx/plugins/last-modified";
import { z } from "zod";

export const docs = defineDocs({
	dir: "content/docs",
});

export const changelog = defineDocs({
	dir: "content/changelog",
	docs: {
		schema: frontmatterSchema.omit({ title: true, description: true }).extend({
			date: z.string(),
			version: z.string().optional(),
		}),
	},
});

export const blog = defineDocs({
	dir: "content/blog",
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

// Announcement bodies, one `<id>.mdx` per entry in
// `features/announcements/announcements-data.ts`. The page reads the title, date,
// category, image and link from that entry, so frontmatter is optional here.
export const announcements = defineDocs({
	dir: "content/announcements",
	docs: {
		schema: frontmatterSchema.omit({ title: true, description: true }),
	},
});

export default defineConfig({
	plugins: [lastModified()],
	mdxOptions: {
		providerImportSource: "@/mdx-components",
	},
});
