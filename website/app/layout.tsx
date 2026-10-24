import type { Metadata, Viewport } from "next";
import "./globals.css";
import { RootProvider } from "fumadocs-ui/provider/next";
import { Roboto } from "next/font/google";
import { PostHogProvider } from "@/components/providers/PostHogProvider";
import {
	OrganizationJsonLd,
	SoftwareApplicationJsonLd,
	WebSiteJsonLd,
} from "@/components/seo/json-ld";
import { GlobalAnnouncement } from "@/components/site/global-announcement";
import { Toaster } from "@/components/ui/sonner";
import { cn } from "@/lib/utils";

const roboto = Roboto({
	subsets: ["latin"],
	weight: ["400", "500", "700"],
	// "optional": use Roboto only if it's ready almost immediately; otherwise
	// keep the fallback for this page view. "swap" (the default) always swaps
	// in Roboto once it arrives, which produced a visible font jump on load.
	display: "optional",
	variable: "--font-roboto",
});

/**
 * Viewport configuration for mobile keyboard handling.
 * - interactiveWidget: 'resizes-content' tells mobile browsers (especially Chrome Android)
 *   to resize the CSS layout viewport when the virtual keyboard opens, so sticky elements
 *   (like the chat input bar) stay visible above the keyboard.
 * - viewportFit: 'cover' enables env(safe-area-inset-*) for notched/home-indicator devices.
 */
export const viewport: Viewport = {
	width: "device-width",
	initialScale: 1,
	viewportFit: "cover",
	interactiveWidget: "resizes-content",
};

export const metadata: Metadata = {
	metadataBase: new URL("https://www.surfsense.com"),
	alternates: {
		canonical: "https://www.surfsense.com",
	},
	title: "SurfSense: Open-Source NotebookLM Alternative & Web Research",
	description:
		"The open-source NotebookLM alternative. Research the open web with live data from Reddit, YouTube, TikTok, Indeed & more, through one platform, API, or MCP server.",
	keywords: [
		"open web research platform",
		"web research for AI agents",
		"live web data for agents",
		"web scraping API",
		"reddit scraper api",
		"youtube scraper api",
		"deep research agent",
		"mcp server",
		"agent harness",
		"open source NotebookLM alternative",
		"SurfSense",
	],
	openGraph: {
		title: "SurfSense - NotebookLM for Open Web Research",
		description:
			"The open-source NotebookLM alternative. Research the open web with live data from Reddit, YouTube, TikTok, Indeed & more, through one platform, API, or MCP server.",
		url: "https://www.surfsense.com",
		siteName: "SurfSense",
		type: "website",
		images: [
			{
				url: "/og-image.png",
				width: 1200,
				height: 630,
				alt: "SurfSense, the air-gapped open-source NotebookLM alternative",
			},
		],
		locale: "en_US",
	},
	twitter: {
		card: "summary_large_image",
		title: "SurfSense - NotebookLM for Open Web Research",
		description:
			"The open-source NotebookLM alternative. Research the open web with live data from Reddit, YouTube, TikTok, Indeed & more, through one platform, API, or MCP server.",
		creator: "@SurfSenseAI",
		site: "@SurfSenseAI",
		images: [
			{
				url: "/og-image.png",
				width: 1200,
				height: 630,
				alt: "SurfSense, the air-gapped open-source NotebookLM alternative",
			},
		],
	},
};

export default function RootLayout({
	children,
}: Readonly<{
	children: React.ReactNode;
}>) {
	return (
		<html lang="en" suppressHydrationWarning>
			<head>
				<link rel="preconnect" href="https://api.github.com" />
				<OrganizationJsonLd />
				<WebSiteJsonLd />
				<SoftwareApplicationJsonLd />
			</head>
			<body
				className={cn(roboto.className, roboto.variable, "bg-background antialiased h-full w-full")}
			>
				<PostHogProvider>
					{/* Light by default. The marketing pages keep their own light palette
					    in `.ss-home` whatever this resolves to. A fresh storageKey, so a
					    "dark" the hosted app's old toggle saved under "theme" is ignored. */}
					<RootProvider
						theme={{
							defaultTheme: "light",
							enableSystem: false,
							storageKey: "surfsense-site-theme",
						}}
					>
						<GlobalAnnouncement />
						{children}
						<Toaster />
					</RootProvider>
				</PostHogProvider>
			</body>
		</html>
	);
}
