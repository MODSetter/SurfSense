"use client";

import { Pricing } from "@/components/pricing";

const demoPlans = [
	{
		name: "COMMUNITY",
		price: "0",
		yearlyPrice: "0",
		period: "forever",
		features: [
			"Community support",
			"Supports 100+ LLMs",
			"Supports OpenAI spec and LiteLLM",
			"Supports local vLLM or Ollama setups",
			"6000+ embedding models",
			"50+ File extensions supported.",
			"Podcasts support with local TTS providers.",
			"Connects with 15+ external sources, like Drive and Notion.",
			"Cross-Browser Extension for dynamic webpages including authenticated content",
			"Role-based access control (RBAC)",
			"Collaboration and team features",
		],
		description: "Open source version with powerful features",
		buttonText: "Dive In",
		href: "/docs",
		isPopular: false,
	},
	{
		name: "CLOUD",
		price: "0",
		yearlyPrice: "0",
		period: "in beta",
		features: [
			"Everything in Community",
			"Email support",
			"Get started in seconds",
			"Instant access to new features",
			"Easy access from anywhere",
			"Remote team management and collaboration",
		],
		description: "Instant access for individuals and teams",
		buttonText: "Get Started",
		href: "/",
		isPopular: true,
	},
	{
		name: "ENTERPRISE",
		price: "Contact Us",
		yearlyPrice: "Contact Us",
		period: "",
		features: [
			"Everything in Community",
			"Priority support",
			"White-glove setup and deployment",
			"Monthly managed updates and maintenance",
			"On-prem or VPC deployment",
			"Audit logs and compliance",
			"SSO, OIDC & SAML",
			"SLA guarantee",
			"Uptime guarantee on VPC",
		],
		description: "Professional, customized setup for large organizations",
		buttonText: "Contact Sales",
		href: "/contact",
		isPopular: false,
	},
];

function PricingBasic() {
	return (
		<Pricing plans={demoPlans} title="SurfSense Pricing" description="Choose what works for you" />
	);
}

export default PricingBasic;
