"use client";
import {
	IconBrandDiscord,
	IconBrandGithub,
	IconBrandReddit,
	IconMenu2,
	IconX,
} from "@tabler/icons-react";
import { AnimatePresence, motion } from "motion/react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { SignInButton } from "@/components/auth/sign-in-button";
import { Logo } from "@/components/Logo";
import { ThemeTogglerComponent } from "@/components/theme/theme-toggle";
import { useGithubStars } from "@/hooks/use-github-stars";
import { cn } from "@/lib/utils";

export const Navbar = () => {
	const [isScrolled, setIsScrolled] = useState(false);

	const navItems = [
		{ name: "Pricing", link: "/pricing" },
		{ name: "Contact\u00A0Us", link: "/contact" },
		{ name: "Changelog", link: "/changelog" },
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
		<div className="fixed top-1 left-0 right-0 z-60 w-full">
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
			<Link
				href="/"
				className="flex flex-1 flex-row items-center gap-0.5 hover:opacity-80 transition-opacity"
			>
				<Logo className="h-8 w-8 rounded-md" />
				<span className="dark:text-white/90 text-gray-800 text-lg font-bold">SurfSense</span>
			</Link>
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
				<Link
					href="/"
					className="flex flex-row items-center gap-2 hover:opacity-80 transition-opacity"
				>
					<Logo className="h-8 w-8 rounded-md" />
					<span className="dark:text-white/90 text-gray-800 text-lg font-bold">SurfSense</span>
				</Link>
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
