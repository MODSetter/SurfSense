"use client";

import Image from "next/image";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { HomeButton } from "@/components/site/home-button";
import { DOWNLOADS_URL, type SiteLink, type SiteMenuItem } from "@/components/site/site-content";
import { SiteStars } from "@/components/site/site-stars";
import { siteText } from "@/components/site/site-text";
import { cn } from "@/components/ui/cn";
import { ChevronDownIcon, MenuTwoLineIcon } from "@/components/ui/icons";
import { BUSINESS_LAUNCHED } from "@/features/business-launch/business-launched.mts";
import {
	isNavMenu,
	type NavEntry,
	type NavGroup,
	type NavMenu,
	siteNavigation,
} from "@/features/site-navigation/site-navigation";

/**
 * Site navigation.
 *
 * Rendered once by `app/(home)/layout.tsx`, above any route branch, so it is a
 * single element in a single slot for every page. React therefore keeps it
 * mounted across navigations: the drawer, the dropdowns, the scroll listener and
 * the star query all survive, and only the content below it changes. Rendering
 * a different nav per route — which is what this replaced — made React unmount
 * one component and mount another, resetting all of that on every link click.
 *
 * A floating bar, inset from the viewport edges and pinned to the top. It looks
 * the same at every scroll position: no blur or shadow that appears on scroll.
 *
 * It carries no palette of its own. Inside `.ss-home` it picks up the pinned
 * dark palette; everywhere else it picks up the same token names from
 * `globals.css` and follows the visitor's theme. Styling is Tailwind; the
 * `ss-home-nav*` classes left on the markup are hooks for the surface shadow
 * and the menu motion in `home.css`.
 *
 * What it links comes from `siteNavigation`, which changes with the Business
 * launch switch: plain links and dropdown menus, in order, the For menu first.
 * One menu is open at a time.
 *
 * The star count arrives as a prop rather than being fetched here: it is read
 * and cached on the server, so it is already in the HTML on first paint.
 */

const MENU_ID = "site-nav-menu";

const NAV = siteNavigation(BUSINESS_LAUNCHED);

/**
 * The drawer's runs: each group of a menu under its own heading (a menu of one group under
 * the menu's name), and the plain links between menus together.
 */
type DrawerGroup = { key: string; heading?: string; links: SiteLink[] };

function drawerGroups(entries: NavEntry[]): DrawerGroup[] {
	const groups: DrawerGroup[] = [];
	for (const entry of entries) {
		if (isNavMenu(entry)) {
			for (const group of entry.groups) {
				const heading = group.heading ?? entry.name;
				groups.push({ key: `${entry.name}/${heading}`, heading, links: group.items });
			}
			continue;
		}
		const last = groups.at(-1);
		if (last && last.heading === undefined) {
			last.links.push(entry);
		} else {
			groups.push({ key: entry.href, links: [entry] });
		}
	}
	return groups;
}

const DRAWER_GROUPS = drawerGroups(NAV);

const LINK_CLASS =
	"flex items-center gap-1 rounded-lg px-3 py-2 text-sm font-medium text-muted-foreground transition-colors duration-100 hover:text-foreground focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-ring";

const DRAWER_LINK_CLASS = cn(LINK_CLASS, "py-2.5 text-base");

function Wordmark() {
	return (
		<Link
			href="/"
			className="flex shrink-0 items-center gap-1.5 justify-self-start rounded-lg p-1 select-none transition-colors duration-100 hover:text-muted-foreground focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-ring"
		>
			<Image
				src="/icon-128.svg"
				alt=""
				width={20}
				height={20}
				priority
				className="size-6 invert in-[.ss-home]:invert-0"
			/>
			<span className="font-[family-name:var(--font-brand)] text-lg font-semibold text-foreground [font-variation-settings:'SOFT'_75,'WONK'_0]">
				SurfSense
			</span>
		</Link>
	);
}

function DownloadLink({ onClick, className }: { onClick?: () => void; className?: string }) {
	return (
		<HomeButton asChild size="lg" className={cn("rounded-full px-4", className)}>
			<Link href={DOWNLOADS_URL} onClick={onClick}>
				Download
			</Link>
		</HomeButton>
	);
}

