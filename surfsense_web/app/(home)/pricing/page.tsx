import type { Metadata } from "next";
import PricingBasic from "@/components/pricing/pricing-section";
import { BreadcrumbNav } from "@/components/seo/breadcrumb-nav";

export const metadata: Metadata = {
	title: "Pricing | SurfSense - Free AI Search Plans",
	description:
		"Explore SurfSense plans and pricing. Use ChatGPT, Claude AI, and any AI model free. Open source NotebookLM alternative for teams.",
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
