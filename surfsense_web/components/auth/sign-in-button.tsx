"use client";

import Link from "next/link";

interface SignInButtonProps {
	/**
	 * - "desktop": Hidden on mobile, visible on md+ (for navbar with separate mobile menu)
	 * - "mobile": Full width, always visible (for mobile menu)
	 * - "compact": Always visible, compact size (for headers)
	 */
	variant?: "desktop" | "mobile" | "compact";
}

export const SignInButton = ({ variant = "desktop" }: SignInButtonProps) => {
	const getClassName = () => {
		if (variant === "desktop") {
			return "hidden rounded-full bg-black px-8 py-2 text-sm font-bold text-white shadow-[0px_-2px_0px_0px_rgba(255,255,255,0.4)_inset] md:block dark:bg-white dark:text-black";
		}
		if (variant === "compact") {
			return "rounded-full bg-black px-6 py-1.5 text-sm font-bold text-white shadow-[0px_-2px_0px_0px_rgba(255,255,255,0.4)_inset] dark:bg-white dark:text-black";
		}
		// mobile
		return "w-full rounded-lg bg-black px-8 py-2 font-medium text-white shadow-[0px_-2px_0px_0px_rgba(255,255,255,0.4)_inset] dark:bg-white dark:text-black text-center touch-manipulation";
	};

	return (
		<Link href="/login" className={getClassName()}>
			Sign In
		</Link>
	);
};