function MenuLink({ item, onNavigate }: { item: SiteMenuItem; onNavigate: () => void }) {
	return (
		<Link
			href={item.href}
			onClick={onNavigate}
			className="flex items-center gap-3 rounded-md px-3 py-2.5 transition-colors duration-100 hover:bg-accent focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-ring"
		>
			<span className="grid size-9 shrink-0 place-items-center rounded-lg bg-secondary text-foreground">
				<item.icon aria-hidden="true" className="size-[1.125rem]" />
			</span>
			<span className="flex min-w-0 flex-col gap-0.5">
				<span className="text-sm font-medium text-foreground">{item.name}</span>
				<span className="text-xs text-muted-foreground">{item.description}</span>
			</span>
		</Link>
	);
}

function MenuGroup({ group, onNavigate }: { group: NavGroup; onNavigate: () => void }) {
	return (
		<div className="flex flex-col">
			{group.heading ? (
				<p className={cn(siteText.eyebrow, "px-3 pt-2.5 pb-1")}>{group.heading}</p>
			) : null}
			{group.items.map((item) => (
				<MenuLink key={item.href} item={item} onNavigate={onNavigate} />
			))}
		</div>
	);
}

/**
 * One dropdown. A menu of one group is a single list, as Resources is; a menu of several
 * groups, as For is, puts its first group in one column and the rest in the other.
 */
function MenuDropdown({
	menu,
	open,
	onToggle,
	onNavigate,
}: {
	menu: NavMenu;
	open: boolean;
	onToggle: () => void;
	onNavigate: () => void;
}) {
	const [first, ...rest] = menu.groups;
	return (
		<div className="relative">
			<button type="button" className={LINK_CLASS} aria-expanded={open} onClick={onToggle}>
				{menu.name}
				<ChevronDownIcon
					aria-hidden="true"
					className={`size-3.5 shrink-0 transition-transform duration-150 ${
						open ? "rotate-180" : ""
					}`}
				/>
			</button>

			{open && first ? (
				<div
					className={cn(
						"absolute top-full left-1/2 mt-7 -translate-x-1/2 rounded-xl bg-popover p-1.5 text-popover-foreground shadow-(--nav-surface)",
						rest.length > 0 ? "grid w-[36rem] grid-cols-2 gap-x-1.5" : "w-72"
					)}
				>
					<MenuGroup group={first} onNavigate={onNavigate} />
					{rest.length > 0 ? (
						<div className="flex flex-col gap-1">
							{rest.map((group) => (
								<MenuGroup key={group.heading} group={group} onNavigate={onNavigate} />
							))}
						</div>
					) : null}
				</div>
			) : null}
		</div>
	);
}

