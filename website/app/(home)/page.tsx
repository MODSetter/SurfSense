import type { Metadata } from "next";
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
 * Title, description and heading order come from the `/` landing brief in
 * `plans/community-local/seo/02-page-briefs.md` (B6). The headings carry demand
 * phrases and their order is load-bearing — see `home-content.ts`.
 *
 * A server component. Most sections are static and the FAQ uses native
 * details/summary; the client exceptions are the claims tabs and the formats
 * row's hover spotlight (see `home-sections.tsx`).
 */

export const metadata: Metadata = {
	title: "Air-Gapped, Open Source NotebookLM Alternative | SurfSense",
	description:
		"A private, self-hosted NotebookLM alternative that runs air-gapped on your own machine. Your documents, your model keys, no cloud, no account.",
	alternates: { canonical: "https://www.surfsense.com" },
	openGraph: {
		title: "Air-Gapped, Open Source NotebookLM Alternative | SurfSense",
		description:
			"A private, self-hosted NotebookLM alternative that runs air-gapped on your own machine. Your documents, your model keys, no cloud, no account.",
		url: "https://www.surfsense.com",
		siteName: "SurfSense",
		type: "website",
		images: [
			{
				url: "/og-image.png",
				width: 1200,
				height: 630,
				alt: "SurfSense, the air-gapped open-source NotebookLM alternative",
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
		"A private, self-hosted NotebookLM alternative that runs air-gapped on your own machine.",
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
