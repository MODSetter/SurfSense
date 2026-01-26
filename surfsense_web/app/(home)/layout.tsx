"use client";

import { usePathname } from "next/navigation";
import { FooterNew } from "@/components/homepage/footer-new";
import { Navbar } from "@/components/homepage/navbar";

export default function HomePageLayout({ children }: { children: React.ReactNode }) {
	const pathname = usePathname();
	const isAuthPage = pathname === "/login" || pathname === "/register";

	return (
		<main className="min-h-screen bg-linear-to-b from-gray-50 to-gray-100 text-gray-900 dark:from-black dark:to-gray-900 dark:text-white overflow-x-hidden">
			<Navbar />
			{children}
			{!isAuthPage && <FooterNew />}
		</main>
	);
}
