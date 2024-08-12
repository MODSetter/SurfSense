import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { ThemeProvider } from "@/components/theme-provider";
import { MainNavbar } from "@/components/homepage/NavBar";
import { Toaster } from "@/components/ui/toaster"
import { Footer } from "@/components/homepage/Footer";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
	title: "SurfSense - A Knowledge Graph Brain for World Wide Web Surfers.",
	description:
		"Save anything you see or browse on the Internet and save it to ask AI about it.",
	openGraph: {
		images: [
			{
				url: "https://surfsense.net/og-image.png",
				width: 1200,
				height: 627,
				alt: "SurfSense - A Knowledge Graph Brain for World Wide Web Surfers.",
			},
		],
	},
	twitter: {
		card: "summary_large_image",
		site: "https://surfsense.net",
		creator: "https://surfsense.net",
		title: "SurfSense - A Knowledge Graph Brain for World Wide Web Surfers.",
		description:
			"Save anything you see or browse on the Internet and save it to ask AI about it.",
		images: [
			{
				url: "https://surfsense.net/og-image.png",
				width: 1200,
				height: 627,
				alt: "SurfSense - A Knowledge Graph Brain for World Wide Web Surfers.",
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
    <html lang="en">
      <body className={inter.className}>
        <ThemeProvider
          attribute="class"
          defaultTheme="system"
          enableSystem
          disableTransitionOnChange
        >

          <div className="flex flex-col">
            <MainNavbar />
            <div className="grow">
              {children}
            </div>
            <Footer />
          </div>



          <Toaster />
        </ThemeProvider>
      </body>
    </html>
  );
}
