import type { ReactNode } from "react";
import { siteText } from "@/components/site/site-text";

/**
 * One question in a marketing FAQ.
 *
 * Native details/summary: no client JS, keyboard operable, and the answer stays
 * in the markup for crawlers. The open/close motion and the plus-to-cross
 * marker are `.ss-home-faq*` in `app/(home)/home.css`.
 */
export function SiteFaqItem({ question, children }: { question: string; children: ReactNode }) {
	return (
		<details className="ss-home-faq">
			<summary className="flex cursor-pointer list-none items-center justify-between gap-4 py-5 font-medium transition-colors duration-100 ease-out hover:text-primary focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-ring [&::-webkit-details-marker]:hidden">
				<span className={siteText.h3}>{question}</span>
				<span aria-hidden="true" className="ss-home-faq-marker" />
			</summary>
			<div className="pb-6">{children}</div>
		</details>
	);
}
