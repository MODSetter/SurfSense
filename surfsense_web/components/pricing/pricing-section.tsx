"use client";

import { Pricing } from "@/components/pricing";

const demoPlans = [
	{
		name: "FREE",
		price: "0",
		yearlyPrice: "0",
		period: "",
		billingText: "1,000 pages included",
		features: [
			"Self Hostable",
			"500 pages included to start",
			"Earn up to 3,000+ bonus pages for free",
			"Includes access to OpenAI text, audio and image models",
			"Realtime Collaborative Group Chats with teammates",
			"Community support on Discord",
		],
		description: "",
		buttonText: "Get Started",
		href: "/login",
		isPopular: false,
	},
	{
		name: "PAY AS YOU GO",
		price: "1",
		yearlyPrice: "1",
		period: "1,000 pages",
		billingText: "No subscription, buy only when you need more",
		features: [
			"Everything in Free",
			"Buy 1,000-page packs at $1 each",
			"Priority support on Discord",
		],
		description: "",
		buttonText: "Get Started",
		href: "/login",
		isPopular: false,
	},
	{
		name: "ENTERPRISE",
		price: "Contact Us",
		yearlyPrice: "Contact Us",
		period: "",
		billingText: "",
		features: [
			"Everything in Pay As You Go",
			"On-prem or VPC deployment",
			"Audit logs and compliance",
			"SSO, OIDC & SAML",
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
		<Pricing
			plans={demoPlans}
			title="SurfSense Pricing"
			description="Start free with 1,000 pages. Earn up to 3,000+ more or buy as you go."
		/>
	);
}

export default PricingBasic;
