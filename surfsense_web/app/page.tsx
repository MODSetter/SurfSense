"use client";

import { Footer } from "@/components/Footer";
import { CTAHomepage } from "@/components/homepage/cta";
import { FeaturesBentoGrid } from "@/components/homepage/features-bento-grid";
import { ModernHeroWithGradients } from "@/components/homepage/ModernHeroWithGradients";
import { Navbar } from "@/components/Navbar";

export default function HomePage() {
	return (
		<main className="min-h-screen bg-gradient-to-b from-gray-50 to-gray-100 text-gray-900 dark:from-black dark:to-gray-900 dark:text-white">
			<Navbar />
			<ModernHeroWithGradients />
			<FeaturesBentoGrid />
			<CTAHomepage />
			<Footer />
		</main>
	);
}
