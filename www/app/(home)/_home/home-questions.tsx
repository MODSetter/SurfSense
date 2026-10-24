import { HOME_FAQ } from "@/app/(home)/_home/home-content";
import { HomeBadge } from "@/components/site/home-badge";
import { sectionSpacing } from "@/components/site/home-section-spacing";
import { FAQJsonLd } from "@/components/site/json-ld";
import { SiteFaqItem } from "@/components/site/site-faq-item";
import { siteText } from "@/components/site/site-text";
import { cn } from "@/components/ui/cn";

/**
 * FAQ block, one `SiteFaqItem` per question.
 *
 * Headed like the features section (a centred badge and headline). An open
 * answer pushes the rule below it down rather than overlapping anything.
 *
 * Emits `FAQPage` schema from the same array, so the structured data and the
 * visible answers can never drift apart.
 */
export function HomeQuestions() {
	return (
		<section className={sectionSpacing.foot}>
			<div className={cn("text-center", sectionSpacing.head)}>
				<HomeBadge>FAQ</HomeBadge>
				<h2 className={cn(siteText.h2, "mt-4")}>Questions people ask</h2>
			</div>

			<div className="ss-home-grid mt-10 border-t border-border lg:mt-14">
				{HOME_FAQ.map((item) => (
					<SiteFaqItem key={item.question} question={item.question}>
						<p className={siteText.body}>{item.answer}</p>
					</SiteFaqItem>
				))}
			</div>

			<FAQJsonLd questions={HOME_FAQ} />
		</section>
	);
}
