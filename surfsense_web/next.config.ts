import path from "node:path";
import { createMDX } from "fumadocs-mdx/next";
import type { NextConfig } from "next";
import createNextIntlPlugin from "next-intl/plugin";

// Create the next-intl plugin
const withNextIntl = createNextIntlPlugin("./i18n/request.ts");

// TODO: Separate app routes (/login, /dashboard) from marketing routes
// (landing page, /contact, /pricing, /docs) so the desktop build only
// ships what desktop users actually need.
const nextConfig: NextConfig = {
	output: "standalone",
	outputFileTracingRoot: path.join(__dirname, ".."),
	reactStrictMode: false,
	typescript: {
		ignoreBuildErrors: true,
	},
	images: {
		remotePatterns: [
			{
				protocol: "https",
				hostname: "**",
			},
		],
	},
	experimental: {
		optimizePackageImports: [
			"lucide-react",
			"@tabler/icons-react",
			"date-fns",
			"@assistant-ui/react",
			"@assistant-ui/react-markdown",
			"motion",
		],
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

	// Proxy /api/v1/* to the FastAPI backend. Keeps the real backend host
	// out of the client bundle. BACKEND_PROXY_TARGET is server-only.
	async rewrites() {
		const target =
			process.env.BACKEND_PROXY_TARGET ||
			process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL ||
			"http://localhost:8000";
		return [
			{
				source: "/api/v1/:path*",
				destination: `${target.replace(/\/+$/, "")}/api/v1/:path*`,
			},
		];
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

// Wrap the config with MDX and next-intl plugins
const withMDX = createMDX({});

export default withNextIntl(withMDX(nextConfig));
