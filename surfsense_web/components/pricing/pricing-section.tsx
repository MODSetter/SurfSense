"use client";

import { Pricing } from "@/components/pricing";

const demoPlans = [
	{
		name: "FREE",
		price: "0",
		yearlyPrice: "0",
		period: "",
		billingText: "",
		features: [
			"Self Hostable",
			"Upload and chat with 300+ pages of content",
			"Includes access to ChatGPT text and audio models",
			"Realtime Collaborative Group Chats with teammates",
			"Community support on Discord",
		],
		description: "",
		buttonText: "Get Started",
		href: "/login",
		isPopular: false,
	},
	{
		name: "PRO",
		price: "0",
		yearlyPrice: "0",
		period: "",
		billingText: "Free during beta",
		features: [
			"Everything in Free",
			"Includes 6000+ pages of content",
			"Access to more models and providers",
			"Priority support on Discord",
		],
		description: "",
		buttonText: "Get Started",
		href: "/login",
		isPopular: true,
	},
	{
		name: "ENTERPRISE",
		price: "Contact Us",
		yearlyPrice: "Contact Us",
		period: "",
		billingText: "",
		features: [
			"Everything in Pro",
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
		<Pricing plans={demoPlans} title="SurfSense Pricing" description="Choose what works for you" />
	);
}

export default PricingBasic;
