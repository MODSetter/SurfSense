import path from "node:path";
import { createMDX } from "fumadocs-mdx/next";
import type { NextConfig } from "next";
import { docsRedirects } from "./features/docs/docs-redirects";
import { installScriptRedirects } from "./features/downloads/install-script-redirects";

// The per-scraper marketing pages gave way to each plugin's page under /plugins.
const LISTED_SCRAPERS = [
	"google-search",
	"web-crawl",
	"reddit",
	"youtube",
	"instagram",
	"tiktok",
	"google-maps",
	"amazon",
	"walmart",
	"indeed",
];

const nextConfig: NextConfig = {
	async redirects() {
		return [
			// /mcp-connector was split into the two MCP directions; the external
			// (client) side kept the original content.
			{ source: "/mcp-connector", destination: "/external-mcp-connectors", permanent: true },
			// The connectors index was renamed to /plugins, which is what the
			// product calls them everywhere else.
			{ source: "/connectors", destination: "/plugins", permanent: true },
			...LISTED_SCRAPERS.map((id) => ({
				source: `/${id}`,
				destination: `/plugins/${id}`,
				permanent: true,
			})),
			...docsRedirects,
			...installScriptRedirects,
		];
	},
	outputFileTracingRoot: path.join(__dirname, ".."),
	reactStrictMode: false,
	typescript: {
		ignoreBuildErrors: true,
	},
	images: {
		// AVIF first: noticeably smaller than WebP at the same quality. 85 is for
		// the dithered homepage scene, where 75 starts to smudge the dots.
		formats: ["image/avif", "image/webp"],
		qualities: [75, 85],
		remotePatterns: [
			{
				protocol: "https",
				hostname: "**",
			},
		],
		// Allow remote SVGs (e.g. README badges from img.shields.io, trendshift.io,
		// etc.) which are otherwise blocked by next/image. The CSP below sandboxes
		// the SVG and forbids any embedded scripts, which is the mitigation
		// recommended by Vercel's NEXTJS_SAFE_SVG_IMAGES conformance rule.
		dangerouslyAllowSVG: true,
		contentDispositionType: "attachment",
		contentSecurityPolicy: "default-src 'self'; script-src 'none'; sandbox;",
	},
	experimental: {
		optimizePackageImports: ["@hugeicons/core-free-icons", "date-fns", "motion"],
	},
	// Turbopack config (used during `next dev --turbopack`)
	turbopack: {
		rules: {
			"*.svg": {
				loaders: ["@svgr/webpack"],
				as: "*.js",
			},
		},
	},

	// Configure webpack (SVGR)
	webpack: (config) => {
		// SVGR: import *.svg as React components
		const fileLoaderRule = config.module.rules.find(
			(rule: { test?: { test?: (s: string) => boolean } }) => rule.test?.test?.(".svg")
		);
		config.module.rules.push(
			// Re-apply the existing file loader for *.svg?url imports
			{
				...fileLoaderRule,
				test: /\.svg$/i,
				resourceQuery: /url/, // e.g. import icon from './icon.svg?url'
			},
			// Convert all other *.svg imports to React components
			{
				test: /\.svg$/i,
				issuer: fileLoaderRule.issuer,
				resourceQuery: { not: [...fileLoaderRule.resourceQuery.not, /url/] },
				use: ["@svgr/webpack"],
			}
		);
		fileLoaderRule.exclude = /\.svg$/i;

		return config;
	},
};

const withMDX = createMDX({});

export default withMDX(nextConfig);
