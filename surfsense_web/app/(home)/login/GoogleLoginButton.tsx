"use client";
import { useTranslations } from "next-intl";
import { useState } from "react";
import { Logo } from "@/components/Logo";
import { Button } from "@/components/ui/button";
import { buildBackendUrl } from "@/lib/env-config";
import { trackLoginAttempt } from "@/lib/posthog/events";

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
		<section className="ss-home-hero ss-home-pad flex min-h-screen items-center justify-center">
			<div className="mx-auto flex w-full max-w-md flex-col items-center text-center">
				<Logo className="h-14 w-14 rounded-md transition-all md:h-16 md:w-16" />
				<h1 className="ss-home-h2 mt-6 mb-8">{t("sign_in")}</h1>

				<Button
					variant="outline"
					className="w-full max-w-md gap-2 rounded-md border-white bg-white px-6 py-5 font-medium text-[#1f1f1f] shadow-sm hover:bg-zinc-100 hover:text-[#1f1f1f] dark:border-white md:py-5"
					disabled={isRedirecting}
					onClick={handleGoogleLogin}
				>
					<GoogleGLogo className="h-5 w-5" />
					<span className="text-base font-medium">{t("continue_with_google")}</span>
				</Button>
			</div>
		</section>
	);
}
