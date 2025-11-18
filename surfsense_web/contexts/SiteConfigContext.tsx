"use client";

import React, { createContext, useContext, useEffect, useState } from "react";

export interface SiteConfig {
	// Header/Navbar toggles
	show_pricing_link: boolean;
	show_docs_link: boolean;
	show_github_link: boolean;
	show_sign_in: boolean;

	// Homepage toggles
	show_get_started_button: boolean;
	show_talk_to_us_button: boolean;

	// Footer toggles
	show_pages_section: boolean;
	show_legal_section: boolean;
	show_register_section: boolean;

	// Route disabling
	disable_pricing_route: boolean;
	disable_docs_route: boolean;
	disable_contact_route: boolean;
	disable_terms_route: boolean;
	disable_privacy_route: boolean;

	// Registration control
	disable_registration: boolean;

	// Custom text
	custom_copyright: string | null;
}

const defaultConfig: SiteConfig = {
	show_pricing_link: false,
	show_docs_link: false,
	show_github_link: false,
	show_sign_in: true,
	show_get_started_button: false,
	show_talk_to_us_button: false,
	show_pages_section: false,
	show_legal_section: false,
	show_register_section: false,
	disable_pricing_route: true,
	disable_docs_route: true,
	disable_contact_route: true,
	disable_terms_route: true,
	disable_privacy_route: true,
	disable_registration: false,
	custom_copyright: "SurfSense 2025",
};

interface SiteConfigContextType {
	config: SiteConfig;
	isLoading: boolean;
	error: string | null;
	refetch: () => Promise<void>;
}

const SiteConfigContext = createContext<SiteConfigContextType>({
	config: defaultConfig,
	isLoading: true,
	error: null,
	refetch: async () => {},
});

export function SiteConfigProvider({ children }: { children: React.ReactNode }) {
	const [config, setConfig] = useState<SiteConfig>(defaultConfig);
	const [isLoading, setIsLoading] = useState(true);
	const [error, setError] = useState<string | null>(null);

	const fetchConfig = async () => {
		try {
			setIsLoading(true);
			setError(null);

			const backendUrl =
				process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL || "http://localhost:8000";
			const response = await fetch(`${backendUrl}/api/v1/site-config/public`);

			if (!response.ok) {
				throw new Error(`Failed to fetch site configuration: ${response.statusText}`);
			}

			const data = await response.json();
			setConfig(data);
		} catch (err) {
			const errorMessage = err instanceof Error ? err.message : "Unknown error occurred";
			setError(errorMessage);
			console.error("Error fetching site configuration:", err);
			// Keep default config on error
		} finally {
			setIsLoading(false);
		}
	};

	useEffect(() => {
		fetchConfig();
	}, []);

	return (
		<SiteConfigContext.Provider value={{ config, isLoading, error, refetch: fetchConfig }}>
			{children}
		</SiteConfigContext.Provider>
	);
}

export function useSiteConfig() {
	const context = useContext(SiteConfigContext);
	if (!context) {
		throw new Error("useSiteConfig must be used within a SiteConfigProvider");
	}
	return context;
}
