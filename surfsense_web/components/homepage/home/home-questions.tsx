import { HOME_FAQ } from "@/components/homepage/home/home-content";
import { FAQJsonLd } from "@/components/seo/json-ld";

/**
 * FAQ block. Rendered as native `details`/`summary` so it needs no client
 * JavaScript, stays keyboard operable for free, and is readable by a crawler
 * with the answers in the markup rather than behind a state toggle.
 *
 * Each question is a cell in the reference's ruled grid, so an open answer
 * pushes the rule below it down rather than overlapping anything.
 *
 * Emits `FAQPage` schema from the same array, so the structured data and the
 * visible answers can never drift apart.
 */
export function HomeQuestions() {
	return (
		<section className="ss-home-rule">
			<div className="ss-home-head">
				<h2 className="ss-home-h2">Questions people ask</h2>
			</div>

			<div className="ss-home-grid">
				{HOME_FAQ.map((item) => (
					<details key={item.question} className="ss-home-faq">
						<summary className="ss-home-faq-summary ss-home-pad py-5">
							<span className="ss-home-h3">{item.question}</span>
							<span aria-hidden="true" className="ss-home-faq-marker" />
						</summary>
						<div className="ss-home-pad pb-6">
							<p className="ss-home-body max-w-prose">{item.answer}</p>
						</div>
					</details>
				))}
			</div>

			<FAQJsonLd questions={HOME_FAQ} />
		</section>
	);
}
