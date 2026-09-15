"use client";
import {
	IconBook,
	IconBrandDiscord,
	IconBrandReddit,
	IconChevronDown,
	IconMenu2,
	IconNews,
	IconSparkles,
	IconSpeakerphone,
	IconX,
} from "@tabler/icons-react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import Link from "next/link";
import { Fragment, useEffect, useRef, useState } from "react";
import { SignInButton } from "@/components/auth/sign-in-button";
import { NavbarGitHubStars } from "@/components/homepage/github-stars-badge";
import { Logo } from "@/components/Logo";
import { ThemeTogglerComponent } from "@/components/theme/theme-toggle";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface NavItem {
	name: string;
	link: string;
}

interface ResourceItem extends NavItem {
	description: string;
	icon: typeof IconNews;
}

const resourceItems: ResourceItem[] = [
	{
		name: "Blog",
		link: "/blog",
		description: "Guides, comparisons, and deep dives",
		icon: IconNews,
	},
	{
		name: "Announcements",
		link: "/announcements",
		description: "Product news and updates",
		icon: IconSpeakerphone,
	},
	{
		name: "Changelog",
		link: "/changelog",
		description: "What's new in SurfSense",
		icon: IconSparkles,
	},
	{
		name: "Docs",
		link: "/docs",
		description: "Setup, connectors, and API reference",
		icon: IconBook,
	},
];

interface NavbarProps {
	/** Override the scrolled-state background classes (desktop & mobile). */
	scrolledBgClassName?: string;
}

interface DesktopNavProps {
	navItems: NavItem[];
	isScrolled: boolean;
	scrolledBgClassName?: string;
}

interface MobileNavProps {
	navItems: NavItem[];
	isScrolled: boolean;
	scrolledBgClassName?: string;
}

export const Navbar = ({ scrolledBgClassName }: NavbarProps = {}) => {
	const [isScrolled, setIsScrolled] = useState(false);

	const navItems: NavItem[] = [
		{ name: "Plugins", link: "/plugins" },
		{ name: "Pricing", link: "/pricing" },
		{ name: "Contact\u00A0Us", link: "/contact" },
	];

	useEffect(() => {
		if (typeof window === "undefined") return;

		const handleScroll = () => {
			setIsScrolled(window.scrollY > 20);
		};

		handleScroll();
		window.addEventListener("scroll", handleScroll, { passive: true });
		return () => window.removeEventListener("scroll", handleScroll);
	}, []);

	return (
		<div className="fixed top-0 left-0 right-0 z-60 w-full select-none">
			<DesktopNav
				navItems={navItems}
				isScrolled={isScrolled}
				scrolledBgClassName={scrolledBgClassName}
			/>
			<MobileNav
				navItems={navItems}
				isScrolled={isScrolled}
				scrolledBgClassName={scrolledBgClassName}
			/>
		</div>
	);
};

const ResourcesDropdown = () => {
	const [open, setOpen] = useState(false);
	const shouldReduceMotion = useReducedMotion();
	const closeTimeout = useRef<ReturnType<typeof setTimeout> | null>(null);

	const openMenu = () => {
		if (closeTimeout.current) clearTimeout(closeTimeout.current);
		setOpen(true);
	};

	// ponytail: small close delay bridges the pointer gap between trigger and panel
	const closeMenu = () => {
		closeTimeout.current = setTimeout(() => setOpen(false), 100);
	};

	return (
		// biome-ignore lint/a11y/noStaticElementInteractions: hover intent only; keyboard access lives on the button
		<div
			className="relative"
			onMouseEnter={openMenu}
			onMouseLeave={closeMenu}
			onKeyDown={(e) => {
				if (e.key === "Escape") setOpen(false);
			}}
			onBlur={(e) => {
				if (!e.currentTarget.contains(e.relatedTarget as Node)) setOpen(false);
			}}
		>
			<button
				type="button"
				aria-expanded={open}
				aria-haspopup="menu"
				onClick={() => setOpen((prev) => !prev)}
				className={cn(
					"flex cursor-pointer items-center gap-1 rounded-lg px-3 py-2 text-muted-foreground outline-none transition-colors duration-150 ease-out hover:text-foreground focus-visible:ring-3 focus-visible:ring-ring/50",
					open && "bg-accent text-accent-foreground"
				)}
			>
				Resources
				<IconChevronDown
					className={cn("h-3.5 w-3.5 transition-transform duration-200", open && "rotate-180")}
				/>
			</button>
			<AnimatePresence>
				{open && (
					<div className="absolute left-1/2 top-full -translate-x-1/2 pt-2">
						<motion.div
							initial={{
								opacity: 0,
								scale: shouldReduceMotion ? 1 : 0.95,
								y: shouldReduceMotion ? 0 : 6,
							}}
							animate={{ opacity: 1, scale: 1, y: 0 }}
							exit={{
								opacity: 0,
								scale: shouldReduceMotion ? 1 : 0.97,
								y: shouldReduceMotion ? 0 : 4,
								transition: { duration: 0.12, ease: "easeIn" },
							}}
							transition={{ type: "spring", duration: 0.3, bounce: 0.15 }}
							className="w-72 origin-top overflow-hidden rounded-lg border border-border bg-popover p-2 supports-backdrop-filter:backdrop-blur-xl"
						>
							{resourceItems.map((item) => (
								<Link
									key={item.link}
									href={item.link}
									onClick={() => setOpen(false)}
									className="group flex items-start gap-3 rounded-lg px-3 py-2.5 transition-colors duration-150 ease-out hover:bg-accent"
								>
									<span className="mt-0.5 flex size-8 shrink-0 items-center justify-center rounded-lg border border-border bg-card text-muted-foreground transition-colors duration-150 ease-out group-hover:text-foreground">
										<item.icon className="h-4 w-4" aria-hidden />
									</span>
									<span className="flex flex-col">
										<span className="text-sm font-medium text-foreground">{item.name}</span>
										<span className="text-xs text-muted-foreground">{item.description}</span>
									</span>
								</Link>
							))}
						</motion.div>
					</div>
				)}
			</AnimatePresence>
		</div>
	);
};

