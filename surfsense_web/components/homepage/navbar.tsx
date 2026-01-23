"use client";
import { IconBrandDiscord, IconBrandGithub, IconBrandReddit, IconMenu2, IconX } from "@tabler/icons-react";
import { AnimatePresence, motion } from "motion/react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { Logo } from "@/components/Logo";
import { ThemeTogglerComponent } from "@/components/theme/theme-toggle";
import { useGithubStars } from "@/hooks/use-github-stars";
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

// Sign in button component that handles both Google OAuth and local auth
const SignInButton = ({ variant = "desktop" }: { variant?: "desktop" | "mobile" }) => {
	const isGoogleAuth = AUTH_TYPE === "GOOGLE";

	const handleGoogleLogin = () => {
		trackLoginAttempt("google");
		window.location.href = `${BACKEND_URL}/auth/google/authorize-redirect`;
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
					variant === "desktop"
						? "hidden rounded-full bg-white px-5 py-2 text-sm text-neutral-700 shadow-md ring-1 ring-neutral-200/50 hover:shadow-lg md:flex dark:bg-neutral-900 dark:text-neutral-200 dark:ring-neutral-700/50"
						: "w-full rounded-lg bg-white px-8 py-2.5 text-neutral-700 shadow-md ring-1 ring-neutral-200/50 dark:bg-neutral-900 dark:text-neutral-200 dark:ring-neutral-700/50 touch-manipulation"
				)}
			>
				<GoogleLogo className="h-4 w-4" />
				<span>Sign In</span>
			</motion.button>
		);
	}

	return (
		<Link
			href="/login"
			className={cn(
				variant === "desktop"
					? "hidden rounded-full bg-black px-8 py-2 text-sm font-bold text-white shadow-[0px_-2px_0px_0px_rgba(255,255,255,0.4)_inset] md:block dark:bg-white dark:text-black"
					: "w-full rounded-lg bg-black px-8 py-2 font-medium text-white shadow-[0px_-2px_0px_0px_rgba(255,255,255,0.4)_inset] dark:bg-white dark:text-black text-center touch-manipulation"
			)}
		>
			Sign In
		</Link>
	);
};

export const Navbar = () => {
	const [isScrolled, setIsScrolled] = useState(false);

	const navItems = [
		// { name: "Home", link: "/" },
		{ name: "Pricing", link: "/pricing" },
		{ name: "Changelog", link: "/changelog" },
		// { name: "Sign In", link: "/login" },
		{ name: "Docs", link: "/docs" },
	];

	useEffect(() => {
		if (typeof window === "undefined") return;

		const handleScroll = () => {
			setIsScrolled(window.scrollY > 20);
		};

		handleScroll();
		window.addEventListener("scroll", handleScroll);
		return () => window.removeEventListener("scroll", handleScroll);
	}, []);

	return (
		<div className="fixed top-1 left-0 right-0 z-[60] w-full">
			<DesktopNav navItems={navItems} isScrolled={isScrolled} />
			<MobileNav navItems={navItems} isScrolled={isScrolled} />
		</div>
	);
};

const DesktopNav = ({ navItems, isScrolled }: any) => {
	const [hovered, setHovered] = useState<number | null>(null);
	const { compactFormat: githubStars, loading: loadingGithubStars } = useGithubStars();
	return (
		<motion.div
			onMouseLeave={() => {
				setHovered(null);
			}}
			className={cn(
				"mx-auto hidden w-full max-w-7xl flex-row items-center justify-between self-start rounded-full px-4 py-2 lg:flex transition-all duration-300",
				isScrolled
					? "bg-white/80 backdrop-blur-md border border-white/20 shadow-lg dark:bg-neutral-950/80 dark:border-neutral-800/50"
					: "bg-transparent border border-transparent"
			)}
		>
			<div className="flex flex-1 flex-row items-center gap-0.5">
				<Logo className="h-8 w-8 rounded-md" />
				<span className="dark:text-white/90 text-gray-800 text-lg font-bold">SurfSense</span>
			</div>
			<div className="hidden flex-1 flex-row items-center justify-center space-x-2 text-sm font-medium text-zinc-600 transition duration-200 hover:text-zinc-800 lg:flex lg:space-x-2">
				{navItems.map((navItem: any, idx: number) => (
					<Link
						onMouseEnter={() => setHovered(idx)}
						onMouseLeave={() => setHovered(null)}
						className="relative px-4 py-2 text-neutral-600 dark:text-neutral-300"
						key={`link=${idx}`}
						href={navItem.link}
					>
						{hovered === idx && (
							<motion.div
								layoutId="hovered"
								className="absolute inset-0 h-full w-full rounded-full bg-gray-100 dark:bg-neutral-800"
							/>
						)}
						<span className="relative z-20">{navItem.name}</span>
					</Link>
				))}
			</div>
			<div className="flex flex-1 items-center justify-end gap-2">
				<Link
					href="https://discord.gg/ejRNvftDp9"
					target="_blank"
					rel="noopener noreferrer"
					className="hidden rounded-full p-2 hover:bg-gray-100 dark:hover:bg-neutral-800 transition-colors md:flex items-center justify-center"
				>
					<IconBrandDiscord className="h-5 w-5 text-neutral-600 dark:text-neutral-300" />
				</Link>
				<Link
					href="https://www.reddit.com/r/SurfSense/"
					target="_blank"
					rel="noopener noreferrer"
					className="hidden rounded-full p-2 hover:bg-gray-100 dark:hover:bg-neutral-800 transition-colors md:flex items-center justify-center"
				>
					<IconBrandReddit className="h-5 w-5 text-neutral-600 dark:text-neutral-300" />
				</Link>
				<Link
					href="https://github.com/MODSetter/SurfSense"
					target="_blank"
					rel="noopener noreferrer"
					className="hidden rounded-full px-3 py-2 hover:bg-gray-100 dark:hover:bg-neutral-800 transition-colors md:flex items-center gap-1.5"
				>
					<IconBrandGithub className="h-5 w-5 text-neutral-600 dark:text-neutral-300" />
					{loadingGithubStars ? (
						<div className="w-6 h-5 dark:bg-neutral-800 animate-pulse"></div>
					) : (
						<span className="text-sm font-medium text-neutral-600 dark:text-neutral-300">
							{githubStars}
						</span>
					)}
				</Link>
				<ThemeTogglerComponent />
				<SignInButton variant="desktop" />
			</div>
		</motion.div>
	);
};

