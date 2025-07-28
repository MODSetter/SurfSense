"use client";

import { Footer } from "@/components/Footer";
import { ModernHeroWithGradients } from "@/components/ModernHeroWithGradients";
import { Navbar } from "@/components/Navbar";

export default function HomePage() {
	return (
		<main className="min-h-screen bg-gradient-to-b from-gray-50 to-gray-100 text-gray-900 dark:from-black dark:to-gray-900 dark:text-white">
			<Navbar />
			<ModernHeroWithGradients />
			<Footer />
		</main>
	);
}