const DesktopNav = ({ navItems, isScrolled, scrolledBgClassName }: DesktopNavProps) => {
	const [hovered, setHovered] = useState<number | null>(null);
	return (
		<motion.div
			onMouseLeave={() => {
				setHovered(null);
			}}
			className={cn(
				"mx-auto hidden w-full max-w-[var(--home-max,88rem)] flex-row items-center justify-between self-start px-6 py-3 lg:flex transition-[background-color,border-color] duration-200 ease-out",
				isScrolled
					? (scrolledBgClassName ??
							"bg-background/85 supports-backdrop-filter:backdrop-blur-md border-b border-border")
					: "bg-transparent border border-transparent"
			)}
		>
			<Link
				href="/"
				className="flex flex-1 flex-row items-center gap-0.5 hover:opacity-80 transition-opacity"
			>
				<Logo className="h-8 w-8 rounded-md" disableLink />
				<span className="text-foreground text-lg font-bold tracking-tight">SurfSense</span>
			</Link>
			<div className="hidden flex-1 flex-row items-center justify-center space-x-2 text-sm font-medium text-zinc-600 transition duration-200 hover:text-zinc-800 lg:flex lg:space-x-2">
				{navItems.map((navItem: NavItem, idx: number) => (
					<Fragment key={navItem.link}>
						<Link
							onMouseEnter={() => setHovered(idx)}
							onMouseLeave={() => setHovered(null)}
							className="relative rounded-lg px-3 py-2 text-muted-foreground transition-colors duration-150 ease-out hover:text-foreground"
							href={navItem.link}
						>
							{hovered === idx && (
								<motion.div
									layoutId="hovered"
									className="absolute inset-0 size-full rounded-lg bg-accent"
								/>
							)}
							<span className="relative z-20">{navItem.name}</span>
						</Link>
						{navItem.link === "/pricing" && <ResourcesDropdown />}
					</Fragment>
				))}
			</div>
			<div className="flex flex-1 items-center justify-end gap-2">
				<Link
					href="https://discord.gg/ejRNvftDp9"
					target="_blank"
					rel="noopener noreferrer"
					aria-label="SurfSense on Discord"
					className="hidden rounded-lg p-2 hover:bg-accent transition-colors duration-150 ease-out md:flex items-center justify-center focus-visible:ring-3 focus-visible:ring-ring/50 outline-none"
				>
					<IconBrandDiscord className="size-5 text-muted-foreground" aria-hidden />
				</Link>
				<Link
					href="https://www.reddit.com/r/SurfSense/"
					target="_blank"
					rel="noopener noreferrer"
					aria-label="SurfSense on Reddit"
					className="hidden rounded-lg p-2 hover:bg-accent transition-colors duration-150 ease-out md:flex items-center justify-center focus-visible:ring-3 focus-visible:ring-ring/50 outline-none"
				>
					<IconBrandReddit className="size-5 text-muted-foreground" aria-hidden />
				</Link>
				<NavbarGitHubStars className="hidden md:flex" />
				<span className="ss-theme-toggle">
					<ThemeTogglerComponent />
				</span>
				<SignInButton variant="desktop" />
			</div>
		</motion.div>
	);
};

