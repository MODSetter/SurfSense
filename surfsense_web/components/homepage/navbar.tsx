"use client";
import { motion } from "motion/react";
import React, { useEffect, useState } from "react";
import Link from "next/link";
import { IconBrandGithub } from "@tabler/icons-react";
import { Logo } from "@/components/Logo";
import { ThemeTogglerComponent } from "@/components/theme/theme-toggle";
import { cn } from "@/lib/utils";
import { useSiteConfig } from "@/contexts/SiteConfigContext";

export const Navbar = () => {
	const [isScrolled, setIsScrolled] = useState(false);

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
			<DesktopNav isScrolled={isScrolled} />
			<MobileNav isScrolled={isScrolled} />
		</div>
	);
};

const DesktopNav = ({ isScrolled }: any) => {
	const { config } = useSiteConfig();

	return (
		<motion.div
			className={cn(
				"mx-auto hidden w-full max-w-7xl flex-row items-center justify-between self-start rounded-full px-4 py-2 lg:flex transition-all duration-300",
				isScrolled
					? "bg-white/80 backdrop-blur-md border border-white/20 shadow-lg dark:bg-neutral-950/80 dark:border-neutral-800/50"
					: "bg-transparent border border-transparent"
			)}
		>
			<div className="flex flex-1 flex-row items-center gap-2">
				<Logo className="h-8 w-8 rounded-md" />
				<span className="dark:text-white/90 text-gray-800 text-lg font-bold">SurfSense</span>
			</div>

			<div className="flex items-center gap-6">
				{config.show_pricing_link && !config.disable_pricing_route && (
					<Link
						href="/pricing"
						className="text-neutral-600 dark:text-neutral-400 hover:text-neutral-900 dark:hover:text-neutral-100 transition-colors text-sm font-medium"
					>
						Pricing
					</Link>
				)}
				{config.show_docs_link && !config.disable_docs_route && (
					<Link
						href="/docs"
						className="text-neutral-600 dark:text-neutral-400 hover:text-neutral-900 dark:hover:text-neutral-100 transition-colors text-sm font-medium"
					>
						Docs
					</Link>
				)}
				{config.show_github_link && (
					<Link
						href="https://github.com/okapteinis/SurfSense"
						target="_blank"
						rel="noopener noreferrer"
						className="text-neutral-600 dark:text-neutral-400 hover:text-neutral-900 dark:hover:text-neutral-100 transition-colors"
						aria-label="GitHub"
					>
						<IconBrandGithub className="h-5 w-5" />
					</Link>
				)}
			</div>

			<div className="flex flex-1 items-center justify-end gap-2">
				{config.show_sign_in && (
					<Link
						href="/login"
						className="text-sm font-medium text-neutral-600 dark:text-neutral-400 hover:text-neutral-900 dark:hover:text-neutral-100 transition-colors"
					>
						Sign In
					</Link>
				)}
				<ThemeTogglerComponent />
			</div>
		</motion.div>
	);
};

const MobileNav = ({ isScrolled }: any) => {
	const { config } = useSiteConfig();
	const [isMenuOpen, setIsMenuOpen] = useState(false);

	// Check if we have any navigation items to show
	const hasNavItems =
		(config.show_pricing_link && !config.disable_pricing_route) ||
		(config.show_docs_link && !config.disable_docs_route) ||
		config.show_github_link ||
		config.show_sign_in;

	return (
		<>
			<motion.div
				className={cn(
					"mx-auto flex w-full max-w-[calc(100vw-2rem)] flex-row items-center justify-between px-4 py-2 lg:hidden transition-all duration-300 rounded-full",
					isScrolled
						? "bg-white/80 backdrop-blur-md border border-white/20 shadow-lg dark:bg-neutral-950/80 dark:border-neutral-800/50"
						: "bg-transparent border border-transparent"
				)}
			>
				<div className="flex flex-row items-center gap-2">
					<Logo className="h-8 w-8 rounded-md" />
					<span className="dark:text-white/90 text-gray-800 text-lg font-bold">SurfSense</span>
				</div>
				<div className="flex items-center gap-2">
					<ThemeTogglerComponent />
					{hasNavItems && (
						<button
							onClick={() => setIsMenuOpen(!isMenuOpen)}
							className="text-neutral-600 dark:text-neutral-400 hover:text-neutral-900 dark:hover:text-neutral-100 transition-colors p-2"
							aria-label="Toggle menu"
						>
							<svg
								className="h-6 w-6"
								fill="none"
								strokeLinecap="round"
								strokeLinejoin="round"
								strokeWidth="2"
								viewBox="0 0 24 24"
								stroke="currentColor"
							>
								{isMenuOpen ? (
									<path d="M6 18L18 6M6 6l12 12" />
								) : (
									<path d="M4 6h16M4 12h16M4 18h16" />
								)}
							</svg>
						</button>
					)}
				</div>
			</motion.div>

			{/* Mobile Menu Dropdown */}
			{hasNavItems && isMenuOpen && (
				<motion.div
					initial={{ opacity: 0, y: -10 }}
					animate={{ opacity: 1, y: 0 }}
					exit={{ opacity: 0, y: -10 }}
					className="mx-auto mt-2 w-full max-w-[calc(100vw-2rem)] lg:hidden bg-white/95 dark:bg-neutral-950/95 backdrop-blur-md border border-white/20 dark:border-neutral-800/50 rounded-2xl shadow-lg overflow-hidden"
				>
					<div className="flex flex-col p-4 gap-2">
						{config.show_pricing_link && !config.disable_pricing_route && (
							<Link
								href="/pricing"
								onClick={() => setIsMenuOpen(false)}
								className="text-neutral-600 dark:text-neutral-400 hover:text-neutral-900 dark:hover:text-neutral-100 transition-colors text-sm font-medium py-2 px-3 rounded-lg hover:bg-neutral-100 dark:hover:bg-neutral-900"
							>
								Pricing
							</Link>
						)}
						{config.show_docs_link && !config.disable_docs_route && (
							<Link
								href="/docs"
								onClick={() => setIsMenuOpen(false)}
								className="text-neutral-600 dark:text-neutral-400 hover:text-neutral-900 dark:hover:text-neutral-100 transition-colors text-sm font-medium py-2 px-3 rounded-lg hover:bg-neutral-100 dark:hover:bg-neutral-900"
							>
								Docs
							</Link>
						)}
						{config.show_github_link && (
							<Link
								href="https://github.com/okapteinis/SurfSense"
								target="_blank"
								rel="noopener noreferrer"
								onClick={() => setIsMenuOpen(false)}
								className="text-neutral-600 dark:text-neutral-400 hover:text-neutral-900 dark:hover:text-neutral-100 transition-colors text-sm font-medium py-2 px-3 rounded-lg hover:bg-neutral-100 dark:hover:bg-neutral-900 flex items-center gap-2"
							>
								<IconBrandGithub className="h-4 w-4" />
								GitHub
							</Link>
						)}
						{config.show_sign_in && (
							<Link
								href="/login"
								onClick={() => setIsMenuOpen(false)}
								className="text-neutral-600 dark:text-neutral-400 hover:text-neutral-900 dark:hover:text-neutral-100 transition-colors text-sm font-medium py-2 px-3 rounded-lg hover:bg-neutral-100 dark:hover:bg-neutral-900"
							>
								Sign In
							</Link>
						)}
					</div>
				</motion.div>
			)}
		</>
	);
};
