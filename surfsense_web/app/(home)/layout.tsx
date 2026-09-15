"use client";

import { usePathname } from "next/navigation";
import { FooterNew } from "@/components/homepage/footer-new";
import { GlobalAnnouncement } from "@/components/homepage/global-announcement";
import { HomeFooter } from "@/components/homepage/home/home-footer";
import { HomeNav } from "@/components/homepage/home/home-nav";
import { Navbar } from "@/components/homepage/navbar";
import { cn } from "@/lib/utils";

export default function HomePageLayout({ children }: { children: React.ReactNode }) {
	const pathname = usePathname();
	const isAuthPage = pathname === "/login" || pathname === "/register";
	const isFreeModelChat = /^\/free\/[^/]+$/.test(pathname);

	if (isFreeModelChat) {
		return <>{children}</>;
	}

	// The landing page owns its full shell: it pins the dark palette and paints
	// its own background, so the shared gradient would only show as a light
	// frame around it.
	const isLanding = pathname === "/";

	return (
		<main
			className={cn(
				"min-h-screen",
				// `overflow-x: hidden` turns this element into a scroll container, and
				// a sticky child then sticks inside *it* rather than to the viewport —
				// the landing navigation would scroll away. The landing page clips its
				// own overflowing decoration instead, so it does not need this.
				!isLanding && "overflow-x-hidden",
				// `ss-home` is declared in the landing page's own stylesheet. Applying
				// it here rather than only inside the page means the shared Navbar and
				// FooterNew sit inside the dark scope too, instead of rendering light
				// chrome around a dark page.
				isLanding
					? "ss-home"
					: "bg-linear-to-b from-gray-50 to-gray-100 text-gray-900 dark:from-black dark:to-gray-900 dark:text-white"
			)}
		>
			<GlobalAnnouncement />
			{isLanding ? (
				// The landing page uses its own navigation and footer so that the
				// shared ones can keep serving every other route under (home)
				// unchanged. The footer is part of the page rather than chrome around
				// it: it sits inside the same ruled column as every section above, so
				// the side borders run unbroken from the hero to the wordmark.
				<>
					<HomeNav />
					<div className="ss-home-shell">
						{children}
						<HomeFooter />
					</div>
				</>
			) : (
				<>
					<Navbar />
					{children}
					{!isAuthPage ? <FooterNew /> : null}
				</>
			)}
		</main>
	);
}