const MobileNav = ({ navItems, isScrolled, scrolledBgClassName }: MobileNavProps) => {
	const [open, setOpen] = useState(false);
	const navRef = useRef<HTMLDivElement>(null);

	useEffect(() => {
		if (!open) return;

		const handleClickOutside = (e: MouseEvent | TouchEvent) => {
			if (navRef.current && !navRef.current.contains(e.target as Node)) {
				setOpen(false);
			}
		};

		document.addEventListener("mousedown", handleClickOutside);
		document.addEventListener("touchstart", handleClickOutside, { passive: true });
		return () => {
			document.removeEventListener("mousedown", handleClickOutside);
			document.removeEventListener("touchstart", handleClickOutside);
		};
	}, [open]);

	return (
		<motion.div
			ref={navRef}
			animate={{ borderRadius: open ? "4px" : "2rem" }}
			key={String(open)}
			className={cn(
				"relative mx-auto flex w-full max-w-[calc(100vw-2rem)] flex-col items-center justify-between px-4 py-2 lg:hidden transition-[background-color,border-color,box-shadow] duration-300",
				isScrolled
					? (scrolledBgClassName ??
							"bg-background/85 supports-backdrop-filter:backdrop-blur-md border-b border-border")
					: "bg-transparent border border-transparent"
			)}
		>
			<div className="flex w-full flex-row items-center justify-between">
				<Link
					href="/"
					className="flex flex-row items-center gap-2 hover:opacity-80 transition-opacity"
				>
					<Logo className="h-8 w-8 rounded-md" disableLink />
					<span className="text-foreground text-lg font-bold tracking-tight">SurfSense</span>
				</Link>
				<Button
					type="button"
					variant="ghost"
					size="icon"
					onClick={() => setOpen((prev) => !prev)}
					className="relative z-50 -mr-2 rounded-lg p-2 hover:bg-accent transition-colors duration-150 ease-out touch-manipulation focus-visible:ring-3 focus-visible:ring-ring/50 outline-none"
					aria-label={open ? "Close menu" : "Open menu"}
				>
					{open ? (
						<IconX className="size-6 text-foreground" />
					) : (
						<IconMenu2 className="size-6 text-foreground" />
					)}
				</Button>
			</div>

			<AnimatePresence>
				{open && (
					<motion.div
						initial={{ opacity: 0, y: -10 }}
						animate={{ opacity: 1, y: 0 }}
						exit={{ opacity: 0, y: -10 }}
						transition={{ duration: 0.2, ease: "easeOut" }}
						className="absolute inset-x-0 top-full z-20 flex w-full flex-col items-start justify-start gap-4 border-b border-border bg-popover supports-backdrop-filter:backdrop-blur-xl px-4 py-6"
					>
						{navItems.map((navItem: NavItem) => (
							<Fragment key={navItem.link}>
								<Link
									href={navItem.link}
									className="relative text-muted-foreground transition-colors duration-150 ease-out hover:text-foreground"
								>
									<motion.span className="block">{navItem.name} </motion.span>
								</Link>
								{navItem.link === "/pricing" &&
									resourceItems.map((item) => (
										<Link
											key={item.link}
											href={item.link}
											className="relative text-muted-foreground transition-colors duration-150 ease-out hover:text-foreground"
										>
											<motion.span className="block">{item.name} </motion.span>
										</Link>
									))}
							</Fragment>
						))}
						<div className="flex w-full items-center gap-2 pt-2">
							<Link
								href="https://discord.gg/ejRNvftDp9"
								target="_blank"
								rel="noopener noreferrer"
								aria-label="SurfSense on Discord"
								className="flex items-center justify-center rounded-lg p-2 hover:bg-accent transition-colors duration-150 ease-out touch-manipulation focus-visible:ring-3 focus-visible:ring-ring/50 outline-none"
							>
								<IconBrandDiscord className="size-5 text-muted-foreground" aria-hidden />
							</Link>
							<Link
								href="https://www.reddit.com/r/SurfSense/"
								target="_blank"
								rel="noopener noreferrer"
								aria-label="SurfSense on Reddit"
								className="flex items-center justify-center rounded-lg p-2 hover:bg-accent transition-colors duration-150 ease-out touch-manipulation focus-visible:ring-3 focus-visible:ring-ring/50 outline-none"
							>
								<IconBrandReddit className="size-5 text-muted-foreground" aria-hidden />
							</Link>
							<NavbarGitHubStars className="rounded-lg" />
							<span className="ss-theme-toggle">
								<ThemeTogglerComponent />
							</span>
						</div>
						<SignInButton variant="mobile" />
					</motion.div>
				)}
			</AnimatePresence>
		</motion.div>
	);
};
