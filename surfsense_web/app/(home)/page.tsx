"use client";

import { Footer } from "@/components/homepage/footer";
import { HeroSection } from "@/components/homepage/hero-section";

export default function HomePage() {
	return (
		<main className="min-h-screen bg-gradient-to-b from-gray-50 to-gray-100 text-gray-900 dark:from-black dark:to-gray-900 dark:text-white">
			<HeroSection />
			<Footer />
		</main>
	);
}
