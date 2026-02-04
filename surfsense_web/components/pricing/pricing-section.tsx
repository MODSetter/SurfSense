"use client";

import { Pricing } from "@/components/pricing";

const demoPlans = [
	{
		name: "FREE",
		price: "0",
		yearlyPrice: "0",
		period: "",
		billingText: "Includes 30 day PRO trial",
		features: [
			"Open source on GitHub",
			"Upload and chat with up to 1,000 pages of content",
			"Connects with 8 popular sources, like Drive and Notion.",
			"Includes limited access to ChatGPT, Claude, and DeepSeek models",
			"Supports 100+ more LLMs, including Gemini, Llama and many more.",
			"50+ File extensions supported.",
			"Generate podcasts in seconds.",
			"Cross-Browser Extension for dynamic webpages including authenticated content",
			"Community support on Discord",
		],
		description: "Powerful features with some limitations",
		buttonText: "Get Started",
		href: "/",
		isPopular: false,
	},
	{
		name: "PRO",
		price: "10",
		yearlyPrice: "10",
		period: "user / month",
		billingText: "billed annually",
		features: [
			"Everything in Free",
			"Upload and chat with up to 20,000 pages of content",
			"Connects with 15+ external sources, like Slack and Airtable.",
			"Includes extended access to ChatGPT, Claude, and DeepSeek models",
			"Collaboration and commenting features",
			"Centralized billing",
			"Shared BYOK (Bring Your Own Key)",
			"Team and role management",
			"Priority support",
		],
		description: "The AIknowledge base for individuals and teams",
		buttonText: "Upgrade",
		href: "/contact",
		isPopular: true,
	},
	{
		name: "ENTERPRISE",
		price: "1000",
		yearlyPrice: "1000",
		period: "month",
		billingText: "billed annually",
		features: [
			"Everything in Pro",
			"Connect and chat with virtually unlimited pages of content",
			"Limit models and/or providers",
			"On-prem or VPC deployment",
			"Audit logs and compliance",
			"SSO, OIDC & SAML",
			"Role-based access control (RBAC)",
			"White-glove setup and deployment",
			"Monthly managed updates and maintenance",
			"SLA commitments",
			"Dedicated support",
		],
		description: "Customized setup for large organizations",
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
