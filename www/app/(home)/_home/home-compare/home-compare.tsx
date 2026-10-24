import { CompareHeadToHead } from "@/app/(home)/_home/home-compare/compare-head-to-head";
import { CompareTable } from "@/app/(home)/_home/home-compare/compare-table";
import { HomeBadge } from "@/components/site/home-badge";
import { sectionSpacing } from "@/components/site/home-section-spacing";
import { siteText } from "@/components/site/site-text";
import { cn } from "@/components/ui/cn";

/**
 * Not one of the brief's eight H2s, so the headline is a `<p>` styled as one.
 * The table is hidden on phones, not removed, so it stays in the markup for
 * search while the head-to-head switcher takes its place.
 */
export function HomeCompare() {
	return (
		<section className={sectionSpacing.foot}>
			<div className={cn("text-center", sectionSpacing.head)}>
				<HomeBadge>How it compares</HomeBadge>
				<p className={cn(siteText.h2, "mt-4")}>Getting started, compared</p>
			</div>

			<div className="mt-10 hidden md:block lg:mt-14">
				<CompareTable />
			</div>
			<div className="mt-8 md:hidden">
				<CompareHeadToHead />
			</div>
		</section>
	);
}
