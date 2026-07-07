import { AuthRedirect } from "@/components/homepage/auth-redirect";
import { CommunityStrip } from "@/components/homepage/community-strip";
import { CompareTable } from "@/components/homepage/compare-table";
import { ConnectorGrid } from "@/components/homepage/connector-grid";
import { HeroSection } from "@/components/homepage/hero-section";
import { HomeFaq } from "@/components/homepage/home-faq";
import { HowItWorks } from "@/components/homepage/how-it-works";
import { PersonaPaths } from "@/components/homepage/persona-paths";
import { UseCasesRow } from "@/components/homepage/use-cases";

export default function HomePage() {
	return (
		<div className="min-h-screen bg-linear-to-b from-gray-50 to-gray-100 text-gray-900 dark:from-black dark:to-gray-900 dark:text-white">
			<AuthRedirect />
			<HeroSection />
			<PersonaPaths />
			<ConnectorGrid />
			<HowItWorks />
			<UseCasesRow />
			<CompareTable />
			<HomeFaq />
			<CommunityStrip />
		</div>
	);
}
