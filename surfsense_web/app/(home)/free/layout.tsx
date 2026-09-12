import type { ReactNode } from "react";
import { AdSenseScript } from "@/components/ads/adsense-script";

/**
 * Wraps the /free hub and all /free/[model_slug] subpages. Mounting
 * <AdSenseScript /> here loads adsbygoogle.js across the entire /free route
 * tree, which is what powers both the manual <AdUnit /> slots and AdSense
 * Auto ads. Because the script lives here (not in the root layout), Auto ads
 * is naturally scoped to /free and its subpages only.
 */
export default function FreeSectionLayout({ children }: { children: ReactNode }) {
	return (
		<>
			<AdSenseScript />
			{children}
		</>
	);
}
