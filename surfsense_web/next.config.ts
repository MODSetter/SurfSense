import { createMDX } from "fumadocs-mdx/next";
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
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
				hostname: "images.unsplash.com",
			},
			{
				protocol: "https",
				hostname: "static.vecteezy.com",
			},
		],
	},
};

// Wrap the config with createMDX
const withMDX = createMDX({});

export default withMDX(nextConfig);
