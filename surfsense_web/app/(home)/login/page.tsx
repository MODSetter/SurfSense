"use client";

import { Loader2 } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useSearchParams } from "next/navigation";
import { useTranslations } from "next-intl";
import { Suspense, useEffect, useState } from "react";
import { toast } from "sonner";
import { Logo } from "@/components/Logo";
import { getAuthErrorDetails, shouldRetry } from "@/lib/auth-errors";
import { AmbientBackground } from "./AmbientBackground";
import { GoogleLoginButton } from "./GoogleLoginButton";
import { LocalLoginForm } from "./LocalLoginForm";

function LoginContent() {
	const t = useTranslations("auth");
	const tCommon = useTranslations("common");
	const [authType, setAuthType] = useState<string | null>(null);
	const [isLoading, setIsLoading] = useState(true);
	const [urlError, setUrlError] = useState<{ title: string; message: string } | null>(null);
	const searchParams = useSearchParams();

	useEffect(() => {
		// Check for various URL parameters that might indicate success or error states
		const registered = searchParams.get("registered");
		const error = searchParams.get("error");
		const message = searchParams.get("message");
		const logout = searchParams.get("logout");

		// Show registration success message
		if (registered === "true") {
			toast.success(t("register_success"), {
				description: t("login_subtitle"),
				duration: 5000,
			});
		}

		// Show logout confirmation
		if (logout === "true") {
			toast.success(tCommon("success"), {
				description: "You have been securely logged out",
				duration: 3000,
			});
		}

		// Show error messages from OAuth or other flows using auth-errors utility
		if (error) {
			// Use the auth-errors utility to get proper error details
			const errorDetails = getAuthErrorDetails(error);

			// If we have a custom message from URL params, use it as description
			const errorDescription = message ? decodeURIComponent(message) : errorDetails.description;

			// Set persistent error display
			setUrlError({
				title: errorDetails.title,
				message: errorDescription,
			});

			// Show toast with conditional retry action
			const toastOptions: any = {
				description: errorDescription,
				duration: 6000,
			};

			// Add retry action if the error is retryable
			if (shouldRetry(error)) {
				toastOptions.action = {
					label: "Retry",
					onClick: () => window.location.reload(),
				};
			}

			toast.error(errorDetails.title, toastOptions);
		}

		// Show general messages
		if (message && !error && !registered && !logout) {
			toast.info("Notice", {
				description: decodeURIComponent(message),
				duration: 4000,
			});
		}

		// Get the auth type from environment variables
		setAuthType(process.env.NEXT_PUBLIC_FASTAPI_BACKEND_AUTH_TYPE || "GOOGLE");
		setIsLoading(false);
	}, [searchParams]);

	// Show loading state while determining auth type
	if (isLoading) {
		return (
			<div className="relative w-full overflow-hidden">
				<AmbientBackground />
				<div className="mx-auto flex h-screen max-w-lg flex-col items-center justify-center">
					<Logo className="rounded-md" />
					<div className="mt-8 flex items-center space-x-2">
						<Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
						<span className="text-muted-foreground">{tCommon("loading")}</span>
					</div>
				</div>
			</div>
		);
	}

	if (authType === "GOOGLE") {
		return <GoogleLoginButton />;
	}

	return (
		<div className="relative w-full overflow-hidden">
			<AmbientBackground />
			<div className="mx-auto flex h-screen max-w-lg flex-col items-center justify-center">
				<Logo className="rounded-md" />
				<h1 className="my-8 text-xl font-bold text-neutral-800 dark:text-neutral-100 md:text-4xl">
					{t("sign_in")}
				</h1>

				{/* URL Error Display */}
				<AnimatePresence>
					{urlError && (
						<motion.div
							initial={{ opacity: 0, y: -10, scale: 0.95 }}
							animate={{ opacity: 1, y: 0, scale: 1 }}
							exit={{ opacity: 0, y: -10, scale: 0.95 }}
							transition={{ duration: 0.3 }}
							className="mb-6 w-full max-w-md rounded-lg border border-red-200 bg-red-50 p-4 text-red-900 shadow-sm dark:border-red-900/30 dark:bg-red-900/20 dark:text-red-200"
						>
							<div className="flex items-start gap-3">
								<svg
									xmlns="http://www.w3.org/2000/svg"
									width="18"
									height="18"
									viewBox="0 0 24 24"
									fill="none"
									stroke="currentColor"
									strokeWidth="2"
									strokeLinecap="round"
									strokeLinejoin="round"
									className="flex-shrink-0 mt-0.5 text-red-500 dark:text-red-400"
								>
									<title>Error Icon</title>
									<circle cx="12" cy="12" r="10" />
									<line x1="15" y1="9" x2="9" y2="15" />
									<line x1="9" y1="9" x2="15" y2="15" />
								</svg>
								<div className="flex-1 min-w-0">
									<p className="text-sm font-semibold mb-1">{urlError.title}</p>
									<p className="text-sm text-red-700 dark:text-red-300">{urlError.message}</p>
								</div>
								<button
									type="button"
									onClick={() => setUrlError(null)}
									className="flex-shrink-0 text-red-500 hover:text-red-700 dark:text-red-400 dark:hover:text-red-200 transition-colors"
									aria-label="Dismiss error"
								>
									<svg
										xmlns="http://www.w3.org/2000/svg"
										width="16"
										height="16"
										viewBox="0 0 24 24"
										fill="none"
										stroke="currentColor"
										strokeWidth="2"
										strokeLinecap="round"
										strokeLinejoin="round"
									>
										<title>Close</title>
										<line x1="18" y1="6" x2="6" y2="18" />
										<line x1="6" y1="6" x2="18" y2="18" />
									</svg>
								</button>
							</div>
						</motion.div>
					)}
				</AnimatePresence>

				<LocalLoginForm />
			</div>
		</div>
	);
}

// Loading fallback for Suspense
const LoadingFallback = () => (
	<div className="relative w-full overflow-hidden">
		<AmbientBackground />
		<div className="mx-auto flex h-screen max-w-lg flex-col items-center justify-center">
			<Logo className="rounded-md" />
			<div className="mt-8 flex items-center space-x-2">
				<Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
				<span className="text-muted-foreground">Loading...</span>
			</div>
		</div>
	</div>
);

export default function LoginPage() {
	return (
		<Suspense fallback={<LoadingFallback />}>
			<LoginContent />
		</Suspense>
	);
}
