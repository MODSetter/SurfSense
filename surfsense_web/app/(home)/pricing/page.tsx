import type { Metadata } from "next";
import PricingBasic from "@/components/pricing/pricing-section";
import { BreadcrumbNav } from "@/components/seo/breadcrumb-nav";

export const metadata: Metadata = {
	title: "Pricing | SurfSense - Free AI Search Plans",
	description:
		"Explore SurfSense plans and pricing. Start free with 500 pages & $5 in premium credits. Use ChatGPT, Claude AI, and premium AI models. Pay as you go at provider cost.",
	alternates: {
		canonical: "https://surfsense.com/pricing",
	},
};

const page = () => {
	return (
		<div>
			<div className="container mx-auto pt-24 px-4">
				<BreadcrumbNav
					items={[
						{ name: "Home", href: "/" },
						{ name: "Pricing", href: "/pricing" },
					]}
				/>
			</div>
			<PricingBasic />
		</div>
	);
};

export default page;
