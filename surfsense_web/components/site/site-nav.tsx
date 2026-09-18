"use client";

import { IconChevronDown, IconMenu2, IconX } from "@tabler/icons-react";
import Image from "next/image";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { TopAnnouncementBar } from "@/components/homepage/top-announcement-bar";
import { NAV_LINKS, NAV_RESOURCES } from "@/components/site/site-content";
import { SiteStars } from "@/components/site/site-stars";

/**
 * Site navigation.
 *
 * Rendered once by `app/(home)/layout.tsx`, above any route branch, so it is a
 * single element in a single slot for every page. React therefore keeps it
 * mounted across navigations: the drawer, the dropdown, the scroll listener and
 * the star query all survive, and only the content below it changes. Rendering
 * a different nav per route — which is what this replaced — made React unmount
 * one component and mount another, resetting all of that on every link click.
 *
 * It is sticky and visually identical at every scroll position: opaque, no
 * blur, no border that appears on scroll.
 *
 * It carries no palette of its own. Inside `.ss-home` it picks up the pinned
 * dark palette; everywhere else it picks up the same token names from
 * `globals.css` and follows the visitor's theme.
 *
 * The star count arrives as a prop rather than being fetched here: it is read
 * and cached on the server, so it is already in the HTML on first paint.
 */

function Wordmark() {
	return (
		<Link
			href="/"
			className="flex shrink-0 items-center gap-1.5 rounded-[2px] px-1 py-1 transition-colors duration-100 hover:text-[color:var(--muted-foreground)] focus-visible:outline-2 focus-visible:outline-offset-[-2px] focus-visible:outline-[color:var(--ring)]"
		>
			<Image
				src="/icon-128.svg"
				alt=""
				width={20}
				height={20}
				priority
				className="size-5 select-none dark:invert"
			/>
			<span className="text-[0.9375rem] font-semibold tracking-tight text-[color:var(--foreground)]">
				SurfSense
			</span>
		</Link>
	);
}

export function SiteNav({ starCount, starsHref }: { starCount: number | null; starsHref: string }) {
	const [menuOpen, setMenuOpen] = useState(false);
	const [resourcesOpen, setResourcesOpen] = useState(false);
	const headerRef = useRef<HTMLElement>(null);

	// Escape closes whatever is open; a click outside the header closes the
	// dropdown. Both match what a visitor expects from a menu regardless of how
	// it was opened.
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
			<TopAnnouncementBar />
			<div className="ss-home-nav-bar">
				<Wordmark />

				<nav className="hidden items-center md:flex" aria-label="Main">
					{NAV_LINKS.map((link) => (
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
								{NAV_RESOURCES.map((item) => (
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
					<SiteStars count={starCount} href={starsHref} />

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

					{/* No Sign in here: the bar's own button stays visible while the
					    drawer is open, so repeating it would show the same control
					    twice on one screen. */}
					<div className="ss-home-nav-drawer">
						<div className="flex flex-col gap-0.5 px-4 py-3">
							{NAV_LINKS.map((link) => (
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

							{NAV_RESOURCES.map((item) => (
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
