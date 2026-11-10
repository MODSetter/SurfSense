import type { Metadata } from "next";
import { HomeAudiences } from "@/app/(home)/_home/home-audiences";
import { HomeCompare } from "@/app/(home)/_home/home-compare/home-compare";
import { HomeConfidential } from "@/app/(home)/_home/home-confidential/home-confidential";
import { HomeFeatures } from "@/app/(home)/_home/home-features/home-features";
import { HomeFormats } from "@/app/(home)/_home/home-formats/home-formats";
import { HomeLogos } from "@/app/(home)/_home/home-logos";
import { HomePillars } from "@/app/(home)/_home/home-pillars/home-pillars";
import { HomeQuestions } from "@/app/(home)/_home/home-questions";
import { HomeHero, HomeOnYourMachine } from "@/app/(home)/_home/home-sections";
import { JsonLd } from "@/components/site/json-ld";

/**
 * Landing page.
 *
 * Heading order comes from the `/` landing brief in
 * `plans/community-local/seo/02-page-briefs.md` (B6). The headings carry demand
 * phrases and their order is load-bearing — see `home-content.ts`. The title, the
 * description and the H1 lead with private AI for confidential documents since
 * `plans/community-local/seo/09-audience-pages.md` (9 Nov 2026), with NotebookLM as the
 * familiar hook below them.
 *
 * A server component. Most sections are static and the FAQ uses native
 * details/summary; the client exceptions are the claims tabs and the formats
 * row's hover spotlight (see `home-sections.tsx`).
 */

export const metadata: Metadata = {
	title: "Air-Gapped Private AI for Confidential Documents | SurfSense",
	description:
		"SurfSense is free, open-source private AI that runs on your computer: a NotebookLM-style notebook for files you can't upload. No account, works offline.",
	alternates: { canonical: "https://www.surfsense.com" },
	openGraph: {
		title: "Air-Gapped Private AI for Confidential Documents | SurfSense",
		description:
			"SurfSense is free, open-source private AI that runs on your computer: a NotebookLM-style notebook for files you can't upload. No account, works offline.",
		url: "https://www.surfsense.com",
		siteName: "SurfSense",
		type: "website",
		images: [
			{
				url: "/og-image.png",
				width: 1200,
				height: 630,
				alt: "SurfSense, air-gapped private AI for confidential documents",
			},
		],
	},
};

/** `SoftwareApplication` with an honest zero price — the app is free. */
const APPLICATION_SCHEMA = {
	"@context": "https://schema.org",
	"@type": "SoftwareApplication",
	name: "SurfSense",
	applicationCategory: "productivity",
	operatingSystem: "Windows, macOS, Linux",
	description:
		"Free, open-source private AI for confidential documents: a NotebookLM-style notebook that runs on your own computer, air-gapped with a local model.",
	url: "https://www.surfsense.com",
	isAccessibleForFree: true,
	offers: {
		"@type": "Offer",
		price: 0,
		priceCurrency: "USD",
	},
};

export default function HomePage() {
	return (
		// The palette, the ruled column, the navigation and the footer all come
		// from app/(home)/layout.tsx, which renders them for every site-design route.
		<>
			<JsonLd data={APPLICATION_SCHEMA} />
			<HomeHero />
			<HomeLogos />
			<HomeAudiences />
			<HomeOnYourMachine />
			<HomePillars />
			<HomeCompare />
			<HomeFeatures />
			<HomeConfidential />
			<HomeFormats />
			<HomeQuestions />
		</>
	);
}
