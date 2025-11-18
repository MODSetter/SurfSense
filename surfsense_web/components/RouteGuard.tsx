"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useSiteConfig, SiteConfig } from "@/contexts/SiteConfigContext";

interface RouteGuardProps {
	children: React.ReactNode;
	routeKey: "pricing" | "docs" | "contact" | "terms" | "privacy" | "registration";
}

const routeConfigMap: Record<RouteGuardProps["routeKey"], keyof SiteConfig> = {
	pricing: "disable_pricing_route",
	docs: "disable_docs_route",
	contact: "disable_contact_route",
	terms: "disable_terms_route",
	privacy: "disable_privacy_route",
	registration: "disable_registration",
};

export function RouteGuard({ children, routeKey }: RouteGuardProps) {
	const { config, isLoading } = useSiteConfig();
	const router = useRouter();

	useEffect(() => {
		if (isLoading) return;

		const disableKey = routeConfigMap[routeKey];
		const isDisabled = config[disableKey];

		if (isDisabled) {
			router.replace("/404");
		}
	}, [config, isLoading, routeKey, router]);

	// Show loading state while checking configuration
	if (isLoading) {
		return (
			<div className="min-h-screen flex items-center justify-center bg-white dark:bg-black">
				<div className="text-neutral-600 dark:text-neutral-400">Loading...</div>
			</div>
		);
	}

	// Check if route is disabled
	const disableKey = routeConfigMap[routeKey];
	const isDisabled = config[disableKey];

	if (isDisabled) {
		return null;
	}

	return <>{children}</>;
}
