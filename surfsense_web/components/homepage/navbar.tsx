"use client";
import { motion } from "motion/react";
import React, { useEffect, useState } from "react";
import { Logo } from "@/components/Logo";
import { ThemeTogglerComponent } from "@/components/theme/theme-toggle";
import { cn } from "@/lib/utils";

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
			<div className="flex flex-1 items-center justify-end gap-2">
				<ThemeTogglerComponent />
			</div>
		</motion.div>
	);
};

const MobileNav = ({ isScrolled }: any) => {
	return (
		<motion.div
			className={cn(
				"mx-auto flex w-full max-w-[calc(100vw-2rem)] flex-row items-center justify-between px-4 py-2 lg:hidden transition-all duration-300",
				isScrolled
					? "bg-white/80 backdrop-blur-md border border-white/20 shadow-lg dark:bg-neutral-950/80 dark:border-neutral-800/50"
					: "bg-transparent border border-transparent"
			)}
		>
			<div className="flex flex-row items-center gap-2">
				<Logo className="h-8 w-8 rounded-md" />
				<span className="dark:text-white/90 text-gray-800 text-lg font-bold">SurfSense</span>
			</div>
			<ThemeTogglerComponent />
		</motion.div>
	);
};
