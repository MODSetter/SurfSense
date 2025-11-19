"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useSiteConfig } from "@/contexts/SiteConfigContext";

interface RouteGuardProps {
	children: React.ReactNode;
	routeKey: "pricing" | "docs" | "contact" | "terms" | "privacy" | "registration";
}

export function RouteGuard({ children, routeKey }: RouteGuardProps) {
	const { config, isLoading } = useSiteConfig();
	const router = useRouter();

	useEffect(() => {
		if (isLoading) return;

		// Special case: registration uses disable_registration instead of disable_registration_route
		const disableKey = routeKey === "registration"
			? "disable_registration"
			: (`disable_${routeKey}_route` as keyof typeof config);
		const isDisabled = config[disableKey as keyof typeof config];

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
	// Special case: registration uses disable_registration instead of disable_registration_route
	const disableKey = routeKey === "registration"
		? "disable_registration"
		: (`disable_${routeKey}_route` as keyof typeof config);
	const isDisabled = config[disableKey as keyof typeof config];

	if (isDisabled) {
		return null;
	}

	return <>{children}</>;
}
