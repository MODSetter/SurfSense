import type { Metadata } from "next";
import PricingBasic from "@/components/pricing/pricing-section";

export const metadata: Metadata = {
	title: "Pricing | SurfSense - Free AI Workspace, Automations & Agents",
	description:
		"Explore SurfSense plans and pricing. Start free with 500 pages & $5 in premium credits. Run AI automations and agents, use ChatGPT, Claude AI, and premium AI models, and pay as you go at provider cost.",
	alternates: {
		canonical: "https://www.surfsense.com/pricing",
	},
};

const page = () => {
	return (
		<div>
			<PricingBasic />
		</div>
	);
};

export default page;
