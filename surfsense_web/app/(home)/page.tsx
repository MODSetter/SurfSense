"use client";

import dynamic from "next/dynamic";
import { HeroSection } from "@/components/homepage/hero-section";

const FeaturesCards = dynamic(
	() => import("@/components/homepage/features-card").then((m) => ({ default: m.FeaturesCards })),
	{ ssr: false }
);

const FeaturesBentoGrid = dynamic(
	() =>
		import("@/components/homepage/features-bento-grid").then((m) => ({
			default: m.FeaturesBentoGrid,
		})),
	{ ssr: false }
);

const ExternalIntegrations = dynamic(() => import("@/components/homepage/integrations"), {
	ssr: false,
});

const CTAHomepage = dynamic(
	() => import("@/components/homepage/cta").then((m) => ({ default: m.CTAHomepage })),
	{ ssr: false }
);

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