const MobileNav = ({ navItems, isScrolled }: any) => {
	const [open, setOpen] = useState(false);
	const { compactFormat: githubStars, loading: loadingGithubStars } = useGithubStars();

	return (
		<motion.div
			animate={{ borderRadius: open ? "4px" : "2rem" }}
			key={String(open)}
			className={cn(
				"relative mx-auto flex w-full max-w-[calc(100vw-2rem)] flex-col items-center justify-between px-4 py-2 lg:hidden transition-all duration-300",
				isScrolled
					? "bg-white/80 backdrop-blur-md border border-white/20 shadow-lg dark:bg-neutral-950/80 dark:border-neutral-800/50"
					: "bg-transparent border border-transparent"
			)}
		>
			<div className="flex w-full flex-row items-center justify-between">
				<div className="flex flex-row items-center gap-2">
					<Logo className="h-8 w-8 rounded-md" />
					<span className="dark:text-white/90 text-gray-800 text-lg font-bold">SurfSense</span>
				</div>
				<button
					type="button"
					onClick={() => setOpen(!open)}
					className="relative z-50 flex items-center justify-center p-2 -mr-2 rounded-lg hover:bg-gray-100 dark:hover:bg-neutral-800 transition-colors touch-manipulation"
					aria-label={open ? "Close menu" : "Open menu"}
				>
					{open ? (
						<IconX className="h-6 w-6 text-black dark:text-white" />
					) : (
						<IconMenu2 className="h-6 w-6 text-black dark:text-white" />
					)}
				</button>
			</div>

			<AnimatePresence>
				{open && (
					<motion.div
						initial={{ opacity: 0, y: -10 }}
						animate={{ opacity: 1, y: 0 }}
						exit={{ opacity: 0, y: -10 }}
						transition={{ duration: 0.2, ease: "easeOut" }}
						className="absolute inset-x-0 top-full mt-1 z-20 flex w-full flex-col items-start justify-start gap-4 rounded-xl bg-white/90 backdrop-blur-xl border border-white/20 shadow-2xl px-4 py-6 dark:bg-neutral-950/90 dark:border-neutral-800/50"
					>
						{navItems.map((navItem: any, idx: number) => (
							<Link
								key={`link=${idx}`}
								href={navItem.link}
								className="relative text-neutral-600 dark:text-neutral-300"
							>
								<motion.span className="block">{navItem.name} </motion.span>
							</Link>
						))}
						<div className="flex w-full items-center gap-2 pt-2">
							<Link
								href="https://discord.gg/ejRNvftDp9"
								target="_blank"
								rel="noopener noreferrer"
								className="flex items-center justify-center rounded-lg p-2 hover:bg-gray-100 dark:hover:bg-neutral-800 transition-colors touch-manipulation"
							>
								<IconBrandDiscord className="h-5 w-5 text-neutral-600 dark:text-neutral-300" />
							</Link>
							<Link
								href="https://www.reddit.com/r/SurfSense/"
								target="_blank"
								rel="noopener noreferrer"
								className="flex items-center justify-center rounded-lg p-2 hover:bg-gray-100 dark:hover:bg-neutral-800 transition-colors touch-manipulation"
							>
								<IconBrandReddit className="h-5 w-5 text-neutral-600 dark:text-neutral-300" />
							</Link>
							<Link
								href="https://github.com/MODSetter/SurfSense"
								target="_blank"
								rel="noopener noreferrer"
								className="flex items-center gap-1.5 rounded-lg px-3 py-2 hover:bg-gray-100 dark:hover:bg-neutral-800 transition-colors touch-manipulation"
							>
								<IconBrandGithub className="h-5 w-5 text-neutral-600 dark:text-neutral-300" />
								{loadingGithubStars ? (
									<div className="w-6 h-5 dark:bg-neutral-800 animate-pulse"></div>
								) : (
									<span className="text-sm font-medium text-neutral-600 dark:text-neutral-300">
										{githubStars}
									</span>
								)}
							</Link>
							<ThemeTogglerComponent />
						</div>
						<SignInButton variant="mobile" />
					</motion.div>
				)}
			</AnimatePresence>
		</motion.div>
	);
};
