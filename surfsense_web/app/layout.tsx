import type { Metadata, Viewport } from "next";
import "./globals.css";
import { Roboto } from "next/font/google";
import Script from "next/script";
import { DesktopUpdateToast } from "@/components/desktop/desktop-update-toast";
import { DesktopAppBanner } from "@/components/desktop-app-banner/desktop-app-banner";
import { AuthCutoverPurge } from "@/components/providers/AuthCutoverPurge";
import { GlobalLoadingProvider } from "@/components/providers/GlobalLoadingProvider";
import { I18nProvider } from "@/components/providers/I18nProvider";
import { PostHogProvider } from "@/components/providers/PostHogProvider";
import { ZeroProvider } from "@/components/providers/ZeroProvider";
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
	title: "SurfSense",
	description: "Self-hosted SurfSense.",
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
			</head>
			<body
				className={cn(roboto.className, roboto.variable, "bg-background antialiased h-full w-full")}
			>
				<PostHogProvider>
					<LocaleProvider>
						<I18nProvider>
							{/* Dark until the user picks Light or System in the sidebar. */}
							<ThemeProvider
								attribute="class"
								enableSystem
								disableTransitionOnChange
								defaultTheme="dark"
								storageKey="surfsense-theme"
							>
								<PlatformProvider>
									<DesktopAppBanner />
									<ReactQueryClientProvider>
										<AuthCutoverPurge />
										<ZeroProvider>
											<GlobalLoadingProvider>{children}</GlobalLoadingProvider>
										</ZeroProvider>
									</ReactQueryClientProvider>
									<DesktopUpdateToast />
									<Toaster />
								</PlatformProvider>
							</ThemeProvider>
						</I18nProvider>
					</LocaleProvider>
				</PostHogProvider>
			</body>
		</html>
	);
}
