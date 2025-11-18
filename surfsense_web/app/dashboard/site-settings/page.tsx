"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { useSiteConfig } from "@/contexts/SiteConfigContext";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Loader2 } from "lucide-react";
import { AUTH_TOKEN_KEY } from "@/lib/constants";

interface SiteConfigForm {
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
	custom_copyright: string;
}

export default function SiteSettingsPage() {
	const { config, isLoading, refetch } = useSiteConfig();
	const router = useRouter();
	const [formData, setFormData] = useState<SiteConfigForm>({
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
	});
	const [isSaving, setIsSaving] = useState(false);
	const [isCheckingAuth, setIsCheckingAuth] = useState(true);
	const [isSuperuser, setIsSuperuser] = useState(false);

	// Check if user is a superuser
	useEffect(() => {
		const checkSuperuser = async () => {
			try {
				const backendUrl = process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL || "http://localhost:8000";
				const token = localStorage.getItem(AUTH_TOKEN_KEY);

				if (!token) {
					router.push("/login");
					return;
				}

				const response = await fetch(`${backendUrl}/verify-token`, {
					headers: {
						Authorization: `Bearer ${token}`,
					},
				});

				if (!response.ok) {
					router.push("/login");
					return;
				}

				const data = await response.json();

				if (!data.user?.is_superuser) {
					toast.error("Access Denied", {
						description: "You must be a superuser to access site settings.",
						duration: 5000,
					});
					router.push("/dashboard");
					return;
				}

				setIsSuperuser(true);
			} catch (error) {
				console.error("Error verifying superuser status:", error);
				router.push("/login");
			} finally {
				setIsCheckingAuth(false);
			}
		};

		checkSuperuser();
	}, [router]);

	// Load config into form when available
	useEffect(() => {
		if (!isLoading && config) {
			setFormData({
				show_pricing_link: config.show_pricing_link,
				show_docs_link: config.show_docs_link,
				show_github_link: config.show_github_link,
				show_sign_in: config.show_sign_in,
				show_get_started_button: config.show_get_started_button,
				show_talk_to_us_button: config.show_talk_to_us_button,
				show_pages_section: config.show_pages_section,
				show_legal_section: config.show_legal_section,
				show_register_section: config.show_register_section,
				disable_pricing_route: config.disable_pricing_route,
				disable_docs_route: config.disable_docs_route,
				disable_contact_route: config.disable_contact_route,
				disable_terms_route: config.disable_terms_route,
				disable_privacy_route: config.disable_privacy_route,
				disable_registration: config.disable_registration,
				custom_copyright: config.custom_copyright || "SurfSense 2025",
			});
		}
	}, [config, isLoading]);

	const handleToggle = (field: keyof SiteConfigForm) => {
		setFormData((prev) => ({
			...prev,
			[field]: !prev[field],
		}));
	};

	const handleTextChange = (field: keyof SiteConfigForm, value: string) => {
		setFormData((prev) => ({
			...prev,
			[field]: value,
		}));
	};

	const handleSave = async () => {
		setIsSaving(true);
		try {
			const backendUrl = process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL || "http://localhost:8000";
			const token = localStorage.getItem(AUTH_TOKEN_KEY);

			const response = await fetch(`${backendUrl}/api/v1/site-config`, {
				method: "PUT",
				headers: {
					"Content-Type": "application/json",
					Authorization: `Bearer ${token}`,
				},
				body: JSON.stringify(formData),
			});

			if (!response.ok) {
				const error = await response.json();
				throw new Error(error.detail || "Failed to update site configuration");
			}

			toast.success("Site configuration updated successfully!");

			// Refetch the config to update the global context
			await refetch();
		} catch (error) {
			console.error("Error updating site configuration:", error);
			toast.error(error instanceof Error ? error.message : "Failed to update site configuration");
		} finally {
			setIsSaving(false);
		}
	};

	// Show loading screen while checking authentication or loading config
	if (isCheckingAuth || isLoading) {
		return (
			<div className="flex flex-col items-center justify-center min-h-screen space-y-4">
				<Card className="w-[350px] bg-background/60 backdrop-blur-sm">
					<CardHeader className="pb-2">
						<CardTitle className="text-xl font-medium">
							{isCheckingAuth ? "Verifying Access" : "Loading Configuration"}
						</CardTitle>
						<CardDescription>
							{isCheckingAuth ? "Checking superuser permissions..." : "Loading site settings..."}
						</CardDescription>
					</CardHeader>
					<CardContent className="flex justify-center py-6">
						<Loader2 className="h-12 w-12 text-primary animate-spin" />
					</CardContent>
				</Card>
			</div>
		);
	}

	// If not checking auth anymore and user is not superuser, they've been redirected
	if (!isSuperuser) {
		return null;
	}

	return (
		<div className="min-h-screen bg-gradient-to-b from-gray-50 to-gray-100 dark:from-black dark:to-gray-900 py-12 px-4 sm:px-6 lg:px-8">
			<div className="max-w-4xl mx-auto">
				<div className="bg-white dark:bg-neutral-900 shadow-xl rounded-lg overflow-hidden border border-neutral-200 dark:border-neutral-800">
					<div className="px-6 py-8 sm:p-10">
						<div className="mb-8">
							<h1 className="text-3xl font-bold text-gray-900 dark:text-white mb-2">
								Site Appearance Settings
							</h1>
							<p className="text-gray-600 dark:text-gray-400">
								Configure the visibility of site elements and customize your homepage appearance.
							</p>
						</div>

						<div className="space-y-8">
							{/* Header/Navbar Section */}
							<section>
								<h2 className="text-xl font-semibold text-gray-900 dark:text-white mb-4">
									Header & Navigation
								</h2>
								<div className="space-y-3">
									<ToggleSwitch
										label="Show Pricing Link"
										checked={formData.show_pricing_link}
										onChange={() => handleToggle("show_pricing_link")}
									/>
									<ToggleSwitch
										label="Show Docs Link"
										checked={formData.show_docs_link}
										onChange={() => handleToggle("show_docs_link")}
									/>
									<ToggleSwitch
										label="Show GitHub Link"
										checked={formData.show_github_link}
										onChange={() => handleToggle("show_github_link")}
									/>
									<ToggleSwitch
										label="Show Sign In Button"
										checked={formData.show_sign_in}
										onChange={() => handleToggle("show_sign_in")}
									/>
								</div>
							</section>

							{/* Homepage Section */}
							<section>
								<h2 className="text-xl font-semibold text-gray-900 dark:text-white mb-4">
									Homepage Buttons
								</h2>
								<div className="space-y-3">
									<ToggleSwitch
										label="Show 'Get Started' Button"
										checked={formData.show_get_started_button}
										onChange={() => handleToggle("show_get_started_button")}
									/>
									<ToggleSwitch
										label="Show 'Talk to Us' Button"
										checked={formData.show_talk_to_us_button}
										onChange={() => handleToggle("show_talk_to_us_button")}
									/>
								</div>
							</section>

							{/* Footer Section */}
							<section>
								<h2 className="text-xl font-semibold text-gray-900 dark:text-white mb-4">
									Footer Sections
								</h2>
								<div className="space-y-3">
									<ToggleSwitch
										label="Show Pages Section"
										description="Pricing, Docs, Contact links"
										checked={formData.show_pages_section}
										onChange={() => handleToggle("show_pages_section")}
									/>
									<ToggleSwitch
										label="Show Legal Section"
										description="Terms of Service, Privacy Policy links"
										checked={formData.show_legal_section}
										onChange={() => handleToggle("show_legal_section")}
									/>
									<ToggleSwitch
										label="Show Register Section"
										description="Create Account, Sign In links"
										checked={formData.show_register_section}
										onChange={() => handleToggle("show_register_section")}
									/>
								</div>
							</section>

							{/* Route Disabling Section */}
							<section>
								<h2 className="text-xl font-semibold text-gray-900 dark:text-white mb-4">
									Route Disabling
								</h2>
								<p className="text-sm text-gray-600 dark:text-gray-400 mb-4">
									Disabled routes will show a 404 page when accessed.
								</p>
								<div className="space-y-3">
									<ToggleSwitch
										label="Disable Pricing Route"
										checked={formData.disable_pricing_route}
										onChange={() => handleToggle("disable_pricing_route")}
									/>
									<ToggleSwitch
										label="Disable Docs Route"
										checked={formData.disable_docs_route}
										onChange={() => handleToggle("disable_docs_route")}
									/>
									<ToggleSwitch
										label="Disable Contact Route"
										checked={formData.disable_contact_route}
										onChange={() => handleToggle("disable_contact_route")}
									/>
									<ToggleSwitch
										label="Disable Terms of Service Route"
										checked={formData.disable_terms_route}
										onChange={() => handleToggle("disable_terms_route")}
									/>
									<ToggleSwitch
										label="Disable Privacy Policy Route"
										checked={formData.disable_privacy_route}
										onChange={() => handleToggle("disable_privacy_route")}
									/>
								</div>
							</section>

							{/* Registration Control Section */}
							<section>
								<h2 className="text-xl font-semibold text-gray-900 dark:text-white mb-4">
									Registration Control
								</h2>
								<p className="text-sm text-gray-600 dark:text-gray-400 mb-4">
									Control user registration availability. When disabled, the Sign Up link will be hidden
									and the registration page will show a 404 error. The backend will also block registration
									requests with a 403 error.
								</p>
								<div className="space-y-3">
									<ToggleSwitch
										label="Disable Registration"
										description="Prevent new users from creating accounts"
										checked={formData.disable_registration}
										onChange={() => handleToggle("disable_registration")}
									/>
								</div>
							</section>

							{/* Custom Text Section */}
							<section>
								<h2 className="text-xl font-semibold text-gray-900 dark:text-white mb-4">
									Custom Text
								</h2>
								<div>
									<label
										htmlFor="custom_copyright"
										className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2"
									>
										Copyright Text
									</label>
									<input
										type="text"
										id="custom_copyright"
										value={formData.custom_copyright}
										onChange={(e) => handleTextChange("custom_copyright", e.target.value)}
										placeholder="SurfSense 2025"
										className="w-full px-4 py-2 border border-gray-300 dark:border-gray-700 rounded-lg bg-white dark:bg-neutral-800 text-gray-900 dark:text-white focus:ring-2 focus:ring-orange-500 focus:border-transparent"
									/>
									<p className="mt-2 text-sm text-gray-500 dark:text-gray-400">
										This text will appear in the footer copyright notice.
									</p>
								</div>
							</section>
						</div>

						{/* Save Button */}
						<div className="mt-8 flex justify-end">
							<button
								onClick={handleSave}
								disabled={isSaving}
								className="px-6 py-3 bg-gradient-to-r from-orange-500 to-yellow-500 text-white font-semibold rounded-lg shadow-lg hover:shadow-xl transition-all duration-300 hover:scale-105 disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:scale-100"
							>
								{isSaving ? "Saving..." : "Save Configuration"}
							</button>
						</div>
					</div>
				</div>
			</div>
		</div>
	);
}

// Toggle Switch Component
interface ToggleSwitchProps {
	label: string;
	description?: string;
	checked: boolean;
	onChange: () => void;
}

function ToggleSwitch({ label, description, checked, onChange }: ToggleSwitchProps) {
	return (
		<div className="flex items-center justify-between py-3 px-4 bg-gray-50 dark:bg-neutral-800 rounded-lg">
			<div className="flex-1">
				<div className="text-sm font-medium text-gray-900 dark:text-white">{label}</div>
				{description && (
					<div className="text-xs text-gray-500 dark:text-gray-400 mt-1">{description}</div>
				)}
			</div>
			<button
				type="button"
				onClick={onChange}
				className={`relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-orange-500 focus:ring-offset-2 ${
					checked ? "bg-orange-500" : "bg-gray-300 dark:bg-gray-600"
				}`}
				role="switch"
				aria-checked={checked}
			>
				<span
					aria-hidden="true"
					className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out ${
						checked ? "translate-x-5" : "translate-x-0"
					}`}
				/>
			</button>
		</div>
	);
}
