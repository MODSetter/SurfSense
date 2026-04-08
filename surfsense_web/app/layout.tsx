import type { Metadata, Viewport } from "next";
import "./globals.css";
import { RootProvider } from "fumadocs-ui/provider/next";
import { Roboto } from "next/font/google";
import { AnnouncementToastProvider } from "@/components/announcements/AnnouncementToastProvider";
import { GlobalLoadingProvider } from "@/components/providers/GlobalLoadingProvider";
import { I18nProvider } from "@/components/providers/I18nProvider";
import { PostHogProvider } from "@/components/providers/PostHogProvider";
import { ZeroProvider } from "@/components/providers/ZeroProvider";
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
	title: "SurfSense - Open Source NotebookLM Alternative for Teams",
	description:
		"Connect any LLM to your internal knowledge sources and chat with it in real time alongside your team. SurfSense is an open source alternative to NotebookLM, built for enterprise AI search and knowledge management.",
	keywords: [
		"enterprise ai",
		"enterprise search",
		"enterprise search software",
		"chatgpt alternative free",
		"ai enterprise search",
		"enterprise search solutions",
		"intranet search engine",
		"federated search",
		"enterprise search engine",
		"what is enterprise search",
		"enterprise knowledge management software",
		"free chatgpt alternative",
		"chatgpt free alternative",
		"best enterprise search software",
		"enterprise ai search",
		"enterprise knowledge management",
		"federated search engine",
		"enterprise knowledge management system",
		"free claude ai",
		"what is enterprise search engine marketing",
		"ai driven enterprise search",
		"free alternative to chatgpt",
		"free claude",
		"alternative to chatgpt free",
		"free ai chatbot like chatgpt",
		"enterprise search software comparison",
		"apps like chatgpt for free",
		"free chatgpt no login",
		"free ai chatbots like chatgpt",
		"enterprise document search",
		"search engine for intranet",
		"free chatgpt without login",
		"unified search engine",
		"chatgpt alternative online free",
		"free chatgpt alternative app",
		"free chatgpt alternative with image upload",
		"best free alternative to chatgpt",
		"enterprise search engine open source",
		"open source notebooklm alternative",
		"notebooklm alternative for teams",
		"SurfSense",
	],
	openGraph: {
		title: "SurfSense - Open Source NotebookLM Alternative for Teams",
		description:
			"Connect any LLM to your internal knowledge sources and chat with it in real time alongside your team. Open source enterprise AI search and knowledge management.",
		url: "https://surfsense.com",
		siteName: "SurfSense",
		type: "website",
		images: [
			{
				url: "https://surfsense.com/og-image.png",
				width: 1200,
				height: 630,
				alt: "SurfSense - Open Source NotebookLM Alternative for Teams",
			},
		],
		locale: "en_US",
	},
	twitter: {
		card: "summary_large_image",
		title: "SurfSense - Open Source NotebookLM Alternative for Teams",
		description:
			"Connect any LLM to your internal knowledge sources and chat with it in real time alongside your team. Open source enterprise AI search and knowledge management.",
		creator: "https://surfsense.com",
		site: "https://surfsense.com",
		images: [
			{
				url: "https://surfsense.com/og-image-twitter.png",
				width: 1200,
				height: 630,
				alt: "SurfSense - Open Source NotebookLM Alternative for Teams",
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
