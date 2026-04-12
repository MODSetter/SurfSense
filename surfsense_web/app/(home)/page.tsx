import dynamic from "next/dynamic";
import { HeroSection } from "@/components/homepage/hero-section";
import { AuthRedirect } from "@/components/homepage/auth-redirect";
import { FeaturesCards } from "@/components/homepage/features-card";
import { FeaturesBentoGrid } from "@/components/homepage/features-bento-grid";

const WhySurfSense = dynamic(
	() => import("@/components/homepage/why-surfsense").then((m) => ({ default: m.WhySurfSense })),
);

const ExternalIntegrations = dynamic(() => import("@/components/homepage/integrations"));

const CTAHomepage = dynamic(
	() => import("@/components/homepage/cta").then((m) => ({ default: m.CTAHomepage })),
);

export default function HomePage() {
	return (
		<main className="min-h-screen bg-gradient-to-b from-gray-50 to-gray-100 text-gray-900 dark:from-black dark:to-gray-900 dark:text-white">
			<AuthRedirect />
			<HeroSection />
			<WhySurfSense />
			<FeaturesCards />
			<FeaturesBentoGrid />
			<ExternalIntegrations />
			<CTAHomepage />
		</main>
	);
}
