import { AuthRedirect } from "@/components/homepage/auth-redirect";
import { CommunityStrip } from "@/components/homepage/community-strip";
import { CompareTable } from "@/components/homepage/compare-table";
import { ConnectorGrid } from "@/components/homepage/connector-grid";
import { HeroSection } from "@/components/homepage/hero-section";
import { HomeFaq } from "@/components/homepage/home-faq";
import { LogoCloud } from "@/components/homepage/logo-cloud";
import { SocialProof } from "@/components/homepage/social-proof";

export default function HomePage() {
	return (
		<div className="min-h-screen bg-linear-to-b from-gray-50 to-gray-100 text-gray-900 dark:from-black dark:to-gray-900 dark:text-white">
			<AuthRedirect />
			<HeroSection />
			<LogoCloud />
			<SocialProof />
			<ConnectorGrid />
			<CompareTable />
			<HomeFaq />
			<CommunityStrip />
		</div>
	);
}
