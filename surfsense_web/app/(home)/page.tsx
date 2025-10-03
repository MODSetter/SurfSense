"use client";

import { CTAHomepage } from "@/components/homepage/cta";
import { FeaturesBentoGrid } from "@/components/homepage/features-bento-grid";
import { FeaturesCards } from "@/components/homepage/features-card";
import { Footer } from "@/components/homepage/footer";
import { HeroSection } from "@/components/homepage/hero-section";
import ExternalIntegrations from "@/components/homepage/integrations";
import { Navbar } from "@/components/homepage/navbar";

export default function HomePage() {
	return (
		<main className="min-h-screen bg-gradient-to-b from-gray-50 to-gray-100 text-gray-900 dark:from-black dark:to-gray-900 dark:text-white">
			<HeroSection />
			<FeaturesCards />
			<FeaturesBentoGrid />
			<ExternalIntegrations />
			<CTAHomepage />
		</main>
	);
}
