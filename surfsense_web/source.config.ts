import { defineConfig, defineDocs, frontmatterSchema } from "fumadocs-mdx/config";
import { z } from "zod";

export const docs = defineDocs({
	dir: "content/docs",
});

export const changelog = defineDocs({
	dir: "changelog/content",
	docs: {
		schema: frontmatterSchema.extend({
			date: z.string(),
			tags: z.array(z.string()).optional(),
			version: z.string().optional(),
		}),
	},
});

export default defineConfig({
	lastModifiedTime: "git",
	mdxOptions: {
		providerImportSource: "@/mdx-components",
	},
});
