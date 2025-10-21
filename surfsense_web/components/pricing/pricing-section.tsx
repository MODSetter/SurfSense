"use client";

import { Pricing } from "@/components/pricing";

const demoPlans = [
	{
		name: "COMMUNITY",
		price: "0",
		yearlyPrice: "0",
		period: "forever",
		features: [
			"Supports 100+ LLMs",
			"Supports local Ollama or vLLM setups",
			"6000+ Embedding Models",
			"50+ File extensions supported.",
			"Podcasts support with local TTS providers.",
			"Connects with 15+ external sources.",
			"Cross-Browser Extension for dynamic webpages including authenticated content",
			"Upcoming: Mergeable MindMaps",
			"Upcoming: Note Management",
		],
		description: "Open source version with powerful features",
		buttonText: "Get Started",
		href: "/docs",
		isPopular: true,
	},
	{
		name: "ENTERPRISE",
		price: "Contact Us",
		yearlyPrice: "Contact Us",
		period: "",
		features: [
			"Everything in Community",
			"Priority Support",
			"Role-based access permissions",
			"Collaboration and multiplayer features",
			"Advanced security features",
		],
		description: "For large organizations with specific needs",
		buttonText: "Contact Sales",
		href: "/contact",
		isPopular: false,
	},
];

function PricingBasic() {
	return (
		<Pricing plans={demoPlans} title="SurfSense Pricing" description="Choose that works for you" />
	);
}

export default PricingBasic;
