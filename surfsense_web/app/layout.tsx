import type { Metadata, Viewport } from "next";
import "./globals.css";
import { RootProvider } from "fumadocs-ui/provider/next";
import { Roboto } from "next/font/google";
import Script from "next/script";
import { AnnouncementToastProvider } from "@/components/announcements/AnnouncementToastProvider";
import { DesktopUpdateToast } from "@/components/desktop/desktop-update-toast";
import { AuthCutoverPurge } from "@/components/providers/AuthCutoverPurge";
import { GlobalLoadingProvider } from "@/components/providers/GlobalLoadingProvider";
import { I18nProvider } from "@/components/providers/I18nProvider";
import { PostHogProvider } from "@/components/providers/PostHogProvider";
import { ZeroProvider } from "@/components/providers/ZeroProvider";
import {
	OrganizationJsonLd,
	SoftwareApplicationJsonLd,
	WebSiteJsonLd,
} from "@/components/seo/json-ld";
import { ThemeProvider } from "@/components/theme/theme-provider";
import { Toaster } from "@/components/ui/sonner";
import { LocaleProvider } from "@/contexts/LocaleContext";
import { PlatformProvider } from "@/contexts/platform-context";
import { BUILD_TIME_AUTH_TYPE } from "@/lib/env-config";
import { ReactQueryClientProvider } from "@/lib/query-client/query-client.provider";
import { getRuntimeAuthInitScript, resolveRuntimeAuthUiMode } from "@/lib/runtime-auth-config";
import { cn } from "@/lib/utils";

const roboto = Roboto({
	subsets: ["latin"],
	weight: ["400", "500", "700"],
	display: "swap",
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
	title: "SurfSense - Competitive Intelligence Platform for AI Agents",
	description:
		"SurfSense is an open-source competitive intelligence platform. Your AI agents monitor competitors, track rankings, and listen to your market through one API or MCP server.",
	keywords: [
		"competitive intelligence platform",
		"competitive intelligence software",
		"market intelligence tools",
		"competitor monitoring",
		"competitor price monitoring",
		"brand monitoring",
		"rank tracking",
		"social listening",
		"mcp server",
		"agent harness",
		"open source competitive intelligence",
		"SurfSense",
	],
	openGraph: {
		title: "SurfSense - Competitive Intelligence Platform for AI Agents",
		description:
			"SurfSense is an open-source competitive intelligence platform. Your AI agents monitor competitors, track rankings, and listen to your market through one API or MCP server.",
		url: "https://www.surfsense.com",
		siteName: "SurfSense",
		type: "website",
		images: [
			{
				url: "/og-image.png",
				width: 1200,
				height: 630,
				alt: "SurfSense - Competitive Intelligence Platform for AI Agents",
			},
		],
		locale: "en_US",
	},
	twitter: {
		card: "summary_large_image",
		title: "SurfSense - Competitive Intelligence Platform for AI Agents",
		description:
			"SurfSense is an open-source competitive intelligence platform. Your AI agents monitor competitors, track rankings, and listen to your market through one API or MCP server.",
		creator: "@SurfSenseAI",
		site: "@SurfSenseAI",
		images: [
			{
				url: "/og-image-twitter.png",
				width: 1200,
				height: 630,
				alt: "SurfSense - Competitive Intelligence Platform for AI Agents",
			},
		],
	},
};

export default function RootLayout({
	children,
}: Readonly<{
	children: React.ReactNode;
}>) {
	// Using client-side i18n
	// Language can be switched dynamically through LanguageSwitcher component
	// Locale state is managed by LocaleContext and persisted in localStorage
	return (
		<html
			lang="en"
			data-surfsense-auth-type={resolveRuntimeAuthUiMode(BUILD_TIME_AUTH_TYPE)}
			suppressHydrationWarning
		>
			<head>
				<Script id="surfsense-runtime-auth-init" strategy="beforeInteractive">
					{getRuntimeAuthInitScript(BUILD_TIME_AUTH_TYPE)}
				</Script>
				<link rel="preconnect" href="https://api.github.com" />
				<OrganizationJsonLd />
				<WebSiteJsonLd />
				<SoftwareApplicationJsonLd />
			</head>
			<body className={cn(roboto.className, "bg-main-panel antialiased h-full w-full ")}>
				<PostHogProvider>
					<LocaleProvider>
						<I18nProvider>
							<ThemeProvider
								attribute="class"
								enableSystem
								disableTransitionOnChange
								defaultTheme="system"
							>
								<PlatformProvider>
									<RootProvider>
										<ReactQueryClientProvider>
											<AuthCutoverPurge />
											<ZeroProvider>
												<GlobalLoadingProvider>{children}</GlobalLoadingProvider>
											</ZeroProvider>
										</ReactQueryClientProvider>
										<DesktopUpdateToast />
										<Toaster />
										<AnnouncementToastProvider />
									</RootProvider>
								</PlatformProvider>
							</ThemeProvider>
						</I18nProvider>
					</LocaleProvider>
				</PostHogProvider>
			</body>
		</html>
	);
}
