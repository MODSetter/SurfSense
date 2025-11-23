import { createMDX } from "fumadocs-mdx/next";
import type { NextConfig } from "next";
import createNextIntlPlugin from "next-intl/plugin";

// Create the next-intl plugin
const withNextIntl = createNextIntlPlugin("./i18n/request.ts");

const nextConfig: NextConfig = {
	output: "standalone",
	// Disable StrictMode for BlockNote compatibility with React 19/Next 15
	reactStrictMode: false,
	typescript: {
		ignoreBuildErrors: true,
	},
	eslint: {
		ignoreDuringBuilds: true,
	},
	images: {
		remotePatterns: [
			{
				protocol: "https",
				hostname: "**",
			},
		],
	},
	// Mark BlockNote server packages as external
	serverExternalPackages: ["@blocknote/server-util"],

	// Configure webpack to handle blocknote packages
	webpack: (config, { isServer }) => {
		if (isServer) {
			// Don't bundle these packages on the server
			config.externals = [...(config.externals || []), "@blocknote/server-util"];
		}
		return config;
	},
};

// Wrap the config with MDX and next-intl plugins
const withMDX = createMDX({});

export default withNextIntl(withMDX(nextConfig));
