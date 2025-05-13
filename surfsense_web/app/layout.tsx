import type { Metadata } from "next";
import "./globals.css";
import { cn } from "@/lib/utils";
import { Roboto } from "next/font/google";

import { Toaster } from "@/components/ui/sonner";
import { ThemeProvider } from "@/components/theme/theme-provider";
import { RootProvider } from 'fumadocs-ui/provider';

const roboto = Roboto({ 
  subsets: ["latin"],
  weight: ["400", "500", "700"],
  display: 'swap',
  variable: '--font-roboto',
});

export const metadata: Metadata = {
  title: "SurfSense – Customizable AI Research & Knowledge Management Assistant",
  description:
    "SurfSense is an AI-powered research assistant that integrates with tools like Notion, GitHub, Slack, and more to help you efficiently manage, search, and chat with your documents. Generate podcasts, perform hybrid search, and unlock insights from your knowledge base.",
  keywords: [
    "SurfSense",
    "AI research assistant",
    "AI knowledge management",
    "AI document assistant",
    "customizable AI assistant",
    "notion integration",
    "slack integration",
    "github integration",
    "hybrid search",
    "vector search",
    "RAG",
    "LangChain",
    "FastAPI",
    "LLM apps",
    "AI document chat",
    "knowledge management AI",
    "AI-powered document search",
    "personal AI assistant",
    "AI research tools",
    "AI podcast generator",
    "AI knowledge base",
    "AI document assistant tools",
    "AI-powered search assistant",
  ],
  openGraph: {
    title: "SurfSense – AI Research & Knowledge Management Assistant",
    description:
      "Connect your documents and tools like Notion, Slack, GitHub, and more to your private AI assistant. SurfSense offers powerful search, document chat, podcast generation, and RAG APIs to enhance your workflow.",
    url: "https://surfsense.net",
    siteName: "SurfSense",
    type: "website",
    images: [
      {
        url: "https://surfsense.net/og-image.png",
        width: 1200,
        height: 630,
        alt: "SurfSense AI Research Assistant",
      },
    ],
    locale: "en_US",
  },
  twitter: {
    card: "summary_large_image",
    title: "SurfSense – AI Assistant for Research & Knowledge Management",
    description:
      "Have your own NotebookLM or Perplexity, but better. SurfSense connects external tools, allows chat with your documents, and generates fast, high-quality podcasts.",
    creator: "https://surfsense.net",
    site: "https://surfsense.net",
    images: [
      {
        url: "https://surfsense.net/og-image-twitter.png",
        width: 1200,
        height: 630,
        alt: "SurfSense AI Assistant Preview",
      },
    ],
  }
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
          <RootProvider>
            {children}
            <Toaster />
          </RootProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
