import type { Metadata } from "next";
import "./globals.css";
import { cn } from "@/lib/utils";
import { Roboto } from "next/font/google";

import { Toaster } from "@/components/ui/sonner";
import { ThemeProvider } from "@/components/theme/theme-provider";

const roboto = Roboto({ 
  subsets: ["latin"],
  weight: ["400", "500", "700"],
  display: 'swap',
  variable: '--font-roboto',
});

export const metadata: Metadata = {
	title: "SurfSense - A Personal NotebookLM and Perplexity-like AI Assistant for Everyone.",
	description:
		"Have your own private NotebookLM and Perplexity with better integrations.",
	openGraph: {
		images: [
			{
				url: "https://surfsense.net/og-image.png",
				width: 1200,
				height: 630,
				alt: "SurfSense - A Personal NotebookLM and Perplexity-like AI Assistant for Everyone.",
			},
		],
	},
	twitter: {
		card: "summary_large_image",
		site: "https://surfsense.net",
		creator: "https://surfsense.net",
		title: "SurfSense - A Personal NotebookLM and Perplexity-like AI Assistant for Everyone.",
		description:
			"Have your own private NotebookLM and Perplexity with better integrations.",
		images: [
			{
				url: "https://surfsense.net/og-image.png",
				width: 1200,
				height: 630,
				alt: "SurfSense - A Personal NotebookLM and Perplexity-like AI Assistant for Everyone.",
			},
		],
	},
};

export default async function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body
        className={cn(
          roboto.className,
          "bg-white dark:bg-black antialiased h-full w-full"
        )}
      >
        <ThemeProvider
          attribute="class"
          enableSystem
          disableTransitionOnChange
          defaultTheme="light"
        >
          {children}
          <Toaster />
        </ThemeProvider>
      </body>
    </html>
  );
}
