"use client";

import Link from "next/link";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { buildBackendUrl } from "@/lib/env-config";
import { trackLoginAttempt } from "@/lib/posthog/events";
import { cn } from "@/lib/utils";

// Official Google "G" logo with brand colors
const GoogleLogo = ({ className }: { className?: string }) => (
	<svg
		className={className}
		viewBox="0 0 24 24"
		xmlns="http://www.w3.org/2000/svg"
		role="img"
		aria-label="Google logo"
	>
		<title>Google logo</title>
		<path
			d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
			fill="#4285F4"
		/>
		<path
			d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
			fill="#34A853"
		/>
		<path
			d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
			fill="#FBBC05"
		/>
		<path
			d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
			fill="#EA4335"
		/>
	</svg>
);

interface SignInButtonProps {
	/**
	 * - "desktop": Hidden on mobile, visible on md+ (for navbar with separate mobile menu)
	 * - "mobile": Full width, always visible (for mobile menu)
	 * - "compact": Always visible, compact size (for headers)
	 */
	variant?: "desktop" | "mobile" | "compact";
}

export const SignInButton = ({ variant = "desktop" }: SignInButtonProps) => {
	const [isRedirecting, setIsRedirecting] = useState(false);

	const handleGoogleLogin = () => {
		if (isRedirecting) return;
		setIsRedirecting(true);
		trackLoginAttempt("google");
		window.location.href = buildBackendUrl("/auth/google/authorize-redirect");
	};

	const getGoogleClassName = () => {
		if (variant === "desktop") {
			return "hidden rounded-full border border-white bg-white px-5 py-2 text-sm font-medium text-[#1f1f1f] shadow-sm hover:bg-zinc-100 hover:text-[#1f1f1f] md:flex dark:border-white";
		}
		if (variant === "compact") {
			return "rounded-full border border-white bg-white px-4 py-1.5 text-sm font-medium text-[#1f1f1f] shadow-sm hover:bg-zinc-100 hover:text-[#1f1f1f] dark:border-white";
		}
		// mobile
		return "w-full rounded-lg border border-white bg-white px-8 py-2.5 font-medium text-[#1f1f1f] shadow-sm hover:bg-zinc-100 hover:text-[#1f1f1f] dark:border-white touch-manipulation";
	};

	const getLocalClassName = () => {
		if (variant === "desktop") {
			return "hidden rounded-full bg-black px-8 py-2 text-sm font-bold text-white shadow-[0px_-2px_0px_0px_rgba(255,255,255,0.4)_inset] md:block dark:bg-white dark:text-black";
		}
		if (variant === "compact") {
			return "rounded-full bg-black px-6 py-1.5 text-sm font-bold text-white shadow-[0px_-2px_0px_0px_rgba(255,255,255,0.4)_inset] dark:bg-white dark:text-black";
		}
		return "w-full rounded-lg bg-black px-8 py-2 font-medium text-white shadow-[0px_-2px_0px_0px_rgba(255,255,255,0.4)_inset] dark:bg-white dark:text-black text-center touch-manipulation";
	};

	return (
		<>
			<Button
				type="button"
				variant="ghost"
				onClick={handleGoogleLogin}
				disabled={isRedirecting}
				className={cn(
					"runtime-auth-google flex items-center justify-center gap-2 transition-colors duration-200 disabled:cursor-not-allowed disabled:opacity-50",
					getGoogleClassName()
				)}
			>
				<GoogleLogo className="h-4 w-4" />
				<span>Sign In</span>
			</Button>
			<Link href="/login" className={cn("runtime-auth-local", getLocalClassName())}>
				Sign In
			</Link>
		</>
	);
};
