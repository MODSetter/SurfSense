"use client";

import { useTranslations } from "next-intl";
import { Pricing } from "@/components/pricing";

function PricingBasic() {
	const t = useTranslations('pricing');
	
	const demoPlans = [
		{
			name: t('community_name'),
			price: "0",
			yearlyPrice: "0",
			period: t('forever'),
			features: [
				t('feature_llms'),
				t('feature_ollama'),
				t('feature_embeddings'),
				t('feature_files'),
				t('feature_podcasts'),
				t('feature_sources'),
				t('feature_extension'),
				t('upcoming_mindmaps'),
				t('upcoming_notes'),
			],
			description: t('community_desc'),
			buttonText: t('get_started'),
			href: "/docs",
			isPopular: true,
		},
		{
			name: t('enterprise_name'),
			price: t('contact_us'),
			yearlyPrice: t('contact_us'),
			period: "",
			features: [
				t('everything_community'),
				t('priority_support'),
				t('access_controls'),
				t('collaboration'),
				t('video_gen'),
				t('advanced_security'),
			],
			description: t('enterprise_desc'),
			buttonText: t('contact_sales'),
			href: "/contact",
			isPopular: false,
		},
	];

	return (
		<Pricing plans={demoPlans} title={t('title')} description={t('subtitle')} />
	);
}

export default PricingBasic;
