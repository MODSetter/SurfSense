"use client";

import { IconChevronDown, IconMenu2, IconX } from "@tabler/icons-react";
import Image from "next/image";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { HomeStars } from "@/components/homepage/home/home-stars";

/**
 * Homepage navigation.
 *
 * A port of the reference design's `Nav.svelte`: a flush bar the width of the
 * page column, ruled on three sides so it reads as the first cell of the grid
 * rather than as a floating pill.
 *
 * It is sticky and visually identical at every scroll position — opaque, no
 * blur, no border that appears on scroll. A bar that restyles itself as the
 * page moves is motion the visitor did not ask for, and the reference does not
 * do it.
 *
 * This is homepage-only on purpose. The shared `Navbar` still serves every
 * other route under `(home)`, so nothing here changes those pages.
 */

const SIGN_IN_URL = "/login";

type NavLink = { name: string; href: string; external?: boolean };
type NavMenuItem = NavLink & { description: string };

const LINKS: NavLink[] = [
	{ name: "Connectors", href: "/connectors" },
	{ name: "Docs", href: "/docs" },
	{ name: "Pricing", href: "/pricing" },
];

const RESOURCES: NavMenuItem[] = [
	{ name: "Blog", href: "/blog", description: "Guides, comparisons and deep dives" },
	{ name: "Announcements", href: "/announcements", description: "Product news and updates" },
	{ name: "Changelog", href: "/changelog", description: "What's new in SurfSense" },
	{ name: "Contact us", href: "/contact", description: "Questions, bugs and feedback" },
];

function Wordmark() {
	return (
		<Link
			href="/"
			className="flex shrink-0 items-center gap-1.5 rounded-[2px] px-1 py-1 transition-colors duration-100 hover:bg-[color:var(--accent)] focus-visible:outline-2 focus-visible:outline-offset-[-2px] focus-visible:outline-[color:var(--ring)]"
		>
			<Image
				src="/icon-128.svg"
				alt=""
				width={20}
				height={20}
				priority
				className="size-5 select-none invert"
			/>
			<span className="text-[0.9375rem] font-semibold tracking-tight text-[color:var(--foreground)]">
				SurfSense
			</span>
		</Link>
	);
}

export function HomeNav() {
	const [menuOpen, setMenuOpen] = useState(false);
	const [resourcesOpen, setResourcesOpen] = useState(false);
	const headerRef = useRef<HTMLElement>(null);

	// Escape closes whatever is open; a click outside the header closes the
	// dropdown. Both match the reference's behaviour and are what a visitor
	// expects from a menu regardless of how it was opened.
	useEffect(() => {
		if (!menuOpen && !resourcesOpen) {
			return;
		}

		const onKeyDown = (event: KeyboardEvent) => {
			if (event.key === "Escape") {
				setMenuOpen(false);
				setResourcesOpen(false);
			}
		};
		const onPointerDown = (event: PointerEvent) => {
			if (!headerRef.current?.contains(event.target as Node)) {
				setResourcesOpen(false);
			}
		};

		document.addEventListener("keydown", onKeyDown);
		document.addEventListener("pointerdown", onPointerDown);
		return () => {
			document.removeEventListener("keydown", onKeyDown);
			document.removeEventListener("pointerdown", onPointerDown);
		};
	}, [menuOpen, resourcesOpen]);

	const closeAll = () => {
		setMenuOpen(false);
		setResourcesOpen(false);
	};

	return (
		<header ref={headerRef} className="ss-home-nav">
			<div className="ss-home-nav-bar">
				<Wordmark />

				<nav className="hidden items-center md:flex" aria-label="Main">
					{LINKS.map((link) => (
						<Link key={link.href} href={link.href} className="ss-home-nav-link">
							{link.name}
						</Link>
					))}

					<div className="relative">
						<button
							type="button"
							className="ss-home-nav-link"
							aria-expanded={resourcesOpen}
							onClick={() => setResourcesOpen((open) => !open)}
						>
							Resources
							<IconChevronDown
								aria-hidden="true"
								className={`size-3 shrink-0 text-[color:var(--muted-foreground)] transition-transform duration-150 ${
									resourcesOpen ? "rotate-180" : ""
								}`}
							/>
						</button>

						{resourcesOpen ? (
							<div className="ss-home-nav-panel">
								{RESOURCES.map((item) => (
									<Link
										key={item.href}
										href={item.href}
										onClick={closeAll}
										className="ss-home-nav-item"
									>
										<span className="text-[0.8125rem] font-medium text-[color:var(--foreground)]">
											{item.name}
										</span>
										<span className="text-xs text-[color:var(--muted-foreground)]">
											{item.description}
										</span>
									</Link>
								))}
							</div>
						) : null}
					</div>
				</nav>

				<div className="flex items-center gap-1">
					{/* The bar's one action is signing in. Downloading is the hero's job:
					    repeating it here would put two primary calls to action on the
					    same screen, competing with each other. */}
					<HomeStars />

					<Link href={SIGN_IN_URL} className="ss-home-nav-cta">
						Sign in
					</Link>

					<button
						type="button"
						onClick={() => {
							setMenuOpen((open) => !open);
							setResourcesOpen(false);
						}}
						aria-label={menuOpen ? "Close menu" : "Open menu"}
						aria-expanded={menuOpen}
						className="ss-home-nav-link ss-home-nav-toggle"
					>
						{menuOpen ? (
							<IconX aria-hidden="true" className="size-4" />
						) : (
							<IconMenu2 aria-hidden="true" className="size-4" />
						)}
					</button>
				</div>
			</div>

			{menuOpen ? (
				<>
					{/* Tap-to-dismiss ground. It is decorative: Escape and the toggle
					    both already close the menu, so a keyboard user loses nothing by
					    it being unreachable. */}
					<button
						type="button"
						aria-hidden="true"
						tabIndex={-1}
						className="ss-home-nav-scrim"
						onClick={closeAll}
					/>

					<div className="ss-home-nav-drawer">
						{/* No Sign in here: the bar's own button stays visible while the
						    drawer is open, so repeating it would show the same control
						    twice on one screen. */}
						<div className="flex flex-col gap-0.5 px-4 py-3">
							{LINKS.map((link) => (
								<Link
									key={link.href}
									href={link.href}
									onClick={closeAll}
									className="ss-home-nav-link"
								>
									{link.name}
								</Link>
							))}

							<div className="my-1.5 border-t border-[color:var(--border)]" />
							<p className="ss-home-eyebrow px-2.5 pt-1 pb-1">Resources</p>

							{RESOURCES.map((item) => (
								<Link
									key={item.href}
									href={item.href}
									onClick={closeAll}
									className="ss-home-nav-link"
								>
									{item.name}
								</Link>
							))}
						</div>
					</div>
				</>
			) : null}
		</header>
	);
}
