"use client";

import { Pricing } from "@/components/pricing";

const demoPlans = [
	{
		name: "STARTER",
		price: "50",
		yearlyPrice: "40",
		period: "per month",
		features: [
			"Up to 10 projects",
			"Basic analytics",
			"48-hour support response time",
			"Limited API access",
			"Community support",
		],
		description: "Perfect for individuals and small projects",
		buttonText: "Start Free Trial",
		href: "/sign-up",
		isPopular: false,
	},
	{
		name: "PROFESSIONAL",
		price: "99",
		yearlyPrice: "79",
		period: "per month",
		features: [
			"Unlimited projects",
			"Advanced analytics",
			"24-hour support response time",
			"Full API access",
			"Priority support",
			"Team collaboration",
			"Custom integrations",
		],
		description: "Ideal for growing teams and businesses",
		buttonText: "Get Started",
		href: "/sign-up",
		isPopular: true,
	},
	{
		name: "ENTERPRISE",
		price: "299",
		yearlyPrice: "239",
		period: "per month",
		features: [
			"Everything in Professional",
			"Custom solutions",
			"Dedicated account manager",
			"1-hour support response time",
			"SSO Authentication",
			"Advanced security",
			"Custom contracts",
			"SLA agreement",
		],
		description: "For large organizations with specific needs",
		buttonText: "Contact Sales",
		href: "/contact",
		isPopular: false,
	},
];

function PricingBasic() {
	return (
		<Pricing
			plans={demoPlans}
			title="Simple, Transparent Pricing"
			description="Choose the plan that works for you"
		/>
	);
}

export default PricingBasic;
