"use client";
import { useTranslations } from "next-intl";
import { useState } from "react";
import { Logo } from "@/components/Logo";
import { Button } from "@/components/ui/button";
import { buildBackendUrl } from "@/lib/env-config";
import { trackLoginAttempt } from "@/lib/posthog/events";
import { AmbientBackground } from "./AmbientBackground";

function GoogleGLogo({ className }: { className?: string }) {
	return (
		<svg
			className={className}
			xmlns="http://www.w3.org/2000/svg"
			viewBox="0 0 48 48"
			aria-hidden="true"
		>
			<path
				fill="#EA4335"
				d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z"
			/>
			<path
				fill="#4285F4"
				d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z"
			/>
			<path
				fill="#FBBC05"
				d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z"
			/>
			<path
				fill="#34A853"
				d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z"
			/>
		</svg>
	);
}

export function GoogleLoginButton() {
	const t = useTranslations("auth");
	const [isRedirecting, setIsRedirecting] = useState(false);

	const handleGoogleLogin = () => {
		if (isRedirecting) return;
		setIsRedirecting(true);

		// Track Google login attempt
		trackLoginAttempt("google");

		// IMPORTANT: Use the redirect-based authorize endpoint for cross-origin OAuth
		// This fixes CSRF cookie issues in Firefox/Safari where cookies set via
		// cross-origin fetch requests may not be sent on subsequent redirects.
		// The authorize-redirect endpoint does a server-side redirect to Google
		// and sets the CSRF cookie properly for same-site context.
		window.location.href = buildBackendUrl("/auth/google/authorize-redirect");
	};
	return (
		<div className="relative w-full overflow-hidden">
			<AmbientBackground />
			<div className="mx-auto flex h-screen max-w-lg flex-col items-center justify-center px-6 md:px-0">
				<Logo className="h-16 w-16 md:h-32 md:w-32 rounded-full my-4 md:my-8 transition-all" />
				{/* <h1 className="my-8 text-xl font-bold text-neutral-800 dark:text-neutral-100 md:text-4xl">
					Login
				</h1> */}
				{/* 
				<motion.div
					initial={{ opacity: 0, y: -5 }}
					animate={{ opacity: 1, y: 0 }}
					transition={{ duration: 0.3 }}
					className="mb-4 w-full overflow-hidden rounded-lg border border-yellow-200 bg-yellow-50 text-yellow-900 shadow-sm dark:border-yellow-900/30 dark:bg-yellow-900/20 dark:text-yellow-200"
				>
					<motion.div
						className="flex items-center gap-2 p-4"
						initial={{ x: -5 }}
						animate={{ x: 0 }}
						transition={{ delay: 0.1, duration: 0.2 }}
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
							className="flex-shrink-0"
						>
							<title>Google Logo</title>
							<path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
							<line x1="12" y1="9" x2="12" y2="13" />
							<line x1="12" y1="17" x2="12.01" y2="17" />
						</svg>
						<div className="ml-1">
							<p className="text-sm font-medium">
								{t("cloud_dev_notice")}{" "}
								<a
									href="/docs"
									className="text-blue-600 underline dark:text-blue-400 hover:text-blue-800 dark:hover:text-blue-300"
								>
									{t("docs")}
								</a>{" "}
								{t("cloud_dev_self_hosted")}
							</p>
						</div>
					</motion.div>
				</motion.div> */}

				<Button
					variant="outline"
					className="w-full max-w-md gap-2 rounded-lg border-white bg-white px-6 py-5 font-medium text-[#1f1f1f] shadow-sm hover:bg-zinc-100 hover:text-[#1f1f1f] dark:border-white md:py-5"
					disabled={isRedirecting}
					onClick={handleGoogleLogin}
				>
					<GoogleGLogo className="h-5 w-5" />
					<span className="text-base font-medium">{t("continue_with_google")}</span>
				</Button>
			</div>
		</div>
	);
}
