"use client";

import { motion } from "motion/react";
import Link from "next/link";
import { AUTH_TYPE, BACKEND_URL } from "@/lib/env-config";
import { trackLoginAttempt } from "@/lib/posthog/events";
import { cn } from "@/lib/utils";

// Official Google "G" logo with brand colors
const GoogleLogo = ({ className }: { className?: string }) => (
	<svg className={className} viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
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
	const isGoogleAuth = AUTH_TYPE === "GOOGLE";

	const handleGoogleLogin = () => {
		trackLoginAttempt("google");
		window.location.href = `${BACKEND_URL}/auth/google/authorize-redirect`;
	};

	const getClassName = () => {
		if (variant === "desktop") {
			return isGoogleAuth
				? "hidden rounded-full bg-white px-5 py-2 text-sm text-neutral-700 shadow-md ring-1 ring-neutral-200/50 hover:shadow-lg md:flex dark:bg-neutral-900 dark:text-neutral-200 dark:ring-neutral-700/50"
				: "hidden rounded-full bg-black px-8 py-2 text-sm font-bold text-white shadow-[0px_-2px_0px_0px_rgba(255,255,255,0.4)_inset] md:block dark:bg-white dark:text-black";
		}
		if (variant === "compact") {
			return isGoogleAuth
				? "rounded-full bg-white px-4 py-1.5 text-sm text-neutral-700 shadow-md ring-1 ring-neutral-200/50 hover:shadow-lg dark:bg-neutral-900 dark:text-neutral-200 dark:ring-neutral-700/50"
				: "rounded-full bg-black px-6 py-1.5 text-sm font-bold text-white shadow-[0px_-2px_0px_0px_rgba(255,255,255,0.4)_inset] dark:bg-white dark:text-black";
		}
		// mobile
		return isGoogleAuth
			? "w-full rounded-lg bg-white px-8 py-2.5 text-neutral-700 shadow-md ring-1 ring-neutral-200/50 dark:bg-neutral-900 dark:text-neutral-200 dark:ring-neutral-700/50 touch-manipulation"
			: "w-full rounded-lg bg-black px-8 py-2 font-medium text-white shadow-[0px_-2px_0px_0px_rgba(255,255,255,0.4)_inset] dark:bg-white dark:text-black text-center touch-manipulation";
	};

	if (isGoogleAuth) {
		return (
			<motion.button
				type="button"
				onClick={handleGoogleLogin}
				whileHover={{ scale: 1.02 }}
				whileTap={{ scale: 0.98 }}
				className={cn(
					"flex items-center justify-center gap-2 font-semibold transition-all duration-200",
					getClassName()
				)}
			>
				<GoogleLogo className="h-4 w-4" />
				<span>Sign In</span>
			</motion.button>
		);
	}

	return (
		<Link href="/login" className={getClassName()}>
			Sign In
		</Link>
	);
};