export function SiteNav({ starCount, starsHref }: { starCount: number | null; starsHref: string }) {
	const [menuOpen, setMenuOpen] = useState(false);
	const [openMenu, setOpenMenu] = useState<string | null>(null);
	const headerRef = useRef<HTMLElement>(null);

	// Escape closes whatever is open; a click outside the header closes the
	// dropdown. Both match what a visitor expects from a menu regardless of how
	// it was opened.
	useEffect(() => {
		if (!menuOpen && openMenu === null) {
			return;
		}

		const onKeyDown = (event: KeyboardEvent) => {
			if (event.key === "Escape") {
				setMenuOpen(false);
				setOpenMenu(null);
			}
		};
		const onPointerDown = (event: PointerEvent) => {
			if (!headerRef.current?.contains(event.target as Node)) {
				setOpenMenu(null);
			}
		};

		document.addEventListener("keydown", onKeyDown);
		document.addEventListener("pointerdown", onPointerDown);
		return () => {
			document.removeEventListener("keydown", onKeyDown);
			document.removeEventListener("pointerdown", onPointerDown);
		};
	}, [menuOpen, openMenu]);

	const closeAll = () => {
		setMenuOpen(false);
		setOpenMenu(null);
	};

	return (
		<>
			<header
				ref={headerRef}
				className="ss-home-nav sticky top-(--fd-banner-height,0px) z-50 px-6 py-3 md:px-10"
			>
				<div aria-hidden="true" className="ss-home-nav-blur">
					<span />
					<span />
					<span />
					<span />
				</div>

				{/* Equal side columns keep the links on the bar's true center. */}
				<div className="relative z-1 mx-auto grid h-14 w-full max-w-5xl grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)] items-center gap-4 rounded-2xl bg-card pr-4 pl-3 shadow-(--nav-surface)">
					<Wordmark />

					<nav className="hidden items-center gap-1 lg:flex" aria-label="Main">
						{NAV.map((entry) =>
							isNavMenu(entry) ? (
								<MenuDropdown
									key={entry.name}
									menu={entry}
									open={openMenu === entry.name}
									onToggle={() => setOpenMenu((open) => (open === entry.name ? null : entry.name))}
									onNavigate={closeAll}
								/>
							) : (
								<Link key={entry.href} href={entry.href} className={LINK_CLASS}>
									{entry.name}
								</Link>
							)
						)}
					</nav>

					<div className="col-start-3 flex items-center gap-2 justify-self-end">
						{/* Phones keep only the toggle here; these move into the drawer. */}
						<SiteStars count={starCount} href={starsHref} className="hidden sm:inline-flex" />
						<DownloadLink className="hidden sm:inline-flex" />

						<button
							type="button"
							onClick={() => {
								setMenuOpen((open) => !open);
								setOpenMenu(null);
							}}
							aria-label={menuOpen ? "Close menu" : "Open menu"}
							aria-expanded={menuOpen}
							aria-controls={MENU_ID}
							data-state={menuOpen ? "open" : "closed"}
							className="grid size-9 place-items-center rounded-full bg-foreground text-background transition-colors duration-150 hover:bg-foreground/90 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring lg:hidden"
						>
							{/* One icon whose bars morph between menu and close, rather than
							    two icons swapped in a single frame. */}
							<MenuTwoLineIcon aria-hidden="true" className="ss-home-nav-burger size-4" />
						</button>
					</div>
				</div>

				{/* The scrim and drawer stay mounted so opening and closing can
				    animate; `inert` keeps the closed drawer out of the tab order and
				    the accessibility tree.

				    The scrim is a tap-to-dismiss ground. It is decorative: Escape and
				    the toggle both already close the menu, so a keyboard user loses
				    nothing by it being unreachable. */}
				<button
					type="button"
					aria-hidden="true"
					tabIndex={-1}
					data-state={menuOpen ? "open" : "closed"}
					className="ss-home-nav-scrim fixed inset-0 z-0 size-full cursor-default border-0 bg-black/50 p-0 backdrop-blur-sm lg:hidden"
					onClick={closeAll}
				/>

				<div
					id={MENU_ID}
					data-state={menuOpen ? "open" : "closed"}
					inert={!menuOpen}
					data-lenis-prevent
					className="ss-home-nav-drawer absolute inset-x-6 top-full z-1 mx-auto max-h-[calc(100dvh-6rem)] max-w-5xl overflow-y-auto overscroll-contain rounded-2xl bg-card p-2 shadow-(--nav-surface) md:inset-x-10 lg:hidden"
				>
					<div className="flex flex-col gap-0.5">
						{DRAWER_GROUPS.map((group, index) => (
							<div key={group.key} className="flex flex-col gap-0.5">
								{index > 0 ? <div className="my-2 border-t border-border" /> : null}
								{group.heading ? (
									<p className={cn(siteText.eyebrow, "px-3 py-1")}>{group.heading}</p>
								) : null}
								{group.links.map((link) => (
									<Link
										key={link.href}
										href={link.href}
										onClick={closeAll}
										className={DRAWER_LINK_CLASS}
									>
										{link.name}
									</Link>
								))}
							</div>
						))}
					</div>

					{/* Phones only: below `sm` the bar has room for the toggle alone, so
					    the stars and the download move in here. */}
					<div className="mt-2 flex items-center justify-between gap-3 border-t border-border px-1 pt-3 pb-1 sm:hidden">
						<SiteStars count={starCount} href={starsHref} />
						<DownloadLink onClick={closeAll} />
					</div>
				</div>
			</header>
		</>
	);
}
