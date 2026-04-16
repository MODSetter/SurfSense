import type { Metadata, Viewport } from "next";
import "./globals.css";
import { RootProvider } from "fumadocs-ui/provider/next";
import { Roboto } from "next/font/google";
import { AnnouncementToastProvider } from "@/components/announcements/AnnouncementToastProvider";
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
import { ReactQueryClientProvider } from "@/lib/query-client/query-client.provider";
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
	metadataBase: new URL("https://surfsense.com"),
	alternates: {
		canonical: "https://surfsense.com",
	},
	title: "SurfSense - NotebookLM Alternative | Free ChatGPT & Claude AI",
	description:
		"Open source NotebookLM alternative for teams with no data limits. Use ChatGPT, Claude AI, and any AI model for free.",
	keywords: [
		"chatgpt online",
		"online chatgpt",
		"chat gpt free",
		"chatgpt free",
		"free chatgpt",
		"free chat gpt",
		"chatgpt no login",
		"chatgpt online free",
		"chatgpt free online",
		"chatgpt without login",
		"free chatgpt without login",
		"free chatgpt no login",
		"chatgpt for free",
		"claude ai free",
		"claude free",
		"free claude ai",
		"free claude",
		"chatgpt alternative free",
		"free chatgpt alternative",
		"free alternative to chatgpt",
		"alternative to chatgpt free",
		"chatgpt alternative online free",
		"ai like chatgpt",
		"sites like chatgpt",
		"free ai chatbot like chatgpt",
		"apps like chatgpt for free",
		"free ai chatbots like chatgpt",
		"best free alternative to chatgpt",
		"free chatgpt alternative app",
		"free chatgpt alternative with image upload",
		"free ai apps",
		"ai with no restrictions",
		"notebooklm alternative",
		"notebooklm alternative for teams",
		"open source notebooklm alternative",
		"SurfSense",
	],
	openGraph: {
		title: "SurfSense - NotebookLM Alternative | Free ChatGPT & Claude AI",
		description:
			"Open source NotebookLM alternative for teams with no data limits. Use ChatGPT, Claude, and any AI model for free.",
		url: "https://surfsense.com",
		siteName: "SurfSense",
		type: "website",
		images: [
			{
				url: "/og-image.png",
				width: 1200,
				height: 630,
				alt: "SurfSense - Open Source NotebookLM Alternative with Free ChatGPT and Claude AI",
			},
		],
		locale: "en_US",
	},
	twitter: {
		card: "summary_large_image",
		title: "SurfSense - NotebookLM Alternative | Free ChatGPT & Claude AI",
		description:
			"Open source NotebookLM alternative for teams with no data limits. Use ChatGPT, Claude AI, and any AI model for free.",
		creator: "@SurfSenseAI",
		site: "@SurfSenseAI",
		images: [
			{
				url: "/og-image-twitter.png",
				width: 1200,
				height: 630,
				alt: "SurfSense - Open Source NotebookLM Alternative with Free ChatGPT and Claude AI",
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
		<html lang="en" suppressHydrationWarning>
			<head>
				<link rel="preconnect" href="https://api.github.com" />
				<OrganizationJsonLd />
				<WebSiteJsonLd />
				<SoftwareApplicationJsonLd />
			</head>
			<body className={cn(roboto.className, "bg-white dark:bg-black antialiased h-full w-full ")}>
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
											<ZeroProvider>
												<GlobalLoadingProvider>{children}</GlobalLoadingProvider>
											</ZeroProvider>
										</ReactQueryClientProvider>
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
