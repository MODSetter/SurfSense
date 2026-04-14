"use client";

import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Pricing } from "@/components/pricing";
import { isAuthenticated, redirectToLogin, authenticatedFetch } from "@/lib/auth-utils";
import { BACKEND_URL } from "@/lib/env-config";

const PLAN_IDS = {
	pro_monthly: "pro_monthly",
	pro_yearly: "pro_yearly",
};

function PricingBasic() {
	const [isOnline, setIsOnline] = useState(true);
	const [isYearly, setIsYearly] = useState(false);
	const [isLoading, setIsLoading] = useState(false);

	useEffect(() => {
		setIsOnline(navigator.onLine);
		const handleOnline = () => setIsOnline(true);
		const handleOffline = () => setIsOnline(false);
		window.addEventListener("online", handleOnline);
		window.addEventListener("offline", handleOffline);
		return () => {
			window.removeEventListener("online", handleOnline);
			window.removeEventListener("offline", handleOffline);
		};
	}, []);

	const handleUpgradePro = async () => {
		if (!isOnline || isLoading) return;

		if (!isAuthenticated()) {
			redirectToLogin();
			return;
		}

		setIsLoading(true);
		try {
			const planId = isYearly ? PLAN_IDS.pro_yearly : PLAN_IDS.pro_monthly;
			const response = await authenticatedFetch(
				`${BACKEND_URL}/api/v1/stripe/create-subscription-checkout`,
				{
					method: "POST",
					headers: {
						"Content-Type": "application/json",
					},
					body: JSON.stringify({ plan_id: planId }),
				}
			);

			if (!response.ok) {
				toast.error("Unable to start checkout. Please try again later.");
				return;
			}

			const data = await response.json();
			const checkoutUrl = data.checkout_url;
			if (typeof checkoutUrl === "string" && checkoutUrl.startsWith("https://")) {
				window.location.href = checkoutUrl;
			} else {
				toast.error("Invalid checkout response. Please try again.");
			}
		} catch (error) {
			toast.error("Something went wrong. Please check your connection and try again.");
		} finally {
			setIsLoading(false);
		}
	};

	// Pricing plans — static constant (loads offline)
	const demoPlans = [
		{
			name: "FREE",
			price: "0",
			yearlyPrice: "0",
			period: "month",
			billingText: "No credit card required",
			features: [
				"Self hostable",
				"500 pages ETL / month",
				"50 LLM messages / day",
				"Basic models (GPT-3.5 Turbo)",
				"Community support on Discord",
			],
			description: "Perfect for personal use and exploration",
			buttonText: "Get Started",
			href: "/login",
			isPopular: false,
		},
		{
			name: "PRO",
			price: "12",
			yearlyPrice: "9",
			period: "month",
			billingText: isYearly ? "billed annually ($108/yr)" : "billed monthly",
			features: [
				"Everything in Free",
				"5,000 pages ETL / month",
				"1,000 LLM messages / day",
				"Premium models (GPT-4, Claude, Gemini)",
				"Priority support on Discord",
			],
			description: "For power users and professionals",
			buttonText: isLoading ? "Redirecting…" : isOnline ? "Upgrade to Pro" : "Offline — unavailable",
			href: "#",
			isPopular: true,
			onAction: handleUpgradePro,
			disabled: !isOnline || isLoading,
		},
		{
			name: "ENTERPRISE",
			price: "Contact Us",
			yearlyPrice: "Contact Us",
			period: "",
			billingText: "",
			features: [
				"Everything in Pro",
				"Unlimited pages ETL",
				"Unlimited LLM messages",
				"All models including latest releases",
				"On-prem or VPC deployment",
				"SSO, OIDC & SAML",
				"Audit logs and compliance",
				"Dedicated support & SLA",
			],
			description: "Custom setup for large organisations",
			buttonText: "Contact Sales",
			href: "/contact",
			isPopular: false,
		},
	];

	return (
		<Pricing
			plans={demoPlans}
			title="SurfSense Pricing"
			description="Start free. Upgrade when you need more power."
			isYearly={isYearly}
			onToggleBilling={setIsYearly}
		/>
	);
}

export default PricingBasic;
